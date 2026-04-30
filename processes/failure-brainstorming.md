# Failure Brainstorming

This process generates raw failure modes through direct analysis and invites human contributions. Raw failures accumulate in a pool until they're ready for analysis and grouping.

## Overview

The goal of failure brainstorming is breadth: come up with as many things as possible that could go wrong. This is the creative, divergent phase — don't filter, don't group, don't worry about duplicates. That's what failure analysis is for.

Brainstorming can happen over time. Multiple runs can contribute, humans can add their own insights, and the pool grows until someone decides it's ready for analysis. This process can be run multiple times, each run adding to the same pool.

## Tools Available

You have Bash commands for recording your findings. **Always use these** — do not write files directly. Each command reads JSON from stdin. Your working directory is the project root; the tools auto-discover `.clarity-protocol/` from there.

### record_failure

Record a failure mode to the brainstorming mailbox:

```bash
python -m clarity_agent.ai_actions.brainstorm record-failure << 'EOF'
{
  "title": "Short title of what goes wrong",
  "description": "1-3 sentences: what fails, how, who is harmed"
}
EOF
```

Optional fields: `"additional_context"`, `"pre_existing"` (boolean), `"failure_chain"` (array of steps).

### record_suggestion

Record a suggestion to improve a project document:

```bash
python -m clarity_agent.ai_actions.suggestion record << 'EOF'
{
  "title": "Short title",
  "target_document": "goal/stakeholders.md",
  "suggestion": "What to add or change"
}
EOF
```

### recommend_deeper_analysis

Flag an area for specialist analysis (only when specialists are listed in system context):

```bash
python -m clarity_agent.ai_actions.brainstorm recommend-deeper << 'EOF'
{
  "thinker_name": "security-thinker",
  "rationale": "Why this specialist would add value"
}
EOF
```

### read_thinker_guide

Load a specialist's methodology guide (only when specialists are listed in system context):

```bash
python -m clarity_agent.ai_actions.brainstorm read-thinker-guide << 'EOF'
{
  "thinker_name": "security-thinker"
}
EOF
```

## When to Use This Process

Run this process when:

- Starting failure analysis for the first time (need raw material to analyze)
- The solution or architecture has changed significantly (new failure modes may exist)
- A domain expert wants to contribute failure ideas
- You want a specific analytical perspective (e.g., just security, or just UX)
- Someone thought of a new "what could go wrong" that should be captured

## Inputs Needed

Before starting, you should have at least:

- `.clarity-protocol/goal/problem.md` — To understand what you're trying to achieve
- `.clarity-protocol/goal/stakeholders.md` — To know who could be affected (especially adversarial and indirect stakeholders)

Ideally you also have:

- `.clarity-protocol/solution/solution.md` — What you're building
- `.clarity-protocol/solution/architecture.md` — How it's built

If the solution isn't fleshed out yet, that's okay. Brainstorming on the problem alone can surface important failure modes early. But the more context you have, the more specific the failures will be.

## Process Steps

### Step 1: Read Project Context

Read the available project documents to understand what you're analyzing:

1. Read `.clarity-protocol/goal/problem.md`
2. Read `.clarity-protocol/goal/stakeholders.md`
3. Read `.clarity-protocol/solution/solution.md` (if it exists)
4. Read `.clarity-protocol/solution/architecture.md` (if it exists)

Don't skip this step. You need real context to generate meaningful failures. If key documents are missing, note this and work with what's available.

### Step 2: Broad Analysis

Apply the failure reasoning methodology (provided in your system context) to analyze the system broadly. Think through:

- **System-in-use thinking** — How will real people actually use this? What happens when they're tired, rushed, confused, or malicious?
- **Component interconnects** — Where do components talk to each other? What happens when one fails, is slow, or returns unexpected data?
- **Stakeholder-by-stakeholder review** — For each stakeholder (including adversarial ones), what could go wrong from their perspective?
- **Human and AI fallibility** — Where do humans make mistakes? Where does AI produce wrong or harmful output?
- **Misuse scenarios** — How could this be deliberately abused or weaponized?
- **Cascading failures** — What small problems could snowball into large ones?

As you identify failure modes, **record each one immediately** using `record_failure`. Don't batch them up — record as you go. Each failure should:

- End in actual harm (not just a principle violation)
- Have a clear title that describes what goes wrong
- Include enough description to understand the failure without reading the full chain
- Optionally include a failure chain showing the step-by-step progression

When your analysis reveals gaps or ambiguities in project documents, use `record_suggestion` to note them.

### Step 3: Recommend Specialist Analysis

If specialist thinkers are available (listed in your system context), review your findings and recommend deeper analysis where specialist methodology would add value. Use `recommend_deeper_analysis` for each recommendation.

Present your recommendations to the user:

> "I've identified [N] potential failure modes in my broad analysis. I recommend deeper analysis in these areas:
>
> - **[Specialist Name]**: [rationale — what this specialist's lens would catch that broad analysis might miss]
>
> Would you like me to apply any of these specialist perspectives? Or would you prefer to explore a specific area first?"

### Step 4: Deepen on Request

When the user asks for deeper analysis in a specific area:

1. Use `read_thinker_guide` to load the specialist's methodology
2. Apply that methodology systematically to the project
3. Record additional failures using `record_failure`

You can also deepen without a specialist guide — if the user asks you to explore a particular area (e.g., "what about data privacy?"), do so using your own analytical reasoning and the failure reasoning methodology.

### Step 5: Invite Human Contributions

After your analysis, ask the user:

> "I've identified [N] potential failure modes so far. Based on your experience or domain knowledge, are there others we should consider? Things that might go wrong that automated analysis might miss?"

Human domain experts often know failure modes that general analysis can't discover — organizational dynamics, historical incidents, regulatory subtleties, cultural factors.

If the user contributes failures, help them formulate each one and record it using `record_failure` with source "human" (or the contributor's name/role if they specify).

### Step 6: Communicate Results and Hand Off

Summarize what was found:

> "I've brainstormed [N] potential failure modes:
>
> **Broad analysis**: [N] failures (e.g., [1-2 highlights])
> **[Specialist area]**: [N] additional failures (e.g., [1-2 highlights])
> [etc.]
>
> These are in the brainstorming pool, ready for analysis. Would you like to:
> - Add any failure modes from your own experience?
> - Explore a specific area more deeply?
> - Move on to failure analysis (grouping and chain development)?
> - Work on something else?"

**Whatever the user chooses, keep the conversation going.** This process doesn't end in silence — it ends by handing off to the next thing:

- If the user wants to add failures -> stay in this process, capture them, and ask again
- If the user wants deeper analysis -> apply the specialist lens and return to this step
- If the user wants failure analysis -> load and follow **failure-analysis** process guide
- If the user wants to do something else, or isn't sure -> re-enter the **clarity-agent** main loop

After any process completes, the user should never be left wondering what happens next.

## Outputs and Updates

This process creates/updates:

- `.clarity-protocol/mailboxes/failure-brainstorm/*.md` — Individual raw failure mode files
- `.clarity-protocol/mailboxes/failure-brainstorm/_config.json` — Mailbox configuration and status
- `.clarity-protocol/suggestion-box/*.md` — Document improvement suggestions (if any)

## Success Indicators

You've completed brainstorming successfully when:

- Multiple perspectives have examined the system (broad + specialist where relevant)
- Each raw failure mode ends in actual harm (not just a principle violation)
- The pool contains enough raw material for meaningful grouping
- The user has had the opportunity to contribute their domain knowledge

## Common Pitfalls

**Pitfall: Filtering too aggressively**

During brainstorming, the goal is breadth. Don't dismiss a potential failure because it seems unlikely — unlikely + severe is still important. Save filtering for analysis.

**Pitfall: Writing too much per failure**

A raw failure mode should be quick to write and quick to read. If you're spending more than a minute on one, you're doing analysis, not brainstorming. Capture the idea and move on.

**Pitfall: Too narrow a perspective**

Make sure you're thinking beyond just technical failures. Consider human factors, social dynamics, misuse, organizational issues, and cascading effects.

**Pitfall: Skipping human input**

Automated analysis works from general domain knowledge. Humans know the specific organizational, cultural, and historical context. Always ask.

**Pitfall: Not recording as you go**

Use `record_failure` as you identify each failure — don't try to batch them. This ensures nothing is lost and the user can see progress in real time.

## Next Steps

After brainstorming, run **failure-analysis** to group raw failures into coherent failure modes with full chains and intervention points.

If the pool isn't ready yet (more brainstorming needed), run this process again later with additional perspectives or human input.
