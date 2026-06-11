"""Exploration completion signal.

The ``complete_exploration`` marker is detected by
``session_manager.chat()`` in the model's response text.  No tool
infrastructure or CLI plumbing is needed — the model just includes
the phrase and the backend emits a WebSocket event.

The tool schema is kept here for reference and potential future use
with native tool-calling backends (direct Anthropic API, OpenAI).
"""

from __future__ import annotations

from typing import Any

COMPLETE_EXPLORATION_TOOL: dict[str, Any] = {
    "name": "complete_exploration",
    "description": (
        "Signal that the first-exploration session has reached its "
        "natural conclusion. Call this exactly once, in the same turn "
        "as your closing message, after you have delivered the "
        "reflection and next-action invitation. Do not call it early."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
