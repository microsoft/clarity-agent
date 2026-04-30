# Solution Summary: AI Roadmap for Expense Management

## What We're Building

A three-phase AI investment program that transforms the company's expense management platform from a rules-based system into a data-driven intelligence layer — using the company's own 100M-receipt/month corpus as the foundational asset.

## What It Feels Like

**For the average employee submitting expenses:** They photograph a receipt. The OCR reads it correctly the first time. The expense is automatically categorized into the right category for their role and spending history, not some generic rule. If something looks off — a duplicate, a policy violation, an unusually large claim — a flag appears with a plain-English explanation before the manager even sees it. They spend less time correcting things and more time doing their actual job.

**For the finance manager:** The dashboard shows spend patterns across teams, flags unusual activity without waiting for month-end review, and surfacing policy compliance rates automatically. They can type "show me all meals over $100 last month without receipts" and get results. Insights arrive proactively rather than requiring manual analysis.

**For the buyer evaluating vendors:** They hear a clear story — not "we use AI" but "our AI is trained on your industry's expense patterns at a scale that commodity tools can't match."

## How It Addresses the Problem

- **OCR fix (Phase 1):** Upgrade via managed API under a DPA — fast win that addresses the most common customer complaint
- **Categorization fix (Phase 1):** Train a gradient boosting classifier on existing categorization pattern data — this requires no ML team, just the data scientists the company already has elsewhere
- **Competitive narrative (Phase 2):** Anomaly detection, policy compliance, and spend insights give the "AI-powered insights" story competitors are selling — but built on proprietary data
- **The moat (Phase 3):** Fine-tuned OCR and categorization models trained on the company's own receipt corpus — a training dataset that will exceed 1 billion receipts by Phase 3, impossible for any competitor to replicate

## Key Design Decisions

**Build the moat, use APIs as a bridge.** Cloud OCR at 100M receipts/month costs $1.5–2M/year at list price. Using APIs in Phase 1 is acceptable for speed; migrating to self-hosted custom models in Phase 3 is the plan, not an afterthought.

**Assist before automate.** All models launch in suggestion mode. Users see AI recommendations and can accept or override. This builds trust and generates labeled data for model improvement simultaneously. Automation increases only after accuracy thresholds are met per customer segment.

**The NLP query layer never touches raw data.** In Phase 3, natural language querying uses an LLM to translate intent to structured queries — the LLM sees query strings and schema, never raw expense records. This satisfies data privacy requirements while delivering the power-user feature.

**Hire ML engineers before committing to Phase 2.** Phase 1 is achievable with product engineers + borrowed data scientists. Phase 2 requires dedicated ML engineering capacity. The budget ask includes this hire as a prerequisite, not an afterthought.

## Budget Summary

| Phase | Investment | Key Milestone |
|-------|-----------|---------------|
| Phase 1 (0–3 mo) | $100–200K | OCR accuracy up, categorization model live |
| Phase 2 (3–9 mo) | $300–500K | Anomaly detection, spend insights in product |
| Phase 3 (9–18 mo) | $200–400K | Custom models, NL query, API cost reduction |
| **Year 1 Total** | **$480–925K** | Full AI story delivered, ROI measurable |
