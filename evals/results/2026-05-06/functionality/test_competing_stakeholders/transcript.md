## Turn 1

**User:**
Hey, I could use some help thinking through a situation I'm in the middle of. I'm a Director of Engineering at a ~200-person B2B SaaS company, and I've got a classic competing-priorities problem that's been grinding on me for three days.

Short version: our VP of Sales committed to a large enterprise customer that we'd ship an SSO and provisioning feature set in Q2 — without looping me in. That contract is worth about $1.2M ARR. My most senior lead says Q3 at earliest. And we're already mid-stream on a platform migration that was explicitly prioritized last quarter by our VP of Engineering.

I'm trying to figure out how to balance these competing needs without blowing something up. What's the best way to think through this?

**Assistant:**
This is a real situation that deserves careful thinking — let me capture what you've shared while I ask a few things that will sharpen the picture.

A couple of questions to get the most important context:

**On the timeline gap:** When your lead says "Q3 at earliest," does that mean early July or more like August-September? And is the Q2 deadline in the contract as a hard delivery date, or was it a verbal commitment from your VP of Sales?

**On the migration:** How far in are you — are you 20% done and flexible, or 80% done and stopping would be genuinely painful? And what breaks if it slips?

**On the org dynamics:** Does your VP of Engineering know about the sales commitment yet? And do you have a direct relationship with the VP of Sales, or does this need to go through your VP of Engineering?

The reason I ask: there are a few very different situations that look similar on the surface here. In one version, you're managing a scoping/negotiation problem with a path to a creative solution. In another, you're navigating a genuine political fire that needs to be escalated, not solved at your level.

## Turn 2

**User:**
Good questions. Let me fill in the gaps.

Q3 for Raj means August at the earliest if we pull some people — he said "Q3" but when I pushed him it was more like "not before August." The customer's deadline is end of June. The sales commitment was verbal, but the customer is treating it as real — their procurement cycle closes then.

On the migration: I'd say we're 30-35% in. Not trivial to pause, but not 80% done either. The thing that breaks if it slips is Data Retention and Growth Metering — both were waiting on this migration to even start. Those are things our VP of Engineering specifically cited when he prioritized the migration last quarter.

VP Engineering does know about the sales commitment — he's been in the same email threads I have. His position is basically "I'll back what you decide." Which is supportive in theory and not super helpful in practice. I do have a direct relationship with VP Sales, though it's been strained this week.

That last framing you offered — scoping problem vs. political fire — I think that's the right question actually. My instinct has been to treat it as the former and find a creative solution. But I'm starting to wonder.

**Assistant:**
Your instinct to reframe that question is right — and I think the honest answer is: **it's both, and you need to sequence them correctly.**

Here's the key thing the numbers tell you: the gap isn't weeks, it's months. End of June vs. August isn't a "crunch harder" problem — it's a calendar problem. No amount of creative scoping closes a 6-week gap on a feature set Raj already estimated *with* resource pulls. So the first conclusion is:

**You cannot engineer your way out of this.** The variables that actually matter — customer flexibility on timeline, customer flexibility on scope, whether VP Sales will renegotiate, whether there's a partial delivery that satisfies the procurement requirement — none of those are in your control.

The second thing that stands out: your VP of Engineering saying "I'll back what you decide" is well-meaning but it's putting you in a genuinely bad position. This decision involves a Sales commitment and an Engineering priority that *he* set. That's a VP-level tradeoff, not a Director-level one. If you make the wrong call — or even the right call that someone disagrees with later — you're exposed. That's not a fair position to be in.

So before you solve the technical problem, I think you need to answer one structural question: **Is the right move to own the decision, or to force it up?**

My read is you should force it up — but not by abdicating. The move is to go to your VP of Engineering and say: *"I need you and [VP Sales] in the same room. Here's exactly what's achievable by June 30, here's what August actually means, and here's what we lose in each scenario. I'll give you the options. You two need to make the call together."* That's not weakness — that's correctly routing a cross-functional business decision.

Before that conversation, though, there's one thing worth finding out fast: **what does the customer actually need SSO for?** Sometimes "we need SSO by June" means "our security review requires it." Sometimes it means "our IT admin will hate onboarding without it." Those have very different minimum viable answers. Does VP Sales have that context — or is that a conversation you could be part of?

## Turn 3

**User:**
The logic tracks, but "force it up" is where I get uncomfortable. I've been trying to handle this at my layer precisely because I don't want to be the person who drops a $1.2M problem on the CEO's desk because I couldn't figure it out. That feels like failure.

And VP Engineering saying "I'll back what you decide" — I hear you that it's not ideal, but I also took it as genuine. He's been around a long time. I don't think he's hanging me out to dry, I think he genuinely trusts me to work it.

But — the customer question is actually something I haven't dug into enough. VP Sales has been in "this is existential" mode and I've been reacting to that framing. I don't actually know what the customer's procurement requirement is underneath the headline ask. Like, does SAML alone satisfy their security review? Can they onboard manually for a quarter if roles come later? I don't know, and that feels like a gap.

I've been sitting on some scope-reduction options I haven't fully pressure-tested either. Ship SAML for Q2 and SCIM for Q3. Or basic SSO without fine-grained roles, if the contract language actually lets us defer that. I don't know if any of these would satisfy the customer, and I realize I've been treating that as an unknown instead of going to find out.

**Assistant:**
That's the right diagnosis — you've been managing the *perception* of the problem ("existential!") instead of the *substance* of it. And the customer requirements gap is exactly where to start. Let me also clarify what I meant by "force it up," because I think it landed wrong.

I wasn't suggesting dropping this on the CEO. I meant: don't make the final tradeoff call *alone* when it has VP-level consequences. Coming to your VP of Engineering with a proposal and saying "here's the path I'm recommending, I need your sign-off" is not failure — that's how this should work. The bad version is you quietly deciding to de-prioritize the migration and nobody at VP level explicitly blessed that tradeoff. Your VP saying "I trust you" doesn't protect you if that comes back later.

But — that's a later problem. Right now you've correctly identified that you're missing the foundation for *any* of the scope options. You can't evaluate SAML-only-for-Q2 until you know whether SAML satisfies the customer's actual requirement.

**Here's the sequence that makes sense to me:**

**Step 1 (next 24 hours): One focused conversation with VP Sales.** Not about timelines — about requirements. Specific questions to get answered:
- What does the customer's security review actually gate on? SAML alone, or does it require automated deprovisioning via SCIM?
- How big is their initial rollout? If it's 50 users, manual provisioning for a quarter is fine. If it's 5,000, it's not.
- What language is in the contract/SOW? "SSO and provisioning" or something more specific?
- Is there any flexibility if you can give them *something* concrete by June 30 — even a working SAML integration with SCIM on a committed Q3 date?

**Step 2 (in parallel or right after): Quick scope conversation with Raj.** Not "can we do it all," but specific variants: SAML only — what's the estimate? SAML + basic provisioning without fine-grained roles — what's the estimate? These are probably different answers than "the whole thing."

**Step 3: You'll know.** Either a path exists at your layer, or it doesn't and you go to VP Sales with a specific counter-proposal rather than a problem.

The point about VP Sales being in "existential" mode is worth holding onto. That framing may be accurate, or it may be VP Sales managing their own anxiety about the commitment they made. You won't know until you get under the headline ask.

What's your read on VP Sales — will they let you have that requirements conversation directly, or is this going to filter through them?

## Turn 4

**User:**
Okay, that reframe on "force it up" actually helps. Coming to VP Engineering with a recommendation and asking for sign-off — yes, that's different from what I was picturing. That I can do.

On VP Sales: yes, I can go directly. We have a working relationship, it's just been tense this week because he keeps framing everything as a crisis and I've been trying to pump the brakes. But he's not going to route me through VP Engineering. If I come to him with specific questions instead of another "here's why it's hard" conversation, I think he'll engage.

Honestly, your step 1 questions are almost exactly what I should have asked three days ago instead of getting pulled into the timeline fight. The SCIM deprovisioning one in particular — I have no idea whether their security review requires automated deprovisioning or whether that's a nice-to-have. That's a real gap.

The thing I'm still uncertain about: even if I do steps 1 and 2 and find a path, at some point VP Sales and VP Engineering are going to need to be aligned. If I bring them a phased proposal — SAML for Q2, SCIM for Q3 — VP Engineering still needs to bless de-prioritizing two weeks of migration work to make the Q2 part real. So I guess my question is, when does that conversation happen? Before I have the requirements clarity, or after?

**Assistant:**
After. Clearly after. Here's why:

Right now you don't have anything concrete to align on. If you bring VP Engineering in before steps 1 and 2, you're asking him to evaluate a hypothetical tradeoff — "should we pause some migration work to potentially do SAML for a customer who might be okay with that?" That's not a real ask. He can't meaningfully say yes or no, and you'll likely end up in another abstract discussion.

His "I'll back what you decide" is telling you something: he wants you to come back with a recommendation, not another status update. Come to him when you can say: *"Here's what I found out. SAML alone satisfies the customer's security review. Raj says six weeks with two engineers, and I've identified which two. That means the migration slips by two weeks on the data retention work. I'm recommending we take that tradeoff. I need your explicit sign-off."*

That's a 10-minute conversation and he'll say yes or no. You walk out with an answer.

The three-way alignment — you, VP Sales, VP Engineering — only needs to happen if there's a conflict that can't resolve at your layer. Which you won't know until you've done the discovery. Most likely it doesn't happen at all: VP Engineering blesses the tradeoff, you tell VP Sales what you can deliver and by when, VP Sales manages the customer.

**On urgency:** it's May 8. If SAML-only is even 4-5 weeks of work, you're making this decision on borrowed time. The discovery conversations — VP Sales and Raj — should happen in the next 48 hours, not next week.

One framing shift for the VP Sales conversation: don't walk in with scope options to negotiate. Walk in with questions. *"I want to find a path here, but I need to understand what actually matters to the customer before I can propose anything credible."* That repositions you from "Engineering pushing back" to "Engineering doing due diligence to solve this." Different dynamic entirely.

What's your calendar look like — can you get VP Sales tomorrow?

## Turn 5

**User:**
Yes, I can get him tomorrow morning. That's not the obstacle.

The framing shift you offered — questions, not options — that's actually the thing I most needed to hear. I've been going into every conversation in defense mode, explaining why the timeline doesn't work. That's the wrong posture and I've known it but haven't been able to get out of it.

Okay. So my week looks like: tomorrow, VP Sales with the requirements questions. Tomorrow afternoon or Monday, Raj with the specific variants. Then VP Engineering with a recommendation once I have real numbers.

The thing I want to make sure I'm not kidding myself about: is there a scenario where steps 1 and 2 don't produce a path — where even SAML alone is too much to do in 6 weeks, or the customer won't accept a phased approach — and then what? At some point this becomes a VP-level problem that has to go above me, right? Including potentially to the CEO if Sales and Engineering can't get aligned?

**Assistant:**
Yes, and you're right to not kid yourself. Let's name it clearly.

**The no-path scenarios:**

1. Raj comes back and says even SAML-only is 8-9 weeks — there's genuinely not enough runway regardless of scope.
2. The customer's security review requires automated deprovisioning, making SCIM non-deferrable.
3. Both things are technically achievable, but the migration cost is so high that VP Engineering won't bless the tradeoff.
4. You find a path, bring it to VP Sales, and the customer won't accept anything phased — they want the full commitment honored.

In any of these cases: yes, it becomes a VP-level problem. And yes, if VP Sales and VP Engineering can't align, it goes to the CEO.

**But here's the thing — that's not your failure.** The failure would be if you showed up to that conversation empty-handed. If you arrive having done the work — customer requirements understood, scope options with real estimates, a specific proposal, a clear articulation of what doesn't work and why — you're not dropping a problem on the CEO's desk. You're doing exactly what a Director should do: surfacing a decision that requires authority above your level, with all the information needed to make it.

The version that looks bad is "I've been going in circles for three weeks and I don't know what to do." The version that looks good is "I've pressure-tested every path, here's the one option that might work and what it costs, here's what happens in each scenario, and VP Sales and VP Engineering can't align — I need a call." Those are very different conversations.

There's also a reframe worth having on the CEO question specifically: **a $1.2M ARR commitment made without engineering input is already a VP-level problem.** It became one the moment VP Sales signed that deal. You didn't create this situation. You're trying to resolve it. If it ultimately requires executive arbitration, that's the natural consequence of how the commitment was made — not evidence that you failed to solve it.

Your plan for this week is right. Do the discovery. Come back with real numbers. Then you'll know which scenario you're in — and you'll know exactly what to do next in either case.

## Turn 6

**User:**
That last paragraph actually helps more than the rest of it put together. I've been carrying this like it's my fault to solve, and that's not quite right.

One thing I should probably admit: the CEO hasn't been briefed on any of this. Like, at all. I've been managing it at my layer specifically to avoid it becoming a CEO-level thing. If it does need to go there — which now I'm thinking it might — that's going to be a more complicated conversation because it'll feel like it came out of nowhere for him.

I don't know if that changes anything about the sequence you laid out, but it feels relevant.

**Assistant:**
It's relevant, but it doesn't change your sequence — it adds one thing to step 3.

Steps 1 and 2 are still exactly right. You don't have enough information to brief anyone usefully yet, including the CEO. A heads-up with no resolution path creates anxiety without helping anything.

What it changes: when you bring your recommendation to VP Engineering, you add one explicit thing to that conversation: *"He hasn't been briefed on any of this. If this needs to go up, I think we need a plan for that — whether that's a proactive heads-up from you now, or a joint conversation if it turns into an escalation."*

That's his call to make, not yours. VP Engineering has been in the email threads. This isn't a situation where you've been hiding something from your chain of command — you've been managing at your layer, appropriately, while your VP was aware. The CEO briefing is a VP-level decision about what to surface up. You surfacing it explicitly in your recommendation conversation is the right move; you going around VP Engineering to brief the CEO directly would not be.

The one thing I'd flag: the longer a significant situation stays invisible to the CEO, the worse the "it came out of nowhere" problem gets. If VP Engineering's response to your flag is "let's just see how the discovery goes first," that's probably fine — you've got a week before you have real information anyway. If his response is "I don't think we need to loop him in," that's worth a gentle pushback: a $1.2M commitment in question, 8 weeks from deadline, is exactly the kind of thing CEOs want early visibility on. A heads-up framed as "we're working on a path" is a very different conversation than an emergency briefing.

But that's his call. Your job is to surface it — once, clearly — and let him own it.

Does that feel like it resolves the concern, or is there something else about the CEO dynamic that's weighing on you?

## Turn 7

**User:**
No, that resolves it. "Surface it once, clearly, and let him own it" — I can do that. That's actually a relief to hear framed that way.

I came in this morning pretty tangled up in this, and I feel like I have an actual week in front of me now. Tomorrow VP Sales with the requirements questions, Raj with the specific scope variants, then VP Engineering with a real recommendation. And I stop managing this like it's my private problem to solve.

Thanks for not just handing me back a restatement of my options. I've been staring at those for three days.

**Assistant:**
Good luck tomorrow. You've got the right questions and the right posture — that's most of it.

One thing worth remembering when VP Sales does his "this is existential" framing: you're not there to push back on it, and you're not there to agree with it. You're there to find out what's actually true underneath it. That's a very stable place to operate from.

Come back if the discovery surfaces something unexpected. There may be more to think through once you have real numbers.Glad it helped. Good luck tomorrow.
