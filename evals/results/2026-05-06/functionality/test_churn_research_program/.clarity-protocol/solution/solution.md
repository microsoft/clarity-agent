# Churn Research Plan

## Approach

A sequenced 6-week sprint: mine existing data first to generate hypothesis-driven interview questions, then run targeted qualitative interviews in parallel. The internal dataset (product usage, support sentiment, NPS, CRM notes) is rich enough to test most hypotheses quantitatively. Interviews fill the gap that data can't close — the *why* behind what the data shows, and the "didn't have bandwidth to run it properly" signal that won't surface cleanly in usage telemetry.

The sequencing is not a shortcut. It produces better interviews because questions are grounded in evidence, and more defensible findings because qualitative and quantitative are mutually corroborating rather than standalone.

**Hard constraint:** Interview outreach begins by end of week 2 regardless of data sprint status. If the sprint isn't complete, draft the interview guide from current hypotheses and refine as data comes in. Interviews do not wait for data.

---

## Phase 1: Data Sprint (Weeks 1–2)

**Owner:** Head of CS + analytics partner. CSMs contribute context on specific accounts.

### Cohort analysis (analytics partner, ~3 days)
Pull usage data for all 40 churned accounts. Compare 60-day activation curves against a matched cohort of retained accounts. Classify each churned account by usage pattern:
- **Never activated** — flat engagement from week one. Primary ICP signal.
- **Activated then dropped** — meaningful engagement followed by decline. Primary onboarding/engagement failure signal.
- **Consistently low** — below-baseline engagement throughout. Ambiguous; flag for interviews.

Segment by company size (50–200 employee cluster vs. others) and churn quarter (Q3 cluster where competitor is mentioned most).

### CRM cancel note analysis (CS Head + CSMs, ~1–2 days)
Systematically code all 40 cancel notes. For each account, capture: stated reason, confidence level (high/medium/low based on note quality), deal size, segment, and which of the five hypotheses it tags. Flag accounts with thin or one-liner notes — these become interview priorities because they have the most to reveal.

### NPS trajectory (analytics partner, ~1 day)
NPS scores in the 6 months before churn for churned vs. retained accounts. Did NPS decline consistently precede churn? Were churned accounts always low, or did they decline? This helps distinguish "chronic disengagement" from "acute event" churn.

### Support sentiment (analytics partner, ~1 day)
Support ticket volume and sentiment in the final 90 days of tenure. Spike in tickets or sentiment decline before churn is a signal of unresolved product or service friction.

### Dollar story (CS Head, ~half day)
Model the forward risk: if churn stays at 11% vs. returns to 7%, what does ARR trajectory look like over 2–3 years given current expansion rates? Frame as compounding drag on the expansion base and erosion of NRR over time — not simply ARR already lost, which understates the problem given current NRR health.

### Data sprint output
- Hypothesis signal matrix: each of the five hypotheses rated strong/weak/unclear based on data
- Interview priority list: accounts with thin notes, accounts fitting the strongest hypotheses, accounts in the "never activated" cluster
- Draft interview guide (hypothesis-driven, refined before outreach goes out)
- Dollar story model

---

## Phase 2: Interview Design and Outreach (End of Week 2)

**Identify 15–18 target accounts**, expecting 8–12 completions. Prioritization:
1. Accounts with thin or low-confidence CRM notes (most unknown)
2. Accounts with "never activated" usage pattern (ICP hypothesis test)
3. Accounts in the 50–200 employee Q3 cluster (competitive hypothesis test)
4. Accounts where a CSM has an existing relationship (easier to reach, warmer conversation)

**Interview structure (30–40 minutes):**

Six questions in order. Each is designed to surface what it's probing without leading the witness.

1. *"Walk me through the last few months of your time with [product]. Start wherever feels right."* — Open narrative. What they choose to lead with is a signal. Don't redirect too quickly.

2. *"At what point did you actually decide not to renew? What was going on at that time?"* — Surfaces the real trigger (mental decision usually precedes churn date by weeks).

3. *"What were you able to accomplish with [product]? Where did things work, and where did they fall short?"* — Probes onboarding and ICP simultaneously. Follow-up: *"Were there things you planned to use it for that you never got to?"*

4. *"Who on your team was mainly responsible for running [product] day-to-day — and did that work out the way you expected?"* — ICP probe. Finds out if there was a real owner and whether it was the right person/role. If operationalization themes surface: *"If you'd had a dedicated person whose job was to run this, would you have stayed?"* — Yes = ICP/resourcing. No = something else.

5. *"What did you move to after [product], or what are you doing differently now?"* — Non-leading competitive probe. If they name a competitor: *"What made that a better fit?"*

6. *"If you were advising us — what's the one thing that would have made you renew?"* — Surfaces the real reason when earlier answers have been diplomatic. If a product gap is named: *"Was that something you raised with us before your renewal decision?"* and *"Is there a tool you've moved to that does this?"* — validates against post-hoc rationalization.

**Coaching note for CSMs:** The hardest skill is not filling silences. Count to five after they stop talking before responding — people often add the most important thing after a pause. If they're being overly polite, say: *"I really want the honest version — we're doing this to understand what we got wrong."* Permission to be critical usually unlocks a more useful conversation.

**Outreach:** Personalized. CS Head or CSM based on relationship. Brief and direct — don't over-explain the purpose. Target completion by end of week 4 to leave time for synthesis.

---

## Phase 3: Interviews (Weeks 3–5)

Synthesize after the first 4–5 conversations before continuing — early signals may reshape the interview guide. CSMs join calls where they have existing relationships; otherwise debrief with them afterward.

If any hypothesis is clearly confirmed or refuted by the midpoint, adjust the remaining interview targets to focus on what's still uncertain.

---

## Phase 4: Synthesis and Churn Plan (Weeks 5–6)

### Full findings document (COO briefing)
For each hypothesis: status (confirmed / partially confirmed / refuted / insufficient evidence), evidence summary (data signals + interview corroboration), account segments affected. Where findings are mixed, explicit evidence thresholds: "this is what solid would look like; here is where we are against it."

ICP findings, if material: three-source corroboration — usage pattern (never-activated shape), interview language (fit vs. execution), sales cycle signals (flagged accounts, CSM handoff notes). This is the evidence bar for a cross-functional conversation.

### Churn plan (annual planning input)
Organized by intervention, not by hypothesis. For each recommended action: what's driving it, what we're changing, what we expect it to achieve, rough ARR impact if successful. Framed for COO + CRO audience. Dollar story embedded.

### CSM-facing summary
What changes, why, and how it helps them succeed. Delivered before the churn plan circulates upward. Coverage model or comp implications handled in separate individual conversations, not via document.

---

## Hypothesis Evidence Thresholds

Defined in advance so findings are assessed against a standard, not a judgment call under pressure.

| Hypothesis | What "confirmed" looks like |
|---|---|
| Onboarding failure | Cohort data shows churned accounts have significantly lower 60-day activation rates; "activated then dropped" pattern; interview language about execution/support gaps, not fit |
| Competitive displacement | CRM notes tag competitor in 8+ of 40 accounts; interviewees name competitor and describe a specific capability gap or pricing event; concentrated in 50–200 employee segment |
| Pricing sensitivity | Pricing raised in CRM notes across multiple accounts; interviewees describe a specific renewal negotiation event; not explained by competitive or ICP factors |
| ICP mismatch | "Never activated" usage pattern in multiple accounts; interviewees use fit/role language, not execution language; "dedicated person" probe returns "still wouldn't have renewed"; sales cycle signals present |
| Product gap | Feature named in CRM notes pre-churn (not post-hoc); multiple independent accounts name the same gap; competitor demonstrably offers it today |
