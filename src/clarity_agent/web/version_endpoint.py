"""``GET /api/version`` — the runtime's self-description.

Single endpoint covering both update modes:

  * **Release binaries** (``source: "release"`` — either an actual
    stamped release or a ``PRETEND_TO_BE_VERSION`` test run) check
    the GitHub Releases feed via
    :func:`~clarity_agent.setup.release_feed.check_for_update`.
  * **Source checkouts** (``source: "local"``) check the current
    branch's upstream for new commits via
    :func:`~clarity_agent.setup.updater.check_for_updates`.

The two modes feed a discriminated ``latest`` field on the wire:
``{"kind": "release", ...}`` or ``{"kind": "git", ...}``.  Frontends
dispatch on ``latest.kind`` rather than re-deriving it from
``source``.

Caching applies only to the release-mode check (the GitHub HTTP
round-trip).  Git-mode lookups are local subprocess calls that
already finish in well under a second, and their freshness matters
more — caching them would mean the badge stays stale after a
``git fetch`` outside the app.  TTL is one hour per the design
discussion; the update check happens on-read whenever the cache
is stale.  No background task, no asyncio lifecycle plumbing, no
thrashing if the process exits early.
"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from clarity_agent.setup.release_feed import (
    ReleaseFeed,
    UpdateAvailability,
    check_for_update,
)
from clarity_agent.setup.version import VersionInfo, current_version

#: Seconds between fresh GitHub Releases queries.  One hour matches
#: the user's "best-practice cadence" call — long enough to be
#: polite to the API, short enough that users see new releases
#: within a working day.
CACHE_TTL_SECONDS = 3600

# Cached release-mode update-check result, plus the timestamp it
# was generated.  ``None`` means "never checked yet" — the next read
# refreshes.  Guarded by a lock because multiple concurrent request
# handlers can hit ``get_version_payload`` simultaneously; without
# it two threads could each see a stale cache and both fire HTTP
# requests.  Git-mode lookups are not cached (see module docstring).
_cache: tuple[float, UpdateAvailability] | None = None
_cache_lock = threading.Lock()


def reset_cache() -> None:
    """Drop the cached update check.  Used by tests to ensure a
    fresh check happens with the stub feed they're passing in.
    Production callers shouldn't need this — the TTL handles
    natural staleness.
    """
    global _cache
    with _cache_lock:
        _cache = None


def get_version_payload(
    feed: ReleaseFeed | None = None,
    agent_dir: Path | None = None,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Build the ``/api/version`` response body.

    Dispatches between release-mode and git-mode based on
    ``current_version().source`` — callers don't need to pre-classify.

    Parameters exist for tests:

      * ``feed`` — pass a stub :class:`ReleaseFeed` to avoid hitting
        GitHub.  When supplied, the cache is bypassed (no point
        caching against a stub) and the result is returned directly.
      * ``agent_dir`` — path to the clarity-agent checkout.  Required
        when the current build's ``source`` is ``"local"`` (the
        route handler threads it in from ``create_app``); ignored in
        release mode.  Tests can pass a stub path or rely on the
        ``"local"`` branch never running.
      * ``now`` — override the cache-staleness clock; lets tests
        verify TTL behavior without sleeping.
    """
    version = current_version()

    if version.source == "local":
        return _local_payload(version, agent_dir)

    # Release mode.
    if feed is not None:
        # Test path — never cache stub results, never read the cache.
        availability = check_for_update(feed=feed, current=version)
    else:
        availability = _availability_with_cache(version, now)
    return _release_payload(version, availability)


def _availability_with_cache(
    version: VersionInfo,
    now: float | None,
) -> UpdateAvailability:
    """Production-only cache read for the release-mode GitHub check.
    Pulled out so ``get_version_payload`` reads top-to-bottom
    without nesting."""
    global _cache
    current_time = now if now is not None else time.monotonic()
    with _cache_lock:
        if _cache is not None and (current_time - _cache[0]) < CACHE_TTL_SECONDS:
            return _cache[1]
        availability = check_for_update(current=version)
        _cache = (current_time, availability)
        return availability


def _release_payload(
    version: VersionInfo, availability: UpdateAvailability,
) -> dict[str, Any]:
    """Shape the wire response for a release-mode build.  ``latest``
    carries a ``kind: "release"`` discriminator so the frontend can
    dispatch alongside the git-mode shape."""
    latest_dict: dict[str, Any] | None = None
    if availability.latest is not None:
        latest_dict = {"kind": "release", **asdict(availability.latest)}
    return {
        "version": version.version,
        "source": version.source,
        "is_release": version.is_release,
        "update_status": availability.status,
        "latest": latest_dict,
        "reason": availability.reason,
    }


def _local_payload(
    version: VersionInfo, agent_dir: Path | None,
) -> dict[str, Any]:
    """Shape the wire response for a source-checkout build.

    Per the v1 design (issue #48): the badge surfaces only when
    there are upstream commits ahead of the current branch.  No
    upstream branch, detached HEAD, or feed errors → ``unknown``
    with a reason; the badge stays silent and the tooltip can
    explain.  An equal local/remote is ``up_to_date``.  Only the
    ``commit_count > 0`` case yields ``"available"``.
    """
    if agent_dir is None:
        # The route is misconfigured rather than the user's setup
        # being broken — name it as such so debugging is easy.
        return _shape_local(
            version, status="unknown", reason="agent_dir not threaded into endpoint",
            latest=None,
        )

    from clarity_agent.setup.updater import check_for_updates
    try:
        status = check_for_updates(agent_dir)
    except Exception as exc:
        return _shape_local(
            version, status="unknown", reason=f"git error: {exc}", latest=None,
        )

    if not status.available:
        # Either up-to-date or couldn't determine.  Distinguish via
        # ``remote_sha``: missing remote == lookup failure (no
        # upstream, fetch error); present remote == genuinely
        # up-to-date.
        if status.remote_sha is None:
            return _shape_local(
                version, status="unknown",
                reason="no upstream branch (or git fetch failed)",
                latest=None,
            )
        return _shape_local(version, status="up_to_date", reason=None, latest=None)

    # Update available.  Surface enough for the UI to render the
    # "N commits behind branch X" badge.
    latest = {
        "kind": "git",
        "branch": _safe_branch_name(agent_dir),
        "commit_count": status.commit_count,
        "remote_sha": (status.remote_sha or "")[:12],
    }
    return _shape_local(version, status="available", reason=None, latest=latest)


def _shape_local(
    version: VersionInfo,
    *,
    status: str,
    reason: str | None,
    latest: dict[str, Any] | None,
) -> dict[str, Any]:
    """Common envelope for the local-mode response shape — same
    top-level keys as :func:`_release_payload` so the frontend can
    read every payload uniformly."""
    return {
        "version": version.version,
        "source": version.source,
        "is_release": version.is_release,
        "update_status": status,
        "latest": latest,
        "reason": reason,
    }


def _safe_branch_name(agent_dir: Path) -> str:
    """Best-effort branch lookup for the payload.  Failures collapse
    to ``""`` rather than raising — the badge will render without a
    branch label, which is the right degradation.  We re-query here
    (rather than threading the branch out of ``check_for_updates``)
    to keep that function's contract narrow."""
    from clarity_agent.setup.updater import _git_current_branch
    return _git_current_branch(agent_dir) or ""
