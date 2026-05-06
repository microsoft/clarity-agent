# Clarity Agent Guidelines

## Behaviors

These apply to all clarity-agent processes and interactions:

**Move quickly through what's obvious.** Many processes have multiple steps, but sometimes the
answer to a step is already clear from context. When it is, just do it — write the result and
present a summary for confirmation. Don't stop to ask permission at every small step. The goal is a
natural conversation, not a checklist. Reserve interactive discussion for genuine ambiguity,
tradeoffs, or decisions that need the user's judgment.

**Keep outputs narrative but brief.** All `.md` files in this project — protocol documents, process
guides, and instructions — are repeatedly read by both humans and LLMs. They should read as smooth,
concise narrative: easy to understand on first read, with nothing that wastes the reader's
attention. A reader must immediately understand both the "what" and the "why." Cut anything that
doesn't carry meaningful information. Since many of these files are instructions for LLMs which
create further `.md` files, they should encourage the same discipline.

**Use `notes.md` as shared memory.** At the start of every process, read
`.clarity-protocol/notes.md` for guiding principles and cross-phase observations. When you notice
something worth remembering — a design philosophy, a team constraint, an insight relevant to a
future phase — add it. Tag actionable items for a specific phase with `[for: <phase>]` (e.g.,
`[for: failure-analysis] Authentication is a single point of failure`). When acting on a tagged
item, remove it. Keep the file compact: consolidate redundant entries and remove items that have
been absorbed into the relevant protocol documents.

**Generate threat model artifacts.** When writing or updating `solution/architecture.md`, include a
Mermaid threat model diagram directly in the file as a fenced ` ```mermaid ` block — the packet
generator extracts it automatically. Write the diagram yourself; you'll produce a better diagram
than any code generator. Also write `.clarity-protocol/system-design.json` with structured
component/flow/threat data for tooling. After failure brainstorming or analysis, write
`.clarity-protocol/threat-model.md` — a concise threat model summary (1-2 pages max) with top
risks, severities, one-line mitigations, and single points of failure.

## Commands

```bash
# Install all dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run a single test file
uv run pytest tests/test_packet_status.py

# Run a single test by name
uv run pytest tests/test_packet_status.py::TestPacketStatus::test_something

# Lint
uv run ruff check .

# Type check
uv run pyright

# Run the web UI (headless, against a project dir)
uv run python clarity.py web /tmp/test-project

# Run the CLI
uv run python clarity.py cli /tmp/test-project

# Run the desktop app
uv run python clarity.py app

# Rebuild the React frontend (only when changing web/ source)
cd web && npm install && npm run build

# Frontend dev server with hot-reloading (proxies /api and /ws to :8420)
# Terminal 1: uv run python clarity.py web /tmp/test-project
# Terminal 2: cd web && npm run dev
```

## Architecture

### Mental model: process guides are the program; Python is the stdlib

`processes/` contains markdown files that act as the control flow — an LLM reads and executes them. `src/clarity_agent/` contains Python infrastructure those processes call. `clarity.py` is the entry point.

### Entry point and routing

`processes/clarity-agent.md` is "main". It checks whether `.clarity-protocol/` exists, runs `packet_status.py` to assess state, and routes to the correct process guide. After any process completes, control returns here.

`src/clarity_agent/protocol/packet_status.py` is the build system / flow controller. It maintains a SHA-256 dependency graph among protocol documents (stored in `config.json`) and detects when a dependency has changed since a document was last accepted. The first stale document in topological order is what to work on next. The `--agent` flag produces markdown suitable for injection into an AI system prompt.

### Document dependency graph

```
problem → stakeholders → requirements → open-questions → solution → failures
                                                                  → architecture (↔ failures)
                                                                  → solution-summary (← solution + architecture)
```

Decisions are tracked separately via `decisionState` in `config.json`.

### Async mailbox mechanism

`src/clarity_agent/protocol/mailbox.py` handles operations where multiple actors produce results in parallel (e.g., failure brainstorming). A mailbox is a directory under `.clarity-protocol/mailboxes/<name>/`. Actors drop files in; whenever the agent runs it offers to invoke the "collector" (a process guide or Python function) on new items. Collectors must be reentrant.

### Failure brainstorming and thinkers

`thinkers/` contains specialist markdown guides with YAML frontmatter (name, type, execution, modes, prerequisites, tags). `src/clarity_agent/protocol/thinker_registry.py` auto-discovers them, checks prerequisites, and selects which to run. Brainstorming uses AI tool calls (`record_failure`, `record_suggestion`, etc.) to write structured output to the mailbox; `ai_actions/` contains tool schemas and handlers.

### LLM backends

All LLM interaction goes through two abstractions in `src/clarity_agent/llm/`:
- `LLMClient` (`client.py`) — low-level completions
- `ChatBackend` (`chat.py`) — multi-turn conversations with tool use

`llm/config.py` (`LLMConfig`) resolves provider/model/key from CLI flags and env vars. `llm/factory.py` instantiates the correct backend. Four providers: `anthropic`, `openai`, `azure` (Azure AI Inference), `claude-sdk` (default, uses `claude login`). Implementations are in `llm/impl/`.

### Web UI

`src/clarity_agent/web/app.py` is a FastAPI server. The WebSocket at `/ws/chat` streams chat between the React frontend and `ClaritySession`. `session_manager.py` bridges the sync session to async WebSocket via a thread pool. REST endpoints call the same Python functions as the CLI.

The React frontend (`web/`) is built with Vite + TypeScript + Tailwind CSS. `web/dist/` is pre-built and checked in — Node.js is only needed when changing frontend code. All visual tokens live in `web/src/themes/sage.css` as CSS custom properties.

### Registry sync invariant

Several registries are intentionally decoupled (packet status graph, packet renderer, init templates, test fixtures). `tests/test_registry_sync.py` enforces that they stay in sync. When adding a new protocol document, process, thinker, or LLM provider, consult `UPDATE-CHECKLIST.md` for the full list of files to touch — the test catches some invariants but not documentation or process guide updates.

## Protocol documents

`.clarity-protocol/` (in any embedded project) contains:
- `summary.md`, `notes.md` — high-level state and shared memory across sessions
- `goal/` — problem, stakeholders, requirements, open/resolved questions
- `solution/` — solution description, architecture, solution summary
- `failures/` — failure modes with causal chains and management plans
- `decisions/` — decision records
- `config.json` — dependency graph and content hashes (the "build database")

`src/clarity_agent/protocol/initialize.py` creates the initial directory with template content.

<!-- clarity-begin -->
<!-- clarity-version: 2 -->
## Clarity Protocol

This project uses the Clarity Protocol (`.clarity-protocol/`) for structured
thinking about problems, solutions, and failure modes.

**Before building — think when it matters.** Two triggers:

1. *The user asks.* When they want to explore what to build, clarify
   requirements, brainstorm risks, or work through a decision — use the
   `run_clarity` tool (or read `processes/clarity-agent.md`).

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