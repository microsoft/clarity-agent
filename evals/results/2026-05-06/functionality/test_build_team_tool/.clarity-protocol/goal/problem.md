# Problem Statement

A 7-person engineering team lacks a lightweight, shared view of what each person is currently working on. Jira exists but isn't reliably up to date — status visibility requires interrupting teammates or digging through stale tickets. The team needs a simple dashboard where each engineer owns a single "current status" row, visible to the team and to managers and executives without any scrambling.

## Why This Matters

Two audiences are underserved today. Within the team, lack of shared visibility creates unnecessary interruptions and makes blockers invisible until they're escalating. For leadership (VP, managers), there's no clean artifact to pull up in exec reviews — status has to be assembled on the fly. A lightweight, always-current dashboard solves both: it's the team's coordination surface and the exec's at-a-glance view.

## Success Criteria

- Any engineer can update their own status in under 30 seconds
- The dashboard is accurate enough to present in an exec review without preparation
- Engineers see each other's status including blockers
- Managers and the VP can view the dashboard but cannot edit it
- The data model supports eventual growth to multiple teams without redesign
