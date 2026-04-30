"""Failure brainstorming tools.

Provides tools for the failure-brainstorming process: recording failure
modes, recommending specialist thinkers for deeper analysis, and reading
thinker methodology guides.

Tools are delivered to the AI via ``ChatBackend.chat(tools=...,
tool_handler=...)`` for API backends, or as CLI commands via Bash for
the SDK backend.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from clarity_agent.ai_actions.suggestion import (
    RECORD_SUGGESTION_TOOL,
    handle_record_suggestion,
)
from clarity_agent.llm.types import ToolCallback, ToolUseBlock
from clarity_agent.protocol.mailbox import Mailbox
from clarity_agent.protocol.thinker_registry import ThinkerInfo

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ChainAnnotation:
    """An annotation on a failure chain step."""

    type: str  # "intervention_point", "observation", "branch_point"
    content: str


@dataclass
class ChainStep:
    """A single step in a failure chain."""

    step_number: int
    description: str
    annotations: list[ChainAnnotation] = field(default_factory=list)
    harm_begins: bool = False
    harm_ends: bool = False


@dataclass
class RawFailure:
    """A single raw failure mode captured during analysis."""

    title: str
    source: str
    description: str
    additional_context: str = ""
    failure_chain: list[ChainStep] = field(default_factory=list)
    pre_existing: bool | None = None


@dataclass
class DeeperAnalysisRecommendation:
    """A recommendation to run a specialist thinker for deeper analysis."""

    thinker_name: str
    rationale: str


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

RECORD_FAILURE_TOOL: dict[str, Any] = {
    "name": "record_failure",
    "description": (
        "Record a potential failure mode discovered during analysis. "
        "Call this once for each distinct failure mode you identify."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short descriptive title of what could go wrong",
            },
            "description": {
                "type": "string",
                "description": (
                    "1-3 sentences: what goes wrong, how it happens, "
                    "and who is harmed. Must end in actual harm."
                ),
            },
            "additional_context": {
                "type": "string",
                "description": (
                    "Optional: more detail about severity, related concerns, "
                    "initial thoughts on the failure chain"
                ),
            },
            "pre_existing": {
                "type": "boolean",
                "description": (
                    "Optional: true if this failure also exists (at similar "
                    "or greater severity) in the world before this solution "
                    "is implemented. Helps triage during analysis."
                ),
            },
            "failure_chain": {
                "type": "array",
                "description": (
                    "Optional annotated failure chain — a sequence of "
                    "steps describing how this failure unfolds. Include "
                    "this when you can see the chain of events clearly. "
                    "Each step can be annotated with intervention points, "
                    "observations, branch points, and harm boundary markers."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "step_number": {
                            "type": "integer",
                            "description": "Step number in the chain (1-based)",
                        },
                        "description": {
                            "type": "string",
                            "description": "What happens at this step",
                        },
                        "annotations": {
                            "type": "array",
                            "description": (
                                "Intervention points, observations, or "
                                "branch points on this step"
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": [
                                            "intervention_point",
                                            "observation",
                                            "branch_point",
                                        ],
                                        "description": "Type of annotation",
                                    },
                                    "content": {
                                        "type": "string",
                                        "description": "The annotation text",
                                    },
                                },
                                "required": ["type", "content"],
                            },
                        },
                        "harm_begins": {
                            "type": "boolean",
                            "description": "True if harm begins at this step",
                        },
                        "harm_ends": {
                            "type": "boolean",
                            "description": "True if harm ends at this step",
                        },
                    },
                    "required": ["step_number", "description"],
                },
            },
        },
        "required": ["title", "description"],
    },
}

RECOMMEND_DEEPER_ANALYSIS_TOOL: dict[str, Any] = {
    "name": "recommend_deeper_analysis",
    "description": (
        "Recommend a specialized thinker for deeper analysis in a specific "
        "area. Call this when your broad analysis reveals an area where a "
        "specialist thinker would find failures that your general analysis "
        "cannot cover in sufficient depth."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "thinker_name": {
                "type": "string",
                "description": (
                    "The name of the specialized thinker to recommend "
                    "(from the available thinkers list)"
                ),
            },
            "rationale": {
                "type": "string",
                "description": (
                    "Why this specialist would add value for this "
                    "particular system — what specific areas or concerns "
                    "make their expertise relevant"
                ),
            },
        },
        "required": ["thinker_name", "rationale"],
    },
}

READ_THINKER_GUIDE_TOOL: dict[str, Any] = {
    "name": "read_thinker_guide",
    "description": (
        "Read a specialist thinker's methodology guide. Use this when you "
        "want to apply a specialist's analytical framework to discover "
        "failures their expertise would reveal."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "thinker_name": {
                "type": "string",
                "description": (
                    "The name of the specialist thinker whose guide "
                    "to read (from the available thinkers list)"
                ),
            },
        },
        "required": ["thinker_name"],
    },
}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_ANNOTATION_LABELS: dict[str, str] = {
    "intervention_point": "Intervention point",
    "observation": "Observation",
    "branch_point": "Branch point",
}


def render_chain_markdown(chain: list[ChainStep]) -> str:
    """Render a failure chain to markdown.

    Produces numbered steps with inline annotations, harm boundary
    markers, and indented sub-items for intervention points,
    observations, and branch points.
    """
    parts: list[str] = []
    for step in chain:
        desc: str = step.description
        if step.harm_begins:
            desc += " **harm begins**"
        if step.harm_ends:
            desc += " **harm ends**"
        parts.append(f"{step.step_number}. {desc}\n")

        for ann in step.annotations:
            label: str = _ANNOTATION_LABELS.get(ann.type, ann.type)
            parts.append(f"   - *{label}:* {ann.content}\n")

    return "".join(parts)


def render_failure_markdown(failure: RawFailure) -> str:
    """Render a RawFailure as markdown content for a mailbox file."""
    parts: list[str] = [
        f"# {failure.title}\n\n",
        f"**Source:** {failure.source}\n",
    ]
    if failure.pre_existing is not None:
        label: str = "Yes" if failure.pre_existing else "No"
        parts.append(f"**Pre-existing:** {label}\n")
    parts.append(f"\n{failure.description}\n")
    if failure.failure_chain:
        parts.append(
            f"\n## Failure Chain\n\n"
            f"{render_chain_markdown(failure.failure_chain)}"
        )
    if failure.additional_context:
        parts.append(
            f"\n## Additional Context\n\n"
            f"{failure.additional_context}\n"
        )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Core functions (shared by handler and CLI)
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str, max_len: int = 50) -> str:
    """Convert a title to a filename-safe slug."""
    slug: str = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug[:max_len]


def _parse_chain(raw_chain: list[dict[str, Any]]) -> list[ChainStep]:
    """Parse a failure chain from tool call input into ChainStep objects."""
    steps: list[ChainStep] = []
    for raw_step in raw_chain:
        annotations: list[ChainAnnotation] = [
            ChainAnnotation(type=a["type"], content=a["content"])
            for a in raw_step.get("annotations", [])
        ]
        steps.append(ChainStep(
            step_number=raw_step["step_number"],
            description=raw_step["description"],
            annotations=annotations,
            harm_begins=raw_step.get("harm_begins", False),
            harm_ends=raw_step.get("harm_ends", False),
        ))
    return steps


FAILURE_MAILBOX_NAME: str = "failure-brainstorm"


def record_failure(
    protocol_dir: Path,
    title: str,
    description: str,
    *,
    source: str = "conversation",
    additional_context: str = "",
    pre_existing: bool | None = None,
    failure_chain: list[dict[str, Any]] | None = None,
) -> tuple[Path, str]:
    """Record a failure mode to the failure-brainstorm mailbox.

    Returns (path, confirmation_message).
    """
    chain: list[ChainStep] = _parse_chain(failure_chain) if failure_chain else []
    raw = RawFailure(
        title=title,
        source=source,
        description=description,
        additional_context=additional_context,
        failure_chain=chain,
        pre_existing=pre_existing,
    )
    content: str = render_failure_markdown(raw)

    mailbox_config: dict[str, Any] = {
        "display_name": "failure brainstorming",
        "collector": "failure-analysis",
        "collector_type": "batch",
        "status": "collecting",
    }
    mailbox: Mailbox = Mailbox.open_or_create(
        protocol_dir, FAILURE_MAILBOX_NAME, mailbox_config,
    )

    slug: str = _slugify(title)
    path: Path = mailbox.write(slug, content)

    pre_marker = " (pre-existing)" if pre_existing else ""
    return path, f"Recorded failure: {title}{pre_marker}"


def read_thinker_guide(agent_dir: Path, thinker_name: str) -> str:
    """Read a specialist thinker's methodology guide.

    Returns the full guide content.
    """
    guide_path: Path = agent_dir / "thinkers" / f"{thinker_name}.md"
    if not guide_path.exists():
        return f"Error: thinker guide not found at {guide_path}"
    return guide_path.read_text()


# ---------------------------------------------------------------------------
# Tool handler (for API backends)
# ---------------------------------------------------------------------------

def create_brainstorm_handler(
    protocol_dir: Path,
    agent_dir: Path,
    on_tool_use: ToolCallback | None = None,
    source: str = "conversation",
) -> Callable[[ToolUseBlock], str]:
    """Create a stateless tool handler for brainstorm tool calls.

    Dispatches tool calls to core functions and fires *on_tool_use*
    callbacks for progress reporting.  Returns a callable conforming
    to the ``ToolHandler`` protocol.
    """

    def handle(tc: ToolUseBlock) -> str:
        if tc.name == "record_failure":
            inp: dict[str, Any] = tc.input
            _, msg = record_failure(
                protocol_dir,
                title=inp["title"],
                description=inp["description"],
                source=source,
                additional_context=inp.get("additional_context", ""),
                pre_existing=inp.get("pre_existing"),
                failure_chain=inp.get("failure_chain"),
            )
            if on_tool_use:
                on_tool_use("record_failure", msg)
            return msg

        if tc.name == "record_suggestion":
            _, msg = handle_record_suggestion(
                tc, protocol_dir, source=source,
            )
            if on_tool_use:
                on_tool_use("record_suggestion", msg)
            return msg

        if tc.name == "recommend_deeper_analysis":
            inp = tc.input
            msg = f"Noted recommendation: {inp['thinker_name']} — {inp['rationale']}"
            if on_tool_use:
                on_tool_use("recommend_deeper_analysis", msg)
            return msg

        if tc.name == "read_thinker_guide":
            content = read_thinker_guide(agent_dir, tc.input["thinker_name"])
            if on_tool_use:
                on_tool_use(
                    "read_thinker_guide",
                    f"Reading guide: {tc.input['thinker_name']}",
                )
            return content

        return f"Unknown tool: {tc.name}"

    return handle


# ---------------------------------------------------------------------------
# Tool set creation
# ---------------------------------------------------------------------------

def create_brainstorm_tools(
    available_thinkers: list[ThinkerInfo] | None = None,
) -> list[dict[str, Any]]:
    """Return tool schemas for the brainstorming process.

    Always includes ``record_failure`` and ``record_suggestion``.
    Includes ``recommend_deeper_analysis`` and ``read_thinker_guide``
    only when specialist thinkers are available.
    """
    tools: list[dict[str, Any]] = [RECORD_FAILURE_TOOL, RECORD_SUGGESTION_TOOL]
    if available_thinkers:
        tools.append(RECOMMEND_DEEPER_ANALYSIS_TOOL)
        tools.append(READ_THINKER_GUIDE_TOOL)
    return tools


def format_available_thinkers(thinkers: list[ThinkerInfo]) -> str:
    """Format specialist thinker info for inclusion in a system prompt."""
    lines: list[str] = [
        "## Available Specialist Thinkers\n",
        "The following specialists are available for deeper analysis. "
        "Use `recommend_deeper_analysis` to flag areas where their expertise "
        "would add value. Use `read_thinker_guide` to load their methodology "
        "when you want to apply their perspective directly.\n",
    ]
    for t in thinkers:
        lines.append(f"- **{t.display_name}** (`{t.name}`): {t.description}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point (for SDK/Bash path)
# ---------------------------------------------------------------------------

def _find_protocol_dir() -> Path:
    """Locate the protocol directory from cwd, walking up if needed."""
    from clarity_agent.app_paths import find_protocol_dir
    return find_protocol_dir()


def _find_agent_dir() -> Path:
    """Locate the clarity-agent installation directory."""
    # The thinkers/ dir is alongside the package source
    return Path(__file__).resolve().parent.parent.parent.parent


def _cli_main() -> None:
    """CLI: python -m clarity_agent.ai_actions.brainstorm <command> < input.json

    All paths are auto-discovered from the working directory.
    No flags required.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m clarity_agent.ai_actions.brainstorm",
        description="Brainstorm tools CLI. Reads JSON from stdin.",
    )
    sub = parser.add_subparsers(dest="command")

    # record-failure
    sub.add_parser("record-failure", help="Record a failure mode (JSON on stdin)")

    # recommend-deeper
    sub.add_parser("recommend-deeper", help="Recommend deeper analysis (JSON on stdin)")

    # read-thinker-guide
    sub.add_parser("read-thinker-guide", help="Read a thinker guide (JSON on stdin)")

    args = parser.parse_args()

    if args.command == "record-failure":
        data: dict[str, Any] = json.load(sys.stdin)
        path, msg = record_failure(
            _find_protocol_dir(),
            title=data["title"],
            description=data["description"],
            source=data.get("source", "conversation"),
            additional_context=data.get("additional_context", ""),
            pre_existing=data.get("pre_existing"),
            failure_chain=data.get("failure_chain"),
        )
        print(msg)
        print(f"Path: {path}")

    elif args.command == "recommend-deeper":
        data = json.load(sys.stdin)
        print(f"Noted recommendation: {data['thinker_name']}")
        print(f"Rationale: {data['rationale']}")

    elif args.command == "read-thinker-guide":
        data = json.load(sys.stdin)
        content = read_thinker_guide(_find_agent_dir(), data["thinker_name"])
        print(content)

    else:
        parser.error("a command is required")


if __name__ == "__main__":
    _cli_main()
