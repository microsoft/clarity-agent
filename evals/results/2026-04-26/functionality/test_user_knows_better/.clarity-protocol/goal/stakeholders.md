# Stakeholders

## Implementation Team

The primary consumer of the spec. Familiar enough with CRDTs to implement YATA but not necessarily fluent in causal graph theory. The spec must be expressible as a lookup table plus a clear rule — not as a proof.

**Needs:** Clear, unambiguous merge rules they can implement without deep CRDT background. Named terms (`startInclusive`/`endInclusive`) that don't collide with other CRDT vocabulary (tombstones, causal dependencies).

## End Users

Authors collaborating on rich-text documents. They experience merge behavior indirectly through unexpected formatting appearing or disappearing after concurrent edits.

**Needs:** Insertions at mark boundaries behave predictably — character formatting extends naturally when typing, structural marks (links, comments) don't grow unexpectedly.
