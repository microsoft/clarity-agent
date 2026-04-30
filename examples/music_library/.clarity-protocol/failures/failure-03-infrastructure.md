# Failure: Infrastructure Failure or Quota Exhaustion

## Summary

GCP infrastructure issues — Cloud Function cold starts, free tier quota exhaustion triggered by a runaway sync loop, or platform-level outages — make the app unavailable or severely degraded. Because this is a free-tier personal project, there's no billing headroom and no proactive monitoring.

**Consequence category: App stops working**

## Failure Chain

1. App is used normally, or a background process (sync, token refresh) runs.
2. Infrastructure fails via one of two routes:
   - **Cold start:** Cloud Function hasn't been invoked in a while; first call takes several seconds. User clicks "Connect with Spotify," nothing appears to happen.
     - *Intervention point (mitigation):* Show a loading indicator immediately on auth initiation so the user knows something is happening.
   - **Quota exhaustion:** A bug causes excessive Firestore reads/writes (e.g., a sync loop). Free tier quota is consumed. All Cloud Function invocations or Firestore operations fail until quota resets (next billing cycle) or billing is enabled.
3. **Harm begins.** App is partially or fully non-functional. Cold start: user retries unnecessarily, may create duplicate auth state. Quota: app is completely broken for days with no warning.
   - *Intervention point (detection):* GCP provides quota alerts — configure them to fire before exhaustion, not after.
4. For cold starts: resolves on its own within seconds once the function warms up.
5. For quota exhaustion: app stays broken until quota resets or billing is enabled.
   - *Intervention point (recovery):* Enable GCP billing with a spending cap as a backstop — quota issues are unblocked immediately, costs remain bounded.
6. **Harm ends** when infrastructure recovers or quota is restored.

## Observations

- **Severity:** Low for cold starts (cosmetic, self-resolving); High for quota exhaustion (extended outage, potentially confusing to diagnose).
- **Related failures:** Spotify API dependency (failure-02) — similar UX (app seems broken) but different cause and recovery path.
- **Variants:**
  - `20260302-201119` — GCP free tier limits exceeded, app stops working unexpectedly
  - `20260302-201157` — Cloud Function cold start delays OAuth flow, user thinks app is broken

## Intervention Points

### Prevention
- Write Firestore operations defensively — avoid loops that could trigger runaway reads/writes
- Keep sync logic idempotent and bounded

### Detection
- Configure GCP quota alerts to fire at 80% consumption, not 100%
- Log Cloud Function invocation counts to detect anomalous patterns

### Mitigation
- Show immediate loading state on all async operations to prevent user confusion during cold starts
- Display a meaningful error (not a blank screen) when infrastructure calls fail

### Recovery
- Cold start: self-resolving; no action needed
- Quota exhaustion: enable billing with a spending cap, or wait for quota reset

---

## Management Plan

### Strategy

Cold starts are cosmetic — just show a loading state and they resolve themselves. Quota exhaustion is the real risk; prevent it through defensive coding and get early warning from GCP alerts. Enable billing with a spending cap as a backstop so quota issues can be unblocked immediately without the app being broken for days.

### Planned Interventions

- **Loading state on all async operations**: Every Cloud Function call shows an immediate loading indicator. Users see something is happening; cold start latency is not perceived as a failure.
  - Type: Mitigation
  - Addresses: Chain step 2 (cold start perceived as broken app)

- **Defensive Firestore writes**: All sync and write operations are idempotent and bounded — no unbounded loops, no writes triggered by reads without a clear termination condition. Code review this before deploying.
  - Type: Prevention
  - Addresses: Chain step 2 (runaway reads/writes exhausting quota)

- **GCP quota alerts at 80%**: Configure billing alerts to fire before quota is exhausted. Gives time to investigate and act before the app breaks.
  - Type: Detection
  - Addresses: Chain step 3 (quota exhaustion discovered only after app breaks)

- **Enable billing with a spending cap**: Set a low spending cap (e.g., $5/month) so quota exhaustion can be immediately unblocked by enabling billing rather than waiting for the next reset cycle. At personal-use scale, actual costs should be effectively zero.
  - Type: Recovery
  - Addresses: Chain step 5 (app broken for days waiting for quota reset)

- **"Doctor" command coverage**: Include GCP quota status and Cloud Function error rates.
  - Type: Detection
  - Addresses: Chain step 3 (quota issues not visible without checking GCP console)

### Accepted Risks

- A platform-level GCP outage would break the app regardless of these interventions. Accepted — this is extremely rare, temporary, and outside our control.
- Cold start latency on the OAuth flow is inherent to serverless architecture. Accepted — it's cosmetic if loading state is shown.

### Monitoring

GCP quota alerts (automated). "Doctor" command for on-demand diagnosis.
