# Clarity Protocol Agent

This file integrates the Clarity Protocol into your AI-assisted development workflow. The Clarity Protocol helps you build systems that actually work by maintaining shared understanding of what you're building, why, and what could go wrong.

## What This Does

When building software with AI assistance, three things commonly go wrong:

1. **The AI loses track** of what you're really trying to achieve as conversations get long
2. **Failure scenarios get overlooked** because nobody's thinking systematically about what could break
3. **Decisions get lost** once they scroll out of the chat history

The Clarity Protocol solves this by creating a `.clarity-protocol/` directory alongside your code that captures:

- **The problem** you're solving and who cares about it
- **The solution** you're building and why it's designed that way
- **The failures** that could happen and how you'll handle them
- **The decisions** you've made and when to reconsider them

Think of it as the "missing manual" for your code—the stuff you can't figure out just by reading the implementation.

## When to Use Clarity Processes

The clarity agent provides several processes that help at different stages of development. The **clarity-agent** process is the natural entry point — it assesses where the project stands and routes you to the right process.

### Not Sure What to Do Next?

**Run clarity-agent**: `.clarity-agent/processes/clarity-agent.md`

The clarity-agent process looks at the current state of the `.clarity-protocol/` directory and figures out what needs attention:

- No protocol directory? Creates the structure and routes to problem clarification.
- Problem vague or missing? Routes to problem clarification.
- Problem clear but no solution? Routes to solution brainstorming.
- Solution exists but no failure analysis? Routes to failure analysis.
- Everything solid? Reports status and asks what you'd like to work on.

You can also invoke any process directly when you know what's needed.

### Clarifying What You're Building

**Process**: `~/.clarity-agent/processes/problem-clarification.md`

This is typically the first substantive process to run. It transforms vague ideas into clear problem statements through probing conversation.

**Key strategies** (see process guide for details):

- **Handle fuzzy criteria**: When you hear "fast," "easy," "secure"—use outrageous examples to help users articulate what they really mean
- **Separate problems from solutions**: When users arrive with specific implementations, probe for the underlying need they're trying to address
- **Clarify scalable criteria**: For decision-making criteria that need to be applied consistently (by humans or AI), use the rigorous 6-step criteria clarification process
- **Detect "magic"**: Flag any step that assumes someone will "just know" what another intends without explicit communication

Updates: `goal/problem.md`, `goal/stakeholders.md`, `goal/requirements.md`

### Thinking Through What Could Go Wrong

**When starting a new feature or making significant changes:**

- Load and follow the **failure analysis process**: `~/.clarity-agent/processes/failure-analysis.md`
- This orchestrates multiple "thinker" agents that examine the system from different perspectives
- Each thinker is a specialized guide in `~/.clarity-agent/thinkers/`
- Update: `failures/` directory with identified failure modes

**When you hit an unexpected problem:**

- Check existing failures in `.clarity-protocol/failures/failures.md`
- See if this matches a known failure mode
- If it's new, run failure analysis to capture it

### Making Important Decisions

**When there are multiple ways forward:**

- Load and follow the **decision guidance process**: `~/.clarity-agent/processes/decision-guidance.md`
- Walk through criteria, options, and tradeoffs
- Record the decision and when to reconsider it
- Update: `decisions/` directory

### Designing the Solution

**When you need to translate a problem into an implementation plan:**

- Load and follow the **solution brainstorming process**: `~/.clarity-agent/processes/solution-brainstorming.md`
- Explore different approaches
- This naturally triggers failure analysis and architecture design as sub-processes
- Update: `solution/solution.md`, `solution/architecture.md`

## How to Integrate This

When a project uses the Clarity Protocol, it will have a `.clarity-protocol/config.json` that points to the clarity agent installation (typically `~/.clarity-agent/`).

### For Any Project

1. Load and run **clarity-agent** (`~/.clarity-agent/processes/clarity-agent.md`)
2. The clarity agent will:
   - Create the `.clarity-protocol/` directory if it doesn't exist
   - Assess the current state of existing protocol files
   - Recommend the most valuable next process to run
3. At natural points during development, suggest relevant processes:
   - New feature? "Let's think about what could go wrong with this feature."
   - Unexpected bug? "This might be a known failure mode. Let me check..."
   - Architecture decision? "This seems like an important decision. Should we document it?"
   - Not sure? Run clarity-agent again to reassess.

## Context Management

To manage context windows effectively:

**Always load** (small, essential files):

- `.clarity-protocol/config.json`
- `.clarity-protocol/goal/problem.md`
- `.clarity-protocol/solution/solution.md`

**Load on demand** (only when relevant):

- `.clarity-protocol/failures/failures.md` (index only, not full failure documents)
- `.clarity-protocol/decisions/decisions.md` (index only, not full decision documents)
- Specific process guides from `~/.clarity-agent/processes/` (only the one you're running)
- Individual failure or decision documents (only when working on that specific issue)

**Lazy loading pattern**: The failures.md and decisions.md files contain brief summaries. Only load the full `failure-XX-*.md` or `decision-XX-*.md` files when actually working on that failure or decision.

## Available Processes

All process guides are in `~/.clarity-agent/processes/`:

- `clarity-agent.md` - Assess project state and route to the right process (start here)
- `problem-clarification.md` - Refine problem statements and stakeholder understanding
- `solution-brainstorming.md` - Explore solution approaches
- `failure-analysis.md` - Systematic failure discovery (orchestrates thinkers)
- `failure-grouping.md` - Organize failures by causation chains
- `mitigation-planning.md` - Develop failure management strategies
- `architecture-design.md` - Create technical designs and implementation plans
- `decision-guidance.md` - Walk through important decisions
- `as-built-analysis.md` - Analyze existing code for failures and discrepancies

Each process guide is self-contained and follows a narrative format:

- What it achieves and why it matters
- When to use it
- Step-by-step walkthrough
- What files it updates
- Sub-processes it may invoke

## Available Thinkers

All thinkers are in `~/.clarity-agent/thinkers/`:

- `security-thinker.md` - Authentication, authorization, injection, data protection
- `scalability-thinker.md` - Load, traffic, data volume, geographic distribution
- `privacy-thinker.md` - Data exposure, consent, retention, third-party sharing
- `accessibility-thinker.md` - Visual, motor, cognitive, assistive technology
- `data-integrity-thinker.md` - Corruption, consistency, race conditions
- `user-experience-thinker.md` - Confusion, error recovery, workflow interruptions

The failure-analysis process selects which thinkers to run based on the system being built.

## Writing Style

When creating or updating clarity protocol documents, follow these principles:

1. **Start with synthesis** - Explain how this solves a problem or fits the bigger picture
2. **Focus on what and why** - Not just how, but what it accomplishes and why it matters
3. **Narrative flow** - Tell the story of how it works and what happens
4. **Implementation at the end** - Save technical details for later sections
5. **Process-oriented** - Emphasize what people do with this, not just what it contains

The goal is for anyone—human or AI, technical or non-technical—to quickly understand the essence, then dive deeper only as needed.

## Getting Started

1. Load and run `.clarity-agent/processes/clarity-agent.md`
2. The clarity agent will create the protocol if needed and recommend what to do next
3. Follow the recommended process, then run clarity-agent again to reassess
4. At natural points in development, suggest relevant processes or re-run clarity-agent

Remember: The clarity protocol isn't paperwork. It's a tool to help you and your AI collaborators build systems that actually work.
