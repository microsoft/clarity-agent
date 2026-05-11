# Stakeholders

## Jobs to Be Done

The clarity agent serves different people in different situations — but the most useful way to think about stakeholders is through what they're *trying to do* when they encounter the tool, because the job shapes the UX far more than the role does.

### "I have an idea and I need to figure out what I actually want."

The most fundamental job. Someone has a rough notion and needs to develop it into something concrete enough to act on. The value is primarily *in their head*: the process of being challenged and questioned is the product. The clarity protocol is a useful byproduct.

This user might be a solo developer, a founder, a PM, or someone planning a non-software project. They know they need to think things through (or at least suspect it) and are looking for a thinking partner.

**Entry point:** Comes to the clarity agent directly through the web UI, CLI, desktop app, VS Code sidebar, or embedded in their coding agent.

### "I'm about to build something and I need to think about what could go wrong."

The user already has reasonable clarity on *what* they want, but hasn't done failure analysis. They need adversarial, operational, and human-factors perspectives they can't generate alone. The value is partly in sharpened thinking and partly in the artifact (a persistent record of failure modes and management plans).

**Entry point:** Likely already in a coding agent flow running clarity via embedded mode; the AGENTS.md integration intercepts them naturally.  They may also directly invoke failure analysis.

### "I need to get other people aligned on what we're doing and why."

People routinely *believe* they agree about what they're building, but actually don't. The artifact matters enormously here - it's the shared reference that surfaces hidden disagreements. The UX need is about *producing something others will read and respond to*, not just about the builder's own thinking.

**Entry point:** May start as a deliberate process ("let's write up what we're building") or emerge from individual use ("I wrote this up with the clarity agent. Does this match your understanding?").

### "I need to bring someone (or something) up to speed."

The "someone" might be a new team member, a coding agent starting a new session, or the user's own future self. The artifact is the entire value. The UX need is about *readability and navigability* of the protocol documents, not about the conversational process.

**Entry point:** The `.clarity-protocol/` directory, the AGENTS.md file (for coding agents), or a generated review packet.

### "Something changed and I need to know what to revisit."

Requirements shifted, a decision got challenged, new information arrived. The user needs to understand the ripple effects across their design. This is where staleness tracking and the dependency graph earn their keep.

**Entry point:** The packet status check at session start, or a deliberate "what's stale?" query.

### "We need this on the record."

The user needs structured documentation that captures what was considered, what was decided, and what risks were identified for compliance, communication, or organizational memory. They may or may not care deeply about the thinking process itself, but the artifact needs to exist and be credible. In practice, this job is often held by someone who *does* care about safety and quality, working in an environment where others might prefer to move fast without examining risks.

A well-structured clarity protocol makes it natural and non-controversial to have failure modes, risk decisions, and design rationale documented framed as good record-keeping rather than blame assignment.

**Entry point:** May come through any path, but the review packet generator and the persistent protocol directory are the key outputs.

## Primary Personas

The three personas below are the initial target userbase. Each has a different relationship to structured thinking, works in different tools, and needs Clarity to reach them differently. The jobs-to-be-done above describe *what* someone is trying to accomplish; the personas describe *who* is doing it and *how Clarity meets them*.

Together they cover a complete building flow — from defining the problem (PM), to building the solution (engineer), to the rapidly growing population of people doing both at once with AI but without the planning instincts that traditionally came with engineering experience (citizen developer). These are also the three populations where AI tool adoption is fastest, which means they're where the "agreeable AI" problem from the problem statement is most acute.

**Personas considered but deferred:** *Founders and solo builders* blur the PM/engineer line — they're consciously building a product and know every choice is consequential, but they're wearing every hat at once. Unlike citizen developers (who don't know what they don't know), founders know the stakes but can't hold everything coherent simultaneously. They may be the highest-value early adopter of the full Clarity process, and they don't fit neatly into any of the three personas above. Worth revisiting as a distinct persona once the initial three are well-served. *Designers* face a similar "agreeable AI" problem as AI design tools mature, but would need different thinker perspectives (usability, accessibility, interaction patterns) to serve well — a later expansion.

### Citizen Developers

People shipping software through vibe-coding tools — Cursor, Bolt, Replit, v0, Claude Code used casually — without formal engineering training or security instinct. They're building real things, often quickly, with AI doing most of the coding. They don't know what they don't know about auth, data handling, payment flows, or API trust boundaries.

**Relationship to Clarity:** The value proposition appeals to them — they know they're not software experts and want help thinking like one. They'll try it out. The challenge isn't discovery, it's *timing*: they don't have the instinct for when to invoke structured thinking. They won't pause before choosing an auth pattern because they don't recognize it as a consequential moment. Clarity needs to both be available when they seek it out *and* show up at critical moments they wouldn't recognize — when the code touches auth, payments, user data, or external APIs. The intervention is context-aware: fix clear issues automatically (linter mode), open a conversation when there's genuine ambiguity (e.g., "what's your trust model for this API?").

**What they need:** Checklists and warnings, not protocol documents. Security thinking injected where it never existed. Graduated depth — start with a nudge, go deeper only when the situation warrants it.

**Where they are:** Cursor, Bolt, Replit, v0, Claude Code. Integration via rules files (`.cursorrules`, `CLAUDE.md`), MCP `clarity-check` tool, `/clarity-secure` skill, deploy gates.

**Primary jobs:** "I have an idea and need to figure out what I actually want," "I'm about to build something and need to think about what could go wrong." These users are experts in their own domain — they know exactly *what* they want to build — but they haven't had reason to develop the project-planning and architecture instincts that come from years of shipping software. Clarity helps them think like a product builder: structuring requirements, anticipating failure modes, and making deliberate choices about trust boundaries and data flows.

**Key risk:** The timing gap — they'll use Clarity when they think to, but won't recognize many of the moments that matter most. Alert fatigue is the secondary risk: if the proactive interventions fire too often, they train themselves to dismiss everything, including real threats.

### Product Managers

PMs working alongside engineering teams, increasingly using AI tools — Claude Projects, ChatGPT, coding agents — to think through what to build. They need to translate rough product intuitions into specs clear enough that an engineering team or a coding agent can build from them.

**Relationship to Clarity:** They're thinkers looking for a thinking partner. They know they need to articulate what they want but struggle with the gap between "I have a vision" and "here's what to build." Clarity pushes back on vague specs, surfaces missing stakeholders, and demands testable success criteria — the kind of challenge they'd get from a great senior engineer, but earlier in the process.

**What they need:** The protocol as a handoff contract — what a PM produces with Clarity is what an engineer's coding agent consumes, eliminating the spec-to-implementation translation gap. They need persistence across sessions and something lightweight enough to not feel like "learning a tool."

**Where they are:** Claude Projects, ChatGPT, general-purpose AI tools. Near-term: light expression loaded as project knowledge (no tooling required). Later: MCP-enhanced AI tools for full staleness tracking and protocol management.

**Primary jobs:** "I have an idea and need to figure out what I actually want," "I need to get other people aligned." The protocol-as-handoff-contract is their unique contribution — bridging the gap between product thinking and engineering execution.

**Key risk:** Persistence is the gap. The light expression gives the full challenging disposition with zero setup, but without persistence it's a thinking tool that forgets. MCP closes the gap but adds friction the PM may resist.

### Professional Engineers

Software engineers using AI coding agents — Claude Code, Cursor, Copilot, VS Code, JetBrains — as a primary part of their workflow. They build complex systems, make architectural decisions, and need to think through failure modes, but they're under time pressure and won't context-switch to a separate thinking tool unless the value is immediate.

**Relationship to Clarity:** They know structured thinking matters — or at least, they've been burned when it didn't happen. They want it embedded in their existing workflow, not as a side quest. Clarity triggers at natural inflection points — when the coding agent recognizes a choice that would be expensive to reverse — and provides full infrastructure for deep analysis when they choose to go deeper.

**What they need:** AGENTS.md snippet for ambient awareness. MCP server for full infrastructure without leaving the editor. Quick-access commands for focused operations (`/fail-check`, `/decide`, `/clarity`). PR review integration for catching drift between thinking and building. Post-incident integration for closing the loop between failure analysis and reality.

**Where they are:** Claude Code, Cursor, Copilot, VS Code, JetBrains. Integration via rules files, MCP server, slash commands, IDE extensions (VS Code sidebar), PR review hooks, post-incident workflows.

**Primary jobs:** "I'm about to build something and need to think about what could go wrong," "Something changed and I need to know what to revisit," "We need this on the record."

**Key risk:** Agent misjudges when to trigger — too often is annoying, too rare means missed decisions. Also: the tool becomes furniture if it's always visible but never prompts action.

### Cross-Cutting: Decision Coherence

Every persona shares a fundamental need: decisions made at any point — architectural choices, scope tradeoffs, risk acceptances — must stay aligned with the problem statement, requirements, and stakeholder needs. Without active tracking, it's easy for individual decisions to be locally reasonable but collectively contradictory. Clarity's dependency graph and staleness tracking exist precisely for this: when something upstream changes, downstream decisions get surfaced for review. But even without upstream changes, the agent should catch when a new decision conflicts with existing ones.

How this plays out differs by persona:

- **Citizen developers** need Clarity to catch decisions they didn't realize they were making — choosing a database, exposing an API, storing user data. These are architectural choices with implications for security, privacy, and scalability that the user may not recognize as decisions at all.
- **Product managers** work upstream: when the problem evolves — a new customer conversation, a shifted market, a stakeholder concern — they need to see how that change ripples into the existing solution, architecture, and failure analysis. A PM who refines the problem statement should immediately understand what downstream thinking needs revisiting.
- **Professional engineers** work downstream: when they make implementation choices — a framework, a data model, an auth pattern — they need to see how those choices trace back to requirements and stakeholder needs. An engineer who picks a technology should be challenged if it contradicts a requirement they may not have read recently.

This coherence function matters most across the PM-to-engineer handoff, where upstream and downstream ownership split across people and tools. But solo builders benefit too: you-in-week-three may not remember the tradeoff you-in-week-one made.

### Cross-Cutting: Adaptive Depth

All three personas use the same process guides, but at different depths. Clarity calibrates from the conversation itself — every exchange, not as a one-time assessment. A citizen developer who says "I want to build an app" gets drawn out through follow-up questions. A PM who brings a crisp audience definition gets challenged on gaps. A senior engineer in a hurry gets focused failure analysis, not basics. The teaching mechanism is the same: draw out before filling in, push one level beyond where the user is, name the pattern without lecturing.

### Cross-Cutting: The Composability Model

One installation, multiple surfaces. The protocol format is the interop layer across all three personas. Every integration starts light (checklist → focused analysis → full process). MCP is the universal connector: one server, many clients.

## Situational Dimensions

Beyond personas, several dimensions shape what a user needs:

**New project vs. evolving project.** A new project is mostly "figure out what I want." An evolving project is harder: the system has accumulated implicit assumptions baked into code and organizational memory, and the user needs to re-derive clarity about something that's already partially built. The conversation is fundamentally different — not starting from a blank page, but from "we have this thing, and now we need to change it, and we don't fully understand what we have."

**How much is legible vs. in people's heads.** People assume that because a software system exists, "what it does" is knowable from the code. But code expresses *how it's implemented*, not *what it's for* or *how users think about it*. The product-as-understood-by-users — the mental model, the flows, the expectations — is often nowhere in code, especially in web services where software boundaries and product boundaries don't align. The clarity agent can't just "read the codebase and understand the project." It needs to draw out the stuff that isn't written down.

**Values quality vs. wants to externalize risk.** Most users fall somewhere on a spectrum. Some genuinely want to build well. Others want to ship fast and are content to let failures land on end users or downstream teams, so long as they never have to overtly acknowledge the choice. The clarity agent serves both — the first group through better thinking, the second group because compliance and communication are non-controversial values, and a well-structured record quietly makes it harder to claim that risks weren't known.

## UX Implications

These stakeholder patterns required multiple entry points and interaction models — all now shipped:

- A **conversational mode** for deep thinking (Jobs 1, 2, 3) — web UI, CLI, desktop app, VS Code sidebar
- An **embedded mode** that integrates into coding agent workflows and intercepts users who wouldn't seek out the tool deliberately (Job 2) — AGENTS.md/CLAUDE.md snippet, MCP server
- A **reading/reference mode** for the protocol as a navigable artifact (Jobs 4, 6) — protocol viewer in web/desktop/VS Code, generated review packets
- A **status/alert mode** for change tracking (Job 5) — packet status checker at session start, status panel in web/desktop

These are different products sharing a protocol format and session infrastructure, confirming the stakeholder analysis: a single UX can't serve all these jobs well.

## Other Stakeholders

**External regulators and stakeholders.** Software is increasingly a regulated industry, and many other domains where clarity-agent techniques apply (healthcare, finance, infrastructure) already are. Regulators need evidence of structured thinking: what was considered, what was decided, what risks were identified and how they're managed. The clarity protocol's structure aligns well with these requirements — not coincidentally, as the authors have spent significant time engaging with regulators on these ideas. The protocol format serves as a natural compliance artifact without needing to be reframed or reformatted for regulatory audiences.

**End users of systems built with the clarity agent.** They never interact with the tool, but benefit (or suffer) based on whether the clarity process produced well-designed systems with appropriate failure mitigations. Their proxy voice in the process is the failure analysis — especially the human-factors thinker.

**Framework maintainers.** The people building and extending the clarity agent itself. They need the architecture to be extensible (new thinkers, process guides, and LLM backends via file addition, not core changes) and the self-hosting model to work well — if using the clarity protocol on this project is awkward, it'll be awkward for users too.

**Open source contributors and integrators.** With the project open-sourced under MIT, contributors may submit new thinkers, process guides, LLM backends, or bug fixes. Integrators may embed Clarity's process guides, protocol format, or MCP server into their own tools. Contributors need a clear contribution path (CLA, coding conventions, registry sync invariants). Integrators need stable interfaces — especially the protocol format and MCP tool surface — and confidence that the framework won't change underneath them without warning.
