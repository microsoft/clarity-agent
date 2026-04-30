## Turn 1

**User:**
Hi, I'm Danielle Moreau, Director of Engineering at a B2B SaaS company. I'm dealing with a tricky situation and was hoping you could help me figure out what to do this week. Basically, a large enterprise customer needs an SSO / provisioning feature set to close an expansion contract worth ~$1.2M ARR. Our VP Sales committed to the customer that the feature would ship in Q2, but our engineering lead estimates Q3 at earliest. Pulling this into Q2 would slip our platform migration by 6-8 weeks. The CEO hasn't been briefed, and I've been trying to handle it at my layer. I have some scope-reduction options I haven't fully evaluated yet. How do I balance these competing needs?

**Assistant:**
This is a genuinely thorny situation — the kind where the right move depends heavily on details that aren't visible yet. Before jumping to options, I want to make sure I understand the full shape of it.

A few questions:

1. **What does "Q2 commitment" actually mean contractually?** Is this a signed contract with a ship date, a verbal promise the VP made in a sales call, or something in between? The answer changes your leverage and your exposure significantly.

2. **What's at stake in the platform migration if it slips 6–8 weeks?** Is that purely an internal quality/debt concern, or does it have its own downstream customer or compliance dependencies?

3. **What are the scope-reduction options you're sitting on?** Even a rough sketch — are you thinking about phasing the SSO implementation, delivering a lighter-weight version, using a third-party integration as a bridge?

4. **What's your read on the VP Sales' posture right now?** Do they know there's a gap, or are they still operating as if Q2 is achievable?

## Turn 2

**User:**
1. The "Q2 commitment" isn't contractually binding, but it's a verbal promise the VP made during the customer's procurement process. If we don't deliver, it will damage our credibility and hurt future sales cycles. However, the customer hasn't signed anything yet.

2. The platform migration is mostly an internal quality issue, but it also affects our ability to deliver future features and support new customers. If we slip, we'll increase our technical debt and risk losing momentum in the market.

3. The scope-reduction options I'm considering are:

- Only implementing SSO for the most critical user groups and adding more later
- Delivering a basic provisioning feature without automation and expanding it over time
- Using a third-party integration like Okta or Auth0 to handle SSO and provisioning until we build our own solution

4. The VP Sales knows there's a gap, but they're still optimistic that we can pull this off somehow. They think they can convince the customer to sign with a "soft" Q2 date and then renegotiate if we need more time. They're counting on me to make it happen. They're also aware of the platform migration and have expressed disappointment, but they're prioritizing the expansion contract over the migration.

**Assistant:**
Good — this sharpens things considerably. Let me capture what I'm hearing and then probe a couple more things.Three things I want to understand better:

**On the third-party option:** The Okta/Auth0 bridge is potentially the most interesting path — it might let you deliver *something real* in Q2 without the migration hit. What's your instinct on why it hasn't been fully evaluated? Is it engineering resistance, cost concerns, customer preference, or just no one's had time to scope it?

**On what the customer actually needs:** When the customer asked for SSO/provisioning, do you know what's driving it? Is this a security/compliance requirement (e.g., IT policy, SOC2 audit), an admin workflow problem (too many manual steps), or a signal from their IT team that they won't approve a tool without it? The answer matters because it affects whether a third-party integration or a "lite" scope would actually satisfy them.

**On the CEO:** You said you've been handling this at your layer. What's your concern about bringing it up the chain — is it that you want to have a solution before you escalate, or something more political?

## Turn 3

**User:**
**On the third-party option:** I think it's a combination of all those factors. Engineering resistance is the biggest one, because they don't want to rely on an external service that we don't control and that might not integrate well with our platform. Cost concerns are also valid, because we don't know how much it would cost to license and implement Okta/Auth0. Customer preference is unclear, but we have some reason to believe they would prefer a native solution over a third-party one. And yes, no one's had time to scope it fully, because we've been focused on other priorities.

**On what the customer actually needs:** I don't have a definitive answer, but I'm guessing it's a mix of security/compliance and admin workflow reasons. The customer is a large enterprise with strict IT policies and a complex user base. They want to ensure that their data is secure and accessible only to authorized users, and that their administrators can easily manage user accounts and permissions. I don't think it's a hard requirement from their IT team, but it might be a strong preference.

**On the CEO:** My concern is both pragmatic and political. Pragmatically, I want to have a solution before I escalate, because I don't want to waste the CEO's time with a problem I can't solve. Politically, I don't want to look like I'm undermining the VP Sales or failing to deliver on our commitments. I also don't want to expose the platform migration delay, which might make the CEO question our engineering capabilities and priorities. I'm hoping to resolve this without involving the CEO, but I know that's risky.

**Assistant:**
Okay — I have a clear enough picture now to say something useful. Let me capture this fully and then give you my honest read.Here's my honest read.

---

**The VP's "soft Q2" tactic is the riskiest path, not the safest one.** Getting the customer to sign based on a date you already know is likely wrong means they're making a $1.2M decision on incomplete information. When you miss Q2, the conversation isn't "we need a little more time" — it's "we knew when you signed." Enterprise procurement teams remember that. The relationship damage from a sign-and-disappoint scenario is typically worse than the damage from an honest conversation before signing.

**The CEO concern is backwards.** Your instinct is to have a solution before you escalate. But the longer you wait, the worse it looks — both politically and practically. If the VP's soft-date tactic fails and the CEO finds out you knew and didn't say anything, that's a much harder position than walking in this week with "here's the gap, here's what I'm evaluating, here's what I need from you." Bringing it with options is not weakness — it's exactly what a Director of Engineering should do. The risk you're trying to avoid (looking like you can't deliver) is actually higher if this surfaces later without your fingerprints on the solution.

**The third-party option deserves a real answer before you commit to anything.** Right now you're making decisions without knowing whether Okta/Auth0 could satisfy the customer. That's fixable in a day or two. What I'd prioritize this week:

1. **Find out what the customer actually needs.** Get someone (you, the account manager, the VP) on a call with the customer's IT contact. The question is: "We're evaluating implementation approaches — would a solution built on Okta/Auth0 work for your requirements, or do you need native?" This answer changes everything. If they don't care about native, option 3 might let you deliver Q2 without touching the migration at all.

2. **Get a rough scope on the third-party path.** Even a half-day engineering spike: what would it cost, how long to implement, what are the real integration risks? Don't let engineering resistance be the default answer without a real estimate.

3. **Get aligned with VP Sales before you go to the CEO.** Don't make this adversarial. Go to the VP with "I want to help you close this deal — I need us to go to the CEO together with a real plan, not a soft date." A joint approach is much stronger than escalating around them.

4. **Brief the CEO this week, with options.** Even if the options aren't fully evaluated, "here's the situation, here's what I'm looking at, here's what I need your input on" is a legitimate and strong position.

What's your access to the customer like — can you or someone on the account team get that conversation in the next few days?

## Turn 4

**User:**
I appreciate your honest read. It's clear and compelling. You make a strong case for why the current approach is flawed and what I need to do instead. You're right that I'm trying to avoid risk in the wrong way, and that I need to challenge my assumptions and test my options.

To answer your question, I think we have a good chance of getting that conversation with the customer. I have a good relationship with the account manager, and they know the customer's IT contact well. I can ask them to set up a call this week, or even join them on the call if they want me to. I'll also follow up with engineering and see if I can get a rough scope on the third-party option. I'll do my best to align with the VP Sales and get their buy-in for briefing the CEO. I agree that a joint approach is stronger than an individual one.

You've given me a lot to think about and act on. Thank you for your guidance and insight. This has been very helpful. I'll let you know how things go. Have a good day.

**Assistant:**
Good luck — you've got a clear path forward. A few things to capture before you go:I've captured everything — the problem, stakeholders, requirements, and the three open questions that most need answers this week (customer requirements, third-party scope, timeline flexibility). If you come back after those conversations, we can move into evaluating the actual solution paths with much better information.

Good luck with the calls. The fact that you're thinking this clearly about it puts you in a strong position.

## Turn 5

**User:**
Thank you again. I appreciate your support and encouragement. I'm glad I reached out to you. I'll be in touch soon. Take care.

**Assistant:**
Take care, Danielle. Come back once you've had those conversations — the picture will be a lot clearer.
