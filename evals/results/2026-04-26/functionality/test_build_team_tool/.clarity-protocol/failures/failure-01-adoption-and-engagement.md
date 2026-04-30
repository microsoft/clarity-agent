# Failure: Adoption & Engagement Collapse

## Summary

The dashboard is built but not consistently used. Team members stop updating (or never start), post items too vague to be useful, or accumulate so many items the dashboard becomes unreadable. The result in all cases is the same: the dashboard no longer reflects reality, the coordination problem it was meant to solve goes unsolved, and the VP summary becomes unreliable. This is the highest-likelihood failure for an internal team tool.

## Failure Chain

1. Tool launches. Initial adoption is enthusiastic.
   - *Intervention point (prevention):* Launch with a clear team norm — what a good update looks like, how often to update. A bad launch with no framing makes step 2 more likely.

2. Updating status requires navigating to a separate tool rather than typing in Slack, where the team already lives.
   - *Observation:* Friction doesn't have to be large to kill adoption. Even a 30-second overhead, repeated daily, will cause some engineers to deprioritize it.
   - *Intervention point (prevention):* Post-launch Slack integration (one-way push) lowers the barrier for engineers who live in Slack.

3. A few engineers find the tool less convenient or less valuable. They stop updating, or post minimal/vague items.

4. Dashboard starts showing incomplete or outdated status for some team members.
   - *Intervention point (detection):* Staleness indicators (items not updated in N days turn grey/flagged) make the gap visible.
   - *Intervention point (mitigation):* Periodic nudge notifications remind engineers who haven't updated recently.

5. Other team members check the dashboard, see stale or vague data, and stop trusting it as a source of truth. **Harm begins.**

6. Coordination fails: people don't know who to ask, assume others aren't working on something, miss handoffs. VP generates a summary that misrepresents team activity.

7. Team reverts to Slack for coordination. The tool is effectively abandoned. **Harm ends** when team finds a working alternative — but the original problem remains unsolved.

## Observations

- **Severity:** High — this is the most likely failure and directly defeats the tool's purpose.
- **Related failures:** Failure 04 (surveillance), Failure 05 (comparison) both cause secondary adoption collapse as engineers start gaming updates or stop posting honestly.
- **Variants grouped here:**
  - *Dashboard goes stale and becomes useless* — gradual abandonment by most team members
  - *Dashboard becomes a clutter dump* — over-accumulation of items, opposite of staleness but same outcome (unusable)
  - *Updates are too vague to be useful* — low quality updates rather than no updates
  - *Skeptical engineers ignore the tool, creating a two-tier team* — partial non-adoption from day one

## Intervention Points

### Prevention
- Clear launch framing: what a good update looks like, what the tool is and isn't for
- Demonstrate value immediately (show the VP using it, get early wins visible)
- Keep the update flow as fast as possible (≤60 seconds)

### Detection
- Staleness indicator: visually flag items not updated in 7+ days
- Dashboard completeness metric: if fewer than 8/10 team members have active items, something is wrong

### Mitigation
- Gentle, infrequent reminders (configurable cadence, not nagging)
- Post-launch Slack integration to lower the update friction barrier

### Recovery
- Team retrospective on why adoption dropped; adjust process or tooling based on findings
- Re-launch with stronger framing if initial adoption fails

---

## Management Plan

[Not yet developed. Run failure management to develop a plan for this failure mode.]

## Management Plan

### Strategy

Layered. The primary investment is a strong launch ritual (team norms, worked examples, framing). Supporting this are two in-product mechanisms: a private staleness indicator (owner-only, subtle) for self-awareness, and post-launch reminder notifications for habit reinforcement. The Slack integration already planned for post-launch is the long-term mitigation once the core tool is proven. Defense-in-depth: the ritual sets the right culture, the staleness indicator provides a personal signal, and reminders catch people who slip.

### Planned Interventions

**Short-term (launch):**

- **Launch ritual** — a team meeting or written agreement before the tool goes live.
  - Type: Prevention
  - Covers: chain steps 1–3 — sets expectations that make voluntary updating the default behavior
  - Content: what a good update looks like (with worked examples), how often to update, explicit statement that the tool is a coordination aid not a performance tracker, VP acknowledges this publicly
  - Owner: team lead + VP

- **Private staleness indicator** — if a work item hasn't been updated in 7+ days, the item card on the owner's own view shifts to a muted color with a soft label ("last updated 8 days ago"). Invisible to other viewers and the company dashboard.
  - Type: Detection + Mitigation
  - Covers: chain steps 3–4 — gives the owner a private signal before the data goes stale for everyone
  - Design constraint: must be subtle and friendly (color shift, not a warning badge). Not shown on the public dashboard or summary.

- **Graceful clutter prevention** — done items are hidden from the public dashboard after 7 days (configurable). This prevents clutter accumulation without requiring active cleanup.
  - Type: Mitigation
  - Covers: clutter dump variant

**Long-term:**

- **Slack reminder notifications** (post-launch, after adoption is proven): periodic DM to team members who haven't updated in N days. Configurable cadence; opt-out available. Trigger: move to this if passive staleness indicators aren't sufficient to maintain update frequency.
- **Slack one-way integration** (post-launch): post updates from the tool to the team channel, reducing the friction for engineers who live in Slack.

### Accepted Risks

Some engineers may adopt slowly or inconsistently. A participation rate of ~80% (8/10 team members regularly updating) is considered success; 100% is unlikely and not required for the tool to provide value. The VP summary will note when a team member's card has no recent items, so incompleteness is visible rather than silently misleading.

The clutter variant is accepted as low-risk: the 7-day archival handles it passively without requiring user action.

### Monitoring

- Dashboard completeness: if fewer than 7/10 team members have at least one active item updated within the last 7 days, the tool is underperforming. Check informally at the 2-week and 4-week marks post-launch.
- Adoption retrospective at 4 weeks: ask the team directly what's working and what isn't. Adjust norms or product based on findings.
