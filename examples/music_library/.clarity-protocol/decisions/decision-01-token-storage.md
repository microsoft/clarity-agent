# Decision: Where to Store Spotify OAuth Tokens

**Status:** decided
**Decided:** March 2026
**Context:** Failure management for security misconfiguration (failure-08)

## The Question

Should Spotify OAuth tokens be stored in Firestore (readable by the frontend, secured by security rules), or held server-side only in Cloud Functions (never exposed to the client)?

## Options Considered

**Option A — Tokens in Firestore, secured by security rules** *(chosen)*

The frontend holds a Firebase Auth session and can read its own Firestore documents, including tokens. Cloud Functions handle the OAuth flow and token refresh; the frontend uses the access token to call Spotify's API directly.

- Simpler architecture — frontend calls Spotify directly, less Cloud Function logic
- Tokens are accessible if security rules are misconfigured (mitigated by strict rules from day one)
- Easier to develop and debug

**Option B — Tokens server-side only**

Tokens live in Cloud Function memory or Secret Manager. The frontend holds only a session cookie. All Spotify API calls are proxied through Cloud Functions.

- No token exposure risk regardless of Firestore rules
- Significantly more Cloud Function complexity — every Spotify API call goes through a function
- Higher latency, more infrastructure to maintain

## Decision

**Option A.** The blast radius of token exposure for a single-user personal music library app is low — the tokens grant access to a Spotify account, not financial or sensitive personal data. The architectural simplicity of Option A is worth preserving, especially given the design principle of keeping the app minimal and maintainable.

The risk is mitigated by strict Firestore security rules (enforced before first deployment) and minimizing what's stored in Firestore (refresh token only; access token held in memory).

## Assumptions

- This is a single-user personal tool. No other users' data is at risk.
- The Spotify account is not linked to payment methods or unusually sensitive personal information beyond listening history.
- The developer will set and maintain strict Firestore security rules.

## Reconsideration Triggers

- If the app expands to multiple users — server-side token storage becomes necessary, as Firestore rules become significantly harder to get right across users.
- If Spotify tokens are ever used to access more sensitive capabilities (e.g., payment, account management).
- If a security incident occurs (tokens accessed by unauthorized party) — immediately revisit.
- If maintaining Cloud Function complexity becomes easier than expected, the calculus shifts.
