"""Unified runtime-state introspection — the canonical "what
clarity-agent am I" library.

Single source of truth for "what version am I, what kind of build
am I, what branch+SHA am I on if I'm a checkout, is there an
update available?"  Every consumer that wants any of that — the
web ``/api/version`` endpoint, the CLI ``doctor`` command, the
startup banner, a future menu-bar item — should go through this
module rather than re-deriving pieces from the lower-level
modules.

Two behaviors live here:

  * :func:`current_version` (+ :data:`PRETEND_ENV_VAR`) — the
    baked-version-string reader.  Stdlib-only.  Reads the
    committed ``_version.py`` defaults, honoring the
    ``PRETEND_TO_BE_VERSION`` env-var override used for manual
    E2E testing.

  * :func:`current_state` — the orchestrator that builds on top.
    Adds git branch+SHA introspection in local mode, dispatches
    to the GitHub release feed in release mode, returns the
    discriminated update payload that the sidebar consumes.

Their return types (:class:`VersionInfo`, :class:`RuntimeState`,
etc.) live in :mod:`~clarity_agent.setup.types` so each behavioral
module (this one, ``release_feed``, ``updater``) imports its
peers' shapes without forming a load-time dependency cycle.  Only
one runtime-level call still requires a lazy import: see the
comment inside
:func:`~clarity_agent.setup.release_feed.check_for_update`.

:func:`current_state` is pure: each call performs the full lookup,
including the (potentially-network-touching) update check.  Callers
that need rate-limiting should add their own cache; the web
endpoint does this with a 1-hour TTL on release-mode results.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Literal

from .release_feed import check_for_update
from .types import (
    GitState,
    GitUpdate,
    ReleaseInfo,
    RuntimeState,
    UpdateStatus,
    UpdateStatusLiteral,
    VersionInfo,
)
from .updater import (
    _git_current_branch,
    _git_head,
    check_for_updates,
)

# Re-exported so the public surface stays as ``setup.version`` for
# every caller, even though the shapes physically live in
# ``setup.types``.  ``current_state`` is THE canonical entry point;
# everything else here is a building block kept callable for tests
# and direct use but documented as secondary.
__all__ = [
    "CACHE_TTL_SECONDS",
    "PRETEND_ENV_VAR",
    "GitState",
    "ReleaseInfo",
    "RuntimeState",
    "UpdateStatusLiteral",
    "VersionInfo",
    "current_state",
    "current_version",
    "reset_cache",
]


# ---------------------------------------------------------------------------
# Baked-version reader (stdlib-only — feeds release_feed + updater)
# ---------------------------------------------------------------------------

#: Environment variable that overrides ``__version__`` at process
#: start.  Setting it makes the binary self-report as a release at
#: the given version, which is enough to trigger the update path
#: against the real GitHub Releases feed — see the module docstring
#: in :mod:`clarity_agent._version` for the full design rationale.
#: Safe by construction: no URL override, no key bypass.  Worst case
#: if abused: the app installs the latest legitimate release.
PRETEND_ENV_VAR = "PRETEND_TO_BE_VERSION"


def current_version() -> VersionInfo:
    """Return the running binary's version metadata.

    Precedence:

    1. ``PRETEND_TO_BE_VERSION`` env var, if set.  Forces source
       to ``"release"`` so the update flow activates.  Used for
       manual E2E testing of the updater against the real GitHub
       Releases feed; see :data:`PRETEND_ENV_VAR`.
    2. The baked :mod:`clarity_agent._version` module (stamped by
       release CI for actual releases; defaults to ``"local"``
       otherwise).
    3. ``"local"`` / ``"local"`` if even the baked module can't be
       imported (defensive — that would be a packaging bug).
    """
    pretend = os.environ.get(PRETEND_ENV_VAR)
    if pretend:
        return VersionInfo(version=pretend, source="release")

    try:
        from clarity_agent import _version
    except ImportError:
        return VersionInfo(version="local", source="local")

    # The baked file's ``__build_source__`` is constrained to the
    # ``Literal`` we accept; coerce defensively in case someone
    # hand-edits ``_version.py`` to something unexpected.
    source: Literal["release", "local"] = (
        "release" if _version.__build_source__ == "release" else "local"
    )
    return VersionInfo(version=_version.__version__, source=source)


# ---------------------------------------------------------------------------
# Runtime-state orchestrator
#
# ``current_state`` is the canonical entry point.  It owns the
# release-mode cache (1-hour TTL — polite to the GitHub API);
# local-mode results bypass the cache so a ``git fetch`` outside
# the app shows up on next refresh.
#
# Data shapes (``GitState``, ``RuntimeState``, the update-target
# union members) live in :mod:`~clarity_agent.setup.types`.  Only
# the behavior — dispatch, caching, git introspection, status
# translation — lives here.
# ---------------------------------------------------------------------------


#: How long to reuse a release-mode lookup.  Long enough to be
#: polite to the GitHub API, short enough that users see new
#: releases within a working day.
CACHE_TTL_SECONDS = 3600

# Cached release-mode :class:`RuntimeState` plus the (monotonic)
# timestamp it was generated.  ``None`` means "never checked yet".
# Guarded by a lock so concurrent ``/api/version`` requests don't
# both fire a GitHub round-trip on cache miss.
_cache: tuple[float, RuntimeState] | None = None
_cache_lock = threading.Lock()


def reset_cache() -> None:
    """Drop the cached release-mode result.  Tests autouse this
    between cases; production code rarely needs it (the TTL handles
    natural staleness and ``force_refresh=True`` handles the
    "I-suspect-stale" case)."""
    global _cache
    with _cache_lock:
        _cache = None


def current_state(
    agent_dir: Path | None = None,
    *,
    force_refresh: bool = False,
    now: float | None = None,
) -> RuntimeState:
    """Return the complete runtime state of the running binary.

    The single canonical entry point.  Dispatches on
    :attr:`VersionInfo.source`:

    * Release builds (stamped or ``PRETEND_TO_BE_VERSION``) go
      through the GitHub Releases feed via
      :func:`~clarity_agent.setup.release_feed.check_for_update`.
      Cached for :data:`CACHE_TTL_SECONDS` so repeated reads don't
      hammer the API.  ``git`` is ``None``; ``agent_dir`` is ignored.
    * Source-checkout builds go through the local git layer via
      :func:`~clarity_agent.setup.updater.check_for_updates`,
      tracking ``origin/<current-branch>``.  Never cached —
      freshness matters when the user is the one updating their
      own remote.  ``git`` is populated with the current branch +
      short SHA when available.

    Parameters:

    * ``agent_dir`` — required for local-mode lookups; passing
      ``None`` in local mode returns ``"unknown"`` with a
      "missing agent_dir" reason rather than guessing.  Release
      mode accepts ``None`` cleanly.
    * ``force_refresh`` — when True, ignore the cached release-mode
      result and recompute.  The fresh result replaces the cache,
      so subsequent reads see it.  Use this when you have reason
      to suspect the cached value is stale (e.g. just after the
      app applied an update).
    * ``now`` — test seam for the cache-TTL clock.  Production
      callers leave it at ``None``; the implementation falls back
      to :func:`time.monotonic`.

    No exceptions escape this function — git failures and feed
    errors collapse to ``status="unknown"`` with ``reason`` carrying
    the message.  Calling this is always safe.
    """
    version = current_version()

    if version.source != "release":
        # Local mode: never cached.
        return _local_state(version, agent_dir)

    return _release_state_cached(version, force_refresh=force_refresh, now=now)


def _release_state_cached(
    version: VersionInfo,
    *,
    force_refresh: bool,
    now: float | None,
) -> RuntimeState:
    """Cache-wrapped release-mode lookup.  Encapsulates the lock
    and TTL check so ``current_state`` reads top-to-bottom."""
    global _cache
    current_time = now if now is not None else time.monotonic()
    with _cache_lock:
        if (
            not force_refresh
            and _cache is not None
            and (current_time - _cache[0]) < CACHE_TTL_SECONDS
        ):
            return _cache[1]
        fresh = _release_state(version)
        _cache = (current_time, fresh)
        return fresh


# ---------------------------------------------------------------------------
# Release-mode branch
# ---------------------------------------------------------------------------


def _release_state(version: VersionInfo) -> RuntimeState:
    """Build the state for a release / PRETEND_TO_BE_VERSION binary."""
    avail = check_for_update(current=version)
    return RuntimeState(
        version=version,
        git=None,
        update_status=avail.status,
        update_latest=avail.latest,
        update_reason=avail.reason,
    )


# ---------------------------------------------------------------------------
# Local-mode branch
# ---------------------------------------------------------------------------


def _local_state(
    version: VersionInfo, agent_dir: Path | None,
) -> RuntimeState:
    """Build the state for a source-checkout build.

    Two failure modes that collapse to ``"unknown"``:

    * Endpoint forgot to thread ``agent_dir`` — a configuration
      bug.  Surfaced loudly so debugging is obvious.
    * Any exception from the git subprocess layer (no ``.git/``
      directory, no ``git`` binary, network failure on fetch).
      Caught and reported in ``reason``.
    """
    if agent_dir is None:
        return RuntimeState(
            version=version, git=None,
            update_status="unknown",
            update_latest=None,
            update_reason="agent_dir not provided",
        )

    git = _git_state(agent_dir)

    try:
        status = check_for_updates(agent_dir)
    except Exception as exc:
        return RuntimeState(
            version=version, git=git,
            update_status="unknown",
            update_latest=None,
            update_reason=f"git error: {exc}",
        )

    return _local_update_state(version, git, status)


def _git_state(agent_dir: Path) -> GitState:
    """Best-effort branch + SHA snapshot.  Failures collapse to
    empty strings — the UI uses absence to fall back to the
    generic "local" label."""
    try:
        branch = _git_current_branch(agent_dir) or ""
    except Exception:
        branch = ""
    try:
        local_sha = _git_head(agent_dir)[:12]
    except Exception:
        local_sha = ""
    return GitState(branch=branch, local_sha=local_sha)


def _local_update_state(
    version: VersionInfo, git: GitState, status: UpdateStatus,
) -> RuntimeState:
    """Translate an :class:`UpdateStatus` into the
    :class:`RuntimeState` update fields.

    Three branches in the update-availability axis:

    * ``available=True`` → ``status="available"`` with a
      :class:`GitUpdate` carrying the branch/commit-count/SHA.
    * ``available=False`` with a known ``remote_sha`` → genuinely
      up to date.
    * ``available=False`` with ``remote_sha is None`` → couldn't
      determine (no upstream branch, fetch failed, detached HEAD).
      Surfaces as ``"unknown"`` so the badge stays silent and the
      tooltip explains.
    """
    if status.available:
        return RuntimeState(
            version=version, git=git,
            update_status="available",
            update_latest=GitUpdate(
                branch=git.branch,
                commit_count=status.commit_count,
                remote_sha=(status.remote_sha or "")[:12],
            ),
            update_reason=None,
        )

    if status.remote_sha is None:
        return RuntimeState(
            version=version, git=git,
            update_status="unknown",
            update_latest=None,
            update_reason="no upstream branch (or git fetch failed)",
        )

    return RuntimeState(
        version=version, git=git,
        update_status="up_to_date",
        update_latest=None,
        update_reason=None,
    )
