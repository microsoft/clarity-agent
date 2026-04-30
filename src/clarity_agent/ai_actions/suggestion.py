"""Cross-cutting document suggestion tool.

Provides a tool for any process to record suggestions about project
documents (e.g., "stakeholders.md should include adversarial actors").
Suggestions are written to the permanent suggestion box mailbox.

Usable independently by any process — brainstorming, failure analysis,
solution design, etc.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clarity_agent.llm.types import ToolUseBlock
from clarity_agent.protocol.mailbox import Mailbox, ensure_suggestion_box

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class RawSuggestion:
    """A suggestion to update a project document."""

    title: str
    source: str
    target_document: str
    suggestion: str
    rationale: str = ""


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

RECORD_SUGGESTION_TOOL: dict[str, Any] = {
    "name": "record_suggestion",
    "description": (
        "Record a suggestion to update a project document. "
        "Use this when your analysis reveals information that should "
        "be added to or updated in an existing document (e.g., new "
        "adversarial stakeholders discovered during analysis)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": (
                    "Short descriptive title for the suggestion "
                    "(e.g., 'Add stalker adversary to stakeholders')"
                ),
            },
            "target_document": {
                "type": "string",
                "description": (
                    "The document to update, as a path relative to "
                    ".clarity-protocol/ (e.g., 'goal/stakeholders.md')"
                ),
            },
            "suggestion": {
                "type": "string",
                "description": (
                    "The suggested content to add or change. "
                    "Be specific enough that someone can act on this "
                    "without needing to redo the analysis."
                ),
            },
            "rationale": {
                "type": "string",
                "description": (
                    "Optional: why this update is needed — what "
                    "analysis led to this suggestion"
                ),
            },
        },
        "required": ["title", "target_document", "suggestion"],
    },
}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_suggestion_markdown(suggestion: RawSuggestion) -> str:
    """Render a RawSuggestion as markdown content for the suggestion box."""
    parts: list[str] = [
        f"# {suggestion.title}\n\n",
        f"**Source:** {suggestion.source}\n",
        f"**Target:** {suggestion.target_document}\n",
        f"\n{suggestion.suggestion}\n",
    ]
    if suggestion.rationale:
        parts.append(
            f"\n## Rationale\n\n"
            f"{suggestion.rationale}\n"
        )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Core function (shared by handler and CLI)
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str, max_len: int = 50) -> str:
    """Convert a title to a filename-safe slug."""
    slug: str = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug[:max_len]


def record_suggestion(
    protocol_dir: Path,
    title: str,
    target_document: str,
    suggestion: str,
    *,
    source: str = "conversation",
    rationale: str = "",
) -> tuple[Path, str]:
    """Record a suggestion to the suggestion box.

    Returns (path, confirmation_message).
    """
    raw = RawSuggestion(
        title=title,
        source=source,
        target_document=target_document,
        suggestion=suggestion,
        rationale=rationale,
    )
    content: str = render_suggestion_markdown(raw)
    box: Mailbox = ensure_suggestion_box(protocol_dir)
    slug: str = _slugify(title)
    path: Path = box.write(slug, content)
    return path, f"Recorded suggestion: {title}"


# ---------------------------------------------------------------------------
# Tool handler (for API backends)
# ---------------------------------------------------------------------------

def handle_record_suggestion(
    tc: ToolUseBlock,
    protocol_dir: Path,
    source: str = "conversation",
) -> tuple[Path, str]:
    """Handle a record_suggestion tool call.

    Returns (path, confirmation_message).
    """
    inp: dict[str, Any] = tc.input
    return record_suggestion(
        protocol_dir,
        title=inp["title"],
        target_document=inp["target_document"],
        suggestion=inp["suggestion"],
        source=source,
        rationale=inp.get("rationale", ""),
    )


# ---------------------------------------------------------------------------
# CLI entry point (for SDK/Bash path)
# ---------------------------------------------------------------------------

def _find_protocol_dir() -> Path:
    """Locate the protocol directory from cwd, walking up if needed."""
    from clarity_agent.app_paths import find_protocol_dir
    return find_protocol_dir()


def _cli_main() -> None:
    """CLI: python -m clarity_agent.ai_actions.suggestion record < input.json

    Auto-discovers .clarity-protocol from the working directory.
    No flags required.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m clarity_agent.ai_actions.suggestion",
        description="Record a document suggestion. Reads JSON from stdin.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("record", help="Record a suggestion (JSON on stdin)")

    args = parser.parse_args()
    if args.command != "record":
        parser.error("a command is required (e.g. 'record')")

    data: dict[str, Any] = json.load(sys.stdin)
    path, msg = record_suggestion(
        _find_protocol_dir(),
        title=data["title"],
        target_document=data["target_document"],
        suggestion=data["suggestion"],
        source=data.get("source", "conversation"),
        rationale=data.get("rationale", ""),
    )
    print(msg)
    print(f"Path: {path}")


if __name__ == "__main__":
    _cli_main()
