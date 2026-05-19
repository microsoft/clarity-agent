# Solution

## The Core Idea

The Clarity Agent is an AI-powered thinking partner that helps people develop genuine clarity about what they're building, what could go wrong, and why they're making the choices they're making. It is rooted in decades of practice in structured thinking, safety engineering, and organizational design — techniques that work, but have historically required scarce expertise. The clarity agent makes these techniques accessible to anyone working with an AI.

The system is designed as a **capability first, products second.** At its foundation is an intellectual corpus — the principles and concepts of structured thinking — from which everything else is derived. Specific products adapt this capability to the contexts where users actually are: coding agents, general-purpose AI tools, standalone applications, and integration points we haven't imagined yet.

The shipped implementation focuses on software engineering, where the resulting artifacts have dual value as human reference and AI coding agent input. But the underlying framework is domain-agnostic by design.

---

## The System As Built

### What Exists Today

The current implementation is a **full-implementation product** with three entry points, built on a set of process guides backed by Python infrastructure.

**Process guides** (`processes/`) are markdown documents that direct how an AI should conduct a structured conversation. They encode what to ask, when to push back, what to write down, and when to move on. An AI agent loaded with a process guide can follow it to conduct a clarity session — the guides are the logic; everything else is mechanics.

**Thinker guides** (`thinkers/`) encode specialized analytical perspectives for failure brainstorming — security, human factors, adversarial, operational, and a general thinker that runs first and recommends which specialists to invoke for deeper analysis.

**The protocol format** defines the structure of the outputs: problem statement, stakeholders, requirements, solution, architecture, failure modes, decisions, and open questions — all as human-readable markdown files in a `.clarity-protocol/` directory, version-controllable alongside the code they describe.

**Infrastructure** provides mechanical support:

| Component | Role |
|---|---|
| `packet_status.py` | Content-hash-based staleness tracking across a document dependency graph |
| `brainstorm_runner.py` | Thinker orchestration: general thinker inline, specialists on demand |
| `thinker_registry.py` | Discovers and selects thinkers based on metadata and prerequisites |
| `mailbox.py` | Async result collection for thinker operations |
| `llm/` | Provider-agnostic LLM abstraction (Anthropic, OpenAI, Azure, GitHub Copilot, Google Gemini) |
| `session.py` | Session coordination and event dispatch |
| `transcript/` | Event-based session recording, reconstruction, and rendering across multi-session chapters |
| `mcp/` | MCP server exposing eight infrastructure tools via stdio, SSE, and HTTP transport |
| `packet/` | Review packet generation (Markdown, DOCX) |
| `feedback.py` | User response ratings and feedback storage |

**Five entry points (products):**

- **Coding agent integration (AGENTS.md)** — an `AGENTS.md` file in a project root instructs AI coding agents to engage clarity at inflection points: when the user asks to think, and proactively when the agent recognizes a choice that would be expensive to reverse. The coding agent session itself becomes the clarity conversation.
- **Web application** — FastAPI + React for dedicated clarity conversations, protocol browsing, staleness monitoring, transcript viewing, and packet generation.
- **CLI** — initialization, packet status checking, session management.
- **Desktop application** — a Tauri-packaged native app wrapping the web UI; installable as a standalone app on macOS, Linux, and Windows.
- **MCP server** — exposes eight infrastructure tools (staleness checking, document read/write, decision and failure recording, process guide injection) via MCP stdio, SSE, and HTTP transport; works with any MCP-capable AI environment without embedding the codebase.

### What It Does Well

The system produces genuinely useful structured thinking for software projects. The conversational process guides create natural dialogue, not form-filling. The staleness tracker reliably surfaces what needs revisiting when documents change. The thinker system — especially the general-thinker-first approach — produces failure analysis that users find valuable. Packet generation is well-liked for sharing with stakeholders. The AGENTS.md integration meets developers where they already are.

### Where It Falls Short of the Updated Vision

The current system was designed for a narrower scope than the updated problem statement and requirements describe:

- **No explicit intellectual corpus (Layer 1).** The principles behind the process guides are implicit — baked into the guides themselves and scattered across design notes. There's no canonical source of truth from which the guides are derived, which makes it hard to verify consistency, extend to new domains, or create alternative expressions.
- **One expression of the methodology.** The process guides assume tool access, multi-file context, and filesystem operations. There's no way to bring the clarity agent's thinking to a user in a bare AI conversation (claude.ai, ChatGPT) without the full infrastructure. The light expression is designed to address this but not yet written.
- **Greenfield assumption.** The system assumes you're starting a new project. There's no structured support for re-deriving clarity about an existing, partially-built system (FR11).
- **No light-implementation path.** Five entry points exist, all in the full-implementation path. There's still no path for the general AI user or the citizen developer operating in a bare conversation without tool access.

---

## The System As Envisioned

### Layered Architecture

The target architecture has four layers, with two implementation paths (full and light) that share a common foundation.

#### Layer 1: The Intellectual Corpus

The deepest layer — the principles, concepts, and methodology of structured thinking, independent of any particular expression or tooling. Maintained as an explicit set of markdown files that serve as the canonical source of truth.

The corpus captures:

- **Why clarity is hard** — the iterative nature of understanding what you want, the gap between "I have an idea" and "I know what I actually want," and why most processes (and most AI tools) fail to help close it.
- **The theory of failure analysis** — why it requires multiple perspectives, why people can't do it well alone, what distinguishes a substantive failure mode from a vague worry, and how to move from raw failures to causal chains and management plans.
- **The structure of good decisions** — what to capture, why rejected alternatives matter, when and how to reconsider.
- **Stakeholder thinking** — why you need it, how hidden misalignment works between people who believe they agree, and how structured artifacts surface disagreements early.
- **The challenging disposition** — why pushing back is the core value, how to do it without being adversarial, when to yield, and why agreeableness in AI tools is actively harmful.
- **The protocol format and why it's structured the way it is** — what each document type is for, why the dependency order matters, how the artifacts serve multiple audiences simultaneously.
- **How the process itself fails** — the failure modes of structured thinking (not of the user's project): how AI agents skip steps, how users resist challenge, how documents become bureaucratic rather than useful, how staleness tracking can create alert fatigue.

This layer is not loaded directly by any AI session. It is the source from which the Layer 2 expressions are derived, and it's closely related to the forthcoming book on the same principles. The book, the full process guides, and the light guide are three expressions of the same corpus, each optimized for a different audience and context.

#### Layer 2: The Reified Intellectual Corpus

Layer 1's principles expressed in forms that an AI can directly follow. Two expressions serve different environments:

**Full expression** — the process guides, thinker guides, and protocol format specification as they exist today (with ongoing refinement). Multiple files, assumes tool access and multi-file context, designed for an agent that can switch between guides and read/write the filesystem.

**Light expression** — a condensed form designed for single-context, no-tool environments (a Claude Project, a custom GPT, a system prompt). Captures the same core moves and disposition — the same questions to ask, the same push-back instincts, the same analytical structure — but in a form that works within the constraints of a single loaded document and no file system access. Protocol output is produced as structured text in the conversation.

The two expressions are independently crafted derivations of Layer 1, not of each other. When a principle is refined in Layer 1, it propagates to both — but the form of propagation differs because the expressions serve different environments.

#### Layer 3: Infrastructure (Full Implementation Only)

Mechanical support that enriches the full-expression experience. Exposed primarily via **MCP** (Model Context Protocol), which makes the infrastructure portable across any MCP-capable AI tool. REST adapters provide a fallback for platforms that don't support MCP natively.

The infrastructure includes staleness tracking, thinker orchestration, structured file operations, packet generation, session management, and LLM abstraction — all as described in the as-built section. The key change is the **exposure mechanism**: MCP rather than direct Python invocation, enabling any MCP-capable AI environment to use the full infrastructure without embedding the clarity agent's codebase.

The light implementation has no Layer 3 — the AI operates with Layer 2 alone.

#### Layer 4: Products

Context-specific shells that bring the capability to users where they are. Products in the full implementation use Layers 2 (full) + 3. Products in the light implementation use Layer 2 (light) only. All products share the same protocol format as the interoperability point.

**Current products (full implementation):**
- Coding agent integration (AGENTS.md)
- Web application
- CLI
- Desktop application (Tauri-packaged)
- MCP server (stdio/SSE/HTTP)

**Remaining products, in priority order** (see [Decision 01](../decisions/decision-01-product-priority.md)):

1. **MCP-enhanced general AI (hybrid).** MCP infrastructure now exists. Remaining work is the light Layer 2 expression — a condensed guide loaded as context — which, combined with the MCP server, delivers the full experience in a general-purpose AI environment.
2. **General-purpose AI integration (light).** The light Layer 2 expression loaded into a Claude Project, custom GPT, or similar. Highest reach, lowest friction — blocked on Layer 1 formalization → light expression.
3. **IDE integration.** Extensions for VS Code or other development environments. MCP support means VS Code integration may be lower effort than expected (VS Code already supports MCP).
4. **Hosted web service.** Multi-tenant, no installation, projects in the cloud. Deferred — high effort, high risk, well-understood engineering.
5. **Deep model integration.** The clarity agent's thinking patterns built directly into AI models or platforms. Distant horizon.

### How the System Thinks

The clarity agent's processes form a directed graph, not a linear pipeline. Different user attitudes lead to different paths:

**"I want to build X"** — the agent starts with problem clarification: what are you actually trying to build, and why? This flows into stakeholders, requirements, solution exploration, and failure analysis. The user may traverse the full graph or stop when they have enough clarity to act.

**"We have X and need to change it"** — the agent helps articulate what exists: what does the current system do, what assumptions are baked in, what's the mental model users have? Much of this understanding is implicit — in code, organizational memory, habits. Only after the current state is understood can the agent help plan the evolution.

**"Something isn't right and I need to think"** — the most open-ended entry. The agent helps the user figure out what they mean — what's bothering them, what they've tried, what they're hoping for. This may lead to problem clarification, failure analysis of an existing system, or a decision that needs revisiting.

In full-implementation contexts, the staleness tracker maintains awareness of what's current and what needs revisiting. In light-implementation contexts, the conversation itself serves this function — the agent asks about what's changed and what might be affected.

### Quality Architecture

Failure analysis revealed three cross-cutting patterns that shape the solution at every layer. These are not afterthoughts — they are design principles with the same weight as the layer model.

#### Time to First Insight

The single most impactful factor in user engagement is how quickly the agent demonstrates concrete, specific value — surfacing an assumption the user hadn't examined, a stakeholder they hadn't considered, a failure mode they hadn't imagined. If this happens in the first few exchanges, the user stays engaged through the harder parts of the process. If it doesn't, friction accumulates and disengagement follows.

This means the process guides must be structured to surface a genuine challenge or insight early, not after twenty minutes of information gathering. The agent should be looking for something to push back on from the user's very first description of their project. This is a Layer 1 principle (encoded in the intellectual corpus) and a Layer 2 design constraint (the guides must implement it).

Time to first insight should also be measured — though detecting "the user encountered something they hadn't thought of" is non-trivial. Possible proxies include user response length and engagement after the agent's first substantive challenge, or explicit user feedback. This is a long-term quality metric to develop.

#### Self-Critique and Multi-Perspective Review

The user is a single point of failure for output quality. When they disengage or trust the output uncritically, AI-generated analysis goes unchallenged and shallow thinking passes as rigor. The system needs built-in self-checking that doesn't rely solely on user vigilance.

The solution is to extend the "room full of experts" model — already embodied in failure brainstorming thinkers — across the entire process. Concretely, this means **critique guides**: specialized markdown files that teach the AI what to watch for in its own output at each phase.

- A problem statement critique guide might encode: "Are the success criteria actually testable? Are there stakeholders who would disagree with this framing? What assumptions are implicit?"
- A requirements critique guide: "Can each requirement be verified? Are there conflicts between requirements? What's missing?"
- A solution critique guide: "What alternatives were dismissed too quickly? Where is the solution driven by familiarity rather than fitness? What would a skeptic challenge?"
- A failure analysis critique guide: "Are the failure modes specific to this system or generic? Do the management plans actually work if you walk through them step by step?"

Crucially, self-critique should be **invisible** — part of how the agent thinks, not a separate process step. A skilled human thinking partner doesn't announce "now I'm going to critique what I just said." They notice something feels off and say "actually, wait — I'm not sure that requirement is really testable." The critique guides inform the agent's disposition and internal standard, not a visible review phase. This resolves the tension between quality and engagement time: there's no extra step, no duration cost. The agent simply holds itself to a higher standard continuously — checking its own output for specificity, questioning whether its failure modes are generic, noticing when a management plan is hand-wavy — as a natural part of the conversation.

In the longer term, a **review process** — where someone other than the original author critically examines the protocol — would address four of the seven identified failure modes (AI quality, false alignment, analysis depth, compliance theater). This is the highest-leverage future capability. While it traditionally requires organizational structure (pre-launch review committees with domain experts), there are approaches to making it more broadly accessible. This is on the roadmap.

#### Conciseness by Design

Verbosity is not a style problem — it's a failure mode that undermines engagement, alignment, and quality simultaneously. When documents are too long, users skim past critical content; when text is ambiguous, different readers interpret it differently; when the AI produces wordy output, shallow thinking hides behind volume.

The solution addresses this at two levels:

**Protocol format design.** Each document type in the protocol should have a "summary layer" — the critical content comes first, with detail available on demand. Length guidelines, information-splitting principles, and structural conventions for each document type should be captured in Layer 1 and enforced in both Layer 2 expressions. These guidelines draw on extensive practical experience refining templates interactively with real teams over an extended period.

**Process guide output discipline.** The process guides should instruct the agent to keep outputs concise: lead with the most important point, use specifics rather than vague generalities, and resist the LLM tendency toward comprehensive but unfocused prose. This is a Layer 2 concern — each expression implements conciseness differently based on its environment's constraints.

### What the System Produces

The **clarity protocol** — a structured set of documents that captures:

- What the project is and why it matters (problem, stakeholders)
- What it needs to do (requirements)
- How it should work (solution, architecture)
- What could go wrong and how to handle it (failure modes, management plans)
- What was decided and why (decisions, alternatives, rationale)
- What's still open (open questions, discovery plans)

These documents serve multiple audiences simultaneously: the builder (as a thinking aid), the team (as an alignment artifact), future collaborators (as context), coding agents (as implementation guidance), and regulators (as evidence of structured design thinking).

In full-implementation products, these are persistent files in a `.clarity-protocol/` directory. In light-implementation products, they are structured text in the conversation that the user can save and organize as they choose.

### What It Is Not

The clarity agent focuses exclusively on the thinking-before-and-during-building phase. It is not a project management tool, a code generator, a deployment pipeline, or a monitoring system. It deliberately stays out of implementation — its job is done when the user has clarity, the artifacts exist, and someone (human or AI) can read them and understand what to build and why.
