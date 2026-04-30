# Failure: Spotify API Dependency Breaks

## Summary

The app stops functioning because Spotify's API changes in a way the app doesn't handle — endpoints are deprecated, response schemas change, rate limits are hit during a large sync, or Spotify experiences an outage. Since the entire library is sourced from Spotify, any sustained API disruption makes the app useless for browsing.

**Consequence category: App stops working**

## Failure Chain

1. App makes Spotify API calls (on load, during sync, or when refreshing library data).
2. API call fails or returns unexpected data via one of several routes:
   - Spotify outage or degraded service (temporary)
   - Rate limit hit during paginated full-library resync (hundreds of albums)
   - Endpoint deprecated or response schema changed (permanent until app is updated)
3. App receives error response or malformed data.
   - *Intervention point (detection):* Structured error handling per failure type — rate limit (429 + Retry-After) vs. outage (503) vs. schema change (unexpected field shape).
4. **Harm begins.** Library data is stale, partial, or unavailable. User can't browse new albums or may see an incomplete collection.
5. For temporary failures (outage, rate limit): failure resolves when Spotify recovers or cooldown expires.
   - *Intervention point (mitigation):* Exponential backoff and retry for transient failures; show cached data with a "last synced X ago" indicator rather than an empty state.
6. For permanent changes (deprecation): app stays broken until the developer (the user) updates the code.
   - *Intervention point (detection):* Monitoring or alerting on repeated API errors would surface this faster than noticing the app is stale.
7. **Harm ends** when Spotify recovers (transient) or app is updated (permanent).

## Observations

- **Severity:** Medium for outages (temporary, cached data usable); High for schema/deprecation changes (requires developer intervention, no timeline).
- **Related failures:** Auth invalidated (failure-01) — 401 errors are a distinct failure type handled separately. Infrastructure failure (failure-03) — GCP-side failures have similar UX but different causes.
- **Variants:**
  - `20260302-201124` — Spotify changes or deprecates API endpoints used by the app
  - `20260302-201059` — Spotify API rate limit hit during full library resync

## Intervention Points

### Prevention
- Paginate full-library syncs conservatively to stay within rate limits
- Use incremental sync (only fetch albums added since last sync timestamp) to avoid full resyncs

### Detection
- Differentiate error types: 429 (rate limit), 503 (outage), unexpected schema (deprecation signal)
- Log API errors persistently so patterns are visible over time

### Mitigation
- Serve cached Firestore data when Spotify API is unavailable; display last-synced timestamp
- Exponential backoff with jitter for transient failures

### Recovery
- For outages: automatic recovery when Spotify service resumes
- For deprecation: developer updates API integration; no data loss (organization data unaffected)

---

## Management Plan

### Strategy

Serve cached data for transient failures; accept developer intervention for permanent ones. The organizing data lives in Firestore and is unaffected by Spotify API failures — the worst case is that new albums don't appear until the API recovers. The "doctor" command (failure-09 intervention) surfaces API error state so the user doesn't have to discover it by noticing their library is stale.

### Planned Interventions

- **Incremental sync with timestamp**: On each app open, only fetch albums added after the last known sync timestamp. Avoids full resyncs, stays well within rate limits even with a large library.
  - Type: Prevention
  - Addresses: Chain step 2 (rate limit hit during full resync)

- **Typed error handling**: Distinguish 429 (rate limit, backoff and retry), 5xx (outage, retry with exponential backoff), and unexpected schema (log prominently, surface in doctor command).
  - Type: Detection + Mitigation
  - Addresses: Chain step 3 (all errors treated the same)

- **Serve cached Firestore data during API failures**: If the Spotify API is unavailable, show the library as it was at last sync with a "last synced X ago" notice. Don't show an error screen — the collection is still fully browsable.
  - Type: Mitigation
  - Addresses: Chain step 4 (user can't browse at all during outage)

- **"Doctor" command coverage**: Include last successful Spotify API call timestamp and any recent API errors. Makes deprecation/schema changes visible without requiring the user to notice stale data.
  - Type: Detection
  - Addresses: Chain step 6 (permanent breakage discovered late)

### Accepted Risks

- A Spotify API deprecation may require developer intervention with no warning. Accepted — this is an external dependency risk inherent to the platform. The mitigations (cached data, doctor command) ensure it's survivable and diagnosable.
- Incremental sync may miss edge cases (e.g., Spotify backdates an album's `added_at` timestamp). Accepted — a manual "full sync now" option provides a recovery path.

### Monitoring

Covered by "doctor" command. No continuous monitoring.
