# Failure: Operational and security risks

## Summary

The system's broader product surface — MCP servers, hosted services, general AI integrations, LLM provider dependencies — introduces standard infrastructure risks: data exposure, cost runaway, single points of failure, prompt injection, and capability dependencies. These are well-understood risk categories with known mitigations.

## Key Risks

**LLM provider data exposure.** All protocol content is sent to LLM providers. For sensitive projects, this content may be used for training (depending on provider terms). Users of hosted or general-AI products may not understand this data flow.
- *Mitigation:* Make data flow transparent. Support self-hosted LLMs. Ensure provider terms are understood before adoption.

**Hosted service data breach.** A multi-tenant hosted service stores protocols for multiple organizations. Storage isolation or access control failures expose one organization's design thinking to another.
- *Mitigation:* Per-tenant storage isolation, authentication, standard security practices for multi-tenant SaaS.

**MCP server as single point of failure.** If Layer 3 is exposed via a single MCP server, any downtime blocks all MCP-connected products from infrastructure capabilities.
- *Mitigation:* Products should degrade gracefully when infrastructure is unavailable — fall back to Layer 2 only. MCP server should be lightweight and reliable.

**Light guide prompt injection.** In light-implementation products, the methodology is loaded as a system prompt. A malicious modified guide could inject adversarial instructions.
- *Mitigation:* Distribute the light guide through trusted channels. Users should verify the source of any guide they load.

**LLM cost accessibility.** A full clarity session involves many LLM calls across deep-tier models. For resource-constrained users, the cumulative cost may be prohibitive.
- *Mitigation:* The tier system allows using cheaper models for less critical tasks. The general-thinker-first approach reduces unnecessary specialist runs. The light implementation has no infrastructure cost.

**LLM capability dependency.** Process guides assume high-capability LLMs (long context, tool use, instruction following). Smaller or open-source models may degrade.
- *Mitigation:* The tier system maps quality requirements to model capability. Process guides should be tested against the range of supported models.

## Observations

- **Severity:** Ranges from Medium (cost, capability) to Critical (data breach for hosted service)
- **Overall assessment:** These are standard infrastructure risks with well-understood mitigations. They require attention during implementation but don't pose the same existential threat as the process quality and engagement failures (Groups 1-4).

---

## Management Plan

### Strategy

Standard infrastructure risk management — these are well-understood risk categories with well-understood mitigations. Each risk is managed independently; there are no significant interactions between them (unlike the process-quality failures FM01-04). The approach is: implement known mitigations, make risks transparent to users, and design for graceful degradation.

### Planned Interventions

**LLM provider data exposure:**
- Type: Prevention + transparency
- Make the data flow visible to users. The initialization process should state clearly: "All protocol content will be sent to [provider]. Review your provider's data usage terms before including sensitive information."
- Support self-hosted/on-premise LLMs through the existing provider abstraction (FR13). This is the only complete mitigation for sensitive projects.
- The protocol format (local markdown files) means the data at rest is always under the user's control — only the conversation with the LLM involves external data flow.

**Hosted service data breach:**
- Type: Prevention (standard SaaS security)
- This risk only materializes when/if a hosted service is built. At that point: per-tenant storage isolation, authentication, authorization, standard audit logging, encryption at rest.
- Design decision: storage isolation architecture should be determined during hosted service design, not retroactively. Flag as a requirement when that product is scoped.

**MCP server reliability:**
- Type: Mitigation (graceful degradation)
- Products must function — with reduced capability — when the MCP server is unavailable. Full-implementation products fall back to direct Python invocation (the current as-built approach). Light-implementation products don't depend on MCP at all. The MCP-enhanced hybrid falls back to light-only mode.
- The MCP server itself should be lightweight and stateless — it wraps existing Python infrastructure, so the failure surface is small.

**Light guide prompt injection:**
- Type: Prevention (trusted distribution)
- Distribute the light guide through official channels (published Claude Project, verified Custom GPT, project repo). The guide is a read-only artifact — users shouldn't need to modify it.
- Accept that a determined attacker with access to modify a user's system prompt can inject adversarial instructions. This is true of any system-prompt-based tool and is not unique to the clarity agent.

**LLM cost:**
- Type: Mitigation (cost controls)
- The tier system maps expensive models to high-value tasks (problem clarification, architecture) and cheaper models to mechanical tasks (routing, status checks). The general-thinker-first approach already reduces unnecessary specialist runs.
- The light implementation has zero infrastructure cost — it uses whatever LLM the user already has access to. This is the cost-conscious path.
- Long-term: cost tracking per session with configurable budgets. The cost callback infrastructure exists; wiring it to limits is straightforward.

**LLM capability dependency:**
- Type: Mitigation (tiered requirements)
- Process guides should be tested against the supported model range to establish minimum capability requirements per phase. Some phases (failure brainstorming, architecture review) may require higher-capability models; others (simple status checks, document recording) work with anything.
- The light expression should be designed for the broadest model compatibility — it needs to work in any general AI conversation, not just top-tier models.

### Accepted Risks

- **Data exposure is inherent to the approach.** Any system that uses external LLMs sends data externally. Users must understand and accept this. The tool cannot prevent data exposure to the LLM provider — only make it transparent and offer alternatives (self-hosted models).
- **Prompt injection in the full implementation** (adversarial text in protocol documents becoming part of thinker prompts) is an accepted risk. No sanitization is practical without breaking the system's ability to analyze the documents' content.
- **Model capability will vary.** The system will produce better results with more capable models. Users on smaller or open-source models will get lower quality — this is an inherent limitation, not a fixable bug.

### Monitoring

- **Cost per session** tracked via existing callback infrastructure. Alert if sessions exceed configurable budget thresholds.
- **MCP server uptime** (when deployed). Standard health checks and availability monitoring.
- **Provider API availability.** The LLM abstraction layer should track and report provider failures so the user understands when quality degradation is external.
