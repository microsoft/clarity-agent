---
name: human-factors-thinker
display_name: Human Factors
type: ai
modes: [quick, deep]
prerequisites:
  required: [goal/problem.md, solution/solution.md]
  recommended: [goal/stakeholders.md, solution/architecture.md]
tags: [human-factors, usability, error, decision-making]
execution: sync
description: "Human and AI error: user mistakes, operator misconfiguration, cognitive biases, information loss"
---
# Human Factors Thinker

This thinker identifies failure modes arising from how humans and AI components err while participating in a system — as users, operators, decision-makers, or components in a larger workflow.

## Purpose

Systems fail when the people and AI agents within them make mistakes. These mistakes are rarely random — they follow predictable patterns shaped by system design, cognitive limitations, environmental pressures, and incentive structures. This thinker systematically examines a system from a human factors perspective to identify where and how these errors will occur.

## Scope

This thinker focuses on **good-faith actors erring within the system**:

- Users making mistakes while trying to use the system correctly
- Operators misconfiguring, misunderstanding, or mishandling the system
- AI components producing incorrect, incomplete, or misleading outputs
- Decision-makers (human or AI) applying criteria inconsistently or incorrectly
- Information being lost, distorted, or misinterpreted as it flows between actors

**Not in scope** (handled by other thinkers):

- **Deliberately adversarial use** — attackers, abusers, and bad actors are covered by other thinkers
- **Indirect harm to non-users** — people affected by the system who aren't participants in it are covered by other thinkers

**Boundary case — motivated error**: This thinker *does* cover cases where good-faith actors are subtly influenced by incentives, biases, or social pressure to produce skewed results. The distinction from adversarial use is intent: a loan officer who unconsciously applies stricter criteria to certain demographics is a human factors failure, not a security failure.

## Analysis Approach

### Identify the actors

Start by mapping all the human and AI actors in the system. Read the problem statement and solution to understand:

- **Who uses this system?** End users, administrators, operators, on-call engineers.
- **Who or what makes decisions?** Human decision-makers, AI components, hybrid workflows where humans review AI outputs or vice versa.
- **What does each actor do?** What inputs do they receive, what outputs do they produce, what judgments do they make?
- **What information flows between actors?** Where does data cross a boundary from one actor to another?

### Apply the "junior human" test

For any AI component in the system, imagine replacing it with a relatively junior, potentially quite naive human employee. Ask: how would we make *that* system safe? What training, oversight, and checks would we put in place? The failure modes of LLMs and humans are remarkably similar — hallucination, misinterpretation, susceptibility to framing, inconsistent application of criteria — and the safeguards that work for one often work for the other.

### Core principles

Keep these in mind throughout the analysis:

- **"User error" is never a root cause.** It is always a symptom of a deeper design problem — in the system, the process, the interface, or the training — that made the error more likely or more consequential. When you identify an error, always ask: what aspect of the system's design allowed or encouraged this?
- **Catastrophic errors must be hard to make.** If an error would have severe consequences, the system must make it difficult to commit. Consider the circumstances under which the action might be taken (including stress, fatigue, time pressure) and ask what would force careful thinking at the right moment.
- **Routine errors signal design problems.** If an error is happening repeatedly, something about the system is causing it. The fix is in the system, not in telling people to be more careful.
- **Complicated vs. complex matters.** Complicated systems (difficult but solvable with expertise) benefit from checklists of tasks. Complex systems (unpredictable, adaptive) benefit from checklists of *questions to ask*. Mismatching these — applying rigid procedures to complex situations, or leaving complicated procedures to improvisation — is itself a failure mode.

**Consider the prior state**: For each failure you identify, note whether it also exists before this solution is implemented. Many human factors failures (e.g., misinterpretation of ambiguous data) are pre-existing and universal. If the solution doesn't make them worse, flag them as pre-existing — they'll be triaged efficiently during analysis.

## Failure Discovery Checklist

Work through these categories systematically for each actor in the system. Not every category applies to every actor or every system — use judgment.

### Garbage In, Garbage Out

Bad inputs produce bad outputs. This applies to every actor — humans entering data, AI models receiving prompts, operators providing configuration.

**What if actors receive bad inputs?**

- Users enter incomplete, inaccurate, or ambiguous information
- AI components receive poorly structured or misleading prompts
- Operators work from outdated documentation or stale configuration templates
- Upstream data sources provide incorrect or corrupted data

**What if the system can't distinguish good inputs from bad?**

- No validation at the point of entry, so errors propagate silently
- Validation exists but is too narrow (rejects valid input) or too broad (accepts invalid input)
- Errors in input are only discovered much later, when the damage is done and the cause is hard to trace

**What if data quality degrades over time?**

- Data entered correctly becomes stale as the world changes
- Accumulated small errors compound into systematic bias
- No process exists to audit or refresh aging data

### Hallucination and Omission

When a process is supposed to be grounded in underlying data, actors can introduce information that isn't there (hallucination) or drop information that is (omission). Both humans and AI are prone to this.

**What if actors add information that isn't supported by the source?**

- AI components confabulate plausible-sounding details (names, dates, statistics, citations)
- Humans fill in gaps from memory or assumption rather than checking the source
- Summaries include conclusions not supported by the underlying data
- Repeated telephone-game handoffs between actors amplify small embellishments

**What if actors drop critical information?**

- Caveats, scope limitations, or uncertainty qualifiers are lost when information is summarized or transferred
- Minority viewpoints or edge cases are omitted from reports
- "Known unknowns" — things explicitly flagged as uncertain — are treated as settled by downstream actors
- AI components produce confident-sounding output that omits important context from the input

### Misinterpretation of Data

Whenever data crosses a boundary between actors — human to human, human to AI, AI to human, system to system — both sides must agree on its meaning. Misinterpretation is one of the most common and insidious failure modes.

**What if actors interpret data differently than intended?**

- Field semantics are ambiguous (a "string" field with no specification means "whatever people have been sending or might choose to send")
- Units, formats, or encoding conventions differ between sender and receiver
- The same term means different things to different actors (e.g., "active user" defined differently by product and engineering)
- System behavior doesn't match users' mental model of what the controls do, making errors nearly certain

**What if the system measures the wrong thing? (Proxy metrics)**

This is the most dangerous form of misinterpretation. It happens when you want to measure quantity X but actually measure a related quantity Y, and the difference is hidden.

*Example*: The COMPAS recidivism prediction system aimed to predict likelihood of re-offending, but could only measure proxies — likelihood of being re-arrested, re-indicted, re-convicted. The gap between those proxies and actual re-offending is, almost by definition, the set of biases in the criminal justice system. By building a model that predicted the proxy but treating it as the real thing, the system actively amplified systemic biases.

- Where does the system use proxy metrics? What's the gap between the proxy and the intended measurement?
- Who might mistake the proxy for the real thing?
- Could the gap between proxy and reality systematically harm particular groups?
- Are the limitations of proxy metrics documented and visible to decision-makers?

**What if API contracts are underspecified?**

- Multiple client versions in the field send different data for the same field, with no record of what old versions expect
- Error responses are ambiguous, leading callers to misinterpret failure as success (or vice versa)
- Implicit assumptions about data format, ordering, or completeness aren't documented

### Amplifying Preconceptions

Actors — both human and AI — tend to agree with what they hear, reinforce existing framings, and suppress dissent. This leads to groupthink, confirmation bias, and echo chambers.

**What if actors reinforce each other's biases?**

- Human teams converge on a shared view without adequately considering alternatives
- AI components trained via RLHF are especially prone to sycophantic agreement — saying "great idea!" rather than identifying problems
- Inputs implicitly frame the desired output, and actors follow the frame rather than questioning it
- Dissenting perspectives exist but aren't empowered to speak or aren't heard when they do

**What if the system lacks adequate diversity of perspective?**

- For complex problems, having multiple different perspectives is essential — not just as a nice-to-have but as a reliability mechanism
- A single-perspective analysis will systematically miss certain categories of failure
- Social dynamics (hierarchy, politeness, desire to avoid conflict) suppress useful disagreement

**What if feedback loops amplify bias?**

- The system's outputs influence its future inputs (e.g., recommendation engines that narrow over time)
- Early decisions constrain later ones in ways that aren't visible
- Success metrics reward convergence rather than accuracy

### Unexpected Preferences

Any decision-making system has preferences, by its nature. Failures emerge when the system's *revealed* preferences — what it actually does at scale — differ from those *intended* by its creators. This rarely manifests in individual decisions; it emerges statistically.

**What if the system's behavior differs from its intent?**

- Individual decisions look reasonable, but aggregate patterns show systematic bias
- Edge cases are handled inconsistently because criteria don't cover them clearly
- Cultural, demographic, or contextual factors influence decisions in unintended ways

**What if no one is looking for the drift?**

- There's no monitoring to detect whether aggregate outcomes match intended policy
- The people defining policy don't see enough individual decisions to notice patterns
- Feedback from affected populations doesn't reach decision-makers

### Decision-Making at Scale

When a system (human, AI, or hybrid) makes nontrivial decisions at scale — loan approvals, content moderation, recommendations, risk assessments — it is especially vulnerable to the failures above. This section applies when the system includes such a component.

**What if decision criteria aren't calibrated?**

- The policy-maker's intent isn't clearly communicated to the decision-makers (human or AI)
- Decision-makers interpret criteria differently from each other and from the policy-maker
- No process exists to test whether criteria produce the intended outcomes on example cases
- Criteria that were calibrated once drift as context changes

**What if cross-checking is absent?**

- Every case goes to a single decision-maker with no second opinion
- Disagreements between decision-makers aren't tracked or escalated
- Hard cases (where reasonable people would disagree) aren't identified for special handling

**What if monitoring doesn't catch problems?**

- Inputs and outputs aren't tracked in enough detail to detect correlations
- Unexpected correlations (e.g., decision outcomes correlating with time of day, decision-maker identity, or demographic factors) go undetected
- Monitoring exists but no one acts on its findings

## Error Triggers

The categories above describe *what* goes wrong. This section describes *why* — the conditions that trigger errors. After identifying potential failures from the checklist, consider which triggers apply in this system's context.

### Naive Error

The actor doesn't know the error is possible or that it matters. They haven't been trained, warned, or given feedback that would make them aware.

- Are there places where actors might not realize they can err?
- Are the consequences of errors visible to the people making them?
- Is there adequate training or onboarding for the system's complexity?

### Rushed Error

Under high cognitive load — time pressure, multitasking, fatigue, stressful conditions — actors take shortcuts and skip checks they'd normally perform.

- What happens when operators are under time pressure? (Incident response, deployment deadlines, on-call at 3am)
- What happens when users are distracted or multitasking?
- Are there bottlenecks where a single overloaded actor becomes a reliability risk?

### Illusion

Input signals are genuinely confusing or ambiguous, leading actors to confidently misinterpret what they're seeing.

*Example*: The somatogravitic illusion in aviation — pilots can't distinguish between pitch angle and acceleration by feel alone, leading them to interpret one as the other with potentially fatal results.

- Are there places where the system's signals are ambiguous or could be confused?
- Could an actor be confident they understand the situation while actually misreading it?
- Does the system's interface make the current state clear, or does it require interpretation that could go wrong?

### Forced Error

The actor *cannot* verify or check the system's output — they are forced to trust it. This turns the system into a single point of failure.

- Are there actors who lack the expertise or access to verify what the system tells them? (e.g., a vision augmentation system for blind users, a code generator for non-engineers)
- Are there time constraints that make verification impractical even when the actor has the ability?
- What safeguards exist when the actor must trust the system?

### Motivated Error

The actor has an incentive — conscious or subconscious — to produce a particular outcome, and they manipulate inputs or creatively interpret outputs to get it.

- Are there actors with incentives that might conflict with accurate system use?
- Could social pressure (hierarchy, peer expectations, organizational culture) push actors toward particular outcomes?
- Are there accountability mechanisms that make motivated errors detectable?

## Common Intervention Points

Human factors failures often have intervention points at:

- **Clear mental models**: System behavior matches user intuition. When it can't, explicit training bridges the gap.
- **Input validation with useful feedback**: Don't just reject bad input — tell the actor *why* and *how to fix it*.
- **Confirmation for irreversible actions**: Require explicit, friction-adding confirmation for actions with severe consequences. The friction is the feature.
- **Visible system state**: Make the current state unambiguous. Don't require actors to infer what's happening.
- **Calibrated decision criteria**: For decisions at scale, use the calibration recipe: write criteria, create annotated examples, have multiple raters evaluate independently, iterate until convergence, maintain the test set.
- **Cross-checking and monitoring**: For decisions at scale, send a random subset to multiple raters, track inter-rater agreement, escalate disagreements, and monitor for unexpected correlations in inputs and outputs.
- **Diversity of perspective**: Ensure that complex problems are examined from multiple viewpoints, and that dissent is structurally empowered (not just permitted).
- **Graceful error recovery**: Assume errors will happen. Make them detectable, reversible, and low-consequence where possible.

## Output Format

For each human factors failure identified, record a raw failure mode. Each failure record contains:

- **Title**: A short descriptive title of what could go wrong
- **Source**: `human-factors-thinker`
- **Description**: 1-3 sentences describing what goes wrong, how it happens, and who is harmed. This must end in actual harm — a violated principle that doesn't lead to harm is not a failure mode.
- **Additional context** (optional): More detail about the scenario, potential severity, related concerns. Include any initial thoughts about the failure chain, but don't develop full chains here — that happens during failure analysis.

Remember: "user error" is never the failure. The failure is always the design that made the error possible, likely, or consequential. Frame your findings accordingly.

Keep raw failures lightweight. The goal is to capture the idea, not to fully analyze it. Full failure chains, intervention points, and management strategies are developed in later stages (failure analysis and failure management).

## Cross-Domain Considerations

Human factors failures often interact with other domains:

- **Security**: Human errors create security vulnerabilities (misconfiguration, credential mistakes, social engineering susceptibility)
- **Privacy**: Misinterpretation of data boundaries can lead to privacy violations
- **Accessibility**: Systems that require high cognitive load or specific sensory abilities exclude users with disabilities
- **Scalability**: Human bottlenecks (manual review, approval workflows) create scaling limits
- **Fairness**: Unexpected preferences and proxy metric failures disproportionately affect marginalized groups

When identifying human factors failures, note these cross-domain interactions in the additional context — they help during failure analysis and grouping.

## Using This Thinker

This thinker is invoked by the failure brainstorming process. The AI reads this guide (via `read_thinker_guide`) and applies its methodology, recording failures via the `record_failure` tool and suggestions via the `record_suggestion` tool.

In either mode, the thinker examines the problem statement, solution description, and architecture (if available) to identify human-factors-specific failures.

Work systematically through the checklist, but use judgment — not every category applies to every system. A single-user CLI tool has different human factors concerns than a platform with AI-assisted decision-making at scale.

For each potential failure:

1. Identify the actor and what they're doing
2. Assess if this error is relevant to this system's actual context
3. Record it as a raw failure mode, framing the failure as a design issue (not "user error")
4. Include enough context for someone else to understand the scenario

The output is a set of raw failure modes. These will later be grouped, analyzed, and developed into full failure mode documents with chains and management plans.
