"""Shared data shapes for the ``setup`` package.

Every dataclass that crosses module boundaries lives here, so the
behavioral modules (:mod:`~clarity_agent.setup.version`,
:mod:`~clarity_agent.setup.release_feed`,
:mod:`~clarity_agent.setup.updater`) can import each others' types
without creating circular dependencies.  This module is stdlib-only
by design — it has no behavior, only shapes, and nothing in here
imports from any sibling module.

Read the docstring on each dataclass for what it represents and
which module is responsible for *producing* values of that type;
the producers are the natural place to put related logic.

There is still one runtime-level cycle this module doesn't address:
:func:`~clarity_agent.setup.release_feed.check_for_update` calls
:func:`~clarity_agent.setup.version.current_version` when its
``current`` argument is ``None``, but ``version.py`` imports
``release_feed`` at top level.  That's handled with a single
function-scope import inside ``check_for_update`` — see the
comment there.  Pulling the dataclasses out into this module
shrinks the surface area where it could matter to just that one
runtime call.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

UpdateStatusLiteral = Literal["available", "up_to_date", "unknown"]


# ---------------------------------------------------------------------------
# Version identity (produced by setup.version)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VersionInfo:
    """The running binary's self-reported version.

    Two-field record: ``version`` is either a release tag like
    ``"v1.2.3"`` or the literal ``"local"``; ``source`` is
    ``"release"`` for genuine release-CI builds (or the
    pretend-override) and ``"local"`` for everything else.
    """

    version: str
    source: Literal["release", "local"]

    @property
    def is_release(self) -> bool:
        """Convenience: True when we can ask about updates."""
        return self.source == "release"


@dataclass(frozen=True)
class GitState:
    """Local-mode introspection: branch + short HEAD SHA.

    Always present alongside ``source == "local"``; either field
    may be the empty string if the lookup failed (detached HEAD,
    no ``.git/`` directory, no ``git`` binary on PATH).  Failures
    collapse silently here — the UI uses absence to fall back to
    the generic "local" label rather than surfacing a confusing
    error to the user.
    """

    branch: str
    local_sha: str  # 12-char short SHA, or "" if unavailable


# ---------------------------------------------------------------------------
# Release-feed shapes (produced by setup.release_feed)
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

    status: UpdateStatusLiteral
    current: VersionInfo
    latest: ReleaseInfo | None = None
    reason: str | None = None
    """Free-text reason set when status is ``"unknown"`` — e.g.
    ``"not a release build"`` or ``"network error: …"`` — so the
    UI can render an informative tooltip."""


# ---------------------------------------------------------------------------
# Local-mode update shapes (produced by setup.updater)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UpdateStatus:
    """Result of :func:`~clarity_agent.setup.updater.check_for_updates`.

    A minimal git-mode summary — translated by
    :func:`~clarity_agent.setup.version._local_update_state` into the
    richer :class:`RuntimeState` shape the UI consumes.  ``remote_sha
    is None`` is the signal for "couldn't determine" (no upstream,
    fetch failed, detached HEAD); a present ``remote_sha`` with
    ``available=False`` means genuinely up-to-date.
    """

    available: bool
    local_sha: str
    remote_sha: str | None
    commit_count: int  # number of commits behind origin/<current-branch>


@dataclass(frozen=True)
class GitUpdate:
    """The local-mode counterpart to :class:`ReleaseInfo` —
    describes "what's waiting upstream" for a git-checkout build.

    Used by :class:`RuntimeState` as the ``update_latest`` payload
    when a source checkout has commits ready to pull.

    Fields:

    * ``branch`` — the local branch name (e.g. ``"main"``,
      ``"issue48-1"``).  Empty string only if the branch couldn't be
      resolved, which shouldn't reach this point.
    * ``commit_count`` — strictly positive number of commits
      ``origin/<branch>`` has that HEAD doesn't.
    * ``remote_sha`` — 12-char short SHA of the upstream tip, for
      tooltips / debugging.
    """

    branch: str
    commit_count: int
    remote_sha: str


# ---------------------------------------------------------------------------
# Unified runtime state (produced by setup.version)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeState:
    """The complete self-description of the running clarity-agent.

    The two halves:

    * **Identity** — ``version`` (always), ``git`` (when local).
      Describes what binary is running.
    * **Update availability** — ``update_status`` (always),
      ``update_latest`` (only when ``"available"``), ``update_reason``
      (typically set on ``"unknown"`` to explain why).  Describes
      whether the user should consider updating.

    ``update_latest`` is a discriminated union — :class:`ReleaseInfo`
    in release mode (with the GitHub release URL and asset map),
    :class:`GitUpdate` in local mode (with the branch, commit count,
    and upstream SHA).  Callers dispatch on ``isinstance`` (or on
    ``state.version.source``) rather than re-deriving the mode from
    other fields.
    """

    version: VersionInfo
    git: GitState | None
    update_status: UpdateStatusLiteral
    update_latest: ReleaseInfo | GitUpdate | None
    update_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable wire shape for ``/api/version``.

        Tags the discriminated ``update_latest`` union with a
        ``kind`` field so frontends can ``switch (latest.kind)``
        rather than re-deriving the mode from ``source``.  The
        ``branch`` and ``local_sha`` fields are hoisted to the top
        level (null in release mode) because the sidebar's version
        label reads them on every render — flattening them
        sidesteps a layer of nesting on the wire.
        """
        return {
            "version": self.version.version,
            "source": self.version.source,
            "is_release": self.version.is_release,
            "branch": self.git.branch if self.git else None,
            "local_sha": self.git.local_sha if self.git else None,
            "update_status": self.update_status,
            "latest": _latest_to_dict(self.update_latest),
            "reason": self.update_reason,
        }


def _latest_to_dict(
    latest: ReleaseInfo | GitUpdate | None,
) -> dict[str, Any] | None:
    """Tag the union with a ``kind`` field for the wire.  Free
    function rather than a method so :class:`ReleaseInfo` and
    :class:`GitUpdate` don't need to know they're being
    serialized — the discriminator is the consumer's concern."""
    if latest is None:
        return None
    if isinstance(latest, ReleaseInfo):
        return {"kind": "release", **asdict(latest)}
    return {"kind": "git", **asdict(latest)}
