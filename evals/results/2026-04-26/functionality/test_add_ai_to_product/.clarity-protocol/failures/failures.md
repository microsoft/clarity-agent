# Failure Modes

Analysis of 19 raw failure modes brainstormed for the AI roadmap initiative. Grouped into 4 coherent failure modes.

---

## FM-1: AI Model Quality Failures Erode Customer Trust

**Summary:** The AI features ship, but customers experience them as less reliable than the rules-based system they replaced. Models fail on edge cases, degrade over time without detection, or get pushed to production before they're accurate enough. Users override or disable AI features; the ROI case collapses.

**Raw failures included:** Edge case failures in production, model drift over time, anomaly detection false positives, model monitoring ownership gap, premature automation due to CEO pressure, low customer adoption due to distrust.

**Failure chain:**
1. Models trained on historical data show strong test accuracy
2. Edge cases in production (low-quality photos, international receipts, new vendors) reveal gaps not in test data
3. OR: CEO/executive pressure drives shipping AI in "auto-apply" mode before accuracy thresholds are met
4. OR: No monitoring system exists; model accuracy silently degrades as spending patterns evolve
5. Users experience incorrect auto-applied categories or spurious anomaly flags
6. Users override AI suggestions repeatedly or disable features
7. Finance managers distrust AI-flagged anomalies; stop reviewing them
8. Adoption metrics disappoint; the product team cannot demonstrate ROI
9. Board questions whether the AI investment is working; future budget requests weaken

**Intervention points:**
- *Before launch:* Establish per-segment accuracy thresholds that must be met before any AI auto-applies
- *At launch:* Ship all models in "suggest, not apply" mode by default; automate only after per-customer trust is established
- *In production:* Implement accuracy monitoring dashboards with alerts; assign explicit ownership of model health
- *Governance:* No AI feature ships without a defined rollback criterion

**Severity:** High — this is the scenario where the investment backfires rather than just underperforming.

---

## FM-2: Data Privacy and Compliance Failures

**Summary:** Sensitive customer financial data — receipts, transaction amounts, employee names — is exposed through a vendor breach, improperly included in training data, or leaked across customer tenants via an AI query interface. The company faces regulatory action, customer loss, and reputational damage.

**Raw failures included:** OCR API vendor data breach, PII in ML training data creates GDPR/CCPA exposure, cross-tenant data leak via natural language query in Phase 3.

**Failure chain:**
1. Company sends 100M receipts/month to third-party OCR API under a DPA — but the vendor has a security incident
2. OR: Training data is drawn from the receipt corpus without auditing for PII (employee names, cardholder data, addresses)
3. OR: Phase 3 NL query feature generates SQL without tenant isolation; a user queries another company's expense records
4. Customer data is exposed or accessed without authorization
5. Regulatory notification requirements trigger (GDPR: 72h; CCPA varies)
6. Enterprise customers receive breach notification; some invoke contract termination rights
7. Regulatory investigation opens; potential fines
8. Media/industry coverage damages sales pipeline

**Intervention points:**
- *Phase 1:* Vendor DPA review, right-to-audit clauses, and data minimization (send only extracted text, not raw images, where possible)
- *Before model training:* PII audit and anonymization pipeline for training data
- *Phase 3 design:* NL query layer must enforce tenant isolation at the query generation level, with automated test suite for cross-tenant leaks before any production deployment
- *Ongoing:* Annual third-party security assessment of AI data flows

**Severity:** Very high — a breach at this data volume would be a company-defining event. Probability is moderate if not actively managed.

---

## FM-3: Execution and Resourcing Failures Stall the Roadmap

**Summary:** The company commits to an AI roadmap at the board level but cannot secure the resources to execute it — ML engineering hires take longer or cost more than planned, data science collaborators are pulled back, budget gets cut mid-year, or Phase 1 simply takes longer than the board's patience allows. The roadmap exists on paper but doesn't ship.

**Raw failures included:** ML engineers cannot be hired on budget/timeline, borrowed data scientists pulled back, Phase 1 exceeds three months, board approves insufficient budget, budget cut mid-year after Phase 1 investment, engineering team morale drop, baseline metrics not captured before launch.

**Failure chain:**
1. Board approves roadmap with real or implicit timeline expectations
2. ML engineering hiring takes 3-6 months longer than projected (competitive market)
3. OR: Internal data science collaboration doesn't materialize (reprioritized by their management)
4. OR: Phase 1 OCR/categorization work encounters unexpected complexity in the existing data pipeline
5. OR: Mid-year financial review cuts AI budget as company priorities shift
6. Phase 1 misses its delivery window — no "quick wins" demonstrated before the board meeting
7. Board confidence in the AI program erodes; executive sponsor loses political capital
8. Team demoralization: engineers feel the AI initiative was theater; key people leave
9. Future AI investment becomes politically difficult even if resources eventually materialize

**Intervention points:**
- *Before budget meeting:* Start ML engineering recruiting immediately — don't wait for budget approval to begin the pipeline
- *Phase 1 design:* Identify a "minimum viable quick win" (e.g., OCR API swap) that can ship in 4-6 weeks with existing team, independent of the categorization model
- *Data science collaboration:* Get explicit management commitment (not just individual agreement) before the plan depends on it
- *Baseline metrics:* Capture OCR accuracy and categorization error rates in the first week — before any AI work begins
- *Budget:* Build Phase 1 to succeed within a conservative budget floor; Phase 2 is the bet that needs the ML hire

**Severity:** High — this is the most likely failure mode given the team constraints. The probability is highest if execution planning is optimistic.

---

## FM-4: AI Investment Fails to Produce Competitive Differentiation

**Summary:** The company spends $500K–$900K on AI features, ships them, and still loses the competitive narrative — either because competitors moved faster, because enterprise customers' AI governance policies prevent adoption, or because the OCR API dependency creates a strategic ceiling that delays the proprietary model advantage indefinitely.

**Raw failures included:** Competitors ship AI features before Phase 2 completes, OCR API vendor dependency becomes a strategic trap, enterprise customers block AI features due to AI governance policies.

**Failure chain:**
1. Phase 1 ships (better OCR, improved categorization) but takes 3-6 months
2. During Phase 1-2 window, competitors launch visible AI features (spend insights, anomaly detection) with marketing push
3. OR: Key enterprise accounts have internal AI governance policies requiring vendor assessment before enabling AI features — new procurement step delays activation
4. OR: Company remains dependent on cloud OCR API through Phase 2; custom model development in Phase 3 is deprioritized or never funded
5. Sales team lacks a compelling differentiated AI story in competitive deals
6. The company's AI narrative is "we're catching up" rather than "we have an advantage"
7. The $500-900K Year 1 investment doesn't bend the competitive win rate measurably

**Intervention points:**
- *Messaging:* Lead with the data asset story from Day 1 — "We have 100M receipts/month of training data that no competitor can replicate" — this is true today, before Phase 3 ships
- *Enterprise readiness:* Build AI governance controls (customer-level opt-out, data processing agreements, audit logs) before launching to enterprise accounts
- *Phase 3 commitment:* Include Phase 3 custom model development as a board-level commitment, not an "if we have budget" aspiration
- *Competitive monitoring:* Assign someone to track competitor AI feature announcements quarterly

**Severity:** Medium — the investment succeeds technically but fails strategically. Painful but recoverable.

---

## Cross-Cutting Observations

**Pinch point: "Assist before automate" is the single most valuable cross-cutting control.** FM-1, FM-2, and FM-4 all have intervention points that depend on AI features starting in suggestion mode and earning trust before automation increases. A company policy that *no AI feature auto-applies without explicit customer opt-in and accuracy threshold* addresses multiple failure modes simultaneously.

**Pinch point: Baseline measurement is a prerequisite for FM-1 and FM-3.** Without pre-AI accuracy baselines on OCR and categorization, the company cannot prove Phase 1 worked. This is a day-one action, costs nothing, and blocks multiple downstream problems.

**Cascade risk: FM-3 (execution stall) → FM-4 (competitive failure).** If Phase 1 slips, Phase 2 slips, and competitors fill the window. The probability of FM-4 is directly coupled to execution speed in Phase 1.
