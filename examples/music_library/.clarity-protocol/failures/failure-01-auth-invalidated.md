# Failure: Auth State Invalidated

## Summary

The app's Spotify authentication becomes invalid — tokens expire, are revoked, or are invalidated by a password change — and the app fails to recover gracefully. The user is left in a broken state without a clear path to re-authenticate. As a personal tool with no support channel, the user is their own debugger.

**Consequence category: App stops working**

## Failure Chain

1. User has an authenticated session; access and refresh tokens are stored in Firestore.
2. Auth state becomes invalid via one of three routes:
   - Access token expires (happens every hour, expected)
   - Refresh token revoked (Spotify security event, user deauthorizes app)
   - Spotify password change (invalidates all tokens immediately)
3. App attempts an operation requiring a valid token (library fetch, sync check).
   - *Intervention point (prevention):* Proactive token refresh before expiry avoids the most common case.
4. API call returns 401 Unauthorized.
5. App must distinguish between "token expired, try refreshing" and "refresh token invalid, re-auth required." If it doesn't, it may silently retry, loop, or show a generic error.
   - *Intervention point (detection):* Distinct error handling for 401 vs. refresh failure; clear UI state for "session expired."
6. **Harm begins.** App is non-functional. User sees empty library, stale state, or an unhelpful error.
7. User doesn't know whether to wait, reload, or re-authenticate. They may try reloading multiple times.
   - *Intervention point (mitigation):* Explicit "reconnect with Spotify" CTA shown on auth failure, not buried in settings.
8. User re-authenticates via full OAuth flow.
9. **Harm ends.** App resumes normal operation.

## Observations

- **Severity:** Medium — app is fully non-functional until re-auth, but no data is lost and recovery is straightforward if the UI makes the path clear.
- **Related failures:** Security misconfiguration (failure-04) — tokens stored in Firestore are the target of that failure; this failure is the experience when those tokens go bad legitimately.
- **Variants:**
  - `20260302-201011` — Spotify OAuth token expires and app silently breaks
  - `20260302-201016` — Spotify refresh token revoked, user loses access with no recovery path
  - `20260302-201201` — Spotify account password change invalidates app session with no graceful handling

## Intervention Points

### Prevention
- Proactively refresh access tokens before expiry (e.g., refresh when <5 min remaining)
- Detect refresh token failure immediately and flag for re-auth rather than retrying

### Detection
- Distinguish 401 (expired token) from refresh failure (revoked/invalid) in error handling
- Surface auth failure state clearly in UI — not just a broken/empty view

### Mitigation
- Show a prominent, actionable "Reconnect with Spotify" prompt on auth failure
- Preserve the user's current view/state so nothing is lost when they re-authenticate

### Recovery
- Full OAuth re-authentication flow
- No data loss — all organization data is in Firestore and unaffected by token state

---

## Management Plan

### Strategy

Layered: prevent the most common case (token expiry) automatically, detect the rarer cases (revocation, password change) quickly, and make recovery a single clear action rather than a debugging exercise. The app should never leave the user staring at an empty screen with no explanation.

### Planned Interventions

- **Proactive token refresh**: Refresh the access token before it expires (e.g., when <5 minutes remain), not reactively after a 401. Eliminates the most common auth failure entirely.
  - Type: Prevention
  - Addresses: Chain steps 2–4 (token expiry reaching the user)

- **Typed error handling for auth failures**: Distinguish between "access token expired, refresh succeeded" (transparent), "refresh token invalid, re-auth required" (show prompt), and "unknown auth error" (show generic error with retry). Never show a blank screen.
  - Type: Detection + Mitigation
  - Addresses: Chain step 5 (app can't distinguish error types)

- **Prominent "Reconnect with Spotify" CTA**: On any unrecoverable auth failure, show a clear, prominent reconnect prompt — not buried in settings, not a generic error message. Include a brief explanation ("Your Spotify connection expired — tap to reconnect").
  - Type: Mitigation
  - Addresses: Chain steps 6–7 (user confused about what to do)

- **Preserve UI state through re-auth**: The user's current view (which category they were in, which album they were looking at) should survive re-authentication. Don't dump them back to the home screen.
  - Type: Mitigation
  - Addresses: Chain step 7 (unnecessary disruption during recovery)

- **"Doctor" command coverage**: The health check (failure-09 intervention) should include Spotify token status — valid, expiring soon, or invalid — so the user can diagnose auth problems without opening the app and hitting an error.
  - Type: Detection
  - Addresses: Chain step 4 (user doesn't know auth is broken until they use the app)

### Accepted Risks

- If the user is offline, re-authentication is impossible until connectivity is restored. The app can degrade gracefully to read-only browsing of cached Firestore data in the interim.
- Proactive refresh adds a small amount of Cloud Function invocation overhead. Accepted — negligible for a personal tool.

### Monitoring

Covered by "doctor" command. No continuous monitoring.
