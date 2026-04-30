# Requirements

Requirements are derived from the problem statement and stakeholder needs. All fields on work items are optional unless otherwise noted.

## Must-Have (any solution fails without these)

**R1 — Self-managed work items**  
Each team member can create, edit, and delete their own work items. No one else manages their items. Supported fields (all optional): name, description, status, priority, assignee, due date, comments.  
*Traced to: Team Members — autonomy and low friction*

**R2 — Team dashboard view**  
A single view showing all team members and their current work items, readable by anyone with company access.  
*Traced to: Team Members — coordination; VP — situational awareness; Company-wide viewers — cross-team visibility*

**R3 — VP-accessible summary export**  
The VP (or anyone) can generate a summary of the team's current work and share it — via a shareable link and via copy-paste-friendly output (e.g., formatted text suitable for a slide or email). No dependency on a person to produce it.  
*Traced to: VP — stakeholder reporting*

**R4 — Low update friction**  
Updating status must take less than a minute. The tool cannot require more fields than the user wants to fill. If it's harder than posting in Slack, it will be abandoned.  
*Traced to: Team Members — adoption; problem — Slack workaround fails due to low participation*

## Important (significantly reduce value if absent)

**R5 — Slack one-way integration (nice-to-have)**  
Users can post updates from the tool to a designated Slack channel. Bidirectional sync (channel → tool) is out of scope for launch but may be added later.  
*Traced to: Team Members — where they already live; adoption strategy*

**R6 — Notification / reminder system**  
Periodic nudges to team members who haven't updated recently (cadence TBD — probably configurable). Must not be so aggressive it becomes noise.  
*Traced to: Adoption — habit-building; problem — people forget to post*

**R7 — Google Workspace SSO**  
Authentication via Google Workspace (OAuth). No separate account system. Company-wide access means any Google Workspace user in the org can log in and read the dashboard; only team members post updates.  
*Traced to: Company-wide access; adversarial concern — keeps data inside the company*

## Nice-to-Have (valuable but not blocking)

**R8 — Edit/delete own posts**  
Users can correct or remove their own updates.  
*Traced to: Adversarial concern — accidental or low-quality posts*

**R9 — Stale indicator**  
Items not updated in N days are visually flagged as potentially stale.  
*Traced to: VP — summary accuracy; Team Members — coordination*

## Non-Negotiable Constraints

- No mandatory workflow or process enforcement
- No manager-level control over others' items
- Must be accessible company-wide (not gated to the team)
