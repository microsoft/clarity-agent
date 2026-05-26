"""Release-feed abstraction + version comparison.

The :class:`ReleaseFeed` protocol is the seam that makes the update
flow unit-testable.  Production code uses :class:`GitHubReleaseFeed`,
which talks to the real GitHub Releases API.  Tests substitute a
stub instance — no network, no signing keys, no special build mode
required.

What this module does NOT do: download binaries, verify signatures,
swap a running app's executable.  Those are the Tauri updater
plugin's responsibility on the desktop binary path, and they're
exercised end-to-end via the ``PRETEND_TO_BE_VERSION`` mechanism
documented in :mod:`~clarity_agent.setup.version` — there's no point
mocking them on the Python side because the production code that
matters here lives in Rust.

What this module *does* do, all of which is fully testable:

  * Parse and compare version strings (:func:`is_newer`).
  * Translate "GitHub Releases API JSON" into a typed
    :class:`ReleaseInfo`.
  * Orchestrate "what's my current version, what's the latest, is
    there an update?" (:func:`check_for_update`).

Stdlib-only on purpose so the updater can run before pip has
finished installing third-party deps.
"""

from __future__ import annotations

import json
import platform
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, Protocol

from .version import VersionInfo, current_version

#: The repository the production feed talks to.  Single source of
#: truth — referenced by ``GitHubReleaseFeed`` as the default and by
#: any external diagnostics that need to display the upstream URL.
DEFAULT_REPO = "microsoft/clarity-agent"


# ---------------------------------------------------------------------------
# Result shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReleaseInfo:
    """One release as seen on the feed.

    ``version`` is the tag string verbatim (e.g. ``"v1.2.3"``); the
    leading ``v`` is preserved so it matches what
    :func:`~clarity_agent.setup.version.current_version` returns
    for a stamped release.

    ``release_url`` is the GitHub Release page (``html_url`` from
    the API) — the human-facing URL the v1 update badge links to.
    Defaulted to ``""`` so test fixtures that don't care about it
    can keep constructing :class:`ReleaseInfo` with just the
    version/assets pair.

    ``assets`` maps a Tauri-updater-style platform key (e.g.
    ``"darwin-aarch64"``, ``"windows-x86_64"``) to the asset's
    download URL.  Callers that don't care about the per-platform
    breakdown (the doctor check, the "you're behind" banner) can
    ignore it.
    """

    version: str
    assets: dict[str, str]
    release_url: str = ""


@dataclass(frozen=True)
class UpdateAvailability:
    """The result of asking "should I update?"

    Three states encoded in ``status``:

      * ``"available"`` — a newer release than the running version
        exists.  ``latest`` is populated.
      * ``"up_to_date"`` — running version is the latest (or newer
        than the feed, which can happen with local pretend-tests).
        ``latest`` is populated.
      * ``"unknown"`` — couldn't ask (non-release build, feed error,
        no releases yet).  ``latest`` may be ``None``.
    """

    status: Literal["available", "up_to_date", "unknown"]
    current: VersionInfo
    latest: ReleaseInfo | None = None
    reason: str | None = None
    """Free-text reason set when status is ``"unknown"`` — e.g.
    ``"not a release build"`` or ``"network error: …"`` — so the
    UI can render an informative tooltip."""


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------


_VERSION_NUMERIC_RE = re.compile(r"^v?(\d+(?:\.\d+)*)")
"""Anchored leading-numeric prefix.  Match groups[0] gives the
dotted-int portion; anything after (``-rc1``, ``-dev``, ``+build``)
becomes the suffix used for pre-release ordering."""


def _parse(v: str) -> tuple[tuple[int, ...], str]:
    """Split a version string into ``(numeric_tuple, suffix)``.

    Examples:
        ``"v1.2.3"``       → ``((1, 2, 3), "")``
        ``"1.2.3-rc1"``    → ``((1, 2, 3), "-rc1")``
        ``"v0.10"``        → ``((0, 10), "")``
        ``"local"``        → ``((), "local")`` — non-comparable
        ``""`` / garbage   → ``((), v)``

    The empty-tuple sentinel for non-numeric strings is what makes
    :func:`is_newer` return False whenever either side isn't a real
    version — comparing ``"local"`` against ``"v1.2.3"`` should
    never claim an update is available.
    """
    m = _VERSION_NUMERIC_RE.match(v.strip())
    if not m:
        return ((), v)
    numeric = tuple(int(x) for x in m.group(1).split("."))
    suffix = v.strip()[m.end():]
    return (numeric, suffix)


def is_newer(candidate: str, current: str) -> bool:
    """Return True iff *candidate* is a strictly newer version than *current*.

    Comparison rules:

    1. Both strings are parsed into ``(numeric_tuple, suffix)``.  A
       non-numeric string (``"local"``, garbage) parses to an empty
       tuple and is **never** considered newer than anything.  This
       is what keeps the update path quiet on dev / source builds.
    2. Numeric tuples compare lexicographically; missing trailing
       components are treated as ``0`` (``v1.2`` == ``v1.2.0``).
    3. When the numeric portions are equal, a release with **no
       suffix** beats one with a pre-release suffix (``v1.2.3`` >
       ``v1.2.3-rc1``).  This matches PEP 440 / semver convention.
    4. When both have suffixes and numerics tie, lexicographic
       suffix comparison breaks the tie — coarse but adequate for
       Clarity's ``-rc<N>`` / ``-beta<N>`` style.  We don't
       implement full PEP 440 pre-release ordering because it's
       overkill for the conventions we'll actually use.
    """
    cand_num, cand_suffix = _parse(candidate)
    curr_num, curr_suffix = _parse(current)

    if not cand_num or not curr_num:
        return False

    # Pad to equal length so v1.2 vs v1.2.0 compares equal.
    width = max(len(cand_num), len(curr_num))
    cand_padded = cand_num + (0,) * (width - len(cand_num))
    curr_padded = curr_num + (0,) * (width - len(curr_num))

    if cand_padded != curr_padded:
        return cand_padded > curr_padded

    # Numerics tie — suffix rules.
    if cand_suffix == curr_suffix:
        return False
    if not cand_suffix:
        # Release vs pre-release of same numeric: release wins.
        return True
    if not curr_suffix:
        # Pre-release vs release of same numeric: pre-release loses.
        return False
    return cand_suffix > curr_suffix


# ---------------------------------------------------------------------------
# Feed abstraction
# ---------------------------------------------------------------------------


class ReleaseFeed(Protocol):
    """A source of release metadata.  Production talks to GitHub;
    tests substitute an in-memory stub.  Methods may raise on
    network / parse failures — :func:`check_for_update` catches
    and translates these into ``UpdateAvailability(status="unknown")``.
    """

    def latest(self) -> ReleaseInfo | None:
        """Return the most recent release, or ``None`` if the feed
        has no releases yet (e.g. brand-new repo).  Raise on
        network errors so the orchestrator can distinguish "feed
        says nothing" from "couldn't ask"."""
        ...


class GitHubReleaseFeed:
    """Production :class:`ReleaseFeed` — queries the GitHub Releases
    REST API.  Single short HTTP request per call; no auth required
    for public repos.
    """

    def __init__(
        self,
        repo: str = DEFAULT_REPO,
        *,
        timeout: float = 10.0,
    ) -> None:
        self._repo = repo
        self._timeout = timeout

    def latest(self) -> ReleaseInfo | None:
        url = f"https://api.github.com/repos/{self._repo}/releases/latest"
        req = urllib.request.Request(
            url, headers={"Accept": "application/vnd.github+json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                # Brand-new repo, no releases yet.  Distinct from
                # "couldn't reach the server" — let the orchestrator
                # report this as ``up_to_date`` against ``None``.
                return None
            raise
        return _parse_release(data, repo=self._repo)


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def check_for_update(
    feed: ReleaseFeed | None = None,
    current: VersionInfo | None = None,
) -> UpdateAvailability:
    """Tell the caller whether an update is available.

    Both parameters default to production values
    (:class:`GitHubReleaseFeed` and :func:`current_version`) but
    accept stubs so unit tests can exercise every branch without
    network access.

    Returns a typed :class:`UpdateAvailability`:

      * Non-release builds always return ``status="unknown"`` with
        a ``reason`` of ``"not a release build"`` — we don't try to
        update source clones or locally-built frozen binaries from
        here.  (Source-clone updates flow through the git-based
        path in :mod:`~clarity_agent.setup.updater`; locally-built
        frozen binaries are intentionally not auto-updateable.)
      * Network / parse errors return ``status="unknown"`` with the
        error message in ``reason`` — the UI can show a quiet
        tooltip rather than a failure modal.
      * A feed result that's not strictly newer than the current
        version → ``status="up_to_date"``.
      * A feed result that *is* strictly newer → ``status="available"``.
    """
    if current is None:
        current = current_version()
    if not current.is_release:
        return UpdateAvailability(
            status="unknown", current=current,
            reason="not a release build",
        )

    if feed is None:
        feed = GitHubReleaseFeed()

    try:
        latest = feed.latest()
    except Exception as exc:
        return UpdateAvailability(
            status="unknown", current=current,
            reason=f"feed error: {exc}",
        )

    if latest is None:
        return UpdateAvailability(
            status="up_to_date", current=current, latest=None,
            reason="no releases on feed",
        )

    if is_newer(latest.version, current.version):
        return UpdateAvailability(
            status="available", current=current, latest=latest,
        )
    return UpdateAvailability(
        status="up_to_date", current=current, latest=latest,
    )


# ---------------------------------------------------------------------------
# GitHub response parsing — split out so tests can hit it directly
# ---------------------------------------------------------------------------


def _parse_release(data: dict, *, repo: str = DEFAULT_REPO) -> ReleaseInfo:
    """Translate a single GitHub Releases API response into
    :class:`ReleaseInfo`.

    Stable across the API's optional fields — the only required
    fields on the wire are ``tag_name`` and ``assets``.  Asset URLs
    are pulled from ``browser_download_url``; the platform key is
    derived from the asset's filename using
    :func:`_platform_key_for_asset` (Tauri-updater-compatible).
    ``release_url`` is read from the ``html_url`` field with a
    fallback to the conventional ``/releases/tag/<tag>`` URL — the
    fallback covers older tests/fixtures that don't include
    ``html_url`` in their payloads.
    """
    version = data.get("tag_name") or ""
    release_url = data.get("html_url") or (
        f"https://github.com/{repo}/releases/tag/{version}" if version else ""
    )
    assets: dict[str, str] = {}
    for asset in data.get("assets", []):
        name = asset.get("name") or ""
        url = asset.get("browser_download_url") or ""
        if not name or not url:
            continue
        for key in _platform_keys_for_asset(name):
            assets[key] = url
    return ReleaseInfo(version=version, assets=assets, release_url=release_url)


def _platform_keys_for_asset(filename: str) -> Iterator[str]:
    """Derive Tauri-updater-style platform keys from an asset
    filename.  Yields zero or more keys per asset (one asset can
    match multiple platforms, e.g. a universal binary).

    Conservative pattern matching — we only emit keys we're
    confident about; an unrecognized filename yields nothing and
    falls out of the assets map.
    """
    lower = filename.lower()
    if lower.endswith(".dmg") or lower.endswith(".app.tar.gz"):
        if "aarch64" in lower or "arm64" in lower:
            yield "darwin-aarch64"
        elif "x64" in lower or "x86_64" in lower:
            yield "darwin-x86_64"
        else:
            # Universal DMG — match both arches.
            yield "darwin-aarch64"
            yield "darwin-x86_64"
    elif lower.endswith(".msi") or lower.endswith(".exe.zip"):
        yield "windows-x86_64"
    elif lower.endswith(".appimage") or lower.endswith(".appimage.tar.gz"):
        yield "linux-x86_64"


def current_platform_key() -> str:
    """Return the Tauri-updater-style key for the running OS+arch.

    Used by the per-project ``/api/version`` endpoint to pick the
    right download URL out of :class:`ReleaseInfo.assets` when
    surfacing the "update available" affordance to the UI.
    """
    machine = platform.machine().lower()
    if sys.platform == "darwin":
        return "darwin-aarch64" if machine in ("arm64", "aarch64") else "darwin-x86_64"
    if sys.platform == "win32":
        return "windows-x86_64"
    return "linux-x86_64"
