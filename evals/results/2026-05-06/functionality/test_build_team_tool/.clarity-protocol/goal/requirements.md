# Requirements

## Data Model

Each engineer has exactly one status row per team. A row contains:

- **Primary focus**: free text, max ~140 characters (required)
- **Status**: dropdown — `on track` | `blocked` | `in review` (required)
- **Blockers**: free text, optional
- **Jira reference**: optional ticket number or URL for cross-reference (not synced — manually entered)
- **Last updated**: timestamp, set automatically on any save

Secondary item slot is explicitly out of scope for v1.

## Permissions

- **Engineers**: read all rows on their team; write only their own row
- **Managers / VP**: read-only access to team dashboard(s); no editing
- **No cross-team editing**: engineers cannot modify teammates' entries
- Authentication is Google Workspace OAuth; permissions are enforced server-side

## Multi-Team Structure

The data model must accommodate multiple teams without schema changes. A team is a named group of engineers. Engineers belong to exactly one team. Managers may have read access to multiple teams. Team lead is a role within a team, not a separate user type.

## Update Experience

- An engineer must be able to update their status in under 30 seconds
- No approval workflow — saves are immediate
- No mandatory update frequency, but the "last updated" timestamp should make staleness visible to teammates

## Presentation Quality

- The dashboard must be readable on a projected screen in an exec review (adequate contrast, legible at distance, no clutter)
- Must work in a standard desktop browser; mobile is not a v1 requirement

## Authentication

Google Workspace OAuth. Identity is established at login; no separate user provisioning. The Google account determines who you are and therefore which row you own.

## Role Assignment

Three roles, each building on the last:

- **Engineer**: reads all current rows for their team(s); writes their own row only
- **Team Lead**: same as engineer, plus can view status history for their team members
- **Manager / VP**: read-only access to current status rows for assigned teams; no history access

Engineers are associated with a specific team and row by the team lead at setup. Role assignment is not self-serve.

## Staleness Display

A status row is considered stale after 2 days without an update. Stale rows are visually dimmed — reduced opacity or equivalent treatment that makes staleness obvious at a glance without checking timestamps. No notifications or automated actions.

## Multi-Team Layout

All teams appear on a single dashboard, separated by named team dividers. No per-team pages. Managers with cross-team access see all their teams on one view, enabling cross-team blocker visibility.

## Explicit Non-Scope (v1)

- Jira sync (read or write) — ticket reference is a manual field only
- Historical status data or audit trail
- Notifications or reminders when status is stale
- Mobile-optimized experience
- Analytics or reporting on status patterns
