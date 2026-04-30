# Solution: AI Roadmap for Expense Management

## The Core Approach

The strategy is **data-led AI on proprietary infrastructure** — three phases that move from quick wins (using existing patterns and best-in-class tools), to an intelligence layer (ML models trained on company-specific data), to a genuine moat (custom models that competitors cannot replicate because they don't have the data).

The company's 100M receipts/month is the central strategic asset. At this scale, cloud OCR APIs alone would cost $1.5–2M/year at list price — making in-house model development not just strategically desirable but economically necessary within 12–18 months.

---

## Phase 1: Fix What's Broken (0–3 months)

**Goal:** Demonstrate AI value to customers and the board fast, with what the team can ship without ML expertise.

### 1a. OCR Upgrade (Weeks 1–6)
Replace or augment the current OCR with a modern managed OCR service (AWS Textract, Google Document AI, or Azure Document Intelligence) under a signed Data Processing Agreement that satisfies compliance requirements. Even a commodity upgrade here likely delivers a large accuracy jump at low implementation cost.

**Cost:** ~$10–30K for a pilot (process a fraction of volume, validate improvement, then decide on scope). Data privacy is managed via DPA, not by avoiding the API entirely.

**Success metric:** OCR accuracy rate (% of fields correctly extracted without manual correction) — measure before/after.

### 1b. ML-Based Categorization (Months 1–3)
Use the existing categorization pattern data to train a gradient boosting classifier (XGBoost/LightGBM — no deep learning required, no GPU needed). This is a well-understood supervised learning problem: given merchant name, amount, employee role, and any extracted line items → predict expense category.

Internal data scientists (from other parts of the company) can lead the model training with product engineers providing the data pipeline. The product team owns the integration.

**Success metric:** Categorization accuracy on a held-out test set; reduction in manual override rate.

---

## Phase 2: Make It Smart (Months 3–9)

**Goal:** Build the intelligence layer that becomes the "AI story" for prospects.

### 2a. Anomaly & Policy Compliance Engine
Flag expenses that deviate from historical patterns (unusually large amounts, atypical categories for the employee, duplicate submissions, policy violations). This can be built on statistical baselines + the categorization model, not a separate deep ML system.

### 2b. Merchant Intelligence
Build a merchant-to-category mapping database using the accumulated receipt corpus. This makes categorization more accurate AND enables spend benchmarking by merchant — a feature data-savvy customers have explicitly asked for.

### 2c. Spend Insights Dashboard
Surface patterns from the categorization and anomaly data as actionable insights: top spend categories, unusual spikes, policy adherence rates, department benchmarks. This is the "AI-powered insights" story that will address the competitive narrative.

**Team investment for Phase 2:** Hire 1–2 ML engineers. These are the critical hires — not researchers, but engineers who can train, deploy, and monitor models in production. Consider internal transfer or collaboration from the data science function as a bridge.

---

## Phase 3: The Moat (Months 9–18)

**Goal:** Build AI that competitors using commodity APIs cannot match.

### 3a. Custom OCR Fine-Tuned on Receipt Corpus
Fine-tune an open-source OCR model (e.g., PaddleOCR, TrOCR, or a layout-aware document model like LayoutLM) on the company's own receipt data. At 100M receipts/month, 12 months of operation produces over a billion receipts for training — an unassailable training corpus for expense-domain OCR.

### 3b. Personalized Categorization by Organization
Rather than one global model, train per-customer or per-industry-segment models that learn each company's specific expense patterns and policies. This is a genuine differentiator.

### 3c. Natural Language Expense Query
"Show me all meals over $100 with missing receipts last quarter." This uses LLM-as-interface over structured expense data — the LLM never sees raw expense data, only translates natural language to queries. Addresses the advanced analytics request from power users.

---

## Team Plan

| Phase | Who | What |
|-------|-----|------|
| Phase 1 | Product engineers + borrowed data scientists | OCR API integration, categorization model training |
| Phase 2 | Hire 1–2 ML engineers | Anomaly detection, merchant intelligence, model ops |
| Phase 3 | ML team (2–3 engineers) + data scientists | Custom models, fine-tuning, NLP query |

Using managed ML platforms (AWS SageMaker, Google Vertex AI) in Phase 1–2 reduces the ML ops burden until the team has the experience to manage infrastructure directly.

---

## Budget Estimate (Year 1)

| Item | Range |
|------|-------|
| OCR API pilot + production (Year 1) | $50–150K |
| ML engineering hires (1–2, fully loaded) | $300–500K |
| ML infrastructure (managed platform, GPU compute) | $50–100K |
| Data labeling for training sets | $30–75K |
| Internal data science collaboration (time cost) | $50–100K |
| **Total Year 1** | **$480K–$925K** |

Year 2+ costs flatten as the team scales the infrastructure they've built and cloud API dependence decreases.

---

## ROI Framing

- **Retention:** If AI features reduce churn by 1% (10 customers), retaining even $10K ARR/customer = $100K ARR protected annually
- **Competitive wins:** If improved accuracy converts 5% more prospects per quarter who were considering AI-forward rivals, and ACV averages $20–50K, the math is compelling
- **User productivity:** Reducing per-user categorization correction time by 20% saves hours monthly at scale — quantifiable as cost reduction for customers
- **Cost avoidance:** Moving off cloud OCR APIs to self-hosted models in Phase 3 saves $500K–$2M/year versus continuing at scale with external APIs

---

## Alternatives Considered

**All-in on third-party AI APIs (OpenAI, etc.):** Fast to prototype, but creates data privacy liability, unpredictable costs at 100M-receipt scale, and zero differentiation since any competitor can do the same. Rejected as a primary strategy; acceptable for NLP interface layer in Phase 3 where raw receipt data never leaves the system.

**Pure rules-based improvements:** Low risk but no strategic value — this is table stakes, not an AI story.

**Acquire an ML startup:** High risk, high cost, and cultural integration is hard. Internal development with the right hires is more controllable.

---

## Risks and Mitigations

- **Execution risk (no ML experience):** Mitigated by hiring ML engineers before committing to Phase 2, and using borrowed data scientists as Phase 1 bridge
- **Data privacy:** Mitigated by DPA for any APIs used; custom models in Phase 3 keep data fully on-premises
- **OCR API cost at scale:** Mitigated by framing Year 1 as a pilot, with migration to custom models as Phase 3 milestone
- **Model quality:** All models launch in "assist" mode (suggesting, not auto-applying) — this limits blast radius and builds trust before automation increases
