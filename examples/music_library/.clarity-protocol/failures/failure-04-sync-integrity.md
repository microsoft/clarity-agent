# Failure: Sync Integrity — Library Drifts from Spotify

## Summary

The app's view of the user's library silently diverges from their actual Spotify library. Albums saved in Spotify don't appear in the app's inbox; albums removed from Spotify persist as ghost entries in categories. The user's carefully organized collection quietly fills with dead links or missing items, undermining trust in the tool without a clear error signal.

**Consequence category: Silent wrongness**

## Failure Chain

1. User saves or removes albums in Spotify (via mobile app, desktop, or web player).
2. The web app only syncs when opened — there's no background or push-based sync.
3. **Missing albums:** New saves accumulate in Spotify but don't appear in the app's inbox until the app is opened and sync runs.
   - *Observation:* This is an expected behavior gap, not a bug — but if the user doesn't realize it, they may think albums are missing.
4. **Ghost entries:** The sync logic adds new albums but may not detect removals. Albums the user has unsaved from Spotify remain in their categories indefinitely.
   - *Intervention point (prevention):* During each sync, compare the full Spotify library against Firestore albums and mark/remove entries no longer in Spotify.
5. **Harm begins.** User encounters ghost entries (clicking opens Spotify to an unrecognized or broken state) or notices albums they remember saving aren't in their collection.
6. Ghost entries accumulate over time. The collection degrades in quality — categories contain albums the user no longer has, distorting the browsing experience.
   - *Intervention point (detection):* When a deep link to Spotify returns an error or the album isn't in the user's library, surface a "this album may no longer be in your library" notice.
7. User manually audits and cleans up, or a future sync correctly handles removals.
   - *Intervention point (recovery):* Provide a "sync now" action that performs a full reconciliation (additions and removals).
8. **Harm ends** when sync is corrected and ghost entries are pruned.

## Observations

- **Severity:** Medium — the app remains functional but trust erodes gradually. Ghost entries are especially insidious because they look like real data.
- **Related failures:** Behavioral traps (failure-08) — a degraded, cluttered collection contributes to disengagement.
- **Variants:**
  - `20260302-201031` — Library sync misses albums added in Spotify between sessions
  - `20260302-201036` — Album removed from Spotify library still appears in categories

## Intervention Points

### Prevention
- Sync should reconcile both additions and removals, not just additions
- Incremental sync using Spotify's `added_after` timestamp for additions; periodic full reconciliation for removals

### Detection
- When a Spotify deep link is followed, detect if the album is no longer in the user's library and display a notice
- Surface last-sync timestamp so user can judge how fresh the data is

### Mitigation
- Mark ghost entries visually (e.g., dimmed) when they can't be verified against Spotify library

### Recovery
- Manual "sync now" that performs full library reconciliation
- Bulk-remove ghost entries after reconciliation

---

## Management Plan

### Strategy

Prevent both variants at the sync layer: sync must reconcile additions *and* removals, not just additions. Ghost entries are the more insidious problem (silent wrongness that accumulates); the missing-album case is lower stakes since those albums just sit in the inbox once the user opens the app. Provide a manual "sync now" escape hatch for when the user wants to force reconciliation.

### Planned Interventions

- **Bidirectional sync reconciliation**: On each sync, compare the full set of Spotify-saved albums against Firestore. Add new ones to the inbox; mark removed ones as unverified (or remove them, depending on user preference). This is the primary prevention for ghost entries.
  - Type: Prevention
  - Addresses: Chain step 4 (removals not detected)

- **Last-synced timestamp display**: Show "last synced X ago" in the UI so the user always knows how fresh the data is. Sets correct expectations about the on-open sync model.
  - Type: Detection
  - Addresses: Chain step 3 (user doesn't realize sync is on-open only)

- **Manual "sync now" action**: Allow the user to trigger a full reconciliation sync at any time, not just on app open. Important for cleaning up ghost entries after the sync logic is corrected.
  - Type: Recovery
  - Addresses: Chain steps 6–7 (recovering from accumulated ghost entries)

- **Ghost entry handling on deep link**: When a user clicks an album and Spotify indicates it's no longer in their library, show a clear notice ("This album is no longer in your Spotify library — remove it from your collection?") rather than silently doing nothing.
  - Type: Detection + Recovery
  - Addresses: Chain step 5 (ghost entries discovered only by clicking them)

### Accepted Risks

- New Spotify saves won't appear in the inbox until the app is next opened. Accepted — this is an intentional design choice (on-open sync), not a bug. The last-synced timestamp makes it transparent.
- Reconciliation requires fetching the full Spotify library periodically, which takes more API calls than incremental sync. Accepted — with conservative pagination (failure-02 intervention), this stays within rate limits.

### Monitoring

Last-synced timestamp visible in UI. No additional monitoring needed.
