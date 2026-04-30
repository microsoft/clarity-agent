# Failure: Post-Program Failure

## Summary

The research program succeeds — diagnosis is credible, presentation is good — but nothing changes as a result. The executive team accepts findings but doesn't commit resources. Or they do commit resources but never measure whether interventions worked. Or the world changes between diagnosis and implementation and the recommendations no longer fit. In all variants, the program produces no lasting improvement in churn.

## Failure Chain

1. Executive presentation goes well. Findings are accepted. Recommendations are presented.
2. Recommendations require resource commitment: budget, engineering time, marketing changes, CS team changes.
   - *Observation:* Recommendations that are vague ("improve the onboarding experience") require much less commitment than specific ones ("hire a dedicated onboarding specialist and rebuild the first-30-days email sequence"). Vague recommendations are easier to accept and easier to not act on.
   - *Intervention point (prevention):* Make recommendations specific and ownable. Each recommendation should have: a named owner, a concrete deliverable, and a 30/60/90-day milestone. Vague recommendations die in committee.
3. Branch A: Competing priorities win. No formal decision is made; "we'll discuss it in the next planning cycle" is the outcome.
   - *Intervention point (prevention):* Before the presentation, secure a commitment from the COO that the session will produce decisions, not discussions. Prepare a decision framework: "For each recommendation, we need a yes, a no, or a named owner and date."
4. Branch B: Recommendations are accepted and assigned, but no measurement framework is established.
   - *Intervention point (prevention):* Include a measurement plan as a core part of the recommendations: what metric indicates success, what's the baseline, and what's the target at 90 days and 6 months.
   - *Intervention point (detection):* At the 90-day mark, pull the agreed metrics. If no one has been tracking them, the measurement plan failed.
5. Branch C: Implementation begins, but an external event (competitor launches a superior product, market contracts, macroeconomic change) shifts customer behavior faster than the interventions can work.
   - *Observation:* This branch is largely outside Elena's control. The mitigation is to build interventions that are robust to environmental change — customer success improvements are more durable than marketing messaging changes, which can become stale quickly.
   - *Intervention point (mitigation):* Build a review trigger into the plan: "If churn rate hasn't improved by X% within 90 days, reconvene to assess whether the diagnosis still holds."
6. **Harm begins.** Churn continues at its current rate. The CS team has spent six weeks on research with no measurable outcome.
7. Credibility of the CS function is damaged. Future research programs face higher skepticism. **Harm ends** when leadership invests in a second, more implementation-focused program — but significant time and trust have been lost.

## Observations

- **Severity:** High — This is the terminal failure for the whole program. All other failures lead here if not caught. Probability is non-trivial: research programs that don't produce decisions are common in organizations.
- **Related failures:** Downstream of all other failure modes. Also directly related to Failure 5 (Cross-Functional Resistance) — politically-softened recommendations are less likely to get implemented with conviction.
- **Variants (from brainstorm):**
  - Executive team accepts findings but doesn't act
  - Executive team acts but never measures impact
  - External factors override findings mid-implementation

## Intervention Points

### Prevention
- Make each recommendation specific with a named owner, concrete deliverable, and 30/60/90-day milestone
- Secure a pre-commitment from the COO that the presentation session will produce decisions
- Include a measurement plan (baseline metric, target, review date) as part of every recommendation

### Detection
- 30-day follow-up: check whether assigned owners have taken first steps
- 90-day review: pull the agreed metrics baseline and compare

### Mitigation
- Build a reconvene trigger into the plan: if churn hasn't improved by X% in 90 days, reassess the diagnosis
- Design interventions that are robust to environmental change (customer success changes > messaging changes)

### Recovery
- If the program produces no action: reframe the findings as an input to the next planning cycle rather than a one-time presentation; keep the diagnosis visible until it's addressed

---

## Management Plan

Not yet developed. Run failure management to develop a plan for this failure mode.
