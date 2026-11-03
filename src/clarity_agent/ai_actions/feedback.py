"""Feedback tool for the Clarity Agent.

Provides a tool that any process can use to let users send product
feedback.  Available in all processes and free chat.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from clarity_agent.feedback import (
    FeedbackReport,
    gather_llm_info,
    gather_transcript,
    prepare_feedback,
)
from clarity_agent.llm.types import ToolCallback, ToolUseBlock

# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

SEND_FEEDBACK_TOOL: dict[str, Any] = {
    "name": "send_feedback",
    "description": (
        "Prepare a GitHub issue for product feedback from the user to the "
        "Clarity Agent team. Only use this after the user asks to share "
        "feedback, report a bug, or suggest an improvement. Before calling, "
        "ask the user: "
        "(1) what their message is, "
        "(2) whether we may contact them for more information and if so "
        "their email address, "
        "(3) whether to attach LLM backend info (default yes), "
        "(4) whether to attach recent transcript turns or other relevant context. "
        "The tool returns a link where the user can review and submit the issue."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The user's feedback message.",
            },
            "contact_ok": {
                "type": "boolean",
                "description": (
                    "Whether the user consents to being contacted "
                    "for more information about their feedback."
                ),
            },
            "contact_email": {
                "type": "string",
                "description": (
                    "The user's email address, if they consent to "
                    "being contacted. Omit if contact_ok is false."
                ),
            },
            "include_llm_info": {
                "type": "boolean",
                "description": (
                    "Whether to attach information about the LLM "
                    "backend and models in use. Default: true."
                ),
            },
            "transcript_turns": {
                "type": "integer",
                "description": (
                    "Number of recent transcript turns to attach. "
                    "0 or omitted means do not attach transcript."
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "Optional additional context relevant to understanding "
                    "the feedback."
                ),
            },
        },
        "required": ["message"],
    },
}


# ---------------------------------------------------------------------------
# Handler factory
# ---------------------------------------------------------------------------

def create_feedback_handler(
    project_dir: Path,
    *,
    provider: str | None = None,
    model: str | None = None,
    active_model: str | None = None,
    on_tool_use: ToolCallback | None = None,
) -> Callable[[ToolUseBlock], str]:
    """Create a tool handler for feedback tool calls.

    Returns a callable conforming to the ``ToolHandler`` protocol.
    Returns a prefilled GitHub issue for the user to review and submit.
    """

    def handle(tc: ToolUseBlock) -> str:
        if tc.name != "send_feedback":
            return f"Unknown tool: {tc.name}"

        inp: dict[str, Any] = tc.input

        # Gather optional context.
        llm_info: dict[str, str] = {}
        if inp.get("include_llm_info", True):
            llm_info = gather_llm_info(
                provider, model, active_model,
            )

        transcript: str | None = None
        turns = inp.get("transcript_turns", 0)
        if turns and turns > 0:
            transcript = gather_transcript(project_dir, turns)

        report = FeedbackReport(
            message=inp["message"],
            contact_ok=inp.get("contact_ok", False),
            contact_email=inp.get("contact_email", ""),
            llm_info=llm_info,
            transcript_excerpt=transcript,
            context=inp.get("context"),
        )

        result = prepare_feedback(report)

        if on_tool_use:
            on_tool_use("send_feedback", "GitHub issue draft prepared")
        return (
            "A GitHub issue draft has been prepared. Ask the user to review "
            f"and submit it using this link: {result.issue_url}"
        )

    return handle


def create_feedback_tools() -> list[dict[str, Any]]:
    """Return the tool schema list for the feedback tool."""
    return [SEND_FEEDBACK_TOOL]
