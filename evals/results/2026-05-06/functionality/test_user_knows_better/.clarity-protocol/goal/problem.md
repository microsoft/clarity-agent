# Problem

## What we're working on

A mark-attribution ambiguity in a YATA-based rich-text CRDT. When a mark (e.g., bold) has a right-open boundary and a concurrent insertion lands at or near that boundary, the merge produces a correct total order but incorrect attribution roughly half the time — the insert inherits the mark when it shouldn't, or vice versa, depending on which side of the boundary the user's intent placed it.

## Success criteria

A design that:
- Produces correct, deterministic mark attribution for concurrent inserts at mark boundaries
- Keeps mark-semantic logic out of the CRDT merge path
- Is auditable for legacy documents (bare `char_id` left-origins)
- Can be phased: fix the bug now, improve bias derivation later without a second protocol change

## Approaches evaluated

### Option A: Explicit attach-left/attach-right bit on mark endpoints (Fuchs-Fuchs)
Type-level (one expand policy per mark type) is correct. Instance-level is a footgun — every mark-creation callsite becomes load-bearing correctness. Key decision: type-level vs. instance-level matters more than mechanism choice.

### Option B: Deriving attachment from causal cursor metadata at insert time
Not viable. Local cursor state at insert time may conflict with post-merge mark state. No principled resolution when metadata contradicts position-derived attribution. High complexity, low maintainability.

### Option C: UI disambiguation on merge conflict
Not viable for the common case (typing at a mark boundary happens constantly). Only defensible for rare, exotic conflicts. Breaks the CRDT's seamless-collaboration promise.

### Typed anchors (fourth option, extension of A)
Left-origin becomes `{ id: char_id, bias: 'left' | 'right' }` rather than a bare `char_id`. Marks are attributed by comparing anchors directly — no mark-schema logic in the merge path. The editor sets bias from keyboard navigation direction when available; falls back to the mark-type expand rule otherwise. The CRDT stays decoupled from mark semantics entirely.

## Chosen direction

**Typed anchors with type-level fallback, shipped in two phases:**

- **Phase 1 (immediate):** Add `expand: { left, right }` to mark type schema. Change left-origin wire format to `{ id, bias }`. Editor derives bias from mark-type schema (same decisions as Option A). CRDT uses bias field; never consults mark schemas. Fixes the attribution bug.
- **Phase 2 (later, no protocol change):** Editor derives bias from keyboard navigation direction when available; falls back to type schema when not (mouse clicks, programmatic inserts, contenteditable ambiguity).

## Legacy migration policy

Bare `char_id` left-origins in existing documents are interpreted as `{ id: char_id, bias: 'right' }` — the least-wrong default, not a semantic implication of YATA (YATA's left-origin is an ordering constraint, not a mark-attribution statement). The audit of mark types where boundary attribution is semantically critical is load-bearing, not optional. Per-type migration flags handle anything that doesn't hold up.

## Key constraints

- Full control over insert schema across all clients — typed anchors not blocked on protocol grounds
- Mix of ProseMirror and contenteditable implementations; contenteditable requires virtual cursor state tracking (not DOM selection) to reliably capture navigation direction
- Comment marks need non-expanding behavior (type-level `expand: { left: false, right: false }`) — not an argument for instance-level bits
- Design review in two days — frame as "lead with the fix, not the architecture"
