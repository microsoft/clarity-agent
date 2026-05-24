"""Current-version introspection for the running clarity-agent.

Three things live here, kept small because they all conceptually
answer the same question — "what version of Clarity is this?":

  * :class:`VersionInfo` — the typed record we return everywhere.
  * :func:`current_version` — the canonical reader.  Consults the
    baked :mod:`clarity_agent._version` module, with one env-var
    override (``PRETEND_TO_BE_VERSION``) used to manually exercise
    the update flow against the real GitHub Releases feed without
    cutting a real release.
  * :data:`PRETEND_ENV_VAR` — the env-var name, exported as a
    constant so tests and docs reference it without retyping.

Everything else about updates — feed access, comparison, "should I
download" — lives in :mod:`~clarity_agent.setup.release_feed`.  This
module knows only how to read the *current* version, not how to ask
what's available.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

#: Environment variable that overrides ``__version__`` at process
#: start.  Setting it makes the binary self-report as a release at
#: the given version, which is enough to trigger the update path
#: against the real GitHub Releases feed — see the module docstring
#: in :mod:`clarity_agent._version` for the full design rationale.
#: Safe by construction: no URL override, no key bypass.  Worst case
#: if abused: the app installs the latest legitimate release.
PRETEND_ENV_VAR = "PRETEND_TO_BE_VERSION"


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
