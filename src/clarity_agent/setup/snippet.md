<!-- markdownlint-disable MD041 -->
<!-- clarity-begin -->
<!-- clarity-meta
schema_version: 1
mode: {{MODE}}
protocol_dir_name: {{PROTOCOL_DIR_NAME}}
processes_dir: {{PROCESSES_DIR}}
-->
<!-- Clarity manages this block; edits between the clarity-begin / clarity-end markers will be overwritten on the next project open. Put project-specific guidance outside the markers. -->

## Clarity Protocol

This project uses the Clarity Protocol for structured thinking about consequential decisions — what to build and why, how it should be designed, where it might fail. Protocol documents live in `{{PROTOCOL_DIR_NAME}}/`. Process guides live in `{{PROCESSES_DIR}}/`; the entry point for any Clarity work is `{{PROCESSES_DIR}}/clarity-agent.md`.

### When to engage

**Before building — think when it matters.** Two triggers:

1. *The user asks.* When they want to explore what to build, clarify requirements, brainstorm risks, or work through a decision: first check whether the `run_clarity` MCP tool is in your available tools. If it is, use the MCP tools. If it isn't, read and follow `{{PROCESSES_DIR}}/clarity-agent.md` directly. Don't ask the user which to use; make this determination yourself.

2. *You recognize an inflection point.* Before making choices that would be expensive to reverse — new services, auth/trust models, data schemas, external integrations, significant API contracts — call `check_decision` with what you plan to do. It returns existing decisions, requirements, and architecture so you can check for conflicts. Don't interrupt for routine implementation. The test: "If this turns out wrong, is it a 5-minute fix or a multi-day rework?" Interrupt for the latter.

**After building — keep the record current.** After significant implementation work (new features, architectural changes), call `get_packet_status` to find stale protocol documents. Update them with `read_protocol_document` / `write_protocol_document`. Record significant choices with `record_decision`; add risks with `record_failure`.

### Behaviors (apply throughout)

**Move quickly through what's obvious.** Many processes have multiple steps, but sometimes the answer to a step is already clear from context. When it is, just do it — write the result and present a summary for confirmation. Don't stop to ask permission at every small step. The goal is a natural conversation, not a checklist. Reserve interactive discussion for genuine ambiguity, tradeoffs, or decisions that need the user's judgment.

**Keep outputs narrative but brief.** All `.md` files in this project — protocol documents, process guides, and instructions — are repeatedly read by both humans and LLMs. They should read as smooth, concise narrative: easy to understand on first read, with nothing that wastes the reader's attention. A reader must immediately understand both the "what" and the "why." Cut anything that doesn't carry meaningful information. Since many of these files are instructions for LLMs which create further `.md` files, they should encourage the same discipline.

**Use `{{PROTOCOL_DIR_NAME}}/notes.md` as shared memory.** At the start of every process, read `{{PROTOCOL_DIR_NAME}}/notes.md` for guiding principles and cross-phase observations. When you notice something worth remembering — a design philosophy, a team constraint, an insight relevant to a future phase — add it. Tag actionable items for a specific phase with `[for: <phase>]` (e.g., `[for: failure-analysis] Authentication is a single point of failure`). When acting on a tagged item, remove it. Keep the file compact: consolidate redundant entries and remove items that have been absorbed into the relevant protocol documents.

**Generate threat model artifacts.** When writing or updating `solution/architecture.md`, include a Mermaid threat model diagram directly in the file as a fenced ` ```mermaid ` block — the packet generator extracts it automatically. Write the diagram yourself; you'll produce a better diagram than any code generator. Also write `{{PROTOCOL_DIR_NAME}}/system-design.json` with structured component/flow/threat data for tooling. After failure brainstorming or analysis, write `{{PROTOCOL_DIR_NAME}}/threat-model.md` — a concise threat model summary (1-2 pages max) with top risks, severities, one-line mitigations, and single points of failure.

<!-- clarity-end -->
