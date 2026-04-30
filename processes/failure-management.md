# Failure Management

This process develops management plans for identified failure modes. It takes failure mode documents that have chains and intervention points but no management plans, and works out what to actually do about them.

## Overview

Failure analysis tells you *what* could go wrong and *where* you could intervene. Failure management decides *what to do about it* — which interventions to build, what residual risk to accept, and how to monitor for problems.

This is fundamentally a collaborative design exercise — the user and the agent work through plans together. Each management plan involves real tradeoffs (intervention cost vs. risk reduction, user friction vs. safety, short-term pragmatism vs. long-term robustness) and may involve modifications to the solution and architecture — sometimes very minor (adding a note about UX text), sometimes very major (rethinking the entire approach). **Always propose strategies and discuss them with the user before writing plans.** The user brings judgment about organizational context, acceptable cost, and stakeholder priorities that the agent can't infer from documents alone. Because major rethinking is possible, it's a good idea to start failure analysis and management as early as possible, before the architecture is committed to.

Every intervention has costs: development time, runtime performance, user friction, operational complexity. A management plan balances the cost of intervention against the severity of the failure and the acceptable level of residual risk from all stakeholders' perspectives.

Management plans should also consider interactions between failure modes. Sometimes a single mechanism addresses several failures. Sometimes mitigating one failure makes another worse. Sometimes the management plan for one failure creates a new failure mode that needs its own plan. These interactions are why failure management works best as a holistic process rather than treating each failure in isolation.

**In the course of developing a management plan, you may discover new stakeholders, new stakeholder goals, or changes to the requirements.** These are legitimate outcomes of the analysis. Edit the stakeholder and requirements files directly during this process — don't wait for a separate "update stakeholders" step.

## Key Principles

These principles guide how management plans are developed. They reflect hard-won lessons about what works (and what doesn't) in practice.

### Principle 1: If the risk creates tension with the problem statement, clarify the problem

A seeming contradiction between a failure mode's management and the problem statement is always a sign that it's time to "go back to basics." Return to the **problem-clarification** process, this time keeping the failure mode(s) causing the tension front and center.

Ask: what do each of the stakeholders really want to happen in these situations? Zoom in on what's *actually* important to each stakeholder versus nice-to-have. If the stakeholders' interests aren't genuinely adversarial to each other, it's usually possible to figure out a restatement of their requirements that dissolves the tension. With that in hand, return to the management plan and update the solution to match.

Sometimes this is not possible: what one stakeholder wants directly goes against the wishes of another. In this case, the user has to make some decisions. Do you attempt some kind of compromise? Do you favor one stakeholder over the other, essentially regarding one as adversarial in this context? Use **decision-guidance** to work through these.

Sometimes this reveals the genuine impossibility of the entire solution approach. This is rare but it happens. In that case, clearly write up the problem statement including these failure modes, and append an explanation of why the solutions considered so far don't resolve it. This is valuable output — it saves everyone from continuing down a dead end.

**The deeper the change to the solution, the more important it is to re-check whether it still addresses the underlying problem.** Keep the problem statement firmly in mind throughout management planning.

### Principle 2: Be flexible about what constitutes a management plan

Sometimes you're changing a system to avoid a risk. Sometimes you're preparing an incident response plan. Sometimes you're changing how you communicate about the system — UX text, marketing, documentation. Any of these might be acceptable and appropriate, depending on the situation.

Sometimes fixes happen in very different parts of the system than where the problem appears to occur. For example, most privacy problems ultimately boil down to a mismatch between users' expectations of how data will be used and the reality. You sometimes fix this by changing how the data is used, and sometimes by changing the users' expectations — which you do by changing how you communicate in and about the product.

### Principle 3: The acceptance criterion is stakeholder sign-off on overall cost

Each management plan imposes costs: the work of changing a system, the ongoing operational work of running incident response, the costs imposed on users by the actual failures themselves. The ultimate criterion for whether the plan is acceptable is: "are the affected stakeholders willing to sign off on this?"

When review phases exist, this becomes "are all the reviewers willing to sign off?" — since reviewers generally represent the people who have to pay these costs.

### Principle 4: Short-term and long-term solutions can mix

Sometimes you'll do one thing in the short term (e.g., "we'll handle it manually via incident response if it happens") but expect a different approach in the long term. This may be because you don't know the details of how the failure will manifest, or because you don't know how frequent it will be yet, or because building the more robust solution will simply take time.

This is completely fine so long as you understand the short-term costs and those are acceptable. Note both the short-term approach and the conditions under which you'd move to the long-term one.

### Principle 5: Prioritize by severity, not severity times likelihood

In traditional risk management, risks are assigned severities and likelihoods, and their overall importance is described by the product of the two. This method was designed for insurance companies managing resource allocation over a pool of risks; it works great for that, but poorly for people whose job is to design, build, and operate systems. Three reasons:

1. You frequently end up multiplying large numbers (severity) by small numbers (likelihood), and the product is statistical noise — you don't get a good prioritization.
2. In many applications, especially computing ones, rates are high enough that everything is better understood as a matter of frequency, not likelihood. If something happens to one in a million users once a year and you have a billion users, that's a thousand times a year. In practice, likelihood is effectively 1 (certainty).
3. Severity and likelihood are both difficult to quantify, which leads to lengthy and often pointless arguments about prioritization.

The solution is simple: in most cases, you don't need to prioritize failures at all, but rather develop management plans for *all* of them. If you do need to sequence work — e.g., to plan a development roadmap — do it by looking at the costs of the short-term solution and which ones you need to mitigate fastest. If you're doing a very expensive manual incident response process very often, you may be inclined to automate that quickly.

### Principle 6: If you're adding a new component, design it properly

Many management plans involve adding new components to the system — incident response processes, monitoring systems, manual review workflows, moderation tools. These are new parts of the solution and the entire design process applies to them just like any other part of the system.

For incident response specifically, ask:

- Who needs to be called in?
- How quickly do they need to respond? (5-minute SLAs create very different work requirements than 1-business-day ones.)
- Will they have access to all the information they need to assess the situation?
- Will they have access to all the controls they need to bring the situation under control?
- Might they need to bring in additional people, and if so, do they have the right contacts and ways to reach those people at appropriate SLAs?
- If they have to do this in the middle of the night, will the system be simple enough to get into a "not bleeding" state while tired and groggy, or will they need to perform complex tasks?
- Is there adequate staffing to handle this at the rate it's likely to happen?

Note that nearly every system needs to deal with "unknown unknown" type failures — things you haven't anticipated that require conscious human intervention. This means nearly every system needs some form of incident response process, even if every known failure mode is handled through other means.

## When to Use This Process

Run this process when:

- Failure analysis has produced failure mode documents without management plans
- New failure modes have been identified and need plans
- Existing management plans need revision (architecture changed, new constraints, experience in production)
- Stakeholders want to discuss how specific failures will be handled
- You want to assess overall residual risk across all failure modes
- You're in the failure analysis conversation and a failure mode is well-understood enough to discuss management (this process can be invoked for a single failure, then return to analysis)

## Inputs Needed

Before starting, you should have:

- Failure mode documents in `.clarity-protocol/failures/` with completed analysis sections (chains, intervention points)
- `.clarity-protocol/failures/failures.md` — Index showing which failures need plans
- `processes/failure-reasoning-guidelines.md` — Shared guidelines on analyzing the complete system and focusing on meaningful harm
- `.clarity-protocol/goal/problem.md` — The problem statement (keep this front and center)
- `.clarity-protocol/goal/stakeholders.md` — To assess acceptability from each stakeholder's perspective
- `.clarity-protocol/goal/requirements.md` — Constraints on what management approaches are feasible
- `.clarity-protocol/solution/solution.md` — What's being built (management plans must be compatible)
- `.clarity-protocol/solution/architecture.md` — How it's built (if available; management plans often inform architecture)

## Process Steps

### Step 1: Survey Unmanaged Failures

Read the failures index to identify which failure modes need management plans. Read all the failure mode documents — both managed and unmanaged — because interactions matter.

Consider which failures to address first. Rather than computing a priority score, look at:

- **Severity**: How bad is it when this failure occurs?
- **Urgency**: Is there a reason this needs to be addressed before others? (e.g., it's already happening, or it blocks other work)
- **Cost of short-term mitigation**: Some failures have cheap short-term mitigations (Principle 4) — knocking those out quickly reduces overall exposure.
- **Interactions**: Does managing this failure first simplify or complicate management of others?

But the general approach is to develop plans for all of them (Principle 5). Don't spend more time debating which to do first than it would take to just start.

**Present the landscape to the user:**

> "There are [N] failure modes that need management plans. Here's what I see:
>
> [For each: title, severity, and 1-sentence summary of what went wrong]
>
> I'd suggest starting with [X] because [rationale]. Want to work through them in that order, or would you prefer to start elsewhere?"

### Step 2: Consider Interactions

Before developing individual plans, look across all failure modes for:

- **Shared intervention points**: Where a single mechanism addresses multiple failures. These are high-value investments.
- **Conflicting interventions**: Where the management approach for one failure makes another worse. For example, aggressive rate limiting (to prevent abuse) might cause legitimate users to be locked out (a UX failure mode). These conflicts need explicit tradeoff decisions.
- **Cascade dependencies**: Where Failure A's management plan depends on Failure B being managed first, or where managing Failure A eliminates Failure B entirely.
- **Pinch points**: Intervention points that appear across many failure chains. A well-designed mechanism at a pinch point addresses many failures efficiently.

Document these interactions. They inform the order in which you develop plans and the tradeoffs you'll need to make.

### Step 3: Develop Management Plans

For each unmanaged failure mode (or group of related ones where interactions demand joint planning):

#### 3a: Review the Failure Chain and Intervention Points

Re-read the failure chain carefully. Also re-read the problem statement — the management plan must keep the solution aligned with the underlying problem (Principle 1). For each intervention point, consider:

- **Feasibility**: Can we actually build this intervention given our constraints (technical, resource, timeline)?
- **Effectiveness**: How much does this intervention reduce the severity or frequency of harm?
- **Cost**: What does it cost to build and maintain? What friction does it add for users or operators?
- **Side effects**: Does this intervention create new problems? Does it interact with other failure modes?

#### 3b: Choose a Management Strategy

**Start by considering the prior state.** How is this failure handled in the world before this solution exists? This grounds the management plan in reality:

- If this failure is **pre-existing and not worsened** by the solution, the management plan is usually "keep handling as before." These should already be grouped as "Existing issues" from the analysis triage step. If one slipped through, this is the place to catch it.
- If this failure is **pre-existing but worsened** by the solution, describe how it's handled today and analyze what changes. Does the existing approach still work? Does it need to scale differently? Does the solution introduce new attack surface or new consequences that the existing approach doesn't cover?
- If this failure is **new** (introduced by the solution), there's no prior-state management to build on. But there may be analogous failures in the prior state that suggest management patterns.

Be creative about what constitutes a management plan (Principle 2). The fix might involve changing the system, changing the communication, changing the process, or some combination. It might happen in a very different part of the system than where the failure manifests.

Most failure modes are managed through some combination of:

- **Prevention**: Stop the failure from happening. Best when feasible, but often expensive or impossible to make perfect. Examples: input validation, access controls, redundancy.
- **Detection**: Know when the failure is happening or about to happen. Essential when prevention isn't perfect. Examples: monitoring, alerting, anomaly detection, user reports.
- **Mitigation**: Limit the damage once a failure is occurring. Reduces impact even when prevention fails. Examples: circuit breakers, rate limiting, graceful degradation, sandboxing.
- **Recovery**: Restore safety after the failure has occurred. The last line of defense. Examples: rollback, incident response procedures, user notification, data restoration.
- **Acceptance**: Acknowledge the residual risk without active intervention. Appropriate when the cost of intervention exceeds the expected cost of the failure, or when the failure is sufficiently unlikely and low-impact.

A good management plan usually layers several of these. Pure prevention is brittle (one miss and you're exposed). Defense in depth — prevention + detection + mitigation + recovery — is more resilient.

Short-term and long-term approaches can differ (Principle 4). A simple short-term plan ("handle it manually if it happens") combined with a more robust long-term plan ("automate detection and mitigation once we understand the pattern") is a perfectly valid management strategy.

**Present your proposed strategy to the user before writing it up.** For each failure mode (or group), lay out:

> "For **[failure mode]**, here's what I'm thinking:
>
> - **Strategy**: [overall approach — e.g., layered defense, acceptance with monitoring, etc.]
> - **Key interventions**: [which intervention points you'd target and why]
> - **Main tradeoff**: [what this costs — development effort, user friction, operational complexity]
> - **Alternative considered**: [a different approach and why you prefer the proposed one]
>
> Does this seem right, or would you approach it differently?"

Wait for the user's input before proceeding. They may adjust the strategy, raise constraints you weren't aware of, or confirm your thinking. Only move to 3c once the strategy direction is agreed.

#### 3c: Assess Residual Risk

After choosing interventions, assess what risk remains:

- What failure scenarios are still possible despite the planned interventions?
- How severe are the consequences of those residual scenarios?
- Is this residual risk acceptable from each stakeholder's perspective? (Principle 3 — the criterion is stakeholder sign-off on the overall cost, not an abstract risk score.)

If the residual risk is not acceptable, either strengthen the plan or escalate to a decision (using the decision-guidance process). If the risk creates a genuine tension with the problem statement (Principle 1), return to problem clarification to work through it.

#### 3d: Write the Management Plan

Update the failure mode document's Management Plan section:

```markdown
---

## Management Plan

### Strategy

[Overall approach: which intervention types are prioritized and why.
Example: "Layered defense. Prevent most instances through input validation,
detect what gets through via monitoring, and recover quickly through
automated rollback."]

### Planned Interventions

[Specific interventions to implement, mapped to intervention points
in the failure chain.]

**Short-term:**

- **[Intervention point from chain]**: [What we'll build/do]
  - Type: [Prevention/Detection/Mitigation/Recovery]
  - Addresses: [Which failure chain steps this covers]

**Long-term** (if different from short-term):

- **[Intervention point]**: [What we'll build/do when ready]
  - Trigger: [When/why we'd move to this from the short-term approach]

### Accepted Risks

[What risk remains after planned interventions, and why it's acceptable.
Be specific: "An attacker with valid credentials can still..." is more
useful than "some risk remains."]

### Monitoring

[How we'll know if this failure mode is manifesting despite interventions.
What signals to watch, what thresholds trigger action, who gets alerted.]
```

The short-term/long-term split is optional — use it when the approaches differ, skip it when they don't.

### Step 4: Update the Failures Index

Update each managed failure's entry in `.clarity-protocol/failures/failures.md` to replace "**no mitigation plan**" with a brief summary of the management strategy. The index format is defined in `failure-analysis.md`; each entry is a numbered item like:

```markdown
1. **[Title](failure-01-name.md)** (High) Brief description of what goes
   wrong. What this means for stakeholders. Layered: validate inputs +
   monitor for anomalies + automated rollback.
```

Don't change the structure — just update the management summary at the end of each entry you've managed.

### Step 5: Check for Induced Failures

Review all newly developed management plans and ask: do any of these interventions create new failure modes?

Common examples:

- Rate limiting creates "legitimate user locked out" failure mode
- Complex authentication creates "user abandons task due to friction" failure mode
- Automated rollback creates "rollback oscillation" failure mode
- Monitoring creates "alert fatigue" failure mode

If you identify induced failures, add them as raw failure modes to an active brainstorming mailbox (or the suggestion box) for the next analysis cycle. Note the connection in both documents.

**If any intervention introduces a new component** — incident response, monitoring infrastructure, manual review workflows — note that this component needs its own design pass (Principle 6). It's a new part of the solution, and the full design process applies to it. At minimum, make sure the management plan answers the key design questions for that component (who operates it, what SLAs apply, what access is needed, whether staffing is adequate).

### Step 6: Communicate Results and Hand Off

Tell the user what was decided:

> "I've developed management plans for [N] failure modes:
>
> **[Failure 1]** ([severity]): [1-sentence strategy summary]
> — Residual risk: [brief assessment]
>
> **[Failure 2]** ([severity]): [1-sentence strategy summary]
> — Residual risk: [brief assessment]
>
> [If interactions found:] Several failures share intervention points —
> [mechanism] addresses [Failure A, B, and C] simultaneously.
>
> [If conflicts found:] There's a tradeoff between [Failure X] and
> [Failure Y] — [brief description]. This may need a decision.
>
> [If induced failures found:] The planned interventions may introduce
> [N] new failure modes that should be brainstormed in the next cycle."

**Hand off to what's next:**

- If you were working through failures one at a time from the failure analysis conversation, return to that loop to continue with the next failure or activity.
- If there are tradeoffs that need decisions, offer to run **decision-guidance**.
- If new failure modes were identified, offer to run **failure-brainstorming** or fold them into the analysis conversation.
- If management plans require significant changes to the solution or architecture, note that those documents should be updated and offer to work on that.
- Otherwise, return to the **clarity-agent** main loop.

## Outputs and Updates

This process updates:

- `.clarity-protocol/failures/failure-NN-name.md` — Management Plan sections filled in
- `.clarity-protocol/failures/failures.md` — Index updated with management status
- `.clarity-protocol/mailboxes/suggestions/*.md` — New raw failures if interventions induce them (via the suggestion box)
- `.clarity-protocol/goal/stakeholders.md` — If new stakeholders or goals are discovered
- `.clarity-protocol/goal/requirements.md` — If requirements change based on management analysis
- `.clarity-protocol/solution/solution.md` — If the management plan requires solution changes

After writing, record document state for the files you updated. Always include `failures/failures.md`; add any other tracked documents you modified (e.g. `goal/stakeholders.md`, `solution/solution.md`):

```bash
python -m clarity_agent.protocol.packet_status . --record failures/failures.md [other updated docs]
```

## Success Indicators

You've completed failure management successfully when:

- All identified failure modes have management plans (or explicit rationale for deferral)
- Plans consider interactions between failure modes
- Residual risk is assessed and explicitly accepted (or escalated as decisions)
- Induced failure modes are identified and captured for future analysis
- New components introduced by management plans have adequate design
- The problem statement is still being solved by the updated solution
- Stakeholders can understand and evaluate the plans

## Common Pitfalls

**Pitfall: Managing failures in isolation**

Failure modes interact. A plan that's optimal for one failure may be terrible when you consider its effect on others. Always survey the full landscape before committing to individual plans.

**Pitfall: Zero residual risk**

No system has zero risk. Trying to eliminate all risk leads to over-engineering, excessive cost, and usually new failure modes from the complexity itself. Explicitly accept residual risk and be clear about what it is.

**Pitfall: Ignoring stakeholder perspectives**

A residual risk that's acceptable to the team building the system may be unacceptable to users, regulators, or the business. Check acceptability from each stakeholder's perspective, not just the builder's (Principle 3).

**Pitfall: Prevention-only strategies**

Prevention is important but insufficient. What happens when prevention fails? Defense in depth — prevention + detection + mitigation + recovery — is more resilient than any single layer.

**Pitfall: Forgetting induced failures**

Every intervention changes the system. Rate limiting, authentication, monitoring, automated responses — all of these can fail in their own ways. Check for induced failure modes.

**Pitfall: Prioritizing by severity times likelihood**

Don't spend time computing risk scores by multiplying severity by likelihood. This approach produces unreliable rankings and leads to unproductive arguments about estimates. Instead, develop plans for all failures, and sequence work by urgency and cost of short-term mitigation if needed (Principle 5).

**Pitfall: Treating new components as trivial**

When a management plan introduces a new component — incident response, monitoring, manual workflows — that component needs proper design. "We'll page someone" is not a complete incident response plan. Who gets paged? What information do they have? Can they actually fix the problem? At 3am? With adequate staffing? (Principle 6).

**Pitfall: Losing sight of the problem**

Management plans change the solution. The deeper the change, the more important it is to verify that the solution still addresses the underlying problem. If a management plan creates tension with the problem statement, that's a signal to go back to problem clarification, not to push through (Principle 1).

**Pitfall: Static plans**

Management plans should evolve as the system, threats, and understanding change. This process can be re-run whenever plans need updating.

## Next Steps

After failure management, typical next processes are:

- **failure-analysis.md** — Return to the analysis conversation if working through failures incrementally
- **architecture-design.md** — Incorporate planned interventions into the architecture
- **decision-guidance.md** — If tradeoffs between failure modes need explicit decisions
- **failure-brainstorming.md** — If induced failure modes were identified
- **solution-brainstorming.md** — If management plans require rethinking the solution approach
- **problem-clarification.md** — If management reveals tension with the problem statement
