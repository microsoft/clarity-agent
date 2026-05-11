## Turn 1

**User:**
Hi — I'm hoping you can help me think through a research plan. I'm Head of Customer Success at a B2B SaaS company and our gross logo churn has crept up from about 7% to 11% over the last three quarters. My COO asked me point-blank last week why we're losing accounts, and I gave her a list of plausible reasons but nothing I'd actually stand behind.

I want to build a proper research program to get a defensible answer — surveys of churned customers, interviews, cohort analysis of usage patterns, segmentation by persona and vertical. I'm thinking 2–3 months of work. I have about 40 accounts that churned in the last two quarters and annual planning starts in 6 weeks, so the COO wants a "churn plan" as input.

Can you help me scope this out and make sure I'm asking the right questions and using the right methods?

**Assistant:**
Great problem to dig into — and there's something worth flagging right away before we scope the research.

You said 2–3 months of work, but annual planning starts in 6 weeks. That's a real tension: your COO wants a churn plan *as input* to planning, not as a follow-up to it. So the first question worth settling is: **what does she actually need in 6 weeks vs. what can be a follow-up?**

A few more things would help me understand the shape of this:

1. **What do you already suspect?** You said you gave her "plausible reasons" — what were they? That shapes which hypotheses need rigorous testing vs. just validating.

2. **What data do you already have?** Is there CRM data, product usage/telemetry, NPS/CSAT scores, exit surveys? Or is this mostly institutional knowledge right now?

3. **Who's doing the research?** Is this you personally, you plus a team, or are you engaging a researcher or analyst?

4. **How reachable are churned accounts?** 40 accounts — do you have relationships with contacts at most of them, or have many gone cold?

The reason I ask before scoping: a survey-heavy program with cohort analysis and segmentation is a solid 3-month effort. But if the COO needs a *defensible directional answer* in 6 weeks, there's a faster path — targeted interviews with 8–12 churned customers plus a quick pass at whatever usage data exists can get you there. The fuller program is still worth doing, but you'd be sequencing it differently.

Let me start capturing what you've told me while we talk.What were those plausible reasons you gave the COO?

## Turn 2

**User:**
The timeline tension is real and I haven't fully resolved it in my head. The COO needs *something* in 6 weeks, but I've been telling myself the research is the plan — which your question is making me realize is circular.

On the plausible reasons: I told her three things. One, pricing — we're not the cheapest and some accounts mentioned it in renewal conversations. Two, a specific competitor that's been aggressive in our mid-market segment over the last year. Three, our onboarding — anecdotally, accounts that struggled in the first 60 days seem to have higher churn, but I haven't actually verified that pattern.

The honest answer is I'm not sure which of those is actually driving the 11% or whether it's something else entirely. That's what worries me.

On data: I have product usage data — feature adoption, DAUs, session depth. Support ticket volume with sentiment tags. NPS survey responses (quarterly, roughly 15% response rate). And CRM notes from our CSMs covering renewals and cancellations, though the quality is inconsistent. Some CSMs write detailed notes, some are one-liners.

Team-wise: it's me and 4 CSMs, plus I have an analytics partner I can pull in for the heavier quantitative work. I can't dedicate a CSM full-time to this, but I can involve them.

**Assistant:**
This is really clarifying. A few things are coming into focus that I want to share before asking more:

**The research-as-plan circularity is the key insight.** What your COO needs in 6 weeks isn't a research plan — she needs findings she can act on. And here's the thing: you already have most of what you need to get there. Product usage data, support sentiment, NPS, CRM notes across 40 accounts — that's a rich dataset. You don't need to build a research program from scratch; you need a structured 6-week sprint to mine what you have and fill the gaps with targeted interviews.

**Your three hypotheses are testable with existing data:**
- *Onboarding* → directly testable with your usage data right now. 60-day feature adoption curves, DAU trajectories for churned vs. retained cohorts. Your analytics partner could have a preliminary answer in a week.
- *Competitor displacement* → the CRM cancel notes will flag this. If a CSM wrote "went to [Competitor]" in 15 of 40 accounts, that's a signal. If it appears in 3, it's noise.
- *Pricing* → also in the CRM notes, and you can cross-reference with renewal conversation records and deal size.

Two questions before I go further:

1. **How are those 40 churned accounts distributed?** Mostly mid-market (where the competitor is active), spread across segments, or skewed another way? This matters a lot for whether competitive displacement is a primary driver or a segment-specific story.

2. **Have any of the 40 been spoken to since churning?** Even informal "why'd you leave?" conversations? Knowing what's already been learned vs. genuinely cold contacts changes the interview strategy.

I'm also keeping notes as we go:

## Turn 3

**User:**
That framing lands. I think I've been conflating "doing rigorous research" with "having a defensible answer" — and those aren't the same thing if I'm sitting on data I haven't actually analyzed.

On the 40 accounts: they're mostly mid-market, which is our core segment, so that's not terribly diagnostic on its own. But when I think about it, there's probably a cluster in the 50-200 employee range that churned in Q3 — that's roughly where I've heard the competitor mentioned most. I don't have a clean segmentation in front of me, but my analytics partner could slice it quickly.

On post-churn conversations: a few. Two of my CSMs reached out informally to accounts they had close relationships with — I'd estimate 4 or 5 conversations total, nothing structured. The consistent thing I heard second-hand was something like "the product's great but we didn't have bandwidth to run it properly." Which could mean onboarding, could mean we sold to the wrong persona, could mean something else entirely.

What I'm warming up to is the idea of doing the data pass first before I design the interview program. If the usage cohort analysis shows a clear onboarding signal, I'm asking different questions in interviews than if the cancel notes are all competitive displacement. That's actually a better research design anyway, not just a time-saver.

But I want to make sure I'm not under-investing in the qualitative piece. The data can tell me *what* happened — I need conversations to tell me *why*.

**Assistant:**
You've landed on genuinely good research design — sequencing quantitative before qualitative means your interviews are hypothesis-driven rather than exploratory, which makes them sharper and the findings more defensible. That's not cutting corners, that's the right method.

One thing worth flagging: those informal post-churn conversations surfaced something that *isn't* in your three hypotheses. "Product's great, didn't have bandwidth to run it properly" is a distinct signal — it could mean **wrong ICP or persona** (you sold to accounts that were never set up to operationalize the product, regardless of onboarding quality). That's worth adding as a fourth hypothesis, because it points at a different intervention than the other three. Onboarding failure is a CS problem. Selling to the wrong profile is a sales + ICP problem. The annual plan implications are very different.

On under-investing in qualitative: the protection isn't more interviews — it's better questions. Eight to twelve conversations is plenty if the interview guide is hypothesis-driven from what the data shows. What kills qualitative research is asking "why did you leave?" and getting polite post-hoc rationalization. What makes it work is asking "walk me through the last 60 days of your contract" and listening for when things changed.

Here's the shape of what I think this looks like:

**Weeks 1–2: Data sprint**
- Analytics partner runs cohort analysis: 60-day activation rates and feature depth for churned vs. retained accounts
- Systematic coding of CRM cancel notes for all 40 accounts: stated reason, deal size, segment — even inconsistent notes give you something when you look at them in aggregate
- NPS score trajectory in the 6 months before churn, by cohort
- Support sentiment in final 90 days of tenure

The output is: hypothesis status going into interviews (strong signal / weak signal / unknown), and a prioritized interview list (thin CRM notes, accounts fitting the strongest hypotheses)

**Weeks 2–3: Interview design + outreach**
- Write interview guide based on what the data shows
- Reach out to 15–18 accounts, target 8–12 completions
- Prioritize: accounts with thin CRM notes, the Q3 50–200 employee cluster where the competitor is mentioned, accounts where usage data shows the "never really activated" pattern

**Weeks 3–5: Interviews**
- 30–40 minutes each, at least one CSM involved where they have the relationship
- Synthesize after the first 4–5 before continuing

**Week 5–6: Synthesis and churn plan**
- Hypothesis confirmed / refuted / uncertain with supporting evidence
- Recommendations tied to each confirmed hypothesis
- What's still unknown and what it would take to find out

Does this feel like the right shape? I want to make sure we get the problem and success criteria properly scoped before we get into the details — specifically, what "defensible" means to your COO and what the churn plan actually needs to contain.

## Turn 4

**User:**
That fourth hypothesis is the one that makes me a little uncomfortable — not because it's wrong, but because if it's true, the conversation with my COO looks very different. "We have an onboarding problem" is mine to own and fix. "We've been selling to accounts that can't operationalize the product" is a Sales and ICP conversation that involves people who aren't in my org. I need to be prepared to walk into that with solid evidence, not just a pattern in cancel notes.

The plan shape feels right to me. I was skeptical when you started pushing toward "use what you have," but this isn't a shortcuts version — it's sequenced correctly and it's actually more defensible because the interviews are grounded in data.

On what the COO needs: honestly, I haven't been precise about this. My mental model is she wants to walk into annual planning knowing where to invest — do we double down on CS headcount, do we fix the onboarding motion, do we tighten the ICP, do we build a competitive response. "Churn plan" in her language probably means "here's what's causing it and here's what we're changing." I don't think she needs statistical significance — she needs a clear story with evidence she could defend to the board if pressed.

What she doesn't want is another list of plausible reasons with no prioritization. That's what I gave her last week and it clearly wasn't enough.

One thing I'm uncertain about: how do I frame findings that are genuinely mixed or inconclusive? If the data points at onboarding but interviews suggest ICP, do I present both? I've seen that kind of ambiguous finding get used to justify inaction.

**Assistant:**
The mixed findings question is the right one to nail down before you're in front of your COO — because the framing choice you make now will determine whether the findings produce decisions or hedging.

**The dangerous version of mixed findings:** "It could be onboarding, or it could be ICP." That's what gets used to justify inaction, and it's what you already gave her last week in a different form.

**The useful version:** Segmented findings. "For this cluster — mid-market, 50-200 employees, Q3 cohort — the evidence points to ICP. For this cluster — smaller accounts that churned earlier — the evidence points to onboarding." That's not ambiguity, that's precision. Different causes, different segments, different interventions. Your COO doesn't need one root cause — she needs to know where to invest. Segmented findings give her that.

When data and interviews point in different directions, that's usually not a conflict — it's complementary. Data tells you *what* happened (activation dropped at day 45). Interviews tell you *why* (we never had an internal champion after the person we sold to left). Neither is wrong. The frame you want: "Here's what we observed in the data. Here's what the interviews explain about it."

On the ICP hypothesis and the cross-functional conversation: you're right to hold this to a higher evidence bar. Here's what "solid evidence" looks like for that finding specifically — and it's distinct from onboarding failure even if both show up as low activation:

- **Usage pattern:** Accounts that *never* activated meaningfully — flat engagement from week one, not a drop after initial adoption. That's a different shape than "started strong, fell off."
- **Interview language:** Multiple independent accounts using language about *fit* rather than *execution* — "it was solving a problem we didn't really have," "the person who was supposed to use it turned out not to be the right role"
- **Sales cycle signal:** CSM handoff notes or CRM records showing warning signs at the point of sale — small champion, unclear use case, competitive displacement of a free tool

If all three line up across several accounts, you're not walking into a Sales conversation with a pattern in cancel notes — you're walking in with a coherent story across three independent data sources.

One thing worth building into your synthesis now: for each hypothesis, document the evidence threshold that would make you confident vs. uncertain. Then when you have findings, you're not making a judgment call under pressure — you already decided what "solid" means.

I want to make sure we get the full scope captured properly. Let me update the documents and then I'd like to work through one more thing with you: who else has a stake in the findings, because that affects how the research gets packaged and what "defensible" means in practice.Who else will see these findings — your CSMs, Sales leadership, the broader exec team? And is the COO the decision-maker on all four potential interventions, or do some of them require buy-in from someone else?

## Turn 5

**User:**
That three-signal test for ICP is exactly what I needed — I was thinking about it as "do we see a pattern" but you've given me something much more specific to look for.

On stakeholders: the COO is the primary audience and she owns the CS org, so she can authorize anything that's mine to fix — onboarding redesign, QBR process changes, CSM coverage model. That's clean.

The harder scenario is if ICP comes back as a primary finding. The CRO owns Sales, and she and my COO are peers. They have a decent working relationship but it's not without friction. If I walk in saying "Sales is closing accounts that shouldn't be in our ICP," that's a conversation between two C-suite people, not something I can just put in a slide deck and let land on its own. I'd want my COO aligned on the findings before they go anywhere near the CRO.

My CSMs will definitely see the findings — I'd involve them in synthesis anyway, they know these accounts. And if there's a comp or coverage model conversation that comes out of this, that's sensitive. I'd want to frame findings to them before they're presented upward, not after.

The broader exec team — CEO, CFO — would likely see this in the context of annual planning, but probably as a summary, not the full research. If churn is going to be a line item in the plan, the CFO will have questions about the revenue impact. I should probably think about how to connect the findings to a rough dollar story.

Does that affect how we think about packaging the output?

**Assistant:**
Yes — significantly. What you've described isn't one deliverable, it's a sequenced set of outputs aimed at different audiences for different purposes. Getting the sequencing wrong is as damaging as getting the findings wrong.

Here's how I'd think about the packaging:

**The source document** — full findings, all hypotheses, evidence, segmentation. This is what you and the COO see first, in a private briefing before anything circulates. This conversation is where you walk through the ICP finding if it emerges, let her react, and figure out together how it gets taken to the CRO. You don't want her surprised by it in an exec meeting.

**The churn plan for annual planning** — action-oriented, not research-oriented. Organized by intervention ("here's what we're changing, why, and what we expect it to do"), not by hypothesis. The ICP finding, if it surfaces, gets framed as "sales qualification opportunity" or "ICP refinement" — a joint problem to solve, not an attribution of fault. Dollar-connected: if churn stays at 11% vs. returns to 7%, here's the ARR implication. That's the CFO frame and it actually strengthens the case for every intervention by putting a number on the cost of inaction.

**CSM-facing summary** — before it goes upward, as you said. Focus on what changes and why, framed around how it improves their ability to help customers succeed. If coverage model or comp is on the table, that conversation happens separately with each person, not via a document.

**CEO/CFO view** — summary of the plan and the dollar story. They don't need the research; they need to know the problem is diagnosed and being addressed with a credible plan.

The sequencing: **you → COO → CSMs → CRO (COO-led) → annual planning doc → exec team**. The CRO conversation is COO-to-CRO with you as context-provider, not you presenting to the room.

One more thing on the dollar story: you'll want to connect the 40 churned accounts to ARR, then model what it means if churn stays elevated vs. improves. You probably know those numbers better than you realize — average contract value times churn rate math is simple, and it makes the conversation with the CFO much more grounded. Worth building that in parallel with the research, not as an afterthought.

Let me capture the stakeholder picture properly:I think we have enough clarity on the problem and stakeholders to move into actually designing the research. Before I do, one question: is there anything about the problem framing as I've described it that doesn't feel right — either the four hypotheses, the 6-week constraint, or the way I've characterized what the COO needs? I want to make sure we're building the research design on solid ground before committing to it.

## Turn 6

**User:**
The framing feels largely right, but there's something I should have flagged earlier that adds nuance: our net revenue retention is still above 100% because the accounts that stay expand. So we're losing logos but not net ARR — yet. The COO's concern is the trendline, not an immediate revenue crisis. That might affect how the dollar story gets framed — it's less "here's the ARR we lost" and more "here's the ARR at risk if this trajectory continues, plus the compounding drag on the business."

On the four hypotheses: I'm comfortable with those, but one thing I don't have a bucket for yet is product gaps. A handful of churned accounts mentioned features they needed that we either didn't have or didn't have in a mature enough state. I don't know if that's a primary driver or just a convenient explanation, but it probably deserves to be on the hypothesis list even if it turns out to be noise.

The 6-week constraint is real and I'm genuinely more at peace with the sequenced approach than I expected to be at the start of this conversation.

The one thing I'd still push on: I want to make sure the interview component doesn't get de-prioritized if the data sprint takes longer than expected. The "didn't have bandwidth to run it properly" signal from informal conversations feels important and it's exactly the kind of thing that won't show up cleanly in usage data.

But overall — yes, build on this. I think we're ready.

**Assistant:**
Good additions — both of them change the design in specific ways.

The NRR framing matters for the dollar story and also for the COO's urgency calibration. The right frame is: "We're not in a revenue crisis today because expansion masks logo loss — but churn at 11% is compounding drag that erodes the expansion base over time, and the trendline suggests it gets worse before it gets better." That's a more sophisticated argument than ARR lost to date, and it's actually more alarming if you model it out two or three years.

Product gaps as a fifth hypothesis is right to include, with one caveat: it's the easiest thing for a churned customer to say and the hardest to verify. "We needed feature X" often means "we didn't find the value we expected," with a specific feature attached post-hoc. The interview needs to probe: was this feature in the sales conversation? Did they raise it before churning? Is a competitor offering it? If yes to all three, it's a real product gap. If not, it may be a convenient explanation for something else.

And the interview guardrail you're asking for — I'll hard-code it into the plan. **Outreach starts by end of week 2, regardless of where the data sprint is.** Not "when the data sprint is done." If the sprint isn't complete, you draft the interview guide from current hypotheses and refine it as data comes in. Interviews are not downstream of data — they run in parallel once outreach is live.

Let me write this up properly now.Now let me write the research design:Here's what we've built. The research plan has four phases across six weeks:

**Weeks 1–2: Data sprint** — your analytics partner runs cohort analysis (activation curves, usage pattern classification), you and your CSMs code the 40 cancel notes systematically, and you build the dollar story as a forward compounding-drag model. Output: a hypothesis signal matrix and a prioritized interview list.

**End of week 2: Interview outreach starts** — non-negotiable, regardless of sprint status. Target 15–18 accounts for 8–12 completions, prioritized by thin notes, never-activated usage, and the Q3 mid-market cluster.

**Weeks 3–5: Interviews** — 30–40 min each, timeline-walkthrough structure rather than "why did you leave." The "dedicated person" probe distinguishes ICP from onboarding. Synthesize after the first 4–5.

**Weeks 5–6: Synthesis and churn plan** — findings document for the COO briefing (hypothesis by hypothesis, with evidence thresholds defined in advance), action-oriented churn plan for annual planning, and CSM-facing summary before anything goes upward.

The one thing I'd encourage you to do before the sprint starts: spend an hour with your analytics partner aligning on what "never activated" vs. "activated then dropped" looks like in your data. That classification is doing a lot of work — it's the primary signal for the ICP hypothesis — and you want agreement on the definition before you're looking at 40 accounts and trying to categorize them.

Anything you'd change, or are you ready to take this into execution?

## Turn 7

**User:**
This is ready to take into execution. The pre-sprint conversation with my analytics partner about activation classification is a good call — that's exactly the kind of thing that turns into a two-week back-and-forth if I don't define it upfront.

One thing I want before I close out: the interview guide structure. You've given me the right framing — "walk me through the last 60 days" rather than "why did you leave" — and the dedicated-person probe for ICP vs. onboarding. But I'm going to be running some of these interviews myself and coaching my CSMs on others, and qualitative interviewing is not my strongest skill. Can you sketch out the core questions? Not a full script, but the five or six things I need to make sure I actually ask and in roughly what order. The hypotheses I'm probing are: onboarding failure, wrong ICP/persona, competitive displacement, pricing pressure, and product gaps.

**Assistant:**
Here are the six questions, in order, with a note on what each is actually doing:

---

**1. "Walk me through the last few months of your time with [product]. Start wherever feels right."**

Open-ended, narrative, non-threatening. You're not asking *why* they left — you're asking them to tell a story. What they choose to start with is itself a signal. Let them talk. Don't redirect too quickly.

---

**2. "At what point did you actually decide not to renew? What was going on at that time?"**

The mental decision to leave usually happens weeks or months before the formal churn date. This surfaces the real trigger — an event, a conversation, a moment — rather than the accumulated grievances they'll recite if you ask "why did you leave?"

---

**3. "What were you able to accomplish with [product]? Where did things work, and where did they fall short?"**

This probes onboarding and ICP simultaneously without leading. You're listening for: *Did they ever reach value?* If the answer is mostly "we never really got it going," that's onboarding or ICP. If the answer is "it worked for X but not Y," that's a product or fit signal. Follow up if needed: *"Were there things you planned to use it for that you never got to?"*

---

**4. "Who on your team was mainly responsible for running [product] day-to-day — and did that work out the way you expected?"**

This is the ICP probe, more elegant than asking about bandwidth. You're finding out: was there a real owner? Was it the right person/role? If there was no clear owner, or the owner turned over, that's a qualification signal. 

If operationalization themes surface here, follow up: *"If you'd had a dedicated person whose job was to run this, do you think you would have stayed?"* Yes = ICP/resourcing problem. No = something else.

---

**5. "What did you move to after [product], or what are you doing differently now?"**

Non-leading — doesn't assume they went to a competitor. If they name one: *"What made that a better fit for where you are?"* That's where competitive displacement surfaces naturally. If they say "we're doing it manually" or "we're not doing it at all," that's a different signal about the priority of the problem.

---

**6. "If you were advising us — what's the one thing that would have made you renew?"**

Save this for last. It often surfaces the real reason when earlier answers have been diplomatic. It's also where product gaps come out most clearly. If a specific feature is named: *"Was that something you raised with us before your renewal decision?"* and *"Is there a tool you've moved to that does this?"* — that's your validation check against post-hoc rationalization.

---

**Two coaching notes for CSMs:**

The hardest skill in qualitative interviewing is not filling silences. After the person stops talking, count silently to five before responding. People often add the most important thing after a pause.

If they start defending you or being overly polite, say: *"I really want the honest version — we're doing this specifically because we want to understand what we got wrong."* Permission to be critical usually unlocks a more useful conversation.

---

I'll add this to the research plan document so it's in one place:That's everything you need to run the interviews yourself and coach your CSMs. The questions are sequenced so the most sensitive probes (ICP, competitive) emerge naturally from the narrative rather than feeling like interrogation.

The thing most likely to go wrong in the first few interviews is rushing to question three before they've finished with question one. If in doubt, follow the energy — if they're telling you something useful, stay there longer. The guide is a skeleton, not a script.

Good luck with the data sprint. The activation classification conversation with your analytics partner is your first milestone — everything else flows from that.

## Turn 8

**User:**
Question four is the one I'm going to use in every interview. It's genuinely elegant — you're not asking "did you have enough resources" which sounds defensive, you're just asking who owned it and whether that worked. That's a question a curious colleague would ask, not an exit survey.

The coaching note about not filling silences is also something I need to actually practice. I have a tendency to interpret pauses as confusion and jump in to clarify. I'll brief my CSMs on it too.

I came into this thinking I needed to design a 3-month research program from scratch and I'm leaving with a 6-week sequenced plan, a hypothesis framework with defined evidence thresholds, a packaging strategy I can actually navigate politically, and an interview guide I can run without being a trained researcher. That's more than I expected.

First thing Monday: get time on the calendar with my analytics partner to define activation. Thanks for pushing back on the scope early — the sequenced approach is genuinely better research design, not just a shortcut.

**Assistant:**
Good plan. The analytics partner conversation is the right first move — it's a 30-minute investment that de-risks the entire data sprint.

Everything is captured in the protocol: problem statement with all five hypotheses and the NRR framing, stakeholder map with delivery sequencing and audience framing, the full research plan with phase-by-phase detail and evidence thresholds, and the interview guide. If you come back mid-sprint to refine the interview guide once the cohort analysis is in hand, we can pick up right there.

Let me clear the notes file of items we've now resolved:Good luck with it. Come back after the data sprint if you want help refining the interview guide based on what the cohort analysis shows — or after interviews if you want to think through how to package a mixed or unexpected finding before the COO briefing.
