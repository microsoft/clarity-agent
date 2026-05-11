# AI Roadmap for Expense Management SaaS

## The Situation

We're a mid-market expense management company with 4,000 customers, a 22-person engineering team, and a CEO who came back from a conference energized about AI. Three things converged at once: board meeting in six weeks, customers asking "what's your AI story?" in QBRs, and our largest competitor announcing an "AI assistant" via press release.

The natural instinct was to build a chatbot. The right answer is smarter categorization.

## The Core Insight

We have two years of labeled categorization data — merchant, description, category chosen — across 4,000 customers. That's a proprietary training dataset no new entrant can replicate. Meanwhile, our two biggest user pain points are exactly what ML can fix: OCR error rates around 30% (users manually correcting every third expense) and rules-based category suggestions that fail often enough that users have given up on them.

A natural language AI assistant is only as good as the data underneath it. We build the intelligence layer first — accurate categorization — and the assistant follows naturally in Phase 3 when the underlying data is trustworthy. This is a stronger long-term position than shipping a chatbot on top of bad data.

## The Roadmap

**Before the board meeting (6 weeks):**
- Ship an OCR provider upgrade (Google Document AI / AWS Textract / Azure Form Recognizer). This is an API swap — 2–3 weeks of engineering. Reduces the ~30% manual correction rate. A real shipped improvement to point to.
- Build a categorization proof of concept: train on historical data, show accuracy numbers. "We trained on millions of labeled transactions and the model suggests the right category X% of the time" lands in a board room.

**Phase 1 — Production categorization + visible AI (months 1–4):**
- ML-based categorization suggestions in the submission flow, trained on per-customer historical patterns
- "Suggested by AI" labels with confidence indicators on every suggestion
- User feedback mechanism (accept/reject) feeding back into model improvement
- Staffing: one senior ML contractor ($25–35K/month, 4–6 months) plus the existing ML-curious engineer

**Phase 2 — Finance manager dashboard + policy intelligence (months 4–7):**
- Accuracy dashboard for finance managers: AI-handled categorizations, acceptance rate trend, month-over-month improvement
- Spend anomaly flagging
- Named AI product identity — something demo-able for the CEO and for QBRs

**Phase 3 — Natural language layer (months 7–12):**
- "Show me T&E spend by department this quarter" — answering questions against accurately-categorized data
- This is where the chatbot vision lands, and it's actually useful because Phase 1 made the underlying data trustworthy

**Budget range: $300–500K year one.** Primarily ML expertise and infrastructure. Will sharpen after engineering conversations on data readiness and OCR switching cost.

## The CEO Narrative

*"A natural language assistant is only as good as the data underneath it. If our competitor's chatbot is answering questions about their customers' spend, it's answering questions about poorly-categorized expenses. We're building the intelligence layer first — so when we ship the assistant, it's actually accurate."*

The visible AI layer (labels, dashboard, named product identity) gives the CEO a demo moment without requiring a chatbot to exist. Finance managers see "Suggested by AI" on every expense. The dashboard shows numbers. It feels like AI because it is AI — just useful AI.

## The Trust/Adoption Arc

Finance managers are risk-averse. They won't trust AI suggestions on day one — and that's fine. Design for a trust-building arc:
- Never auto-apply; always suggestions, always in control
- Confidence thresholds: only surface high-confidence suggestions initially
- Measure acceptance rate, not just accuracy — and track the trend upward
- Show reasoning briefly ("suggested because: United Airlines → Travel, 94% of your team's purchases")
- Frame corrections as the model improving, not as failures

Target arc: 60–70% acceptance in month one, climbing to 85–90% by end of quarter. That's a more defensible board story than promising 97% on day one.

## Top Risks

1. **Training data is messier than expected.** If categorization history needs significant cleanup, Phase 1 timeline and cost shift. Don't quote accuracy numbers until engineering has assessed data quality.
2. **Competitor's product is genuinely impressive.** If the trial account shows real capability, the "building the foundation" narrative is harder. Know this before the board meeting.
3. **CEO redirects to "build me a chatbot."** Have the reframe language ready. Know in advance whether you'd add a thin chatbot surface in Phase 2 to keep him engaged.
4. **Finance manager trust doesn't build.** Mitigated by design choices: confidence thresholds, never auto-apply, acceptance rate as the headline metric.

## Open Questions (resolve before board meeting)

1. Is the two-year categorization data clean enough to train on? (Engineering lead, this week)
2. OCR current provider and switching cost — is the quick win achievable in the timeline? (Engineering lead, this week)
3. What does the competitor's AI assistant actually do? (Reach out to ex-colleagues, spin up trial account)
4. Chart of accounts model architecture — per-customer vs. clustered vs. global with mapping? (ML contractor to assess)

## This Week

- Have the engineering lead conversation: data quality + OCR switching cost
- Reach out to ex-colleagues at competitor customer companies
- Spin up a competitor trial account
- Have the CEO direction conversation — direction, not details; hold the budget number for the budget meeting
