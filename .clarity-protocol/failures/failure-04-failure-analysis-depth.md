# Failure: Failure analysis lacks depth or credibility

## Summary

The failure brainstorming and analysis process — the system's most distinctive capability — fails to deliver on its promise of surfacing things the user wouldn't have found alone. Either the coverage has blind spots (entire categories of failure go unexamined), the management plans are security theater (they sound reasonable but don't actually mitigate the risk), or the process itself breaks down due to technical constraints (context overflow, duration that kills engagement). The user ends up with a false sense of safety.

## Failure Chain

1. The user runs failure brainstorming. The general thinker produces an initial pass, possibly followed by specialist thinkers.
2. The thinkers analyze the system, but their coverage is bounded by:
   - The perspectives encoded in the thinker guides (are they broad enough?)
   - The LLM's training data (does it know about this domain's failure patterns?)
   - The project context provided (is the problem/solution/architecture detailed enough?)
   - The context window (can the LLM hold all the relevant material simultaneously?)
   - *Intervention point (coverage awareness):* The system should make coverage explicit — "Here's what we examined; here's what we didn't."
   - *Intervention point (human expertise):* The brainstorming process should actively solicit domain-specific failure modes from the user that automated analysis can't find.
3. Blind spots exist. Failure modes that fall outside the thinkers' perspectives, that are domain-specific in ways the LLM doesn't know, or that arise from unusual combinations of factors are missed entirely.
   - *Observation:* The most dangerous failures are precisely the ones nobody thought to look for. A false sense of completeness is worse than acknowledged incompleteness.
4. For failures that are identified, management plans are developed. But plans may be superficial:
   - "We'll add monitoring" — monitoring what, triggering on what threshold, alerting whom, with what response?
   - "We'll have a fallback" — to what? How is it triggered? Has it been tested?
   - "We'll train users" — training decays, people don't read docs, new users skip onboarding.
   - *Intervention point (plan scrutiny):* The failure management process should challenge every plan: "Walk me through exactly what happens when this fails. Who does what, in what order, and how do they know to do it?"
   - **Harm begins** — the team has management plans that create a feeling of safety without providing actual safety.
5. A failure occurs that was either not identified (blind spot) or whose management plan doesn't work in practice (security theater).
6. The team discovers the gap during an incident. The clarity protocol, which was supposed to prevent this, either didn't cover the failure or covered it with an inadequate plan. **Harm continues** through the incident and its aftermath.
   - *Observation:* If the failure was in the protocol with a management plan that failed, the post-incident analysis is particularly painful — "We knew about this, we had a plan, and it didn't work."

**Technical constraint sub-chain:**

3a. For complex projects, loading the full problem, stakeholders, solution, architecture, thinker guide, and accumulated failures exceeds the LLM's context window.
   - *Branch:* The LLM truncates input silently, missing critical context. Analysis proceeds but is blind to parts of the system.
   - *Branch:* The system fails entirely and the user gets an error.
   - *Intervention point (context management):* Intelligent summarization or selective loading of context, rather than dumping everything.

3b. Thorough analysis takes a long time. The user loses patience.
   - *Observation:* This connects to Group 2 (disengagement). Duration is a friction source that competes with depth.
   - *Intervention point (progressive depth):* The general-thinker-first approach helps — quick broad analysis, then selective deepening. But even the broad pass can be slow for complex systems.

## Observations

- **Severity:** High — failure analysis is the system's most distinctive feature and the area where the promise is most specific ("surface failures you wouldn't have found alone")
- **Related failures:** Group 1 (inadequate AI thinking) — generic thinker output is a sub-case. Group 2 (user disengagement) — duration and verbosity push users away from the deep analysis that would catch more.
- **Variants:**
  - Failure brainstorming has blind spots
  - Failure plans that don't actually work (security theater)
  - Context buffer overflow during brainstorming
  - Brainstorming duration breaks user engagement

## Intervention Points

### Prevention
- Make coverage explicit: what perspectives were applied, what wasn't examined
- Actively solicit human domain knowledge — the user knows things the LLM doesn't
- Challenge management plans rigorously: "Walk through exactly what happens"
- Manage context intelligently: summarize, prioritize, selectively load
- The general-thinker-first approach provides quick broad coverage; specialist depth on demand
- Layer 1 corpus should encode what distinguishes real mitigation from security theater

### Detection
- Track coverage: which thinker perspectives have been applied, which haven't
- Flag management plans that use vague language ("add monitoring," "implement fallback") without specifics

### Mitigation
- Progressive depth: start broad, deepen where it matters most
- Incremental analysis: process partial results rather than waiting for everything
- Human review of management plans — the user should be able to say "this plan wouldn't actually work because..."

### Recovery
- Post-incident analysis can feed back into the protocol — new failure modes, revised management plans
- The protocol structure supports incremental improvement: add new failures, deepen existing analysis

---

## Management Plan

### Strategy

Defense in depth, combining coverage awareness, plan scrutiny, and human expertise. This failure mode is particularly important because failure analysis is the system's most distinctive capability — the area where the promise is most specific. Security-theater plans are the highest-harm variant because they create the illusion of safety.

Shares the review process intervention with FM02 and FM03. Shares the self-critique mechanism with FM02. The context management concern is unique to this failure mode.

### Planned Interventions

**Prevention:**

- **Coverage transparency** (chain step 2, intervention point "coverage awareness"): After brainstorming, the agent should make coverage explicit — what perspectives were applied, what domain areas were examined, and what *wasn't* examined. Short-term: the agent narrates coverage at the end of brainstorming ("we looked at this from security, operational, and human-factors perspectives; we haven't examined regulatory compliance or supply chain risk"). Long-term: structured coverage tracking in the failures index.

- **Human expertise solicitation** (chain step 2, intervention point "human expertise"): The brainstorming process should actively ask the user for domain-specific failure modes: "Based on your experience building systems like this, what goes wrong that an outsider wouldn't think of?" This is already somewhat present in the process but should be elevated — the user's domain knowledge is the primary defense against LLM blind spots.

- **Plan scrutiny via self-critique** (chain step 4, intervention point "plan scrutiny"): The invisible self-critique for failure management should include a specific check: "If I walk through this management plan step by step — this failure occurs, then what happens? — does each step actually work?" The failure management process guide should encode the "walk me through exactly what happens" discipline as a required internal check, not just a suggestion. The Layer 1 corpus should capture what distinguishes real mitigation from security theater (a vague "we'll add monitoring" vs. a specific "we'll alert the on-call engineer via PagerDuty when error rate exceeds 5%, and they'll have a runbook with these three steps").

- **Context management** (technical constraint sub-chain, step 3a): For complex projects, intelligent context loading — summarize documents that aren't the current focus, load full detail only for the document being analyzed. Short-term: process guides should instruct the agent to manage context deliberately ("focus on the authentication subsystem for this thinker pass"). Long-term: Layer 3 infrastructure that provides context-aware summarization.

**Detection:**

- **Vague-plan detection** (chain step 4): The self-critique disposition should flag management plans that use vague language without specifics. Markers: "add monitoring" (monitoring what?), "implement fallback" (to what?), "train users" (how? refresher cadence?). These are symptoms of security theater and should trigger the agent to either deepen the plan or explicitly accept the vagueness as a known gap.

**Mitigation:**

- **Progressive depth** (technical constraint sub-chain, step 3b): The general-thinker-first approach already provides this — quick broad coverage, specialist depth on demand. The agent should present brainstorming results with clear "want to go deeper here?" prompts, letting the user direct effort where it matters most to them.

- **Incremental analysis** (chain step 4): Failure management should be doable incrementally — plan a few failures per session rather than requiring all seven in one sitting. The process already supports this; the guide should make it explicit.

**Long-term:**

- **Review process** (chain step 4): A review pass specifically focused on "do these management plans actually work?" is the strongest intervention against security theater. A reviewer who wasn't part of the original analysis will catch plans that sound reasonable but don't hold up under scrutiny. Shared with FM02 and FM03.

- **Post-incident feedback loop:** When a managed failure actually occurs, the outcome should feed back into the protocol — did the management plan work? What was missed? This requires usage tracking and incident reporting that doesn't exist yet, and is likely only relevant for organizations with operational maturity.

### Accepted Risks

- **LLM knowledge boundaries.** The AI cannot brainstorm failure modes it doesn't know about. Domain-specific failures that aren't well-represented in training data will be blind spots. The human expertise solicitation mitigates this partially, but some gaps will remain.
- **Context window limitations.** For very large projects, even intelligent context management may not fit everything relevant. The agent should acknowledge when it's working with partial context.
- **Duration vs. depth tradeoff.** Thorough analysis takes time. The progressive-depth approach manages this, but at some point the user decides "enough" — and that point may be before all important failures are covered. This is accepted; the protocol supports returning to deepen analysis later.

### Monitoring

- **Coverage tracking:** Which thinker perspectives have been run against which parts of the system. Gaps should be visible in the failures index.
- **Plan specificity:** Management plans should be reviewable for specificity — a plan with concrete steps, named systems, and walk-through-able procedures is higher quality than one with abstract mitigations.
- **Post-release feedback:** If failures occur that should have been caught, that's the ultimate quality signal. Only available for projects with operational feedback loops.
