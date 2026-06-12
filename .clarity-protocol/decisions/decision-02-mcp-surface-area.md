# Decision: MCP Tool Surface Area

**Status:** decided
**Date:** 2026-06-08

## Context

The MCP server needed a tool surface for coding agents. The Python codebase has ~20+ callable functions (init_protocol, list_processes, read_process_guide, generate_packet, get_mailbox_status, check_failure_state, snapshot_mailbox, list_mailbox_items, read_mailbox_item, archive_mailbox_item, etc.). Exposing all of them would create a large, confusing tool surface that coding agents would struggle to navigate effectively.

## Decision

Expose exactly 8 tools as the public MCP surface. All other functions remain importable Python for the web/CLI/desktop modes but are hidden from MCP clients.

The 8 tools are organized around three workflow moments:
- **Before acting:** `check_decision`
- **Assess and navigate:** `run_clarity`, `get_packet_status`
- **Read, write, record:** `read_protocol_document`, `write_protocol_document`, `record_decision`, `record_failure`, `record_suggestion`

Additionally, 6 MCP resources provide passive context: `clarity://summary`, `clarity://decisions`, `clarity://behaviors`, `clarity://processes/{name}`, `clarity://thinkers/{name}`, and `clarity://protocol/{path}`.

## Rationale

A coding agent needs a focused set of actions, not a menu of everything the system can do. The key insight: `run_clarity` handles routing (it inlines the appropriate process guide), so the agent doesn't need separate process-discovery or process-selection tools. Similarly, `write_protocol_document` auto-records content hashes, eliminating the need for a separate `record_packet_status` tool.

The internal functions remain available for the web UI, CLI, and desktop app where a richer interface is appropriate and the user has different interaction patterns (browsing, clicking, selecting).

## Alternatives Considered

- **Expose everything as MCP tools (~20+ tools):** Rejected — coding agents perform worse with large tool surfaces; they waste tokens deliberating which tool to call and make more errors.
- **Expose a minimal 3-tool surface (run_clarity, read, write):** Rejected — `check_decision` and `record_decision` serve distinct workflow moments that shouldn't be folded into generic read/write; `record_failure` and `record_suggestion` write to specific mailbox structures that are hard to replicate with raw file writes.
- **Dynamic tool registration based on project state:** Over-engineered for current needs; revisit if the surface needs to grow.

## Consequences

- Coding agents have a clear, memorable tool surface they can use effectively without detailed documentation.
- New capabilities default to internal-only; promoting to MCP requires deliberate consideration.
- The web/CLI/desktop modes have richer capabilities than the MCP surface — this is intentional, not a gap.
