#!/usr/bin/env python3
"""
Initialize a protocol directory for a project.

Creates the directory structure, config.json, and template files.
Optionally refreshes the Clarity block in the project's ``AGENTS.md``
via :func:`~clarity_agent.setup.snippet.ensure_agents_md`.

The protocol directory's name (``.clarity-protocol/`` for embedded
git-repo projects, ``Clarity Protocol/`` for userspace ones) is
resolved per-project by :func:`clarity_agent.app_paths.protocol_dir`.

Can be used standalone (CLI) or imported as a module by the clarity
CLI (``clarity.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..setup.agent_dir import get_agent_dir

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict[str, object] = {
    "clarityAgent": {
        "path": get_agent_dir().as_posix(),
        "version": "1.0.0",
    },
    "thinkers": {
        "disabled": [],
        "custom": [],
    },
    "processes": {
        "custom": [],
    },
}


# ---------------------------------------------------------------------------
# Template files
# ---------------------------------------------------------------------------

# Keys are paths relative to .clarity-protocol/.
# Values are the file contents (minimal templates that clearly indicate
# they need to be filled in).
TEMPLATES: dict[str, str] = {
    "summary.md": """\
# [Project Title]

[Write this like you're telling a friend about something you're excited to work on. \
What's the problem that got you fired up? What's the idea? Why does it matter? \
Keep it to a few short paragraphs — enough to make someone care, not enough to bore them.]
""",
    "goal/problem.md": """\
# Problem Statement

[To be determined. Run problem clarification to develop this.]

## Why This Matters

[TBD]

## Success Criteria

[TBD]
""",
    "goal/stakeholders.md": """\
# Stakeholders

[To be determined. Run problem clarification to identify stakeholders.]
""",
    "goal/requirements.md": """\
# Requirements

[To be determined. Run problem clarification to extract requirements.]
""",
    "goal/open-questions.md": """\
# Open Questions

No open questions have been identified yet. Problem clarification will assess whether there are \
fundamental unknowns that would change the solution approach.
""",
    "goal/resolved-questions.md": """\
# Resolved Questions

No questions have been resolved yet. When open questions are resolved, they are moved here \
with their findings and resolution.
""",
    "solution/solution.md": """\
# Solution

[To be determined. Run solution brainstorming to develop this.]
""",
    "solution/architecture.md": """\
# Architecture

[To be determined. Run architecture design to develop this.]
""",
    "solution/solution-summary.md": """\
# Solution Summary

[To be determined. This summary is generated during solution brainstorming \
and updated during architecture design.]
""",
    "failures/failures.md": """\
# Failure Modes

No failure modes have been analyzed yet. Run failure analysis to begin identifying potential failures.
""",
    "decisions/decisions.md": """\
# Decisions

No decisions have been recorded yet. As important choices arise, they will be documented here.
""",
    "notes.md": """\
# Notes

[To be determined. Guiding principles and cross-phase observations will be added here as the \
project develops. Items tagged `[for: <phase>]` are actionable observations for a specific phase; \
untagged items are permanent guiding principles.]
""",
    "observations.md": """\
# Observations

No observations have been recorded yet. As failure analysis and other processes surface \
interesting patterns, coverage notes, and provenance details, they will be logged here.
""",
}


# ---------------------------------------------------------------------------
# Core operation
# ---------------------------------------------------------------------------

def init_protocol(
    project_dir: Path,
    clarity_agent_dir: Path | None = None,
) -> Path:
    """Initialize the protocol directory in *project_dir*.

    Creates the directory structure, config.json, and template files.
    If *clarity_agent_dir* is provided, also refreshes the Clarity
    block in the project's ``AGENTS.md`` via
    :func:`~clarity_agent.setup.snippet.ensure_agents_md`.

    Skips files that already exist (safe to run on a
    partially-initialized project).

    Returns the path to the protocol directory.
    """
    from clarity_agent.app_paths import protocol_dir as _protocol_dir
    protocol_dir: Path = _protocol_dir(project_dir)

    # Create directory structure
    for template_path in TEMPLATES:
        (protocol_dir / template_path).parent.mkdir(parents=True, exist_ok=True)

    # Write config.json
    config_path: Path = protocol_dir / "config.json"
    if not config_path.exists():
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
            f.write("\n")

    # Write template files
    created: list[str] = []
    for rel_path, content in TEMPLATES.items():
        full_path: Path = protocol_dir / rel_path
        if not full_path.exists():
            full_path.write_text(content, encoding="utf-8")
            created.append(rel_path)

    # Refresh the Clarity block in the project's AGENTS.md.  Embedded
    # mode if the user has explicitly installed clarity-agent into
    # this repo (``.clarity-agent/`` present); userspace otherwise.
    # Either way, ``ensure_agents_md`` is idempotent and only writes
    # if the rendered content actually differs from what's on disk.
    if clarity_agent_dir is not None:
        from ..setup.layout import (
            EMBEDDED_AGENT_SUBDIR,
            Mode,
            ProjectLayout,
        )
        from ..setup.snippet import (
            EnsureStatus,
            ensure_agents_md,
            snippet_path,
        )
        if snippet_path().exists():
            embedded_agent = project_dir / EMBEDDED_AGENT_SUBDIR
            is_embedded = embedded_agent.is_dir()
            layout = ProjectLayout(
                mode=Mode.EMBEDDED if is_embedded else Mode.USERSPACE,
                project_dir=project_dir,
                clarity_agent_dir=embedded_agent if is_embedded else clarity_agent_dir,
                protocol_dir=protocol_dir,
            )
            status = ensure_agents_md(layout)
            if status is not EnsureStatus.UNCHANGED:
                created.append(f"{layout.agents_md.name} ({status.value})")

    # Create mailbox infrastructure and the suggestion box.
    (protocol_dir / "mailboxes").mkdir(parents=True, exist_ok=True)
    (protocol_dir / "archive").mkdir(parents=True, exist_ok=True)
    from clarity_agent.protocol.mailbox import ensure_suggestion_box
    ensure_suggestion_box(protocol_dir)

    return protocol_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Initialize a .clarity-protocol/ directory for a project",
    )
    parser.add_argument(
        "project_dir",
        nargs="?",
        default=".",
        help="Project directory (default: current directory)",
    )
    parser.add_argument(
        "--clarity-agent",
        default=None,
        help="Path to clarity agent installation (inserts snippet into agent config)",
    )

    args: argparse.Namespace = parser.parse_args()

    project_dir: Path = Path(args.project_dir).resolve()
    if not project_dir.exists():
        parser.error(f"Project directory does not exist: {project_dir}")

    clarity_agent_dir: Path | None = Path(args.clarity_agent).resolve() if args.clarity_agent else get_agent_dir()
    protocol_dir: Path = init_protocol(project_dir, clarity_agent_dir)
    print(f"Initialized {protocol_dir.relative_to(project_dir)}/")


if __name__ == "__main__":
    main()
