# Failure: Deep Link Fails Silently

## Summary

Clicking an album to open it in Spotify fails silently — either because the Spotify app isn't installed, or because the browser blocks the `spotify://` URI scheme. The user gets a dead click with no feedback. This is the one moment in the browsing flow that hands off to Spotify, so a silent failure here defeats the primary use of the app.

**Consequence category: Silent wrongness**

## Failure Chain

1. User browses their library, finds an album they want to play, and clicks it.
2. App fires a `spotify://album/{id}` URI.
3. The URI fails via one of two routes:
   - **No Spotify app:** The device doesn't have the Spotify desktop/mobile app installed; the OS has no handler for the `spotify://` scheme. The browser silently does nothing, or shows a generic "no application found" error.
   - **Browser blocks URI:** Some browsers (especially on desktop) block custom URI schemes by default or prompt for permission. The user dismisses the prompt or doesn't notice it, and nothing opens.
4. **Harm begins.** The user clicked something expecting Spotify to open. Nothing happened. No error, no alternative.
   - *Intervention point (mitigation):* Implement a fallback: after a short timeout with no navigation, open `https://open.spotify.com/album/{id}` in a new tab. This works universally.
5. User is confused — is the app broken? Is the album missing? They may try clicking again, or give up.
6. **Harm ends** when user discovers the fallback (if implemented) or navigates to Spotify manually.

## Observations

- **Severity:** Medium — the browsing flow completely fails at its final step. Repeated occurrences (e.g., always using a browser without the Spotify app) make the app frustrating to use.
- **Observation:** The fallback (web URL) is fully sufficient — Spotify's web player is capable. The only reason to prefer the URI is to open the native app when available. A graceful fallback eliminates this failure mode almost entirely.
- **Variants:**
  - `20260302-201108` — Deep link fails silently when Spotify app not installed
  - `20260302-201206` — Browser blocks spotify:// URI, playback never opens

## Intervention Points

### Prevention
- Use a reliable deep link pattern: fire `spotify://` URI and simultaneously set a timeout; if page hasn't navigated away, open the web URL fallback

### Detection
- Listen for the `visibilitychange` or `blur` event as a heuristic for whether the native app opened; if not triggered, assume failure

### Mitigation
- Always provide a visible "Open in Spotify" web link alongside or as fallback to the URI

### Recovery
- User can manually open Spotify and search — but this should not be necessary if fallback is implemented

---

## Management Plan

### Strategy

Implement the universal fallback pattern — fire the native URI, detect failure via a short timeout, open the web URL if the app didn't open. This eliminates the failure mode almost entirely with minimal complexity. A visible "Open in Spotify" link alongside the album also gives the user a reliable manual path.

### Planned Interventions

- **Deep link with timeout fallback**: On album click, fire `spotify://album/{id}` and simultaneously set a short timeout (~500ms). Listen for `visibilitychange` or `blur` as a signal the native app opened. If neither fires within the timeout, open `https://open.spotify.com/album/{id}` in a new tab as fallback.
  - Type: Prevention + Mitigation
  - Addresses: Chain steps 2–4 (silent failure with no alternative)

- **Visible "Open in Spotify" web link**: Show a direct `open.spotify.com` link alongside or beneath the album title in the detail view. Always visible, always works, regardless of native app state. Eliminates the "dead click with no alternative" experience entirely.
  - Type: Mitigation
  - Addresses: Chain step 5 (user doesn't know what to do after a failed click)

### Accepted Risks

- The `visibilitychange`/`blur` heuristic is imperfect — some browsers may not reliably fire these events. In the worst case, the user gets both the native app and a new tab opening. Accepted — harmless.
- Some browsers block new tabs opened programmatically. Accepted — the visible web link provides a reliable manual fallback in that case.

### Monitoring

None needed — the fallback is automatic.
