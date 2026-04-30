# Failure: The process fails to achieve actual alignment

## Summary

The clarity protocol is supposed to surface hidden disagreements within teams and maintain shared understanding over time. This failure mode is when it doesn't — when the protocol exists, people believe they're aligned, but they actually aren't. The protocol creates false confidence in agreement, which may be worse than having no shared document at all, because it suppresses the conversations that would have revealed the misalignment.

## Failure Chain

1. A team member (or solo builder) runs the clarity process and produces protocol documents: problem statement, stakeholders, requirements, solution.
2. The documents are shared with the team (or exist for the user's future self).
   - *Observation:* "Shared" often means "put in the repo." It does not mean "read carefully and critically examined."
3. Other team members read the documents — or more commonly, skim them — and nod. They interpret the text through their own mental models, silently filling in gaps and resolving ambiguities in ways that may differ from the author's intent. **Harm begins.**
   - *Intervention point (active review):* Instead of passive sharing, the process could require active engagement — each stakeholder marks specific sections as "agree," "disagree," or "need to discuss."
   - *Intervention point (structured disagreement):* The protocol could include prompts designed to surface disagreement: "What in this document do you think is wrong or incomplete?"
4. Development proceeds on the basis of assumed alignment. Different team members make implementation decisions based on different understandings of the requirements and solution.
   - *Observation:* This is exactly the dynamic the protocol was supposed to prevent, now reinforced by the false confidence of a shared document.
5. Misalignment surfaces during implementation — conflicting PRs, features that don't fit together, arguments about scope that reveal different understandings of the problem.
6. The team must re-derive alignment, now with the additional cost of undoing work and the social friction of "but we agreed on this." **Harm continues** until the misalignment is actually resolved.
   - *Intervention point (trace back):* When disagreements arise at the solution level, the agent should guide the team to re-examine the problem statement. Solution-level disagreements often have their root in different understandings of the problem.
   - *Observation:* Users don't intuitively trace disagreements back to the problem. This is a learned skill that the process guides need to actively teach.

**Variant chain — protocol treated as done:**

1. The team produces a thorough clarity protocol at project inception.
2. Months pass. Requirements shift through conversations, Slack messages, and stakeholder feedback. The protocol isn't updated.
3. A new team member reads the protocol and implements against the original design. **Harm begins** — the protocol now actively misleads.
   - *Intervention point (staleness as engagement):* The staleness tracker flags changes, but the team has to actually re-engage with the documents. If they've mentally moved on, alerts are ignored.
4. The new team member's work conflicts with the team's evolved (but undocumented) understanding. The protocol that was supposed to help onboarding has made it worse.

## Observations

- **Severity:** High — undermines the team coordination value proposition; false alignment may be worse than acknowledged misalignment
- **Related failures:** Group 2 (user disengagement) — if people skim rather than read, alignment can't be achieved. Group 1 (inadequate AI thinking) — if the documents are vague, they're easier to misinterpret.
- **Variants:**
  - Users don't trace disagreements back to the problem
  - Hidden team misalignment persists despite protocol
  - User treats protocol as done rather than living

## Intervention Points

### Prevention
- Process guides should encourage active review, not passive sharing
- Documents should be written to minimize ambiguity — concrete examples, testable criteria, explicit rather than implied
- The agent should teach users to trace solution-level disagreements back to the problem level
- The protocol should include prompts designed to surface disagreement

### Detection
- Staleness tracking catches document-level drift
- Future: a review process where multiple team members independently engage with the protocol and disagreements are surfaced

### Mitigation
- When disagreements arise, the agent should guide users back to the problem statement
- The agent should flag when documents haven't been updated despite significant elapsed time

### Recovery
- The protocol structure makes it possible to re-derive alignment — the documents are there, they just need updating
- The dependency graph shows what needs revisiting when upstream documents change

---

## Management Plan

### Strategy

Prevention through document quality and format design. Detection through staleness tracking and active review prompts. The core insight: false alignment arises from ambiguity in the artifacts and passive consumption of them. Both are addressable.

This failure interacts with FM01 (if people skim, alignment can't be achieved), FM02 (vague AI output is easier to misinterpret), and FM05 (compliance theater produces alignment artifacts without alignment). The shared interventions — conciseness, specificity, the protocol format spec — are detailed in FM01 and FM02's plans.

### Planned Interventions

**Prevention:**

- **Specificity and testability in protocol documents** (chain step 3, intervention point "structured disagreement"): The agent's invisible self-critique should continuously check for ambiguous language that different readers might interpret differently. Concrete markers: success criteria must be testable, requirements must be verifiable, decisions must state what was rejected and why. The protocol format (FR7) should encode these as structural requirements — not style guidelines the agent might ignore, but section-level expectations that make vagueness structurally visible (e.g., a "verification method" field on each requirement).

- **Active engagement prompts** (chain step 3, intervention point "active review"): When the protocol is shared with a team, the process should encourage active review rather than passive sharing. Short-term: the process guides should suggest structured review practices — "ask each team member to identify one thing they disagree with or don't understand." Long-term: a formal review process (shared intervention with FM02 and FM04).

- **Trace-back teaching** (chain step 6, intervention point "trace back"): The agent should teach the skill of tracing solution-level disagreements back to the problem statement. When the user reports a disagreement ("the frontend team wants X, the backend team wants Y"), the agent should guide them to examine whether they actually agree on the problem and stakeholder needs, rather than debating the solution directly. This is a Layer 1 principle — it should be in the intellectual corpus as a named technique.

**Detection:**

- **Staleness tracking** (variant chain, step 3): Already built. The dependency graph catches document-level drift. The intervention point is ensuring teams actually re-engage when flagged, not just acknowledge the alert.

- **Time-based re-engagement prompts** (variant chain, step 2): For evolving projects, the agent should prompt re-engagement with the protocol at natural intervals — not calendar-based ("it's been 30 days") but event-based ("you've added three new API endpoints since the architecture was written — should we revisit?"). This requires integration context that only full-implementation products have. Short-term: the agent asks about changes at session start.

**Mitigation:**

- **Conciseness as ambiguity reduction** (chain step 3): Shorter, more specific text has less room for divergent interpretation. The summary-layer design from FR7 forces the most important content to be front-and-center, reducing the damage from skimming. (Shared intervention, detailed in FM01.)

**Long-term:**

- **Review process** (chain step 3): Independent review is the strongest intervention against false alignment — a reviewer who wasn't part of the original conversation brings fresh eyes and different interpretations. On the roadmap; shared with FM02 and FM04.

### Accepted Risks

- The system cannot force team members to engage deeply with the protocol. If someone nods without reading, the protocol creates false confidence. The review process partially mitigates this, but ultimately team engagement is an organizational behavior the tool can encourage but not guarantee.
- In solo use, "false alignment with your future self" is subtler and harder to detect — staleness tracking helps, but the user must actually re-engage with flagged documents.
- The light implementation has no staleness tracking. In those contexts, false alignment from document drift is largely unmitigated — the guide can encourage checking, but can't enforce it.

### Monitoring

- **Staleness response rate:** When the staleness tracker flags a document, does the user actually update it? A high ignore rate signals FM01 (disengagement) compounding FM03.
- **Disagreement surfacing rate:** In team use, how often does the clarity process surface a previously-hidden disagreement? This is the positive signal — the system doing its job.
- **Document revision after team review:** Documents that get revised after sharing indicate real engagement; documents that don't may indicate passive acceptance.
