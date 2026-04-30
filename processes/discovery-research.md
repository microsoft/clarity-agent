# Discovery Research

Design and execute a research program to answer questions that can't be resolved by thinking or prototyping alone. Reduce uncertainty through structured investigation.

## Overview

Some open questions require gathering information that nobody currently has. Maybe the answer exists in the world but hasn't been collected — user behavior data, competitive analysis, expert knowledge, published research. Maybe the answer requires running experiments. Either way, reasoning alone won't get you there.

This process helps design a research program: what questions to investigate, what evidence would be convincing, what methods to use, and how to sequence the work so you learn the most important things first.

## When to Use This Process

Run this process when:

- An open question in `goal/open-questions.md` has strategy "research"
- The answer requires gathering information from outside the team's current knowledge
- The question is too complex or uncertain for a single prototype to resolve
- Multiple sub-questions need to be investigated, potentially in different ways

Don't use this for:

- Questions answerable through deeper discussion (use problem-clarification instead)
- Questions where the fastest path is to just build something and see if it works (use discovery-prototype instead)
- Designing the actual solution (use solution-brainstorming instead)

## Inputs

Read these before starting:

- `.clarity-protocol/goal/open-questions.md` — The specific question(s) you're investigating
- `.clarity-protocol/goal/problem.md` — What you're ultimately trying to achieve
- `.clarity-protocol/goal/stakeholders.md` — Who cares and why (may inform what counts as evidence)
- `.clarity-protocol/goal/requirements.md` — Constraints that bound the solution space

## Process Steps

### Step 1: Understand What You Don't Know

Read the open question and characterize the uncertainty:

- **Factual uncertainty**: "Does X exist? Is Y true?" — The answer is out there, we just don't have it.
- **Empirical uncertainty**: "What happens when we do X?" — The answer requires observation or experimentation.
- **Preference uncertainty**: "What do users actually want?" — The answer lives in other people's heads.
- **Structural uncertainty**: "How do these pieces fit together?" — The answer requires synthesizing multiple inputs.

Different types of uncertainty call for different investigation methods. Knowing which type you're dealing with prevents mismatched methods (e.g., running user interviews to answer a factual question, or doing literature review to answer a preference question).

### Step 2: Decompose Into Sub-Questions

Most research questions are composites. Break them down:

> **Main question**: "Can we build a recommendation system that users trust?"
>
> **Sub-questions**:
> 1. What makes users trust or distrust recommendations? (preference uncertainty)
> 2. What recommendation approaches exist and how do they perform? (factual uncertainty)
> 3. Can we achieve acceptable accuracy with our data? (empirical uncertainty)
> 4. How do users react to recommendations that are transparent vs. opaque? (preference uncertainty)

For each sub-question, note:

- What type of uncertainty it represents
- What answering it would tell you about the main question
- Whether it depends on answers to other sub-questions

Some sub-questions may be independent (answerable in any order), while others form chains (question B only makes sense once question A is answered). This matters for sequencing.

### Step 3: Define Evidence Thresholds

For each sub-question, define what "good enough" evidence looks like. Research can expand indefinitely — you need to know when to stop.

Ask:

- "What result would make me confident enough to proceed?"
- "What result would make me confident enough to abandon this direction?"
- "What result would leave me uncertain and requiring more investigation?"

Be specific:

> **Sub-question**: "Can we achieve acceptable accuracy with our data?"
>
> **Proceed**: Accuracy >80% on our benchmark dataset with <1 week of tuning
>
> **Abandon**: Accuracy <60% even with significant tuning effort
>
> **Uncertain**: Accuracy 60-80% — would need user testing to know if it's "good enough"

Evidence thresholds prevent two common failure modes: stopping too early (before you've learned enough to decide) and stopping too late (continuing to gather evidence when you already have enough).

### Step 4: Design Investigations

For each sub-question, choose an investigation method that matches the uncertainty type:

**For factual uncertainty:**

- Literature review — What's already known? Published research, blog posts, documentation.
- Competitive analysis — How have others approached this? What can you learn from their results?
- Expert consultation — Who knows about this? What can they tell you?

**For empirical uncertainty:**

- Controlled experiments — Change one variable, measure the result.
- Data analysis — What do existing datasets tell you?
- Proof-of-concept — Build the smallest thing that would generate evidence (this overlaps with discovery-prototype; if the sub-question is simple enough, consider switching to that process).

**For preference uncertainty:**

- User interviews — Ask people what they want, but more importantly, watch what they do.
- Surveys — Useful for breadth, less useful for depth.
- A/B testing — Let users choose and measure what they actually prefer.
- Observation — Watch people use existing solutions and note friction, workarounds, and complaints.

**For structural uncertainty:**

- Synthesis workshops — Bring together what's known from different domains.
- System modeling — Map the components and their interactions.
- Scenario analysis — Trace through specific cases to see how the pieces connect.

For each investigation, define:

- **Method**: What you'll do
- **Inputs**: What you need to start (data, access, participants, etc.)
- **Expected output**: What the investigation will produce
- **Effort estimate**: Rough sense of scale (hours, days, weeks)
- **Evidence threshold**: When this investigation is done (from Step 3)

### Step 5: Sequence the Work

Order investigations to maximize learning and minimize waste:

1. **Cheapest disqualifiers first.** If a 2-hour literature review could reveal that the approach is known to be infeasible, do that before a 2-week experiment.

2. **Dependencies before dependents.** If sub-question B only matters when sub-question A has a positive result, answer A first.

3. **Independent investigations in parallel.** If sub-questions are unrelated, pursue them simultaneously when resources allow.

4. **Decision points between steps.** After each investigation, explicitly decide whether to continue, pivot, or stop. Don't auto-advance to the next investigation — assess whether it's still worth pursuing given what you've learned.

Present the sequence as a plan:

> **Phase 1** (can run in parallel):
> - Literature review on recommendation trust (1-2 days)
> - Survey of existing recommendation approaches (1 day)
>
> **Decision point**: Do viable approaches exist? If not, rethink the direction.
>
> **Phase 2** (after Phase 1):
> - Proof-of-concept with top 2 approaches using our data (1 week)
>
> **Decision point**: Does accuracy meet the "proceed" threshold?
>
> **Phase 3** (if Phase 2 is promising):
> - User interviews on trust and transparency preferences (1 week)

### Step 6: Execute and Record Incrementally

As each investigation completes, update `goal/open-questions.md` immediately:

- Update **Findings** with what you learned — specific evidence, not just conclusions
- If a sub-question is resolved, note it
- If a finding changes the research plan (makes a later investigation unnecessary, or reveals a new question), note that too

Don't wait until all investigations are done to record findings. Incremental updates ensure nothing is lost and let the team track progress.

After each decision point, reassess:

- Has the main question been answered (even partially)?
- Are the remaining investigations still worth pursuing?
- Have new questions emerged that should be added to the plan?
- Should any investigation's evidence threshold be adjusted based on what you've learned?

### Step 7: Synthesize and Return

When the research program is complete (or when you've hit enough evidence thresholds to answer the main question), synthesize:

1. **Answer the question** — What did you learn? Be specific about the evidence.
2. **Note confidence level** — How confident are you in the answer? What would change your mind?
3. **Surface implications** — What does this mean for the solution approach?
4. **Flag new questions** — Did the research reveal new unknowns?

Update `.clarity-protocol/goal/open-questions.md`:

- If the question is conclusively answered, **move it** to `goal/resolved-questions.md` with its findings and resolution (see problem-clarification.md for the resolved question format)
- If not conclusive, update the **Strategy** if the question needs a different approach, and update **Findings** with the synthesis
- Add any new questions as new entries in `open-questions.md`

If findings are extensive, create a detailed document at `.clarity-protocol/goal/discovery/` and link to it:

```markdown
**Findings:** Users trust transparent recommendations 2:1 over opaque ones. Accuracy of 78% is achievable with approach B. See [detailed findings](discovery/research-q2-recommendation-trust.md) for full analysis.
```

Record the updated state:

```bash
python -m clarity_agent.protocol.packet_status . --record goal/open-questions.md
```

Then return to **clarity-agent** for reassessment.

## Sub-Processes

This process might naturally lead to:

- **discovery-prototype.md** — If a sub-question is best answered by building something small
- **decision-guidance.md** — If findings create a fork between approaches that requires careful tradeoff analysis
- **problem-clarification.md** — If findings change the problem itself or surface questions that need the "thinking" strategy
- **solution-brainstorming.md** — If the question is resolved and it's time to design the actual solution

## Outputs and Updates

This process updates:

- `.clarity-protocol/goal/open-questions.md` — Updated findings, or removal of resolved questions (updated incrementally)
- `.clarity-protocol/goal/resolved-questions.md` — Resolved questions moved here with findings and resolution
- Optionally: `.clarity-protocol/goal/discovery/` — Detailed research findings (not tracked in staleness graph)
- Optionally: `.clarity-protocol/goal/problem.md` — If findings change the problem understanding

## Common Pitfalls

**Pitfall: Researching instead of deciding**

Research reduces uncertainty, but at some point you know enough to decide. If you keep designing more investigations when you already have a clear direction, you're procrastinating on the decision. Use the evidence thresholds from Step 3 to recognize when you're done.

**Pitfall: Skipping evidence thresholds**

Without explicit thresholds, research has no stopping condition. Every finding generates new questions, and you never feel "certain enough." Define what "good enough" looks like before you start, and stick to it unless circumstances genuinely change.

**Pitfall: All investigation, no synthesis**

Raw findings aren't useful until they're connected to the question. After each investigation, don't just record what you found — explain what it means for the main question. If you can't, the investigation may not have been well-targeted.

**Pitfall: Ignoring negative results**

A finding of "this approach doesn't work" or "users don't care about this feature" is just as valuable as a positive result. Don't treat negative findings as failures to be explained away — treat them as information that changes the direction.

**Pitfall: Researching what you could prototype**

If the fastest way to answer a sub-question is to build something small and test it, switch to discovery-prototype for that sub-question. Research is for when you need to gather information; prototyping is for when you need to generate it.

## Next Steps

After recording findings, run **clarity-agent** to reassess the project state. Resolved questions may unblock solution brainstorming, reveal new questions, or trigger decisions that need guidance.
