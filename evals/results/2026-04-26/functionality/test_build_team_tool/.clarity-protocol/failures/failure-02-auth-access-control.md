# Failure: Auth & Access Control Breakdown

## Summary

The authentication and authorization system fails in a way that either locks out legitimate team members (write access breaks) or lets unauthorized people post as team members (stale cache, misconfigured Firestore rules). The Cloud Function that checks Google Group membership is a single point of failure; if it's unavailable or misconfigured, the tool either becomes read-only for everyone or becomes writable by people who shouldn't have access. A setup dependency (domain-wide delegation) also has the potential to block the entire launch.

## Failure Chain

1. An auth subsystem enters an inconsistent state: Cloud Function fails, service account credentials expire, Firestore security rules are deployed incorrectly, or group membership cache is stale.
   - *Observation:* These are four distinct root causes, but they converge on the same symptom: the membership check returns the wrong result.
   - *Intervention point (prevention):* Automated health monitoring on the Cloud Function; alerts on service account expiry; Firestore rule tests in CI.

2. A user attempts to write (create/edit/delete) a work item.

3. The auth check returns an incorrect result.
   - *Branch A — False denial:* A legitimate team member is blocked from posting. Their card on the dashboard goes stale; they can't update their status. **Harm begins** (data quality, frustration).
   - *Branch B — False grant:* A non-team-member or recently-removed user can post items. **Harm begins** (misleading data, unauthorized access).

4. *Branch A:* The team member tries to report the issue.
   - *Intervention point (mitigation):* Clear error message telling them it's a permission issue, not a bug. Contact info for who to fix it.
   - *Intervention point (recovery):* Whoever manages the service account or Cloud Function can restore access; target: within 1 business day.

5. *Branch B:* An unauthorized post appears on the dashboard.
   - *Intervention point (detection):* Any team member or admin can flag/delete a post that doesn't belong to the right person.
   - *Intervention point (mitigation):* Firestore audit log captures who wrote what; root cause is identifiable.

6. **Harm ends** when the auth system is corrected and any bad data is removed.

## Observations

- **Severity:** High — Branch A (lockout) makes the tool unusable for affected team members. Branch B (unauthorized posts) is a security and trust issue.
- **Single point of failure:** The Cloud Function is the only way to verify group membership. If it's down, the app degrades hard.
- **Launch blocker:** Domain-wide delegation setup requires a Workspace admin. If this isn't arranged before build starts, it can delay the entire launch. Plan for it explicitly.
- **Related failures:** Failure 03 (external exposure) can be worsened if Firestore rules grant broader read access than intended.
- **Variants grouped here:**
  - *Group membership Cloud Function breaks write access*
  - *Stale membership cache allows unauthorized posts*
  - *Firestore rules misconfigured, users edit each other's items*
  - *Domain-wide delegation setup blocks or delays launch*

## Intervention Points

### Prevention
- Firestore security rules: each user can only write documents where `ownerUid == their UID`
- Cloud Function deployed with health check endpoint; monitored by uptime service
- Service account credential expiry monitored with calendar alert or automated renewal
- Membership cache refreshed on every login AND includes a max TTL (e.g., 24 hours)

### Detection
- Cloud Function error rate alert
- Automated test: attempt a cross-user write with a test account and verify it is rejected

### Mitigation
- Graceful degradation: if membership check fails, fail closed (deny write access) rather than fail open
- Clear in-app error message with support contact

### Recovery
- Documented runbook for restoring Cloud Function and rotating service account credentials
- Admin ability to manually override membership status for a user in Firestore

---

## Management Plan

[Not yet developed. Run failure management to develop a plan for this failure mode.]

## Management Plan

### Strategy

Layered technical defense. The architecture already encodes the most critical interventions (fail-closed Cloud Function, two-layer auth, Firestore rules as second check). This plan operationalizes those decisions and adds the monitoring and recovery components that make them maintainable. No significant tradeoffs — these are engineering hygiene steps with high value and low cost.

### Planned Interventions

- **Fail-closed Cloud Function** — if the membership check fails for any reason (network, quota, error), write `isTeamMember: false`. Never fail open.
  - Type: Prevention
  - Covers: chain step 3 (false grant branch) — unauthorized access is impossible if the function fails

- **Firestore security rules as second layer** — `isTeamMember == true AND ownerUid == caller.uid` enforced on all writes, independent of the Cloud Function result.
  - Type: Prevention
  - Covers: Firestore misconfiguration variant; also the case where isTeamMember is set incorrectly

- **Firestore rule tests in CI** — automated tests using the Firebase emulator verify: (a) a cross-user write is rejected, (b) a non-member write is rejected, (c) a valid team member write succeeds. Runs on every PR.
  - Type: Prevention (continuous)
  - Covers: misconfiguration introduced during development

- **24-hour membership cache TTL** — `membershipLastChecked` expires after 24 hours; Cloud Function re-verifies on the next login after expiry. This limits the window during which a removed member retains write access to at most 24 hours.
  - Type: Mitigation
  - Covers: stale membership cache variant

- **Cloud Function health monitoring** — uptime check or Firebase function error rate alert. If error rate exceeds threshold, Slack alert to named owner.
  - Type: Detection
  - Covers: chain step 1 (function enters inconsistent state) — owner is alerted before users notice

- **Service account credential rotation calendar reminder** — at time of service account creation, add a recurring annual reminder to rotate credentials. Store current expiry date in the ops runbook.
  - Type: Prevention
  - Covers: service account expiry variant

- **Ops runbook** — written document in team wiki covering: how to verify service account health, how to rotate credentials, how to manually override `isTeamMember` in Firestore for a user, how to redeploy the Cloud Function. This is the recovery path for any auth breakdown.
  - Type: Recovery
  - Covers: all variants — ensures any engineer can restore service without tribal knowledge

- **Domain-wide delegation pre-flight** — before the build sprint begins, confirm that a Google Workspace admin has configured the service account and granted domain-wide delegation. Block the first sprint day on this if needed; do not assume it can be done ad hoc.
  - Type: Prevention (launch blocker)
  - Covers: launch blocker variant

### Accepted Risks

Removed team members retain write access for up to 24 hours after removal (the cache TTL). For a normal offboarding this is acceptable. For an immediate termination, the named owner can manually set `isTeamMember: false` in Firestore as an emergency override — this is documented in the ops runbook.

Google infrastructure outages will temporarily disable auth entirely. This is accepted as a correlated failure with the broader company dependency on Google (Gmail, Meet, etc. are also down). No mitigation beyond graceful degradation message.

### Monitoring

- Cloud Function error rate alert: >5% error rate on `checkMembership` in any 15-minute window → Slack alert to named owner
- Firestore rule test failures in CI: blocks merge; treated as a P0 issue
- Annual calendar reminder for service account credential review
