# First 5 Minutes Experience — Draft Plan

**Assertion:** Clarity Agent needs to show value (in the form of a helpful insight) in the first 5 minutes of use.

**Required steps to do that:** Discovery → Install → LLM Setup → First Conversation → First Insight

## The Ideal First 5 Minutes

```
0:00  User lands on README (aka.ms/clarity-agent) or releases page (aka.ms/clarity-agent-bits)
      → One obvious action: "Download" (macOS/Win) or "curl | bash" (Linux)

0:30  Install completes
      → App opens (or web UI launches)
      → If LLM already detectable: auto-configure, skip wizard

1:00  Setup wizard (if needed)
      → Recommended provider pre-selected
      → Enter key → Test → Save (3 clicks)

2:00  Bridge moment
      → Brief orienting message: "Tell me what you're working on"
      → Conversation begins

3:00  User describes their project (even roughly)

4:00  Agent responds with first substantive challenge or reframe
      → User thinks: "Oh, I hadn't considered that"

5:00  User is engaged. Process continues naturally.
```

Each phase has one job: get to the next phase with minimum friction and maximum clarity about what's happening.

---

## Phase 0: Discovery & Install Choice

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

## Phase 1: Install Experience

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

## Phase 2: LLM Setup

### Design Principles

1. **Recommend, don't just list.** Surface a default based on what's already available on their system (env vars, installed CLIs).
2. **Validate early.** Check API key format before the "test connection" step.
3. **Skipping should be safe.** If skipped, re-prompt on next launch rather than crashing.
4. **The setup wizard is the last gate before value.** Keep it short — minimum viable configuration to start talking.

### Gap Analysis

**Gaps against the ideal flow (0:30 → 1:00):**

The ideal says: "If LLM already detectable, auto-configure and skip wizard. If wizard needed, recommended provider pre-selected, 3 clicks to done." Here's where the current experience falls short:

**No recommendation — 5 providers with no guidance**
- **User Impact: High (8/10).** This is the single biggest "I don't know what to do" moment in the entire flow. Users who don't already have a preferred LLM provider (many non-developers, and even some developers) are stuck. They don't know what these providers *are*, which is best, or what the cost implications are. The paradox of choice applies strongly here — more options feel less helpful.
- **Gap:** Violates "recommend, don't just list." The wizard shows a flat list of 5 providers with no hierarchy, no "recommended" badge, no auto-detection of what's already configured on the system.

**Validation happens late (step 4 of 5)**
- **User Impact: Medium (6/10).** User fills in 3 screens of information, hits "test," discovers their key is wrong, and must restart. Frustrating but recoverable.
- **Gap:** Violates "validate early." The ideal flow is "enter key → test → save" (3 clicks). The current flow is "pick provider → pick auth mode → enter credentials → test → save" (5 steps, with validation only at step 4).

**CLI auth prompt is terse (`[l] [e] [s]`)**
- **User Impact: Medium (5/10).** Only affects CLI installers (already a more technical audience). The three options are cryptic but the stakes are low.
- **Gap:** Minor violation of "recommend, don't just list" — but in a lower-traffic path. CLI users can tolerate terse prompts.

**Skipping setup produces a runtime crash later**
- **User Impact: High (7/10).** User skips because they're not sure what to pick, expects to configure later, then gets an unhandled error on first use. This feels like a bug in the software, not a configuration issue.
- **Gap:** Directly violates "skipping should be safe." The system should re-prompt gracefully, not crash.

### Supporting Research

- **Ollama** requires no API key — it runs models locally. Zero setup friction. (Not applicable to Clarity, which needs a cloud LLM, but illustrates the ideal: no setup step at all.)
- **LM Studio** auto-detects downloaded models on startup. If you have models, it just works. If you don't, it shows a model browser (the equivalent of our provider picker) with recommendations.
- **VS Code** extensions that need auth (GitHub Copilot, etc.) prompt inline when you first try to use the feature — not at install time. The "try it and get prompted" model means setup only happens when the user has already demonstrated intent.
- **Docker Desktop** requires no account for local use. Login is optional and prompted only when you try to push/pull from Docker Hub.

**Pattern:** The best tools either (a) need no setup at all, (b) auto-detect what's available, or (c) defer setup to the moment of use rather than blocking at launch.

### Proposed Model

**Auto-detect first.** Before showing the wizard, check:
- Is `ANTHROPIC_API_KEY` set? → Pre-select Anthropic, pre-fill, go straight to "Test & Save"
- Is `claude` CLI logged in? → Pre-select Claude SDK, test it, auto-configure
- Is `gh` CLI authenticated? → Pre-select GitHub Copilot

**If nothing detected, recommend one path** with a brief rationale:
> "Clarity works best with Claude. If you have a Claude account, that's the fastest path. [Use Claude] [Other providers →]"

**Keep the full provider list accessible** but don't lead with it. "Other providers" expands the matrix for users who need Azure, OpenAI, etc.

### Open Questions

- What's the right default recommendation? (Claude is best quality; GitHub Copilot is most likely "already have it" for developers)
- Should the app work in a limited mode without an LLM? (e.g., browse existing protocol, view documents, but can't start conversations)
- How do we handle the "I just want to try it" user who doesn't have any API key yet?

---

## Phase 3: First Conversation (The Opening)

### Design Principles

1. **Bridge the transition.** A brief moment between "setup done" and "conversation starts" that sets expectations: what Clarity does, what's about to happen, what the user should bring.
2. **The opening question should be answerable by everyone.** "What are you working on?" works for most but fails for "I'm just exploring" users.
3. **First value in < 3 exchanges.** The agent should push back, surface a gap, or reframe something within the first few turns.
4. **Don't announce the process.** The user should feel like they're talking to a thinking partner, not launching a workflow.

### Gap Analysis

**Gaps against the ideal flow (2:00 → 3:00):**

The ideal says: "Brief orienting message, then conversation begins. User describes their project." Here's where the current experience falls short:

**Abrupt transition from setup to conversation**
- **User Impact: Medium (6/10).** User completes the wizard, page reloads, and suddenly there's a chat with "What are you working on?" — with no context about what just happened or what to expect. Not blocking, but it makes Clarity feel like a generic chatbot rather than a specialized thinking partner.
- **Gap:** Violates "bridge the transition." There's no moment that sets expectations or differentiates Clarity from ChatGPT. The user has no mental model for what's about to happen.

**CLI requires typing `run` at a menu**
- **User Impact: Medium (5/10).** The command menu adds a step that feels like bureaucracy — the user came to talk, not to navigate menus. For first-run specifically, the menu is all cost and no benefit.
- **Gap:** Violates "don't announce the process." The menu exposes internal machinery (process names, commands) before the user has any context for why they'd want that.

**Opening question too vague for exploratory users**
- **User Impact: Medium (6/10).** "What are you working on?" works for users who arrive with a project in mind. But users who installed to *see what this does* don't have a ready answer. They feel put on the spot.
- **Gap:** Violates "answerable by everyone." The opening assumes one user attitude (has a project) and doesn't handle others (exploring, evaluating, unsure).

**No path for "what does this do?" users**
- **User Impact: High (7/10).** A user who types "what can you help with?" currently gets an undesigned LLM-generated response. This matters because a meaningful portion of first-time users are evaluating, not using. If the evaluation experience is poor, they never become users.
- **Gap:** Violates "bridge the transition" at a deeper level. The bridge should be good enough that this question doesn't arise — but if it does, there should be a designed response, not an improvised one.

### Supporting Research

- **Ollama** after install just runs and says: "You'll be prompted to run a model or connect Ollama to your existing agents." It tells you what to do next, in one line.
- **Obsidian** on first launch shows a vault creation dialog with a "Learn more" option. It doesn't drop you into a blank page and wait — it explains the one concept you need (vault = folder) before starting.
- **LM Studio** on first launch shows a model browser — it gives you something to *do* rather than asking an open-ended question.
- **VS Code** on first open shows a "Get Started" tab with categorized next steps (themes, keybindings, extensions). It gives structure without being prescriptive.

**Pattern:** Good first-run experiences either (a) tell you exactly what to do next, or (b) give you structured options rather than a blank canvas. None of them open with a vague question and wait.

### Proposed Model

**After setup, show a brief bridge screen** (2-3 seconds, or a dismissible card):
> "Clarity helps you think through projects — asking the hard questions before you build. Tell me what you're working on, and I'll help you figure out what you actually want."

Then the conversation begins. The opening adapts to what the user types:

| User says | Agent disposition |
|-----------|-----------------|
| Describes a project ("I'm building a...") | Standard problem clarification — look for first pushback opportunity |
| Asks what Clarity does ("What can you help with?") | Brief explanation + "Want to try it? Tell me about something you're working on — even rough ideas work." |
| Expresses a problem ("My team can't agree on...") | Jump directly into the problem — skip meta-discussion |
| Pastes existing context (PRs, docs, specs) | Acknowledge the context, assess it, identify what's missing or unclear |

**CLI simplification:** Remove the command menu for first-run. If the protocol doesn't exist, go straight into conversation. The menu is for returning users who want specific operations.

### Open Questions

- Should the bridge screen be a one-time thing, or appear each session?
- How much should the opening differ by modality? (Desktop user vs. developer using `clarity embed`)
- Is there a way to let users "try before committing" — e.g., a sample conversation or walkthrough?
- Should the first conversation save outputs somewhere visible ("here's what we captured") to reinforce value?

---

## Phase 4: Time to First Insight

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
