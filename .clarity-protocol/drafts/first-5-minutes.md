# First 5 Minutes Experience — Draft Plan

**Assertion:** Clarity Agent needs to show value (in the form of a helpful insight) in the first 5 minutes of use.

**Required steps to do that:** Discovery → Install → Bridge Moment → First Conversation → First Insight

## The Ideal First 5 Minutes

```
Discovery (0:00)
  User lands on README (aka.ms/clarity-agent) or releases page (aka.ms/clarity-agent-bits)
  → One obvious action: "Download" (macOS/Win) or "curl | bash" (Linux)

Install (0:30)
  Install completes, app opens (or web UI launches)
  → If LLM already detectable: auto-configure, skip setup step in bridge

Bridge Moment (1:00)
  → LLM setup (if needed): recommended provider pre-selected, 3 clicks
  → Orientation: what Clarity is, what to expect, how to hold it right
  → Optional: guided walkthrough with a sample project
  → Transition to conversation

First Conversation (3:00)
  User describes their project (even roughly)
  → Agent listens, asks clarifying questions, looks for first pushback opportunity

First Insight (4:00)
  Agent responds with first substantive challenge or reframe
  → User thinks: "Oh, I hadn't considered that"
  → User is engaged. Process continues naturally.
```

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

## Bridge Moment

The bridge moment is everything between "install completes" and "user is in a real conversation." It consolidates LLM setup, orientation, and the transition to first use into a single designed experience. The goal: the user arrives at their first real exchange understanding what Clarity is, how to use it well, and ready to engage.

### Design Principles

1. **Setup is part of the bridge, not a separate phase.** LLM configuration should feel like getting ready to talk, not like configuring enterprise software. Embed it in the flow rather than treating it as a gate.
2. **Teach how to hold it right.** Clarity is unlike other AI tools — it pushes back, it asks hard questions, it's not trying to please you. Users who don't understand this will either fight it or dismiss it. The bridge is where you set that expectation.
3. **Show, don't tell.** A brief walkthrough with a sample project teaches more than any amount of explanatory text. Users learn "how this works" by seeing it work, not by reading about it.
4. **Recommend, don't just list.** For LLM setup, surface a default based on what's already available on the system. Don't present a 5×N matrix of choices.
5. **Every path leads to conversation.** Whether the user goes through setup, skips it, takes the walkthrough, or dismisses everything — they should end up in a conversation within 2 minutes.
6. **Skipping should be safe.** Users who dismiss orientation can always access it later. Users who skip LLM setup get re-prompted gracefully, not crashed.

### Gap Analysis

**Gaps against the ideal flow (0:30 → 3:00):**

The ideal says: "Bridge moment begins — setup if needed, orientation, optional walkthrough, then conversation starts." The current experience has three separate disconnected pieces (setup wizard, blank chat, process guide start) with no coherent bridge between them.

**LLM setup is a disconnected gate**
- **User Impact: High (8/10).** The setup wizard currently blocks all progress. 5 providers × multiple auth modes with no guidance. Users who don't have a preferred provider are paralyzed.
- **Gap:** Setup exists as a separate phase rather than a step within the bridge. It has no orientation context ("why do I need this?") and no recommendation logic.

**No orientation — user doesn't know how to engage**
- **User Impact: High (7/10).** Clarity's value depends on the user engaging honestly and pushing back when the agent is wrong. But nothing in the current experience explains this. Users bring their ChatGPT habits: ask a question, get an answer, say "thanks." When Clarity pushes back, they're confused or annoyed rather than recognizing it as the point.
- **Gap:** There is no designed moment that teaches the user what Clarity is and how it differs from other AI tools. The process guides assume the user already knows to engage as a thinking partner.

**Abrupt transition to conversation**
- **User Impact: Medium (6/10).** Page reloads after setup, blank chat appears, "What are you working on?" with no context. Makes Clarity feel generic.
- **Gap:** No bridge between "configured" and "conversing." The user has no mental model for what's about to happen.

**No path for exploratory or evaluating users**
- **User Impact: High (7/10).** Users who type "what can you help with?" get an undesigned response. Users who installed to *evaluate* have no structured way to experience value before committing a real project.
- **Gap:** The opening assumes the user arrives with a project. A walkthrough would serve evaluators and teach the tool simultaneously.

**Skipping setup crashes later**
- **User Impact: High (7/10).** User skips because they're unsure, then gets an unhandled error on first use. Feels like broken software.
- **Gap:** No graceful degradation or re-prompting.

### The "How to Hold It Right" Problem

Clarity is a new kind of tool. Users' prior mental models (chatbot, search engine, document generator) all lead to wrong expectations. The bridge moment needs to communicate:

**What Clarity is:**
- A thinking partner that asks hard questions — not an assistant that does what you say
- It will push back on your ideas. That's the point, not a bug.
- The goal is *your* clarity about your project, not a document

**How to use it well:**
- Bring a real project — even a rough idea works
- Be honest about what you don't know; the gaps are where value lives
- Push back when the agent is wrong or asks something irrelevant
- The conversation produces documents as a byproduct — you don't need to fill anything in

**What to expect:**
- It will ask questions you haven't thought about
- It may reframe your goal in ways that feel unfamiliar
- The first few exchanges establish what you're working on; then it gets specific

### Walkthrough & Tutorial Considerations

A guided walkthrough addresses multiple problems simultaneously: it teaches how to hold the tool right, it serves evaluating users who don't have a project ready, and it demonstrates value before the user invests their own context.

**Design considerations:**

| Consideration | Options | Tradeoffs |
|--------------|---------|-----------|
| **Sample project** | Pre-built example vs. user picks from a few options vs. "tell me anything, even hypothetical" | Pre-built is fastest but may not resonate; user-chosen is more engaging but slower to value |
| **Length** | 3-5 exchanges (60 seconds) vs. full mini-session (3-5 minutes) | Short proves the concept; long proves the depth. First-timers need short. |
| **Interactivity** | Fully scripted replay vs. live conversation with training wheels vs. user-driven with guardrails | Scripted is predictable but passive; live is engaging but model-dependent; guardrails balance both |
| **Replayability** | One-time first-run vs. accessible from help menu | Should be accessible later for "remind me how this works" moments |
| **Content** | Software project vs. non-software vs. user's choice | Software is our strongest domain but limits audience; offering choice respects domain-neutrality |
| **What it demonstrates** | The pushback disposition vs. the output format vs. both | Pushback is the differentiator; output is the proof of durability. Show pushback first. |
| **Skip affordance** | Obvious "skip" button vs. subtle dismiss vs. no skip | Must be skippable — forcing a tutorial on an eager user is its own friction |

**Proposed walkthrough structure:**

1. **Brief orientation card** (5 seconds, dismissible): "Clarity is a thinking partner that pushes back. It'll ask hard questions to help you figure out what you actually want. Try it with a sample project, or bring your own."
2. **Choice**: [Try a sample project] [I have my own project] [Skip]
3. **If sample**: Pre-loaded 2-3 sentence project description → agent demonstrates a reframe or specificity push → user sees "oh, that's what it does" → "Ready to try with your own project?"
4. **If own project**: Straight to conversation with a brief inline hint: "Tell me what you're working on — even a rough idea. I'll ask questions to help sharpen it."

**What the walkthrough must demonstrate in ≤ 3 exchanges:**
- The agent pushes back (not just agrees)
- The pushback is specific and useful (not generic)
- Something gets captured as an artifact (a question, a requirement, a reframe)
- The user sees the output and thinks "that's worth keeping"

**Anti-patterns to avoid:**
- Don't make the tutorial feel like a tour of features ("here's the sidebar, here's the settings")
- Don't make it so long that impatient users skip and miss the orientation
- Don't use a project so trivial that the pushback feels fake
- Don't use a project so complex that a new user can't follow along
- Don't script responses so rigidly that it feels canned — the point is to demonstrate *thinking*, not recitation

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

### Design Principles

1. **The opening question should be answerable by everyone.** "What are you working on?" works for most but fails for "I'm just exploring" users. The opening must accommodate multiple attitudes.
2. **Don't announce the process.** The user should feel like they're talking to a thinking partner, not launching a workflow. No "Running problem-clarification process..." messages.
3. **Adapt to what arrives.** The agent's first response should be shaped by what the user actually says, not by a fixed script.
4. **CLI goes straight to conversation on first run.** The command menu is for returning users. First-timers shouldn't navigate infrastructure.

### Gap Analysis

**Gaps against the ideal flow (3:00 → 4:00):**

The ideal says: "User describes their project. Agent listens, asks clarifying questions, looks for first pushback opportunity."

**Opening question too vague for exploratory users**
- **User Impact: Medium (6/10).** "What are you working on?" works for users with a project in mind. Users who installed to *see what this does* don't have a ready answer.
- **Gap:** Assumes one user attitude (has a project) and doesn't handle others (exploring, evaluating, unsure). The bridge moment should have reduced this problem — but if the user skipped it or it didn't land, the opening still needs to work.

**CLI requires typing `run` at a menu**
- **User Impact: Medium (5/10).** The command menu adds bureaucracy before conversation begins. For first-run, it's all cost and no benefit.
- **Gap:** Exposes internal machinery (process names, commands) before the user has context for why they'd want that.

**No designed handling for common first-time responses**
- **User Impact: High (7/10).** "What can you help with?", "How does this work?", "I'm just trying this out" — these are all common first messages that currently get undesigned LLM-improvised responses.
- **Gap:** The process guide doesn't explicitly instruct the agent on how to handle evaluation/exploration attitudes.

### Proposed Model

The conversation opening adapts to what the user types:

| User says | Agent disposition |
|-----------|-----------------|
| Describes a project ("I'm building a...") | Standard problem clarification — look for first pushback opportunity |
| Asks what Clarity does ("What can you help with?") | Brief explanation + "Want to try it? Tell me about something you're working on — even rough ideas work." |
| Expresses a problem ("My team can't agree on...") | Jump directly into the problem — skip meta-discussion |
| Pastes existing context (PRs, docs, specs) | Acknowledge the context, assess it, identify what's missing or unclear |
| Says something exploratory ("Just trying this out") | Acknowledge, offer the sample walkthrough, or ask "What's on your mind? Even a half-formed idea works." |

**CLI simplification:** Remove the command menu for first-run. If the protocol doesn't exist, go straight into conversation.

### Open Questions

- Should the process guide explicitly enumerate these response patterns, or should it give a general principle and trust the model?
- How much should the first conversation differ from subsequent ones? (First visit has more hand-holding; return visits assume familiarity)
- Should the first conversation save outputs somewhere visible ("here's what we captured") to reinforce that this produces durable artifacts?

---

## First Insight

### Design Principles

1. **First insight within 3 exchanges.** The agent must surface something genuinely new to the user — a reframe, a missed stakeholder, a failure mode, a specificity challenge — before friction accumulates.
2. **Specific beats generic.** "Have you thought about edge cases?" is worthless. "What happens when two people edit the same paragraph simultaneously?" is valuable. The insight must be *about this project*, not about projects in general.
3. **Challenge, don't lecture.** The insight should arrive as a question or observation, not as a lesson. The user should feel "oh, good point" not "this thing is patronizing me."
4. **The insight should be visible in the output.** Whatever the agent surfaces should appear in the protocol document as a captured requirement, open question, or failure mode — reinforcing that this conversation is producing something durable.

### Gap Analysis

**User Impact: Critical (10/10).** This is the make-or-break moment. Everything else in this document exists to deliver the user to this point. If the first insight lands — if the user thinks "oh, I hadn't considered that" — they're engaged. They'll tolerate friction, learn the tool, come back tomorrow. If it doesn't land (the agent asks generic questions, produces obvious observations, or just agrees with them), the user concludes "this is just another chatbot" and leaves permanently. No amount of install polish or setup streamlining matters if this moment fails.

**Gaps against the ideal flow (3:00 → 4:00):**

The ideal says: "Agent responds with first substantive challenge or reframe." The current process guides support this but don't *guarantee* it:

- `processes/clarity-agent.md` Step 2 says "ask follow-up questions, help them articulate the problem" — but doesn't explicitly instruct the agent to surface a challenge in its *first* response.
- `processes/problem-clarification.md` Step 2.25 ("Pressure-test the framing of the goal") is the right mechanism but is positioned as a later step, not as something to do immediately.
- The agent's behavior depends heavily on model quality and the specificity of the user's input. A vague user description + a weak model = generic follow-up questions that deliver zero insight.
- There's no fallback: if the agent doesn't naturally find something to push back on, there's no designed mechanism to ensure value is still delivered.

### Supporting Research

Clarity's own failure analysis (FM01: User Disengagement) identifies this as the existential risk and calls "time to first insight" the critical metric. The notes.md captures it as: "Value demonstration is the master intervention." The solution doc establishes it as a design constraint on Layer 2.

Despite this, the process guides don't yet enforce it mechanically — they *encourage* early challenge but leave it to the model's judgment. This is the gap between principle and implementation.

### What "First Insight" Looks Like

- Reframing: "You said you want to build X — but it sounds like the real goal is Y. Is that right?"
- A missed stakeholder: "Who maintains this after launch? That person has different needs than the builder."
- A failure mode: "What happens when [specific scenario]? That seems unaddressed."
- A specificity push: "You said 'fast' — what does fast mean here? 100ms? 5 seconds? Different answers lead to different architectures."

### Proposed Constraint on Process Guides

The opening of `processes/clarity-agent.md` Step 2 and `processes/problem-clarification.md` should be structured to surface one of these within the first 2-3 exchanges. Not after information gathering — *during* the first response to what the user says. Concretely:

- The agent's first response to the user's project description should include at least one question that reveals a gap, assumption, or unconsidered angle.
- If the user's description is too thin to challenge substantively, the agent should draw out more detail with *specific* questions (not "tell me more" — rather "who uses this and what happens if they can't?").

### Open Questions

- Can we measure time-to-first-insight? (Proxy: user response length increases after agent challenge)
- Should the agent explicitly flag its first pushback? ("Here's something to think about..." vs. just asking the question naturally)
- How do we avoid the failure mode where the "first insight" is generic/obvious and actually *decreases* trust?
