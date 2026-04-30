# Failure: Organizational Data Permanently Lost

## Summary

All category structure, album assignments, and spatial layout are stored exclusively in Firestore. If the GCP project is deleted, billing lapses and the project is purged, or the user permanently loses access to the GCP account, all organization work is gone with no recovery path. Unlike the albums themselves (which live in Spotify), the organizational layer has no backup.

**Consequence category: Data loss**

## Failure Chain

1. User has built up a meaningful organizational structure over time — categories, assignments, spatial layout.
2. A project-level event destroys or revokes access to Firestore data:
   - GCP project accidentally deleted
   - Billing lapses; GCP purges the project after a grace period
   - User loses access to the GCP account (forgotten credentials, account issue)
3. **Harm begins.** All organizational data — categories, assignments, positions — is gone. The Spotify library itself is unaffected, but the collection is back to an unorganized state.
4. There is no export mechanism, no backup, no way to reconstruct the work.
   - *Observation:* This is qualitatively worse than the app just being broken — the user has lost the accumulated value of all their organizing work. The albums still exist in Spotify; it's the organizational layer that's gone forever.
5. User must start over from scratch, or give up on the tool entirely.
6. **Harm ends** — but the lost work is not recovered.

## Observations

- **Severity:** High — permanent, irreversible loss of accumulated work. The effort to rebuild is proportional to how long and how actively the user has organized their collection.
- **Related failures:** Behavioral traps (failure-08) — data loss is the terminal version of abandonment; the app stops being useful not by choice but by accident.
- **Variants:**
  - `20260302-201041` — Organization data lost if Firestore project is deleted or abandoned

## Intervention Points

### Prevention
- Document the GCP project clearly (project ID, billing account) so credentials and access aren't accidentally lost
- Enable GCP billing alerts to prevent surprise project suspension

### Detection
- N/A — data loss at the infrastructure level is not detectable in advance

### Mitigation
- Implement data export: a "download my library as JSON" function that captures categories, assignments, and positions
- Periodic automated backup of Firestore data (e.g., Firestore scheduled export to Cloud Storage)

### Recovery
- Without a backup: no recovery possible
- With export/backup: restore from most recent export; some recent changes may be lost

---

## Management Plan

### Strategy

Mitigation-first. Prevention (GCP hygiene) reduces the likelihood of infrastructure events; a manual export feature eliminates the worst-case outcome (permanent loss) by keeping a portable copy of organizational data outside GCP entirely. Automated backup is deferred — it adds infrastructure complexity and doesn't protect against GCP account loss the way a portable export does.

### Planned Interventions

**Short-term:**

- **GCP project documentation**: Record the project ID, billing account, and GCP credentials somewhere outside the project (password manager, etc.) before going live.
  - Type: Prevention
  - Addresses: Chain step 2 (lost account access)

- **GCP billing alerts**: Configure alerts at 80% of any free-tier quota and for any unexpected charges.
  - Type: Prevention
  - Addresses: Chain step 2 (billing lapse / project suspension)

- **Manual data export ("Download my library")**: A button in the app that exports the full organizational state — categories, assignments, positions — as a human-readable JSON file. Should be accessible even if Spotify sync is broken.
  - Type: Mitigation
  - Addresses: Chain step 4 (no recovery path without backup)

**Long-term (when it feels worth the complexity):**

- **Automated Firestore scheduled export to Cloud Storage**: Set up GCP's built-in Firestore export on a cron (e.g., weekly). Provides a safety net without user action, but doesn't protect against full GCP account loss.
  - Trigger: If the manual export is rarely used and the collection has grown to the point where weeks of re-organization would be a significant loss.

### Accepted Risks

- If the user loses GCP account access *and* has never exported their data, organizational work is permanently lost. This risk is accepted — it requires two concurrent failures (account loss + no export habit) and the mitigation (export button) is always available.
- The most recent changes since the last export are always at risk. Accepted — the export is a manual action and some staleness is inherent.

### Monitoring

No automated monitoring needed. The intervention (export) is user-initiated. GCP billing alerts cover the infrastructure side.
