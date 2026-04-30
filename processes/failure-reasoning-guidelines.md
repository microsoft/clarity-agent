# Failure Reasoning Guidelines

These guidelines apply to all stages of failure reasoning: brainstorming, analysis, and management. They are included automatically in thinker prompts and referenced by the failure process guides.

## Guideline 1: Analyze the complete system, including its human and social context

The object of failure planning is the system *as it is used* — including all the human factors and social consequences. Humans are components of the system, with capabilities and weaknesses just like any technical component.

This means:

- **Operators** can make bad judgment calls, especially under pressure or fatigue. Incident response at 3am by a groggy engineer is a different system than incident response at 2pm by an alert one.
- **Users** behave in ways the system doesn't expect — not because they're adversarial, but because they have their own goals, mental models, and constraints. A perfectly secure system that's too annoying to use will be bypassed.
- **Organizations** have dynamics that affect how systems work in practice: communication gaps, incentive misalignments, staffing constraints, institutional knowledge that lives in people's heads.
- **Social consequences** matter. A system that works correctly in a technical sense but causes social harm (embarrassment, loss of trust, exclusion) has failed.

When analyzing failures, don't stop at "the technical component fails." Ask: what does the human do next? What pressures are they under? What information do they have? What do they get wrong, and why?

Pay particular attention to:

- **The system's human context**: Who operates this system? Who uses it? What pressures are they under? Humans are components of the system — their behavior under stress, their workarounds, their misunderstandings are all sources of failure. (See Guideline 1 in the shared guidelines.)
- **What counts as meaningful harm here**: The system's context determines which failures matter. A personal tool and a public service have very different failure landscapes. Don't generate failures that wouldn't cause real harm to anyone in this system's actual context. (See Guideline 2.)
- **The prior state**: How does the world work *before* this solution exists? Some failures you'll identify already exist today. Noting this during brainstorming (via the `pre_existing` flag) saves significant work during analysis, where pre-existing failures can be triaged quickly.
- **Adversarial stakeholders**: Their documented objectives define specific threats. "The scraper wants to extract all listing data" generates more focused raw failures than "what if someone scrapes us."
- **Dual-nature stakeholders**: Aligned in some contexts, adversarial in others. These are often hardest to brainstorm for because the failure modes involve legitimate access being misused.
- **Indirect stakeholders**: People affected by the system who aren't users. Easy to miss, important to find. A failure that harms someone who doesn't even know the system exists is particularly insidious.

## Guideline 2: Focus on meaningful harm

A failure is only a failure if it causes meaningful harm to someone. The person or group harmed should be a non-adversarial stakeholder. If you identify someone harmed who isn't already on the stakeholder list, that's a sign they should be added.

**Context determines what's meaningful.** A failure that matters for a public-facing service with millions of users may be irrelevant for a personal tool. If the system is being built for one person's use, failure modes involving "what if an arbitrary user does X" are probably not interesting. The question is always: in the full context of how this system will actually be used, does this failure lead to real harm?

Failures that don't lead to meaningful harm in context can be safely discarded at any stage — brainstorming, analysis, or management. A violated principle that doesn't lead to actual harm is not a failure mode. "The plan is messy" isn't a failure. "The plan is messy, so the team makes a decision that meaningfully harms users (or anyone else who depends on the outcome)" is — but only if there's actually someone who gets hurt.

This is not a license to dismiss failures as unlikely. The question is not "how likely is this?" but "if this happens, does anyone actually get hurt?" If the answer is yes, it's a real failure mode regardless of probability. If the answer is no, it's not worth analyzing further.
