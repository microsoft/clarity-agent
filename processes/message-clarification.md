# Message Clarification

Build the narrative that explains what this project is and why anyone should care — starting with the general story and optionally developing audience-specific versions.

## Overview

Good messaging isn't marketing — it's a thinking tool. When you can articulate what the project is and why it matters in a way that resonates, it means you actually understand what you're building. When you can't, that's a signal that something in the design needs work. **If you can't tell a good story about the system, you don't have a good system.**

This process produces two artifacts:

- **`summary.md`** (required) — the project introduction. A name, a short narrative that explains the what and the why, written like you're talking to someone about something you care about. This is always the first thing someone reads.
- **`messaging.md`** (optional) — audience-specific narratives for projects that need to be explained to different groups. Each audience gets a version of the story that speaks to their concerns and priorities.

This is a conversational process. You're not filling in templates — you're helping the user find the words that feel true and land well.

## When to Use This Process

Run this when:

- The problem and solution are solid enough to tell a story about (both should exist, even if rough)
- `summary.md` is stale, reads like a mechanical spec, or doesn't exist yet
- The user is preparing to explain the project to people (stakeholders, investors, users, skeptics)
- The user is stuck and can't articulate what they're building — working on the narrative often unsticks the design itself

Don't run this before problem clarification and at least an initial solution exist. You can't tell a story about something you haven't figured out yet.

## Inputs

Ground your thinking in:

- `.clarity-protocol/goal/problem.md` — The problem you're solving
- `.clarity-protocol/goal/stakeholders.md` — Who's affected
- `.clarity-protocol/solution/solution.md` — What you're building
- `.clarity-protocol/notes.md` — Any items tagged `[for: message-clarification]`
- `.clarity-protocol/messaging.md` — If it exists, this is a revisit; read what's there

## Process

### 1. Start from what's changed

If this is a revisit (messaging.md or a substantive summary.md already exists), open with:

> "What have you learned since we last talked about this? Any conversations that changed how you think about the project, or reactions you didn't expect?"

This is the continuous iteration loop. Messaging improves through contact with the world — every pitch, every explanation, every confused look teaches you something. Capture that before doing anything else.

If this is the first time, open with the project's story:

> "Let me read through what we have so far and try to tell this back to you."

Read the problem and solution, then give your best shot at a two-to-three sentence summary. Ask: "Does that land? What's wrong with it?" This gives the user something concrete to react to.

### 2. Find the general narrative

Work toward a short narrative that answers: **What is this and why should you care?**

This is harder than it sounds. The temptation is to describe features or architecture. Resist that. The narrative should explain:

- What problem exists in the world (not the technical problem — the human one)
- What this project does about it
- Why that matters

Techniques that help:

- **The friend test.** "If you were explaining this to a smart friend over coffee, what would you say?" People are naturally better at verbal explanation than written. Capture the verbal version.
- **The 'so what?' chain.** For any claim, keep asking "so what?" until you hit something that matters to a real person. "We use a novel caching architecture" → so what? → "Pages load in under a second" → so what? → "Users don't abandon the workflow when they're in the middle of something important." That last one is the narrative.
- **What's the before and after?** Describe life before this project exists and life after. The contrast is the story.

When the user reads the narrative aloud and it feels honest and resonant — not perfect, but true — write it to `summary.md`.

### 3. Ask about audiences

> "Is there anyone specific you need to explain this to — anyone who might see it differently or care about different aspects?"

If the answer is no, you're done. Many projects only need the general narrative.

If the answer is yes, build `messaging.md`. For each audience:

**Identify the audience.** Who are they? Not by role, but by perspective. What's already on their mind? What are they worried about, excited about, skeptical of — even before they hear about this project?

**Find their version of the story.** The core facts don't change, but the emphasis shifts. An investor cares about market and defensibility. A user cares about what it does for them. A skeptic cares about what could go wrong. Each audience needs the narrative to start from *their* concerns and connect to *your* project.

**Address resistance directly.** If an audience is going to be suspicious or hostile, don't talk around it. Identify their specific concern and address it head-on. Talking around a concern comes across as shallow at best and deceptive at worst.

Structure each audience section:

```markdown
## Audience: [Name]

**Who they are:** [Defining properties — not demographics, but perspective and priorities]

**What's on their mind:** [Their top concerns, even unrelated to this project]

**The narrative:** [The story, told from their starting point]
```

### 4. Notice failures

As you work on messaging, you'll discover things:

- "This audience is going to hate that we do X" — that's a failure mode. Write it to the `failure-brainstorm` mailbox.
- "We can't explain why this is safe because we haven't thought it through" — that's a gap in the solution. Note it.
- "The story doesn't work because the problem statement is actually wrong" — that's a signal to revisit problem clarification.

Don't suppress these discoveries. They're among the most valuable outputs of this process.

### 5. Check consistency

All narratives — the general one and any audience-specific ones — must be consistent with each other and with reality. They emphasize different things, but they never contradict. If you find a contradiction, it usually means the underlying thinking isn't settled yet.

Critical requirements for every narrative:

- **Profoundly honest.** About what the project can and cannot do, what the risks and rewards are. Never lie or deceive.
- **Consistent.** Different framings of the same truth, not different truths.
- **Addresses concerns directly.** If an audience will worry about something, say what you're doing about it. Silence reads as evasion.

## Outputs

Update `.clarity-protocol/summary.md` — the general-audience narrative. Write it conversationally: a few short paragraphs, enough to make someone care, not enough to bore them. If it reads like a technical spec with bullet points, rewrite it until it sounds like a person.

If there are multiple audiences, write `.clarity-protocol/messaging.md` with audience-keyed sections.

After writing, record the updated state:

```bash
python -m clarity_agent.protocol.packet_status . --record summary.md
```

## Sub-Processes

This process might naturally lead to:

- **problem-clarification** — If the narrative reveals the problem statement needs work
- **solution-brainstorming** — If the narrative reveals gaps in the solution
- **failure-brainstorming** — If audience concerns surface new failure modes (write them to the mailbox)

And it's often triggered from:

- **solution-brainstorming** — Which writes a first-draft summary; this process refines it
- **problem-clarification** — When the problem is clarified enough to tell a story about

## Common Pitfalls

**Pitfall: Starting before the project is ready**

You can't tell a story about something you haven't figured out. If the problem or solution is still vague, work on those first. The narrative will come naturally once the thinking is solid.

**Pitfall: Describing features instead of telling a story**

"Our system uses a microservices architecture with event-driven..." is not a narrative. It's a spec. The narrative is about what changes for people and why that matters.

**Pitfall: Writing for approval instead of truth**

The goal isn't to make the project sound good. It's to explain it honestly in a way that resonates. If the honest version doesn't sound good, that's valuable information about the project, not a messaging problem.

**Pitfall: Trying to please every audience simultaneously**

Different audiences have different concerns. That's why they get different narratives. Don't water down the general narrative trying to preemptively address every possible objection — that produces something that resonates with nobody.

## Next Steps

After message clarification, run **clarity-agent** again to assess what needs attention next.
