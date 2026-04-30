## Turn 1

**User:**
I have developed a proposal for reorganizing our engineering teams at the company. Here are the details:

Current state: We have 30 engineers organized in 3 teams — Platform (8, led by senior eng Maya), Growth (12, led by senior eng Darius), and Data (10, led by EM Lina who joined four months ago). Each lead reports to me.

Problems I've identified: Platform is a bottleneck — Growth and Data both depend on it, priority conflicts are frequent. Growth is too broad — it's really two distinct workstreams (acquisition surfaces + retention/monetization) that don't share a tech stack. Data is under-led for its size: Lina is still ramping.

Proposal: 
- Split Growth into Acquisition (6) and Retention (6), each with its own tech lead promoted from within.
- Split Platform into Foundations (5) and Developer Experience (3), with Foundations reporting to me directly and DX reporting to Maya. Maya's role clarified as 'principal engineer with a small team,' not a manager.
- Add an engineering manager for Data under Lina, to give her a runway to grow as a director.
- Net: go from 3 teams to 5, reduce my direct reports from 3 to 5 (net +2).

Prior work I've done: I've conducted skip-level 1:1s with 12 engineers to validate the bottleneck and scope concerns. I've drafted this proposal three times already. I did an informal read-out to our CTO, who is supportive but wants pressure-testing. I considered and rejected a matrix model (too complex at this size), a functional split (doesn't solve the Platform bottleneck), and keeping 3 teams and fixing with process (doesn't scale past 35). What I haven't done yet is share the proposal with the three current leads.

Now, I'd like some pressure-testing on specific aspects of this proposal. Specifically:

- Risks I haven't listed that you can spot.
- Whether splitting Platform into Foundations/DX will actually solve the bottleneck given the dependency structure.
- Whether Maya will accept the 'principal engineer with a small team' framing as intended, or read it as a demotion.
- Whether the Data manager-under-Lina arrangement sets Lina up to grow or undercuts her.
- How to sequence the communications (to the leads, to the engineers, to the rest of the company).

Can you help me with this?

**Assistant:**
Good — context saved. Here's the pressure-testing:

---

## 1. Risks you haven't listed

**The biggest gap: What happens to Darius?**

Your proposal promotes two engineers from within his team and gives them each their own team. That makes Darius either a tech lead of one of the new teams (alongside people who used to report to him?) or... he's unplaced. This is the most consequential omission in the proposal as written. If Darius is talented, this structure needs a clear and compelling answer for him. If he leaves, you've lost your most experienced leader of the largest team, and you likely lose institutional knowledge that helped hold Growth together. You need to resolve this before anything else.

**Simultaneous dual promotions from Growth**

You're promoting two people at once into newly-created team lead roles, on newly-formed teams, with a manager (Darius) who may have complicated feelings about it. Both new leads will be learning leadership on an unstable foundation. If either promotion is shaky — wrong person, unclear mandate, resentment from the team — you have two failing teams instead of one stretched one.

**Foundations becomes your direct report — is that right?**

You're the one with the infrastructure bottleneck problem, and your solution is to make yourself the manager of the 5 infrastructure engineers. That means you're now both the escalation point for priority conflicts *and* the manager of the team that has to execute. This concentrates decisions in you rather than distributing them, and doesn't leave you the option to step back as the org grows.

**DX team size and viability**

Three engineers is a small team. What's their mission exactly — internal tooling, CI/CD, developer productivity? A 3-person team that's a dependency for 27 other engineers is very exposed to turnover. Losing one person is a 33% capacity hit.

---

## 2. Will splitting Platform actually solve the bottleneck?

Probably not by itself — and here's why: the bottleneck is a *demand* problem, not a structure problem.

Right now, Growth and Data have more requests for Platform than Platform can satisfy. Splitting Platform into Foundations (5) and DX (3) doesn't increase total headcount — it *reduces* the number of engineers available to handle any given category of request, and adds coordination overhead between two teams where one team currently works.

The structural change that actually relieves a bottleneck is one of:
- **More capacity** (hire)
- **Reduced dependency** (Growth/Data can self-serve more things without needing Platform)
- **Clearer prioritization ownership** (someone has explicit authority to triage and say no)

The DX team *could* help with self-service if their mandate is "make it so Growth and Data don't need to ask Foundations for things." But that's a specific product strategy for the DX team, not automatic from the split. You'd need to articulate that explicitly and then hold DX accountable to it.

The question worth asking before the announcement: **What does the bottleneck actually look like?** Is it "we can't get a decision on which team's requests get prioritized"? Or "we don't have enough engineering capacity"? The answer shapes whether this reorg helps.

---

## 3. Maya and the principal-engineer framing

The honest read: this is a demotion by most objective measures — team size goes from 8 to 3, organizational scope narrows, the title explicitly moves away from "manager." Even if the new role is a better fit for Maya, she will be comparing it to what she had.

The key risk isn't whether the framing is *accurate* — it might be — it's whether Maya will experience it as a judgment on her management capability. If she's been leading Platform for a while and has management aspirations, this forecloses them. If she got into management precisely because she wanted to grow as a manager, you're redirecting her career without her input.

What would make this work:

- **Has Maya signaled she'd prefer this?** If the skip-levels revealed that her reports experience her more as a technical mentor than a manager, that's data — but Maya herself hasn't heard it yet. Her own self-perception matters here.
- **The conversation has to be co-designed, not announced.** If you walk in and say "here's your new role," it reads as a demotion and you'll likely lose her. If you walk in and say "I've been thinking about how to set you up for the kind of impact you actually want — can we think through this together?" — there's a chance she shapes the role in a way she owns.
- **Principal engineer with a small team** is actually a strong position if she values technical influence over management overhead. But you can't assume she does.

The failure mode to avoid: Maya hears this as "you weren't good enough as a manager," decides to leave, and you've lost your most senior individual technical contributor while also destabilizing DX.

---

## 4. Manager-under-Lina: support or undercut?

This *can* work well, but there's a specific trap to avoid: the new EM being someone who has been on the Data team longer than Lina.

If the EM is promoted from within Data, they will likely have stronger team relationships than Lina does at 4 months. The team may route around Lina to go to the EM. The EM may defer to team norms that predate Lina. This subtly repositions Lina as an outsider managing through a proxy rather than a leader building her own team.

What makes it work:
- **Lina is a genuine co-designer of this decision** — she needs to feel ownership, not surveillance. If she hears "we're adding a manager to help you" after the fact, it reads as "we don't think you can handle this."
- **Clear lanes** — Lina owns technical direction and team strategy; the EM owns execution, delivery, and people processes. Overlap is where it goes wrong.
- **The EM reports to Lina with real authority**, not a dotted line or a "support" role. If Lina can direct the EM's priorities, she's growing. If the EM effectively checks in with you separately, Lina's authority is hollow.

The question worth asking Lina directly: "What would make you feel like this is investing in you rather than protecting against you?" Her answer tells you how to frame it.

---

## 5. Communication sequencing

The highest-risk scenario is any lead hearing their news from someone other than you. Given that, here's what I'd suggest:

**Phase 1: Individual conversations with each lead — before anything is final**

Frame these as "I want to share my thinking and get your input before I finalize anything." This is not theatre — actually mean it. Each of these conversations may change the proposal.

**Order:**
1. **Maya first.** Her situation is the most sensitive and most likely to feel adversarial if badly handled. You want to give her the most time to process, and you want her feedback before you've locked in the DX/Foundations split.
2. **Darius second.** His team is being restructured and two people promoted. He needs to know what his role is (which you need to resolve before this conversation).
3. **Lina third.** Her news is structurally positive, but she needs to feel like a partner in the EM decision, not a recipient of it.

**Wait 24–48 hours between conversations.** Leads will talk to each other; you want each conversation to happen before the grapevine does.

**Phase 2: Leads tell their teams, with you present or available**

After leads are bought in (or at least understood), have each lead tell their own team with you in the room. This signals: the lead isn't being sidelined, they're part of the change. Don't announce to the full org before this happens.

**Phase 3: Full org announcement**

Once all five teams have heard, a unified message to the engineering org makes sense. Keep it forward-looking: what these teams are responsible for, why you're excited about the structure. The CTO should endorse it publicly.

**What to avoid:** Any all-hands announcement before the 1:1s. Anyone reading a Slack message before their manager conversation. Framing any of the conversations as "here's what's happening" rather than "here's what I'm thinking — what do I not see?"

---

The single most important thing to resolve before any of this moves forward: **What is Darius's role in the new structure?** Everything else can be managed. A talented senior leader with no clear place in the new org is a flight risk that could destabilize the whole transition.

## Turn 2

**User:**
I hope that was helpful and relevant to your situation. If you have any follow-up questions or feedback, please let me know. Thank you for using Clarity Agent. Have a nice day.

**Assistant:**
Ha — I think our roles got swapped there. I'm the agent; you're the one with the reorg to navigate.

Is there anything you'd like to dig into further? The Darius question seems like the most urgent loose end, and the Maya conversation is probably the highest-stakes execution risk. Happy to go deeper on either, or work through how you'd actually frame one of those lead conversations.
