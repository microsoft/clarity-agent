# Failure: Accidental Mis-organization

## Summary

The user accidentally assigns an album to the wrong category — via a mis-tap on mobile, a misread autocomplete suggestion, or a slip of the hand — and has no way to undo it. They must remember what they did and manually correct it, which on mobile with imprecise touch targets is frustrating and easy to compound.

**Consequence category: Behavioral traps** (erodes confidence in the tool; makes organizing feel risky)

## Failure Chain

1. User performs a quick organize action: right-click album → select category from autocomplete → confirm.
2. The action completes incorrectly via one of:
   - Mis-tap on mobile selects the wrong autocomplete suggestion
   - User misreads a similarly-named category
   - Touch target is too small; adjacent item is activated
3. Firestore is updated immediately. The change propagates to all devices.
   - *Intervention point (prevention):* A brief confirmation or undo window before the write commits would catch immediate errors.
4. **Harm begins.** The album is in the wrong category. The user may not notice immediately.
5. Later, the user can't find an album where they expect it, or notices it in a wrong category.
   - *Observation:* The longer the delay before noticing, the harder it is to remember what the correct state should have been.
6. User must manually locate the album and reassign it.
   - *Intervention point (mitigation):* An undo action (in-session, "undo last change") makes recovery trivial if the error is caught immediately.
   - *Intervention point (recovery):* A change history log allows the user to see recent assignments and reverse them.
7. **Harm ends** when correct assignment is restored.

## Observations

- **Severity:** Low for a single incident; Medium if repeated errors erode trust in the organizing workflow, causing the user to slow down or stop using it.
- **Observation:** The risk of accidental assignment is inherently higher on mobile due to touch imprecision and smaller targets. The right-click + autocomplete flow was designed for desktop; the mobile equivalent needs careful UX attention.
- **Related failures:** Concurrent writes (failure-05) — both produce wrong assignments; this one is user-caused, that one is system-caused. An undo mechanism addresses both.
- **Variants:**
  - `20260302-201151` — Accidental album assignment to wrong category with no undo

## Intervention Points

### Prevention
- On mobile: use a larger touch target for category selection; add a confirmation step for assignments
- Autocomplete should rank frequently-used categories higher to reduce mis-selection

### Detection
- N/A — the user must notice the wrong state themselves

### Mitigation
- Undo last action (in-session, keyboard shortcut on desktop, shake or toast on mobile)
- Toast notification after assignment showing what was done, with an "Undo" button (standard mobile pattern)

### Recovery
- Change history: a short log of recent assignment actions with a "revert" option
- Manual reassignment

---

## Management Plan

### Strategy

Undo toast as the primary mechanism — shared with failure-05 (concurrent writes). Both failures produce wrong assignments; both are fixed by the same pattern: show what was just applied, let the user reverse it immediately. Mobile UX gets additional attention on touch target sizing to reduce the incidence of mis-taps in the first place.

### Planned Interventions

- **Undo toast on assignment**: After every assignment write, show a toast ("Added to Late Night — Undo") for 4–5 seconds with an Undo button. On mobile, this is the standard pattern for reversible actions and users expect it. Shared with failure-05.
  - Type: Mitigation
  - Addresses: Chain steps 3–4 (write commits immediately with no reversal path)

- **Mobile touch target sizing**: Category items in the assignment autocomplete must meet minimum touch target size (44×44pt per Apple HIG / 48×48dp per Material). Test on actual mobile devices before shipping.
  - Type: Prevention
  - Addresses: Chain step 2 (mis-tap on mobile selects wrong category)

- **Autocomplete ranking**: Surface recently-used categories first in autocomplete. Reduces the likelihood of mis-selecting an unfamiliar or rarely-used category that happens to share a name prefix.
  - Type: Prevention
  - Addresses: Chain step 2 (misread autocomplete suggestion)

- **In-session undo stack**: Same mechanism as failure-05 — maintain a short in-memory stack of recent writes, reversible via undo button or keyboard shortcut (Cmd+Z / Ctrl+Z on desktop).
  - Type: Recovery
  - Addresses: Chain step 6 (user must manually locate and reassign)

### Accepted Risks

- If the user doesn't notice the toast and closes the app, the mis-assignment persists. They'd need to manually find and fix it. Accepted — the organizing data is never lost, just misplaced; manual correction is always possible.

### Monitoring

None — user-noticed via unexpected library state or undo toast.
