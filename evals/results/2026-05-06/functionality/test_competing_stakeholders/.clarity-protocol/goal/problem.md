# Problem Statement

A Director of Engineering at a ~200-person B2B SaaS company is navigating a conflict between a VP of Sales commitment and an existing engineering priority. The VP of Sales committed — without engineering input — to delivering SSO and provisioning for a large enterprise customer by end of Q2 (worth ~$1.2M ARR). The senior engineering lead estimates August at earliest even with resource pulls. The team is 30–35% through a platform migration explicitly prioritized last quarter by the VP of Engineering, with Data Retention and Growth Metering blocked downstream.

The Director was not looped in when the commitment was made. The VP of Engineering is aware and has delegated the decision ("I'll back what you decide"), which is genuine trust but creates accountability exposure if the Director makes the call unilaterally. The CEO has not been briefed.

## Why This Matters

The immediate risk is the $1.2M ARR relationship. The deeper risk: the Director has been managing this as their private problem to solve, in defense mode, without verifying what the customer actually needs — which has prevented finding a viable path.

## Success Criteria

A resolution that gives the customer a credible answer by end of June; doesn't blow up the migration beyond recovery; gets VP Sales and VP Engineering explicitly aligned on whatever tradeoff is made; and routes the CEO briefing decision appropriately to VP Engineering rather than leaving it as a silent risk.

## Agreed Plan

1. **Tomorrow — VP Sales (requirements questions, not options):** What does the customer's security review actually gate on? SAML alone, or automated deprovisioning via SCIM? How large is initial rollout? What language is in the contract? Any flexibility if something concrete ships by June 30 with SCIM on a committed Q3 date?

2. **Tomorrow afternoon / Monday — Raj (specific scope variants):** SAML-only estimate. SAML + basic provisioning without fine-grained roles estimate. Not "can we do it all."

3. **Once real numbers exist — VP Engineering (recommendation + sign-off):** Bring a specific proposal. Also explicitly surface that the CEO hasn't been briefed, and let VP Engineering own that decision.

Key posture shift: stop explaining why the timeline doesn't work. Go in with questions. Find out what's actually true underneath VP Sales's "existential" framing before proposing anything.

Clarified details:
- Customer deadline: end of June (~8 weeks out). Engineering estimate: August at earliest with resource pull. Gap is ~6 weeks — not closeable through heroics or minor scope cuts alone.
- Migration is 30–35% complete. Pausing is costly but not catastrophic. The downstream victims are Data Retention and Growth Metering — two features the VP of Engineering explicitly cited when he set the migration as Q1's top priority.
- VP of Engineering is aware and has said "I'll back what you decide" — which puts the decision weight on the Director rather than leadership collectively.
- VP of Sales relationship is strained this week. No word yet on whether the customer has any flexibility on scope or timeline.

## Why This Matters

The immediate risk is the $1.2M ARR relationship. But the deeper risk is that the Director is being asked to own a decision that is genuinely above their pay grade — a cross-functional tradeoff between a Sales commitment and an Engineering priority set by their own VP. Making that call unilaterally, even correctly, creates accountability exposure with no upside.

## Success Criteria

A resolution that: (1) gives the customer a credible answer by end of June — whether that's delivery, a scoped MVP, or a renegotiated date with something concrete; (2) doesn't blow up the migration beyond recovery; (3) gets VP Sales and VP Engineering aligned on the tradeoff explicitly, so the Director isn't holding the bag alone.
