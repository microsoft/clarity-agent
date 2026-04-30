# Architecture Design

Figure out how to implement the solution — the components, their relationships, and how the system works as a whole.

## Overview

You're designing a system that someone has to build, understand, operate, and modify. The goal isn't a technically impressive diagram — it's a design that makes the system *intuitive* to reason about and *practical* to implement.

As with solution brainstorming, you're already good at this. These instructions are here to remind you of things that are easy to lose sight of, not to micromanage the process.

## When to Use This Process

Run this process when:

- A solution approach is chosen and needs a technical design
- The architecture needs updating because requirements or the solution changed
- The team is confused about how the system fits together

## Inputs

Ground your thinking in:

- `.clarity-protocol/goal/problem.md` — What you're solving
- `.clarity-protocol/goal/stakeholders.md` — Who this is for
- `.clarity-protocol/goal/requirements.md` — What the solution must provide
- `.clarity-protocol/solution/solution.md` — The chosen approach

If the solution isn't defined yet, run **solution-brainstorming** first. Architecture without a clear solution direction is premature.

When in doubt about any aspect of the design — a tradeoff, a level of complexity, whether something needs to be configurable — look back to the problem, requirements, and stakeholders. They are your guides and limits.

## What to Keep in Mind

### Find the nouns and verbs first

Before diving into components and interfaces, clarify the fundamental objects the system manages and the actions they undergo. These are the "nouns" and "verbs" of your architecture, and getting them right matters more than almost any other design decision.

Good nouns and verbs are:

- **Intuitive**: People can reason about them without a manual. If you have to explain at length why something is modeled the way it is, the model is probably wrong.
- **Stable**: They don't change every time you add a feature. The right abstractions accommodate growth naturally.
- **Few**: A system with thirty kinds of object is hard to reason about. Aim for the smallest set that covers the problem space.

Look for analogies to existing systems. If your objects behave like something people already understand, lean into that — the borrowed intuition is enormously valuable. A planet-scale storage system might model datacenters as "warehouses" and network links as "shipping routes." The analogy isn't perfect (data is copied, not transported), but the way of thinking it enables — nearest-object routing, transport optimization — proves more useful than a technically precise but unfamiliar abstraction would.

The wrong nouns will haunt you. If the system's fundamental objects don't match how people think about the problem, every interface, every API, every explanation will require a translation step. That friction accumulates.

### The napkin test

Consider how someone would explain the system by drawing on a napkin. What boxes would they draw? What arrows? What would they label? This exercise reveals:

- The **natural components** of the system (the things people draw as boxes)
- The **key relationships** (the arrows between them)
- The **mental model** people use to reason about it (what gets emphasized, what gets omitted)

An architecture that looks like the napkin drawing is an architecture people can understand. This doesn't mean it needs to be simplistic — the napkin captures structure, not detail — but the high-level organization should match how people think about the system.

One specific consequence: if people need to both view and control objects in the system, consider making those happen through the same kind of interface. A unified way of interacting with the system's nouns is easier to learn, easier to explain, and usually easier to implement than separate read and write models (unless there's a strong reason to split them).

### The architecture has to survive contact with reality

As you design, keep asking:

- **Can the team build this?** The best architecture is one the actual team can implement and maintain. A design that requires expertise nobody has is a design that will be built badly.
- **Can someone operate this?** How does this get deployed? Monitored? Debugged at 3am? If you can't answer these questions, the architecture isn't finished.
- **What happens when things change?** Requirements will shift. Can the architecture accommodate reasonable changes without a rewrite?
- **What happens when things break?** Components will fail. The architecture should make failures visible and recoverable, not silent and cascading.

### Ask the user when it matters

The same principle from solution brainstorming applies: use your judgment, but bring the user in when:

- You face a genuine choice between approaches that lead to materially different systems
- You discover constraints or requirements that weren't captured
- You're making assumptions about the team, the infrastructure, or the operational environment

Technology decisions especially benefit from user input — they know their team's strengths, their existing infrastructure, and their operational constraints.

## Outputs

Update `.clarity-protocol/solution/architecture.md` with:

- The key nouns and verbs — what the system manages and what happens to those objects
- The major components and their responsibilities
- How components interact (data flows, protocols, patterns)
- Key technology decisions and their rationale
- How cross-cutting concerns are handled (security, reliability, observability — as relevant)
- Risks, open questions, and things that need validation

Also capture observations that surfaced during design — failure modes, edge cases, requirement gaps — in the appropriate places, just as with solution brainstorming.

### Include threat model diagram

At the end of `architecture.md`, include a Mermaid threat model diagram as a fenced ` ```mermaid ` block. The packet generator extracts it automatically. Write the diagram directly — you'll produce a better diagram than any code generator would.

The diagram should show the full system: components grouped by trust boundary, data flows between them, and threat-affected components highlighted. Include humans, external services, and business processes — not just software components. Make it readable at a glance by someone with zero threat modeling experience.

Also write `.clarity-protocol/system-design.json` with the same components, flows, and threats as structured data (for tooling that consumes it programmatically).

Also update `.clarity-protocol/solution/solution-summary.md` to incorporate architectural insights — especially nonobvious structural decisions and any design choices driven by failure mode analysis. See solution-brainstorming.md for the full specification of this document.

### Record document state

After writing, record the updated document state so the packet status checker has current baselines:

```bash
python -m clarity_agent.protocol.packet_status . --record solution/architecture.md solution/solution-summary.md
```

## Sub-Processes

This process might naturally lead to:

- **failure-analysis.md** — Stress-test the architecture for failure modes
- **decision-guidance.md** — If a technology or design decision needs structured analysis
- **solution-brainstorming.md** — If the architecture reveals the solution needs rethinking

## Common Pitfalls

**Pitfall: Designing in a vacuum**

Don't design the architecture without the user's input on team, infrastructure, and operational constraints. Ask.

**Pitfall: Getting the nouns wrong**

If the system's fundamental objects don't match how people think about the problem, everything downstream — APIs, UIs, conversations about the system — will be harder than it needs to be. Spend time here.

**Pitfall: Over-specifying**

Architecture is about structure and key decisions, not implementation details. Leave room for the people building it to make lower-level choices.

**Pitfall: Premature optimization**

Design for current requirements, not imagined future ones. Note where the architecture could evolve, but don't build for scale you don't need yet.

**Pitfall: Forgetting operations**

A system that works but can't be deployed, monitored, or debugged isn't finished.

## Next Steps

After architecture design, run **clarity-agent** again to assess what needs attention next.
