# Open Questions

## OQ1: What UX surfaces does the clarity agent need?

**Status:** resolved

**The question:** The stakeholder analysis identifies at least six distinct jobs-to-be-done, several of which imply fundamentally different interaction models. Does the clarity agent need multiple UX entry points and modes — and if so, which are essential vs. nice-to-have, and how do they relate to each other?

**Resolution:**

Yes, the system needs multiple products — but the four-layer architecture (Layer 1 intellectual corpus → Layer 2 reified corpus → Layer 3 infrastructure → Layer 4 products) means products are thin shells over shared capability, not independent applications. The protocol format is the interoperability point: a user's protocol works with any product.

The four interaction models identified in the analysis (conversational, embedded, reading/reference, status/alert) are not four products — they're four *capabilities* that products combine differently. AGENTS.md already blends conversational + embedded + status. The web app blends conversational + reading + status. A Claude Project would be conversational only. Products are specific combinations of capabilities tuned to specific environments.

**Product priority and sequencing:**

The near-term focus is improving the existing products (AGENTS.md, web app, CLI) through foundational work that benefits everything:

```
Now (no Layer 1 dependency):
  ├── Protocol format spec (FR7) — interoperability contract, verbosity management
  ├── Critique guides — invisible self-critique across all process phases
  ├── Process guide refinement — early value, adaptive calibration, conciseness
  ├── CI tests for guide commands — prevent guide/code drift
  └── MCP exposure of Layer 3 — infrastructure portability

When ready:
  └── Layer 1 formalization (organizing existing material, not creating from scratch)
       ├── Light expression (Layer 2 light) — first new product
       │    └── Light products (Claude Project, custom GPT) — highest reach, lowest friction
       └── Extended staleness tracking (Layer 1 → Layer 2)

Later:
  ├── MCP-enhanced hybrid products — general AI + infrastructure via MCP
  ├── Hosted web service — multi-tenant, cloud storage, new security concerns
  └── IDE integration, deep model integration — further horizon
```

**Key decisions embedded in this resolution:**

- The light expression is the first *new* product to build, because it has the highest reach and lowest friction — anyone talking to any AI can use it.
- Layer 1 formalization is the prerequisite for the light expression but not for the "now" work items.
- MCP exposure is independent and can proceed in parallel.
- The hosted service, IDE integration, and deep model integration are later-horizon and don't need to be designed now.
- The reading/reference mode is adequately served by well-structured protocol documents (markdown in a repo, packet generation for external stakeholders) — it doesn't need a separate product, just good document design (which FR7 addresses).

**What this resolves and what it doesn't:** This resolves the product *strategy* — which products, in what order, sharing what. It does not resolve detailed UX design for any individual product. Those are implementation decisions that belong in each product's own design process.
