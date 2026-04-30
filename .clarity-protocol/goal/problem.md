# Problem Statement

The hardest part of building anything is figuring out what you actually want. You can't know at the start; clarity emerges iteratively, through making a bit, looking at it, and asking "is this what I meant?" This is true whether you're designing a system, starting a business, or planning any complex endeavor. It is inherently a thinking problem, not an execution problem.

Three things make this problem persistently hard:

**Clarity requires iteration, but most processes assume you already have it.** You're expected to write requirements before you fully understand the problem, to commit to architectures before you've explored the space, to estimate effort before you know what you're building. The gap between "I have an idea" and "I know what I actually want" is where most projects silently go wrong — and it's a gap that can only be closed through disciplined, structured thinking.

**Thinking about failure is a skill most people don't have, and can't do well alone.** The central insight of safety engineering is simple: know what can go wrong, and for each of those things, have a plan. But generating a thorough list of what can go wrong requires simultaneously adopting adversarial, operational, and human-factors perspectives — which is a learned discipline, not a natural instinct. Even experts benefit enormously from having others to think it through with.

**Shared understanding is much harder than people think.** In teams, people routinely *believe* they agree about what they're building and why, but actually don't. The misalignment stays hidden until implementation exposes it — by which point significant work has gone in the wrong direction. And even solo builders face a version of this: you-in-six-months is effectively a different person, and if the reasoning behind your decisions isn't preserved, you'll revisit them from scratch. Written artifacts in the right structure can surface disagreements early and keep context alive across time and people.

These problems have always existed. The people who are good at helping with them — experienced facilitators, senior engineers, safety analysts — have developed powerful techniques over decades. But this expertise is scarce. Most people building things never get access to a thinking partner who will challenge their ideas, walk them through failure analysis, or help them articulate what they actually mean.

## Why This Matters Now

LLMs have become the default thinking partner for a huge and growing number of people. When someone has an idea, they increasingly bring it to an AI to help figure it out — and often to do much of the work. This creates an unprecedented opportunity to democratize the kind of structured thinking support that has historically required rare expertise.

But right now, most AI interactions actually make the underlying problems *worse*. Current tools are far too agreeable: they validate ideas, amplify momentum, and help users execute on plans that haven't been examined. They say "great idea!" and start building, rather than asking "have you thought about what happens when this fails?" or "what problem are you actually trying to solve?" Most insidiously, they create the *illusion* of having thought things through, because confident-sounding output feels like rigor.

The opportunity is to build AI that helps people *think better*, not just execute faster — a thinking partner that knows how to push back, surface hidden assumptions, and guide someone through the kind of structured analysis they'd never do alone. And then to preserve that thinking in a form that serves future collaborators, future selves, and (in software projects) the coding agents that will do much of the implementation.

## Scope

The underlying principles — clarifying goals, examining failure modes, documenting decisions — apply far beyond software. They're relevant to anyone building anything complex. But this project focuses on software engineering, where the authors' expertise is deepest and where the resulting artifacts have dual value: they serve as a reference for humans *and* as direct input for AI coding agents.

The architecture is designed to be extensible to other domains — new process guides and thinker perspectives can be added without changing the framework — but the shipped implementation is tuned for software projects.

**In scope:**
- Problem clarification and requirements articulation
- Failure mode brainstorming, analysis, and management planning
- Decision documentation and reconsideration tracking
- Technical architecture planning
- Document staleness tracking across the dependency graph
- Integration with AI coding agents via structured protocol documents

**Out of scope:**
- Implementation and code generation
- Project management and task tracking
- Deployment pipelines and operations
- Post-launch monitoring and incident response

## Success Criteria

- A user working with the clarity agent develops genuinely sharper thinking about their project — not just documentation, but actual clarity about what they're building, what could go wrong, and why they're making the choices they're making.
- The agent challenges assumptions, asks hard questions, and surfaces failure modes the user would not have identified alone — rather than simply agreeing and executing.
- The process produces persistent, structured artifacts (the clarity protocol) that a new collaborator, a coding agent, or the user's future self can read and immediately understand the project's rationale, rejected alternatives, and active risks.
- When something changes (requirements shift, a decision is revisited, a failure mode is resolved), the system knows what else needs revisiting and guides the user there.
- A team using the clarity protocol discovers misalignments in their shared understanding early — before those misalignments become expensive implementation mistakes.
- The framework is usable by a solo developer in under 15 minutes for a well-understood project, without requiring team ceremony.
