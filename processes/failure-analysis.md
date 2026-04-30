# Failure Analysis

This process takes raw failure modes from the brainstorming pool, discusses them with the user, groups them into coherent failure modes, and develops detailed failure chains with intervention points.

## Overview

Brainstorming gives you a large collection of "things that could go wrong." Analysis turns that into a structured understanding of *how* things go wrong — the sequences of events, the moments where harm begins, and the points where intervention is possible.

The key insight is that many raw failure modes share common patterns. "SQL injection in login" and "SQL injection in search" are different manifestations of the same underlying failure: unvalidated user input reaching an interpreter. By grouping related failures and developing shared chains, you get a tractable set of failure modes (typically ten or fewer for most systems) instead of an overwhelming list of individual problems.

This process also looks for commonalities *across* failure modes — intervention points that appear in multiple chains, mechanisms that could address several failure modes at once. These "pinch points" are especially valuable for architecture and design, because a single well-placed intervention can address many failures simultaneously.

**This process has two phases: automated reduction, then interactive analysis.** First, you do as much grouping as you can without user input — deduplication, prior-state triage, merging obvious fits into existing groups, discarding non-meaningful failures. This automated pass typically handles the majority of raw failures. Then, for the remaining ambiguous cases, you work through them interactively with the user, building chains collaboratively and deciding groupings together. The user can steer the interactive phase — picking which failure to discuss next, brainstorming new ones, reviewing existing groups, or transitioning to management planning.

## When to Use This Process

Run this process when:

- The brainstorming pool has raw failure modes ready for analysis
- New raw failure modes have been added to the pool (incremental analysis)
- You want to regroup existing failure modes based on new understanding
- The solution or architecture has changed and existing groupings may need revision

## Inputs Needed

Before starting, you should have:

- Raw failure modes in a brainstorming mailbox (from brainstorming)
- `processes/failure-reasoning-guidelines.md` — Shared guidelines on analyzing the complete system and focusing on meaningful harm. Read these first; they inform how you triage and analyze failures.
- `.clarity-protocol/goal/problem.md` — Context for what's being built
- `.clarity-protocol/goal/stakeholders.md` — Who is affected
- `.clarity-protocol/solution/solution.md` — What's being built (if available)
- `.clarity-protocol/solution/architecture.md` — How it's built (if available)

If existing failure mode documents already exist in `.clarity-protocol/failures/`, you'll integrate new raw failures into the existing structure where they fit.

## Process Steps

### Step 1: Set Up

**Consume the mailbox** by taking a snapshot:

```bash
python -m clarity_agent.protocol.mailbox snapshot --name failure-brainstorm
```

This moves all items from the mailbox into `archive/failure-brainstorm/snapshot-YYYYMMDD-HHMMSS/`, leaving the mailbox empty. Any new brainstorming that happens during analysis goes into the same mailbox, while analysis works from the stable snapshot.

**Load context**: Read the problem, stakeholders, solution, architecture, the shared failure reasoning guidelines (`processes/failure-reasoning-guidelines.md`), and any existing failure mode documents in `.clarity-protocol/failures/`.

**Tell the user what's happening:**

> "We have [N] raw failure modes from brainstorming. [If existing groups:] There are also [M] grouped failure modes from previous analysis. I'm going to do an initial pass to handle the obvious cases — deduplication, pre-existing issues, clear fits into existing groups — and then we'll work through whatever's left together."

### Step 2: Automated Reduction

Before involving the user, do as much grouping and filtering as you can on your own. The goal is to reduce the set of raw failures to only those that genuinely need human judgment. Work through these operations in order:

#### 2a: Discard non-meaningful failures

For each raw failure, check whether it leads to real harm to a non-adversarial stakeholder in this system's actual context (Guideline 2 in the shared guidelines). If not, discard it with a brief note explaining why. For example, "what if an arbitrary user does X" is not meaningful for a personal-use tool.

#### 2b: Prior-state triage

For each remaining raw failure, assess whether it also exists before this solution is implemented. Use thinker-provided `Pre-existing` tags as a starting point, but apply your own judgment.

- **Pre-existing, not worsened by the solution**: Group these together as **"Existing issues"** — a single failure mode document with the shared management plan of "keep handling as before." This group can include failures from very different domains because what unites them is the management approach, not the mechanism. No individual chain analysis needed.
- **Pre-existing but worsened or changed**: Keep for further analysis. Note how the failure manifests today and what's different.
- **New**: Keep for further analysis.

#### 2c: Deduplicate

Identify obvious duplicates and near-duplicates — raw failures that describe the same thing from different angles or in different words. When two thinkers independently identify the same failure (e.g., "SQL injection through user input" and "unvalidated input in database queries"), keep the more detailed one and note the other as a duplicate.

#### 2d: Merge into existing groups

If there are existing failure mode documents from previous analysis rounds, check whether any remaining raw failures are clearly variants of those existing groups. A raw failure is a clear fit when:

- The underlying mechanism is the same (just a different instance or context)
- The existing group's failure chain covers this variant with minimal modification
- Adding it as a variant would make the group more complete, not less coherent

For clear fits, add them to the existing group's Variants list. Don't force ambiguous cases — those go to the interactive phase.

#### 2e: Cluster remaining failures

Among the raw failures that survived the previous steps, look for obvious clusters — sets of failures that clearly share an underlying mechanism and would naturally form a group. For example, multiple injection-related failures (SQL injection, XSS, command injection) might cluster around "unvalidated input reaching an interpreter."

For each cluster you identify with high confidence:

- Draft a group name and brief summary
- Note which raw failures belong to it
- Draft a preliminary failure chain if the mechanism is clear

Don't force marginal cases into clusters. If you're not sure whether two failures belong together, leave them separate for the interactive phase.

### Step 3: Present Results

Present the automated reduction results to the user. Be transparent about every decision so the user can correct mistakes:

> "Starting from [N] raw failures, I've done an initial pass:
>
> **Handled automatically:**
> - **[D] discarded** as not meaningful in this context: [brief list with reasons]
> - **[P] pre-existing issues** grouped as 'Existing issues' (solution doesn't worsen them): [brief list]
> - **[U] duplicates** removed: [brief list, noting what they duplicated]
> - **[E] merged into existing groups**: [list, noting which group each joined]
> - **[C] new groups drafted** from obvious clusters: [list each group name with its member failures]
>
> **Remaining for discussion: [R] failures** that need your input — either because the right grouping isn't obvious, or because they might form new failure modes that need chain development.
>
> Does the automated grouping look right? Anything I should move or undo?"

If this is the user's first time through failure analysis, add a brief explanation:

> "For the remaining failures, we'll work through them together — discussing what's really going on, developing failure chains (the sequence of events from initial conditions through harm and recovery), and deciding how to group them."

After the user confirms (or adjusts), write the "Existing issues" group document and any drafted cluster documents. Then proceed to the interactive loop for the remaining failures.

### Step 4: The Interactive Analysis Loop

This is where human judgment matters. The automated phase handled the obvious cases; this phase handles everything that's genuinely ambiguous or needs discussion to resolve.

Present the user with three activities they can choose between. After completing any activity, offer the choices again.

#### Activity A: Discuss an Ungrouped Raw Failure

This is the most common activity — working through a raw failure from the pool.

**Pick one.** Suggest a raw failure that seems significant or that you think might seed a useful group. The user can choose a different one.

**Talk it through.** This is a conversation, not a form to fill out:

- What's really going on here? Is the description accurate?
- Who gets harmed, and how?
- What's the sequence of events? Walk through it step by step.
- Where does harm actually begin? Where does it stop?
- Are there points where the chain could be interrupted?

**Develop the failure chain collaboratively.** Draft the chain based on the discussion — the user refines it. See "How to Develop Failure Chains" below for the detailed approach.

**Decide the outcome:**

- **New group**: This failure mode is distinct from anything identified so far. Create a new failure mode document (see "Failure Mode Document Format" below) with this as the seed.
- **Fits existing group**: This is a variant of an existing grouped failure mode. Add it to that group's Variants list, and update the chain if this variant reveals new steps or intervention points.
- **Reject**: This isn't actually a failure mode — it doesn't end in real harm to a non-adversarial stakeholder in this system's actual context (see Guideline 2 in the shared guidelines), or it's a clear duplicate of something already captured. Note why and move on.

**After resolving**, update the user on progress and offer the three activities:

> "[N] raw failures remaining, [M] groups so far. What would you like to do next — work through another raw failure, review one of the groups we've built, or brainstorm more?"

#### Activity B: Review an Existing Grouped Failure Mode

Sometimes the user wants to look at a group that's been formed — to check the chain, reconsider the grouping, or discuss management.

- Look at a grouped failure mode's chain and intervention points together
- Discuss whether the chain is complete, whether the grouping still makes sense
- If the group should be split (turns out to contain genuinely different failures), split it
- **If the failure is well-understood and the user wants to discuss what to do about it**, transition to the **failure-management** process guide for that specific failure. When management planning for that failure is done, return to the analysis loop.

#### Activity C: Brainstorm Additional Failures

Sometimes the discussion surfaces new "what could go wrong" ideas that weren't in the original pool.

- Have a freeform conversation about what else could go wrong
- Write any new raw failures to the brainstorming mailbox via `python -m clarity_agent.protocol.mailbox write --name failure-brainstorm --file FILENAME`
- These become available for Activity A in the next iteration of the loop

#### Breaking Out

At any point, the user can say they want to work on something else. This is fine — analysis doesn't have to happen all at once.

- All grouped failures are already written to files as they're resolved, so nothing is lost
- Update the failures index (see Step 6)
- Hand off to the **clarity-agent** main loop (Step 1: reassess the state)
- When the user returns to failure analysis later, pick up where you left off — the remaining ungrouped raw failures are still in the consumed snapshot, and existing groups are in the failure mode documents

### Step 5: Identify Cross-Cutting Patterns

This isn't a separate phase — it happens naturally as patterns emerge during the analysis loop.

After several failures are grouped, look across the chains for:

- **Shared intervention points**: An intervention point that appears in multiple chains is a "pinch point" — a place where a single mechanism could address many failures. These are especially valuable for architecture.
- **Shared mechanisms**: A single system (e.g., input validation, rate limiting, audit logging) that addresses intervention points across multiple failure modes.
- **Cascade relationships**: Failure A enabling Failure B. Document these connections so management can consider them together.

When you notice a pattern, mention it to the user:

> "I'm noticing that [pattern] — [Failure X] and [Failure Y] both have intervention points around [shared concern]. That suggests [architectural insight]."

Update the failures index and individual failure documents with cross-cutting observations as they emerge.

### Step 6: Wrap Up

When the user is satisfied or the ungrouped pool is empty:

- Update the failures index with the current state (see "Failures Index Format" below)
- The consumed brainstorming snapshot (in `archive/failure-brainstorm/`) is kept for provenance.
- Communicate a summary and offer next steps:

> "[M] failure modes identified from [N] raw failures. [If any remaining:] [R] raw failures are still ungrouped — we can return to those later.
>
> [If cross-cutting patterns:] Several failure modes share common intervention points — notably [pattern]. This suggests [architectural insight].
>
> Would you like to:
>
> - Continue with failure management (developing plans for how to handle these)?
> - Return to any of these groups to refine them?
> - Work on something else?"

**Whatever the user chooses, keep the conversation going.** Hand off to the appropriate process, or return to the clarity-agent main loop.

## How to Develop Failure Chains

A failure chain is a sequence of events that describes how things go wrong. This is the core analytical work — take time with it.

A good chain should:

- **Use steps that are as generic as possible**, keeping only the details that matter to the failure while leaving everything else abstract. This allows the chain to cover all variants in the group.
- **Clearly identify the moment at which harm actually occurs.** Mark this with **harm begins**. A violation of a principle doesn't count as harm unless it leads to someone or something being actually harmed.
- **Continue beyond the moment of harm** to include the recovery process. Mark when harm stops (**harm ends**) — when no more damage is being done. Continue until the system reaches equilibrium.
- **Include branch points** where the chain can diverge (e.g., post owner vs. other viewer responding to a harmful comment).
- **Annotate when various actors become aware** of the harm. If the operator only learns about a failure via the press, many things had to happen before that — usually including the onset of actual harm.

**Annotate chains with:**

- **Intervention points**: Moments where the chain could be stopped or diverted. Note what kind of intervention (prevention, detection, mitigation, recovery) and any initial thoughts on how.
- **Observations**: Notes worth preserving about how a step works, why it matters, or what makes it tricky.

**Example chain** (from a social media comments failure):

```text
1. Initial user makes a post. Non-adversarial users may comment.
2. Adversarial user discovers this post, e.g. through system recommendations.
   - *Intervention point:* If we could identify (user, post) pairs likely to
     lead to negative interaction outcomes, we could avoid recommending those.
3. Adversarial user makes a hostile comment.
   - *Intervention point:* Warning the commenter that their comment may be
     interpreted as adversarial may stop accidentally adversarial users.
   - *Intervention point:* If we can identify a hostile comment before it's
     shown to users, we can mask it pending moderation.
4. A user views the comment and is activated. **harm begins**
5. The user wants the comment removed and looks for a way to make this happen.
   - *Intervention point:* The faster they can find this control, the better.
   - *Branch point:* Post owner can remove the comment for everyone;
     non-owner can hide it from their own view.
   - *Observation:* The service owner wants more detail about why the user
     flagged the comment, but we must prioritize "make it go away" before
     (or instead of) asking for details.
6. If step 5 succeeds, **harm ends** and the chain is complete.
7. Otherwise, activation recurs each time the user encounters the comment,
   returning to step 4. This continues until step 5 succeeds or the user
   disengages from the post.
8. Engagement drops as non-adversarial users depart, leaving only adversarial
   users. Overall platform engagement declines.
```

Chains don't need to follow a rigid template. Use the structure that best captures the failure's dynamics. Some chains are linear, some branch, some loop.

## Failure Mode Document Format

For each failure group (and significant independent failures), create a numbered document in `.clarity-protocol/failures/`:

**Filename**: `failure-NN-short-title.md` (e.g., `failure-01-injection-attacks.md`)

**Content**:

```markdown
# Failure: [Title]

## Summary

[What goes wrong and consequences for stakeholders. If this groups multiple
variants, mention them. Name the stakeholders affected.]

## Failure Chain

[The developed chain. Numbered steps with inline intervention
points, observations, branch points, and harm boundaries.]

## Observations

- **Severity:** [Critical/High/Medium/Low] — [Brief reasoning about the
  magnitude of harm when this failure occurs]
- **Related failures:** [Interactions with other failure modes]
- **Variants:** [Raw failures grouped under this mode, with source references]

## Intervention Points

[Summary of the intervention points identified in the failure chain,
organized by type. This collects the inline annotations into one place
for easy reference during failure management.]

### Prevention
- [How to stop this from happening]

### Detection
- [How to know it's happening]

### Mitigation
- [How to limit damage once it's happening]

### Recovery
- [How to restore safety after it's happened]

---

## Management Plan

[Not yet developed. Run failure management to develop a plan for this
failure mode.]
```

The line above "Management Plan" marks the boundary between analysis output and management output. Everything above it is produced by this process. Everything below it is produced by the failure management process.

**A note on severity vs. priority:** This template assesses severity — how bad things get when this failure occurs — without attempting to estimate likelihood. The goal is to develop management plans for *all* identified failure modes, not to rank them by severity × likelihood. See Principle 5 in `failure-management.md` for the full rationale.

## Failures Index Format

Update `.clarity-protocol/failures/failures.md` to reflect the current state:

```markdown
# Failure Modes

1. **[Title](failure-01-name.md)** (High) Brief description of what goes
   wrong — the mechanism and triggering conditions. What this means for
   affected stakeholders. Summary of the mitigation approach, or
   "**no mitigation plan**" if management planning hasn't been done yet.
2. **[Title](failure-02-name.md)** (Medium) ...

## Cross-Cutting Patterns

[Shared intervention points, pinch points, cascade relationships.]
```

Each entry should give a reader enough context to understand the failure mode
without opening the linked document. The severity rating follows the title in
parentheses. Summarize the management strategy if one exists; if not, say
"**no mitigation plan**" to make gaps immediately visible.

Update this index whenever a failure mode is created, updated, or managed.

## Observations

Append interesting footnotes to `.clarity-protocol/observations.md` — things worth recording but not part of the core failure index. This includes:

- **Coverage**: Which perspectives have been examined (thinker names and dates), and which are still pending.
- **Provenance**: Where failure modes originated (brainstorming sessions, thinker runs, user input) and how they were grouped.
- **Pattern notes**: Interesting interactions between failure modes, surprising findings, or observations about the system's overall risk profile that don't fit neatly into a single failure mode document.

This file is a log, not a summary — append new observations rather than rewriting. Readers who want the quick picture look at `failures.md`; readers who want the full story read `observations.md`.

## Outputs and Updates

This process creates/updates:

- `.clarity-protocol/failures/failure-NN-name.md` — Individual failure mode documents (analysis section only)
- `.clarity-protocol/failures/failures.md` — Organized index with severity and management status
- `.clarity-protocol/observations.md` — Coverage, provenance, and pattern notes (appended)

After writing, record the updated document state so the packet status checker has current baselines:

```bash
python -m clarity_agent.protocol.packet_status . --record failures/failures.md
```

## Success Indicators

You've completed a round of failure analysis successfully when:

- All raw failures in the consumed pool are accounted for (grouped, added to existing groups, or rejected with rationale)
- Each failure mode has a complete failure chain with harm boundaries marked
- Intervention points are identified and categorized
- Cross-cutting patterns are documented as they emerge
- The index clearly shows what's been analyzed and what needs management plans
- The user has participated in the analysis and understands the failure modes

## Common Pitfalls

**Pitfall: Skipping the automated phase or the interactive phase**

Both phases matter. The automated reduction (Step 2) handles obvious cases efficiently — don't force the user to manually confirm every deduplication or pre-existing triage. But the interactive phase (Step 4) is where human domain knowledge surfaces things you can't see — organizational dynamics, historical context, subtle distinctions between failures that look similar on paper. Don't skip either phase, and be transparent about what you did in the automated phase so the user can correct mistakes.

**Pitfall: Over-grouping**

Don't force unrelated failures together just to reduce count. If failures have different causes, chains, and interventions, keep them separate. A failure mode with "multiple failure chains" should be the exception, not the rule.

**Pitfall: Under-grouping**

"SQL injection in login" and "SQL injection in search" should be one failure mode. If the chain is the same except for one substitutable detail, group them.

**Pitfall: Hiding information during grouping**

When grouping, don't lose the specifics. Mention variants within the chain. The grouped failure mode should be *more* informative than any individual raw failure, not less.

**Pitfall: Rigid chain templates**

Don't force every failure chain into a seven-step linear sequence. Some chains branch, some loop, some are short and simple. Use the structure that best captures the failure's dynamics.

**Pitfall: Ignoring the sociotechnical system**

The system includes the humans (and AIs) who operate and use it. A perfectly secure authentication system that's too annoying to use will be bypassed. Include human behavior in failure chains.

**Pitfall: Prioritizing by severity times likelihood**

Don't try to rank failures by multiplying severity by likelihood. This approach was designed for insurance companies managing resource allocation across risk pools; it works well there but poorly for people designing and building systems. The product of large severity and small likelihood is statistical noise, likelihood is hard to estimate, and in computing the rates are high enough that likelihood is effectively 1. Instead, plan to handle all failures, and sequence work by urgency and cost of short-term mitigation if you need to.

## Next Steps

After failure analysis, typical next processes are:

- **failure-management.md** — Develop management plans for identified failures (can also be invoked during analysis for individual failures)
- **architecture-design.md** — Update architecture to incorporate key intervention points
- **solution-brainstorming.md** — If failures reveal the solution needs rethinking
- **decision-guidance.md** — If there are tradeoffs in how to handle failures
