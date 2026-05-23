"""Project layout abstraction — the typed handle for everything that
varies between embedded and userspace projects.

Two project modes exist (see :class:`Mode`):

  * **EMBEDDED** — a git repository the user explicitly installed
    Clarity into (``clarity embed`` / ``clarity install --embedded``).
    Clarity's code lives at ``.clarity-agent/`` inside the repo; the
    protocol dir is ``.clarity-protocol/`` (hidden, so it doesn't
    clutter the working tree); the AGENTS.md snippet uses paths
    relative to the repo so the file commits identically across
    machines.

  * **USERSPACE** — a regular project directory opened from the
    desktop / web app.  Clarity's code lives in the app bundle (the
    user never sees it); the protocol dir is ``Clarity Protocol/``
    (visible, since non-technical users need to find it); the
    AGENTS.md snippet uses absolute install paths.

The asymmetry is concentrated entirely here.  Downstream code takes a
:class:`ProjectLayout` and asks it questions instead of branching on
mode every time it needs a path.

Detection (:func:`detect_layout`) is read-only: it inspects what's on
disk and reports the layout it finds, or ``None`` if the project
isn't a Clarity project yet or is in an ambiguous state.  Creation /
install actions live in :mod:`clarity_agent.setup.project` (userspace
ensure) and :mod:`clarity_agent.setup.installer` (embedded install) —
``layout.py`` itself never writes to disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# The directory name an embedded install uses for the clarity-agent
# code inside the host project.  Matches ``installer.CLARITY_DIR``;
# duplicated here only because importing ``installer`` would pull in
# its third-party-light-but-large surface for what is essentially a
# constant.
EMBEDDED_AGENT_SUBDIR = ".clarity-agent"

# The two possible names for the protocol directory.  Kept in sync
# with :data:`clarity_agent.app_paths._PROTOCOL_DIR_DOT` /
# :data:`_PROTOCOL_DIR_VISIBLE` — exported here so layout-aware code
# doesn't need to reach into ``app_paths``'s private surface.
PROTOCOL_DIR_DOT = ".clarity-protocol"
PROTOCOL_DIR_VISIBLE = "Clarity Protocol"


class Mode(Enum):
    """How a project relates to its Clarity install."""

    EMBEDDED = "embedded"
    USERSPACE = "userspace"


@dataclass(frozen=True)
class ProjectLayout:
    """Resolved paths for a single project, mode-aware.

    Downstream consumers (the snippet renderer, ``ensure_agents_md``,
    the runtime LLM session) take a ``ProjectLayout`` and use its
    fields directly — no further branching on mode required.
    """

    mode: Mode
    project_dir: Path
    """Root of the user's project (where ``AGENTS.md`` lives)."""

    clarity_agent_dir: Path
    """Where Clarity's code (``processes/``, ``thinkers/``, …) lives
    *for this project*.  In EMBEDDED mode that's
    ``project_dir / ".clarity-agent"``; in USERSPACE it's the app
    bundle directory passed in by the caller."""

    protocol_dir: Path
    """Absolute path to the protocol directory.  Name varies by mode
    (see :data:`PROTOCOL_DIR_DOT` / :data:`PROTOCOL_DIR_VISIBLE`)."""

    @property
    def agents_md(self) -> Path:
        """Path to the project's ``AGENTS.md`` — always at the project
        root.  ``AGENTS.md`` is the file every modern LLM coding agent
        (Claude, GPT, …) reads by default, which is why the rendered
        snippet lives here rather than anywhere else.
        """
        return self.project_dir / "AGENTS.md"

    @property
    def processes_dir(self) -> Path:
        """Absolute path to the bundled ``processes/`` directory."""
        return self.clarity_agent_dir / "processes"

    def processes_dir_for_rendering(self) -> str:
        """Return the path to ``processes/`` as it should appear in
        the rendered AGENTS.md.

        EMBEDDED: relative to the project root
        (``.clarity-agent/processes``), so the rendered file commits
        identically across machines.  USERSPACE: absolute, because
        the bundle lives outside the project and there's no relative
        path that makes sense.
        """
        if self.mode is Mode.EMBEDDED:
            return f"{EMBEDDED_AGENT_SUBDIR}/processes"
        return self.processes_dir.as_posix()

    def protocol_dir_name(self) -> str:
        """The leaf name of the protocol directory (``.clarity-protocol``
        or ``Clarity Protocol``) — what callers want to substitute into
        the rendered snippet body, where an absolute path would be
        wrong (the body is read in-project, so the path is implicitly
        project-relative)."""
        return self.protocol_dir.name


def detect_layout(
    project_dir: Path,
    *,
    bundled_clarity_agent_dir: Path,
) -> ProjectLayout | None:
    """Inspect *project_dir* and return its :class:`ProjectLayout`.

    Returns ``None`` when the project either isn't a Clarity project
    yet (no markers present — caller may proceed with an install /
    ensure action) **or** is in an ambiguous broken state (e.g. both
    protocol-directory names present).  The function never writes;
    it's safe to call speculatively at any project-open hook.

    ``bundled_clarity_agent_dir`` is the app's bundled clarity-agent
    location (i.e. ``app_paths.get_bundle_dir()``).  Used as the
    ``clarity_agent_dir`` for USERSPACE layouts where the code lives
    outside the project entirely.

    Detection precedence (deliberately structural, never heuristic):

    1. ``.clarity-agent/`` present in *project_dir* → EMBEDDED.  The
       embedded install marker is unambiguous: the user (or installer)
       explicitly created that directory.  ``protocol_dir`` is
       ``.clarity-protocol/`` if it exists, otherwise constructed
       (the rare "embedded install half-done" case — caller can still
       run ``ensure_agents_md`` against the layout to finish setup).
    2. Both protocol-dir names present → ``None``.  An ambiguous
       project where ``ensure_agents_md`` couldn't reliably choose
       which to advertise; surface the error rather than picking.
    3. ``Clarity Protocol/`` present → USERSPACE.
    4. ``.clarity-protocol/`` present without ``.clarity-agent/`` →
       EMBEDDED.  Someone laid down the protocol dir by hand or via
       ``protocol.initialize`` without a full install; treat it as
       embedded so the snippet's relative paths match.
    5. Neither marker present → ``None``.  Caller decides what to do
       (userspace open creates the dir, embedded install errors).
    """
    project_dir = project_dir.resolve()
    embedded_agent = project_dir / EMBEDDED_AGENT_SUBDIR
    dot_protocol = project_dir / PROTOCOL_DIR_DOT
    visible_protocol = project_dir / PROTOCOL_DIR_VISIBLE

    if embedded_agent.is_dir():
        # Embedded install — protocol dir name is fixed to the dotted
        # form regardless of whether the directory has been created
        # yet (it always is for an embedded install; constructing the
        # path is just a defensive fallback for half-initialized
        # repos that ``ensure_agents_md`` will fix on the next pass).
        return ProjectLayout(
            mode=Mode.EMBEDDED,
            project_dir=project_dir,
            clarity_agent_dir=embedded_agent.resolve(),
            protocol_dir=dot_protocol,
        )

    if dot_protocol.is_dir() and visible_protocol.is_dir():
        # Ambiguous — caller must resolve before we can proceed.
        return None

    if visible_protocol.is_dir():
        return ProjectLayout(
            mode=Mode.USERSPACE,
            project_dir=project_dir,
            clarity_agent_dir=bundled_clarity_agent_dir.resolve(),
            protocol_dir=visible_protocol,
        )

    if dot_protocol.is_dir():
        # Protocol dir exists but no embedded install marker.  Treat
        # as EMBEDDED so paths render relative — matches how the
        # protocol dir was likely created (someone ran
        # ``protocol.initialize`` in a git repo).
        return ProjectLayout(
            mode=Mode.EMBEDDED,
            project_dir=project_dir,
            clarity_agent_dir=bundled_clarity_agent_dir.resolve(),
            protocol_dir=dot_protocol,
        )

    return None
