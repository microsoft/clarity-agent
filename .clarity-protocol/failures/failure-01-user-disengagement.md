# Failure: Users resist or disengage from structured thinking

## Summary

The user encounters friction during the clarity process — pushback they didn't expect, verbosity that overwhelms, cultural discomfort with failure thinking, or noise from staleness alerts — and disengages rather than pushing through. They either abandon the process entirely or complete it superficially. The harm is that they proceed without the structured thinking the tool was supposed to provide, and may blame the tool for the outcome.

This is the existential risk for the product: if users don't stay engaged, nothing else the system does matters.

## Failure Chain

1. User encounters the clarity agent — deliberately or via embedded integration (AGENTS.md, custom GPT, etc.).
2. The agent begins structured thinking: asking questions, pushing back on assumptions, requesting specificity.
   - *Intervention point (calibration):* The agent's intensity should match the user's context. An expert who's already thought deeply needs lighter challenge than a first-timer with a vague idea.
   - *Intervention point (early value):* Surface something the user hadn't considered — a stakeholder they missed, a failure mode they hadn't thought of — so they experience concrete value before friction accumulates.
3. The user experiences friction. Forms vary by variant:
   - *Pushback resistance:* "I asked you to build something, not interrogate me."
   - *Happy path attachment:* "Those failure modes are unlikely, let's focus on the product."
   - *Cultural aversion:* "We don't need all this process, we're agile."
   - *Verbosity fatigue:* "This document is too long, I'll read it later." (They won't.)
   - *Alert noise:* "Everything is always stale, these warnings are meaningless."
   - *Dead-end sense:* The citizen developer produces structured output but has nowhere to put it and no one to share it with.
   - *Observation:* The user's internal calculation is: "Is the value I'm getting worth the friction I'm experiencing?" If they haven't yet experienced concrete value, the answer is always no.
4. User begins to disengage — skimming rather than reading, agreeing without thinking, looking for ways to skip steps or end the session. **Harm begins** — the process is running on form without substance.
   - *Intervention point (engagement sensing):* Watch for signals of disengagement — short answers, rapid agreement, "sure, that's fine" — and adjust approach.
   - *Intervention point (conciseness):* Keep outputs short and scannable. The critical insight should be in the first sentence, not buried in a paragraph.
5. User completes the process superficially or abandons it entirely.
   - *Branch (abandonment):* They proceed with no structured thinking at all.
   - *Branch (superficial completion):* They have protocol documents that look complete but reflect shallow thinking — clarity theater from the human side.
   - *Observation:* In embedded contexts (AGENTS.md), abandonment may mean removing the integration entirely, closing the door on future engagement.
6. The project proceeds without genuine clarity. Failure modes surface in production. Misalignment surfaces during implementation. **Harm continues** until the project fails or succeeds by luck.
   - *Observation:* The user may blame the tool — "We tried that clarity thing, it didn't help" — which poisons future adoption for them and anyone they tell.

## Observations

- **Severity:** Critical — this failure mode prevents all other value the system provides
- **Related failures:** Closely related to Group 1 (AI produces inadequate thinking) — if the AI's output is shallow, the user's disengagement is rational, not a failure of engagement
- **Variants:**
  - Challenging disposition drives users away before they experience value
  - Wrong calibration of challenge intensity
  - Attachment to the happy path
  - Cultural aversion to failure thinking
  - Protocol verbosity causes skimming
  - Citizen developer produces protocol nobody uses
  - Staleness alert fatigue

## Intervention Points

### Prevention
- Calibrate challenge intensity to the user's expertise and context
- Demonstrate concrete value early in the interaction (surface a genuine insight, not a generic observation)
- Keep all outputs concise — critical content first, detail on demand
- Make failure thinking feel productive and energizing, not like a compliance burden
- For citizen developers, provide a clear path for what to do with the output
- Tune staleness tracking granularity to reduce false-positive noise

### Detection
- Watch for disengagement signals: short answers, rapid agreement, requests to skip ahead
- Track whether the user is engaging substantively or just clicking through

### Mitigation
- When disengagement is detected, shift approach: ask fewer questions, surface a surprising insight, explicitly acknowledge the friction
- Offer natural stopping points — "we've covered the most important ground, want to go deeper or is this enough for now?"
- Allow incremental engagement — the user can do problem clarification now and failure analysis later

### Recovery
- Even shallow protocol documents are a starting point for re-engagement later
- The protocol's existence means a future collaborator or session can pick it up

---

## Management Plan

### Strategy

Layered defense anchored on one principle: the user must experience concrete, specific value before friction accumulates. Prevention focuses on process guide design and adaptive behavior. Detection uses conversational signals. Mitigation offers graceful alternatives to full disengagement. Recovery relies on the protocol's persistence.

This failure interacts tightly with FM02 (AI thinking quality) and FM03 (false alignment). If the agent's output is shallow, disengagement is rational — so FM01 management depends on FM02 being managed well. Conversely, if the user disengages, FM02 and FM03 go unchecked. The shared interventions are detailed here and cross-referenced in those plans.

### Planned Interventions

**Prevention:**

- **Early value delivery** (chain step 2, intervention point "early value"): Process guides must be structured to surface a genuine insight, challenge, or reframe within the first 2-3 exchanges. Not a generic observation ("have you thought about security?") but something specific to what the user just told you. This is a Layer 1 principle and a Layer 2 design constraint — every process guide should be evaluated against "how quickly does this produce something the user hadn't thought of?"

- **Adaptive challenge intensity** (chain step 2, intervention point "calibration"): Process guides should include guidance on reading expertise signals and calibrating push-back. An expert who's already thought deeply needs lighter touch; a first-timer with a vague idea needs more scaffolding, not more challenge. Signals include: specificity of the user's language, whether they volunteer constraints unprompted, how they respond to the first challenge.

- **Conciseness discipline** (chain step 3, variant "verbosity fatigue"): The protocol format (FR7) must enforce summary layers in every document type. Process guides must instruct the agent to lead with the most important point and resist comprehensive-but-unfocused prose. Long-term: length guidelines derived from the author's template refinement work, captured in Layer 1.

- **Staleness tuning** (chain step 3, variant "alert noise"): The staleness tracker should distinguish high-impact staleness (problem changed → solution is invalid) from low-impact (cosmetic edit → downstream hashes differ). Short-term: the agent uses judgment when presenting staleness results, not just parroting every stale flag. Long-term: staleness severity tiers in the dependency graph.

**Detection:**

- **Engagement signal monitoring** (chain step 4, intervention point "engagement sensing"): The invisible self-critique disposition should include watching for disengagement signals — short responses, rapid agreement, "sure, that's fine," requests to skip ahead. This is not a separate monitoring system; it's part of how the agent reads the conversation, the same way a skilled human partner notices when someone's eyes glaze over.

**Mitigation:**

- **Approach shift on disengagement** (chain step 4): When the agent senses disengagement, it should change tactics — not announce "I notice you're disengaging." Options: surface a surprising insight to re-engage; offer a natural stopping point ("we've covered the critical ground — want to go deeper or pause here?"); shift from questioning to synthesis ("let me summarize what I'm hearing and you tell me what's wrong").

- **Incremental engagement model** (chain step 3, variant "dead-end sense"): The process should have well-defined value plateaus. Problem clarification alone is useful. Adding failure analysis is more useful. The user shouldn't feel they must complete the entire process to get value. Each phase should produce a standalone artifact worth having.

**Recovery:**

- **Protocol persistence** (chain step 5): Even shallow or abandoned protocol documents are a starting point for future sessions. The agent should make this clear — "we can come back to this anytime" — without being pushy about it.

### Accepted Risks

- Some users will disengage regardless — the friction/value calculus depends on the user's context, patience, and how much they actually need structured thinking. The system cannot force engagement.
- Adaptive calibration depends on the AI correctly reading expertise signals, which it will sometimes get wrong. Over-calibrating (too gentle) risks FM02; under-calibrating (too aggressive) worsens FM01.
- In light-implementation contexts, the agent has fewer tools for detecting disengagement — no session history, no infrastructure signals. The light guide must encode the disposition directly.

### Monitoring

- **Time to first insight** as a quality metric. Proxy measures: user response length and engagement depth after the agent's first substantive challenge; whether the user continues or abandons after the first friction point.
- **Session completion rates** across entry points, where meaningful in full-implementation products.
- **User feedback** on value experienced, if/when feedback mechanisms exist.
