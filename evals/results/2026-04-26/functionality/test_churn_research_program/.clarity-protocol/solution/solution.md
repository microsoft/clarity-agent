# Solution: Churn Research Program

## Approach

A six-week, three-person research program combining data triage, qualitative customer interviews, cross-functional synthesis, and an executive presentation. Given the data quality constraints, qualitative methods are primary. The program is designed to produce a well-reasoned, evidence-based diagnosis — not statistical certainty, but a credible top 2–3 driver story with acknowledged limitations.

The program deliberately separates the Q4 spike investigation from the year-long drift, since they may have different causes and different remediation paths.

## Phase 1: Data Audit and Triage (Weeks 1–2)

**Goal:** Understand what data you actually have before committing to any hypothesis.

- **Exit interview audit:** Review all existing exit interviews. Catalog: which accounts, which account managers, what questions were asked, what reasons were cited. Identify coverage gaps by segment (enterprise, high-value tier, recent cohorts). Flag patterns and outliers.
- **Usage data pull:** Extract whatever is accessible from the analytics system despite export constraints. Compare engagement patterns (login frequency, feature adoption, session depth) between churned and retained accounts in priority segments. Identify if usage decay is a leading indicator.
- **Q4 spike investigation:** Cross-reference the timing of the Q4 churn spike against product releases, pricing changes, support ticket volume, and any known competitive moves. Try to isolate whether this was a triggered event or an acceleration of the trend.
- **NPS/CSAT review:** Segment whatever scores exist by customer type and cohort. Note where data is missing or unreliable — this shapes how much weight to put on it.
- **CRM data cleanup:** Identify which churned accounts are in the priority segments. Build a contact list for interview outreach.

**Deliverable:** A data audit memo — what each source tells us, how much to trust it, and what questions it can and can't answer.

## Phase 2: Customer Interviews (Weeks 2–4)

**Goal:** Direct customer voice on why they left (and why others stayed).

- **Recruit churned customers:** Target 10–15 from enterprise and high-value tier. Use CRM contacts and any warm paths through account managers. Accept that the sample will be self-selected (less hostile churners) — acknowledge this as a limitation.
- **Recruit active customers:** Target 5–8 from the same segments as a contrast group. Use relationship with loyal customers.
- **Standardized interview guide:** Build a consistent guide covering: primary reason for leaving/staying, evaluation of value delivered, product feature gaps, competitive alternatives considered, and what would have changed the outcome. Same guide for both churned and active — varying only the framing.
- **Conduct interviews:** Two team members interview; one person analyzes and codes in parallel. Aim for 45–60 minute sessions.
- **Coding and theming:** Use a simple affinity-mapping approach to cluster responses. Tag each theme with source evidence and segment.

**Deliverable:** Interview synthesis document — top themes by segment, representative quotes, patterns across churned vs. active customers.

## Phase 3: Cross-Functional Workshops (Weeks 3–4, overlapping)

**Goal:** Pressure-test emerging findings with marketing and product; surface information they hold that the CS team doesn't.

- **Marketing workshop:** Share early interview themes. Ask: do these match what you're hearing in sales conversations? Where is the value prop landing vs. falling flat? What competitive positioning concerns are you seeing?
- **Product workshop:** Share feature gap and integration themes from interviews. Ask: are these known issues? What's on the roadmap? What would be a fast win vs. a longer-term fix?
- Run these in weeks 3–4 so findings are directionally clear but still open to revision.

**Deliverable:** Workshop notes with cross-functional input captured; identified gaps between CS findings and marketing/product perspective.

## Phase 4: Synthesis (Weeks 4–5)

**Goal:** Build the evidence-based diagnosis.

- Triangulate across sources: where do interviews, usage data, exit interview audit, and NPS/CSAT point in the same direction? Where do they conflict?
- Identify top 2–3 churn drivers with supporting evidence and honest confidence levels (high / medium / low based on number of sources and sample quality).
- Distinguish Q4 spike cause from year-long drift cause if the data supports it.
- Draft recommendations: for each driver, one or more specific, feasible interventions. Assign owners (CS, marketing, product). Flag quick wins vs. longer-term investments.
- Get marketing and product alignment on recommendations before finalizing.

**Deliverable:** Diagnosis document — drivers, evidence, confidence levels, and recommended interventions.

## Phase 5: Presentation Build (Weeks 5–6)

**Goal:** An executive presentation that earns trust and drives action.

Structure:
1. Situation: churn rate, business impact, why this matters now
2. Methodology: what we did, who we talked to, what data we used, and its limitations
3. Findings: top 2–3 drivers with evidence and confidence levels
4. Recommendations: prioritized actions with owners and timelines
5. What we don't know yet: honest gaps and what would be needed to fill them

**Deliverable:** Executive presentation deck, ready for the six-week mark.

## Key risks

- **Interview recruitment fails:** If churned customers won't engage, the qualitative base thins. Mitigation: start outreach in week 1, use account manager warm intros, offer a brief call rather than a formal interview.
- **Data access worse than expected:** If product analytics are truly inaccessible, the usage-as-predictor question can't be answered quantitatively. Mitigation: deprioritize; lean harder on qualitative.
- **Marketing or product don't engage meaningfully:** If cross-functional workshops become passive reviews, alignment won't happen before the presentation. Mitigation: get COO to signal the expectation of active participation upfront.
- **Findings are ambiguous:** If the evidence doesn't converge on clear drivers, the presentation becomes a "we need more research" story. Mitigation: acknowledge this as a possible outcome early; a well-reasoned "here are the three most likely explanations and here's what we'd need to test each" is still a credible and useful result.
