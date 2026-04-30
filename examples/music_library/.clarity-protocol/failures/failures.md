# Failure Modes

11 failure modes identified from 16 raw failures (broad analysis, March 2026). 11 have management plans.

Failures are organized by **consequence category** — what kind of harm occurs, not just what breaks. This framing emerged from analysis and is more useful for design than a flat severity ranking.

## App Stops Working

Failures where the app becomes non-functional. These have clear error signals and defined recovery paths — they're engineering problems with known solutions.

| # | Failure | Severity | Strategy |
|---|---------|----------|---------|
| [01](failure-01-auth-invalidated.md) | Auth State Invalidated | Medium | Proactive refresh + typed error handling + clear re-auth CTA |
| [02](failure-02-spotify-api-dependency.md) | Spotify API Dependency Breaks | Medium–High | Serve cached data; incremental sync; doctor command |
| [03](failure-03-infrastructure.md) | Infrastructure Failure or Quota Exhaustion | Low–High | Defensive writes; quota alerts; billing cap as backstop |

## Silent Wrongness

Failures where the app appears functional but shows incorrect state. No error signal — the user must notice something is wrong themselves, which may take days or never happen.

| # | Failure | Severity | Strategy |
|---|---------|----------|---------|
| [04](failure-04-sync-integrity.md) | Sync Integrity — Library Drifts from Spotify | Medium | Bidirectional sync (additions + removals); last-synced timestamp |
| [05](failure-05-concurrent-writes.md) | Concurrent Write Conflict | Low | Accept; undo toast as recovery |
| [06](failure-06-deep-link.md) | Deep Link Fails Silently | Medium | Timeout fallback to web URL; visible web link |

## Data Loss

Failures where accumulated work is permanently destroyed. Unlike "app stops working," recovery is impossible or incomplete.

| # | Failure | Severity | Strategy |
|---|---------|----------|---------|
| [07](failure-07-data-loss.md) | Organizational Data Permanently Lost | High | Manual export ("Download my library"); GCP billing alerts |
| [08](failure-08-security-misconfiguration.md) | Security Misconfiguration Exposes Tokens | High | Strict Firestore rules from day one; minimize token storage in Firestore |

## Behavioral Traps

Failures that emerge from usage patterns over time, not technical bugs. No error signal — the tool just quietly becomes less useful, then unused.

| # | Failure | Severity | Strategy |
|---|---------|----------|---------|
| [09](failure-09-behavioral-traps.md) | Behavioral Traps — The Tool Defeats Itself | High | Low-pressure UX; fire-and-forget architecture; doctor command; data export |
| [10](failure-10-accidental-misorganization.md) | Accidental Mis-organization | Low–Medium | Undo toast; mobile touch target sizing |

## Experience Degradation

Failures where the app works technically but the core experience is undermined.

| # | Failure | Severity | Strategy |
|---|---------|----------|---------|
| [11](failure-11-spatial-layout.md) | Spatial Layout Breaks Across Screen Sizes | Medium | Responsive layout approach chosen during prototyping; per-device layout storage if needed |

---

## Cross-Cutting Patterns

**Undo toast** (failures 05, 10): A single mechanism — show what was just applied, offer immediate reversal — addresses both concurrent write conflicts and accidental mis-assignments.

**"Doctor" command** (failures 01, 02, 03, 09): A single health-check diagnostic covers auth state, Spotify API status, GCP quota, and last-sync timestamp. Replaces the need for continuous monitoring across multiple "app stops working" failure modes, and keeps maintenance burden low.

**Data export** (failures 07, 09): The manual export feature eliminates worst-case data loss *and* de-risks abandonment — stopping maintenance becomes a low-stakes decision rather than a potentially catastrophic one.

**Cached Firestore data during outages** (failures 01, 02, 03): All three "app stops working" failures degrade gracefully to read-only browsing of cached data, rather than showing an error screen.

**Bidirectional sync** (failure 04): Sync must reconcile removals as well as additions — a single design requirement that prevents the silent wrongness of ghost entries accumulating over time.

**Responsive layout from the start** (failure 11): The spatial layout approach must be chosen before building — retrofitting is significantly harder. This is an architecture input.

## Coverage

Perspectives examined:
- Broad analysis — March 2026
