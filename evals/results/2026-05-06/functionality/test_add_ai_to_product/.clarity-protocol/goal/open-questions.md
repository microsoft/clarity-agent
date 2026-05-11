# Open Questions

## 1. Data quality and readiness
**Question:** Is the two-year categorization history clean enough to train on without significant prep work?
**Why it matters:** If the data requires substantial cleaning or restructuring, Phase 1 timeline and cost shift. Could affect whether a contractor starts with model development or data engineering.
**Status:** Open
**Owner:** Daniel + engineering lead
**Strategy:** Research — one conversation with the engineering lead should answer this.
**Target:** This week, before CEO direction conversation.

## 2. Chart of accounts model architecture
**Question:** Given that customers have variable and customized charts of accounts, does the categorization model need to be per-customer, clustered, or can a global model with customer-specific mappings work?
**Why it matters:** Affects ML architecture complexity and Phase 1 timeline. Per-customer models at 4,000 customer scale is a different problem than a normalized global classifier. The per-customer history data suggests per-customer learning is viable, but the approach needs validation.
**Status:** Open
**Owner:** Daniel + engineering lead + ML contractor (when engaged)
**Strategy:** Research — engineering conversation plus early data exploration.
**Target:** Before finalizing Phase 1 scope.

## 3. Competitor's actual product capabilities
**Question:** What does the competitor's "AI assistant" actually do? Is it a genuine product capability or marketing?
**Why it matters:** If their assistant is genuinely impressive, the competitive urgency and possibly the roadmap sequence change. If it's thin, the "we're building the foundation first" framing is even stronger.
**Status:** Open — investigating
**Owner:** Daniel
**Strategy:** Research — reach out to ex-colleagues at competitor customer companies; spin up a trial account.
**Target:** Before board meeting (6 weeks).

## 4. OCR current provider and switching cost
**Question:** Which OCR provider are they currently using, and what is the integration effort to switch?
**Why it matters:** The OCR upgrade is the intended quick win (2–3 weeks). If there are contractual lock-ins or integration complexity, this timeline assumption breaks.
**Status:** Open
**Owner:** Engineering lead
**Strategy:** Research — quick internal assessment.
**Target:** This week.
