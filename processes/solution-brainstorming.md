# Solution Brainstorming

Explore and develop a solution approach that satisfies the problem, stakeholders, and requirements — and that can actually be built, maintained, and managed in practice.

## Overview

You're already good at brainstorming solutions. This process doesn't prescribe how to do that — instead, it reminds you of what to ground your thinking in, what to watch for, and when to involve the user.

The goal is a solution approach that's clear enough to drive architecture and implementation. Along the way, you should be noticing things: edge cases the requirements didn't anticipate, failure modes that emerge as the design takes shape, architectural constraints that narrow the option space. These observations are valuable — capture them even when they go beyond "what's the solution?"

## When to Use This Process

Run this process when:

- Problem clarification is done and you're ready to explore how to solve it
- The current solution isn't working and needs rethinking
- Requirements have changed enough that the solution needs revisiting

**Variant: rapid experimentation framing.** If `goal/open-questions.md` indicates the project is in an exploratory phase — pervasive uncertainty about what users need, rather than specific answerable questions — frame this process around building experimentation infrastructure rather than a final solution. The goal shifts from "find the right solution" to "build a system that makes it cheap and fast to try many solutions." Prioritize flexibility, quick iteration, and instrumentation for learning over optimality for any single approach.

## Inputs

Ground your thinking in:

- `.clarity-protocol/goal/problem.md` — The problem you're solving
- `.clarity-protocol/goal/stakeholders.md` — Who cares and what they need
- `.clarity-protocol/goal/requirements.md` — What any solution must provide
- `.clarity-protocol/notes.md` — Guiding principles and any items tagged `[for: solution-brainstorming]`

If the goal documents are missing or stale, go back to **problem-clarification** first. A solution without a clear problem is guesswork.

## What to Keep in Mind

### The solution has to become real

A solution isn't just an idea — it has to lead to an architecture that someone can implement, maintain, and operate. As you brainstorm, keep one eye on:

- **Implementability**: Can this actually be built with reasonable effort? Are there parts that sound elegant but would be nightmarish to implement?
- **Maintainability**: Will someone be able to understand and modify this in six months? Does it create ongoing burdens?
- **Manageability**: Can this be deployed, monitored, and operated? What does the day-to-day look like?

You don't need to solve these fully — that's what architecture design is for — but a solution that's fundamentally unimplementable or unmaintainable isn't a real solution, and you should notice that early.

### Ask the user when it matters

Use your judgment freely, but bring the user in when:

- **Genuine forks exist**: Two approaches both satisfy the requirements but lead to materially different systems. The user's context (team, timeline, preferences) is the tiebreaker, not your guess.
- **Edge cases surface**: Solution design often reveals scenarios the requirements didn't anticipate. When you notice these, flag them — they're valuable discoveries, not distractions.
- **Uncertainty is real**: If you're unsure whether an assumption holds, ask rather than guess. A quick question now prevents a wrong turn that compounds.

Don't ask about things you can reasonably decide yourself. The user wants a thoughtful partner, not a system that needs approval at every step.

### Start noticing failures and architecture early

Solution brainstorming is where failure modes and architectural constraints first start to become visible. You don't need to do formal failure analysis or architecture design yet, but as you think through approaches, you'll naturally notice things like:

- "This approach is elegant, but if [X] fails, the consequences are severe"
- "This requires [Y] to be highly available — that's a real architectural constraint"
- "Users could easily misunderstand [Z], which would lead to data loss"

Capture these observations. They're seeds for later processes — or reasons to prefer one approach over another right now.

## Outputs

Update `.clarity-protocol/solution/solution.md` with:

- The chosen approach and why it fits
- Key design decisions within the approach and their rationale
- What alternatives were considered and why they were set aside
- Open questions, risks, or concerns worth tracking
- Any failure modes, edge cases, or architectural observations that surfaced during brainstorming

The last point is important — insights that emerge during solution brainstorming shouldn't be lost just because they belong to a "different process." Write them down where they'll be found: note failure concerns in the solution doc, flag them for failure analysis, mention architectural constraints for architecture design.

Also update `.clarity-protocol/summary.md` — now that there's a solution, the summary should tell the full story: the problem that sparked the project *and* what you're building to solve it. Write it conversationally, like you're telling a smart friend about something you're excited to work on. A few short paragraphs — enough to make someone care, not enough to bore them. If it reads like a technical spec with bullet points, rewrite it until it sounds like a person.

Also write or update `.clarity-protocol/solution/solution-summary.md` — a short (two pages maximum) summary of what we're building, aimed at someone who has read problem.md and asks "so what's your plan?" It should capture:

- What we're building
- What the experience is like — walk the reader through what it feels like to use the system, concretely enough that they can picture it
- How it addresses the problem
- Nonobvious architectural or design choices that required nontrivial discussion to converge on
- Key design elements that address important failure modes, especially cross-cutting patterns from the failure analysis

This is the short answer; solution.md and architecture.md are the details.

After writing, record the updated document state so the packet status checker has current baselines:

```bash
python -m clarity_agent.protocol.packet_status . --record summary.md solution/solution.md solution/solution-summary.md
```

## Sub-Processes

This process might naturally lead to:

- **architecture-design.md** — Turn the approach into a technical design
- **failure-analysis.md** — Systematically explore what could go wrong
- **decision-guidance.md** — If a design choice within the solution needs structured analysis

## Common Pitfalls

**Pitfall: Stopping at the first workable idea**

The first approach that seems viable gets all the attention. Push yourself to consider at least one genuinely different alternative — even briefly — before committing. You often find something simpler.

**Pitfall: Ignoring the user's instinct**

If the user has a strong preference, take it seriously. They have context you don't. Help them think it through rather than overriding their judgment.

**Pitfall: Designing a solution nobody can build**

Elegance is worthless if it can't be implemented and maintained by the actual team in the actual timeline. Keep one foot on the ground.

**Pitfall: Losing the observations**

If solution brainstorming surfaces a failure concern, an edge case, or an architectural constraint — write it down. Don't let these insights evaporate just because you're "in the wrong process."

## Next Steps

After solution brainstorming, run **clarity-agent** again to assess what needs attention next.
