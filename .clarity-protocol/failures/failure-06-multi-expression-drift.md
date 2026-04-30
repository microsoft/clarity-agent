# Failure: Multi-expression maintenance burden

## Summary

The four-layer architecture requires maintaining multiple expressions of the same intellectual corpus — full process guides, light guides, the book, and potentially others — plus the Layer 1 source of truth that they all derive from. These expressions can drift out of sync, creating inconsistency between different products, confusion for users who encounter more than one expression, and erosion of trust in the methodology.

## Failure Chain

1. The intellectual corpus (Layer 1) exists — either explicitly as maintained documents, or implicitly in the authors' heads and scattered notes.
2. Multiple expressions of the corpus are created: full process guides, light guide, the book.
3. A principle is refined, a technique is improved, or a mistake is discovered.
4. The change is propagated to some expressions but not others. **Harm begins** — different users of different products now receive inconsistent guidance.
   - *Variant:* Layer 1 never gets written as an explicit artifact. Without a canonical source, each expression is maintained independently with no shared reference point. Drift is inevitable.
   - *Variant:* The book is published on a different timeline than the software. The book describes version 1.0 while the tool has moved to 2.0, or vice versa.
   - *Variant:* Process guides reference Python commands that have been refactored. The AI follows the guide, the command fails.
   - *Variant:* The protocol format is assumed rather than specified. Different products interpret the format differently, breaking interoperability.
5. Users encounter inconsistency. They may not realize it (if they use only one product) or they may lose trust in the methodology (if they notice contradictions between the book and the tool).
6. **Harm ends** when the drift is detected and corrected — but without systematic tracking, detection may be slow.

## Observations

- **Severity:** Medium — manageable with discipline and tooling, but the natural tendency is toward drift
- **Related failures:** The staleness tracking infrastructure could be extended to detect Layer 1 → Layer 2 drift
- **Variants:**
  - Light expression diverges from full expression
  - Layer 1 corpus never gets written
  - Book and tool give conflicting advice
  - Process guide drift from code
  - Protocol format without specification

## Intervention Points

### Prevention
- Make Layer 1 an explicit artifact — the canonical source from which both expressions are derived
- Use staleness tracking between Layer 1 and Layer 2 expressions
- Create a protocol format specification as a Layer 1 artifact
- Automated testing that process guide commands actually work (for code drift)

### Detection
- Extend the dependency graph: Layer 1 docs → full guides, Layer 1 docs → light guide
- CI tests that verify process guide commands execute successfully

### Mitigation
- When drift is detected, prioritize fixing the expression users are most likely to encounter
- Version the protocol format specification

### Recovery
- Layer 1 as source of truth makes re-synchronization possible — derive from the canonical source rather than trying to merge diverged expressions

---

## Management Plan

### Strategy

Prevention through explicit source-of-truth artifacts and automated detection. This is a maintenance/engineering problem with well-understood solutions — the key is doing the foundational work (writing Layer 1, writing the format spec) rather than managing drift after the fact.

### Planned Interventions

**Short-term:**

- **Write Layer 1 as an explicit artifact** (variant "Layer 1 never gets written"): This is the single most important intervention. Without a canonical source, drift between expressions is inevitable. The Layer 1 corpus should be a maintained set of markdown files — the same ones that inform the book — from which both Layer 2 expressions are derived. This is already in the solution and architecture documents as a design commitment; the management plan is: actually do it, and do it before creating the light expression.

- **Write the protocol format specification** (variant "format without spec", now also FR7): Define document types, required sections, summary layers, and length guidance as a Layer 1 artifact. This is the interoperability contract and the verbosity management mechanism. Without it, products will interpret the format differently and interoperability is illusory.

- **CI tests for process guide commands** (variant "process guide drift from code"): Automated tests that execute the shell commands in process guides against the actual Python infrastructure. When `packet_status.py` is refactored, the test fails and the guide gets updated. Short-term implementation: extract commands from guide markdown, run them against a test protocol directory, verify they don't error.

**Long-term:**

- **Extended staleness tracking** (chain step 4): Extend the dependency graph to include Layer 1 → Layer 2 dependencies. When a Layer 1 principle document is updated, both the full and light Layer 2 expressions that derive from it are flagged as potentially stale. This uses the same content-hash mechanism already in `packet_status.py`, applied to a broader graph.

- **Book/tool versioning alignment** (variant "book and tool give conflicting advice"): Establish a versioning relationship between the book and the tool. The book will inevitably describe a point-in-time snapshot. The mitigation is: the book references Layer 1 principles by name, and the tool's Layer 2 expressions reference the same names. When they diverge, the naming makes the divergence traceable. Accept that the book and tool will sometimes be out of sync — the Layer 1 corpus is the reconciliation point.

### Accepted Risks

- **Book/tool lag is inevitable.** A published book is a snapshot; software evolves continuously. Accept that the book will sometimes describe an older version of the methodology. Mitigation: versioning and explicit "what changed since the book" documentation.
- **Layer 1 itself can become stale.** If the authors learn something from practice that changes a principle, Layer 1 needs updating before Layer 2. The discipline to update Layer 1 first — not just fix the guide and move on — is organizational, not technical.
- **The light expression is a genuinely different artifact.** It's not a subset of the full expression; it's a separate derivation from Layer 1. Some drift between light and full is not a bug — it reflects the different environments they serve. The question is whether the *principles* are consistent, not whether the *text* is identical.

### Monitoring

- **Layer 1 → Layer 2 staleness tracking** (once extended graph is implemented).
- **CI test pass rate** for process guide commands.
- **User reports** of inconsistency between products (e.g., "the Claude Project guide says X but AGENTS.md says Y").
