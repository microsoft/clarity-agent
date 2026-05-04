<!-- clarity-begin -->
## Clarity Protocol

This project uses the Clarity Protocol (`.clarity-protocol/`) for structured
thinking about problems, solutions, and failure modes.

**Before building — think when it matters.** Two triggers:

1. *The user asks.* When they want to explore what to build, clarify
   requirements, brainstorm risks, or work through a decision — read and
   follow `{{PROCESSES_DIR}}/clarity-agent.md`.

2. *You recognize an inflection point.* Before making choices that would be
   expensive to reverse — new services, auth/trust models, data schemas,
   external integrations, significant API contracts — check
   `.clarity-protocol/` for existing decisions and context. If a relevant
   decision exists, follow it. If the choice contradicts existing requirements
   or architecture, surface the conflict before proceeding. If nothing exists
   and the choice is consequential, offer to think it through:
   "This is a significant architectural choice — want to spend a minute
   thinking through alternatives and risks before I build it?"

   Don't interrupt for routine implementation. The test: "If this turns out
   wrong, is it a 5-minute fix or a multi-day rework?" Interrupt for the
   latter.

**After building — keep the record current.** After completing significant
implementation work (new features, architectural changes), check whether
protocol documents need updating:

1. Run: `python -m clarity_agent.protocol.packet_status . --agent`
2. Update documents the tool identifies as stale or inaccurate
3. Record: `python -m clarity_agent.protocol.packet_status . --record <docs>`
<!-- clarity-end -->
