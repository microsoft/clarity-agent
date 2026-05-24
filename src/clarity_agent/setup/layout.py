"""Project layout abstraction — the typed handle for everything that
varies between project install styles.

Three modes exist (see :class:`Mode`); each is a clean 1:1 mapping
from install style to filesystem layout, with no hybrids:

  * **EMBEDDED** — a git repository the user explicitly installed
    Clarity into (``clarity install --embedded``).  Clarity's code
    lives at ``.clarity-agent/`` inside the repo; the protocol dir
    is ``.clarity-protocol/`` (hidden, doesn't clutter the working
    tree); the AGENTS.md snippet uses repo-relative paths so the
    file commits identically across machines.

  * **USERSPACE** — a regular project directory opened from the
    desktop / web app.  Clarity's code lives in the app bundle (the
    user never sees it); the protocol dir is ``Clarity Protocol/``
    (visible, since non-technical users need to find it); the
    AGENTS.md snippet uses absolute install paths.

  * **CLARITY_AGENT_SOURCE** — the one unusual project: the
    clarity-agent source repo itself, dogfooded.  Detected
    structurally (``clarity.py`` at the root + ``src/clarity_agent/``
    subdirectory).  ``project_dir == clarity_agent_dir``; protocol
    dir is ``.clarity-protocol/``; processes render as just
    ``processes`` because the repo *is* the agent — no
    ``.clarity-agent/`` prefix.  The AGENTS.md is hand-curated and
    must not be auto-rewritten; ``ensure_agents_md`` skips this
    mode.

The asymmetries are concentrated here.  Downstream code takes a
:class:`ProjectLayout` and asks it questions instead of branching on
mode every time it needs a path.

Detection (:func:`detect_layout`) is read-only: it inspects what's on
disk and reports either a layout, ``None`` (no Clarity setup yet —
caller may run an explicit setup flow), or :class:`LayoutBroken`
(partial / inconsistent install — caller should surface a repair
prompt rather than guess).  The function never writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# The directory name an embedded install uses for the clarity-agent
# code inside the host project.  Matches ``installer.CLARITY_DIR``;
# the constant lives here so layout-aware code never has to import
# the heavier ``installer`` module just for one string.
EMBEDDED_AGENT_SUBDIR = ".clarity-agent"

# The two possible names for the protocol directory.  Kept in sync
# with :data:`clarity_agent.app_paths._PROTOCOL_DIR_DOT` /
# :data:`_PROTOCOL_DIR_VISIBLE` — exported here so layout-aware code
# doesn't need to reach into ``app_paths``'s private surface.
PROTOCOL_DIR_DOT = ".clarity-protocol"
PROTOCOL_DIR_VISIBLE = "Clarity Protocol"

# Markers a project may have that suggest it's a code repo (rather
# than a non-technical user's workspace folder).  Used by the flow-3
# "looks like code directory?" decision to pick which install-mode
# default to recommend in the SetupPromptDialog.  Generous on
# purpose — EMBEDDED is only the recommendation, never forced.  Add
# more as needed (Mercurial ``.hg/``, Perforce ``.p4config``, etc.).
_CODE_DIRECTORY_MARKERS: tuple[str, ...] = (
    ".git",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
)

# Markers that uniquely identify the clarity-agent source repo
# itself.  Both must be present; together they're specific enough
# that no other repo will trip the structural detection.  See
# :class:`Mode.CLARITY_AGENT_SOURCE` for why this mode exists.
_CLARITY_AGENT_SOURCE_MARKERS: tuple[str, ...] = (
    "clarity.py",
    "src/clarity_agent",
)


class Mode(Enum):
    """How a project relates to its Clarity install."""

    EMBEDDED = "embedded"
    USERSPACE = "userspace"
    CLARITY_AGENT_SOURCE = "clarity_agent_source"


class LayoutBroken(Enum):
    """Why a directory's layout couldn't be detected as a clean
    Clarity project.  Returned by :func:`detect_layout` (in place of
    a :class:`ProjectLayout`) when the caller needs to know the
    *kind* of brokenness to surface an actionable prompt.
    """

    AMBIGUOUS_PROTOCOL_DIRS = "ambiguous_protocol_dirs"
    """Both ``.clarity-protocol/`` and ``Clarity Protocol/`` exist
    in the same project.  We refuse to pick one silently; the user
    must resolve before we proceed."""

    PARTIAL_EMBEDDED_INSTALL = "partial_embedded_install"
    """``.clarity-protocol/`` is present but ``.clarity-agent/`` is
    not — looks like the embedded install was started but didn't
    finish (or the user manually created the protocol dir in a git
    repo without running the install)."""


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
    bundle directory passed in by the caller; in CLARITY_AGENT_SOURCE
    it's ``project_dir`` itself (the repo *is* the agent)."""

    protocol_dir: Path
    """Absolute path to the protocol directory.  Name is determined
    by ``mode`` (see :data:`PROTOCOL_DIR_DOT` / :data:`PROTOCOL_DIR_VISIBLE`):
    EMBEDDED and CLARITY_AGENT_SOURCE use the dotted name; USERSPACE
    uses the visible name."""

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

        Three forms, one per mode:

        - **EMBEDDED**: ``.clarity-agent/processes`` — repo-relative
          so the rendered file commits identically across machines.
        - **USERSPACE**: absolute path to the bundled processes dir
          — the bundle lives outside the project, no relative path
          makes sense.
        - **CLARITY_AGENT_SOURCE**: ``processes`` — bare relative
          path, because the repo IS clarity-agent (no
          ``.clarity-agent/`` subdirectory layer above the
          processes directory).
        """
        if self.mode is Mode.EMBEDDED:
            return f"{EMBEDDED_AGENT_SUBDIR}/processes"
        if self.mode is Mode.CLARITY_AGENT_SOURCE:
            return "processes"
        return self.processes_dir.as_posix()

    def protocol_dir_name(self) -> str:
        """The leaf name of the protocol directory (``.clarity-protocol``
        or ``Clarity Protocol``) — what callers want to substitute into
        the rendered snippet body, where an absolute path would be
        wrong (the body is read in-project, so the path is implicitly
        project-relative)."""
        return self.protocol_dir.name


# ---------------------------------------------------------------------------
# Structural predicates
# ---------------------------------------------------------------------------


def looks_like_clarity_agent_source(project_dir: Path) -> bool:
    """True iff *project_dir* looks like the clarity-agent source
    repository itself.

    Requires every marker in :data:`_CLARITY_AGENT_SOURCE_MARKERS`
    to be present (``clarity.py`` file + ``src/clarity_agent/``
    package directory).  Both together are specific enough that no
    other project will match.  Used to route detection toward
    :data:`Mode.CLARITY_AGENT_SOURCE` and to make
    :func:`ensure_for_project` skip the dogfooding case.
    """
    return all((project_dir / marker).exists() for marker in _CLARITY_AGENT_SOURCE_MARKERS)


def looks_like_code_directory(project_dir: Path) -> bool:
    """True iff *project_dir* has any marker suggesting it's a code
    repository (rather than a non-technical user's workspace).

    Used by the flow-3 "open ambiguous directory" prompt to pick
    which install-mode default to recommend: code-like → EMBEDDED
    suggested (with USERSPACE permitted as an override),
    everything else → USERSPACE only.  Match is generous on purpose
    — false positives just mean the SetupPromptDialog offers both
    options, which is fine.
    """
    return any((project_dir / marker).exists() for marker in _CODE_DIRECTORY_MARKERS)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def detect_layout(
    project_dir: Path,
    *,
    bundled_clarity_agent_dir: Path,
) -> ProjectLayout | LayoutBroken | None:
    """Inspect *project_dir* and report its layout.

    Three possible return shapes:

    - :class:`ProjectLayout` — clean, recognized layout for one of
      the three modes.
    - :class:`LayoutBroken` — the directory has Clarity markers but
      they're inconsistent (partial install, both protocol-dir
      names, etc.).  Caller should surface a repair prompt rather
      than guess; the variant tells the caller *what* to say.
    - ``None`` — no Clarity markers at all.  Caller may proceed
      with an explicit setup flow (flow 1 "create new" or flow 3
      "open ambiguous" + user confirmation).

    Function is read-only; safe to call speculatively at any
    project-open hook.

    Detection precedence (deliberately structural, never heuristic):

    1. **CLARITY_AGENT_SOURCE**: structural markers
       (``clarity.py`` + ``src/clarity_agent/``) present →
       :data:`Mode.CLARITY_AGENT_SOURCE`.  Checked first so the
       dogfooding case is recognized before any other rules can
       claim it.
    2. **EMBEDDED**: ``.clarity-agent/`` + ``.clarity-protocol/``
       both present → clean :data:`Mode.EMBEDDED`.
    3. **USERSPACE**: ``Clarity Protocol/`` present (without the
       embedded marker) → clean :data:`Mode.USERSPACE`.
    4. **Brokenness** (these checks come *after* the clean cases):
       - Both ``.clarity-protocol/`` and ``Clarity Protocol/``
         present → :data:`LayoutBroken.AMBIGUOUS_PROTOCOL_DIRS`.
       - ``.clarity-protocol/`` present without ``.clarity-agent/``
         (i.e. not the source repo, and not a clean userspace) →
         :data:`LayoutBroken.PARTIAL_EMBEDDED_INSTALL`.
       - ``.clarity-agent/`` present without ``.clarity-protocol/``
         → :data:`LayoutBroken.PARTIAL_EMBEDDED_INSTALL` (same
         remedy: complete the install).
    5. No markers → ``None``.
    """
    project_dir = project_dir.resolve()

    # Source-repo case is structural and takes precedence.  It also
    # has its own ``.clarity-protocol/`` inside, which would
    # otherwise trip the PARTIAL_EMBEDDED_INSTALL branch — checking
    # first sidesteps that.
    if looks_like_clarity_agent_source(project_dir):
        return ProjectLayout(
            mode=Mode.CLARITY_AGENT_SOURCE,
            project_dir=project_dir,
            clarity_agent_dir=project_dir,
            protocol_dir=project_dir / PROTOCOL_DIR_DOT,
        )

    embedded_agent = project_dir / EMBEDDED_AGENT_SUBDIR
    dot_protocol = project_dir / PROTOCOL_DIR_DOT
    visible_protocol = project_dir / PROTOCOL_DIR_VISIBLE

    has_embedded_marker = embedded_agent.is_dir()
    has_dot_protocol = dot_protocol.is_dir()
    has_visible_protocol = visible_protocol.is_dir()

    # Clean EMBEDDED: both markers present and consistent.
    if has_embedded_marker and has_dot_protocol and not has_visible_protocol:
        return ProjectLayout(
            mode=Mode.EMBEDDED,
            project_dir=project_dir,
            clarity_agent_dir=embedded_agent.resolve(),
            protocol_dir=dot_protocol,
        )

    # Clean USERSPACE: visible protocol dir present, no embedded
    # marker, no competing dotted protocol dir.
    if has_visible_protocol and not has_embedded_marker and not has_dot_protocol:
        return ProjectLayout(
            mode=Mode.USERSPACE,
            project_dir=project_dir,
            clarity_agent_dir=bundled_clarity_agent_dir.resolve(),
            protocol_dir=visible_protocol,
        )

    # Brokenness cases — return a specific variant so the caller
    # can surface an actionable prompt rather than a generic "we
    # don't know what to do with this directory."
    if has_dot_protocol and has_visible_protocol:
        return LayoutBroken.AMBIGUOUS_PROTOCOL_DIRS
    if has_embedded_marker and not has_dot_protocol:
        return LayoutBroken.PARTIAL_EMBEDDED_INSTALL
    if has_dot_protocol and not has_embedded_marker:
        return LayoutBroken.PARTIAL_EMBEDDED_INSTALL

    # No markers — caller decides what to do next.
    return None
