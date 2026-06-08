# First 10 Minutes Experience — Draft Plan

**Assertion:** Clarity Agent needs to prove its value within 5 minutes, then deliver personal value within 10.

**Two phases of value:**
- **First 5 minutes (time to tool value):** The user sees that Clarity is *worth using* — it does something different from a chatbot.
- **Minutes 5–10 (time to personal value):** The user experiences an insight about *their own* project — a reframe, a missed stakeholder, a failure mode they hadn't considered. This is what makes them come back.

**Journey:** Discovery → Install → Setup & Tutorial → First Conversation → First Insight

Two transitions connect these phases:
- **Install → Tutorial** (the "getting started" transition): from "I have the app" to "I see what this does"
- **Tutorial → Own Project** (the "make it mine" transition): from "neat demo" to "this helps me think about *my* thing"

## The Ideal First 10 Minutes

```
Discovery (0:00)
  User lands on README (aka.ms/clarity-agent) or releases page (aka.ms/clarity-agent-bits)
  → One obvious action: "Download" (macOS/Win) or "curl | bash" (Linux)

Install (0:30)
  Install completes, app opens (or web UI launches)
  → If LLM already detectable: auto-configure, skip setup

                    ┌─────────────────────────────────────┐
                    │  "Getting Started" transition        │
                    │  (install → demonstrated tool value) │
                    └─────────────────────────────────────┘

Setup & Tutorial (1:00–5:00) — proves tool value
  → LLM setup (if needed): recommended provider pre-selected, 3 clicks
  → Guided tutorial: live exercise with a sample project (email assistant scenario)
  → User makes real judgments, sees Clarity push back, sees artifacts created
  → User understands: "This is different. This helps me think."
  → Tutorial ends with invitation to start their own project

                    ┌─────────────────────────────────────┐
                    │  "Make It Mine" transition           │
                    │  (tool value → personal value)       │
                    └─────────────────────────────────────┘

First Conversation (5:00–8:00) — engages the user's own project
  → User describes their own project (even roughly)
  → Agent adapts: listens, asks clarifying questions, looks for pushback opportunity
  → Conversation feels familiar because the tutorial taught the interaction pattern

First Insight (8:00–10:00) — delivers personal value
  Agent surfaces something the user hadn't considered about *their* project
  → User thinks: "Oh — I hadn't thought about that for *my* thing"
  → User is engaged. This is now their tool. Process continues naturally.
```

**The distinction matters because:**
- In the first 5 minutes, the user is evaluating the *tool*. "Is this worth my time?"
- After minute 5, the user is engaging with their *problem*. "This is helping me think."
- If we try to deliver personal insight before proving tool value, we're asking the user to invest context in something they don't yet trust.
- If we only prove tool value and never bridge to personal value, the user thinks "neat demo" and doesn't return.

Each phase has one job: get to the next phase with minimum friction and maximum clarity about what's happening.

---

## Discovery

### Design Principles

1. **One obvious default path.** The user shouldn't have to understand the modality difference before they've used the tool.
2. **The README is not a download page.** It should explain what Clarity is and link to install instructions, not host them inline (or if inline, with a clear single default).
3. **Platform detection, not user detection.** The install method adapts to the OS, not to a persona the user self-selects into.
4. **CLI is discovered, not chosen upfront.** Power-user paths (embed, headless server) appear after first use, not before.

### Gap Analysis

**Current state:** Clarity's README presents two parallel install options (desktop app vs. CLI script) with roughly equal weight. This forces a choice at a moment when the user has the least context to make it.

**User Impact: High (7/10).** Every single new user encounters this. A confused user at this stage doesn't bounce from one option to the other — they bounce from the project entirely. However, developers (our primary current audience) are somewhat accustomed to choosing between install methods, which limits the severity. The real damage is to non-developer users (PMs, founders, strategists) who see two technical-looking options and feel "this isn't for me."

**Gaps against the ideal flow (0:00 → 0:30):**
- The ideal says "one obvious action." The current README presents two equal-weight blocks — neither is marked as default or recommended.
- The ideal says install completes at 0:30. The CLI path takes 15-20 minutes, making the 5-minute target impossible for that cohort.
- Non-developers who would benefit most from Clarity are most likely to bounce at this step because both options look technical.

**Proposed resolution:** Desktop app is the primary install for macOS and Windows. It bundles the Python server, needs no prerequisites, and includes all functionality. Linux and headless environments get the script installer. The README leads with one thing, not two parallel blocks.

### Supporting Research: How Local-First Tools Handle This

| Tool | Strategy | How CLI relates to GUI |
|------|----------|----------------------|
| **Ollama** | CLI command is the hero; ".dmg" is secondary fallback | Same install produces both; no choice needed |
| **LM Studio** | App is the product; CLI ships inside it | `lms` available after app install; `npx lmstudio install-cli` if PATH is wrong |
| **Docker Desktop** | One installer bundles everything (macOS/Win) | CLI included; Linux gets CLI-only path separately |
| **VS Code** | Download page auto-detects platform; one big button | `code` CLI installed from within the app |
| **Ghostty** | README describes the project; links to separate download page | No CLI vs GUI distinction — it's one app |
| **Claude Code** | One `curl` command; no GUI exists | N/A — pure CLI |

**Key finding:** Successful local tools either (a) bundle both modalities in one install, or (b) pick one as primary and let the other be discovered later. None present parallel equal-weight choices.

### Open Questions

- Should the desktop app offer "Install CLI" from a menu (VS Code model)?
- Should `curl | bash` on macOS install the app, the CLI, or both?
- How do we handle the coding-agent-only user who wants `clarity embed` without the app?

---

## Install

### Design Principles

- Install should take < 3 minutes on a fast connection
- Zero decisions during install (decisions happen in setup, not install)
- If something fails, the error message should say what to do, not just what went wrong
- Progress should be visible ("downloading…", "configuring…", "ready!")

### Gap Analysis

**Gaps against the ideal flow (0:00 → 0:30):**

The ideal says install completes and the app opens within 30 seconds. Here's where each path falls short:

**Silent sidecar failure (Desktop)**
- **User Impact: Critical (9/10).** User sees a blank/loading screen with no error and no recourse. They conclude the app is broken and uninstall. This is a complete loss — the user did everything right and got nothing. The only recovery path (checking `~/.clarity/clarity-startup.log`) is invisible to anyone who isn't a developer debugging their own software.
- **Gap:** Violates "progress should be visible" and "error messages should say what to do." The app has no startup health check that surfaces failure to the user.

**15-20 minute CLI install time**
- **User Impact: High (8/10).** A "try it" user won't wait 15 minutes for dependencies to install. This is acceptable for developers committing to a tool they've already decided to adopt, but devastating for curious first-timers.
- **Gap:** Violates "< 3 minutes." The root cause is architectural: the CLI install clones a repo and builds from source (Python venv + npm) rather than shipping a pre-built artifact.

**Prerequisite assumptions (git, Python 3.12, Node 22)**
- **User Impact: High (7/10).** Each missing prerequisite is a blocking error with a cryptic message. The user must leave Clarity's install flow, figure out how to install Python/Node/git for their platform, then return and retry. Each round-trip risks abandonment. Developers usually have these; non-developers almost never do.
- **Gap:** Violates "zero decisions during install" and "say what to do, not just what went wrong." Prerequisite checks happen late (after download starts) and error messages are generic.

**Embed breaks without system install**
- **User Impact: Medium (5/10).** Only affects users who try `clarity embed` before installing Clarity globally — a sequencing error. The error message ("Clarity is not installed on this machine") is at least clear, but doesn't tell them *how* to fix it.
- **Gap:** Minor — this is a power-user path with a clear (if unhelpful) error. Lower priority because the embed path is typically reached by users who already have Clarity working.

### Supporting Research

- **Ollama** installs in ~30 seconds by shipping a pre-built binary. No git, no Python, no Node. The install script downloads one binary and places it on PATH.
- **Docker Desktop** installs in ~2 minutes via a standard macOS/Windows installer. The `.dmg` drag-to-Applications flow is familiar and requires no terminal.
- **VS Code** installs in ~1 minute. The `.dmg` includes everything; no build step, no dependencies.
- **Claude Code** installs in ~10 seconds via `curl | bash` — downloads a single binary, adds to PATH, done.

The pattern: tools that install fast ship **pre-built artifacts**, not source + build instructions. The CLI path's 15-20 minutes is a consequence of building from source (Python venv creation, pip install, npm install, npm run build).

### Proposed Improvements

- **Desktop:** Add a visible startup progress indicator. If sidecar fails, show an error dialog with "Run `clarity doctor`" suggestion rather than hanging.
- **CLI script:** Check prerequisites (git, Python) *before* downloading anything. Print clear remediation: "Python 3.12+ required. Install with: brew install python@3.12" (platform-appropriate).
- **CLI script speed:** Explore shipping a pre-built binary (like Ollama does) instead of cloning repo + building. The 15-minute install is a dealbreaker for a "try it" experience.

---

## Setup & Tutorial

*The "getting started" transition: from "I have the app" to "I see what this does."*

This phase covers everything between install completing and the user understanding Clarity's value. It includes LLM configuration and the guided tutorial as a single flow. The goal: by the end, the user has seen Clarity push back, create artifacts, and track changes — and is ready to try it on their own project.

### Design Principles

1. **Setup is a step in the flow, not a separate phase.** LLM configuration should feel like getting ready to talk, not like configuring enterprise software.
2. **Teach how to hold it right — by doing.** Users bring ChatGPT habits. The tutorial demonstrates the real interaction pattern (pushback, artifact creation, staleness) rather than explaining it.
3. **Recommend, don't just list.** For LLM setup, surface a default based on what's already available on the system.
4. **Every path leads to the tutorial.** Whether setup is auto-detected, manually configured, or skipped — the next thing is the tutorial.
5. **Skipping should be safe.** Users who skip setup get re-prompted gracefully. Users who skip the tutorial get a compact orientation and go straight to their own project.

### Gap Analysis

**Gaps against the ideal flow (0:30 → 5:00):**

The ideal says: "Setup if needed, then tutorial proves tool value." The current experience has three disconnected pieces (setup wizard, blank chat, process guide start) with no coherent path from install to demonstrated value.

**LLM setup is a disconnected gate**
- **User Impact: High (8/10).** The setup wizard currently blocks all progress. 5 providers × multiple auth modes with no guidance. Users who don't have a preferred provider are paralyzed.
- **Gap:** Setup has no orientation context ("why do I need this?") and no recommendation logic. It feels like enterprise configuration, not getting ready to think.

**No orientation — user doesn't know how to engage**
- **User Impact: High (7/10).** Clarity's value depends on the user engaging honestly and pushing back when the agent is wrong. But nothing teaches this. Users bring their ChatGPT habits.
- **Gap:** There is no designed moment that teaches what Clarity is and how it differs from other AI tools. The tutorial solves this — but it doesn't exist yet.

**No path for exploratory or evaluating users**
- **User Impact: High (7/10).** Users who installed to *evaluate* have no structured way to experience value before committing a real project.
- **Gap:** The opening assumes the user arrives with a project. The tutorial solves this by providing a sample scenario.

**CLI has no interactive login — forces PAT flow**
- **User Impact: Medium (4/10).** The web/desktop UI handles the unconfigured state gracefully (shows setup wizard). The CLI prints a clear error with env var suggestions but exits with code 1 and a "crash log" message — intimidating but not a real crash. The actual gap: the CLI error only suggests PAT-style flows (paste an API key) and doesn't mention `clarity web` or offer interactive browser login the way the installer and setup wizard do.
- **Gap:** CLI has no interactive login recovery at runtime. Filed as [#100](https://github.com/microsoft/clarity-agent/issues/100).

### The "How to Hold It Right" Problem

Clarity is a new kind of tool. Users' prior mental models (chatbot, search engine, document generator) all lead to wrong expectations. The tutorial teaches by doing — the user doesn't read these principles, they experience them:

- Clarity is a thinking partner that pushes back, not an assistant that does what you say
- The goal is the user's clarity about their project, not a document
- The user supplies goals, context, and judgment; Clarity structures reasoning and introduces missing perspectives
- Important reasoning becomes inspectable project artifacts, not chat history
- Requirements and solutions are different things
- Changed premises can make earlier conclusions stale

### The Guided Tutorial (First Five Minutes Process)

The bridge moment's primary mechanism is a live, guided exercise using a sample project. This is not a product tour or a canned replay — it's a real Clarity conversation with guardrails that ensure the learning arc completes.

**Why a tutorial before the user's own project:**
- The user doesn't yet trust the tool enough to invest their real context
- A sample project creates a safe space to experience pushback without feeling interrogated
- Predictable scenario ensures the learning arc completes regardless of what the user brings
- Teaches the interaction pattern before the user needs it for real
- Proves tool value *before* asking for personal investment

**The scenario:** A company building an AI assistant that reads employee email and drafts replies. The team is considering allowing the assistant to send messages automatically.

This scenario works because it's: (a) understandable without specialist knowledge, (b) rich enough for genuine design decisions, (c) ambiguous enough that the user must make real judgments, and (d) raises authority/control/failure questions naturally. Do not present the full scenario at the start — reveal details only as needed.

**Learning arc (6 phases, ~5 minutes):**

| Phase | What happens | What the user learns |
|-------|-------------|---------------------|
| **Frame** | Present the scenario. Ask what decision the team needs to make. | Clarity starts with *what problem are we solving*, not *what should we build* |
| **Expand** | Ask who bears the consequence. Add a stakeholder the user missed. | Clarity broadens the system boundary — introduces perspectives you didn't have |
| **Distinguish** | Surface a proposal (e.g., "require approval"). Ask: is this the requirement or one solution? | Requirements state what must be true; solutions are one way to achieve it |
| **Challenge** | Find a specific failure mode (e.g., stale authorization — user approves, then state changes before send). Express as causal chain. | Clarity surfaces non-obvious failures specific to *this* system, not generic risks |
| **Record** | Show what now exists as protocol artifacts. | Important reasoning becomes inspectable, durable project documents |
| **Reassess** | Introduce a changed premise. Ask what it invalidates. | Changed assumptions affect downstream reasoning. Clarity tracks this. |

**Experience contract — the tutorial must:**
- Use real protocol machinery (actual files, actual packet status)
- Ask the user to make at least two genuine judgments
- Adapt to the substance of the user's answers
- Add at least one perspective the user did not provide
- Distinguish a requirement from a proposed solution
- Surface one non-obvious failure mode with a short causal chain
- Create concise, visible protocol artifacts as it proceeds
- Demonstrate that changing a premise affects downstream reasoning
- End with a clear invitation to begin the user's real project

**The tutorial must NOT:**
- Become a lecture about Clarity
- Present a feature list or terminology
- Require knowledge of Clarity jargon
- Pretend there's one correct answer
- Generate a large or exhaustive design packet
- Overwhelm with many thinkers or failure modes
- Continue refining the hypothetical after learning goals are met

**Interaction style:** Warm, direct, slightly more instructional than a normal Clarity session. Keep explanations brief and tied to something that just happened. Don't praise every answer — respond to substance. Move through obvious steps naturally; pause only for judgments that should genuinely come from the user.

**Completion:** Summarize the pattern in one sentence:

> You framed the problem. Clarity expanded the boundary, separated requirements from solutions, challenged an assumption, and preserved the result. When a premise changed, the affected reasoning needed another look.

Then offer three paths:
1. Start a real project (recommended)
2. Explore the tutorial documents
3. Continue experimenting with the sample

**Recovery paths:**
- User wants their own problem instead → transition to normal Clarity, retain orientation
- User skips tutorial → compact explanation + start with their real project
- User gets deeply engaged in hypothetical → conclude when learning goals are met, offer continued exploration separately
- User can invoke the tutorial later from help menu

**Adaptation guidance:** No two sessions need identical questions, stakeholders, or failure modes. Follow the user's terminology. Ask about the most consequential ambiguity they reveal. Prefer one deep failure over several shallow ones. Move quickly when the user already understands a concept. Maintain the stable arc: Frame → Expand → Distinguish → Challenge → Record → Reassess.

### LLM Setup (Embedded in Bridge)

Setup becomes a step within the bridge rather than a separate blocking phase:

**Auto-detect first.** Before showing anything, check:
- Is `ANTHROPIC_API_KEY` set? → Pre-select Anthropic, pre-fill, go straight to "Test & Save"
- Is `claude` CLI logged in? → Pre-select Claude SDK, test it, auto-configure
- Is `gh` CLI authenticated? → Pre-select GitHub Copilot
- If anything detected → skip straight to orientation/walkthrough

**If nothing detected, one screen within the bridge:**
> "To get started, Clarity needs an AI provider. We recommend Claude for the best experience. [Use Claude →] [Other providers]"

Credentials → Test → Done. One screen, not five steps. Then flow continues into orientation.

**If skipped:** Bridge continues without LLM. Show orientation and walkthrough in "preview" mode. When user tries to start a real conversation, re-prompt for setup. Never crash.

### Supporting Research

- **Ollama** after install just says what to do next in one line. No separate orientation.
- **Obsidian** explains one concept (vault = folder) before starting. Minimal but sufficient.
- **LM Studio** shows a model browser — gives you something to *do* immediately.
- **VS Code** shows a "Get Started" tab with structured next steps on first open.
- **Duolingo** (tutorial reference): teaches by doing, not explaining. First lesson starts immediately with a guided exercise; you learn the mechanics by using them.
- **Figma** shows a brief interactive tutorial on first use that demonstrates the tool's unique interaction model (vector editing), not generic features.

**Pattern:** Good first-run experiences either (a) tell you exactly what to do next, (b) give you structured options rather than a blank canvas, or (c) teach by doing rather than explaining. The best ones combine (b) and (c) — structured options that lead to a guided experience.

### Open Questions

- What's the right default LLM recommendation? (Claude is best quality; GitHub Copilot is most likely "already have it" for developers)
- Should the app work in a limited mode without an LLM? (browse protocol, view docs, but can't converse)
- What sample project resonates with the broadest audience? (Needs to be interesting enough to demonstrate real pushback but simple enough to follow in 60 seconds)
- Should the walkthrough be a real LLM conversation (variable quality, costs money) or a scripted replay (predictable, free, but feels canned)?
- How do we handle the user who skips the walkthrough but then doesn't know how to engage? (Inline hints? Contextual guidance during first real conversation?)
- Should the bridge moment differ by modality? (Desktop/web users may want visual orientation; CLI users may prefer to just start; embedded users have a coding agent as intermediary)

---

## First Conversation

*The "make it mine" transition: from demonstrated tool value to personal value.*

The tutorial proved Clarity is worth using. Now the user needs to experience it on something *they* care about. This is the transition from "neat demo" to "my tool."

### Design Principles

1. **The transition should feel natural.** The tutorial ends with "Ready to start your own project?" — the user already knows the interaction pattern. Don't re-explain.
2. **The opening question should be answerable by everyone.** "What are you working on?" works for most. For users who skip the tutorial, accommodate exploration attitudes too.
3. **Adapt to what arrives.** The agent's first response should be shaped by what the user actually says, not by a fixed script.
4. **Lower the bar for entry.** After the tutorial, the user knows what Clarity does with a well-formed scenario. But their own project might be vague, messy, or half-formed. That's fine — say so explicitly.
5. **CLI goes straight to conversation on first run.** The command menu is for returning users.

### Gap Analysis

**Gaps against the ideal flow (5:00 → 8:00):**

The ideal says: "User describes their own project. Agent adapts, listens, looks for pushback opportunity. Conversation feels familiar because the tutorial taught the pattern."

**Abrupt transition from tutorial to real work**
- **User Impact: Medium (6/10).** If the tutorial workspace and the real workspace feel disconnected (different project, different context, starting over), the user loses momentum.
- **Gap:** Need a smooth handoff: tutorial artifacts stay accessible but the new project starts clean. The user shouldn't feel like they're "rebooting."

**User's own project may be too vague for immediate insight**
- **User Impact: Medium (6/10).** The tutorial used a rich scenario. The user's first description of their own project might be "I'm thinking about building an app for X." That's thin. The agent needs to draw out enough context to push back meaningfully.
- **Gap:** Process guides say "ask follow-up questions" but don't emphasize that the first few exchanges of a *real* project need to build enough context for a specific challenge — not just gather information for its own sake.

**No designed handling for common post-tutorial responses**
- **User Impact: Medium (5/10).** After the tutorial, some users will say "let me think about what to bring here" or "I'll come back with something." That's fine — but there should be a graceful exit that invites return, not an awkward silence.

### Proposed Model

| User does after tutorial | Agent response |
|--------------------------|---------------|
| Describes their project | Begin normal problem clarification — carry the tutorial's energy and directness |
| Asks a follow-up about the tutorial | Answer briefly, then redirect: "Want to try that with your own project?" |
| Says "let me think" or "I'll come back" | "Take your time. When you're ready, just tell me what you're working on — even a rough idea. I'll be here." |
| Brings something very vague | Draw out specifics with concrete questions: "Who's this for? What happens if it doesn't exist?" — build enough context for a real challenge |

### Open Questions

- Should the tutorial project and real project be in the same workspace or separate?
- How much of the tutorial's instructional tone should carry into the real conversation? (Probably: none. The real conversation should feel like a peer, not a teacher.)
- Should the first real conversation explicitly reference the tutorial patterns? ("Remember how we separated requirements from solutions? Let's do that here too.") Or is that patronizing?

---

## First Insight

*Minutes 8–10: Personal value delivered. The user is now engaged with their own problem.*

### Design Principles

1. **First personal insight within 3 exchanges of real conversation.** The agent must surface something genuinely new to the user about *their* project — not the tutorial scenario.
2. **Specific beats generic.** "Have you thought about edge cases?" is worthless. "What happens when two people edit the same paragraph simultaneously?" is valuable. The insight must be *about this project*, not about projects in general.
3. **Challenge, don't lecture.** The insight should arrive as a question or observation. The user should feel "oh, good point" not "this thing is patronizing me."
4. **The insight should be visible in the output.** Whatever the agent surfaces should appear in a protocol document — reinforcing the tutorial's lesson that conversation produces durable artifacts.
5. **This is the retention moment.** The tutorial proved the tool is interesting. This moment proves it's useful *for them*. Without it, the user thinks "neat demo" and doesn't return.

### Gap Analysis

**User Impact: Critical (10/10).** This is what determines whether the user comes back. The tutorial bought trust and taught the pattern, but trust in a demo doesn't transfer automatically to trust in real use. The user needs to think "this helped me see something about *my* problem that I wouldn't have seen alone."

**Gaps against the ideal flow (8:00 → 10:00):**

- The user's first description of their project will be less developed than the tutorial scenario. The agent must work harder to find something specific to challenge.
- The tutorial's instructional scaffolding is gone. The agent must deliver insight through pure conversational quality — no guardrails ensuring the learning arc completes.
- Process guides say to surface challenges early but don't guarantee it within 3 exchanges of a new project. Thin user input + average model performance = risk of generic follow-ups.
- There's a new failure mode: the user compares the real conversation unfavorably to the tutorial ("the demo was better than this"). The tutorial sets a quality bar the real conversation must meet.

### What "First Personal Insight" Looks Like

- Reframing: "You said you want to build X — but it sounds like the real goal is Y. Is that right?"
- A missed stakeholder: "Who maintains this after launch? That person has different needs than the builder."
- A failure mode: "What happens when [specific scenario based on what the user said]?"
- A specificity push: "You said 'fast' — what does fast mean here? 100ms? 5 seconds? Different answers lead to different architectures."
- A scope question: "You described the full vision. What's the smallest version that would still be worth building?"

### Proposed Constraint on Process Guides

The opening of `processes/clarity-agent.md` Step 2 should be structured to surface a challenge within the first 2-3 exchanges of a real project. Concretely:

- The agent's first substantive response should include at least one question that reveals a gap, assumption, or unconsidered angle.
- If the user's description is too thin to challenge, draw out detail with *specific* questions (not "tell me more" — rather "who uses this and what happens if they can't?").
- The questions should build toward a challenge, not just gather information. Every question should make the user think slightly harder.

### Supporting Research

Clarity's own failure analysis (FM01: User Disengagement) identifies this as the existential risk and calls "time to first insight" the critical metric. The notes.md captures it as: "Value demonstration is the master intervention." The solution doc establishes it as a design constraint on Layer 2.

The tutorial changes the dynamic: by minute 8, the user already knows Clarity can deliver insight (they experienced it in the tutorial). The bar is now: "can it do that for *my* thing?" This is a lower bar than cold-start first insight — the user is primed to engage and knows how to hold the tool. But it's also a higher quality bar — the user has a reference point for what good looks like.

### Open Questions

- Can we measure time-to-first-personal-insight? (Proxy: user response length increases; user asks a follow-up rather than answering minimally)
- Should the agent explicitly connect back to tutorial patterns? ("Like the email assistant — let's check if there's a similar authority question here")
- How do we avoid the failure mode where the real conversation feels less impressive than the tutorial? (Tutorial has a curated scenario; real projects are messy.)
- What if the user's project genuinely doesn't have an interesting angle to push on in 3 exchanges? (Fallback: "Here's what I'm noticing is underspecified..." rather than forcing a dramatic reframe)
