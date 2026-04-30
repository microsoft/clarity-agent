# Requirements

## Merge Semantics

**R1: Affinity-bit approach (option a) with type-level defaults.**
Mark boundary ambiguity is resolved using explicit `startInclusive`/`endInclusive` bits per mark type, not per instance. No per-instance override capability is required.

**R2: Affinity defaults table.**
The following defaults govern insertion behavior at mark boundaries. An insertion at a boundary is inside the mark if and only if the corresponding endpoint is inclusive.

| Mark type | startInclusive | endInclusive |
|---|---|---|
| Bold, italic, underline, strikethrough | No | Yes |
| Inline code | No | No |
| Quote, heading (block-level) | N/A | N/A |
| Link | No | No |
| Comment, footnote | No | No |
| Highlight, suggestion, tracked change | No | No |

The practical rule: only character formatting marks (bold, italic, underline, strikethrough) extend rightward when text is inserted at the end boundary. All other inline marks are exclusive at both ends. Block marks are out of scope for character-level affinity.

**R3: No UI disambiguation required.**
Because merge is deterministic given the affinity bits, no runtime disambiguation prompt is needed. Users correct unexpected formatting via standard formatting controls (post-hoc).

**R4: No causal cursor metadata.**
Option (b) is ruled out. Causal metadata does not resolve the concurrent-insertion case and adds implementation complexity without covering the hard case.

## Non-requirements (explicitly out of scope)

- Per-instance affinity overrides
- Mark boundary drag/resize operations (to be evaluated separately if needed)
- UI disambiguation prompts at merge time
