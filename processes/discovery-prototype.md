# Discovery Prototype

Test a specific hypothesis through minimal, focused implementation. Build just enough to answer one question, then return with findings.

## Overview

Sometimes during problem clarification, you identify an open question whose answer would change everything about the solution approach — and the fastest way to answer it is to try. That's what this process is for.

This is not solution brainstorming. You're not exploring the space of possible solutions. You're testing one specific hypothesis: "Does X actually work?" The prototype you build is disposable. Its only purpose is to produce a finding that resolves the question.

## When to Use This Process

Run this process when:

- An open question in `goal/open-questions.md` has strategy "prototyping"
- The question is about feasibility — "can this be done?" not "should this be done?"
- Building something small would answer the question faster than reasoning about it
- You know roughly what to try, but don't know if it works in practice

Don't use this for:

- Questions that can be answered by thinking or discussion (use problem-clarification instead)
- Questions that require gathering external information (use discovery-research instead)
- Building the actual solution (use solution-brainstorming instead)

## Inputs

Read these before starting:

- `.clarity-protocol/goal/open-questions.md` — The specific question you're testing
- `.clarity-protocol/goal/problem.md` — Context about what you're trying to achieve
- `.clarity-protocol/goal/stakeholders.md` — Who cares and why
- `.clarity-protocol/goal/requirements.md` — Constraints that might affect feasibility

Focus on the specific question. You need enough context to test it meaningfully, but don't try to absorb the entire project state — that's a sign you're drifting toward solution brainstorming.

## Process Steps

### Step 1: Understand the Question

Read the open question and make sure you understand exactly what's being asked. Restate it as a testable hypothesis:

> **Question**: "Can we achieve real-time event processing at our expected scale?"
>
> **Hypothesis**: "A system using [specific approach] can process 10k events/sec with <100ms latency on [specific infrastructure]."

If the question is too vague to form a hypothesis, sharpen it first. "Is this technically feasible?" isn't testable. "Can approach X handle constraint Y?" is.

### Step 2: Define the Experiment

Before building anything, define:

1. **What you're testing** — The specific hypothesis, in one sentence
2. **What success looks like** — A concrete, observable result that would confirm the hypothesis
3. **What failure looks like** — A concrete, observable result that would reject it
4. **What you're building** — The minimum implementation that would produce one of those results
5. **What you're NOT building** — Explicitly list what's out of scope (error handling, edge cases, production concerns, polish)

Show this to the user before proceeding. The experiment definition is a contract — it prevents scope creep and makes it clear when you're done.

> "Here's what I'm proposing to test:
>
> **Hypothesis**: [one sentence]
>
> **Success**: [observable result]
>
> **Failure**: [observable result]
>
> **Build**: [what we'll actually implement]
>
> **Not building**: [what we're skipping]
>
> Does this test the right thing?"

### Step 3: Scope Ruthlessly

This is the hardest part. The temptation to build "just a little more" is strong. Resist it.

Rules of thumb:

- If it doesn't directly contribute to testing the hypothesis, don't build it
- If the prototype needs error handling to test the hypothesis, add it. If it only needs error handling to be "good code," skip it.
- If you find yourself thinking about maintainability or extensibility, you've drifted — this is disposable
- If you realize the prototype is growing beyond what you scoped in Step 2, stop and reassess. Either the scope was wrong (update it) or you're drifting (cut back)
- A prototype that answers "no, this doesn't work" in 30 minutes is more valuable than one that answers "yes, sort of" in three days

### Step 4: Build or Design the Prototype

For software projects, this usually means writing code. For other kinds of projects, it might mean:

- A detailed design exercise that traces through specific scenarios
- A paper prototype or mockup that can be tested with users
- A spreadsheet model that tests numerical assumptions
- A thought experiment that follows the approach to its logical conclusions

Whatever form it takes, stay focused on producing the evidence you defined in Step 2.

As you build, notice things:

- **Surprises** — Anything you didn't expect. Even if it doesn't affect the hypothesis, note it.
- **New questions** — The prototype may reveal questions nobody thought to ask.
- **Assumptions** — Things you had to assume to make the prototype work. These are potential failure points for the real solution.
- **The wrong question** — Sometimes, partway through building, you realize the original question isn't the one that matters. This is a valuable finding. Stop and capture it rather than pressing on with a question that's lost its relevance.

### Step 5: Evaluate Findings

Compare results against the success/failure criteria from Step 2:

- **Clear success**: The hypothesis is confirmed. Record the evidence.
- **Clear failure**: The hypothesis is rejected. Record what went wrong and why.
- **Ambiguous**: The results don't clearly confirm or reject. This usually means either the experiment was poorly scoped (the criteria weren't sharp enough) or the answer is genuinely "it depends." Record what you learned and what would resolve the ambiguity.
- **Wrong question**: You discovered that the original question isn't the right one. Record what the right question is.

For each outcome, ask: "What does this mean for the solution approach?" The finding only matters in context of the project.

### Step 6: Record and Return

Update `.clarity-protocol/goal/open-questions.md`:

- If the question is conclusively answered, **move it** to `goal/resolved-questions.md` with its findings and resolution (see problem-clarification.md for the resolved question format)
- If the answer is ambiguous, keep it in `open-questions.md` as `investigating` and update **Findings** with what you learned
- If the prototype surfaced new questions, add them as new entries in `open-questions.md`

If findings are extensive enough that they don't fit in a few lines, create a detailed document at `.clarity-protocol/goal/discovery/` and link to it from the Findings field:

```markdown
**Findings:** Real-time processing works at 5k events/sec but degrades at 8k+. See [detailed findings](discovery/prototype-q1-realtime-findings.md) for benchmarks and analysis.
```

Record the updated state:

```bash
python -m clarity_agent.protocol.packet_status . --record goal/open-questions.md
```

If the findings change the problem understanding, update `goal/problem.md` too — and record it. This will naturally trigger staleness on downstream documents.

Then return to **clarity-agent** for reassessment. The resolved (or updated) question may unblock other work, surface new questions, or lead to decisions that need guidance.

## Sub-Processes

This process might naturally lead to:

- **decision-guidance.md** — If the findings create a fork between approaches ("It works, but only with tradeoff X — is that acceptable?")
- **problem-clarification.md** — If the findings change the problem itself or surface new questions that need the "thinking" strategy
- **solution-brainstorming.md** — If the question is resolved and it's time to design the actual solution

## Outputs and Updates

This process updates:

- `.clarity-protocol/goal/open-questions.md` — Updated findings, or removal of resolved questions
- `.clarity-protocol/goal/resolved-questions.md` — Resolved questions moved here with findings and resolution
- Optionally: `.clarity-protocol/goal/discovery/` — Detailed findings documents (not tracked in staleness graph)
- Optionally: `.clarity-protocol/goal/problem.md` — If findings change the problem understanding

## Common Pitfalls

**Pitfall: Building a solution instead of a prototype**

If you're thinking about architecture, maintainability, or edge cases, you've drifted. A prototype that answers "no" is just as valuable as one that answers "yes." The point is the finding, not the artifact.

**Pitfall: Moving the goalposts**

If the original success criteria were "process 10k events/sec" and the prototype achieves 3k, that's a failure — which is useful information. Don't redefine success to match what the prototype achieved. Record the actual result and let the team decide what it means.

**Pitfall: Not defining failure upfront**

Without clear failure criteria, every prototype "sort of works." Define what would make you abandon this approach *before* you start building.

**Pitfall: Keeping the prototype**

The prototype is disposable. If the finding is positive and you proceed to solution brainstorming, start fresh. The prototype was optimized for speed of learning, not quality of implementation. Carrying it forward creates technical debt from day one.

**Pitfall: Prototyping when you should be thinking**

Not every question needs a prototype. If the answer is reachable through careful reasoning about known constraints, that's faster and cheaper. Only prototype when the question is genuinely empirical — when you need to *try* to find out.

## Next Steps

After recording findings, run **clarity-agent** to reassess the project state. The clarity-agent will check whether the question is resolved, whether new questions emerged, and what should happen next.
