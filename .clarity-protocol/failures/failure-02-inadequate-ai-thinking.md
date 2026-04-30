# Failure: The AI produces inadequate thinking

## Summary

The AI agent follows the *form* of the clarity process without the *substance* — skipping steps, producing generic outputs, generating plausible-sounding documents that don't reflect deep analysis of the specific system. Users believe they've done rigorous structured thinking when they haven't. This is the tool's version of the agreeableness problem it was designed to solve: it creates the illusion of rigor.

## Failure Chain

1. The AI is given a process guide and project context (problem, solution, architecture).
2. The AI begins following the process. It produces output that is structurally correct — right sections, right vocabulary, reasonable-sounding analysis.
   - *Observation:* Structural correctness and substantive quality are independent. An AI can produce a perfectly formatted failure mode document that contains nothing the user couldn't have found in a generic checklist.
3. The AI takes shortcuts. Forms vary by variant:
   - *Step skipping:* The AI decides certain steps are obvious and skips them, or claims to have done analysis it hasn't actually performed.
   - *Generic output:* Thinker produces boilerplate failures ("SQL injection," "unauthorized access") rather than failures specific to this system's design, context, and stakeholders.
   - *Shallow evolving-project analysis:* For existing systems, the AI can only work with what the user tells it. If the user doesn't know what they don't know, the AI can't surface it. The protocol describes the user's mental model, not the system itself.
   - *No quality signal:* There is no mechanism to distinguish good analysis from bad. A rushed protocol looks the same as a thorough one.
   - *Observation:* The AI's training incentivizes producing confident, well-structured output. This is precisely the wrong incentive for a tool whose value depends on admitting uncertainty and finding gaps.
4. The user receives the output and trusts it. **Harm begins** — the user now has false confidence in their understanding.
   - *Intervention point (user verification):* Prompt the user to challenge the output: "Does this match your experience? What's missing?"
   - *Intervention point (specificity check):* The agent could self-assess: "Am I producing analysis specific to this system, or could this apply to any system?"
5. Decisions are made based on incomplete or generic analysis. Failure modes that should have been caught are missed. Requirements that should have been challenged pass through.
6. Problems surface during implementation or in production. **Harm continues** — and the existence of a "thorough" protocol makes it harder to recognize that the thinking was actually shallow.

## Observations

- **Severity:** High — undermines the core value proposition; creates false confidence that may be worse than no process at all
- **Related failures:** Group 2 (user disengagement) — if users disengage, the AI's inadequate output goes unchallenged. Group 4 (failure analysis depth) — generic thinker output is a specific instance of this broader problem.
- **Variants:**
  - AI agent skips process steps
  - Agent produces clarity theater
  - Generic thinker outputs
  - No way to validate protocol quality
  - Evolving project clarity is superficial

## Intervention Points

### Prevention
- Process guides should include self-check instructions: "Before recording this failure, verify it is specific to this system"
- Thinker guides should emphasize project-specific analysis over domain checklists
- For evolving projects, the agent should explicitly ask about areas the user might be uncertain about: "What parts of the current system do you understand least?"
- Layer 1 corpus should encode what distinguishes good analysis from plausible-sounding analysis

### Detection
- Track specificity: are failure modes, requirements, and decisions referencing concrete aspects of this project, or are they generic?
- Future: a review mode where a second pass evaluates the quality of the first

### Mitigation
- The user is the primary quality check — prompt them actively to challenge the output
- The general-thinker-first approach helps by producing a broad initial pass that the user can evaluate before investing in specialist analysis

### Recovery
- Protocol documents can be revisited and deepened in subsequent sessions
- The staleness tracker ensures that if upstream documents change, downstream analysis is flagged for review

---

## Management Plan

### Strategy

Prevention-heavy. The AI's thinking quality is primarily determined by the process guides and the agent's disposition — both of which are under our control. The invisible self-critique mechanism (from the Quality Architecture) is the core intervention. Detection relies on the user and on structural signals. Recovery leverages the protocol's iterability.

This failure interacts with FM01 (disengagement) bidirectionally: if the AI produces shallow output, disengagement is rational; if the user disengages, shallow output goes unchallenged. The shared interventions (early value, conciseness, adaptive calibration) are detailed in FM01's plan and cross-referenced here.

### Planned Interventions

**Prevention:**

- **Invisible self-critique** (chain step 3, all variants): Critique guides — Layer 2 artifacts — inform the agent's internal standard at every phase. These encode what the agent should watch for in its own output:
  - *Specificity check:* "Am I producing analysis specific to this system, or could this apply to any project?" If the answer is "any project," the output is inadequate.
  - *Step fidelity:* "Did I actually do the analysis the process guide calls for, or did I summarize what I think the answer should be?" Distinguishes performing the process from narrating its expected outcome.
  - *Evolving project awareness:* "Am I working with what the user told me, or am I inventing context?" For existing systems, the agent should name its uncertainty explicitly: "I'm working from what you've described — what parts of the current system do you understand least?"
  - These checks happen continuously as part of the agent's thinking, not as a visible separate step. (See Quality Architecture — Self-Critique.)

- **Process guide specificity requirements** (chain step 2): The Layer 1 corpus should encode what distinguishes good analysis from plausible-sounding analysis. This is then expressed in each process guide as specific quality bars — e.g., "every failure mode must reference a concrete aspect of this system's design" rather than "identify failure modes."

- **Shared interventions with FM01:** Early value delivery, adaptive calibration, and conciseness discipline (detailed in FM01 plan) all contribute to FM02 management. Conciseness in particular forces specificity — it's hard to write a short, generic observation.

**Detection:**

- **Structural quality signals** (chain step 3, variant "no quality signal"): The protocol format (FR7) should make quality visible through structure, not just content. Quality indicators include: failure modes that reference specific system components, management plans with walk-through-able steps, requirements traced to specific stakeholder needs, decision documents with concrete rejected alternatives.

- **User as quality check** (chain step 4, intervention point "user verification"): The agent should actively prompt the user to challenge its output at key moments — not generically ("does this look right?") but specifically ("I identified these three failure modes for your authentication system — what am I missing based on your experience with the codebase?").

**Long-term:**

- **Review process** (chain step 4): A second-pass review — by a different AI session, a colleague, or a structured self-review — is the highest-leverage future intervention. It addresses the fundamental problem that the agent can't reliably judge its own output quality. This is on the roadmap and would also address FM03 and FM04.
  - Trigger for moving from short-term to long-term: when the framework has enough users to validate review process patterns, and when the protocol format is stable enough to support structured review criteria.

### Accepted Risks

- The AI's capability ceiling is real. No amount of guide quality or self-critique can make an LLM produce analysis it's not capable of. For domains where the LLM's training data is thin, output quality will be limited regardless.
- Invisible self-critique depends on the LLM following dispositional instructions reliably. Current models are imperfect at this — they sometimes ignore or inconsistently apply internal standards. This will improve with model capability but is a present limitation.
- For evolving projects, the AI fundamentally can't know what it doesn't know. It can only work with what the user provides. If the user doesn't realize what's implicit, the AI can't surface it. The "what do you understand least?" prompt helps but doesn't solve the problem.

### Monitoring

- **Specificity ratio:** In failure analysis, what fraction of failure modes reference concrete system components vs. generic categories? This is measurable by inspection and could eventually be automated.
- **User challenge rate:** How often does the user push back on the agent's output? Counterintuitively, more pushback may indicate better quality — the agent is producing specific enough claims to be challengeable, and the user is engaged enough to challenge them.
- **Iteration depth:** How many times do key documents get revised? More revision suggests genuine iterative thinking rather than first-draft acceptance.
