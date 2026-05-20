"""``AppManifest`` describing clarity-agent for RAMPART.

Enumerates only what evaluators currently need to reference — the
four ``ai_actions`` tools the agent is offered during structured
phases (failure brainstorming, suggestion drops) and the
``.clarity-protocol/`` filesystem surface.  The implicit Bash /
Read / Write tools that the SDK backend exposes aren't declared
because no Phase-1 evaluator references them; add them when one
does.
"""

from __future__ import annotations

from rampart import AppManifest, DataSource, ToolDeclaration

# Tool names match ``clarity_agent.ai_actions._CLI_MAP`` keys.  Keep
# in sync with that module — when an action is added or renamed
# upstream, mirror the change here.
_TOOLS: list[ToolDeclaration] = [
    ToolDeclaration(
        name="record_failure",
        description=(
            "Record a single failure mode to the failures mailbox during "
            "brainstorming.  Each call appends one structured failure "
            "(title, causal chain, severity)."
        ),
    ),
    ToolDeclaration(
        name="record_suggestion",
        description=(
            "Drop a cross-cutting suggestion against any protocol "
            "document for the user to review later."
        ),
    ),
    ToolDeclaration(
        name="recommend_deeper_analysis",
        description=(
            "Flag a thinker (specialist guide) the framework should "
            "invoke for deeper analysis on a specific topic."
        ),
    ),
    ToolDeclaration(
        name="read_thinker_guide",
        description=(
            "Load the markdown body of a named thinker so the agent "
            "can follow its instructions inline."
        ),
    ),
]

_DATA_SOURCES: list[DataSource] = [
    DataSource(
        name=".clarity-protocol",
        type="filesystem",
        # Only the agent and the local user write here.  Eval runs
        # are sandboxed to a temp project dir per session.
        writable_by_untrusted=False,
    ),
]

CLARITY_AGENT_MANIFEST = AppManifest(
    name="clarity-agent",
    description=(
        "Protocol-driven assistant.  Drives a multi-step process guide "
        "(default ``clarity-agent.md``) that writes structured design "
        "artifacts under ``.clarity-protocol/`` and brainstorms failure "
        "modes via specialist thinkers."
    ),
    tools=_TOOLS,
    data_sources=_DATA_SOURCES,
)
