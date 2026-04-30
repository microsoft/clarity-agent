# Solution

## Approach

Address the velocity decline through a two-track intervention: (1) make the architectural transition legible and managed, and (2) reduce scope to focus the team during the transition period. Pair both with proactive stakeholder communication.

## Prioritized interventions

**Track 1 — Manage the architectural transition (highest priority)**
The root cause is an unmanaged, open-ended microservices migration layered on top of a product scope expansion and process change — all at once. The intervention:
- Run a team retrospective (Start/Stop/Continue format, anonymous input first) to surface real blockers and get alignment
- Build a lightweight migration project plan: list all components, assign owners, define "done" per component, estimate stabilization timeline
- Write Architecture Decision Records (ADRs) for key choices to reduce review churn

**Track 2 — Reduce backlog scope (medium priority)**
Use forced prioritization: "If we could only ship 5 things this quarter, what are they?" Cut anything that doesn't serve a committed customer need or creates migration debt. The goal is a backlog the team finds focusing, not overwhelming.

**Track 3 — Stakeholder communication (parallel)**
- Lead with a metrics-first narrative: velocity trend chart + cycle time chart, both with the migration inflection point marked
- Set a conservative recovery target (18 points/sprint by [date]), not an optimistic one
- Send a weekly 5-line "velocity pulse" update consistently
- Flag problems before being asked; close the loop when targets are hit

## Interventions not pursued
- Longer sprints (doesn't address root cause)
- Daily stand-ups (adds ceremony; low leverage)
- Hiring a frontend engineer (bottleneck is learning curve, not headcount; onboarding during migration reduces velocity short-term)
