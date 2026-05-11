## Turn 1

**User:**
Hey — I'm hoping you can help me think through a process problem on my team.

I'm a senior PM running a cross-functional squad of eight engineers and a designer. Over the last quarter I've been picking up signals that our velocity is declining — stakeholders are complaining about shipping pace, and my own read of our sprint reviews is that we're closing less than we used to. I have some candidate interventions in mind but I want to be more deliberate about picking the right one rather than just trying things.

Can you help me design an intervention, or at least think through what's driving this so I'm targeting the right thing?

**Assistant:**
Good problem to think through carefully — picking the wrong intervention for a velocity issue can easily make things worse. Let me capture what you've described while we talk.Two things would help me orient quickly:

**First** — what are the candidate interventions you already have in mind? That tells me a lot about what hypotheses you're already working with.

**Second** — has anything concrete changed in the last quarter that roughly coincides with the slowdown? New team members, a new stakeholder dynamic, a shift in the type of work, a process change, or something else?

## Turn 2

**User:**
Sure. My candidate interventions are: tighter definition of ready before stories enter the sprint, a stricter WIP limit to reduce context-switching, more focused retros (ours have been drifting), and more aggressive story breakdown — I suspect some of our stories are too large and that's slowing completion.

On your second question — honestly, nothing material that I've identified. No new EM, no major tooling changes, no new high-pressure stakeholder that wasn't there before, no acute cross-team dependency issues. That's partly why I'm here — the environment hasn't obviously changed, so I'm trying to figure out what's actually going on before I just start pulling levers.

**Assistant:**
That's actually a useful signal in itself — when nothing obvious has changed but velocity drifts down, it usually points to gradual accumulation rather than a discrete event. Slow debt, scope creep in story sizing, process drift, or something quietly eroding flow state.

Your four interventions are interesting because they map to different root causes. Before I help you pick, one diagnostic question:

**What does the pattern of incomplete work look like?** Specifically — when the sprint ends with less closed than expected, is it typically a few large stories that carried over (work in progress, just not done), or are stories completing but fewer were attempted in the first place, or something else like stories frequently getting blocked or bouncing back from review?

That pattern tends to point clearly at one of your hypotheses. "Carried over" → story size or DoR. "Blocked/bounced" → upstream clarity or dependencies. "Fewer attempted" → WIP and context-switching.

## Turn 3

**User:**
It's more the first and third combined — stories are carrying over, and fewer are getting completed per sprint. Not a lot of blocking in the traditional sense (no obvious external dependencies piling up), but individual stories seem to be taking longer to move through the board than they used to. Which is part of why "story size" and "definition of ready" are high on my list — my instinct is that stories are getting started before they're really ready, which leads to mid-sprint clarification work and slower progress.

Do you want me to share the actual numbers I've been tracking? I have sprint-by-sprint data going back to Q1.

**Assistant:**
Yes, share it — actual data will help a lot. The pattern you're describing (carries + slower cycle time, no external blocking) is consistent with your DoR hypothesis, but the numbers could reveal whether there's an inflection point, whether story sizes have grown, or whether the slowdown is concentrated in certain types of work.

While you pull that together, let me write down what we've established so far.Go ahead and paste the data — raw numbers are fine.

## Turn 4

**User:**
Here's what I have:

- **Q1:** 6 sprints, averaging **38 points/sprint**, **9 stories/sprint**, average **4 days in-progress** per shipped story
- **Q2 (5 sprints in):** averaging **43 points/sprint**, **7 stories/sprint**, average **7 days in-progress** per shipped story

The points-per-sprint number is actually slightly up, but my read is that we're shipping fewer stories and each one is taking longer — which feels like declining velocity to me, even if the raw point count looks okay.

**Assistant:**
This data is actually quite diagnostic. Let me show you what it reveals:

**Q1 → Q2 shifts:**
- Average story size: ~4.2 pts → ~6.1 pts **(+45%)**
- Cycle time per story: 4 days → 7 days **(+75%)**
- Stories shipped: 9 → 7 **(−22%)**

The points-per-sprint being up isn't reassuring — it's explained entirely by story size inflation. The team isn't more productive; they're working the same capacity but on fewer, larger, slower stories. Your instinct is right, and the data is more specific than "velocity is declining" — the unit of work itself has quietly grown by nearly half in one quarter.

This points pretty clearly at **story breakdown + DoR** as the primary intervention, not WIP limits. The 7-day average cycle time is a symptom of stories entering the sprint too large and/or under-specified — not primarily of people juggling too many things at once.

The retro drift matters here too, but as a *maintenance problem* rather than a root cause: if retros were working well, the team likely would have caught and named this drift themselves. The retro fix preserves your ability to self-correct going forward.

One question before I'd feel confident in that diagnosis: **has the nature of the work actually gotten more complex this quarter**, or does this feel like a process drift — stories that could be broken down aren't being broken down? Those look identical in the data but call for slightly different interventions.

## Turn 5

**User:**
Okay, that reframe is interesting — I hadn't done that math explicitly. If points-per-story went from ~4 to ~6, that does explain the arithmetic. But I want to push back slightly: the lived experience on the team still *feels* like slowdown, not just "we're taking on harder work." Stakeholders aren't saying "you're shipping ambitious things slowly," they're saying "where is the output."

That said — to your question about complexity vs. process drift: if I'm being honest, I think it's drift. Backlog grooming meetings have been running long lately, and I've noticed stories have been harder to write. We've been struggling to get acceptance criteria nailed down before sprint start. That's not new domain complexity — that's us not being disciplined about breaking things down before they hit the board.

So I think you're right that the story breakdown + DoR intervention is the right primary lever. What does that actually look like in practice — are we talking about a sizing rule, a checklist, something structural in grooming?

**Assistant:**
Good — that confirmation matters. "Hard to write AC" and "grooming running long" are the process fingerprints of stories arriving at the board too raw.

Here's what I'd actually build:

**The core mechanism: a DoR checklist with a real gate**

Four items — a story isn't sprint-eligible unless:
1. Acceptance criteria written and agreed (not "TBD")
2. Estimated by the team
3. Design resolved (or explicitly out of scope)
4. No open questions that would block starting

The gate has to be real. "We'll figure it out in sprint" needs to become a planning failure, not a norm. Sprint planning becomes the enforcement point: if a story fails DoR, it goes back, full stop.

**The structural fix for grooming**

Your grooming running long is probably because stories are being *written and refined* by the full team in real time, which is expensive. Split the work:
- **PM/tech lead prep** (before grooming): break raw epics into candidate stories, draft AC
- **Team grooming** (30–45 min): validate DoR, estimate, flag gaps

This front-loads the breakdown work where it belongs — with you and whoever owns technical scoping — so the team's time is spent on estimation and review, not discovery.

**Size cap as a forcing function**

A hard rule: no story above 5 points enters the sprint. Stories estimated above that get broken down at grooming, not during the sprint. This makes size drift immediately visible rather than invisible.

**Retros as maintenance**

Time-box to 45 minutes, require one concrete action item per retro with an owner and a "we'll check this next sprint" commitment. The goal isn't more retros — it's closing the loop.

---

Before you commit to this, two things worth thinking through: **who owns the pre-grooming prep work** (this only works if someone is doing the upstream breakdown reliably), and **how you sequence the rollout** (introducing DoR enforcement abruptly when the backlog is already raw can cause a sprint to feel starved). Want to work through either of those?

## Turn 6

**User:**
Both of those are worth working through. On ownership: I'd take the pre-grooming breakdown work myself in partnership with our tech lead. That's actually closer to how we should have been operating — I've been letting too much of the story-writing happen in the room. So that's a structural fix I can make without it being a political conversation.

The sequencing concern is the one I'm more worried about. If I enforce DoR strictly starting next sprint, a meaningful chunk of our current backlog won't qualify — and I'd rather not have a sprint that looks starved from the outside while we're already getting pressure on pace. What does a sensible ramp look like? I'm thinking maybe a softer version first — flag stories that fail DoR, treat it as a warning rather than a hard gate, and move to full enforcement a sprint or two later once we've had time to prep the backlog. But I'm not sure if that just kicks the can.

**Assistant:**
Your instinct is right to be suspicious of the soft version — flagging without gating rarely changes behavior because the escape valve is still open. People will still negotiate stories through at planning, and the grooming dynamic won't actually shift.

Here's a ramp that avoids both problems:

**Sprint N (this sprint):** Announce the change. Tell the team that DoR will be a hard gate starting Sprint N+2. This creates urgency without immediate disruption. Simultaneously, you and your tech lead start the pre-grooming work — the goal is to have the top 10–12 backlog items DoR-ready before N+2.

**Sprint N+1:** Run planning with a soft checkpoint — any story that doesn't meet DoR gets flagged *and* immediately handed back to you for prep before next planning. Stories that fail don't enter the sprint, but you have a prep session within the sprint to fix them. This is different from "just a warning" — there's a real consequence (the story doesn't enter) but you're doing the remediation work in parallel rather than leaving the sprint starved.

**Sprint N+2:** Hard gate, full enforcement.

The key difference from what you described: the remediation work happens during the ramp period, not after. By N+2 your backlog should be meaningfully cleaner.

On the optics concern — I'd actually flip the framing with stakeholders proactively. Something like: *"We've identified that we've been starting work before it's fully defined, which is why cycle times have grown. For the next sprint you'll see a slightly smaller intake, but you'll see more stories close cleanly."* That narrative is more defensible than the current situation where stories silently carry over sprint to sprint.

Does that timeline feel workable, or is there a constraint on how quickly you need to be seen as moving?

## Turn 7

**User:**
That timeline is workable. We're mid-sprint right now, so N+2 is about three weeks out — that's enough runway to clean up the backlog without it feeling like an indefinite delay on the change.

And I like flipping the stakeholder narrative. The "stories carrying over silently" framing is exactly what's been eroding trust, and naming the mechanism proactively is better than waiting for the question.

One more thing I want to nail down before I take this back to my team: how do I know if it's working? What metrics should I be watching over the next two or three sprints to confirm the intervention is actually fixing the root cause rather than just making planning feel more organized?

**Assistant:**
Three metrics, in priority order:

**1. Cycle time per shipped story** — this is your primary signal. Your baseline is ~7 days. If the intervention is working, you should see this trending back toward 4–5 days by sprint N+3. It's the most direct measure of whether stories are moving through the board more cleanly. If cycle time doesn't improve, DoR enforcement alone isn't the fix — something else is slowing stories down (tech debt, actual complexity, a bottleneck in review/QA).

**2. Sprint completion rate** — stories closed vs. stories started within the sprint. You don't have this explicitly in your current data, but it's worth tracking from here. A healthy team with good DoR should be completing 85–90%+ of what they start. If carryover stays high even as cycle time improves, your stories are still too large on average.

**3. Average story size at planning** — track points-per-story at the time stories enter the sprint, not at the time they're estimated. You want this trending back from ~6 toward ~4. This is your leading indicator: if story size at intake is shrinking, the upstream prep work is happening. If it isn't, you're enforcing the gate but not doing the breakdown work.

**What "not working" looks like:** Cycle time stays elevated despite DoR enforcement. That's the signal to look for something the data isn't showing — tech debt accumulation, a quiet morale issue, a design handoff gap. Don't double down on process tightening if cycle time doesn't move; go investigate qualitatively.

**One to watch out for:** If sprint point totals drop sharply in N+1, don't panic — that's the backlog cleanup in action, not the team slowing down. The story count and cycle time numbers matter more than points for the next month.

---

You have a solid plan. Want me to write this up as a concise summary you can take into the team conversation, or capture the intervention design in the protocol so you have it for reference?

## Turn 8

**User:**
This is exactly what I needed. The metrics framing is useful — cycle time as primary, story size at planning as the leading indicator. That gives me something concrete to report back to stakeholders instead of "trust the process."

Yes, a concise written summary would be helpful — something I can share with my tech lead as context before we align on the rollout. Keep it tight; I want it to be something we can read in two minutes, not a document we have to process.

**Assistant:**
Here's the summary — copy/paste ready:

---

**Velocity Intervention: Diagnosis & Plan**

**What the data shows.** Stories per sprint dropped from 9 to 7, average story size grew from ~4 to ~6 points, and average cycle time nearly doubled (4 → 7 days). Points per sprint ticked up slightly — that's explained by story inflation, not higher output. The pattern is process drift: stories are entering sprints before they're properly defined, causing mid-sprint clarification work and slower board movement. No external changes triggered this.

**The intervention.** Two changes, linked:

*Definition of Ready (DoR) enforcement.* A story is sprint-eligible only when it has written acceptance criteria, a team estimate, design resolved, and no open blocking questions. Stories that fail DoR at planning go back — they don't enter the sprint.

*Pre-grooming prep.* PM + tech lead do story breakdown and AC drafting before grooming. Grooming becomes estimation and validation, not in-room discovery. This is what fixes the root cause.

**Rollout (three weeks).** This sprint: announce the change, begin backlog prep immediately, target the top 10–12 items DoR-ready before N+2. Sprint N+1: soft gate — stories that fail DoR don't enter but get prepped for N+2. Sprint N+2: hard gate, full enforcement.

**Stakeholder framing.** *"We identified that we've been starting work before it's fully defined — that's what's been causing stories to carry over silently. For one sprint you'll see slightly smaller intake; after that, stories complete more reliably."*

**How we'll know it's working.** Three numbers, sprint over sprint:
- **Cycle time per shipped story** (primary): ~7 days now, target 4–5 by sprint N+3
- **Sprint completion rate**: stories closed / started in sprint; target 85%+
- **Avg story size at planning** (leading indicator): ~6 pts now, target ~4

If cycle time stays elevated after two sprints of enforcement, DoR isn't the fix — investigate qualitatively.

---

That's saved to the protocol as well if you need to come back to it.
