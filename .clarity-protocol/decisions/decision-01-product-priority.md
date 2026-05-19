# Decision: Product Exploration Priority

**Status:** decided (tentative — revisit as we learn more)
**Date:** 2026-03-03
**Decided by:** Project author

**Update (2026-05-18):** Two products from the original priority list have since been implemented:
- **MCP server** (was priority 1): Implemented under `src/clarity_agent/mcp/server.py` (run via `python -m clarity_agent.mcp`) — eight tools, stdio/SSE/HTTP transport. MCP infrastructure is now the foundation; remaining work for the hybrid use case is the light Layer 2 expression.
- **Standalone desktop application** (was priority 5, deferred): Implemented as a Tauri-packaged native app, contrary to the original "niche audience / defer" assessment.

The active priority list now starts with MCP-enhanced general AI (hybrid) and general-purpose AI integration (light), both blocked on the light expression rather than infrastructure.

## Question

Which new products should we prioritize exploring beyond the existing three (AGENTS.md, web app, CLI), and in what order?

## Criteria

- **Reach** — how many new users does this open up?
- **Dependency weight** — what has to exist before we can build this?
- **Learning value** — does building this stress-test important framework assumptions?
- **Incremental effort** — how much new work beyond what's already planned?
- **Risk** — new operational, security, or maintenance burdens?

## Options Evaluated

| Product | Reach | Dependencies | Effort | Learning | Risk |
|---|---|---|---|---|---|
| General-purpose AI (light) | Very high | Layer 1, format spec | Low | High | Low |
| MCP-enhanced hybrid | Medium (growing) | MCP exposure | Medium | High | Low |
| Hosted web service | Medium | Full stack, multi-tenant | Very high | Medium | High |
| Standalone desktop app | Low | Full stack, packaging | High | Low | Medium |
| IDE integration | Medium | MCP exposure | Medium | Medium | Low |
| Deep model integration | Potentially transformative | Mature methodology, partnerships | Unknown | Very high | High |

## Decision

**Priority order:**

1. **MCP-enhanced hybrid** — first new product to explore. The path to implementation is shortest from where we are: MCP exposure of Layer 3 is already in the near-term work plan, and the hybrid combines that with a light guide loaded as context. Validates the Layer 3 portability thesis. Medium reach today, but MCP adoption is growing.

2. **General-purpose AI integration (light)** — second priority. Higher reach than the hybrid (anyone with any AI tool), but blocked on Layer 1 formalization → light expression, which is on a separate timeline. When it ships, this is likely the highest-reach product form.

3. **IDE integration** — third priority. Once MCP works, VS Code integration may be lower effort than it appears (VS Code already supports MCP). Natural for the "reachable in the flow of creation" requirement (FR11).

4. **Hosted web service** — defer. High effort, high risk, well-understood engineering. Doesn't teach us much about the methodology. Revisit when the user base and use patterns are better understood.

5. **Standalone desktop app** — defer. Niche audience, high effort, low learning value.

6. **Deep model integration** — distant horizon. Revisit when methodology is mature and integration mechanisms exist.

## Reasoning

The MCP hybrid is prioritized over the GPAI light product despite lower reach because its implementation path is shorter from current state — MCP exposure is already planned near-term work, while the light expression requires Layer 1 formalization which is on a separate timeline. Building the hybrid first also validates the MCP portability thesis, which de-risks the broader product strategy.

The key insight from the solution architecture: products are thin shells over shared capability. The foundational work (format spec, critique guides, MCP exposure, process refinement) benefits all products. Product-specific effort is incremental on top of that shared foundation.

## Assumptions

- Layer 1 formalization will happen but on its own timeline
- MCP adoption continues growing across AI tools
- The existing products continue to be maintained and improved
- The "now" foundational work proceeds regardless of product decisions

## Reconsideration Triggers

- Layer 1 formalization completes → GPAI light product becomes unblocked, may leapfrog hybrid in priority
- MCP exposure reveals unexpected portability limitations → reassess hybrid viability
- A specific partnership or integration opportunity emerges → reassess based on opportunity
- User feedback from existing products reveals unmet needs that a specific new product would address
- Significant change in the AI tool landscape (e.g., MCP becomes universal, or a competing standard emerges)
