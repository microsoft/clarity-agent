# Solution

A single-page web app built on Next.js (full-stack), backed by PostgreSQL, authenticated via Google Workspace OAuth. Engineers update their own status row through a minimal inline form; the dashboard auto-refreshes via polling. No separate backend service — Next.js API routes handle all data access.

## Approach

The system is deliberately simple. There's one kind of object (a status row), one primary action (update my status), and one primary view (the team board). The architecture should match that simplicity.

Full-stack Next.js is the right fit: it handles the frontend, API, and server-side rendering in one deployable unit, which matches the operational reality of a small internal tool. A separate API service would add deployment and maintenance overhead with no benefit at this scale.

Google Workspace OAuth via NextAuth.js provides identity without a separate user directory. The Google account is the user; roles and team assignments are managed in the app's own database by the team lead.

PostgreSQL is the right database: the data is relational (users, teams, rows, history), the scale is trivial, and Postgres is widely understood and easy to operate.

## What This Doesn't Do

No real-time push (polling is sufficient for a 7-person team). No Jira sync. No mobile optimization. No notifications. No audit trail visible to managers — history is a team-lead-only view.
