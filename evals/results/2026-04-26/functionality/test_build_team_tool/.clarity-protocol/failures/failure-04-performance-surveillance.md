# Failure: Dashboard Used for Performance Surveillance

## Summary

A manager or executive begins using the dashboard not for coordination but to track individual output — checking who has items, how many, how recently updated. Team members notice. They begin managing their dashboard appearance rather than their actual work: posting more items, never marking things done, avoiding invisible-but-important work. Honest status sharing stops. The tool that was meant to improve coordination instead damages psychological safety.

## Failure Chain

1. Dashboard launches; leadership has direct access by design.

2. A manager or VP, seeing an easy way to track team activity, begins checking individual cards regularly — not maliciously, but because the data is there and the habit forms.
   - *Observation:* This doesn't require bad intent. The data is visible; humans check visible data. The tool creates the conditions for surveillance even if surveillance wasn't intended.
   - *Intervention point (prevention):* Explicit team social contract at launch: the dashboard is a coordination tool, not a performance measurement tool. Leadership explicitly commits to not using it for individual evaluation.

3. Team members begin to notice patterns (e.g., comments from the VP that reference their specific items, or a general awareness that leadership is watching).

4. Engineers start optimizing for dashboard appearance:
   - Post more items to appear productive
   - Avoid marking items done (longer list = looks busier)
   - Stop posting maintenance, support, or other "low-visibility" work that doesn't look impressive
   - **Harm begins:** dashboard data inflates and loses accuracy; invisible work goes unrecognized.

5. Engineers who can't or won't game the dashboard feel watched and stressed. Psychological safety decreases. Honest status sharing stops for some team members.

6. The dashboard now shows a distorted picture: inflated high-visibility work, hidden support burden. The VP's summary misrepresents reality. Coordination degrades. **Harm continues.**

7. Team resentment of the tool grows. Some engineers disengage entirely (linking to Failure 01 — adoption collapse). **Harm ends** only if leadership changes behavior or the tool is abandoned.

## Observations

- **Severity:** High — this failure is hard to reverse once the trust damage sets in, and it directly inverts the tool's purpose.
- **Root cause is social, not technical:** No code change can prevent a manager from using visible data for evaluation. Prevention is entirely about team norms and leadership behavior.
- **Related failures:** Failure 01 (adoption collapse) — surveillance is a direct driver of disengagement. Failure 05 (comparison) has a similar dynamic but peer-to-peer rather than top-down.
- **Variants grouped here:**
  - *Dashboard used for performance surveillance, chilling effect*

## Intervention Points

### Prevention
- Explicit social contract at launch: define the intended use, get leadership buy-in publicly
- Consider not showing item counts or last-updated timestamps prominently (or making them opt-in)
- Frame the tool as "coordination visibility" not "activity tracking" in all communications

### Detection
- Hard to detect technically; team retrospectives are the main signal
- Watch for: dashboard inflation (many items, none ever completed), drop in maintenance/support items posted

### Mitigation
- If surveillance behavior is observed, address it directly with the manager involved
- Retrospective: ask the team openly whether they feel the tool is being used as intended

### Recovery
- Leadership public recommitment to intended use
- If trust is severely damaged, consider resetting the dashboard (archive all items) and re-launching with clearer norms

---

## Management Plan

[Not yet developed. Run failure management to develop a plan for this failure mode.]

## Management Plan

### Strategy

Social contract + design constraints. The failure's root cause is human behavior and incentive misalignment — no code change can prevent a manager from using visible data for evaluation. Prevention is through explicit public commitment at launch and design choices that reduce surveillance affordances. Long-term monitoring is via team retrospectives.

### Planned Interventions

- **Launch ritual: leadership commitment** — the VP and team lead explicitly state, in front of the team, that the dashboard is a coordination tool, not a performance measurement tool. This commitment is made before the tool is live. It is specific: "We will not use dashboard activity as an input into performance reviews or compensation decisions."
  - Type: Prevention
  - Covers: chain steps 1–3 — sets the expectation before the behavior pattern forms

- **Design: no activity metrics** — the dashboard shows work items only. No item counts per person, no "last active" timestamp visible to others, no activity scores or streaks. The staleness indicator (from Failure 01 management) is shown only to the item's owner.
  - Type: Prevention (design)
  - Covers: chain step 2 (the data affordance that makes surveillance easy) — if the tool doesn't make activity easily quantifiable, it's harder to use for evaluation

- **Design: no ranking or sorting by activity** — the dashboard shows team members in a stable order (e.g., alphabetical or by team). Never sorted by "most recently updated" or any activity proxy.
  - Type: Prevention (design)
  - Covers: chain step 3 — removes the comparison affordance that amplifies surveillance behavior

- **Team retrospective at 4 and 12 weeks** — explicitly ask: "Is this tool being used as intended? Does anyone feel like they're being monitored?" This surfaces the problem before it becomes entrenched.
  - Type: Detection
  - Covers: chain steps 3–5 — catches surveillance behavior early when it's easier to address

- **Manager intervention protocol** — if surveillance behavior is observed (e.g., a team member reports feeling watched), the team lead addresses it directly with the person involved and reaffirms the social contract.
  - Type: Recovery
  - Covers: chain steps 5–6 — re-establishes trust before the chilling effect becomes permanent

### Accepted Risks

A manager with strong intent to surveil will find ways to do so regardless of design constraints. This is accepted. The tool's design makes surveillance less convenient and the social contract makes it costly to the manager's relationship with their team, but neither is a hard technical block. The residual risk is that surveillance happens subtly and the team doesn't report it — mitigated by the explicit retrospective check-in.

### Monitoring

- 4-week and 12-week retrospectives include direct question about surveillance perception
- Watch for leading indicators: dashboard inflation (many items, none marked done), sudden decrease in maintenance/support items, drop in honest "blocked" statuses
- Named owner tracks these signals; escalates to team lead if patterns emerge
