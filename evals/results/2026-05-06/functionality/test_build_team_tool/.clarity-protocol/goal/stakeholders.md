# Stakeholders

## Engineers (Primary Users) — Direct, Aligned

Seven engineers on one team. They update their own status row and read everyone else's. Technically comfortable but won't tolerate friction: if updating takes more than a few clicks, they'll stop doing it. They need to trust the system to reflect reality (i.e., other people's entries are real, not stale). Concerns: extra tool overhead, feeling surveilled.

## Team Lead / Engineering Manager — Direct, Aligned

The person who commissioned this tool (primary stakeholder driving the build). Needs a clean, always-ready view for exec reviews and for spotting blockers before they escalate. Will be the de facto admin. Cares about adoption — a dashboard that engineers don't update is worse than nothing.

## VP and Other Managers — Direct, Aligned (Read-Only)

Consume the dashboard in review settings; don't contribute to it. Need a clean, legible view at a glance — this is their signal about team health, not a project-management tool. Won't want to learn a new interface; the experience needs to be zero-friction for a viewer.

## Future Team Leads / Additional Teams — Indirect, Aligned

Not current users, but the data model and permissions design should not require rework if the team splits or a second team is added. Their needs are similar to the current team's.

## Surveillance-Sensitive Engineers — Aligned but Tension Point

Engineers who feel the tool is being used to micromanage rather than coordinate. Not an external adversary, but a real risk to adoption. If status updates feel like time-tracking or performance monitoring, engineers will stop updating or update performatively. The design should minimize this perception: no history/audit trail visible to managers, no "last active" indicators beyond the last-updated timestamp on the status itself.
