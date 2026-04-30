# Failure: Concurrent Write Conflict

## Summary

The user edits their library organization simultaneously from two devices. Firestore's last-write-wins behavior silently overwrites one set of changes with another. The user ends up with an unexpected assignment state and no indication anything was overwritten — the change just looks "wrong" with no error.

**Consequence category: Silent wrongness**

## Failure Chain

1. User has the app open on both phone and desktop.
2. Both devices have a live Firestore listener and show the same library state.
3. User makes an assignment on the phone (e.g., moves an album to "Jazz").
4. Simultaneously, the desktop writes a different assignment for the same album (e.g., to "Late Night").
5. Both writes are sent to Firestore nearly simultaneously.
6. Firestore applies last-write-wins. One write overwrites the other without conflict notification.
   - *Observation:* For a single user, true simultaneity is unlikely but possible — more likely is one device having stale state and writing over a change made on the other device seconds earlier.
7. **Harm begins.** The real-time listener propagates the winning write to both devices. One device's UI suddenly shows a different assignment than the user just made, with no explanation.
8. User notices the assignment looks wrong. They don't know if it was their own mistake or a sync issue.
   - *Intervention point (detection):* Optimistic UI with a brief window to detect conflicts before committing, or a change history / audit log.
9. User manually re-applies the intended assignment.
   - *Intervention point (mitigation):* Undo capability (even just "undo last change") would make recovery trivial.
10. **Harm ends** when correct assignment is restored.

## Observations

- **Severity:** Low — this is a single-user tool, so true concurrent edits are rare. The harm is a mis-assigned album that the user must manually fix. No data is permanently lost.
- **Related failures:** Accidental mis-organization (failure-07) — both result in wrong assignments; this one is caused by the system, that one by the user.
- **Variants:**
  - `20260302-201114` — Concurrent edits from two devices corrupt category assignments

## Intervention Points

### Prevention
- Firestore transactions for assignment writes (atomic read-modify-write)
- Timestamp-based conflict detection: reject writes where the document was modified more recently than the client's last read

### Detection
- Brief optimistic UI delay before committing, surfacing if a conflicting write arrives
- Change log: store a short history of assignment changes so unexpected states can be understood

### Mitigation
- Undo last change (in-session)

### Recovery
- Manual re-assignment; no data is permanently lost

---

## Management Plan

### Strategy

Accept with undo as the primary recovery mechanism. True concurrent edits from a single user are rare enough that complex conflict resolution would be over-engineering. Undo (shared with failure-10) handles the recovery case cleanly. The real mitigation is the undo toast pattern — if the user sees what was just applied, they can catch conflicts immediately.

### Planned Interventions

- **Undo toast on assignment**: After any assignment write, show a toast notification ("Moved to Jazz — Undo") for a few seconds. This surfaces both accidental assignments (failure-10) and unexpected overwrites from another device. One mechanism, two failures.
  - Type: Mitigation + Detection
  - Addresses: Chain step 7 (user doesn't know which assignment "won")

- **In-session undo**: Maintain a short in-memory stack of recent assignment actions. Undo reverses the most recent write. No persistent change log needed — in-session is sufficient for the single-user case.
  - Type: Recovery
  - Addresses: Chain steps 8–9 (user must manually find and re-assign)

### Accepted Risks

- If both devices make assignments and neither user catches the toast, the wrong assignment persists until noticed. Accepted — this is rare for a single-user tool and manual re-assignment is straightforward.
- No persistent change history (only in-session undo). If the user closes the app before noticing a conflict, there's no log to reconstruct from. Accepted — the complexity of a persistent log is not justified for a rare failure mode.

### Monitoring

None — user-noticed via unexpected UI state or undo toast.
