<!-- clarity-begin -->
<!-- clarity-version: 2 -->
## Clarity Protocol

This project uses the Clarity Protocol (`.clarity-protocol/`) for structured
thinking about problems, solutions, and failure modes.

**Before building — think when it matters.** Two triggers:

1. *The user asks.* When they want to explore what to build, clarify
   requirements, brainstorm risks, or work through a decision — use the
   `run_clarity` tool (or read `{{PROCESSES_DIR}}/clarity-agent.md`).

2. *You recognize an inflection point.* Before making choices that would be
   expensive to reverse — new services, auth/trust models, data schemas,
   external integrations, significant API contracts — call `check_decision`
   with a description of what you plan to do. If that tool surfaces conflicts
   with existing decisions or requirements, pause and resolve them. If no
   Clarity MCP tools are available, check `.clarity-protocol/decisions/` and
   `.clarity-protocol/goal/requirements.md` directly.

   Don't interrupt for routine implementation. The test: "If this turns out
   wrong, is it a 5-minute fix or a multi-day rework?" Interrupt for the
   latter.

**After building — keep the record current.** After completing significant
implementation work (new features, architectural changes), call
`get_packet_status` to check whether protocol documents need updating.
If no Clarity MCP tools are available:

1. Run: `python -m clarity_agent.protocol.packet_status . --agent`
2. Update documents the tool identifies as stale or inaccurate
3. Record: `python -m clarity_agent.protocol.packet_status . --record <docs>`
<!-- clarity-end -->
