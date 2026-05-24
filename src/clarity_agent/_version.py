"""Version metadata baked at build time.

This module's *committed* contents are the defaults — ``"local"`` for
both the version string and the source kind — covering every
"running from source" scenario (developer clone, ``clarity web`` on
a checkout, ``clarity install --release`` locally without going
through release CI, …).

The **release CI** overwrites this file before invoking PyInstaller,
stamping in the git tag and ``__build_source__ = "release"``.  The
release workflow's stamping step is the *only* writer of release
metadata — there is no other code path that produces a "release"
build, by design.  See
:func:`clarity_agent.setup.version.current_version` for the
read-side, including the ``PRETEND_TO_BE_VERSION`` env-var override
used to manually exercise the update flow against the real GitHub
Releases feed without cutting a real release.

Don't edit this file by hand — it is intentionally minimal so the
release CI can rewrite it deterministically.
"""

from __future__ import annotations

__version__: str = "local"
"""Either a release tag like ``"v1.2.3"`` (stamped by release CI) or
the literal ``"local"`` for any non-CI build."""

__build_source__: str = "local"
"""Either ``"release"`` (release CI build) or ``"local"`` (anything
else)."""
