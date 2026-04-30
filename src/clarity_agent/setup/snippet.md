<!-- clarity-begin -->
## Clarity Protocol

This project uses the Clarity Protocol (`.clarity-protocol/`) for structured
thinking about problems, solutions, and failure modes.

**Thinking mode:** When the user is exploring what to build, requirements are
unclear, or they ask to brainstorm, clarify, or analyze risks — read and follow
`{{PROCESSES_DIR}}/clarity-agent.md`.

**Maintenance mode:** After completing significant implementation work (new
features, architectural changes, important decisions), add a task to update
protocol documents:

1. Run: `python -m clarity_agent.protocol.packet_status . --agent`
2. Update documents the tool identifies as stale or inaccurate
3. Record: `python -m clarity_agent.protocol.packet_status . --record <docs>`
<!-- clarity-end -->
