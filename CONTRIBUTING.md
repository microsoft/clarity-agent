# Clarity Agent: Developer Guide

Join the [Clarity Agent Discord](https://aka.ms/clarity-agent-community) to talk with the team, share feedback, and connect with the community.

This project welcomes contributions and suggestions. Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us the rights to use your contribution. For details, visit https://cla.microsoft.com.

When you submit a pull request, a CLA-bot will automatically determine whether you need to provide a CLA and decorate the PR appropriately (e.g., label, comment). Simply follow the instructions provided by the bot. You will only need to do this once across all repositories using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

This guide is for people who want to work on the Clarity Agent itself — improving processes, writing thinkers, or extending the infrastructure.

## What the Clarity Agent Is

The Clarity Agent is a framework that guides AI assistants (and humans) through structured thinking about a project: what the problem is, how to solve it, what could go wrong, and what to do about it. It produces a `.clarity-protocol/` directory containing the results of that thinking. Projects can be anything — software, research, product strategy — with or without a codebase. Embedding into a git repo is an optional step that lets a coding agent pick up the protocol automatically.

There are four ways to use the Clarity Agent:

- **Desktop app**: Run `clarity app` (or double-click `Clarity.app`) to launch a native window with a multi-project picker, chat, protocol browsing, packet status reports, and review packet generation. Best for dedicated thinking sessions.
- **Headless web UI**: Run `clarity web [project_dir]` to start the FastAPI server without a native window — useful for server deployments or developer testing.
- **CLI**: Run `clarity cli ./my-project` to interactively run processes in the terminal. Useful for quick checks and scripting.
- **Embedded in a coding agent**: Run `clarity embed /path/to/project` to wire Clarity into a git repo. Your coding agent (Claude Code, Cursor, etc.) detects the process guides and follows them automatically — structured thinking woven into your coding workflow.

## Setting Up a Development Environment

Clone the repo and install all dependencies with [uv](https://github.com/astral-sh/uv):

```bash
git clone https://github.com/microsoft/clarity-agent.git
cd clarity-agent
uv sync --all-extras
```

Prerequisites: **uv** (install with `curl -LsSf https://astral.sh/uv/install.sh | sh` or see [uv docs](https://docs.astral.sh/uv/getting-started/installation/)), **Node.js 18+** (for frontend development only), **git**, and credentials for at least one supported LLM backend (see "LLM backends" below). uv manages Python itself — no separate Python install required.

```bash
# Authenticate (see "LLM backends" below for all options)
# Set one of: ANTHROPIC_API_KEY, AZURE_AI_API_KEY, OPENAI_API_KEY in .env
# Or: claude login

# Run directly from the repo
uv run python clarity.py web /tmp/test-project   # Web UI (headless)
uv run python clarity.py app                     # Desktop app with native window
uv run python clarity.py cli /tmp/test-project   # CLI session
```

The `dev` extra installs all optional dependency groups: `cli` (Claude SDK, Anthropic API, dotenv), `web` (FastAPI, uvicorn), `app` (pywebview for the native desktop window), `brainstorm` (thinker infrastructure), `docx` (review packet Word export), `test` (pytest), and all LLM providers (`openai`, `azure`). If you only need a subset: `uv sync --extra web --extra test`.

### For frontend development

`web/dist/` is built locally — it is not checked into the repo. Every install path (`clarity install`, the desktop bundler, the release workflow) builds it from source via `npm run build`. If you cloned the repo and want a UI in `clarity web`, run the build once:

```bash
cd web
npm install                          # install Node dependencies (first time only)
npm run build                        # build into web/dist/
```

For hot-reloading during frontend development, run both in parallel:

```bash
# Terminal 1: backend (headless)
uv run python clarity.py web /tmp/test-project

# Terminal 2: frontend dev server (proxies /api and /ws to :8420)
cd web && npm run dev
```

CI runs the frontend build on every PR as a compile check — there's no committed-dist invariant to maintain.

## How the System Flows: Logical Architecture

The system is structured like a program. Process guides (markdown files in `processes/`) are the logic; Python modules in `src/clarity_agent/` are infrastructure they call.

### clarity-agent.md is "main"

`processes/clarity-agent.md` is the entry point. It:

1. Checks whether `.clarity-protocol/` exists in the target project
2. If new: initializes the directory (via `protocol/initialize.py`) and starts a conversation
3. If existing: runs the packet status checker to assess project state
4. Routes to the appropriate process guide based on what needs attention
5. After any process completes, control returns here to reassess

### The packet status checker is the flow controller

`src/clarity_agent/protocol/packet_status.py` acts like a build system. It maintains a dependency graph among documents:

```text
problem → stakeholders → requirements → open-questions → solution → failures
                                                                  → architecture (↔ failures)
                                                                  → solution-summary (← solution + architecture)
```

It uses SHA-256 content hashes (stored in `config.json`) to detect when a dependency has changed since a document was last accepted. The first stale document in topological order is usually the next thing to work on. The `--agent` flag produces markdown output suitable for including in an AI system prompt.

Decisions are tracked separately via `decisionState` in config.json, with their own trigger mechanism for when grounding documents change.

### The mailbox mechanism handles asynchronous operations

The system supports a concept of "asynchronous operations," like failure brainstorming or human
reviews, where many (human or AI) actors will provide answers in parallel that ultimately need to be
gathered. Since this is a common pattern, we have a common "mailbox" mechanism for it in `src/clarity_agent/protocol/mailbox.py`.

An asynchronous operation is created using a function that creates a "mailbox" directory in `.clarity-protocol/mailboxes/name`, and specifying a "collector" function -- a .md process or a Python function that can be called to handle incoming. (The collector must be reentrant, i.e. you must be able to call it on a partial set of results, and then on more results later, and it should work) Once that's created, the caller can ask any number of actors to write files into that directory. Whenever the clarity agent runs, if there are new items in the mailbox, it gives the user the option to run the collector and (interactively or automatically, as per the collector) handle them. For example, in failure brainstorming, the collector guides you through the process of thinking about the proposed failures, grouping them, and coming up with plans for them.

### Failure brainstorming uses tools for structured output

For failure brainstorming, the AI applies different analytical lenses (broad analysis plus specialist thinker methodologies) within the main conversation. Tools (`record_failure`, `record_suggestion`, `recommend_deeper_analysis`, `read_thinker_guide`) ensure findings are recorded with controlled formatting to the brainstorming mailbox. The thinker registry (`protocol/thinker_registry.py`) discovers specialist thinkers, parses their YAML frontmatter, checks prerequisites, and determines which are available.

### The web UI wraps the same infrastructure

The web UI (`--web` flag) is a FastAPI server that exposes the same `ClaritySession` used by the CLI:

- **WebSocket** (`/ws/chat`): Streams chat messages between the React frontend and the session. `session_manager.py` bridges the sync session to async WebSocket via a thread pool.
- **REST endpoints**: Protocol tree, document content, packet status reports, and packet generation. These call the same Python functions as the CLI.
- **React frontend** (`web/`): Built with Vite + TypeScript + Tailwind CSS. In production, FastAPI serves the built frontend as static files from `web/dist/`. For development, run `cd web && npm run dev` for hot-reloading (it proxies API/WS to the backend).
- **Theming**: All visual tokens are defined as CSS custom properties in a single theme file (`web/src/themes/sage.css`), mapped to semantic Tailwind color names in `tailwind.config.js`. Swapping themes = changing one CSS file.

### LLM backends are pluggable

The `src/clarity_agent/llm/` package abstracts all LLM interaction behind two interfaces: `LLMClient` (low-level completions) and `ChatBackend` (multi-turn conversations with tool use). Five providers are supported:

| Provider | `--provider` flag | API key env var | Notes |
| --- | --- | --- | --- |
| **Anthropic** | `anthropic` | `ANTHROPIC_API_KEY` | Default auth uses `claude login` (`--auth-mode claude_sdk`); use `--auth-mode api_key` for direct API access. |
| **Azure AI Inference** | `azure` | `AZURE_AI_API_KEY` | Also requires `--endpoint` or `AZURE_AI_ENDPOINT`. |
| **OpenAI** | `openai` | `OPENAI_API_KEY` | Tool definitions translated from Anthropic format. |
| **GitHub Copilot** | `github` | `GITHUB_TOKEN` | Supports bundled GitHub Copilot CLI login (`copilot auth login`), GitHub CLI fallback (`--auth-mode gh_cli`), and personal access tokens. |
| **Google Gemini** | `gemini` | `GEMINI_API_KEY` | API key from [Google AI Studio](https://aistudio.google.com/apikey). |

Select a provider with `--provider`:

```bash
./clarity ./my-project --provider anthropic
./clarity ./my-project --provider anthropic --auth-mode api_key  # use API key instead of claude login
./clarity ./my-project --provider openai --model gpt-4o
./clarity ./my-project --provider azure --endpoint https://your-deployment.inference.ai.azure.com
./clarity ./my-project --provider github
./clarity ./my-project --provider gemini
```

Each provider resolves its default model from provider-specific tier defaults (defined as `*_TIER_DEFAULTS` in `llm/impl/`), which can be overridden via settings, environment variables, or the `--model` flag.

**Architecture:** `LLMConfig` (in `llm/config.py`) resolves provider, API key, model, and endpoint from CLI flags and environment variables. `create_chat_backend()` (in `llm/factory.py`) instantiates the correct backend. `ClaritySession` accepts any `ChatBackend` and doesn't know which provider is behind it.

## How the System Flows: Semantic Stages

The clarity agent guides a project through these stages, roughly in order but with loops back when understanding changes:

| Stage | Process Guide | Outputs to |
| --- | --- | --- |
| **Problem clarification** | `problem-clarification.md` | `goal/problem.md`, `goal/stakeholders.md`, `goal/requirements.md`, `goal/open-questions.md`, `goal/resolved-questions.md` |
| **Discovery prototype** | `discovery-prototype.md` | Updates `goal/open-questions.md`; moves resolved questions to `goal/resolved-questions.md`; optionally `goal/discovery/` |
| **Discovery research** | `discovery-research.md` | Updates `goal/open-questions.md`; moves resolved questions to `goal/resolved-questions.md`; optionally `goal/discovery/` |
| **Solution design** | `solution-brainstorming.md` | `solution/solution.md`, `solution/solution-summary.md` |
| **Architecture** | `architecture-design.md` | `solution/architecture.md`, `solution/solution-summary.md` |
| **Failure brainstorming** | `failure-brainstorming.md` | Raw failures in a mailbox |
| **Failure analysis** | `failure-analysis.md` | `failures/failures.md` (grouped failure modes with chains), `observations.md` (coverage, provenance, pattern notes) |
| **Failure management** | `failure-management.md` | Management plans in failure mode files; updates to solution/architecture |
| **Decision guidance** | `decision-guidance.md` | `decisions/decisions.md` (cross-cutting, invoked from any stage) |

The dependency graph enforces the general order (you can't meaningfully analyze failures without a solution), but the agent is flexible — users can work on whatever they want, and the packet status checker will flag what's become inconsistent.

### Discovery projects

Sometimes during problem clarification, you discover there are fundamental unknowns that would change the solution approach. The system handles this through:

1. **Recognition**: Problem clarification (Step 5.5) checks for signs of a "discovery" situation — structural uncertainty, factual disagreements, dependency on unknown facts.
2. **Capture**: Open questions are written to `goal/open-questions.md` with a status (open/investigating/resolved), strategy (prototyping/research/thinking), and findings.
3. **Resolution**: The clarity-agent routes to the appropriate discovery process based on strategy:
   - **Prototyping** → `discovery-prototype.md` — build a minimal, disposable prototype to test a hypothesis
   - **Research** → `discovery-research.md` — design and execute a structured investigation program
   - **Thinking** → stay in `problem-clarification.md` for deeper discussion
   - **Rapid prototyping at scale** (special case) → `solution-brainstorming.md` framed around experimentation infrastructure
4. **Return**: Discovery processes write findings back to `goal/open-questions.md` and return to the clarity-agent for reassessment. Resolving questions marks `solution/solution.md` as stale.

## File Reference

### `processes/` — Process Guides

The "program logic." Each file is a set of instructions an AI assistant follows.

| File | Role |
| --- | --- |
| `clarity-agent.md` | Entry point and router. Assesses state, picks next process. |
| `problem-clarification.md` | Conversation to sharpen problem, stakeholders, requirements. Includes discovery check. |
| `discovery-prototype.md` | Test a specific hypothesis through minimal, focused implementation. |
| `discovery-research.md` | Design and execute a research program to answer open questions. |
| `solution-brainstorming.md` | Develop a solution approach grounded in the problem. |
| `architecture-design.md` | Turn a solution into components, relationships, implementation plan. |
| `failure-brainstorming.md` | Generate raw failure modes from multiple perspectives. |
| `failure-analysis.md` | Group raw failures into modes, build causal chains, find intervention points. |
| `failure-management.md` | Develop plans for handling each failure mode; may modify solution/architecture. |
| `decision-guidance.md` | Think through important decisions at any stage. |
| `README.md` | Status table for all process guides. |

### `src/clarity_agent/` — Python Infrastructure

The "standard library." Called by process guides and by clarity CLI.

| File | Role |
| --- | --- |
| `session.py` | `ClaritySession` — shared session logic used by both CLI and web backend. |
| `protocol/packet_status.py` | Dependency graph, content hashing, packet status detection. The "build system." |
| `protocol/initialize.py` | Creates `.clarity-protocol/` directory with config and templates. |
| `protocol/mailbox.py` | Async mailbox mechanism for multi-actor operations. |
| `protocol/thinker_registry.py` | Discovers thinkers, parses frontmatter, checks prerequisites, selects which to run. |
| `protocol/failure_state.py` | Failure management state tracking and mailbox integration. |
| `protocol/diagram.py` | Dependency graph diagram generation. |
| `ai_actions/` | AI-invocable tools (suggestion, brainstorm) — schemas, handlers, format control. |
| `setup/installer.py` | Shared install step primitives (StepResult, Outcome). |
| `setup/desktop.py` | Desktop app installer — macOS .app, Windows, Linux, standalone modes. |
| `setup/project.py` | Project embedding — creates `.clarity-protocol/`, AGENTS.md snippet, wrapper. |
| `setup/doctor.py` | Diagnostics and environment validation. |
| `setup/agent_dir.py` | Resolves the clarity-agent repository root directory. |
| `web/app_window.py` | Native desktop window via pywebview — starts uvicorn in a thread, opens WKWebView/WebView2/WebKit2GTK. |
| `llm/config.py` | `LLMConfig` — resolves provider, API key, model, and endpoint from CLI flags and env vars. |
| `llm/factory.py` | `create_client()` / `create_chat_backend()` — instantiates the correct backend for a provider. |
| `llm/chat.py` | `ChatBackend` abstract interface for multi-turn LLM conversations with tool use. |
| `llm/client.py` | `LLMClient` abstract interface for low-level completions. |
| `llm/types.py` | Shared type definitions (tool schemas, message types). |
| `llm/impl/` | Provider implementations: `anthropic.py`, `claude_sdk.py`, `openai.py`, `azure_inference.py`, `github_copilot.py`, `gemini.py`. |
| `packet/` | Review packet generation — assembles protocol content into Markdown or Word documents. |
| `web/app.py` | FastAPI application — WebSocket chat endpoint and REST API for protocol data. |
| `web/session_manager.py` | Bridges sync `ClaritySession` to async WebSocket via `ThreadPoolExecutor`. |
| `web/models.py` | Pydantic request/response models for the REST API. |

### `thinkers/` — Thinker Guides

Specialized perspectives for failure brainstorming. Each is a markdown file with YAML frontmatter declaring its type, modes, prerequisites, and tags.

| File | Role |
| --- | --- |
| `general-thinker.md` | Broad first-pass failure analysis across all dimensions — technical, human, social, misuse, and cascading failures. Recommends specialist thinkers for deeper analysis. |
| `security-thinker.md` | Examines a system for security failures (auth, injection, data protection, etc.). |
| `human-factors-thinker.md` | Examines how humans and AI components err while participating in a system (input errors, misinterpretation, bias, decision-making at scale). |
| `adversarial-analysis-thinker.md` | Reasons from the adversary's perspective — identifies who would attack or misuse the system, their motivations, capabilities, and means. |
| `codebase-scanner-thinker.md` | Scans a repository for architectural signals — API routes, configs, auth patterns, secrets, AI integrations, infrastructure — to inform architecture design and threat modeling. |
| `security-catalog-thinker.md` | Maps threats from `catalogs/security-catalog.csv` to the system's components and records applicable failure modes. |

### `dev-tools/` — Development Utilities

| File | Role |
| --- | --- |
| `refresh-catalog.py` | Standalone tool for updating `catalogs/security-catalog.csv` with latest threat intelligence. Interactive AI conversation that searches the web and proposes changes for human approval. |

### Top-level entry points

| File | Role |
| --- | --- |
| `clarity.py` | Main entry point — web UI, CLI, desktop app, install, embed, update, doctor. |
| `scripts/install.sh` | Bootstrap installer (macOS/Linux) — downloads uv, clones repo, hands off to `clarity install`. |
| `scripts/install.ps1` | Bootstrap installer (Windows) — same, PowerShell equivalent. |
| `README.md` | Full documentation for the CLI and web UI. |

### `web/` — React Frontend

The browser-based UI, built with Vite + TypeScript + Tailwind CSS. In production, the FastAPI server serves the built frontend as static files. For development, run the Vite dev server separately for hot-reloading.

| Directory/File | Role |
| --- | --- |
| `src/components/` | React components — Sidebar, ChatPanel, ProtocolViewer, StalenessPanel, etc. |
| `src/hooks/` | Custom hooks — `useChat` manages WebSocket connection and chat state. |
| `src/themes/` | CSS custom property theme files. Swap theme by changing one import in `index.css`. |
| `src/api/client.ts` | REST API client for protocol data, packet status, and packet generation. |
| `tailwind.config.js` | Tailwind configuration with semantic color tokens mapped to CSS variables. |

### Other Directories

| Directory | Purpose |
| --- | --- |
| `adapters/` | Tool-specific integration templates. Currently: `AGENTS.md.template` for Claude Code. |
| `input-thoughts/` | Working notes and design documents written by humans during development. Not part of the runtime system. |
| `examples/` | Sample `.clarity-protocol/` directories for reference. |
| `tests/` | pytest suite covering the Python infrastructure. |
| `web/` | React frontend for the web UI. See `web/` section above for details. |
| `.clarity-protocol/` | The clarity agent's own clarity protocol (self-hosting). |
