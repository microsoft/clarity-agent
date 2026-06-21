# Clarity Agent

An AI thinking partner that pushes back.

Most AI tools help you execute faster. Clarity helps you figure out whether you're building the right thing in the first place by asking the questions that experienced architects, product managers, and safety engineers would ask. The answers are written down as human-readable documents you can review, share with your team, or export as Word docs for stakeholders; they also are available to agents so the work you do with Clarity outlasts any single conversation.

```
You:      I want to build a real-time collaboration feature for our doc editor.

Clarity:  Before we design that — what happens when two people edit the same
          paragraph at the same time? Do you need true real-time (cursors, presence),
          or is "no one loses work" the actual requirement? Those lead to very
          different architectures.
```

Clarity runs as a desktop app, a web UI, or embedded in your coding agent. It produces a `.clarity-protocol/` directory in your repo which contains human-readable markdown files capturing your problem, solution, failure analysis, and decisions.  The clarity protocol stays current as your project evolves and is managed like source code.

Read more about the philosophy behind clarity agent [in this blog post](https://medium.com/@yonatanzunger/are-we-building-the-right-ai-203cfc7effdc).

You can also join the [Clarity Agent Discord](https://aka.ms/clarity-agent-community) to talk with the team, share feedback, and connect with the community.

## Getting Started

### Install

**Download the desktop app** (no terminal required):

Download the latest `.dmg` (macOS) or `.exe` installer (Windows) from the [GitHub Releases page](https://github.com/microsoft/clarity-agent/releases/latest) and install it directly. No prerequisites.

**Or install via script** (adds the `clarity` CLI and embeds Clarity into git repos):

*macOS / Linux:*

```bash
curl -fsSL https://raw.githubusercontent.com/microsoft/clarity-agent/main/scripts/install.sh | bash
```

*Windows (PowerShell):*

```powershell
irm https://raw.githubusercontent.com/microsoft/clarity-agent/main/scripts/install.ps1 | iex
```

The installer downloads everything it needs — no prerequisites beyond `git`.

**Or clone and install manually:**

```bash
git clone https://github.com/microsoft/clarity-agent.git
cd clarity-agent
bash scripts/install.sh        # macOS / Linux
.\scripts\install.ps1          # Windows
```

### Launch and connect an LLM

**macOS:** Open `Clarity.app` from `~/Applications`.

**Windows:** Run the installed app from the Start Menu, or run `clarity` from your terminal if you used the script installer.

**Linux:** Run `clarity` from your terminal.

On first launch, the setup wizard walks you through connecting an LLM provider.

**Supported providers:**

| Provider | Authentication options |
| --- | --- |
| **Anthropic (Claude)** | Claude Code login (`claude login`) · API key from [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| **OpenAI (GPT)** | API key from [platform.openai.com](https://platform.openai.com/api-keys) |
| **Azure AI** | Microsoft sign-in · Azure CLI (`az login`) · API key |
| **GitHub Copilot** | GitHub Copilot CLI (`copilot auth login`) · GitHub CLI (`gh auth login`) · personal access token |
| **Google Gemini** | API key from [Google AI Studio](https://aistudio.google.com/apikey) |

Clarity works best with frontier models — structured thinking is where model quality matters most. The setup wizard tests your credentials before saving them. Run `clarity doctor` at any time to re-check the configuration.

### Start a session

The app opens the project picker. Create a new project or open an existing folder. Clarity will ask what you're working on and guide you through structured thinking about your problem, solution, and failure modes. Everything is saved to a `.clarity-protocol/` directory — no codebase required.

### Use it

**For any kind of project** — Open the app, create a project, and start talking. Clarity will ask what you're working on and guide you from there. No codebase required.

**For a coding project** — embed Clarity into your repo so your coding agent picks it up:

```bash
clarity embed /path/to/your-project
```

This adds an `AGENTS.md` snippet and a `.clarity-protocol/` directory. These are plain files managed just like any other file in your repo — committed, reviewed in PRs, and diffed. From then on, your coding agent (Claude Code, Cursor, etc.) follows the process guides as part of its normal workflow.

## What It Does

Clarity guides you through structured conversations, writing the results to the clarity protocol as it goes:

**Problem clarification** — "What problem are you solving? Who are the stakeholders? What does success look like?" Pushes you past vague intentions into testable criteria.

**Solution exploration** — "Given that problem, how might we solve it?" Explores approaches, surfaces tradeoffs, and checks that the solution actually addresses the problem.

**Failure analysis** — Multiple AI "thinkers" independently examine your system from different angles (security, human factors, adversarial, operational), then you work through the results together: grouping related failures, tracing causal chains, building management plans.

**Decision tracking** — Important choices get captured with criteria, options, and rationale. When upstream documents change, the agent knows which decisions might need revisiting.

**Staleness tracking** — Documents form a dependency graph. When your problem statement changes, Clarity knows your solution description might be stale and nudges you to revisit it.

## What Comes Out

A `.clarity-protocol/` directory:

```text
.clarity-protocol/
├── summary.md              # Brief summary of what this project is
├── notes.md                # Principles and cross-cutting observations
├── observations.md         # Patterns and coverage notes from analysis
├── goal/
│   ├── problem.md          # What you're trying to achieve and why
│   ├── stakeholders.md     # Who cares about the outcome
│   ├── requirements.md     # Criteria any solution must satisfy
│   ├── open-questions.md   # Unknowns that could change the approach
│   └── resolved-questions.md # Questions answered, with findings
├── solution/
│   ├── solution.md         # What you plan to build
│   ├── architecture.md     # How you plan to build it
│   └── solution-summary.md # Concise overview for stakeholders
├── failures/
│   └── failures.md         # Failure modes, chains, and management plans
├── decisions/
│   └── decisions.md        # Decision log with criteria and reasoning
└── config.json             # Dependency graph and content hashes
```

Human-readable markdown, version-controllable, diffable. Edit the files directly, review them in PRs, or share them with collaborators who weren't part of the conversation. Generate **review packets** (Markdown or Word) for stakeholder review.

## How It Fits Your Work

- **Thinking through a problem?** Open the app and start talking. Works for software, strategy, research, product decisions — anything complex enough to benefit from structured thinking.
- **Starting a software project?** Use Clarity before writing code. By the time you start building, you'll have a clear problem statement, a considered solution, and an initial failure analysis.
- **Existing codebase?** Run `clarity embed` on any git repo. Point the agent at your code and it helps you articulate what's already there, fill in missing context, and keep the protocol current.
- **Team?** The `.clarity-protocol/` directory lives in your repo. Everyone sees the current state; the agent tracks what's gone stale when things change.
- **Before a review?** Generate a review packet to give stakeholders a coherent narrative instead of asking them to read raw notes.

## A Note on AI Limitations

Clarity is an AI-powered tool, and AI has real limitations.  AI-generated content may be incorrect or incomplete. Clarity agent is designed for dialogue - you should push back on ideas that don't seem right, just as it will push back on yours. Quality depends on using a capable model (frontier models make a real difference here) and engaging honestly with the questions it asks.

Do not rely on AI for consequential decisions about health, finance, or the law. Use Clarity as a place to think, not as a substitute for human expertise.

See [Responsible AI FAQ](AIFAQ.md) for detailed information about intended uses, limitations, and responsible use.

## CLI Reference

```text
clarity                            Launch web UI (default)
clarity web [project_dir]          Headless web server
clarity app                        Launch desktop app
clarity cli [project_dir]          Interactive terminal session
clarity process NAME [project_dir] Run a single process by name
clarity packet [project_dir]       Generate a review packet
clarity embed <project_dir>        Wire Clarity into a git repo
clarity install [--mode MODE]      Install as a desktop app
clarity update                     Update to the latest version
clarity doctor                     Diagnose the installation
clarity help                       Show help
```

## Principles

Clarity was designed with the following principles in mind.

**The hard work is understanding what you actually want.** The most valuable thing Clarity does isn't writing documents, it's asking you the right questions. The documents are a side effect.

**Files over memory.** Everything is written to disk as human-readable markdown. Nothing lives only in a chat transcript or an LLM's context window.

**Many perspectives find more failures.** The thinker architecture runs independent analyses from different angles, then synthesizes the results. This mirrors how safety engineering works in practice.

**Clarity is iterative.** Start rough, refine as you learn. The dependency tracker knows when something needs revisiting.

**Tool-agnostic core.** Process guides are plain markdown that any LLM can follow. Swapping tools doesn't mean starting over.


## Contributing

Contributions are welcome, especially:

- New thinkers for additional failure domains (scalability, privacy, accessibility, data integrity)
- Adapters for other AI development tools
- Example projects demonstrating different use cases
- Improvements to process guides based on real-world usage

See [CONTRIBUTING.md](CONTRIBUTING.md) for details about the architecture, development setup, and how to contribute.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow Microsoft's Trademark & Brand Guidelines. Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.
