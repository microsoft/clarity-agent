# Threat Model: AI Roadmap for Expense Management

## Top Risks

| # | Failure Mode | Severity | Probability | Key Mitigation |
|---|-------------|----------|-------------|----------------|
| FM-1 | AI model quality failures erode customer trust | High | High | "Suggest, don't apply" policy; accuracy thresholds before automation |
| FM-2 | Data privacy and compliance failures | Very High | Moderate | Vendor DPA + PII audit + tenant isolation testing |
| FM-3 | Execution and resourcing stall the roadmap | High | High | Minimum viable quick win independent of ML hire; start recruiting now |
| FM-4 | Investment fails to produce competitive differentiation | Medium | Moderate | Lead with data asset narrative; commit to Phase 3 at board level |

## Single Points of Failure

- **The ML engineering hire.** Phase 2 cannot proceed without dedicated ML engineering capacity. If hiring is delayed 6+ months, the entire roadmap slips. *Mitigation: Begin recruiting before budget is formally approved; explore internal transfer from data science teams as a bridge.*

- **The borrowed data scientists.** Phase 1 categorization model training depends on data scientists from other teams. If that commitment is informal (individual agreement rather than management-level), it will be broken. *Mitigation: Get explicit management commitment in writing before the plan depends on it.*

- **Baseline metrics.** If pre-AI accuracy is not measured before Phase 1 ships, the company cannot prove Phase 1 worked. This is a prerequisite for every ROI claim. *Mitigation: Measure in week one — this costs nothing.*

## Cross-Cutting Controls

Two controls address multiple failure modes simultaneously and should be treated as non-negotiable program policies:

1. **"Assist before automate"**: No AI feature auto-applies without explicit per-customer opt-in and accuracy threshold. Addresses FM-1 (trust erosion), FM-2 (blast radius of errors), and FM-4 (enterprise governance). This is also the right product story for a risk-averse board.

2. **Data governance by design**: PII audit before training, tenant isolation testing before NL query ships, vendor DPA before OCR API goes to production. Addresses FM-2 fully and reduces FM-4 enterprise adoption risk.

## Board-Level Risk Summary

The AI initiative carries three categories of risk the board should be aware of:

**Execution risk** is the most probable — building ML capability from zero takes longer and costs more than planned. Mitigation is realistic phasing, beginning recruiting immediately, and a Phase 1 that can succeed even if Phase 2 is delayed.

**Reputational/compliance risk** is the most severe — a data breach at 100M receipts/month would be material. Mitigation is treating data privacy as a design requirement, not a checkbox.

**Strategic risk** is the most nuanced — spending $500-900K and still losing the competitive narrative is possible if Phase 2 is slow. Mitigation is leading with the data asset story from day one, which is true and defensible before a single model ships.
