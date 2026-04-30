# Problem Statement

Designing merge semantics for a rich-text CRDT (YATA-based) with a separate attribute layer for marks. The core problem: when a mark's range boundary and a concurrent local insertion coincide, CRDT ordering is correct but attribute inheritance is ambiguous roughly 50% of the time — the insertion may or may not fall "inside" the mark depending on how the endpoint semantics are defined. This violates user intent in about half of cases.

Three candidate approaches are under consideration:
- **(a) Explicit attach-left/attach-right bit** on each mark endpoint (Fuchs-Fuchs / Peritext style)
- **(b) Causal cursor metadata** to infer insertion intent from the cursor's causal history relative to mark creation
- **(c) UI disambiguation** — accept ambiguity at the CRDT level and surface a resolution step when divergence is detected

## Why This Matters

The merge behavior is part of the core CRDT spec. Getting it wrong means either incorrect document state on concurrent edits or a poor user experience (unexpected formatting, surprising de-formatting). The implementation team needs to understand and maintain this logic, so both correctness and intelligibility matter.

## Success Criteria

A chosen approach is:
- Correct: resolves mark boundary ambiguity deterministically (or with explicit user intent)
- Specified: can be stated precisely enough to implement consistently
- Affordable: runtime overhead is acceptable for a text editor workload
- Intelligible: the implementing team can understand and reason about the rule without deep CRDT theory background
