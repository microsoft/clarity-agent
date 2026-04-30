"""Snippet insertion for integrating Clarity into a project's agent config.

Provides utilities for rendering the snippet template, detecting target files
(CLAUDE.md, AGENTS.md, etc.), and inserting/updating the snippet with
idempotent delimiters.

**Stdlib-only** — this module is imported by :mod:`~clarity_agent.setup.installer`
which runs before ``pip install``, so it must not import third-party packages.
"""

from __future__ import annotations

from pathlib import Path

BEGIN_DELIMITER = "<!-- clarity-begin -->"
END_DELIMITER = "<!-- clarity-end -->"

# Target files in priority order — first match wins.
_TARGET_CANDIDATES = ["CLAUDE.md", "AGENTS.md"]
_DEFAULT_TARGET = "AGENTS.md"


def snippet_path() -> Path:
    """Return the path to the snippet.md template bundled with this package."""
    return Path(__file__).with_name("snippet.md")


def render_snippet(processes_dir: str) -> str:
    """Read the snippet template and substitute ``{{PROCESSES_DIR}}``."""
    template = snippet_path().read_text()
    return template.replace("{{PROCESSES_DIR}}", processes_dir)


def find_target(project_dir: Path) -> Path:
    """Auto-detect the agent config file in *project_dir*.

    Returns the first existing candidate, or the default if none exist.
    """
    for name in _TARGET_CANDIDATES:
        candidate = project_dir / name
        if candidate.exists():
            return candidate
    return project_dir / _DEFAULT_TARGET


def has_snippet(target: Path) -> bool:
    """Check whether *target* already contains the clarity snippet."""
    if not target.exists():
        return False
    content = target.read_text()
    return BEGIN_DELIMITER in content and END_DELIMITER in content


def insert_snippet(target: Path, snippet: str) -> str:
    """Insert or update the clarity snippet in *target*.

    Returns one of ``"created"``, ``"updated"``, or ``"appended"``
    describing what happened.
    """
    if not target.exists():
        target.write_text(snippet)
        return "created"

    content = target.read_text()
    begin = content.find(BEGIN_DELIMITER)
    end = content.find(END_DELIMITER)

    if begin != -1 and end != -1:
        # Replace between delimiters (inclusive).
        end_of_delimiter = end + len(END_DELIMITER)
        # Consume trailing newline if present.
        if end_of_delimiter < len(content) and content[end_of_delimiter] == "\n":
            end_of_delimiter += 1
        new_content = content[:begin] + snippet + content[end_of_delimiter:]
        target.write_text(new_content)
        return "updated"

    # Append to existing file.
    separator = "\n\n" if content and not content.endswith("\n\n") else (
        "\n" if content and not content.endswith("\n") else ""
    )
    target.write_text(content + separator + snippet)
    return "appended"
