# Failure: Service Unavailability and Ownership Gaps

## Summary

The tool goes offline or degrades in a way that can't be quickly fixed because no one is clearly responsible for it. Firebase quota limits, a Google infrastructure outage, or unchecked credential expiry take down the service. Because the tool was built by 1-2 engineers on a sprint with no designated long-term owner, by the time something breaks, the institutional knowledge of how to fix it may have walked out the door.

## Failure Chain

1. A dependency or operational gap causes service degradation:
   - *Branch A — Firebase quota exceeded:* Free tier read/write limits hit as company-wide readership grows; app returns errors.
   - *Branch B — Google infrastructure outage:* Firebase Auth and/or Firestore unreachable; no one can log in.
   - *Branch C — Ownership gap:* Service account expires, Firebase billing lapses, or a config breaks; no one knows who to call.

2. The dashboard becomes unavailable or partially broken.
   - *Intervention point (prevention — quota):* Monitor Firestore read/write usage; set budget alert on Firebase billing. Upgrade to Blaze (pay-as-you-go) before free tier limits are hit.
   - *Intervention point (prevention — ownership):* Assign a named owner at launch. Document all credentials, service account expiry dates, and billing contacts in an ops runbook.

3. Team members try to access the dashboard and get errors. **Harm begins** — team reverts to Slack for coordination; VP can't generate a summary; the problem the tool solved re-emerges.

4. *Branch A/C:* Outage persists until someone investigates.
   - *Intervention point (detection):* Uptime monitoring with Slack alert when the app is unreachable.
   - Without a named owner, whoever gets the Slack alert may not know what to do.

5. *Branch B:* Self-resolves when Google recovers; typically within hours. Low intervention needed.

6. *Branch A/C:* Whoever is responsible upgrades billing tier or rotates credentials. **Harm ends** when service is restored.

## Observations

- **Severity:** Medium — temporary unavailability is annoying but not catastrophic for an internal coordination tool. The deeper risk is a slow, unchecked degradation from ownership gaps that no one notices until the tool is fully broken.
- **Google is a single point of failure:** Auth, database, and the Cloud Function all depend on Google infrastructure. During a Google outage, the team is also likely to be unable to use Gmail and Google Meet — so the coordination harm is partially absorbed by a broader outage context.
- **Related failures:** Failure 02 (auth breakdown) — some causes overlap (service account expiry affects both).
- **Variants grouped here:**
  - *Firebase free tier quota exceeded, app goes down*
  - *Google outage takes down auth and the dashboard simultaneously*
  - *No one owns the tool after launch*

## Intervention Points

### Prevention
- Named owner designated at launch; documented in team wiki
- Firebase on Blaze (pay-as-you-go) plan from the start, with budget alert set at a low threshold
- Service account expiry calendar reminder set at creation time
- Ops runbook covering: how to restore service, who to contact for billing, credential rotation process

### Detection
- Uptime monitoring (e.g., Firebase Hosting health check, or a simple external ping) with Slack alert

### Mitigation
- Clear error page with "check back later" message rather than a broken UI
- Link to the Slack channel as fallback for status sharing during outages

### Recovery
- Documented runbook (see Prevention) enables any engineer to restore service without tribal knowledge
- Post-incident: identify which branch caused it and close the prevention gap

---

## Management Plan

[Not yet developed. Run failure management to develop a plan for this failure mode.]

## Management Plan

### Strategy

Operational hygiene: named ownership, monitoring with alert, and a documented runbook. The Firebase quota risk is eliminated by using Blaze plan from day one. The Google outage risk is accepted as a correlated external dependency. The ownership gap is addressed by explicit designation and documentation before the tool goes live.

### Planned Interventions

- **Firebase Blaze plan from day one** — deploy on the pay-as-you-go Blaze plan rather than the free Spark tier. Set a monthly budget alert at $20 (well above likely spend for a 10-person team). This eliminates quota-related outages entirely.
  - Type: Prevention
  - Covers: Firebase free tier quota variant — quota limits never apply on Blaze

- **Named owner designated at launch** — before the tool goes live, one engineer is explicitly named as the tool owner. Their name and contact are documented in the team wiki. They are responsible for: responding to outage alerts, rotating credentials, handling billing issues, and updating the ops runbook.
  - Type: Prevention + Recovery
  - Covers: ownership gap variant — eliminates "nobody knows who to call"

- **Ops runbook in team wiki** — a short document covering: Firebase project URL and console access, how to check Cloud Function logs, how to rotate the service account credentials, how to manually set isTeamMember for a user, how to upgrade billing tier, service account expiry date and rotation reminder date.
  - Type: Recovery
  - Covers: all variants — any engineer can restore service using the runbook even without prior knowledge

- **Uptime monitoring** — simple HTTP health check against the Firebase Hosting URL (e.g., via UptimeRobot free tier or similar). Sends a Slack message to the named owner when the app is unreachable for >5 minutes.
  - Type: Detection
  - Covers: chain step 2 — owner is alerted before users report the outage

- **Graceful degradation message** — if Firestore is unreachable, the app displays a clear "Dashboard temporarily unavailable — check back soon. For urgent coordination, use [Slack channel link]." No broken UI; a useful fallback.
  - Type: Mitigation
  - Covers: chain step 3 — reduces user frustration during an outage and maintains the Slack fallback

- **Monthly budget alert** — Firebase billing alert at $20/month notifies the named owner if spend is trending unexpectedly. At 10 users, normal spend should be well under $5/month.
  - Type: Detection
  - Covers: Firebase quota variant (early warning before limits are approached)

### Accepted Risks

Google infrastructure outages (Firebase Auth, Firestore) will make the tool unavailable. This is accepted — the company already depends on Google for email, calendar, and chat, so a Google outage affects the whole company regardless. The fallback is the existing Slack channel.

The named owner may leave the team without transferring ownership. Mitigated by: ownership being documented in the team wiki (not in a person's head), the ops runbook enabling any engineer to take over. The team lead is responsible for ensuring ownership is transferred during offboarding.

### Monitoring

- Uptime alert → named owner Slack DM within 5 minutes of downtime
- Monthly budget alert at $20 → named owner email
- Annual ops review: check service account expiry, confirm named owner is still on the team, verify runbook is current
