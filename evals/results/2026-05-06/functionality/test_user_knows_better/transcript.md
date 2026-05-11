## Turn 1

**User:**
I'm working through a mark-attribution problem in a YATA-based rich-text CRDT and I need a thinking partner, not background. Here's the crux:

When a mark (say, bold) has a right-open boundary and a concurrent insertion lands at or near that boundary, the merge produces correct total order but incorrect attribution roughly half the time — specifically, the insert inherits the mark when it shouldn't (or vice versa) depending on which side of the boundary the user's intent placed it.

I've considered three approaches: (a) explicit attach-left/attach-right bit on mark endpoints à la Fuchs-Fuchs; (b) deriving attachment from causal cursor metadata at insert time; (c) accepting the ambiguity and surfacing a UI disambiguation step on merge conflict. I've read Nicolaescu 2016, the Yjs source, the Automerge rich-text RFC, and a few slide decks. So I'm not looking for pointers to literature.

What I want: honest evaluation of those three options on spec complexity, runtime cost, and maintainability — and if there's a real fourth option I haven't named, I want to hear it.

**Assistant:**
Good — here's my honest take.

---

**Option A (attach bit)** is the right call for most implementations, but the critical design decision you have to make first is whether the bit lives at the **mark-type level** (all bold marks always expand right) or the **mark-instance level** (each bold span carries its own bit). Type-level is strictly more maintainable — one decision per mark type, no per-creation heuristic needed, and the semantics are discoverable from the schema. Instance-level is more flexible but means every code path that creates a mark must set the bit correctly, and getting it wrong bakes in wrong behavior permanently with no recovery path. Spec complexity: low once you commit. Runtime: O(1), negligible. Maintainability: excellent if type-level, fragile if instance-level.

**Option B (causal cursor metadata)** has a fundamental soundness problem that makes it not worth pursuing. The cursor metadata captures local state at insert time, but post-merge mark state at that position may differ — a concurrent boundary change could have arrived that the inserting peer didn't know about. Now you have a conflict between what the metadata says and what position-derived attribution says, and there's no principled resolution. If metadata wins, you've invented a form of LWW where the timestamp is "cursor time on originating peer," which produces correct outcomes only when concurrent boundary changes are rare. If position wins, the metadata is noise. High spec complexity, O(k) metadata per insert, and you end up maintaining a system whose semantics are genuinely hard to explain to contributors.

**Option C (UI disambiguation)** isn't viable for the mark-boundary-at-typing case. Concurrent inserts at a formatted boundary happen constantly in any active document — surfacing this as a user-visible conflict would produce a noisy, broken UX. The only scenario where C is defensible is for exotic conflicts (e.g., concurrent mark deletion vs. boundary insert) where the frequency is low enough that user judgment is worth the friction. For the common case you've described, this isn't a real contender.

---

**Fourth option: extend the position primitive to typed anchors, and apply it uniformly.**

This is structurally distinct from Option A, though it ends up in similar territory. The idea: instead of positions in your YATA sequence being character IDs, they're typed anchors — `after(id)` or `before(id)`. These aren't just notational sugar; they're what the YATA insert operation records as left-origin. Every insert already has an anchor, set at the moment the user places a keystroke.

The consequence: mark attribution at merge time requires no special logic at all. You just compare anchors. A mark boundary expressed as `before(char_B)` means anything with `left-origin = after(char_A)` (where char_A is the predecessor of char_B) lands inside the mark; anything with `left-origin = before(char_B)` or later lands outside. YATA's existing total order handles it — you don't need a boundary-checking pass.

How this differs from Option A: Option A puts the decision on the mark (the mark carries an attach bit, and mark-application logic queries it for each nearby insert). Typed anchors put the decision on the insert's left-origin, which is set by the editor layer at keystroke time. The boundary behavior emerges from the position algebra rather than from mark-specific merge logic. The mark schema stays simple; the insert schema gets slightly richer.

The cost: this is a protocol-level change. Left-origin goes from `char_id` to `(char_id, bias)`. Every peer must implement the same anchor semantics, and you'll need to decide how legacy inserts (with bare char_id left-origins) are interpreted.

You're aware of Peritext — this overlaps with its anchor model. The distinction worth naming: Peritext defines anchors relative to mark operations specifically; what I'm describing generalizes anchors to *all* positions in the sequence, making mark attribution a consequence of the position model rather than a parallel mechanism.

---

**My recommendation:** Option A at the mark-type level, unless you control the full insert schema across all clients, in which case typed anchors give you cleaner semantics and less merge-time logic. Option B is a dead end. Option C is a patch for a different problem.

The decision that actually matters most is upstream of all three: do you define attachment at mark-type granularity or per-instance? That's a product call, and getting it right matters more than which mechanism you choose to implement it.

## Turn 2

**User:**
The typed-anchors option is the most interesting thing you've said, but I want to pressure-test the claim that it's structurally distinct from A. If the editor layer sets `(char_id, bias)` at keystroke time, something has to decide the bias. In the boundary-ambiguous case — insert lands exactly at the mark edge — what does the editor use to pick it? If the answer is "the mark type's expansion rule," you've just re-implemented Option A with the logic moved one layer down. The merge is cleaner, sure, but the decision point is the same.

The case where anchors genuinely diverge from A is if the bias can be set from user intent signals at keystroke time — cursor affinity, selection direction, something observable before merge. Do you have a model for that, or is the editor defaulting to the mark-type rule anyway?

On your recommendation: I do control the full insert schema across all clients, so typed anchors aren't off the table on protocol grounds. My hesitation is the legacy migration. We have a corpus of documents with bare char_id left-origins, and "interpret legacy inserts as after(char_id)" is probably the right default but it's a one-way door — if that default is wrong for some class of marks, we've baked in wrong behavior everywhere pre-migration.

The type-level vs instance-level question — I'm already leaning type-level for the reason you named: instance-level means every mark-creation callsite is load-bearing correctness. But some of our mark types genuinely need per-instance behavior. Comments, specifically. A comment mark on "foo bar" should not automatically expand to include a character inserted immediately after "bar" the way bold might.

**Assistant:**
The pressure test lands on the programmatic and mouse-click cases, but not on keyboard-navigation, and that's where the structural divergence is real.

**The cursor-navigation model:**

When a user presses → to arrive at a mark boundary, the cursor traveled *through* `char_A` (the last marked character) to reach position P. The natural anchor is `after(char_A)` — the cursor is "coming from the left," from inside the span. When a user presses ← from outside the span to arrive at the same visual position, the natural anchor is `before(char_B)` (the first unmarked character). Same visual position, different anchors, set from navigation direction — no mark-type rule consulted.

This is cursor affinity operationalized as an anchor type rather than a layout hint. It's a real signal, not a derived policy. The editor emits the anchor based on how the cursor arrived, and the CRDT records it. The mark's expansion rule never enters the picture for these insertions.

Where typed anchors *do* collapse back to Option A: mouse-placed cursors and programmatic inserts. A click between `char_A` and `char_B` has no navigation direction. Paste, API calls, and auto-formatting similarly have no cursor context. For these cases, yes, you need a fallback rule — and that fallback is the mark-type expansion policy, which puts you back at Option A for that subset. Typed anchors aren't a replacement for Option A; they're a mechanism that makes Option A's rule the fallback for edge cases rather than the primary decision point for all cases.

Whether that tradeoff is worth it depends on how common keyboard-navigation-at-boundary is in your workload vs. programmatic inserts. For human typing, it's the dominant path.

---

**On the legacy migration:**

`after(char_id)` isn't just the convenient default — it's the correct reading of existing YATA semantics. A bare left-origin `char_A` in the current protocol already means "place this insert in the sequence after char_A." Interpreting it as `after(char_A)` isn't a new policy; it's making the implicit semantics explicit. The concern about baking in wrong behavior applies most strongly to marks where the type rule disagrees with the expansion behavior users experienced historically. But your system is currently producing wrong attribution roughly half the time — any consistent default is an improvement over an inconsistent one. The real risk is specific mark types where the `after(char_id)` interpretation is systematically wrong (say, a mark type that should always be non-expanding but legacy documents happen to have inserts inside them). You can audit this per mark type before committing, and you don't have to apply one migration rule uniformly.

---

**On comments and the hybrid:**

Comments aren't a good argument for instance-level expansion bits — they're a good argument for type-level `expand: { left: false, right: false }`. A comment mark that auto-expands to include new insertions is semantically broken regardless of which instance it is; no per-instance override makes it right. The real instance-level case would be something like a suggestion span or a tracked-change region where the same mark type needs different expansion rules depending on its content or state — and even there, the better model is usually a status field on the mark rather than a raw expansion bit.

The hybrid you're reaching toward: type-level defaults, with instance-level override only for marks whose expansion behavior legitimately varies by state. That's the right shape. The correctness burden stays off the mark-creation callsite for the common case (bold, italic, comment), and the override path exists but isn't the norm. What it requires is discipline that new mark types ship with an explicit type-level policy — which is a lint rule, not a code review culture.

One thing worth naming explicitly: if you go typed anchors + type-level expansion for fallback, the expansion rule becomes testable in isolation from the CRDT. You can unit-test "given a programmatic insert at this boundary for this mark type, what anchor does the editor emit?" without needing a full merge. That's a maintainability win that Option A (where the expansion logic lives inside mark application in the merge path) doesn't get you.

## Turn 3

**User:**
The cursor-navigation model is the part I hadn't fully worked out. You're right that it's a real signal — navigation direction is observable at keystroke time without consulting the mark schema at all. I'd been mentally conflating cursor affinity (the visual layout hint) with anchor derivation from navigation, and those aren't the same thing. Fair point.

What I want to nail down before I commit to this path: the contract between the editor layer and the CRDT. In practice, "cursor arrived from the left" means the editor layer tracks last-movement-direction and translates that into bias when the user types. That works cleanly in ProseMirror because cursor position is a well-defined object with affinity. It's messier in contenteditable implementations where you're reading from the DOM selection, which doesn't always reflect navigation direction reliably across browsers. We have both in our stack. What does the typed-anchors model say about the case where the editor can't determine bias — is the contract "emit after(char_id) as default, override when known," or does ambiguous bias have to be represented explicitly?

On the testability win — that actually matters a lot for my team. The merge path is where bugs go to die. If expansion logic is in the editor layer and the mark schema, the CRDT itself stays honest about what it knows.

Practical question: I have a design review in two days. If I walk in recommending typed anchors + type-level fallback, I'm proposing a protocol change that touches every client, migration work, and a new editor-layer contract. That's a harder sell than "we add an expand bit to the mark type schema." Is there a phased path — ship type-level Option A now, migrate to typed anchors later — that doesn't create a protocol discontinuity?

**Assistant:**
**On the contract for ambiguous bias:**

Don't represent ambiguity in the wire format. The contract should be: **the editor always emits a definite anchor; when it can't determine bias from navigation context, it falls back to the mark-type schema and emits that result.** The CRDT receives a fully resolved anchor every time and never needs to consult mark semantics. Ambiguity is an editor-layer problem, resolved before the operation is emitted.

This is architecturally important: if you allow `bias: null` in the wire format, the CRDT now has two code paths and needs to know about mark schemas to handle the null case. You've reintroduced mark-semantic logic into the merge path, which is exactly what typed anchors were supposed to eliminate. Keep the CRDT honest — it knows positions, not mark meanings.

For the contenteditable case specifically: don't try to read navigation direction from the DOM selection — it's unreliable. Maintain your own cursor state. Track the last keyboard event; if it was an arrow key, you know the direction and can set bias accordingly. If the selection changed via click, programmatic call, or an event you didn't observe, fall back to the type-level rule. This is standard practice in serious contenteditable editors and not much code. ProseMirror users get this for free; you build it once for the contenteditable path and then both stacks share the same editor-CRDT contract.

---

**On the phased path — this is actually cleaner than it looks:**

The insight is that the protocol change and the "smart bias derivation" change are separable. You don't need two protocol versions.

**Phase 1 (your design review):** Introduce the `{ id, bias }` left-origin format now, but always derive bias from the mark-type expand rule. The CRDT uses the bias field to determine attribution — it never consults mark schemas. The editor sets bias mechanically from the type schema, exactly as Option A would. For legacy documents, bare `char_id` left-origins are interpreted as `{ id: char_id, bias: 'right' }` — consistent with existing YATA semantics.

**Phase 2 (later, no protocol change):** The editor gets smarter. Instead of always asking the mark schema, it derives bias from navigation direction when available and falls back to the schema when not. The CRDT code is untouched. The wire format is untouched. No migration, no discontinuity.

What you're shipping at Phase 1 is essentially Option A — type-level expand rules fixing the attribution bug — but with the decision point in the editor rather than the merge path, and the wire format already expressing anchors. Phase 2 is a pure editor enhancement. You never do a second protocol change.

**For the design review pitch:** Frame it as "we're fixing the attribution bug with type-level expand rules, and we're doing one protocol change to move that logic out of the merge path." Don't lead with typed anchors as an end goal — lead with the fix. The anchor model is the mechanism you're choosing for its testability and the clean CRDT / editor separation. The navigation-direction enhancement is a future improvement that costs nothing to enable, because the wire format is already there.

The harder conversation at the review is probably the legacy migration policy. I'd go in with a concrete proposal: bare left-origins in existing documents are interpreted as `after(id)`, which is consistent with existing YATA semantics, and you're auditing the two or three mark types where non-expansion is load-bearing (comments, links) to verify that `after(id)` produces the right attribution for legacy content. If it doesn't for a specific type, you have a per-type migration flag. That's a bounded, auditable problem — not "we might be wrong everywhere."

## Turn 4

**User:**
The phased path works. That's the frame I'll use at the review — lead with the fix, not the architecture.

One quibble on the legacy migration framing: "consistent with existing YATA semantics" is slightly overselling it. YATA's left-origin is an ordering constraint, not a mark-attribution statement. Saying `after(char_id)` follows from existing semantics is a reasonable heuristic, but it's still a policy choice. The audit is load-bearing, not optional. If we go in to the review saying "legacy bare origins interpret as `after(id)` because YATA semantics," someone will correctly point out that YATA has nothing to say about marks, and we'll lose five minutes defending the framing. Better to say: "we pick `after(id)` as the least-wrong default, we're auditing the mark types where boundary attribution is semantically critical, and we have per-type migration flags for anything that doesn't hold up." That's accurate and bounded.

Otherwise — this gave me what I needed. The Option B critique is the same conclusion I was reaching but sharper, which is useful for shutting that conversation down at the review. The typed-anchors path as a phased extension of Option A is genuinely new to me and solves the design-review-vs-long-term-architecture tension cleanly.

**Assistant:**
You're right — that's a better framing. "YATA has nothing to say about marks" is exactly the objection someone will raise, and it's correct. "Least-wrong default, audit is required, per-type flags for anything that doesn't hold up" is both accurate and harder to attack. I was conflating the ordering semantics with the attribution policy. Good catch; take that version in.

Good luck at the review.Session captured if you want to come back to it.
