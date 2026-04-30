# Stakeholders

## Jobs to Be Done

The clarity agent serves different people in different situations — but the most useful way to think about stakeholders is through what they're *trying to do* when they encounter the tool, because the job shapes the UX far more than the role does.

### "I have an idea and I need to figure out what I actually want."

The most fundamental job. Someone has a rough notion — a feature, a product, a project — and needs to develop it into something concrete enough to act on. The value is primarily *in their head*: the process of being challenged and questioned is the product. The artifact is a useful byproduct.

This user might be a solo developer, a founder, a PM, or someone planning a non-software project. They know they need to think things through (or at least suspect it) and are looking for a thinking partner.

**Entry point:** Comes to the clarity agent directly — web UI, CLI, or embedded in their coding agent.

### "I'm about to build something and I need to think about what could go wrong."

The user already has reasonable clarity on *what* they want, but hasn't done failure analysis. They need adversarial, operational, and human-factors perspectives they can't generate alone. The value is partly in sharpened thinking and partly in the artifact (a persistent record of failure modes and management plans).

**Entry point:** Likely already in a coding agent flow; the AGENTS.md integration intercepts them naturally.

### "I need to get other people aligned on what we're doing and why."

The team coordination job. People routinely *believe* they agree about what they're building, but actually don't. The artifact matters enormously here — it's the shared reference that surfaces hidden disagreements. The UX need is about *producing something others will read and respond to*, not just about the builder's own thinking.

**Entry point:** May start as a deliberate process ("let's write up what we're building") or emerge from individual use ("I wrote this up with the clarity agent — does this match your understanding?").

### "I need to bring someone (or something) up to speed."

The "someone" might be a new team member, a coding agent starting a new session, or the user's own future self. The artifact is the entire value. The UX need is about *readability and navigability* of the protocol documents, not about the conversational process.

**Entry point:** The `.clarity-protocol/` directory, the AGENTS.md file (for coding agents), or a generated review packet.

### "Something changed and I need to know what to revisit."

Requirements shifted, a decision got challenged, new information arrived. The user needs to understand the ripple effects across their design. This is where staleness tracking and the dependency graph earn their keep.

**Entry point:** The packet status check at session start, or a deliberate "what's stale?" query.

### "We need this on the record."

The user needs structured documentation that captures what was considered, what was decided, and what risks were identified — for compliance, communication, or organizational memory. They may or may not care deeply about the thinking process itself, but the artifact needs to exist and be credible. In practice, this job is often held by someone who *does* care about safety and quality, working in an environment where others might prefer to move fast without examining risks. A well-structured clarity protocol makes it natural and non-controversial to have failure modes, risk decisions, and design rationale documented — framed as good record-keeping rather than blame assignment.

**Entry point:** May come through any path, but the review packet generator and the persistent protocol directory are the key outputs.

## Situational Dimensions

Beyond jobs-to-be-done, several dimensions shape what a user needs:

**New project vs. evolving project.** A new project is mostly "figure out what I want." An evolving project is harder: the system has accumulated implicit assumptions baked into code and organizational memory, and the user needs to re-derive clarity about something that's already partially built. The conversation is fundamentally different — not starting from a blank page, but from "we have this thing, and now we need to change it, and we don't fully understand what we have."

**How much is legible vs. in people's heads.** People assume that because a software system exists, "what it does" is knowable from the code. But code expresses *how it's implemented*, not *what it's for* or *how users think about it*. The product-as-understood-by-users — the mental model, the flows, the expectations — is often nowhere in code, especially in web services where software boundaries and product boundaries don't align. The clarity agent can't just "read the codebase and understand the project." It needs to draw out the stuff that isn't written down.

**Knows they need to think vs. doesn't.** The user who knows they need structured thinking is already sold — they just need a good thinking partner. The user who doesn't know will go to their AI, say "build me X," and start getting code. This second user is only reachable if the clarity agent is *embedded in the moment of creation* — woven into the tool they're already using, not a separate destination.

**Values quality vs. wants to externalize risk.** Most users fall somewhere on a spectrum. Some genuinely want to build well. Others want to ship fast and are content to let failures land on end users or downstream teams, so long as they never have to overtly acknowledge the choice. The clarity agent serves both — the first group through better thinking, the second group because compliance and communication are non-controversial values, and a well-structured record quietly makes it harder to claim that risks weren't known.

## UX Implications (Open Questions for Solution Design)

These stakeholder patterns suggest the system may need multiple entry points and interaction models:

- A **conversational mode** for deep thinking (Jobs 1, 2, 3)
- An **embedded mode** that integrates into coding agent workflows and intercepts users who wouldn't seek out the tool deliberately (Job 2, and critically, the user who doesn't know they need to think)
- A **reading/reference mode** for the protocol as a navigable artifact (Jobs 4, 6)
- A **status/alert mode** for change tracking (Job 5)

Whether these are four features of one product, or different products sharing a protocol format, is a solution-level question. But the stakeholder analysis makes clear that a single UX can't serve all these jobs well.

## Other Stakeholders

**External regulators and stakeholders.** Software is increasingly a regulated industry, and many other domains where clarity-agent techniques apply (healthcare, finance, infrastructure) already are. Regulators need evidence of structured thinking: what was considered, what was decided, what risks were identified and how they're managed. The clarity protocol's structure aligns well with these requirements — not coincidentally, as the authors have spent significant time engaging with regulators on these ideas. The protocol format serves as a natural compliance artifact without needing to be reframed or reformatted for regulatory audiences.

**End users of systems built with the clarity agent.** They never interact with the tool, but benefit (or suffer) based on whether the clarity process produced well-designed systems with appropriate failure mitigations. Their proxy voice in the process is the failure analysis — especially the human-factors thinker.

**Framework maintainers.** The people building and extending the clarity agent itself. They need the architecture to be extensible (new thinkers, process guides, and LLM backends via file addition, not core changes) and the self-hosting model to work well — if using the clarity protocol on this project is awkward, it'll be awkward for users too.
