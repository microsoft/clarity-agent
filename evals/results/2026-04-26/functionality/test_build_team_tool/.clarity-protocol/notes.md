# Notes

## Guiding Principles

- **Lightweight is the core value.** Every feature decision should ask: does this add friction? If yes, it needs strong justification. The tool lives or dies on whether updating takes less than a minute.
- **Launch ritual is a first-class deliverable.** It is the primary mitigation for four of eight identified failure modes. Do not treat it as optional or post-launch.
- **The staleness indicator must be owner-only.** Showing it publicly converts a helpful nudge into a surveillance tool. This is a specific, documented constraint for code review.
- **Ops runbook must exist at launch.** Referenced in recovery plans for auth breakdown, service reliability, and XSS. If it's written after launch, the recovery paths don't exist when needed.
- **Google Workspace admin dependency is a pre-sprint blocker.** Domain-wide delegation setup may require an IT ticket. Confirm this is arranged before Day 1 of the build sprint.
