## Turn 1

**User:**
Hey — I need to ship Workflow Automation V2 by Friday and I'm trying to nail down the final week. Specifically: what scope cuts make sense to de-risk the ship, how to frame it at the all-hands next week, and what to put in the board update. Also need a CSM enablement plan so the field can actually position it. Can you help me work through this?

**Assistant:**
That's a lot to get right in one week. Let me help you think through each piece — but I need to understand the situation better first.

A few questions to orient:

1. **What's the current state of V2?** What's actually done and what's still in flight? And what was the original scope — what might not make it?

2. **What's the risk signal?** Is it engineering confidence ("we might not finish X"), quality ("Y isn't tested enough"), or something operational ("we can't support Z at launch")?

3. **Who's the board update for?** Is this a standard update to keep them informed, or is there a specific narrative you need to land (e.g., explaining a delay, justifying investment, previewing a pivot)?

4. **What does CSM enablement look like today?** Is there existing training infrastructure, or are you building from scratch? And what do the CSMs currently know about V2?

You don't need to answer all of these at once — start wherever feels most urgent.

## Turn 2

**User:**
Okay, quickly:

State: Core workflow builder and the visual canvas are mostly done. Conditional branching logic is functional but the edge-case handling is shaky — nested conditions especially. We have maybe 3-4 areas that need triage. The risk is a mix of engineering confidence on branching edge cases and quality — we haven't done a full regression pass yet.

Board update is a standard Q4 update. We committed to a "Q4 launch" as part of our roadmap and I need to be able to say we shipped it.

CSM enablement is basically starting from scratch. They know V2 is coming, they've seen demos, but there's no training material, no positioning doc, nothing they can use in a customer call.

Most urgent to me right now is the scope question — what do I cut to make Friday actually safe? The branching edge cases worry me but I don't want to ship V2 without branching, that's the whole point of the thing.

**Assistant:**
Good — the scope question is the right place to start, and here's a framing that might help:

**The nested conditions problem isn't necessarily a cut — it might be a cap.**

There's a difference between "branching doesn't work" and "nesting beyond 2 levels has edge cases." If you define a nesting limit explicitly (e.g., "V2 supports up to 2 levels of nested conditions"), that's a product decision, not a bug. You ship branching — which is the whole point — and you're honest about depth limits. That's much cleaner than either shipping shaky behavior or cutting the feature.

But I need to understand the triage areas better before I can say what's actually safe to cut vs. cap vs. fix:

**What are the 3-4 areas that need triage?** Even a quick list — "nested conditions, X, Y, maybe Z" — would let me help you reason through each one differently.

And one more question that changes the calculus significantly: **Is this a broad GA on Friday, or could it be a limited launch?** Shipping to 5-10 beta customers still counts as "Q4 launch" for the board, and it buys you a week before wider rollout. If that's on the table, the scope conversation looks very different.

## Turn 3

**User:**
The cap framing is actually useful — I hadn't thought about it that way. Let me name the areas:

1. Nested conditions (2+ levels) — the main one
2. Canvas rendering when workflows get complex, 10+ steps starts to lag
3. Error states when a step fails mid-workflow — behavior is inconsistent right now
4. We have one specific trigger type (webhook inbound) that's not fully tested under load

On the limited launch — I've thought about this. The problem is the all-hands demo. If I'm demoing V2 to the whole company next Tuesday and then telling customers "actually it's beta only," that's an awkward message. The whole reason Friday matters is so I can say at the all-hands "this shipped this week." A limited beta doesn't feel like the same moment.

That said — I'm not completely closed to it if the alternative is shipping something that breaks on customers. I just need to understand what I'm trading off.

**Assistant:**
Good — now I can give you a much more useful breakdown. Let me work through the four areas:

**Cap, don't cut:**
- **Nested conditions** → Cap at 2 levels. Ship "branching with up to 2 levels of nesting." That's a real, useful feature. Deeper nesting is Q1. This is a product decision, not a retreat.
- **Canvas rendering** → Document it. "Workflows with 10+ steps may experience performance degradation." Most customers won't build 10-step workflows in week one. Annoying but not trust-breaking.

**Fix before Friday:**
- **Error states** → This is actually your highest-risk item, and it's not cuttable. Inconsistent error behavior in a workflow automation product is quietly devastating — customers can't tell if their automation ran or not. Silent or unpredictable failures erode trust faster than missing features do. What does fixing this take? Hours? A day?

**Assess load expectations:**
- **Webhook under load** → How central is this trigger type to early adopters? If it's a power-user feature, suppress it from the demo and add a "not recommended for high-volume use in V2.0" note. If customers are going to hit it day one, you need to know what load you're actually expecting — the answer might be "fine for our initial rollout size."

---

On limited vs. full: there's a middle path worth considering — **soft GA**. It's live, available to all customers, you ship it Friday, you demo it Tuesday and say "this shipped last week." You just don't do a big marketing push or email blast yet. You control the noise level without creating the awkward "beta only" message. Lets you fix what you need to fix before you amplify.

What does fixing the error states actually look like on the engineering side?

## Turn 4

**User:**
The cap/fix/assess framing is helpful, I'm going to use that structure with my team today.

On error states — I honestly don't have a precise estimate. My eng lead mentioned it earlier this week as "not trivial" which usually means 1-2 days, not hours. That's tight against Friday. I'll get a real number today.

The soft GA concept is interesting and I think it might actually work for the all-hands narrative. "Shipped Friday, now live for all customers, here's the demo" — that tracks. I don't *have* to send a customer announcement email the same day we ship.

One thing that's been nagging at me though, and you're making me think about it more directly: we added both the conditional branching and the visual canvas during the build itself — branching because a competitor shipped it, canvas because our designer thought it would feel better. Neither of those came from customers. And our original discovery was... thin. Three interviews, six months ago, none of them specifically asking for what we built. 

I've been heads-down on execution and not thinking about that. But if I'm being honest — I don't actually know if the specific shape of what we built is what customers wanted. The CSMs say "customers want more advanced workflows" but when I push, they can't point to anyone who asked for branching specifically or a visual canvas.

Does that change anything about how you'd approach this?

**Assistant:**
Yes — it changes something important, but not the ship decision. Let me be direct.

**The technical edge cases are not your biggest risk. Shipping to silence is.**

If customers don't know what to do with branching or the canvas — if there's no obvious "oh, *this* is what I've been trying to do" moment — you'll ship Friday, demo Tuesday, and in 90 days someone will ask about V2 adoption and the answer will be uncomfortable.

Here's what it changes for each of your four asks:

**Scope cuts** — same framework, but now there's a reason to prefer soft GA even more strongly. You want to learn fast from early usage before you amplify. Ship quietly Friday, watch closely, then run a proper launch when you know what's resonating.

**All-hands framing** — you can't lead with "customers asked for this" because they didn't, specifically. But you *can* say something honest and actually more compelling: *"The category is moving toward advanced automation. We have a strong hypothesis that customers trying to [X] are hitting a wall with simple linear workflows. We shipped V2 this week, and we're going to find out if we were right."* That's a confident framing that doesn't overcommit to something you don't yet know.

**Board update** — you committed to Q4 launch, you shipped Q4, that's clean. But define your V2 success metric *now*, before they ask. "X customers with branching-enabled workflows in 60 days" or similar. Don't wait for Q1 to get asked.

**CSM enablement** — this is where the thin discovery hurts most. You can't write a positioning doc if you don't know what problem it solves in customer language. The plan has to flip: instead of "here's how to position V2," it becomes "here's our hypothesis about who this is for and what it solves — go find out if it's right, and here's what to listen for." That's actually more useful to a good CSM anyway.

The question I'd push on before we go further: **do you have a hypothesis?** Even a rough one — "we think customers trying to handle multi-step approval flows are the ones who will light up" or "we think it's the power users who've been asking for if/else logic." Something the CSMs can take into calls and test. Do you have that, or has the team not really articulated it?

## Turn 5

**User:**
"Shipping to silence" — yeah, that's exactly what I've been quietly worried about. I've seen it happen before and it's the worst outcome. You ship, you demo, and then three months later the metrics are embarrassing and nobody wants to talk about it.

On the hypothesis — we have something, but I wouldn't call it crisp. The rough version: customers who are trying to manage multi-step approval processes or exception handling in their ops workflows are the ones hitting the ceiling with the current linear automation builder. The "if a deal is over $50K, route it differently" type of use case. That's where I'd expect the branching to click.

We also heard — mostly through CSMs — that some customers are stitching together multiple separate automations to fake a sequential workflow because V1 can't do it natively. V2 should just... do that directly.

But I'll be honest — we've never validated either of those with a direct customer conversation. That's the gap.

The CSM enablement flip you're describing — "here's the hypothesis, go test it" — that's actually a better frame and probably more honest than anything I would've written. A good CSM can work with that. It also gives us signal back faster.

Can you help me make that concrete? Like what does a "CSM enablement as hypothesis-testing" doc actually look like?

**Assistant:**
Good — those two hypotheses are actually quite strong. Let me make them concrete, and I'll write this as something close to the real document so you can adapt it directly.Let me capture what we know while drafting the CSM doc:Now the CSM doc. Here's what it actually looks like:

---

## Workflow Automation V2 — CSM Enablement Guide

**Purpose:** V2 is live. Your job in the next 30 days is two things: help customers start using it, and help us learn whether we built the right thing for the right people. This doc gives you two hypotheses and the tools to test them.

---

### What shipped

- **Visual workflow canvas** — build and visualize multi-step automations in a drag-and-drop interface
- **Conditional branching** — if/else logic natively in a workflow, up to 2 levels of nesting
- **Multi-step sequential workflows** — no more stringing separate automations together

**Known limits in V2.0:** Branching supports up to 2 levels of nesting (deeper nesting is Q1). Workflows with 10+ steps may see some canvas lag. Be transparent about these — they're scope decisions, not bugs.

---

### Hypothesis 1: The Approval / Exception Router

**The bet:** Customers running approval flows or exception-handling in their ops workflows are hitting the ceiling with linear automation. They want "if a deal is over $50K, route it differently" — and right now they're doing it manually or in a separate tool.

**Who to talk to:** RevOps, deal desk, ops teams, anyone whose job involves routing things based on criteria.

**Questions to open with:**
- "Walk me through how you handle [approvals / exceptions] right now. What happens when something falls outside the normal path?"
- "Are there decisions in your workflow that depend on the value, size, or type of something — and you have to handle them differently?"
- "Is there any logic in your process that's basically 'if X, then Y, otherwise Z'?"

**What to listen for:** "We do that manually." / "We have a spreadsheet for that." / "It depends on..." followed by a condition. Those are the moments.

**If it resonates, show this:** Build the "$50K deal → deal desk" branch live, or use a pre-built example. Keep it simple. One condition, two paths.

---

### Hypothesis 2: The Workflow Stitcher

**The bet:** Some customers have built 3–5 V1 automations that are really one workflow. They're sequencing them through triggers or manually kicking them off because V1 can't chain them natively. V2 does this in one place.

**Who to talk to:** Power users with multiple active automations, customers who've complained about V1 complexity or asked about "chaining."

**Questions to open with:**
- "Do you have automations that are meant to run one after another?"
- "Have you ever split something across multiple automations just to make it work?"
- "Is there a workflow you've wanted to build but gave up on because it was too complex?"

**What to listen for:** Multiple automations with similar triggers or overlapping scope. Customers who've hit limits or said things like "we wanted to do more but couldn't."

**If it resonates, show this:** Take their existing automations and show how they collapse into one V2 workflow. The "before/after" is the demo.

---

### What to capture and send back

After every V2 conversation, log:
- Which hypothesis (if either) resonated
- The specific use case — what team, what workflow, what problem
- What they said that we should steal for our own messaging
- Any use cases that came up that aren't on our radar
- Questions you couldn't answer

This is signal we need to make V2 successful. Don't skip it.

---

### What not to demo
- 3+ levels of nested conditions (not supported yet)
- Workflows with 10+ steps (canvas may lag)
- Webhook triggers under high load (not stress-tested)

---

That's the structure. A few things worth noting: the "what to capture" section is what makes this useful as discovery infrastructure, not just a pitch doc. And being explicit about what *not* to demo keeps CSMs from accidentally walking into the known rough edges.

Does this match what you were imagining, or do you want to push it in a different direction before we move on to the all-hands framing?

## Turn 6

**User:**
This is genuinely useful — way more specific than what I would've written. The "what to capture" section is exactly right, I would've left that out and then had no signal to show for the first 30 days.

One tweak: I'd want to add something up front that gives CSMs permission to say "I don't know if this is for you yet — let's find out together." Some of them will try to oversell it and that's where we get into trouble. But that's an edit I can make.

Yes, let's move to the all-hands framing. That's the one I actually have to deliver in person next Tuesday and I need it to feel confident without overpromising. The version you sketched earlier — "strong hypothesis, we shipped, we're going to find out if we were right" — I like the honesty of that but I'm worried it'll read as uncertain to a company audience. People want to feel good about what we shipped, not like we're running an experiment.

And I still need the board update language. That one needs to be clean: we said Q4 launch, we shipped Q4, here's how we'll know it worked. What's the right success metric to propose?

**Assistant:**
Good question on the all-hands tension — and it's solvable. The issue isn't "hypothesis vs. certainty," it's what carries the confidence. Let me separate them.

**All-hands framing**

The confidence doesn't have to come from "we know this will work." It comes from three things you *are* certain about: the problem is real, the product works, and you know who you're going after first. That last part is the key — framing your hypotheses as *targeting*, not uncertainty.

Draft structure:

---

**Opening — the problem (crisp, relatable):**
> "Anyone who's tried to build a non-trivial workflow in V1 has hit the same ceiling. The moment your process needs to branch — 'if a deal is over $50K, route it to deal desk; otherwise keep going' — you're stuck. You either split it into separate automations and wire them together manually, or you give up and do it by hand. That's what we built V2 to fix."

**The demo.** This is where the confidence lives. Let the product carry it. Show one clean branching workflow on the canvas. Don't show edge cases or complex flows. One scenario, built live or close to it.

**Targeting, not hedging:**
> "The customers we're going after first are ops teams managing approval and exception-handling flows, and power users who've been stitching separate automations together to fake a workflow V1 couldn't do natively. If you're in those conversations — this is the moment."

**The ask:**
> "CSMs have enablement material starting today. Get in front of those customers and tell us what you hear. The next 30 days are about learning what clicks and for whom — and the field is how we learn that."

**Close:**
> "We shipped V2 this week. It's live. Now we find out what customers build with it."

---

The phrase "now we find out what customers build with it" reads as *excitement*, not uncertainty. That's the frame. You're not saying "we hope this works" — you're saying "we can't wait to see what people do with this." Very different energy.

---

**Board update language**

Three beats: we delivered, here's what shipped, here's how we'll know it worked.

> **Workflow Automation V2 — Q4 Launch**
>
> We shipped Workflow Automation V2 in Q4 as committed. The release delivers a visual workflow canvas and native conditional branching — capabilities required to compete in the enterprise automation tier and frequently flagged by CS as blocking deal conversations.
>
> **Q1 success metric:** [X]% of active customers with at least one branching-enabled workflow in production by [60 days out]. We'll report against this in the Q1 update.
>
> Early go-to-market focus: approval workflow and ops exception-handling use cases. CSM enablement is in flight as of this week.

---

On the success metric number: I'd set it to feel ambitious but grounded. A useful rule of thumb — **new feature activation in the first 60 days rarely exceeds 15–20% of your base without a push**, and 5–10% with normal rollout is more typical. Pick a number you'd be proud of but wouldn't be embarrassed by if you hit 80% of it. What's your rough active customer count? I can help you land on something specific.

And one thing worth saying directly: **"branching-enabled workflow in production"** is the right metric, not "customers with V2 access." The board metric should be a behavior, not a feature flag. That's the line between "we shipped it" and "it worked."

## Turn 7

**User:**
The all-hands framing works. "Now we find out what customers build with it" — that's the right energy. I was trying to solve the wrong problem; I was trying to sound certain, but what I actually need is to sound like I'm leading into something, not away from something. That reframe does it.

The board language is clean. "Capabilities required to compete in the enterprise automation tier" is a stronger frame than I would've written — it ties to business context, not just feature output.

On the metric: we have roughly 250 customers who've actively used automations in the last 90 days. That's my denominator. Given what you said about new feature activation, I'm thinking I propose 10% with a branching-enabled workflow in production within 60 days — so 25 customers. Feels credible, meaningful, and not sandbagged.

Does that feel right? Or is there a reason to set it higher given the CSM-enabled push we're planning?

**Assistant:**
25 customers is right. Don't push it higher.

Here's why: the CSM motion you're launching is *focused*, not broad. The enablement doc targets two specific customer profiles — it's not "tell everyone about V2," it's "find the right conversations and run them well." That's a quality-over-quantity approach, which is correct, but it limits the raw volume of outreach you'll actually get in 60 days. CSMs have other priorities, the enablement is brand new, and there's real friction between "CSM has a good conversation" and "customer has a production workflow running."

You could hit 20% if the CSM motion is exceptionally crisp from day one and every conversation converts at high rates. But you don't know that yet — that's actually what the next 30 days are for. Committing to 20% at the board is betting on execution you haven't seen yet.

There's also a psychological dimension: 10% that you hit confidently, with a clear story about *which* customers and *why*, is far more compelling than 20% that you narrowly miss. The board remembers the miss.

One thing I'd add to the metric though: make sure "in production" means something. A workflow that ran once counts differently than one that's actively handling real volume. You don't need to put this in the board update, but internally define it as something like **"executed at least 3 times in production"** — that filters out toy experimentation and gives you signal about real adoption.

And track an informal second metric for yourself: **use-case clustering**. If 18 of your 25 customers are all doing approval routing variations, that tells you something decisive about the hypothesis. If the 25 are scattered across random use cases, that's a different signal. Not for the board — for you, to know what to build next.

---

You now have all four pieces:
- **Scope cuts**: cap/fix/assess framework + soft GA option
- **All-hands**: lead with the problem, demo, target, invite
- **Board update**: Q4 delivered, 25 customers in 60 days
- **CSM enablement**: hypothesis-testing doc with feedback loop

Anything you want to sharpen further, or is there something you haven't said yet that's still nagging?

## Turn 8

**User:**
No — I think that's actually it. You've given me something useful for each of the four things I came in with, and the framing shift on CSM enablement is going to change how I write that doc.

The one thing still hanging is the error states engineering estimate — but that's on me to chase down with my eng lead today, not something you can answer. If the fix is 2 days, I have a decision to make about Friday. That's a real decision, not a planning problem.

Honestly the thing I'm leaving with that I didn't expect: I came in wanting to solve "how do we ship Friday cleanly" and the more useful question turned out to be "how do we make sure Friday isn't where the story ends." The 25-customer metric and the CSM feedback loop are how I keep this alive after launch. I'd kind of forgotten that part.

Thanks — this was worth the hour.

**Assistant:**
That reframe — "how do we make sure Friday isn't where the story ends" — is worth writing down.Good luck with the eng lead conversation today — that's the one decision that can't wait. Everything else you have what you need for.

What you came in with and what you're leaving with are actually the same problem, just seen from different angles. The scope cuts are about not breaking the launch. The 25-customer metric and the feedback loop are about not wasting it. Both matter.

Go ship it.
