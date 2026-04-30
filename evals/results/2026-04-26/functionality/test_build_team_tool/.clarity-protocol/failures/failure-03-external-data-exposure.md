# Failure: Internal Work Exposed Externally

## Summary

Work item content — project names, priorities, blockers, strategic direction — reaches people outside the company. This can happen accidentally (a shared URL forwarded beyond intended audience) or intentionally (the VP shares the summary in a stakeholder presentation). The "nothing confidential here" assumption may not hold for all items on the team's dashboard, and the tool currently has no mechanism to limit re-sharing once a summary is generated.

## Failure Chain

1. A company employee (likely the VP) opens the `/summary` page and generates a summary of team activity.
   - *Observation:* The summary is explicitly designed to be shareable — that's a feature. The failure occurs when it travels further than intended.

2. The summary is copied to a slide, forwarded in an email, or the URL is shared.
   - *Branch A — Intentional external share:* VP includes the summary in a board deck, partner briefing, or press conversation. They may not realize some items are sensitive.
   - *Branch B — Accidental leak:* URL shared in a Slack message that's visible beyond the intended audience; forwarded email reaches external parties.

3. External party — competitor, partner, journalist, or board member — receives work item content. **Harm begins.**
   - *Intervention point (prevention):* Watermark summaries with "Internal only — do not distribute" to trigger awareness before sharing.
   - *Intervention point (prevention):* Auth wall on the summary URL (requires Google login restricted to company domain) limits accidental external access via link.
   - *Intervention point (prevention):* Team awareness that dashboard items are company-wide visible; some items may warrant less specificity.

4. Strategic information (upcoming features, competitive moves, internal problems) is now outside the company's control.

5. **Harm ends** when the information is stale or when damage from disclosure is contained, but disclosure is generally irreversible.

## Observations

- **Severity:** Medium — depends heavily on the sensitivity of what's posted. For a team that posts "working on OAuth refactor," exposure is harmless. For a team that posts "pivoting away from Product X," exposure is significant.
- **Retention window:** The 7-day archival of done items means sensitive completed work remains visible for up to a week. For most work this is fine; for anything sensitive it's worth knowing.
- **Related failures:** Failure 02 (Firestore rules) — if rules are misconfigured to allow public read access without auth, the exposure is automatic rather than incidental.
- **Variants grouped here:**
  - *Summary page URL leaks sensitive work details outside company*
  - *VP summary shared externally exposes strategic priorities*
  - *(Note) Work items remain visible for up to 7 days after completion — a retention window consideration*

## Intervention Points

### Prevention
- Restrict all routes (including `/summary`) to Google Workspace domain authenticated users only
- Add "Internal — do not distribute" watermark to generated summaries
- Team norm: dashboard items are company-wide; avoid posting highly sensitive strategic details

### Detection
- No reliable way to detect once data has been shared externally; focus on prevention

### Mitigation
- Allow team members to mark specific items as "internal" — excluded from the VP summary copy-paste export
- Configurable retention window for done items (shorter for sensitive teams)

### Recovery
- If a leak is identified, assess which items were exposed and notify relevant stakeholders
- No technical recovery once data is shared externally

---

## Management Plan

[Not yet developed. Run failure management to develop a plan for this failure mode.]

## Management Plan

### Strategy

Defense-in-depth with explicit acceptance of residual risk. Technical controls limit accidental external access. A watermark makes intentional sharing a deliberate act. Team awareness sets expectations. Deliberate external sharing by the VP is accepted as residual risk — the VP is a trusted stakeholder, and preventing them from sharing their own team's summary would undermine a core use case.

### Planned Interventions

- **Auth wall on all routes including `/summary`** — Firebase Auth with Google Workspace domain restriction (`hd` parameter) on every route. Unauthenticated or out-of-domain requests are redirected to the login page, not served content.
  - Type: Prevention
  - Covers: accidental link leak (URL forwarded to an external party is useless without a company Google account)

- **"For internal use only" watermark on copy-paste output** — when the VP uses the copy button on `/summary`, the copied text prepends: `[Internal — do not distribute outside [Company Name]]`. Subtle enough not to clutter the output for internal use; visible enough to prompt awareness before external sharing.
  - Type: Mitigation
  - Covers: intentional VP sharing variant — watermark doesn't prevent sharing but makes it a deliberate choice

- **7-day archival of done items** — done items are removed from the summary after 7 days. This limits the window during which completed (potentially sensitive) work appears in the summary.
  - Type: Mitigation (scope reduction)
  - Covers: retention window concern

- **Team awareness at launch** — as part of the launch ritual, explicitly note: "Dashboard items are visible to anyone in the company. Don't post anything you wouldn't want a colleague from any team to see." This is not a policy — it's a design reality to communicate.
  - Type: Prevention (social)
  - Covers: engineers posting more sensitive content than intended

**Long-term (if needed):**

- **Item-level confidentiality flag** — a "team-only" toggle on individual items that excludes them from the VP copy-paste export (still visible on the dashboard to authenticated employees). Build this if the team finds they're self-censoring items because they don't want them in executive summaries. Not needed at launch.

### Accepted Risks

An authenticated company employee (including the VP) can deliberately share dashboard content with external parties. This is accepted. The "internal only" watermark makes this a deliberate act. The company's acceptable-use policy and employee judgment govern what gets shared externally — this tool does not change that dynamic relative to any other internal communication channel (Slack, email, Google Docs).

If a specific work stream is genuinely confidential (e.g., M&A activity, personnel matters), the team norm is not to post it on the dashboard. This is a social control, not a technical one.

### Monitoring

No automated detection for intentional external sharing. If a leak occurs, the Firestore audit log provides a complete record of who posted what and when. Post-incident response: assess what was exposed, notify relevant stakeholders, update team norms if needed.
