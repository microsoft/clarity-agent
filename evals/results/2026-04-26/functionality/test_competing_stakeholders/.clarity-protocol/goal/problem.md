# Problem Statement

Danielle Moreau, Director of Engineering at a B2B SaaS company, needs to navigate a commitment-delivery conflict with significant organizational and revenue stakes. A VP of Sales verbally committed a large enterprise customer to an SSO/provisioning feature in Q2 during the procurement process. Engineering estimates Q3 at earliest. The expansion contract is worth ~$1.2M ARR and is not yet signed. Delivering in Q2 would require deprioritizing a platform migration, slipping it 6–8 weeks with compound effects on technical debt and future delivery velocity. The CEO has not been briefed. The immediate question is what to do this week.

## Why This Matters

This isn't just a scheduling problem — it's a trust and alignment problem at multiple levels:

- **Customer trust**: The VP's soft commitment creates risk of a sign-and-disappoint dynamic that damages the relationship more than an honest conversation now would.
- **Internal alignment**: Sales made a commitment without engineering buy-in. That gap hasn't been formally surfaced or resolved.
- **Organizational visibility**: The CEO not knowing puts Danielle in a fragile position — she's carrying risk that belongs at a higher level.
- **Technical sustainability**: The migration isn't just cleanup — it affects future delivery capacity. Slipping it compounds the problem.

## Key Facts

- The Q2 commitment is verbal, not contractual. The customer has not signed.
- VP Sales knows the gap exists. Their proposed tactic: get the customer to sign on a "soft" Q2 date and renegotiate if needed.
- Platform migration slip is an internal quality/velocity concern, not a customer-facing commitment.
- Scope-reduction options in play: (1) partial SSO rollout for critical user groups, (2) basic provisioning without automation, (3) third-party SSO/provisioning via Okta/Auth0 as a bridge.
- Third-party option hasn't been properly scoped — blocked by engineering resistance, cost uncertainty, unclear customer preference, and bandwidth.
- Customer need is unclear: guessed to be security/compliance + admin workflow, but no direct confirmation. Not believed to be a hard IT requirement.
- CEO has not been briefed. Danielle has been handling at her layer to avoid looking like she's undermining Sales or exposing engineering's migration delay.

## Open Questions

- What does the customer *actually* need SSO/provisioning for? Is Okta/Auth0 acceptable to them, or do they require native?
- What is the real cost/complexity of the third-party integration path?
- What is the customer's genuine timeline flexibility (vs. their stated preference)?

## Success Criteria

A good outcome this week means: Danielle has a clear, honest position to bring to the VP Sales and CEO — one that gives the customer a credible path to SSO/provisioning, protects the company from a sign-and-disappoint dynamic, and doesn't silently trade the migration for a short-term deal. She isn't carrying the risk alone.
