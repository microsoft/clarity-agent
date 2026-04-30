# Requirements

## The Agent as Thinking Partner

**FR1 — Guided problem clarification.** The agent must guide users through articulating what they're actually trying to build: a clear problem statement, identified stakeholders, and concrete requirements. The output must be testable success criteria, not just a description. The agent should draw out assumptions the user hasn't examined and surface disagreements within teams about what the project *is*.
*Traced to: "I need to figure out what I actually want," "I need to get people aligned"*

**FR2 — Challenging disposition.** The agent must actively push back on vague reasoning, unexamined assumptions, and premature commitment to solutions. It should ask hard questions rather than validating whatever the user says. This is not a stylistic preference — it is the core value proposition. An agent that merely agrees and documents is not solving the problem.
*Traced to: Problem statement — AI agreeableness as a complication; "I need to figure out what I actually want"*

**FR3 — Failure mode brainstorming.** The system must run multiple AI-powered thinker perspectives (security, human factors, adversarial, operational, and others) against the problem and solution, surfacing failure modes the user would not identify alone. Thinkers must operate independently to avoid groupthink, and the system should support running them in parallel for efficiency.
*Traced to: "I need to think about what could go wrong"; problem statement — failure thinking as a learned skill*

**FR4 — Failure analysis and management.** The agent must support grouping raw brainstormed failures into coherent failure modes with causal chains and intervention points, and developing management plans for each. The result should be a persistent, reviewable record of what can go wrong and how it's handled.
*Traced to: "I need to think about what could go wrong," "We need this on the record," external regulators*

**FR5 — Decision documentation and reconsideration.** The agent must capture design decisions with context, evaluated alternatives, and rationale. When inputs that grounded a decision change, the system must surface the decision for potential reconsideration — not silently let it become stale.
*Traced to: "I need to bring someone up to speed," "We need this on the record," external regulators*

## The Protocol as Persistent Artifact

**FR6 — Persistent, human- and machine-readable protocol.** All protocol outputs must be persistently stored in a format that is readable by both humans and LLMs without specialized tooling. For software projects, the outputs should be version-controllable and diffable alongside the code they describe. The protocol is the system's primary persistence layer and its interface with the outside world.
*Traced to: All jobs — but especially "bring someone up to speed," "get people aligned," "on the record"*

**FR7 — Defined protocol format.** The structure and conventions of protocol documents must be explicitly specified — not just implied by whatever the process guides happen to produce. The format specification must define document types, required sections, summary layers (critical content first, detail on demand), and length guidance. This specification serves three purposes: it is the interoperability contract across products (FR10, FR11), the mechanism for managing verbosity (documents that grow unchecked undermine every use case), and a testable standard that tooling can validate against.
*Traced to: All protocol-dependent jobs; conciseness as structural mitigation (failure analysis); product interoperability (solution — Layer 1 artifact)*

**FR8 — Document staleness tracking.** When a protocol document is updated, the system must detect which downstream documents have become stale (based on a defined dependency graph) and surface this to the user. Staleness detection must be based on content changes (not timestamps) to survive version control operations.
*Traced to: "Something changed and I need to know what to revisit"*

**FR9 — Review packet generation.** The system must generate formatted review documents (at minimum Markdown and DOCX) from the protocol, suitable for sharing with stakeholders, regulators, or collaborators who don't have access to the tool. The packet should present a coherent narrative, not just concatenated files.
*Traced to: "We need this on the record," "get people aligned," external regulators*

## Entry Points and Integration

**FR10 — Accessible to the deliberate user.** The framework must support users who come to it intentionally — to start a new project, revisit an existing one, or run a dedicated thinking session. These users know they want structured thinking and need a way to get to it directly.
*Traced to: "I need to figure out what I actually want," "I need to think about what could go wrong," "I need to get people aligned"*

**FR11 — Reachable in the flow of creation.** The framework must also be able to reach users who are already in the process of building — including those who don't yet know they need to think things through. This means the system must be embeddable in existing workflows and tools, so that structured thinking can be introduced at the natural moment rather than requiring a deliberate detour. This is the primary path to broad adoption.
*Traced to: "I'm about to build something," the "doesn't know they need to think" user; problem statement — meeting users where they already are*

**FR12 — Evolving project support.** The framework must support working with existing, partially-built projects — not just greenfield ones. This means the agent must be able to help users re-derive clarity about systems that already have implicit assumptions baked into code and organizational memory, not only build clarity from scratch.
*Traced to: Situational dimension — new vs. evolving projects*

**FR13 — Multiple LLM backend support.** The framework must support multiple LLM providers (Anthropic, OpenAI, Azure, and others) through a common interface, without changing process logic. Users and organizations have existing provider relationships and constraints.
*Traced to: Framework maintainers; adoption breadth*

## Non-Functional Requirements

**NFR1 — Conversation-first UX.** The agent must feel like a thoughtful conversation with a skilled colleague, not a form or wizard. Users should not be aware of the underlying process machinery during normal use. The agent should move quickly past things the user already understands and slow down only for genuine ambiguity or meaningful tradeoffs.
*Traced to: Problem statement — the conversation is where thinking happens; "I need to figure out what I actually want"*

**NFR2 — Low friction for small projects.** Protocol initialization and problem clarification must be completable in under 15 minutes for a well-understood project. The framework must scale down to solo use without requiring team ceremony. A single developer with a side project is as valid a user as a team building a complex system.
*Traced to: "I need to figure out what I actually want" (solo variant); problem statement — broad applicability*

**NFR3 — Extensibility.** Adding a new thinker perspective, process guide, LLM backend, or output format must not require changes to core framework logic — only addition of a new file or implementation. This is both a maintainability requirement and the mechanism that enables future domain expansion beyond software.
*Traced to: Framework maintainers; scope — architecture designed for domain extensibility*

**NFR4 — Self-hosting.** The clarity-agent project must use its own clarity protocol. The `.clarity-protocol/` directory in this repo is the canonical protocol for the framework. If the framework is awkward to use on itself, it's awkward for users.
*Traced to: Framework maintainers*

**NFR5 — Process guides as LLM-readable logic.** All process guides must be plain markdown that any capable LLM can follow without tool-specific extensions. The guides *are* the logic; the Python infrastructure handles mechanics. This ensures the framework's core value is portable across LLM providers and inspectable by humans.
*Traced to: Framework maintainers; NFR3 — extensibility*

**NFR6 — Protocol as compliance artifact.** The protocol document structure and format must be suitable for use as evidence of structured design thinking in regulated environments — without requiring reformatting, translation, or additional documentation effort. The protocol should naturally capture what was considered, what was decided, what risks were identified, and how they're managed.
*Traced to: "We need this on the record," external regulators*
