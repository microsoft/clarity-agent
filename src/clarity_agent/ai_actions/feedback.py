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
    gather_protocol,
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
        "Send product feedback from the user to the Clarity Agent team. "
        "Use this when the user wants to share feedback, report a bug, "
        "or suggest an improvement. Before calling, ask the user: "
        "(1) what their message is, "
        "(2) whether we may contact them for more information and if so "
        "their email address, "
        "(3) whether to attach LLM backend info (default yes), "
        "(4) whether to attach recent transcript turns, "
        "(5) whether to attach the full clarity protocol."
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
            "include_protocol": {
                "type": "boolean",
                "description": (
                    "Whether to attach the entire clarity protocol. "
                    "Default: false."
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
    active_tier: str | None = None,
    on_tool_use: ToolCallback | None = None,
) -> Callable[[ToolUseBlock], str]:
    """Create a tool handler for feedback tool calls.

    Returns a callable conforming to the ``ToolHandler`` protocol.
    Tries to upload feedback; falls back to local save + mailto.
    """

    def handle(tc: ToolUseBlock) -> str:
        if tc.name != "send_feedback":
            return f"Unknown tool: {tc.name}"

        inp: dict[str, Any] = tc.input

        # Gather optional context.
        llm_info: dict[str, str] = {}
        if inp.get("include_llm_info", True):
            llm_info = gather_llm_info(
                provider, model, active_model, active_tier,
            )

        transcript: str | None = None
        turns = inp.get("transcript_turns", 0)
        if turns and turns > 0:
            transcript = gather_transcript(project_dir, turns)

        protocol: str | None = None
        if inp.get("include_protocol", False):
            protocol = gather_protocol(project_dir)

        report = FeedbackReport(
            message=inp["message"],
            contact_ok=inp.get("contact_ok", False),
            contact_email=inp.get("contact_email", ""),
            llm_info=llm_info,
            transcript_excerpt=transcript,
            protocol_content=protocol,
        )

        result = prepare_feedback(report)

        if result.submitted:
            if on_tool_use:
                on_tool_use("send_feedback", "Feedback submitted")
            return (
                "Feedback has been submitted to the Clarity Agent team. "
                "Thank the user and let them know it was received."
            )

        if on_tool_use:
            on_tool_use(
                "send_feedback",
                f"Feedback saved to {result.file_path}",
            )
        return (
            f"Feedback could not be uploaded automatically (the upload "
            f"endpoint is not yet configured). It has been saved to "
            f"{result.file_path}. Let the user know their feedback was "
            f"saved locally and will be deliverable once the feedback "
            f"service is set up."
        )

    return handle


def create_feedback_tools() -> list[dict[str, Any]]:
    """Return the tool schema list for the feedback tool."""
    return [SEND_FEEDBACK_TOOL]
