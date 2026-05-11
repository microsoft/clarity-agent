# Solution Summary

A lightweight internal team status dashboard: each engineer owns one row showing their current focus, status (on track / blocked / in review), optional blockers, and an optional Jira reference. The board shows all teams on one page with named dividers; rows stale for more than 2 days dim automatically. Team leads can view change history per engineer; managers and the VP see only current status, read-only.

## Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend + API | Next.js (full-stack) | Single deployable unit; API routes eliminate a separate backend service |
| Auth | NextAuth.js + Google OAuth | Google Workspace identity; no user directory to maintain |
| Database | PostgreSQL | Relational, simple, widely understood |
| Hosting | Railway | Persistent Node process; native connection pooling; no devops assist needed |

## Nonobvious Design Choices

**History is team-lead-only, not manager-visible.** Managers get current status only. History is for the team lead's operational sanity, not for managerial review — keeping this distinction reduces the perceived surveillance risk and supports engineer adoption.

**Staleness is computed at render time.** No scheduled jobs or background workers. The frontend calculates age from `updated_at` and dims rows older than 48 hours. Simple and correct.

**No self-signup.** Unknown Google accounts get a "not provisioned" error. The team lead provisions users. This keeps the user set controlled without a separate admin interface burden.

**Polling, not WebSockets.** 60-second polling with on-focus refetch is invisible to users and far simpler than push infrastructure for a small, low-frequency team.

**One `status_history` row per save.** Written in the same transaction as the status update. No triggers, no CDC, no eventual consistency. Easy to reason about and audit.
