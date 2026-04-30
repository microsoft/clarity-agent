# Failure Modes

7 failure modes identified from 34 raw failures (27 AI-generated, 7 human-contributed). All 7 have management plans.

## Managed

1. **[User disengagement](failure-01-user-disengagement.md)** (Critical) Users disengage before experiencing concrete value — through friction, slow starts, or sessions that feel like form-filling. When this happens, the remaining failure modes go unchecked. Managed with a layered approach: early value delivery, adaptive challenge calibration, enforced conciseness, engagement sensing, and graceful stopping points.
2. **[Inadequate AI thinking](failure-02-inadequate-ai-thinking.md)** (High) The agent produces output that appears rigorous but is shallow — generic failure modes, vague management plans, surface-level requirements. Goes undetected when users trust rather than challenge the output. Managed prevention-heavy: invisible self-critique via critique guides, specificity requirements baked into process guides, and positioning the user as an active challenger.
3. **[False alignment](failure-03-false-alignment.md)** (High) The protocol appears to capture shared understanding but actually conceals disagreement — team members interpret ambiguous document language differently, and the misalignment only surfaces during implementation. Managed through prevention + detection: document specificity and testability requirements, active review prompts, trace-back teaching, and staleness tracking.
4. **[Failure analysis depth](failure-04-failure-analysis-depth.md)** (High) Failure analysis produces incomplete or superficial results — covering obvious failure modes while missing those requiring specialized knowledge (security, human factors, organizational dynamics). Creates false confidence. Managed with defense in depth: coverage transparency by perspective, human expertise solicitation, plan scrutiny via self-critique, and context management.
5. **[Organizational misuse](failure-05-organizational-misuse.md)** (Medium) The clarity protocol gets used as compliance theater — teams go through the motions to satisfy a process requirement without actually developing clarity. Artifacts exist but don't reflect genuine thinking. Managed with acceptance + structural interventions: value alignment design, traceable reasoning requirements, defensible risk framing, and quality signals.
6. **[Multi-expression drift](failure-06-multi-expression-drift.md)** (Medium) The full expression (process guides) and light expression diverge — a principle update in one isn't propagated to the other, and the two expressions give contradictory guidance. Managed through prevention: formalize Layer 1, write the protocol format spec (FR7), add CI tests for guide consistency, and extend staleness tracking to Layer 1 → Layer 2 dependencies.
7. **[Operational and security risks](failure-07-operational-risks.md)** (Medium–Critical) Operational failures (cost overruns, API outages, context loss) and security exposures (prompt injection, data exfiltration, key exposure) that can affect any session. Managed with standard per-risk mitigations: graceful degradation, transparent data flow documentation, and cost controls.

## Cross-Cutting Patterns

**Value demonstration is the master intervention.** Failures 01, 02, and 05 all converge: concrete, specific value early keeps users engaged, challenges shallow output, and makes compliance theater less tempting. Operationalized in FM01 as "time to first insight" design constraint on process guides.

**Conciseness is structural, not cosmetic.** Verbosity undermines engagement (FM01), hides shallow thinking (FM02), enables ambiguous interpretation (FM03), and signals security theater (FM04). The protocol format spec (FR7) with summary layers is the shared intervention.

**The user is a single point of failure for quality.** FM01-04 all rely on user engagement as the quality check. Invisible self-critique (FM02) partially mitigates this dependency. The review process (long-term, shared across FM02-05) is the strongest future mitigation.

**Review process is the highest-leverage future capability.** Would address FM02 (AI quality), FM03 (false alignment), FM04 (analysis depth), and FM05 (compliance theater). On the roadmap.

**The protocol format spec (FR7) is a four-failure intervention.** Addresses FM03 (ambiguity reduction), FM04 (plan specificity standards), FM05 (quality signals), and FM06 (interoperability contract). Writing it is high priority.
