# Problem Statement

A ~10-person engineering team lacks a shared, lightweight way to see what everyone is working on day-to-day. The current workarounds — a Slack status channel and a high-level project tracker — both fall short. Slack is ephemeral and easy to miss; the project tracker is too coarse-grained (goals and milestones only) and rarely reflects actual individual work. Work changes frequently due to shifting priorities, incidents, and escalations.

The result: coordination happens ad hoc, it's hard to know who to ask for help, and the team lead has no quick, reliable answer when the VP asks about team activity.

The solution is an internal dashboard where each team member self-manages a live view of their current work items. The dashboard is visible to anyone in the company. The VP can generate and export summaries for stakeholders without depending on anyone else to produce them.

## Why This Matters

Without visibility into teammates' work, coordination is slow and lossy. Cross-team collaboration is harder than it needs to be. Leadership can't assess team health, progress, or blockers without assembling status manually. Given the pace of change (frequent reprioritization, on-call rotation, shared platform responsibilities), a static tracker isn't sufficient — the tool needs to stay current with minimal friction.

## Scope

**In scope:**
- Each team member self-manages their own work items (optional fields: name, description, status, priority, assignee, due date, comments)
- Dashboard view showing all team members' current work — read-accessible to anyone in the company
- VP-facing summary/export (link-shareable page + copy-paste friendly output)
- Slack integration: post updates from tool to channel and/or from channel to tool
- Notification/reminder system to prompt updates and check-ins

**Out of scope:**
- Manager-assigned or admin-managed tasks
- Deep project management workflow (Jira-style process enforcement)
- High-level goals and milestone tracking (handled by existing project tracker)

## Success Criteria

- Team members update their status in the tool rather than (or in addition to) the Slack channel
- Anyone can open the dashboard and immediately understand what the team is working on
- The VP can generate a shareable summary without asking anyone for input
- The coordination problems (not knowing who to ask, duplicate work) visibly decrease
