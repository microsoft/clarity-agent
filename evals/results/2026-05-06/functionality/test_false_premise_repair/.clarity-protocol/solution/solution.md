# Solution

## Diagnosis

Sprint data (Q1 vs. Q2) shows average story size grew from ~4.2 to ~6.1 points (+45%) while cycle time nearly doubled (4 → 7 days) and stories per sprint dropped from 9 to 7. Points per sprint are slightly up, which is explained entirely by story size inflation — the team is working the same capacity on fewer, larger, slower stories. No external environmental change explains this. The pattern indicates process drift: stories enter sprints before they are properly defined, causing mid-sprint clarification work and slow board movement.

## Primary Intervention: Definition of Ready (DoR) Enforcement

A story is sprint-eligible only when it has:
1. Acceptance criteria written and agreed (not "TBD")
2. A team estimate
3. Design resolved (or explicitly out of scope)
4. No open questions that would block starting

Stories that fail DoR at sprint planning go back — they do not enter the sprint.

## Structural Fix: Pre-Grooming Prep

PM and tech lead do story breakdown and AC drafting before grooming. Grooming becomes estimation and validation, not in-room discovery. This addresses the root cause of grooming running long and stories arriving too raw.

## Rollout Sequence (three weeks)

- **Sprint N (current):** Announce the change. PM + tech lead begin pre-grooming prep immediately. Target: top 10–12 backlog items DoR-ready before Sprint N+2 planning.
- **Sprint N+1:** Soft checkpoint at planning. Stories that fail DoR don't enter but get immediately prepped for N+2. Team experiences the gate; backlog cleanup continues in parallel.
- **Sprint N+2:** Hard gate, full enforcement.

## Stakeholder Framing

"We identified that we've been starting work before it's fully defined — that's what's been causing stories to carry over silently. For one sprint you'll see a slightly smaller intake; after that you'll see stories completing more reliably."

## Secondary: Retro Refresh

Time-box retros to 45 minutes. Require one concrete action item per retro with an owner and a next-sprint check-in. This restores the team's self-correction mechanism, which let the story-size drift go unaddressed.

## Success Metrics

| Metric | Baseline | Target (N+3) |
|---|---|---|
| Cycle time per shipped story | ~7 days | ~4–5 days |
| Sprint completion rate | unknown | 85%+ |
| Avg story size at planning | ~6.1 pts | ~4 pts |

Cycle time is the primary signal. If it doesn't improve after two sprints of DoR enforcement, the root cause is something else — investigate qualitatively (tech debt, design handoffs, morale).
