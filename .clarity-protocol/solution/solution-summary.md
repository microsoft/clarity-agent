# Solution Summary

## What We're Building

The Clarity Agent is an AI-powered thinking partner that helps people develop genuine clarity about what they're building, what could go wrong, and why they're making the choices they're making. It makes accessible the structured thinking techniques — problem clarification, failure analysis, decision documentation — that have historically required scarce expertise.

The agent focuses on the thinking-before-and-during-building phase. It does not generate code, manage tasks, or run deployments. Its job is done when the user has clarity and the artifacts exist.

## What the Experience Is Like

You're working in Claude Code (or a similar coding agent). You describe a project you're starting — say, a tool that syncs files between two systems. Instead of immediately helping you build it, the agent starts asking questions: What happens when the source and destination have conflicting changes? Who runs this tool, and how often? What does "done" look like for a sync that encounters an error?

Some of these feel obvious at first. Then one lands differently. You realize you've been assuming last-write-wins, but actually the right behavior depends on file type — and you hadn't thought about what happens to partially-written files. The agent captures that as a requirement. It wasn't in your head yet; it is now.

The agent works through problem clarification, stakeholders, requirements, solution, and architecture in conversation — not by handing you forms to fill out, but by asking questions and pushing back on answers that feel underspecified. When you say "it should be fast," it asks what fast means for your users and what the worst acceptable latency is. When you propose a solution, it asks what you considered and rejected, and why.

Then it runs failure analysis. A general thinker identifies broad failure modes across the system. It surfaces things like: what happens if the sync runs twice concurrently? What if the destination is temporarily unreachable mid-sync — do you retry, fail, or leave partial state? You type "deeper" and specialist thinkers run — security, human factors, operational — each examining the system from a different angle. Failures the general thinker missed appear.

Each failure gets a management plan: how to prevent it, detect it, limit damage, and recover. The agent doesn't let you skip this. It asks whether the plan would actually work if you walked through it step by step.

Everything is written to a `.clarity-protocol/` directory — markdown files, version-controlled alongside your code. When you come back three months later, or hand the project to someone else, or feed it to a coding agent, the rationale is there: not just what was decided, but why, and what was considered and rejected.

## How It Addresses the Problem

The problem has three hard parts: clarity requires iteration but most processes assume you have it; thinking about failure requires multiple perspectives most people don't have; and shared understanding is much harder than it looks. The agent addresses all three:

- **Iterative clarity**: Conversation-driven process guides that move from rough idea to testable problem statement, stakeholder map, requirements, solution, and failure modes — you don't need clarity to start.
- **Multi-perspective failure analysis**: A general thinker runs first, then recommends specialists (security, human factors, adversarial, operational) for deeper analysis. Multiple perspectives in one session, without a room full of experts.
- **Shared understanding artifacts**: The clarity protocol surfaces misalignments early and keeps reasoning alive across time, team members, and coding agents.

## Nonobvious Architectural Choices

**Capability first, products second.** The system is built as an intellectual corpus (Layer 1) from which everything else derives — full process guides (Layer 2), a condensed light guide (Layer 2), and infrastructure (Layer 3). Products are context-specific shells. The same methodology reaches a developer using Claude Code with full infrastructure and a solo builder using a bare Claude Project with no tools, without maintaining two separate systems.

**Two Layer 2 expressions, independently derived from Layer 1.** The full and light guides are not a port of each other — they are independently crafted for their environments. This prevents the full expression's tool-access assumptions from leaking into the light guide. The cost is that each must be updated when Layer 1 changes; the benefit is that each is genuinely suited to its context.

**MCP as the infrastructure portability interface.** The system exposes infrastructure as MCP tools via `src/clarity_agent/mcp/server.py` (run via `python -m clarity_agent.mcp`; eight tools, stdio/SSE/HTTP transport), making it available to any MCP-capable AI environment without embedding the codebase. Shell-access environments (Claude Code, CLI) can also invoke Python infrastructure directly — both paths coexist.

**Process guides as the logic layer.** Behavior is encoded in markdown, not Python. The system can be read, evaluated, and improved without running it — and works with any capable LLM. The cost is that guides aren't type-checked or tested as code; the benefit is that the logic is human-auditable and easy to adjust.

**General-thinker-first brainstorming.** A broad general thinker runs inline first, producing useful initial analysis quickly and recommending which specialists to invoke. This replaced running all thinkers in parallel, which was slower, more expensive, and produced less focused output.

## Key Design Elements Addressing Failure Modes

Three failure analysis findings became design constraints with as much weight as the architecture itself:

**Time to first insight** (FM01: user disengagement). Process guides are structured to surface a genuine challenge or insight early — looking for something to push back on from the first description, not after twenty minutes of information gathering. If the agent doesn't demonstrate concrete value quickly, users disengage before the process can help them.

**Invisible self-critique** (FM02: inadequate AI thinking). Critique guides teach the AI what to watch for in its own output at each phase — whether requirements are testable, whether failure modes are specific to this system or generic, whether a management plan would actually work. This shapes the agent's disposition without appearing as a visible step. No extra time cost; the agent simply holds itself to a higher standard as a natural part of the conversation.

**Conciseness by design** (FM01, FM03, FM04). Verbosity is a failure mode: it undermines engagement, hides shallow thinking, and enables ambiguous interpretation. Documents have a summary layer — critical content first, detail on demand. Length guidelines are captured in Layer 1 and enforced in both Layer 2 expressions.

**Coverage transparency** (FM04: failure analysis depth). The failures index shows which analytical perspectives have been applied and when, making gaps immediately visible. Failures without management plans are explicitly marked "**no mitigation plan**" — nothing looks done when it isn't.
