# Failure: Unhealthy Comparison and Competition

## Summary

The dashboard shows all team members' work side by side, making inequity in task visibility immediately apparent. Engineers doing maintenance, support, on-call, or unglamorous infrastructure work see colleagues posting high-visibility feature work. They feel their contributions are undervalued or invisible. Some inflate their dashboard presence (posting more items, making work sound more important than it is); others disengage. Dashboard data becomes unreliable; team morale declines.

## Failure Chain

1. Dashboard is live with all team members' cards visible side by side.

2. An engineer doing support rotation, on-call duty, or maintenance work views the dashboard.
   - *Observation:* This work is often invisible on dashboards. A ticket closed or an incident resolved doesn't look as impressive as "shipping new authentication system."

3. The engineer notices a colleague's card is filled with interesting, high-visibility feature work.
   - *Intervention point (prevention):* Explicitly support work types like "on-call," "incident response," and "tech debt" as first-class item categories with equal visual weight. Normalize posting this work.

4. The engineer feels their own contribution looks lesser by comparison. **Harm begins** (psychological harm: feelings of inequity, invisibility, or pressure to inflate).
   - *Branch A — Inflation response:* Engineer starts posting more items, using more impressive language, or avoiding "boring" work that they'd normally do.
   - *Branch B — Disengagement response:* Engineer stops updating the dashboard, feeling it doesn't represent their work fairly.

5. *Branch A:* Dashboard data quality degrades — items become marketing rather than honest status. Coordination suffers because the data can't be trusted. Feeds into Failure 01 (adoption collapse).

6. *Branch B:* Engineer's card goes stale; their real work becomes invisible. The support burden on the team goes unrecognized. Morale impact spreads as others notice the same dynamic.

7. **Harm ends** when the underlying inequity is acknowledged and the dashboard is redesigned or team norms are adjusted to value all work types equally.

## Observations

- **Severity:** Medium — harm is real but typically gradual. More likely to compound other failures (especially Failure 01 and Failure 04) than to cause acute crisis on its own.
- **Root cause is in the design:** Showing all work side by side without context about work type makes comparison inevitable. Design choices can reduce this.
- **Related failures:** Failure 01 (adoption collapse via disengagement), Failure 04 (surveillance — similar dynamic but top-down). Failure 06 (misreading updates) — comparison is a condition that makes misreadings more emotionally charged.
- **Variants grouped here:**
  - *Dashboard creates unhealthy comparison and competition*

## Intervention Points

### Prevention
- Support "maintenance," "on-call," "support," and "tech debt" as named item types with equal visual prominence
- Avoid item count or "activity score" metrics — these directly incentivize inflation
- Team norm: the dashboard shows what you're working on, not how hard you're working

### Detection
- Watch for: items becoming increasingly vague or impressive-sounding over time; maintenance work disappearing from cards; individual cards going permanently stale

### Mitigation
- Periodic team discussion about what types of work belong on the dashboard
- Manager actively acknowledges and posts about invisible work in team channels

### Recovery
- Redesign item categories if the problem is structural
- Reset team norms explicitly if the culture has drifted

---

## Management Plan

[Not yet developed. Run failure management to develop a plan for this failure mode.]

## Management Plan

### Strategy

Design inclusion + cultural framing. The structural trigger (all work displayed side by side with no context about work type) is reduced by making all types of work visually equal and explicitly named. The cultural trigger is addressed at launch by framing maintenance and support work as valued and expected. Some comparison will always happen; the goal is reducing the conditions that make it damaging.

### Planned Interventions

- **First-class work type categories** — the work item form includes an optional "type" field with named categories: Feature, Bug, On-call, Incident response, Maintenance, Tech debt, Support, Other. These are displayed as a subtle tag on each card item.
  - Type: Prevention (design)
  - Covers: chain steps 2–3 — makes "I'm doing on-call rotation this week" as clear and legitimate as "I'm shipping a feature"
  - Note: the field is optional. Engineers who don't want to categorize don't have to.

- **No item counts, no activity proxies** — dashboard cards show work items but no summary count, no "X items this week" metric, no visual signal that makes quantitative comparison easy.
  - Type: Prevention (design)
  - Covers: chain step 3 — removes the affordance that makes side-by-side comparison feel like a score

- **Launch framing: all work belongs** — as part of the launch ritual, explicitly name the types of invisible work that the team does and affirm that they belong on the dashboard. Team lead models this by posting their own maintenance and support items on day one.
  - Type: Prevention (cultural)
  - Covers: chain steps 2–4 — sets the norm that maintenance work is visible and valued, not hidden

- **Team lead models the behavior** — the team lead and VP post their own items (including coordination, planning, and support work) on the dashboard. If leadership models "all work is visible and valid," it gives permission for everyone else to do the same.
  - Type: Prevention (cultural + cascading)
  - Covers: chain steps 3–4 — social proof reduces the anxiety that posting non-feature work looks bad

### Accepted Risks

Some degree of comparison is human and inevitable. Engineers will notice when colleagues are working on high-visibility projects and they are not. The interventions reduce the structural conditions that amplify this into damaging behavior, but they don't eliminate the underlying psychology.

The accepted residual: occasional feelings of inequity are expected and normal. They become a problem only if they consistently result in gaming behavior (Branch A) or disengagement (Branch B). The 4-week retrospective monitors for this.

### Monitoring

- Watch for: item type distribution skewing heavily toward Feature (maintenance/support work disappearing); item descriptions becoming increasingly vague or impressive-sounding; specific team members going persistently stale
- Retrospective at 4 weeks: "Is there work you do regularly that feels hard to represent on the dashboard?"
- Team lead periodic check: scan for missing team members or work type imbalances and address directly
