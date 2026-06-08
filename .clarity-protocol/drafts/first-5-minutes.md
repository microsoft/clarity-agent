# First 5 Minutes Experience — Draft Plan

## The Journey

Discovery → Install → LLM Setup → First Conversation → First Insight

Each phase has a job. The user should never be stuck wondering "what do I do next?"

---

## Phase 0: Discovery & Install Choice

### Problem

Clarity's README currently presents two parallel install options (desktop app vs. CLI script) with roughly equal weight. This forces a choice at a moment when the user has the least context to make it.

### User Impact: **High** (7/10)

Every single new user encounters this. A confused user at this stage doesn't bounce from one option to the other — they bounce from the project entirely. However, developers (our primary current audience) are somewhat accustomed to choosing between install methods, which limits the severity. The real damage is to non-developer users (PMs, founders, strategists) who see two technical-looking options and feel "this isn't for me."

### Research: How Local-First Tools Handle This

| Tool | Strategy | How CLI relates to GUI |
|------|----------|----------------------|
| **Ollama** | CLI command is the hero; ".dmg" is secondary fallback | Same install produces both; no choice needed |
| **LM Studio** | App is the product; CLI ships inside it | `lms` available after app install; `npx lmstudio install-cli` if PATH is wrong |
| **Docker Desktop** | One installer bundles everything (macOS/Win) | CLI included; Linux gets CLI-only path separately |
| **VS Code** | Download page auto-detects platform; one big button | `code` CLI installed from within the app |
| **Ghostty** | README describes the project; links to separate download page | No CLI vs GUI distinction — it's one app |
| **Claude Code** | One `curl` command; no GUI exists | N/A — pure CLI |

**Key finding:** Successful local tools either (a) bundle both modalities in one install, or (b) pick one as primary and let the other be discovered later. None present parallel equal-weight choices.

### Design Principles

1. **One obvious default path.** The user shouldn't have to understand the modality difference before they've used the tool.
2. **The README is not a download page.** It should explain what Clarity is and link to install instructions, not host them inline (or if inline, with a clear single default).
3. **Platform detection, not user detection.** The install method adapts to the OS, not to a persona the user self-selects into.
4. **CLI is discovered, not chosen upfront.** Power-user paths (embed, headless server) appear after first use, not before.

### Proposed Model

**Desktop app is the primary install for macOS and Windows.** It bundles the Python server, needs no prerequisites, and includes all functionality. The CLI (`clarity embed`, `clarity web`, etc.) can be installed from within the app or via a separate command for Linux/headless.

**Linux and headless environments get the script installer.** This is the appropriate audience for `curl | bash` — people comfortable with terminals who may not have a desktop environment.

**The README leads with one thing:**

> Download Clarity from the [releases page](link) — or on Linux: `curl -fsSL ... | bash`

Not two parallel blocks of equal weight.

### Open Questions

- Should the desktop app offer "Install CLI" from a menu (VS Code model)?
- Should `curl | bash` on macOS install the app, the CLI, or both?
- How do we handle the coding-agent-only user who wants `clarity embed` without the app?

---

## Phase 1: Install Experience

### Issues & Impact

**Silent sidecar failure (Desktop)**
- **User Impact: Critical (9/10).** User sees a blank/loading screen with no error and no recourse. They conclude the app is broken and uninstall. This is a complete loss — the user did everything right and got nothing. The only recovery path (checking `~/.clarity/clarity-startup.log`) is invisible to anyone who isn't a developer debugging their own software.

**15-20 minute CLI install time**
- **User Impact: High (8/10).** A "try it" user won't wait 15 minutes for dependencies to install. This is acceptable for developers committing to a tool they've already decided to adopt, but devastating for curious first-timers. The Ollama comparison is instructive: their install takes ~30 seconds because they ship a binary rather than building from source.

**Prerequisite assumptions (git, Python 3.12, Node 22)**
- **User Impact: High (7/10).** Each missing prerequisite is a blocking error with a cryptic message. The user must leave Clarity's install flow, figure out how to install Python/Node/git for their platform, then return and retry. Each round-trip risks abandonment. Developers usually have these; non-developers almost never do.

**Embed breaks without system install**
- **User Impact: Medium (5/10).** Only affects users who try `clarity embed` before installing Clarity globally — a sequencing error. The error message ("Clarity is not installed on this machine") is at least clear, but doesn't tell them *how* to fix it. Lower impact because the embed path is typically reached by users who already have Clarity working.

### Principles

- Install should take < 3 minutes on a fast connection
- Zero decisions during install (decisions happen in setup, not install)
- If something fails, the error message should say what to do, not just what went wrong
- Progress should be visible ("downloading…", "configuring…", "ready!")

### Proposed Improvements

- **Desktop:** Add a visible startup progress indicator. If sidecar fails, show an error dialog with "Run `clarity doctor`" suggestion rather than hanging.
- **CLI script:** Check prerequisites (git, Python) *before* downloading anything. Print clear remediation: "Python 3.12+ required. Install with: brew install python@3.12" (platform-appropriate).
- **CLI script speed:** Explore shipping a pre-built binary (like Ollama does) instead of cloning repo + building. The 15-minute install is a dealbreaker for a "try it" experience.

---

## Phase 2: LLM Setup

### Problem

After install, the user must configure an LLM provider. This is currently a 5-provider × multiple-auth-mode matrix with no guidance on what to pick.

### Issues & Impact

**No recommendation — 5 providers with no guidance**
- **User Impact: High (8/10).** This is the single biggest "I don't know what to do" moment in the entire flow. Users who don't already have a preferred LLM provider (many non-developers, and even some developers) are stuck. They don't know what these providers *are*, which is best, or what the cost implications are. The paradox of choice applies strongly here — more options feel less helpful. Users who do have a preferred provider still waste time scanning the list rather than being auto-detected.

**Validation happens late (step 4 of 5)**
- **User Impact: Medium (6/10).** User fills in 3 screens of information, hits "test," discovers their key is wrong, and must restart. Frustrating but recoverable — they'll try again. The real risk is users who mistype a key, get a vague "connection failed" error, and assume the tool doesn't support their provider.

**CLI auth prompt is terse (`[l] [e] [s]`)**
- **User Impact: Medium (5/10).** Only affects CLI installers (already a more technical audience). The three options are cryptic but the stakes are low — picking the wrong one just means re-running. Still, it's a missed opportunity to guide the user toward the best choice.

**Skipping setup produces a runtime crash later**
- **User Impact: High (7/10).** User skips because they're not sure what to pick, expects to configure later, then gets an unhandled error on first use. This feels like a bug in the software, not a configuration issue. It erodes trust in the tool's quality at exactly the moment they're forming first impressions.

### Design Principles

1. **Recommend, don't just list.** Surface a default based on what's already available on their system (env vars, installed CLIs).
2. **Validate early.** Check API key format before the "test connection" step.
3. **Skipping should be safe.** If skipped, re-prompt on next launch rather than crashing.
4. **The setup wizard is the last gate before value.** Keep it short — minimum viable configuration to start talking.

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

### Problem

After setup completes, the user lands in an empty chat with a vague opening question. The transition from "setup complete" to "here's your thinking partner" is abrupt, and users who are exploring (vs. arriving with a project) have no clear path.

### Issues & Impact

**Abrupt transition from setup to conversation**
- **User Impact: Medium (6/10).** User completes the wizard, page reloads, and suddenly there's a chat with "What are you working on?" — with no context about what just happened or what to expect. Not blocking (users can figure out it's a chat), but it makes Clarity feel like a generic chatbot rather than a specialized thinking partner. The bridge moment is where you set expectations and build confidence that this is different from ChatGPT.

**CLI requires typing `run` at a menu**
- **User Impact: Medium (5/10).** The command menu adds a step that feels like bureaucracy — the user came to talk, not to navigate menus. Moderate impact because CLI users are comfortable with commands, but it makes the first experience feel tool-like rather than conversational. For first-run specifically, the menu is all cost and no benefit.

**Opening question too vague for exploratory users**
- **User Impact: Medium (6/10).** "What are you working on?" works perfectly for users who arrive with a project in mind. But users who installed Clarity to *see what it does* — a significant portion of first-timers — don't have a ready answer. They feel put on the spot. This isn't blocking (they can type anything), but it creates a moment of "I don't know what to say" that slows momentum.

**No path for "what does this do?" users**
- **User Impact: High (7/10).** A user who types "what can you help with?" or "how does this work?" currently gets a response generated entirely by the LLM — there's no designed experience for this case. The agent may explain well or may be awkward. This matters because a meaningful portion of first-time users are evaluating, not using. If the evaluation experience is poor, they never become users.

### Current State

- **Web/Desktop:** Auto-starts clarity-agent process. User sees "What are you working on?" or similar.
- **CLI:** User must type `run` at a menu before conversation begins.
- **Embedded:** Coding agent infers context and begins inline.

### Design Principles

1. **Bridge the transition.** A brief moment between "setup done" and "conversation starts" that sets expectations: what Clarity does, what's about to happen, what the user should bring.
2. **The opening question should be answerable by everyone.** "What are you working on?" works for most but fails for "I'm just exploring" users.
3. **First value in < 3 exchanges.** The agent should push back, surface a gap, or reframe something within the first few turns.
4. **Don't announce the process.** The user should feel like they're talking to a thinking partner, not launching a workflow.

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

### User Impact: **Critical** (10/10)

This is the make-or-break moment. Everything else in this document exists to deliver the user to this point. If the first insight lands — if the user thinks "oh, I hadn't considered that" — they're engaged. They'll tolerate friction, learn the tool, come back tomorrow. If it doesn't land (the agent asks generic questions, produces obvious observations, or just agrees with them), the user concludes "this is just another chatbot" and leaves permanently. No amount of install polish or setup streamlining matters if this moment fails.

### The Critical Metric

Everything above exists to get the user to this moment: the first time Clarity surfaces something they hadn't thought of. If this happens within 3 exchanges, they stay. If it doesn't, they bounce.

### What "First Insight" Looks Like

- Reframing: "You said you want to build X — but it sounds like the real goal is Y. Is that right?"
- A missed stakeholder: "Who maintains this after launch? That person has different needs than the builder."
- A failure mode: "What happens when [specific scenario]? That seems unaddressed."
- A specificity push: "You said 'fast' — what does fast mean here? 100ms? 5 seconds? Different answers lead to different architectures."

### Design Constraint on Process Guides

The opening of `processes/clarity-agent.md` Step 2 and `processes/problem-clarification.md` should be structured to surface one of these within the first 2-3 exchanges. Not after information gathering — *during* the first response to what the user says.

### Open Questions

- Can we measure time-to-first-insight? (Proxy: user response length increases after agent challenge)
- Should the agent explicitly flag its first pushback? ("Here's something to think about..." vs. just asking the question naturally)
- How do we avoid the failure mode where the "first insight" is generic/obvious and actually *decreases* trust?

---

## Summary: The Ideal First 5 Minutes

```
0:00  User lands on README/releases page
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
