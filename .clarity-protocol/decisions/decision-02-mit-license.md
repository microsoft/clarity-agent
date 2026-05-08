# Decision: Open-Source License (MIT)

**Status:** decided
**Date:** 2026-05-07
**Decided by:** Project author

## Question

Under what license should Clarity Agent be open-sourced?

## Criteria

- **Reach** — does the license maximize who can adopt, embed, and contribute?
- **Compatibility with Microsoft stewardship** — Microsoft is the steward of the project; the license must be one Microsoft can ship under and accept contributions to (CLA-based).
- **Compatibility with the methodology mission** — Clarity wants to be embedded into other tools, forked into other domains, and reused as a capability. Permissive licensing is consistent with "capability first, products second."
- **Ecosystem fit** — alignment with the dominant license in adjacent ecosystems (LLM SDKs, MCP servers, VS Code extensions, Python tooling).
- **Future flexibility** — does the license preclude any plausible future product or business model?

## Options Considered

| License | Notes |
|---|---|
| **MIT** | Maximally permissive. Standard for tooling and SDKs. No copyleft obligations on downstream users. |
| Apache 2.0 | Also permissive. Adds explicit patent grant and contributor patent retaliation clause. Common at Microsoft for larger projects. |
| MPL 2.0 | File-level copyleft. Preserves modifications-public obligation but allows broader integration than GPL. |
| GPL / AGPL | Strong copyleft. Would block embedding into proprietary AI tools — directly counter to the integration strategy. |
| Source-available (BSL, Elastic, etc.) | Restricts commercial use. Blocks the citizen-developer / PM / engineer integration thesis where Clarity is meant to live inside other tools. |

## Decision

**MIT License**, copyrighted to Microsoft Corporation.

## Reasoning

The integration strategy in `notes.md` ("install once, meet them everywhere" — rules files, MCP servers, VS Code extensions, coding-agent snippets) requires a license that imposes no friction on adoption, including by commercial AI tooling vendors. MIT is the dominant license for the surrounding ecosystem (MCP servers, VS Code extensions, most LLM SDKs) and removes any legal barrier to embedding Clarity into other tools.

Apache 2.0 was the closest alternative and would also have worked. MIT was chosen for simplicity and ecosystem fit with the integration targets.

Copyleft (GPL/AGPL) and source-available licenses were rejected because they would directly block the integration thesis: third-party AI tools cannot embed copyleft Clarity components without inheriting copyleft obligations, which is a non-starter for the vendors whose users we most want to reach (citizen developers in vibe-coding tools, PMs in AI assistants, engineers in coding agents).

## Assumptions

- Microsoft remains the project steward and the appropriate copyright holder.
- A Contributor License Agreement (CLA) governs external contributions (already set up via `CONTRIBUTING.md`).
- Trademark rules are governed separately from copyright (already noted in `README.md`).
- The methodology and process guides are licensed alongside the code under the same MIT license — the intellectual corpus (when it becomes an explicit Layer 1 artifact) inherits this.

## Reconsideration Triggers

- A future product strategy depends on commercial licensing terms that MIT cannot support (e.g., a hosted SaaS that needs a copyleft moat against competitors). Unlikely given current strategy.
- A community fork diverges meaningfully and a stronger license becomes necessary to preserve coherence. Unlikely; brand and stewardship address this better than license terms.
- Microsoft policy changes regarding MIT for projects of this type.

## Related Documents

- `LICENSE` (MIT, Microsoft Corporation)
- `CONTRIBUTING.md` (CLA terms)
- `notes.md` — integration strategy (the reach argument)
- `solution/solution.md` — capability-first, products-second positioning
