<!-- clarity-begin -->
## Clarity Protocol

This project uses the Clarity Protocol (`.clarity-protocol/`) for structured
thinking about problems, solutions, and failure modes.

**Before building — think when it matters.** Two triggers:

1. *The user asks.* When they want to explore what to build, clarify
   requirements, brainstorm risks, or work through a decision, call
   `run_clarity` to assess project state and get the relevant process guide.

2. *You recognize an inflection point.* Before making choices that would be
   expensive to reverse — new services, auth/trust models, data schemas,
   external integrations, significant API contracts — call `check_decision`
   with a description of what you plan to do. It returns existing decisions,
   requirements, and architecture so you can check for conflicts.

   Don't interrupt for routine implementation. The test: "If this turns out
   wrong, is it a 5-minute fix or a multi-day rework?" Interrupt for the
   latter.

**After building — keep the record current.** After completing significant
implementation work (new features, architectural changes), call
`get_packet_status` to check if protocol documents need updating. If
documents are stale, read them with `read_protocol_document`, update with
`write_protocol_document`.

Record significant architectural choices with `record_decision`.
Add risks you notice with `record_failure`.
<!-- clarity-end -->
