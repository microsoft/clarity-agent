# Problem Clarification

This process helps transform vague ideas into clear problem statements by asking probing questions and ensuring all stakeholders' needs are understood.

## Overview

The hardest part of building something isn't the implementation—it's knowing what to build and why. This process guides a conversation that sharpens understanding of the problem being solved, identifies who cares about it, and establishes what any solution must provide.

When the problem is clear, everything else becomes easier. Solutions can be evaluated against actual needs. Failures can be understood in context. Decisions can be made with clear criteria. Without problem clarity, you're building on sand.

## When to Use This Process

Run this process when:

- Starting a new project and the problem isn't fully articulated
- The team isn't aligned on what problem they're solving
- You find yourself saying "it depends" without knowing what it depends on
- Solutions keep changing direction (sign of unclear problem)
- Stakeholder needs are conflicting (they may not all have the same problem)

## Inputs Needed

The `.clarity-protocol/` directory should exist with at least template files for `goal/problem.md`, `goal/stakeholders.md`, and `goal/requirements.md`. (The clarity-agent process creates these if they don't exist yet.)

Also read `.clarity-protocol/notes.md` for guiding principles and any items tagged `[for: problem-clarification]`. Act on tagged items during the relevant steps and remove them once addressed.

## Process Steps

### Step 1: Read Current State

Load and read the current problem, stakeholders, and requirements files. Understand what's already documented.

If the files contain only template placeholders (e.g., "[To be determined]"), this is a first-time clarification — you'll be building the problem statement from scratch. If they already have content, you're refining: look for gaps, vagueness, or areas that may have become stale.

### Step 2: Understand the "Why"

Ask questions that get at the core motivation:

- "What happens if this problem doesn't get solved?"
- "What's the current workaround, and why isn't it good enough?"
- "What prompted you to start working on this now?"
- "Who feels the pain when this problem exists?"

The goal is to understand not just what the problem is, but why it matters. This "why" is what keeps projects on track when implementation decisions get tough.

### Step 2.25: Pressure-test the Framing of the Goal

Before going deeper, take one explicit pass at the user's framing of the goal itself. The user has told you *what they want*. Step 2 told you *why it matters to them*. Now ask: **does the stated goal actually serve that "why," or is it one path among several?**

The failure mode this catches is subtle and very common: the user names a goal that is really a *means* to a goal one level up, and you treat the means as the endpoint. Even a thoughtful user will frame their request in terms of the intervention they've been thinking about ("rebuild the donor database," "switch from Jira to Linear," "build a team-tracking dashboard") rather than the outcome that intervention is meant to produce. If you accept the framing as the goal, you'll do good work in service of the wrong thing.

**Concretely, ask:**

- "If [the stated goal] were already done — magic wand, no effort — what would you actually be able to do that you can't do today?"
- "What's the worst version of [the stated goal] that would still count as a success? What does that tell us about what success really is?"
- "Is [the stated goal] the goal, or the route you've picked toward a goal? If it's the route, what's the destination?"
- "What's the next layer up — if we zoomed out one level, what's the larger thing this is in service of?"

**Probe at least once; usually that's enough.** Do it in the first few turns even when the goal sounds concrete and reasonable — that's when the framing is most likely to slip past unexamined. Probing the framing is *not* the same as challenging the user, and it's *not* the same as second-guessing — you're confirming the shared destination before optimizing the route. State that explicitly if the user pushes back: "I'm not pushing you off this — I just want to make sure I'm helping with the right thing before we go deep."

**Signs the framing needs more pressure-testing, not less:**

- The stated goal is a noun that names an artifact ("a CRM," "a dashboard," "a rewrite," "a literature review") rather than a state of the world.
- The user has already done substantial work toward the stated goal — they may be invested in the means and lose sight of the end.
- The "why" from Step 2 names an outcome ("we want to retain more first-time donors") while the stated goal names an artifact ("rebuild the donor database") — the gap between them is room for a different intervention.
- You can articulate a different intervention that would also satisfy the "why" — that's a sign the means and the ends have separated.

**What to do with what you find:**

- If the framing survives the pressure-test, write the stated goal to `problem.md` as before and proceed. Note in `problem.md` that the framing was examined — one short sentence is enough.
- If a higher-level goal surfaces, *don't silently swap*. Surface what you noticed back to the user explicitly: "It sounds like the actual destination might be [X], and [their stated goal] is one route. Is that right?" Then let the user decide whether to keep the original framing or reframe.
- If the user is adamant about the stated framing even after pressure-testing, respect that — capture both the stated goal and the higher-level "why" in `problem.md` so the larger context isn't lost downstream.

This step is intentionally short: one pass, surfaced gently, then proceed. The pitfall to avoid is making every conversation feel like an interrogation. The pitfall it prevents is bigger: a project that succeeds at the wrong thing.

### Step 2.5: Separate Problems from Solutions

**Watch for overspecified requirements.** Sometimes stakeholders arrive with extremely detailed requirements that are actually proposed solutions, not underlying problems. This commonly happens when:

- The stakeholder is trying to be helpful by showing up with a solution, not just a problem
- They've built up existing workarounds and lost track that these are solutions, not requirements
- They're describing implementation details ("it should use React") rather than needs ("it should be maintainable by our JavaScript team")

**When you detect this pattern:**

1. **Acknowledge the solution**: "That's an interesting approach..."
2. **Ask about the underlying problem**: "Help me understand—what problem would that solve?"
3. **Dig deeper**: "What would happen if we solved that problem a different way?"
4. **Separate the concerns**: "So the actual requirement is [underlying need], and [their solution] is one way to achieve that. Are there other constraints that make [their solution] necessary?"

#### Example conversation

> **Stakeholder**: "The system needs to send email notifications every hour with task status."
>
> **You**: "What problem does hourly email solve?"
>
> **Stakeholder**: "People need to know if their tasks are behind schedule."
>
> **You**: "So the requirement is 'people need timely awareness of schedule issues,' and hourly email is one way to do that. Are there constraints that make email the right channel, or hourly the right frequency?"
>
> **Stakeholder**: "Well, they check email regularly. I guess they could also check the app, but we need some way to alert them..."

Now you've separated the problem (awareness of schedule issues) from one proposed solution (hourly email), and can explore whether email is the right approach, whether hourly is the right frequency, or whether other solutions might work better.

**Note**: Sometimes "compatibility with existing solutions" is a legitimate requirement (people have built workflows around the existing approach). But that's very different from "the existing solution is the only one"—and should be captured as a compatibility requirement, not a functional one.

#### When stakeholders and implementers speak different languages

This pattern is especially common when requirements come from non-technical stakeholders (legal, policy, compliance, business) who naturally think in terms of outcomes and constraints, while implementers think in terms of architectures and mechanisms.

**Key techniques for bridging the gap:**

1. **Ask stakeholders to describe outcomes, not implementations**
   - Good: "We need defensible answers when regulators ask about data retention"
   - Bad: "We need to store all data for 7 years in an immutable database"
   - The first describes what needs to happen; the second prescribes how (and may not be the best approach)

2. **Provide decision rubrics with examples**
   - Instead of abstract rules, ask stakeholders to decide concrete cases
   - Show edge cases and gray areas
   - This reveals the true requirement when abstract descriptions are ambiguous

3. **Distinguish constraint types**
   - **Permanent vs. temporary**: Is this a fundamental requirement or a current regulatory requirement that might change?
   - **Critical vs. nice-to-have**: "The regulator will be unhappy" vs. "we can't operate legally" are vastly different risk levels
   - **Hard limits vs. quality issues**: Implementers need to know whether constraints are physically impossible, expensive, or just difficult

4. **Watch for language barriers**

   Common words have opposite meanings across disciplines:

   - **"Must"**: Non-technical stakeholders mean "we need a defensible argument for why we did this." Engineers hear "mathematically guaranteed in all scenarios." Ask: "What happens if this fails 0.1% of the time?"

   - **"Best practice"**: Lawyers mean "documented industry standard; ignoring it is evidence of negligence." Engineers hear "optional recommendation." Ask: "What's the risk if we don't do this?"

   - **"Secure"**: Could mean anything from "prevents casual access" to "resists nation-state attacks." Ask: "Secure against what threat? What's the consequence if breached?"

5. **Show the experience, not the architecture**
   - When proposing solutions to stakeholders, demonstrate what users will see and do
   - Don't explain the technical implementation unless asked
   - Ask: "Does this solve your problem?" not "Is this the right architecture?"

6. **Explain constraint difficulty clearly**
   - "Impossible due to fundamental limits" (e.g., physical laws, CAP theorem)
   - "Expensive but possible" (e.g., requires significant resources)
   - "Difficult quality-wise" (e.g., increases bug risk, maintenance burden)
   - Different constraint types warrant different tradeoff discussions

### Step 3: Identify All Stakeholders

Probe for everyone who has an interest in this problem:

**Primary stakeholders:**

- "Who will use the solution you build?"
- "Who is paying for this to be built?" (if applicable)
- "Who has to maintain it?"

**Secondary stakeholders:**

- "Who might be affected by how this is built?"
- "Who has regulatory or compliance interests?"
- "Are there any external reviewers or auditors?"

**Hidden stakeholders:**

- "Who would be upset if this went wrong?"
- "Who do you need approval from?"
- "Are there any domain experts whose input matters?"

#### Classify each stakeholder

Once you've identified stakeholders, classify each along two axes:

**Aligned vs. adversarial:**

An *aligned* stakeholder is one the builder wants to succeed — users, customers, the operations team. An *adversarial* stakeholder is one the builder wants to fail — an attacker, a spammer, a competitor trying to scrape data.

Most stakeholder lists only capture aligned stakeholders. Actively probe for adversarial ones:

- "Who might try to misuse this system?"
- "Who would benefit from this system failing?"
- "Are there bad actors in this space? What do they typically try to do?"

A single person can be both aligned and adversarial in different contexts. A social media user is aligned in general (the point is to create value for them), but adversarial when they're spamming or harassing other users. When this happens, track the aligned and adversarial personas separately and note that they can be the same person.

**Direct vs. indirect:**

A *direct* stakeholder knowingly engages with the system — users, administrators, API consumers. An *indirect* stakeholder may not even know the system exists but is still affected by it.

Indirect stakeholders are easy to miss and important to find:

- "Who could be affected by this system without choosing to use it?"
- "Are there people whose data might be in the system without their knowledge?"
- "If this system does something wrong, who gets hurt besides the users?"

For example, in a photo sharing app, the people uploading photos are direct stakeholders, but the people *appearing in* the photos are indirect stakeholders — a "search by image" feature could have serious consequences for them, even if they've never heard of the service.

#### For each stakeholder, understand

- What are their characteristics? (technical level, constraints, context)
- Are they aligned or adversarial? (or both, in different contexts)
- Are they direct or indirect?
- What do they need from the system? (For adversarial stakeholders: what are they trying to achieve against it?)
- What would make them unhappy? (For indirect stakeholders: what harms could reach them?)

### Step 4: Clarify Scope and Non-Scope

Ask boundary questions:

- "What's explicitly out of scope for this?"
- "What related problems are you NOT trying to solve?"
- "Where does this end and other systems begin?"
- "What can you assume already exists or works?"

Clear boundaries prevent scope creep and help evaluate solutions.

### Step 5: Extract Requirements

From the problem and stakeholders, derive the "must-haves":

- "What absolutely must be true for any solution to work?"
- "What constraints are non-negotiable?" (legal, technical, business)
- "What would make a solution unacceptable?"
- "Are there performance, security, or other quality requirements?"

Requirements should be:

- **Testable**: You can verify if they're met
- **Necessary**: The solution fails without them
- **Traceable**: Clear why they exist (which stakeholder need, which problem aspect)

### Step 5.5: Identify Open Questions (Discovery Check)

As you've probed the problem, stakeholders, and requirements, step back and assess: **are there fundamental unknowns that would change the solution approach?**

This is the "discovery check." Most projects pass through it quickly — the problem is clear enough to proceed. But some projects have genuine unknowns that need to be resolved before solutions make sense. Catching this early prevents wasted effort on solutions built on unexamined assumptions.

**Signs you're in a "discovery" situation:**

- Many possible solution paths, and the choice between them depends on things nobody knows yet
- The right approach to the problem isn't clear despite thorough clarification
- Pushing hard on "why is this the problem?" or "why is this the right approach?" reveals genuine gaps in knowledge — not just missing details, but structural uncertainty
- Stakeholders disagree not because of different priorities, but because of different beliefs about facts that haven't been established
- You keep hearing "it depends on whether X is true" and nobody knows if X is true

**If you identify open questions:**

1. **Capture them clearly.** Write each question to `.clarity-protocol/goal/open-questions.md` using the format below. Be specific — "Can we achieve real-time processing at our scale?" is actionable; "Is this technically feasible?" is not.

2. **Assign a resolution strategy** to each question:
   - **Prototyping** — build something minimal to test a specific hypothesis, then return to problem clarification with findings. Use this when the question is "does this approach actually work?" and the fastest way to find out is to try.
   - **Research** — design investigations or experiments to answer the question. Use this when the answer requires gathering information that doesn't exist yet.
   - **Thinking** — the answer is reachable through deeper discussion right now. Use this when the question is really about organizing what's already known, not discovering new information.

3. **Continue clarifying.** Open questions don't stop problem clarification — they refocus it. The remaining steps (conflicts, success criteria, document updates) still apply, but they should acknowledge the uncertainty. Success criteria in particular may be conditional: "If X turns out to be true, success looks like A; if not, success looks like B."

**Special case: pervasive uncertainty about what users need.** Sometimes the open questions aren't individual unknowns but a general uncertainty about what the right product or solution even is — the "product-market fit" problem. Signs of this: you know people want *something* but not what, stakeholders can describe pain but not what relief looks like, or every proposed solution feels equally plausible and equally uncertain. This isn't a question you can write down and resolve; it's a signal that the entire solution should be structured around rapid experimentation. In this case, don't try to capture individual questions — instead, note in `goal/open-questions.md` that the project is in an exploratory phase, and when you proceed to solution-brainstorming, frame the goal as building infrastructure for rapid experimentation rather than a final solution. (See the "Rapid Prototyping at Scale" strategy in the discovery projects design notes for more on this idea.)

**If no open questions surface** — which is the common case — write a brief confirmation to `goal/open-questions.md`:

```markdown
# Open Questions

No fundamental unknowns were identified during problem clarification. The problem is well-enough understood to proceed to solutions.
```

Then record the document state:

```bash
python -m clarity_agent.protocol.packet_status . --record goal/open-questions.md
```

**Document format for open questions:**

```markdown
# Open Questions

## Q1: [Sharp, specific question]

**Status:** open | investigating
**Why it matters:** [What decisions or solution paths this blocks]
**Strategy:** prototyping | research | thinking
**Findings:** [What we've learned so far — updated as investigation proceeds]
```

**When a question is resolved, move it out of this file.** Do not mark questions as resolved in `open-questions.md` — the packet renders open questions prominently near the top, so resolved entries left here clutter the reader's view. Instead, **move the entry** to `goal/resolved-questions.md` and add the resolution:

```markdown
## Q1: [The question]

**Status:** resolved
**Why it matters:** [preserved from original]
**Strategy:** [preserved from original]
**Findings:** [preserved from original]
**Resolution:** [Final answer]
```

Then re-record `goal/open-questions.md`. If resolving a question changes the problem understanding, update `problem.md` and the other goal documents accordingly — this will naturally trigger staleness on downstream documents.

### Step 6: Look for Conflicts and Tradeoffs

Identify where stakeholder needs might conflict:

- "Do any stakeholders have opposing needs?"
- "Are there tradeoffs between requirements?" (e.g., security vs. usability)
- "How should we prioritize when we can't satisfy everything?"

Surfacing conflicts now prevents surprise disagreements later.

### Step 7: Articulate Success

Get specific about what "solved" looks like:

- "How will you know this is working?"
- "What does success look like for each stakeholder?"
- "What metrics or indicators matter?"
- "What's good enough vs. perfect?"

Success criteria help you know when to stop and when to course-correct.

### Step 7.5: Clarify Fuzzy Criteria

Sometimes users have an intuitive understanding of what they want, but can't express it precisely. **This is a critical issue when:**

1. **The criteria determine if the solution is acceptable** - If you can't tell whether you've succeeded, you can't know when to stop
2. **The criteria must be applied by others** - If decisions at scale need to be made using these criteria, everyone must understand them the same way
3. **There's an expectation of "magic"** - If any step requires someone to "just know" what another person intends without explicit communication

#### Technique 1: Outrageous Examples (for success criteria)

When criteria are vague, propose scenarios that technically satisfy them but clearly shouldn't:

> **User**: "The system should be fast."
>
> **You**: "If it responds in 30 seconds, would that be fast enough? Or if it's instant for one user but takes 5 minutes when there are 10 users, does that count as fast?"
>
> **User**: "No, 30 seconds is way too long! And it shouldn't slow down with more users."
>
> **You**: "What response time would feel fast to you? And how many concurrent users should it handle at that speed?"

By proposing examples that are clearly wrong, you help users articulate what "right" actually means.

#### Technique 2: Criteria Clarification Process (for decision-making criteria)

When criteria need to be applied at scale or by multiple people (human or AI), use this rigorous process:

1. **Agree on the goal**: Write down what these criteria are meant to achieve. Ensure everyone agrees. (This is the rest of the problem clarification process, focused specifically on the criteria's purpose.)

2. **Write the criteria**: Express the decision-making criteria as they will actually be presented to whoever uses them.

3. **Generate test examples**: Create diverse example situations and ask the criteria author how each should be decided:
   - Examples clearly on either side of the line
   - Gray area examples near the boundary
   - Edge cases

   **Critical**: Help generate examples, but do NOT influence the author's decisions about outcomes. Your goal is to extract their intuition, not shape it.

4. **Test for consistency**: Give the criteria and examples (without the author's answers) to people similar to those who will use them. Ask them to decide each example. "Uncertain" is a valid answer.

5. **Iterate**: Repeat steps 2-4 until decision-makers reliably agree with each other and with the criteria author.

6. **Capture the result**: Document:
   - The final criteria
   - The test examples and their correct answers
   - Use these examples as "unit tests" for the criteria—when criteria need refinement, when new decision-makers are onboarded, or when circumstances change

**Important**: This process typically requires at least three iterations, even with experienced authors. This is normal and expected.

#### Example

> You're building a content moderation system. The requirement is "remove harmful content."
>
> **After iteration 1**: "Remove content that promotes violence or illegal activity."
>
> **Test examples expose gaps**: What about:
>
> - News articles describing violence?
> - Discussion of drug legalization?
> - Video game violence?
> - Medical procedures that look graphic?
>
> **After iteration 3**: Clear criteria with specific guidance for each category, plus 50 test examples showing edge cases and how to handle them.

#### Technique 3: Detecting "Magic"

If any step in the problem requires someone to "just know" what another person intends, **flag this immediately**:

> "I notice this step assumes [person/system] will know [thing] without being told. How will they actually know that? Should we make that communication explicit?"

Ensure there's space in both problem and solution for interactive conversation so people can confirm shared understanding.

### Step 8: Update problem.md

Rewrite the problem statement to capture what you've learned:

```markdown
# Problem Statement

[Clear articulation: What problem is this solving? Include context that explains why this matters.]

## Why This Matters

[Impact of solving or not solving this problem. Who is affected and how?]

## Scope

**In scope:**
- [What this addresses]

**Out of scope:**
- [What this explicitly doesn't address]

## Success Criteria

[What does "solved" look like? How will you know it's working?]
```

### Step 9: Update stakeholders.md

For each identified stakeholder, create or update their section:

```markdown
# Stakeholders

## [Stakeholder Name]

**Type:** aligned | adversarial | dual (aligned in [context], adversarial in [context])
**Engagement:** direct | indirect

**Characteristics:** [Context that's not obvious from the name: technical level, constraints, relevant background]

**Goals:** [What this stakeholder needs from the system. For adversarial stakeholders, what they are trying to achieve against the system — their objectives.]

**Concerns:** [What would make them unhappy or what they're worried about. For indirect stakeholders, what harms could reach them without their knowledge or consent.]
```

For dual-nature stakeholders, document the aligned and adversarial personas in separate sections, noting that they can be the same person in different contexts.

### Step 10: Update requirements.md

List all the must-have requirements:

```markdown
# Requirements

Any solution must:

## Functional Requirements

1. [What the system must do]
2. [...]

## Non-Functional Requirements

### Performance
- [Speed, throughput, latency requirements]

### Security
- [Security requirements]

### Reliability
- [Uptime, data integrity, error handling]

### Usability
- [User experience requirements]

### Compliance
- [Legal, regulatory, policy requirements]

## Constraints

- [Technical constraints: languages, platforms, existing systems]
- [Business constraints: budget, timeline, resources]
- [Organizational constraints: team size, approvals needed]
```

### Step 11: Verify Alignment

Review what you've written with the user:

> "Based on our conversation, here's my understanding:
>
> **Problem**: [One-sentence summary]
>
> **Key stakeholders**: [List them]
>
> **Must-haves**: [Top 3-5 requirements]
>
> Does this capture what you're trying to achieve? Anything I'm missing or misunderstanding?"

Iterate until they confirm alignment.

### Step 12: Update summary.md

Once the problem is understood, write a summary that makes someone *care* about this project. This isn't a technical abstract — it's the answer to "tell me about what you're working on" from someone who's genuinely interested. Write it conversationally, like you're explaining it to a smart friend over coffee.

A good summary has:

- **A problem that resonates** — what's frustrating, broken, or missing? Make the reader feel it.
- **A spark of the idea** — what's the insight or approach? Just enough to be intriguing.
- **Why it matters** — who benefits and why should anyone care?

Keep it to a few short paragraphs. No bullet-point specs, no jargon dumps. If it reads like a technical document, rewrite it until it reads like a person talking about something they're excited about.

If there's no solution yet, the summary focuses on the problem — but it should still be engaging, not clinical. Once a solution exists (via solution-brainstorming), the summary will be updated to include what the project actually *is*.

Show the proposed summary to the user before writing it:

> "Here's how I'd introduce this project to someone new:
>
> [Draft summary]
>
> Does that capture the spirit of what you're doing? Want to adjust the tone or emphasis?"

Iterate until they're happy with it, then write it to `.clarity-protocol/summary.md`.

## Sub-Processes

This process might naturally lead to:

- **solution-brainstorming.md** - Once the problem is clear, explore solutions
- **discovery-prototype.md** - If an open question's strategy is "prototyping," build a minimal, disposable prototype to test a specific hypothesis
- **discovery-research.md** - If an open question's strategy is "research," design and execute a structured investigation program
- **decision-guidance.md** - If stakeholder conflicts require explicit decisions

## Outputs and Updates

This process updates:

- `.clarity-protocol/goal/problem.md` - Refined problem statement with scope and success criteria
- `.clarity-protocol/goal/stakeholders.md` - Complete stakeholder list with their needs and concerns
- `.clarity-protocol/goal/requirements.md` - Comprehensive requirements organized by category
- `.clarity-protocol/goal/open-questions.md` - Open questions requiring investigation, or confirmation that none exist
- `.clarity-protocol/summary.md` - Short project title and elevator pitch

After writing, record the updated document state so the packet status checker has current baselines:

```bash
python -m clarity_agent.protocol.packet_status . --record summary.md goal/problem.md goal/stakeholders.md goal/requirements.md goal/open-questions.md
```

## Success Indicators

You've achieved problem clarity when:

- You can explain the problem in 1-2 sentences and people nod
- All stakeholders are identified and their needs are documented
- Requirements are specific enough to evaluate solutions against
- The team agrees this is the problem to solve
- When someone asks "why?", you have clear answers

## Common Pitfalls

**Pitfall: Accepting the initial framing of the goal**

The user states a goal; you accept it and start optimizing within it. If the stated goal is really a means to a goal one level up, you'll do good work toward the wrong endpoint. Run Step 2.25's framing pressure-test even when the goal sounds concrete and well-formed — *especially* then.

**Pitfall: Jumping to solutions**

If the user starts describing what to build instead of what problem exists, gently redirect: "That sounds like one possible solution. Help me understand the problem that would solve..."

**Pitfall: Accepting vague requirements**

"It should be fast" isn't a requirement. Push for specifics: "How fast? What response time would be acceptable?"

**Pitfall: Missing stakeholders**

The obvious users are easy to identify. The hidden stakeholders (compliance, support, adjacent teams) get forgotten. Explicitly ask about each category.

**Pitfall: Confusing wants with needs**

Requirements should be necessary for success, not nice-to-haves. Challenge each one: "What happens if we don't have this?"

**Pitfall: Documenting everything they say**

Synthesize. If they talk for 10 minutes, your problem statement should still be 2 paragraphs. Capture the essence, not the transcript.

## Next Steps

After problem clarification, run **clarity-agent** again to assess what needs attention next. Typical follow-on processes are:

- **solution-brainstorming.md** - Now that the problem is clear, explore solutions
- **architecture-design.md** - If the solution approach is known, design the implementation
- **failure-analysis.md** - Even before a solution, start thinking about what could go wrong
