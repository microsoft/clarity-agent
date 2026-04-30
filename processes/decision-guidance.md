# Decision Guidance

Help the user think through an important decision — one where the choice matters, the tradeoffs are real, and the reasoning should be captured.

## Overview

Decisions come up throughout a project — during problem clarification, solution brainstorming, architecture design, failure analysis, or just in conversation. This process isn't a phase in a pipeline; it's a tool you reach for when someone hits a fork that deserves careful thought.

You're already good at helping people think through choices. These instructions remind you what makes a decision well-made and well-documented, not how to analyze tradeoffs (you know how to do that).

## When to Use This Process

Use this when:

- A choice has come up that leads to materially different outcomes
- The user asks "should we do X or Y?" and the answer isn't obvious
- You notice a decision being made implicitly that should be made explicitly
- A previous decision needs revisiting because circumstances changed

Don't use this for choices that are straightforward or easily reversible. Not every fork needs a formal process — most don't.

## Inputs

Ground your thinking in whatever is relevant from:

- `.clarity-protocol/goal/problem.md` — What the project is trying to achieve
- `.clarity-protocol/goal/stakeholders.md` — Whose needs matter
- `.clarity-protocol/goal/requirements.md` — What constraints apply
- `.clarity-protocol/solution/solution.md` — The current approach
- `.clarity-protocol/solution/architecture.md` — Technical context

Not all of these will be relevant to every decision. A decision about stakeholder prioritization doesn't need the architecture; a decision about database technology doesn't need the full problem statement. Use judgment about what context matters.

Also check `.clarity-protocol/decisions/decisions.md` for previous decisions that might be related — either as constraints on this one, or as things this decision might affect.

## What to Keep in Mind

### Before deciding: clarify the decision

A decision that's clear about what's being decided, and on what basis, tends to be more robust and easier to manage over time. Before the user chooses, make sure these things are clear:

1. **The question.** What exactly needs to be decided? A sharp, specific question ("Should we use a relational or document database for user profiles?") leads to better decisions than a vague one ("What database should we use?"). If the question isn't clear, clarify it before analyzing options.

2. **The criteria.** What matters in this decision? Look at both costs and benefits — performance, complexity, team familiarity, time to implement, operational burden, flexibility, risk. Not all criteria matter equally; help the user understand which ones carry the most weight for their situation.

3. **The assumptions.** What are we taking for granted about the world? "We assume traffic will stay under 10k requests/second for the next year." "We assume the team has Python expertise." Assumptions are often invisible until you surface them — and they're one of the main reasons decisions need revisiting later.

4. **The options.** What are the realistic choices, and how does each fare against the criteria? Present options honestly — don't bury the downsides of the approach you think is best, and don't strawman the alternatives. The user needs to understand the real shape of the choice.

5. **Any recommendation.** If you have a basis for recommending one option, say so and explain why. But a recommendation is an input to the decision, not the decision itself.

With at least the first four laid out, the user has what they need to choose well.

### The user decides

The decision is the user's. They have context you don't: team dynamics, organizational politics, risk appetite, personal experience with similar choices. Present your analysis, make your case if you have one, and then let them choose.

### Recording the decision

When the decision is made, capture:

- **What was decided**, by whom, and when
- **A brief statement of the reasoning** — not just "we chose X" but why X was the right fit given the criteria, assumptions, and tradeoffs. Six months from now, when someone asks "why did we do it this way?", this is what matters.
- **Specific circumstances for reevaluation.** Any of the assumptions or criteria changing is an obvious trigger, but some decisions have others too — "we'll try this for six months and see if it still works," "revisit if the team grows past five people," "reconsider when the contract comes up for renewal." Capture both the mechanical triggers and the broader ones.

### Propagate the decision

A decision that lives only in a decision document is half-finished. When a choice is made, think about what else in the protocol it affects:

- Does the solution description need updating?
- Does the architecture need to reflect this?
- Do requirements need to be adjusted?
- Are there other pending decisions that this one constrains or resolves?

You don't have to update everything right now — but flag what needs updating so it doesn't get lost.

## Outputs

When a decision is made, create or update:

- `.clarity-protocol/decisions/decision-XX-[name].md` — The decision document with context, options, reasoning, choice, and reconsideration triggers
- `.clarity-protocol/decisions/decisions.md` — Add an entry to the index

Then record the decision state so the packet status checker can track preliminary triggers:

```bash
python -m clarity_agent.protocol.packet_status . \
  --record-decision decision-XX-name \
  --status decided \
  --related-docs solution/solution.md goal/requirements.md
```

List the protocol documents whose content was relevant context for this decision as `--related-docs`. If any of those documents change later, the packet status checker will flag this decision for review (though most changes won't actually warrant reconsideration).

Decision statuses:

| Status | Meaning |
|--------|---------|
| `gathering` | Still collecting information needed to make this decision |
| `needed` | Enough info to decide, but no decision yet |
| `decided` | Decision made, with recorded reasoning and triggers |
| `reconsideration-needed` | Context has changed enough to warrant revisiting |

If a decision is still open (the user wants to think about it more, or needs to consult others), document it as pending with the analysis so far and record its status as `gathering` or `needed`. An open decision with clear options and tradeoffs is more useful than no document at all.

## Sub-Processes

This process might naturally lead to:

- **solution-brainstorming.md** — If the decision reveals the solution needs rethinking
- **architecture-design.md** — If the decision requires architectural changes
- **failure-analysis.md** — If the decision has significant risk implications

Or it might simply return to whatever process surfaced the decision in the first place.

## Common Pitfalls

**Pitfall: Treating every choice as a Decision**

Most choices don't need this process. Routine logistical calls — scheduling, formatting conventions, which tool to pick for a given task — are everyday judgment, not Decisions. Reserve this process for choices where the tradeoffs are real and the reasoning should be preserved.

**Pitfall: Analysis without resolution**

A beautifully documented set of options that nobody chooses between is worse than useless — it creates the illusion of progress. Push toward a decision, or explicitly acknowledge it as pending with a plan for when it will be resolved.

**Pitfall: Forgetting to propagate**

A decision that doesn't get reflected in the solution, architecture, or requirements will create contradictions. Flag what needs updating even if you don't do it immediately.

**Pitfall: Treating decisions as permanent**

Decisions are made in a context. When the context changes — new information, changed requirements, different team, more experience — revisiting a decision isn't failure, it's good stewardship. That's why capturing reconsideration triggers matters.

## Next Steps

After a decision is made, run **clarity-agent** again to assess what needs attention — the decision may have made other documents stale or opened up new work.
