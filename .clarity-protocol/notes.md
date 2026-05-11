# Notes

## Guiding Principles

**Process guides are the product.** The markdown process guides in `processes/` are the core intellectual value of the framework. The Python infrastructure handles mechanics. When improving the framework, invest first in the quality of the guides.

**Self-hosting is a design constraint.** This project uses its own clarity protocol. Any improvement to the protocol format or process flow should be reflected here first. If something is awkward to fill in for this project, it's awkward for users too.

**The conversation, not the document, is the primary experience.** Documents are a byproduct of good conversations. Process guides should be written to produce natural dialogue. Users who feel like they're filling in forms have already had a bad experience.

**Fast past the obvious.** The biggest process failure mode is unnecessary friction on things the user already knows. Guides and agents should move quickly through clear cases and slow down only for genuine ambiguity or meaningful tradeoffs.

**The deepest value proposition is better thinking, not better documents.** The problem statement rewrite surfaced this: the primary value is the quality of thinking the user ends up with. The artifact is evidence and a useful byproduct — especially in teams and for coding agents — but it's secondary. UX decisions should be evaluated against "does this help the user think better?" first.

**Stakeholders and UX are entangled.** Different user jobs-to-be-done imply different UX surfaces. The stakeholder analysis should drive UX thinking, not just list who benefits.

**Capability first, products second.** The architecture is four layers: Layer 1 (intellectual corpus — principles and concepts), Layer 2 (reified corpus — process guides in full or light expression), Layer 3 (infrastructure via MCP), Layer 4 (products). Full and light implementations share Layer 1 but diverge at Layer 2. MCP is the primary portability mechanism for Layer 3; REST adapters are the fallback.

**Layer 1 should become an explicit artifact.** Currently the principles are implicit in the process guides and scattered across input-thoughts files. Making Layer 1 a maintained set of markdown files enables traceability from both Layer 2 expressions back to source principles, and aligns with the book as a third expression of the same corpus.

**Attitude × place is the UX matrix.** Users arrive with different attitudes ("I want to build X," "we need to change X," "something isn't right") from different places (general AI tools, coding agents, IDE, standalone). The product strategy needs to cover this matrix, not just the cells that are obvious today.

## Failure-Analysis-Derived Design Principles

**Value demonstration is the master intervention.** If the user experiences concrete, specific value early — an insight they hadn't considered, a failure mode they'd missed — they stay engaged, challenge shallow output, and resist compliance theater. Time to first insight is the critical adoption metric and should be measured. The process guides should be designed to surface a genuine challenge or insight within the first few exchanges, before friction accumulates.

**The user is a single point of failure for quality.** When they disengage, AI quality degrades, alignment fails, and analysis goes shallow. The system needs built-in self-checking that doesn't rely solely on user vigilance. The "room full of experts" model — multiple somewhat-different perspectives collaborating to improve the idea — is the inspiration. This is already embodied in failure brainstorming thinkers; it should extend to other parts of the process (e.g., critique guides that review problem statements, requirements, solutions for flaws).

**Conciseness is structural, not cosmetic.** Verbosity is a failure mode that undermines engagement, alignment, and quality simultaneously. The protocol format needs a "summary layer" — critical content first, detail on demand. Length guidelines and information-splitting principles from the author's interactive template work (over a year of refinement with real teams) should be captured in Layer 1 and enforced in both Layer 2 expressions.

**Challenge intensity should be adaptive.** FR2's challenging disposition needs calibration — too much drives disengagement (Failure 1), too little enables shallow thinking (Failure 2) and false alignment (Failure 3). Process guides should include guidance on reading expertise signals and adjusting push-back intensity. This is a Layer 2 design concern, not infrastructure.

**Critique guides need calibration, not just content.** The invisible self-critique mechanism can over-correct — the agent becomes hedged, slow, or afraid to commit. The disposition should be "notice when something feels off and say so," not "question everything before saying anything." When writing critique guides, test for over-correction as well as under-correction. [for: architecture-design]

## Messaging Observations

**Vision and clarity are distinct concepts in the pitch.** Vision is directional (what you want to matter); clarity is operational (what specifically you're building and why). The gap between them is where most creative work happens and where AI currently offers nothing. This distinction sharpens the core value proposition and should be reflected in Layer 1.

**The eudaimonic AI hypothesis.** *AI can be most effective by working with, rather than for, humans, and this path can amplify individual capacities the way literacy did.* The Socratic mechanism (questioning toward understanding rather than answering) is one expression of this; "Socrates" is a candidate project name for clarity-focused tooling within the broader research program.

**Two-worlds framing for business-minded audiences.** World 1: clarity is scarce, amplify the capable few, federation model. World 2: clarity is teachable, AI as literacy, everyone who builds anything is the market. The World 2 enterprise value proposition: clarity tooling is a force multiplier on every other AI product in the portfolio — it addresses the actual bottleneck causing ROI disappointment.

**The "wants well" formulation.** "Does AI help humans want well?" is the question upstream of alignment that the field isn't asking. Useful framing for research audiences.

## Integration Strategy Exploration (2026-04-06)

**Core thesis: Clarity is a capability that composes into tools, not a destination.** Tool sprawl is the adoption killer. People install Clarity once, and it meets them wherever they work — via the extensibility primitives converging across the ecosystem (rules files, MCP servers, skills/slash commands, extensions).

**Three personas, three integration philosophies:**

**Citizen developers (vibe coding tools — Cursor, Bolt, Replit, v0, Claude Code casual).** These users ship software without security instinct. Clarity shows up uninvited at critical moments: auth, payments, user data, external APIs. The intervention is *context-aware* — if the remedy is clear (e.g., "you're storing passwords in plaintext"), act like a linter and fix it. If there's genuine ambiguity (e.g., "what's your trust model for this API?"), work through it conversationally until the ambiguity resolves. Output is checklists and warnings, not protocol documents. Surfaces: rules files, MCP `clarity-check` tool, `/clarity-secure` skill, deploy gates.

**Product managers (counterparts to engineering teams).** PMs who work alongside engineers can work in code-adjacent tools — Claude Projects, coding agents with vibe-coding flows — not just Notion and Google Docs. The light expression loaded as project knowledge gives them a thinking partner that pushes back on vague specs and surfaces stakeholder misalignment. The protocol format is the handoff contract: what a PM produces with Clarity is what an engineer's coding agent consumes. Near-term surface: Claude Project / Custom GPT with light expression. Later: MCP-enhanced AI tools.

**Professional engineers (Claude Code, Cursor, Copilot, VS Code, JetBrains).** The existing AGENTS.md snippet, extended to other agent configs. MCP server for full infrastructure access without leaving the editor. Slash commands for quick-access (`/fail-check`, `/decide`, `/clarity`). PR review integration that surfaces protocol staleness against code changes. Post-incident integration that closes the loop between planning and reality.

**Cross-cutting: the composability model.**
- Protocol format as the interop layer across all three personas.
- Graduated depth: checklist → focused analysis → full process. Every integration starts light.
- MCP as the universal connector: one server, many clients.

**Integration points index:**

| Persona | Where they are | Integration point | User experience | Clarity value delivered | Risks |
|---|---|---|---|---|---|
| **Citizen developer** | Cursor, Bolt, Replit, v0, Claude Code (casual) | Rules file (`.cursorrules`, `CLAUDE.md`) | Agent pauses at auth/payments/data patterns; fixes clear issues automatically, opens conversation for ambiguous ones | Security thinking injected where it never existed; catches the "storing passwords in plaintext" class of mistakes | Rules are static — can't adapt to project evolution; alert fatigue if too aggressive; user may override without understanding |
| | | MCP `clarity-check` tool | Agent calls a lightweight threat check; returns top 3 risks as actionable items | Context-aware analysis, not just pattern matching; can reason about the specific system being built | Depends on MCP adoption across vibe-coding tools; quality degrades if project context is thin |
| | | `/clarity-secure` skill | On-demand focused security brainstorm; produces a checklist scoped to current project | Deepest citizen-dev analysis; closest to "having a security engineer review your code" | Requires user to know it exists and choose to invoke — the persona least likely to do so |
| | | Deploy gate (CI/CD) | Pre-deploy scan surfaces unaddressed risks; blocks or warns at ship time | Last line of defense; catches what earlier interventions missed | Positioned late — expensive to fix issues at deploy; can become a checkbox people dismiss |
| **Product manager** | Claude Projects, ChatGPT, coding agents (vibe flows) | Light expression as project knowledge | AI thinking partner pushes back on vague specs, surfaces missing stakeholders, demands testable criteria | Full Clarity disposition — challenging questions, structured thinking — with zero tooling setup | No persistence between sessions; PM must manually carry context forward; no staleness tracking |
| | | MCP server (MCP-capable AI tools) | Full staleness tracking and structured protocol output inside the PM's preferred AI tool | Persistent, tracked protocol that evolves with the project; same infrastructure engineers get | Requires PM to use an MCP-capable tool; adds complexity that may not match PM workflow expectations |
| | | Protocol as handoff contract | PM produces `.clarity-protocol/`; engineer's coding agent consumes it as build context | Eliminates the spec-to-implementation translation gap; shared artifact surfaces misalignment *before* code | Protocol can diverge if PM and engineer edit independently; needs merge/conflict conventions; PM may resist working in a repo |
| **Professional engineer** | Claude Code, Cursor, Copilot, VS Code, JetBrains | Rules file (`AGENTS.md`, `.cursorrules`) | Agent triggers clarity processes at architectural decision points — not constantly, but at natural inflection moments | Structured thinking embedded in existing workflow; decisions get documented as they happen | Agent may misjudge when to trigger (too often → annoying, too rare → missed decisions); rules vary across tools |
| | | MCP server | Full infrastructure via tool calls — `check_staleness()`, `record_decision()`, `run_thinker()` — without leaving editor | Highest-fidelity integration; the complete Clarity process as composable tools | Heaviest dependency; requires MCP server running; adds latency to agent interactions |
| | | Slash commands (`/clarity`, `/fail-check`, `/decide`) | Quick-access focused operations; `/fail-check` on current feature, `/decide` to capture a choice with alternatives | Low-friction entry to specific Clarity capabilities; user controls depth and timing | Fragmented experience — user must know which command to use; may not discover the full process |
| | | PR review (GitHub Action/bot) | Surfaces protocol staleness against code changes: "this PR changes auth but architecture doc is stale" | Catches drift between thinking and building in the review flow where the team is already looking | Can become noisy on active codebases; staleness doesn't always mean the protocol is *wrong*; alert fatigue |
| | | IDE extension (VS Code panel) | Protocol sidebar: problem, requirements, failures, decisions — glanceable while coding | Persistent visibility of *why* this is being built; reduces context-switching to understand project intent | Passive — doesn't prompt action; risks becoming furniture the engineer stops seeing |
| | | Post-incident integration | Reads postmortem, checks: was this failure known? What happened to the management plan? | Closes the planning-to-reality loop; makes failure analysis feel consequential, not theoretical | Requires postmortem discipline that many teams lack; risk of blame-framing if not positioned carefully |

**Risk patterns the table surfaces:**
- *The discoverability paradox.* The personas who need Clarity most (citizen devs) are least likely to invoke it. Integrations that don't require invocation (rules files, deploy gates) deliver less depth. The context-aware linter/conversation toggle is the key mechanism — maximize depth at the moments the system *detects* depth is needed.
- *Alert fatigue is the recurring threat.* Rules files, deploy gates, PR review, staleness tracking all risk becoming noise. Graduated depth must be genuinely selective, not just graduated in theory.
- *Persistence is the PM gap.* The light expression is the fastest PM path, but without persistence it's a thinking tool that forgets. MCP closes the gap but adds friction. A lightweight export/import convention may be a middle ground.

**Open questions from this exploration:**
- How does the context-aware linter/conversation toggle work mechanically? Is it a disposition in the rules file, or does the MCP tool return metadata that the agent interprets?
- What's the minimum viable MCP server surface? Which tools does it need to expose for the citizen developer use case vs. the full engineering use case?
- How do we handle protocol format as a handoff contract when the PM and engineer are in different tools? What happens when the PM's protocol and the engineer's protocol diverge?
- Should the deploy gate be a Clarity product, or should Clarity produce artifacts that existing deploy gates (GitHub Actions, etc.) can consume?
- What's the right relationship between the light expression (for PMs) and the rules-file expression (for vibe coders)? Are these two different Layer 2 derivations, or is the vibe-coder surface a subset of the light expression?

[for: solution-brainstorming] Integration strategy needs to be reconciled with the current Layer 4 product priority list. The "install once, meet them everywhere" model may reshape priorities — MCP server becomes prerequisite infrastructure rather than a product.

[for: architecture-design] MCP server surface area needs explicit design: which tools, what granularity, how does graduated depth work at the protocol level.

## Adaptive Teaching Disposition (2026-04-27)

**"Better product thinkers" is a v1 success criterion.** Working with Clarity should make people better at structured thinking over time, not just produce better artifacts. This is an active design goal, not an aspiration.

**Same process, adaptive depth.** Without cross-project memory, the agent calibrates from the conversation itself — every exchange, not as a one-time assessment. The sophistication of the user's response tells the agent how to proceed. A vibe coder who says "I want to build an app" gets drawn out through follow-up questions. A PM who brings a crisp audience definition gets challenged on gaps. Same process guide, different depth.

**Draw out before filling in.** The master principle for process guide design. When the user's response is thin, ask follow-up questions that help them discover the answer — don't generate it for them. When the response is rich, challenge its weak points rather than walking through basics. In both cases, push one level beyond where the user is. This is the mechanism by which the tool teaches.

**User-first failure brainstorming.** Ask "what do you think could go wrong?" before running thinkers. The contrast between what the user identified and what the thinkers found is where learning happens. Over time, the delta shrinks — and that's measurable.

**Name the pattern, don't lecture about it.** When the agent pushes back (e.g., on an untestable success criterion), briefly name why — one sentence. The user starts recognizing the pattern and applying it without the tool. Heavy-handed teaching kills engagement.

**Minimize forced labor, maximize useful teaching.** The agent shouldn't make users do busywork to "learn the process." It should draw out their thinking where that thinking matters, fill gaps where the user genuinely can't see them, and make the structure visible enough to internalize — all without adding steps or slowing down the experienced user.

[for: solution-brainstorming] Process guides need rewriting with draw-out-before-fill-in disposition. Problem clarification is the natural starting point since it's the first thing every user encounters.

[for: failure-brainstorming] Failure brainstorming flow change: user-first brainstorm, then thinkers as contrast showing what they missed.

## Cross-Phase Observations

Failure analysis and management complete: 7 failure modes from 34 raw failures, all with chains, intervention points, and management plans.

**Review process is the highest-leverage future capability.** It would address 4 of 7 failure modes (AI quality, false alignment, analysis depth, compliance theater). The project author has ideas for making it broadly applicable beyond traditional organizational review structures. This should be captured in solution planning.

**Three high-priority implementation items from failure management:** (1) Write Layer 1 as an explicit artifact — prerequisite for the light expression and drift prevention. (2) Write the protocol format spec (FR7) — a four-failure intervention and the interoperability contract. (3) Build critique guides — the mechanism for invisible self-critique across all process phases.

