"""AI actions for the Clarity Agent framework.

Provides tool schemas, handlers, and CLI entry points for actions used
by AI-driven processes. Actions are delivered to the AI differently
depending on the backend:

- **API backends** (Anthropic, OpenAI, Azure): native tool-use via
  ``ChatBackend.chat(tools=..., tool_handler=...)``
- **SDK backend** (Claude Agent SDK): tools are formatted as CLI
  command documentation and prepended to the system prompt; the AI
  invokes them via Bash.

Modules:
    suggestion  Cross-cutting document suggestion tool.
    brainstorm  Failure brainstorming tools.
    feedback    User feedback tool.
"""

from __future__ import annotations

import json
from typing import Any

# Map tool names to their CLI module and subcommand.
_CLI_MAP: dict[str, tuple[str, str]] = {
    "record_failure": ("clarity_agent.ai_actions.brainstorm", "record-failure"),
    "record_suggestion": ("clarity_agent.ai_actions.suggestion", "record"),
    "recommend_deeper_analysis": ("clarity_agent.ai_actions.brainstorm", "recommend-deeper"),
    "read_thinker_guide": ("clarity_agent.ai_actions.brainstorm", "read-thinker-guide"),
}


def format_tools_as_cli(tools: list[dict[str, Any]]) -> str:
    """Generate Bash command documentation from tool schemas.

    Used by :class:`SdkChatBackend` to tell the AI how to invoke
    process tools via Bash.  The CLI tools auto-discover
    ``.clarity-protocol`` from the working directory, so no flags
    are needed — just a subcommand and JSON on stdin.
    """
    lines: list[str] = [
        "## Process Tools — Bash Commands\n",
        "You have process tools. Invoke them **via Bash** using the "
        "exact commands below. Each reads JSON from stdin.\n",
    ]

    for tool in tools:
        name: str = tool.get("name", "unknown")
        desc: str = tool.get("description", "")
        mapping = _CLI_MAP.get(name)
        if mapping is None:
            continue
        module, command = mapping
        cmd = f"python -m {module} {command}"

        # Build a minimal example showing required fields.
        schema = tool.get("input_schema", {})
        required = set(schema.get("required", []))
        example: dict[str, str] = {p: f"<{p}>" for p in required}
        example_json = json.dumps(example, indent=2)

        lines.append(f"**{name}** — {desc.split('.')[0]}.\n")
        lines.append(
            f"```bash\n"
            f"{cmd} << 'EOF'\n"
            f"{example_json}\n"
            f"EOF\n"
            f"```\n"
        )

    return "\n".join(lines)
