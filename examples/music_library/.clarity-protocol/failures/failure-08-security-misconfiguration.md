# Failure: Security Misconfiguration Exposes Tokens

## Summary

Firestore security rules that are too permissive — left at development defaults or misconfigured — allow an attacker who knows the user's Firestore userId to read the stored Spotify access and refresh tokens. This gives them persistent access to the user's Spotify account, not just the music library app.

**Consequence category: Data loss** (account compromise — loss of control over Spotify account)

## Failure Chain

1. During development, Firestore security rules are left permissive (e.g., `allow read, write: if true`) or misconfigured to allow unauthenticated reads of the `users/{userId}/spotifyTokens` path.
2. App is deployed to production without tightening the rules.
   - *Intervention point (prevention):* Firestore security rules should be set to require authenticated access and enforce that users can only read their own data before any deployment.
3. An attacker discovers the Firebase project ID (visible in the frontend JS bundle) and the userId (also potentially visible).
4. Attacker reads the `spotifyTokens` document directly via the Firestore REST API.
5. **Harm begins.** Attacker has the user's Spotify refresh token — persistent access to the Spotify account, independent of the app.
6. Attacker can use the token to read listening history, modify playlists, or act on behalf of the user in Spotify.
7. Spotify tokens don't expire until revoked. The user has no indication this has happened.
   - *Intervention point (detection):* Spotify's "Connected Apps" page shows authorized sessions; anomalous activity would appear there.
8. User revokes app access in Spotify, invalidating the stolen tokens.
   - *Intervention point (recovery):* Revoke app in Spotify → re-authenticate → tokens are rotated.
9. **Harm ends** after token revocation and re-authentication.

## Observations

- **Severity:** High — this is the only failure mode that affects an account outside the app itself (the user's Spotify account). Token theft gives persistent, hard-to-detect external access.
- **Observation:** This failure is entirely preventable with correct Firestore security rules — it's a setup/deployment hygiene issue, not a fundamental architectural flaw.
- **Related failures:** Auth invalidated (failure-01) — token revocation is the recovery step here; it triggers failure-01 as a side effect.
- **Variants:**
  - `20260302-201027` — Firestore security rules misconfigured, tokens exposed

## Intervention Points

### Prevention
- Set strict Firestore security rules before first deployment: only authenticated users can read their own data
- Store tokens server-side only (in Cloud Functions environment variables or Secret Manager) rather than in Firestore documents readable by the client

### Detection
- Review Firestore security rules in CI/deployment checklist
- Monitor Spotify "Connected Apps" for unexpected sessions

### Mitigation
- Limit token storage to the minimum necessary; don't store access tokens in Firestore if they can be held in memory or short-lived session cookies instead

### Recovery
- Revoke app access in Spotify (invalidates all tokens)
- Re-authenticate to generate fresh tokens
- Audit Spotify listening history for unauthorized activity

---

## Management Plan

### Strategy

Prevention through correct configuration, not architectural change. Tokens remain in Firestore (simpler architecture, frontend calls Spotify API directly), secured by strict Firestore security rules. The low practical value of these tokens — access to a music library app for a single personal user — makes this residual risk acceptable in exchange for architectural simplicity. This decision is explicitly recorded and flagged for reconsideration if scope expands.

### Planned Interventions

- **Strict Firestore security rules from day one**: Rules must require Firebase Authentication and restrict reads/writes to the authenticated user's own documents before any deployment, even during development.
  - Type: Prevention
  - Addresses: Chain steps 1–2 (permissive rules deployed to production)

- **Deployment checklist item**: Firestore security rules review is a mandatory step before going live. Not automated — just a written checklist. Simple enough to actually do.
  - Type: Prevention
  - Addresses: Chain step 2 (rules not tightened before deploy)

- **Minimize access token storage in Firestore**: Store only the refresh token and expiry in Firestore; hold the short-lived access token in memory only (or a short-lived HttpOnly cookie). This limits what an attacker can steal even if rules are misconfigured.
  - Type: Mitigation
  - Addresses: Chain steps 3–5 (attacker reads tokens from Firestore)

### Accepted Risks

- A sufficiently determined attacker who discovers the project ID and bypasses Firebase Auth could potentially exploit a misconfiguration introduced in the future. Accepted — the blast radius is limited to a personal Spotify account, not financial or sensitive personal data.
- This architecture is less secure than moving tokens fully server-side. That tradeoff is explicitly accepted in favor of simplicity; the decision is recorded separately.

### Monitoring

No automated monitoring. Manual: periodically check Spotify's "Connected Apps" page for unexpected active sessions. If the architecture grows (multi-user, sensitive data), revisit the token storage approach before expanding.
