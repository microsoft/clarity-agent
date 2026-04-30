# Integration Strategy — Draft

*Status: Exploration draft (2026-04-06). Not yet committed to solution or architecture.*

## Overview
Clarity risks becoming a tool product builders (especially developers) pick up during planning and put down during development, including the crucial moments of iteration where it should shine. Every new tool competes for attention with everything already installed.  Meanwhile, agentic systems are converging on extensibility primitives like skills, MCP servers, rules files, and extensions that let capabilities compose into tools people already use.  

This document recomends integration points in externally available tools developers, vibe coders, and product managers depend on. The recomendation is followed by backing data for citizen developers (vibe coders), product managers, and professional developers and some of the other integration points considered.

The integrated experience proposed here is not a replacement for the freestanding Clarity Agent experience, it is ment to suppliment it with the expectation that both experiences are necessary.

## Recommendation Summary

### Which tools matter most
After surveying the AI tooling landscape across citizen developers, product managers, and professional engineers, the following tools represent the highest-impact integration targets for Clarity.  See the persona breakouts below for deeper dives into the data including the data sources for all assertions.

**Top 10 tools, in priority order:**
| Priority | Tool | Persona(s) served | Why it matters |
|---|---|---|---|
| 1 | **GitHub Copilot** | Professional engineers, Citizen devs | Highest enterprise adoption (29% workplace, 90% Fortune 100). Microsoft strategic anchor. Full MCP support. The default AI coding tool — if Clarity works in Copilot, it works where the most developers are. |
| 2 | **Claude Code** | Professional engineers | Tied at 18% workplace usage, 46% "most loved." Leads for complex tasks (architecture, refactoring). Full MCP + Skills. The tool most likely to be used at exactly the moments Clarity should intervene. |
| 3 | **Cursor** | Professional engineers, Citizen devs | Leading AI-native IDE (18% workplace, $2B+ ARR). Full MCP + rules file support. Dominant among startups and power users. Where the most technically ambitious work happens. |
| 4 | **GitHub (platform)** | All three | 100M+ developers, 420M repos. PR review and Actions are the universal safety net — tool-agnostic, works for every persona, only surface that reaches closed ecosystems and autonomous agents. The `.clarity-protocol/` directory lives here. |
| 5 | **Lovable** | Citizen devs | #1 vibe coding tool. Highest risk surface: non-technical builders shipping production apps with auth, payments, user data. Closed ecosystem — hardest to reach, but most important to reach. |
| 6 | **Bolt** | Citizen devs | #2 vibe coding tool. Rapid prototyping that increasingly gets deployed. Same closed-ecosystem challenge as Lovable. |
| 7 | **Windsurf** | Professional engineers, Citizen devs | Budget Cursor (free/$15/mo) that bridges the vibe coder and professional developer audiences. Full MCP + rules file support. The easiest integration port after Cursor — same extensibility, more beginner-oriented audience. |
| 8 | **VS Code** | Professional engineers | 72–76% market share, 14M+ active users. The platform underlying Copilot, Cline, and many other tools. Full MCP support. Clarity's IDE extension (protocol sidebar) lives here. |
| 9 | **Replit** | Citizen devs | #3 vibe coding tool. AI Agent ships production apps. Closed ecosystem, but growing risk surface. |
| 10 | **JetBrains** | Professional engineers | 11M+ users, 88% Fortune Global 100, 84% of Java devs. Full MCP support via AI Assistant. Enterprise-dominant for JVM and Python. |

**Notable gap: PM tools.**  
The PM toolchain is fragmented and, at the same time, PMs are also most likely to use Clarity Agent directly given core PM tools are similar in nature to the Clarity Agent web UX, cli, and app interface (Claude Projects, ChatGPT, Copilot M365, Notion AI, and Gemini).  With that in mind, the proposed integration targets skew toward citizen developers (where the risk surface is highest) and professional engineers (where extensibility is strongest).

### Proposed integration point

**Recommendation: Rules files + MCP Server for context-aware Clarity inside the coding agent.**

Combining roles files with a Clarity MCP server means builders don’t need to explicitly invoke Clarity, the agent does it based on context, and the MCP server can still provide interactive conversation around ambiguous decisions and maintain the clarity-protocol. Combined, they form a context-aware system that delivers the right intervention at the right moment without requiring any action from the developer.

**The rules file is the _trigger_ for Clarity Agent** - it teaches the AI coding agent when Clarity should be invoked, based on what the developer is building. It identifies risky moments (adding auth, handling payments, making an architectural choice, touching a stale protocol area). When the remedy is clear, the agent acts like a linter and fixes it; when it isn’t, invoke Clarity.

Examples of rules files: `.github/copilot-instructions.md`, `.cursorrules`, `.windsurfrules`, `AGENTS.md`, `CLAUDE.md`.  

**The MCP server is the _engine_** - it provides the actual Clarity tools (`check_staleness()`, `record_decision()`, `run_thinker()`, `clarity_check()`) and delivers the right depth of response.  When there's ambiguity, the MCP tools open a structured conversation until the ambiguity resolves.  MCP is a format AI agents natively understand. The agent auto-discovers these tools and calls them as part of its reasoning loop without human intervention.

| Effort | Reach | Depth | When it activates |
|---|---|---|---|
| Low–Medium (rules: write once; MCP: thin adapter over existing REST API) | Tools 1–3, 7–8, 10 + Claude Projects (~70%+ of engineers) | Full (context-aware triggers → complete Clarity process) | During coding, at decision points detected by the agent |

**Example flow for continuous protocol maintenance.** A critical property of this approach is that the MCP server has read-write access to `.clarity-protocol/`, which means the protocol stays current *as a side effect of coding* — not as a separate maintenance task. The flow:

1. Rules file detects a trigger moment (e.g., engineer adds a payment flow)
2. Agent calls `clarity_check()` → MCP server returns "no failure analysis exists for payment handling"
3. Agent walks through the analysis conversationally with the engineer
4. Agent calls `record_decision()` → MCP server writes the outcome back to `.clarity-protocol/`
5. Next time code touches payments, the rules file triggers again → `check_staleness()` reads the existing protocol → returns "failure analysis exists but is stale relative to this change" → agent updates it

This creates a living protocol that evolves with the codebase. Architectural decisions get documented as they happen. Failure analyses get updated when the code they describe changes. Staleness is detected and resolved in the normal flow of development, not in a periodic review nobody schedules.

**What remains uncovered: Closed vibe-coder platforms** Vibe coding tools like Lovable, Bolt, and Replit are only reachable via the GitHub Action at PR time and only if the developer deploys through GitHub. PM AI thinking partners other than Claude Projects require platform-specific adapters.

## 1. Citizen Developers — Vibe Coding Tools

These users say "build me an app that does X" and get working code in minutes. They're not going to run a failure analysis yet they build (and ship) software that handles user data, takes payments, and faces the internet. Clarity's biggest value prop for this audience is to show up uninvited at critical moments to help with security considerations (auth, payments, user data, external APIs) and to partner on product consdierations.

### Where vibecoders are
Tools are ordered by a blend of adoption, risk surface, and strategic relevance (see prioritization criteria below):

- **Lovable** — Ranked #1 pure vibe coding tool for non-technical founders. Ships full-stack apps with auth, payments, and Supabase integration. Highest risk surface in this category: production software built by people with no security background [1][2][6].
- **Bolt** — Second most cited tool across comparison reviews. Dominates rapid prototyping and hackathon-style builds. Lower risk surface than Lovable (more front-end focused) but very high adoption among first-time builders [1][5].
- **Replit** — Strong in education and collaborative contexts. AI Agent mode goes beyond prototyping — it handles database migrations and deploys production apps. Meaningful risk surface [1][6].
- **v0 by Vercel** — Industry standard for generating React/Next.js components from prompts or mockups. More UI scaffolding than full-stack, so lower risk surface, but widely used as a starting point that gets deployed [2][4].
- **GitHub Spark** — GitHub-native vibe coding (experimental/preview). Strategically significant despite early-stage maturity: it operates inside the GitHub ecosystem where Clarity's deploy gates, PR review, and Actions integration already work. The natural platform for Clarity to reach vibe coders without requiring any new integration surface. Worth prioritizing for early engagement as it matures [3].
- **Cursor** — Primarily a professional tool (1M+ users), but increasingly used for casual "build me an app" flows. Full Clarity extensibility (MCP, `.cursorrules`). Covered in depth in Section 3 [1][8].
- **Windsurf** — Budget-friendly alternative to Cursor (free/$15/mo). Growing beginner and hobbyist audience. Full extensibility (MCP, `.windsurfrules`, agentic "Cascade" mode) — the easiest vibe-coder-adjacent tool for Clarity to reach [7][8].
- **Claude Code (casual)** — Terminal-based; used casually by developers for quick builds. Full Clarity integration support (MCP, skills, `CLAUDE.md`). Covered in depth in Section 3 [7].
- **Firebase Studio** — Google's new IDE with tight Firebase integration (auth, DB, hosting). Free tier driving adoption among Google-ecosystem citizen devs. Competitive surface to watch — if significant adoption materializes, it's a Google counterpart to GitHub Spark [3].

### Possible integration points
| Integration point | User experience | Value delivered | Risks |
|---|---|---|---|
| Rules file (`.cursorrules`, `CLAUDE.md`, `AGENTS.md`) | Agent pauses at auth/payments/data patterns; fixes clear issues automatically, opens conversation for ambiguous ones | Security thinking injected where it never existed; catches the "storing passwords in plaintext" class of mistakes | Rules are static — can't adapt to project evolution; alert fatigue if too aggressive; user may override without understanding |
| MCP `clarity-check` tool | Agent calls a lightweight threat check; returns top 3 risks as actionable items | Context-aware analysis, not just pattern matching; can reason about the specific system being built | Depends on MCP adoption across vibe-coding tools; quality degrades if project context is thin |
| `/clarity-secure` skill | On-demand focused security brainstorm; produces a checklist scoped to current project | Deepest citizen-dev analysis; closest to "having a security engineer review your code" | Requires user to know it exists and choose to invoke — the persona least likely to do so |
| Deploy gate (CI/CD) | Pre-deploy scan surfaces unaddressed risks; blocks or warns at ship time | Last line of defense; catches what earlier interventions missed | Positioned late — expensive to fix issues at deploy; can become a checkbox people dismiss |

### Tool compatibility

| Integration point | Lovable | Bolt | Replit | Cursor | v0 |
|---|---|---|---|---|---|
| Rules file | ❌ No equivalent | ❌ No equivalent | ❌ No equivalent | ✅ `.cursorrules` | ❌ No equivalent |
| MCP `clarity-check` | ❌ No MCP | ❌ No MCP | ❌ No MCP | ✅ MCP supported | ❌ No MCP |
| `/clarity-secure` skill | ❌ No skill system | ❌ No skill system | ❌ No skill system | ⚠️ Tool-specific impl needed | ❌ No skill system |
| Deploy gate (CI/CD) | ⚠️ Deploys to Netlify | ✅ Tool-agnostic | ✅ Tool-agnostic | ✅ Tool-agnostic | ⚠️ v0 deploys differently |

Lovable, Bolt, and Replit lead because they represent the largest concentration of citizen developers shipping production software with real risk surfaces — and the widest extensibility gap. Cursor appears because it's the most practical near-term integration surface for vibe coders who use an extensible tool. v0 rounds out the top five by adoption, though its UI-focused output carries less risk. Windsurf, Claude Code, and GitHub Spark are covered in the tool-specific analysis above and in depth in Section 3; their extensibility story is strong but they serve a more developer-adjacent audience.

**The gap:** Bolt, Lovable, Replit, and v0 — arguably the most "vibe coder" tools — support almost none of the extensibility primitives. Rules files and MCP are Cursor/Windsurf/Claude Code concepts. These tools are more closed ecosystems. The citizen developer strategy may need a fundamentally different approach for these platforms.

**The Windsurf opportunity:** Windsurf occupies a sweet spot — it targets beginners and budget-conscious developers (free/$15/mo) but supports the same extensibility primitives as Cursor (rules files via `.windsurfrules`, MCP, agentic "Cascade" mode) [7][8]. This means the Cursor integration story ports directly to Windsurf with minimal effort, extending Clarity's reach into a more beginner-oriented audience.

### Emerging platforms to watch

| Platform | Why it matters | Extensibility outlook |
|---|---|---|
| **GitHub Spark** | GitHub-native; natural fit for deploy gates & PR review that Clarity already targets. If it matures, the GitHub Actions integration gives Clarity a free entry point. | Early/experimental. Extensibility TBD but GitHub's ecosystem is the most Clarity-friendly. |
| **Firebase Studio** | Free, Google-ecosystem. Tight Firebase integration means auth/DB patterns are templated — Clarity could validate those templates. Growing citizen dev audience. | Likely closed initially. Google Cloud Build could serve as deploy gate surface. |
| **Google AI Studio** | Free, multimodal, Gemini-based. More for AI app prototyping than shipping production software. Lower risk surface. | Minimal. Not a priority until it starts producing deployable apps. |
| **Taskade Genesis** | Workflow/app automation builder. More productivity tool than code tool. | Low overlap with Clarity's target use cases. |
| **Base44** | No-code full-stack builder. Similar closed-ecosystem challenges as Bolt/Lovable. | Niche audience. Watch only. |

### Sources (Section 1)

1. "Best Vibe Coding Tools 2026: Compared & Ranked" — vibecoding.app/blog/best-vibe-coding-tools
2. "Best Vibe Coding Tools (2026): 10 Platforms Tested and Compared" — morphllm.com/best-vibe-coding-tools
3. "Best Vibe Coding Tools & AI App Builders Compared (2026)" — taskade.com/blog/best-vibe-coding-tools
4. "Best Vibe Coding Tools: Free to $200/mo, Ranked for 2026" — findskill.ai/blog/best-vibe-coding-tools-2026
5. "Vibe Coding Tools Compared 2026: Bolt.new vs Lovable vs Replit vs v0" — effloow.com/articles/vibe-coding-tools-compared-bolt-lovable-replit-v0-2026
6. "Best Vibe Coding Platforms in 2026: Full Comparison" — vibecodingacademy.ai/blog/vibe-coding-platforms-compared
7. "AI Coding Assistants Complete Guide 2026: Devin, Cursor, Windsurf and More" — calmops.com/ai/ai-coding-assistants-2026-complete-guide
8. "Vibe Coding Tools Compared: 13 Tools Tested (2026)" — buildwithabid.com/blog/vibe-coding-tools-compared-2026
9. "The 2026 Vibe Coding Landscape: Best AI Coding Tools Compared" — creolestudios.com/vibe-coding-comparison-for-decision-makers


## 2. Product Managers — Working with Engineering Teams

These users think in problems, stakeholders, and tradeoffs. They already write specs and they already use AI to help. PMs who are counterparts to software engineering teams can work in code-adjacent tools like coding agents with vibe-coding flows. The protocol format is the handoff contract: what a PM produces with Clarity is what an engineer's coding agent consumes. For PMs, Clarity produces sharper specs and surfaces misalignments. The artifacts clarity protocol produces here matter - they are the bridge to engineering.

### Where product managers are
PMs in operate across three layers of AI tooling: 
1. AI thinking partners (where they draft and reason)
2. Collaboration platforms (where they align with stakeholders and engineers)
3. specialized PM tools (where they manage roadmaps and feedback).

More than 70% of PMs use at least one AI tool daily, and 73% of PM teams use AI features weekly [1][2]. Clarity's integration points primarily target the AI thinking partner layer — but the *output* of Clarity must land in the collaboration platforms where engineers pick it up.

Tools are ordered by strategic relevance (weighted towards Microsoft/GitHub ecosystem) and adoption among PMs working closely with engineering teams:

**AI thinking partners (primary Clarity surface):**
- **Microsoft Copilot (M365)** — Embedded across the PM daily workflow: Teams (meeting summaries, action items), Word (PRD drafting), Outlook (email-to-spec conversion), and Loop (collaborative planning). Draws on organizational context via Microsoft Graph, meaning it already knows what the team has discussed, decided, and committed to. $30/user/mo add-on to E3/E5/Business plans. Strategically the most natural home for Clarity's light expression — if the protocol can be surfaced as Copilot context, every PM in a Microsoft org gets it without changing tools [3][4].
- **ChatGPT / Custom GPTs** — Most widely used AI assistant among PMs (~49% regular use for coding-adjacent tasks, broader for general PM work). Largest plugin ecosystem (Jira, Asana, Slack, Zapier integrations). Custom GPTs allow persistent instructions and knowledge files. Strong generalist for brainstorming, drafting, and synthesis. Session-centric — persistent context weaker than Claude Projects [5][6].
- **Claude Projects** — Best persistent workspace context: remembers project state across sessions, ideal for long-running product work spanning months. Up to 1M tokens in enterprise editions. MCP supported natively. Portable Skills system. Favored for regulated industries, compliance documentation, and deep multi-document analysis [5][7][8].
- **Notion AI** — Fastest-growing PM documentation tool (35% YoY adoption growth among PMs). AI operates directly on live Notion workspace content — specs, research trackers, meeting notes, project timelines. Emerging MCP support via Notion MCP server. The "all-in-one" nature makes it attractive as a single surface where Clarity's output and the PM's working docs coexist [2][9].
- **Google Gemini (Gems/Workspaces)** — Tight Google Workspace integration (Gmail, Drive, Docs, Sheets, Meet). 1M-token context window. Natural fit for Google-ecosystem organizations. Gems are easy to build but less extensible than Claude Skills or ChatGPT GPTs. Growing fast but limited outside the Google stack [7][10].

**Collaboration platforms (where Clarity output must land):**
- **GitHub Issues / Projects** — The engineering handoff surface in the Microsoft/GitHub ecosystem. Where PM specs become engineering work items. Strategically critical for the "protocol as handoff contract" integration point: if the PM produces `.clarity-protocol/` in a GitHub repo, the engineer's coding agent consumes it natively. The shortest path from PM thinking to engineer context.
- **Jira + Confluence** — Enterprise standard for engineering alignment (300K+ companies worldwide). Where the PM-to-engineering handoff happens in Atlassian shops. Confluence is the dominant structured documentation platform in enterprises [11][12].
- **Notion** — Doubles as both AI thinking partner (via Notion AI) and collaboration platform. PMs and engineers share the same workspace. The challenge: getting `.clarity-protocol/` artifacts *out* of Notion and into a repo [2][9].
- **Linear** — Surging in startups (<500 employees), overtaking Asana as the #2 issue tracker in fast-moving tech teams. Engineering-focused design makes it a natural handoff surface for technically-oriented PMs [11][13].
- **Azure DevOps** — Microsoft's enterprise project management and engineering platform. Relevant for organizations deeply invested in the Azure ecosystem, particularly where compliance and enterprise controls matter.

| Integration point | User experience | Clarity value delivered | Risks |
|---|---|---|---|
| Light expression as project knowledge | AI thinking partner pushes back on vague specs, surfaces missing stakeholders, demands testable criteria | Full Clarity disposition — challenging questions, structured thinking — with zero tooling setup | No persistence between sessions; PM must manually carry context forward; no staleness tracking |
| MCP server (MCP-capable AI tools) | Full staleness tracking and structured protocol output inside the PM's preferred AI tool | Persistent, tracked protocol that evolves with the project; same infrastructure engineers get | Requires PM to use an MCP-capable tool; adds complexity that may not match PM workflow expectations |
| Protocol as handoff contract | PM produces `.clarity-protocol/`; engineer's coding agent consumes it as build context | Eliminates the spec-to-implementation translation gap; shared artifact surfaces misalignment *before* code | Protocol can diverge if PM and engineer edit independently; needs merge/conflict conventions; PM may resist working in a repo |

### Tool compatibility (AI thinking partners)

| Integration point | Microsoft Copilot (M365) | Claude Projects | ChatGPT / Custom GPT | Notion AI | Google Gemini |
|---|---|---|---|---|---|
| Light expression | ⚠️ Copilot agents/instructions | ✅ Project knowledge | ✅ GPT instructions | ✅ Workspace AI context | ✅ Gems instructions |
| MCP server | ❌ No MCP (Microsoft Graph / REST) | ✅ MCP supported | ❌ No MCP (REST/Actions only) | ⚠️ Emerging via Notion MCP | ❌ No MCP (Google APIs only) |
| Protocol as handoff | ✅ GitHub integration via Copilot | ✅ If PM saves to repo | ✅ If PM saves to repo | ⚠️ Notion-to-repo export needed | ⚠️ Docs-to-repo export needed |

### Tool compatibility (collaboration platforms)

| Integration point | GitHub Issues/Projects | Jira + Confluence | Notion | Linear | Azure DevOps |
|---|---|---|---|---|---|
| Protocol as handoff | ✅ Native (`.clarity-protocol/` in repo) | ⚠️ Requires Jira-to-repo sync or Confluence export | ⚠️ Notion-to-repo export needed | ⚠️ Requires Linear-to-repo sync | ✅ Native (Azure Repos) |
| Clarity-aware automation | ✅ GitHub Actions can validate protocol | ⚠️ Jira automation or Forge app needed | ❌ No equivalent | ❌ No equivalent | ✅ Azure Pipelines can validate protocol |

**The gap:** The PM tool landscape is fundamentally fragmented. Claude Projects is the only AI thinking partner with native MCP support — the rest require REST adapters, plugin architectures, or platform-specific integration work. Microsoft Copilot is strategically the most important surface for Clarity's PM story but has no MCP; reaching it requires building a Copilot agent or plugin that wraps Clarity's capabilities. ChatGPT's Actions model and Notion's emerging MCP support are mid-term paths, while Google Gemini remains the hardest to reach from outside the Google ecosystem.

For collaboration platforms, the GitHub/Azure DevOps ecosystem has the shortest path: `.clarity-protocol/` lives in the repo, GitHub Actions validates it, and the engineer's coding agent reads it natively. Every other platform requires bridging artifacts out of the PM's tool and into a repo — a manual step that the "protocol as handoff contract" depends on but few PMs will do unprompted.

**The Microsoft Copilot opportunity:** Copilot M365 is where PMs in Microsoft-ecosystem organizations already live — Teams meetings, Word docs, Outlook threads. If Clarity can surface as a Copilot agent or plugin, the light expression (challenging questions, structured thinking) reaches PMs without requiring them to adopt any new tool. The handoff then flows naturally through GitHub: Copilot-assisted PM produces `.clarity-protocol/` → pushes to GitHub repo → engineer's coding agent (also Copilot-powered) consumes it. This is the tightest end-to-end Clarity story across both personas.

### Sources (Section 2)

1. "25 Best AI Tools for Product Managers in 2026" — blog.buildbetter.ai/best-ai-tools-for-product-managers-2026
2. "50+ Product Management Statistics" — ideaplan.io/blog/product-management-statistics-2026
3. "Microsoft Copilot for M365 Enterprise Deployment Guide 2026" — epcgroup.net/microsoft-copilot-enterprise-deployment-guide-2026
4. "How to Deploy Microsoft 365 Copilot: IT Admin Guide 2026" — itecsonline.com/post/how-to-deploy-microsoft-365-copilot-it-admin-guide-2026
5. "ChatGPT vs Claude for Product Managers: An Honest Comparison (2026)" — pmthebuilder.com/blog/blog-chatgpt-vs-claude-for-product-managers
6. "AI Tools Compared: ChatGPT vs Claude vs Gemini vs Copilot (2026)" — fieldguidetoai.com/guides/ai-tools-comparison-guide
7. "Custom GPTs, Gems & Claude Projects: Full 2026 Guide" — stackviv.ai/blog/custom-gpts-gems-claude-projects
8. "Claude Skills vs Gemini Gems vs ChatGPT GPTs: Which One Wins?" — findskill.ai/blog/claude-skills-vs-gemini-gems-vs-chatgpt-gpts
9. "Notion MCP: How to Connect ChatGPT, Claude, and Gemini to Your Workspace" — papersflow.ai/blog/notion-mcp-guide-chatgpt-claude-gemini
10. "ChatGPT vs Claude vs Gemini: 2026 Complete Comparison Guide" — novaedgedigitallabs.tech/Blog/chatgpt-vs-claude-vs-gemini-2026-comparison
11. "Linear vs Jira 2026: The Definitive Comparison" — tech-insider.org/linear-vs-jira-2026
12. "The 16 Best Product Management Tools in 2026" — feedough.com/startup-resources/best-product-management-tools
13. "Best AI Tools for Product Managers (2026 Guide)" — prodmgmt.world/blog/ai-for-product-managers

---

## 3. Professional Engineers — Coding Companions

These users are already in a coding agent. They know what they're building (usually). The gap is that architectural decisions get made implicitly, failure modes don't get examined, and six months later nobody remembers why something was built a certain way.

**Where they are**, ordered by strategic relevance (Microsoft/GitHub ecosystem weighted) and adoption among professional engineers:

Over 73% of engineering teams now use AI coding tools daily, up from 41% in 2025. Most developers combine 2–4 tools, using IDE-integrated assistants for routine completion and agentic tools for complex tasks [1][2]. Engineers operate across two layers: AI-powered coding environments (where they write and refactor code) and team alignment surfaces (where they review, coordinate, and ship). Clarity's integration points primarily target the coding environment — but its PR review, deploy gates, and protocol artifacts must land in the team alignment layer.

**AI-powered coding environments (primary Clarity surface):**

- **GitHub Copilot** — The most widely adopted AI coding tool: 76% awareness, 29% workplace usage globally, rising to 40% in large enterprises (5,000+ employees). 4.7M paid subscribers, deployed by 90% of Fortune 100 companies. Leads for routine code completion (51% of AI-assisted completions). Broadest IDE support (VS Code, JetBrains, Visual Studio, Neovim). Strategically the anchor: GitHub Copilot + VS Code (72–76% market share, 14M+ active users) is the most common professional coding setup. Full MCP support via agent mode. Rules files via `.github/copilot-instructions.md` [1][2][3][4].
- **Cursor** — The leading AI-native IDE: 69% awareness, 18% workplace usage, $2B+ ARR, 1M+ active users. VS Code fork with deep multi-file context (Composer mode), codebase indexing, and agentic workflows. Especially popular with startups and power users. Full MCP support, rules files via `.cursorrules` [1][2][5].
- **Claude Code** — Tied with Cursor at 18% workplace usage, but rated "most loved" by 46% of developers (vs. Cursor's 19%, Copilot's 9%). Terminal-native agentic tool that leads for complex engineering tasks: 44% of developers doing multi-file refactoring, architecture work, or debugging choose Claude Code over alternatives. Full MCP support, Skills system, rules via `AGENTS.md`/`CLAUDE.md` [1][2][5][6].
- **Windsurf** — Budget-friendly AI IDE (free/$15/mo). Growing beginner and hobbyist audience. Agentic "Cascade" mode. Supports the same extensibility primitives as Cursor (MCP, rules files via `.windsurfrules`), making it the easiest Clarity integration port after Cursor [7][8].
- **Cline** — Free BYOK (Bring Your Own Key) VS Code extension. Advanced agentic multi-file changes. MCP supported natively. Popular among power users who want AI coding without IDE lock-in. Quality depends on the chosen LLM [9][10].
- **Zed** — Performance-focused editor gaining momentum. Built-in MCP support with prompts surfaced as slash commands. Growing AI integration story but less mature than Cursor or Claude Code [11][12].
- **JetBrains AI Assistant** — 32% awareness, 9% workplace usage. IDE-native within the JetBrains ecosystem (IntelliJ, PyCharm, WebStorm — 11M+ users, 88% of Fortune Global 100). Now has full MCP support via AI Assistant plugin. Rules files depend on the agent. Dominant for Java/Kotlin (84% of Java developers use IntelliJ) and Python (PyCharm) [1][13][14].
- **Aider** — Terminal-based, git-native, open source. Similar niche to Claude Code. No direct MCP support, but reads project configuration and composes well with other tools in terminal workflows. Niche but influential among CLI power users [9][10].

**Enterprise and platform-specific tools** (significant adoption in specific ecosystems):

- **Google Gemini Code Assist** — ~23% of developers have tried it. Growing in Google Cloud organizations. Works through VS Code and JetBrains plugins that already support MCP, so Clarity's MCP server reaches it without tool-specific work [1][15].
- **Amazon Q Developer** — ~15% of developers have tried it. Dominant in AWS shops. Has its own "Review" and "Dev" agent model. Limited MCP support; deploy gate and PR review are the most reliable Clarity integration points [1][4][16].
- **Augment Code** — Enterprise niche. Semantic dependency engine across 400K+ file monorepos. Multi-repo analysis could complement Clarity's staleness tracking. Worth monitoring for partnership potential [10].
- **Sourcegraph Cody** — Enterprise code intelligence. Deep cross-repo search and pattern enforcement. Some MCP support. Enterprise pricing (~$66K/yr). Watch list [16].
- **Tabnine** — Privacy-sensitive enterprise niche. On-prem/local LLM deployment for compliance-driven organizations. Limited extensibility; Clarity's infrastructure-layer integrations (deploy gates, PR review) are the only viable surface [15].

**Team alignment and code review (where Clarity's PR review and deploy gates land):**

- **GitHub** — 100M+ developers, 420M+ repositories. Pull request workflows are the universal code review standard. GitHub Actions provides the CI/CD automation layer. Strategically the most important team surface for Clarity: PR review bots, deploy gates, and protocol validation via Actions all operate here natively. Human-reviewed PRs see 84.4% acceptance vs. 32.7% for AI-generated PRs — quality gates are increasingly important as AI-generated code grows [17][18].
- **Microsoft Teams** — 300M+ monthly active users. Favored by organizations in the Microsoft 365 ecosystem. Deep integration with Outlook, security/compliance. Where engineering teams in Microsoft-ecosystem orgs discuss, plan, and coordinate [19].
- **Slack** — Preferred messaging tool for engineering teams, particularly in startups and tech companies. Vast integration ecosystem (GitHub PR notifications, deploy alerts, Jira/Linear status updates). Channel-based async communication is the engineering team default [19].
- **Jira** — Enterprise standard for issue tracking and sprint management (300K+ companies). Where engineering work items live in Atlassian shops. Clarity's protocol-as-handoff integrates here via Jira-to-repo sync or Confluence documentation [20].
- **Linear** — Surging adoption in startups (<500 employees). Engineering-focused UX with deep GitHub integration (PR links, deployment tracking). Natural handoff surface for teams that have moved beyond Jira [20][21].
- **Azure DevOps** — Microsoft's enterprise engineering platform. Boards, Repos, Pipelines. Relevant for orgs deeply invested in Azure, particularly where compliance matters. Protocol validation via Azure Pipelines mirrors the GitHub Actions story.

**Design principle:** Clarity produces decisions that stick and failures that are managed. The protocol lives in the repo, version-controlled, and the coding agent reads it as context. The engineer's workflow doesn't change — the agent just gets smarter about when to pause and think.

| Integration point | User experience | Clarity value delivered | Risks |
|---|---|---|---|
| Rules file (`AGENTS.md`, `.cursorrules`) | Agent triggers clarity processes at architectural decision points — not constantly, but at natural inflection moments | Structured thinking embedded in existing workflow; decisions get documented as they happen | Agent may misjudge when to trigger (too often → annoying, too rare → missed decisions); rules vary across tools |
| MCP server | Full infrastructure via tool calls — `check_staleness()`, `record_decision()`, `run_thinker()` — without leaving editor | Highest-fidelity integration; the complete Clarity process as composable tools | Heaviest dependency; requires MCP server running; adds latency to agent interactions |
| Slash commands (`/clarity`, `/fail-check`, `/decide`) | Quick-access focused operations; `/fail-check` on current feature, `/decide` to capture a choice with alternatives | Low-friction entry to specific Clarity capabilities; user controls depth and timing | Fragmented experience — user must know which command to use; may not discover the full process |
| PR review (GitHub Action/bot) | Surfaces protocol staleness against code changes: "this PR changes auth but architecture doc is stale" | Catches drift between thinking and building in the review flow where the team is already looking | Can become noisy on active codebases; staleness doesn't always mean the protocol is *wrong*; alert fatigue |
| IDE extension (VS Code panel) | Protocol sidebar: problem, requirements, failures, decisions — glanceable while coding | Persistent visibility of *why* this is being built; reduces context-switching to understand project intent | Passive — doesn't prompt action; risks becoming furniture the engineer stops seeing |
| Post-incident integration | Reads postmortem, checks: was this failure known? What happened to the management plan? | Closes the planning-to-reality loop; makes failure analysis feel consequential, not theoretical | Requires postmortem discipline that many teams lack; risk of blame-framing if not positioned carefully |

### Tool compatibility

| Integration point | Claude Code | Cursor | Windsurf | Cline | Zed | Copilot | VS Code | JetBrains |
|---|---|---|---|---|---|---|---|---|
| Rules file | ✅ `AGENTS.md` | ✅ `.cursorrules` | ✅ `.windsurfrules` | ⚠️ Reads project context | ⚠️ Limited | ✅ `.github/copilot-instructions.md` | ⚠️ Depends on agent | ⚠️ Depends on agent |
| MCP server | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Slash commands | ✅ Skills | ⚠️ Tool-specific | ⚠️ Tool-specific | ❌ No equivalent | ✅ MCP prompts as slash commands | ❌ No equivalent | ⚠️ Depends on agent | ⚠️ Depends on agent |
| PR review | ✅ Tool-agnostic | ✅ Tool-agnostic | ✅ Tool-agnostic | ✅ Tool-agnostic | ✅ Tool-agnostic | ✅ Tool-agnostic | ✅ Tool-agnostic | ✅ Tool-agnostic |
| IDE extension | N/A (terminal) | ⚠️ Needs Cursor extension | ⚠️ Needs Windsurf extension | N/A (is a VS Code extension) | ⚠️ Extension ecosystem maturing | N/A | ✅ VS Code extension | ⚠️ Separate plugin |
| Post-incident | ✅ Tool-agnostic | ✅ Tool-agnostic | ✅ Tool-agnostic | ✅ Tool-agnostic | ✅ Tool-agnostic | ✅ Tool-agnostic | ✅ Tool-agnostic | ✅ Tool-agnostic |

**MCP status update (April 2026):** The MCP landscape has shifted significantly since the initial draft. Copilot, VS Code, and JetBrains all now have full MCP support — VS Code via native integration and MCP Apps [9], JetBrains via the AI Assistant plugin [10], and Copilot via its agent mode. Cline and Zed also support MCP natively [11][12]. This means **every major professional engineering tool now supports MCP** [11][12], making the "MCP as universal connector" thesis substantially stronger than when this document was first drafted.

### Terminal agents: Aider and the Claude Code pattern

**Aider** occupies a similar niche to Claude Code — terminal-based, git-native, open source, favored by CLI power users. It doesn't support MCP directly, but it reads project configuration and can be composed with other tools in a Unix-pipeline style. Since Aider users are likely to also use Claude Code or Cursor, the Clarity integration story reaches them indirectly. Not worth a dedicated integration effort, but worth ensuring the rules-file and protocol-as-repo-artifact approaches work for terminal-first workflows.

### Enterprise and platform-specific coding companions

Several tools have significant professional adoption but operate in distinct ecosystems that may need tailored approaches:

| Tool | Adoption | Extensibility for Clarity | Strategic note |
|---|---|---|---|
| **Google Gemini Code Assist** | ~23% of devs [1] | ✅ Works through VS Code/JetBrains plugins that support MCP — Clarity's MCP server is accessible without tool-specific work [9][10] | Growing fast in Google Cloud orgs. No dedicated integration needed; the MCP server strategy covers it automatically via IDE plugins. |
| **Amazon Q Developer** | ~15% of devs [1][4] | ⚠️ Limited MCP; has its own "Review" and "Dev" agent model [4][8] | Dominant in AWS shops. Deploy gate and PR review (tool-agnostic) are the most reliable integration points. Deeper integration would require Amazon-specific adapter work. |
| **Augment Code** | Enterprise niche [6] | ⚠️ Enterprise API; extensibility model TBD | Semantic dependency engine across 400K+ file codebases [6]. Their multi-repo analysis could complement Clarity's staleness tracking. Worth monitoring for partnership potential. |
| **Sourcegraph Cody** | Enterprise niche [8] | ⚠️ Some MCP support; primarily its own extension model | Deep cross-repo code intelligence. Enterprise pricing (~$66K/yr) [8]. Cody's pattern-awareness could surface where Clarity processes should trigger. Watch list. |
| **Tabnine** | Privacy-sensitive orgs [5] | ❌ Limited extensibility; focus is on completion, not agentic workflows | Important for enterprises that can't use cloud-based AI tools. Clarity's deploy gate and PR review (infrastructure-layer) are the only viable integration points. |

### Sources (Section 3)

1. "Which AI Coding Tools Do Developers Actually Use at Work?" — blog.jetbrains.com/research/2026/04/which-ai-coding-tools-do-developers-actually-use-at-work (JetBrains Developer Survey, April 2026)
2. "Developer Survey 2026: AI Coding Tool Adoption Hits 73%" — claude5.ai/news/developer-survey-2026-ai-coding-73-percent-daily
3. "Top 100 AI Pair Programming Statistics 2026: GitHub Copilot Adoption" — index.dev/blog/ai-pair-programming-statistics
4. "Best AI Coding Assistants as of March 2026" — shakudo.io/blog/best-ai-coding-assistants
5. "GitHub Copilot vs Cursor vs Claude Code: The 2026 AI Coding Showdown" — groundy.com/articles/github-copilot-vs-cursor-vs-claude-code-2026-ai-coding
6. "Claude Code vs Cursor vs GitHub Copilot: The 2026 AI Coding Tool Showdown" — dev.to/alexcloudstar/claude-code-vs-cursor-vs-github-copilot
7. "AI Coding Assistants Complete Guide 2026: Devin, Cursor, Windsurf and More" — calmops.com/ai/ai-coding-assistants-2026-complete-guide
8. "Vibe Coding Tools Compared: 13 Tools Tested (2026)" — buildwithabid.com/blog/vibe-coding-tools-compared-2026
9. "14 Best AI Coding Agents in 2026, Ranked by Benchmarks and Real Usage" — morphllm.com/best-ai-coding-agents-2026
10. "Best AI Coding Agents: 9 Tools Compared for Every Developer Type" — agentsindex.ai/blog/best-ai-coding-agents
11. "Clients – Model Context Protocol" — modelcontextprotocol.io/clients
12. "MCP I Use - MCP Client Compatibility Tables" — mcpiuse.com
13. "Model Context Protocol (MCP) | JetBrains AI Assistant Documentation" — jetbrains.com/help/ai-assistant/mcp.html
14. "VS Code vs JetBrains IntelliJ Statistics – Which is Better?" — coolest-gadgets.com/vs-code-vs-jetbrains-intellij-statistics-which-is-better-2025
15. "Top 10 AI Coding Assistants of 2026" — analyticsvidhya.com/blog/2026/03/ai-coding-assistants
16. "Amazon Q Developer vs Sourcegraph Cody: AWS Integration vs. Multi-Repo Intelligence" — augmentcode.com/tools/amazon-q-developer-vs-sourcegraph-cody
17. "Best Tools to Automate Pull Requests and Code Review in 2026" — codeant.ai/blogs/top-pull-request-automation-tools
18. "Best GitHub Code Review Platforms (2026 Snapshot)" — propelcode.ai/blog/best-github-code-review-platforms-2026
19. "15 Best Team Collaboration Software Tools in 2026 (Expert-Tested)" — guideflow.com/blog/team-collaboration-software-tools
20. "23 Best Software Development Collaboration Tools in 2026" — thedigitalprojectmanager.com/tools/best-software-development-collaboration-tools
21. "Linear vs Jira 2026: The Definitive Comparison" — tech-insider.org/linear-vs-jira-2026

---

## Cross-Cutting: The Composability Model

### Shared infrastructure

All three personas share:

- **Protocol format as the interop layer.** What a PM produces in Claude, an engineer consumes in Cursor, and a CI gate validates in GitHub Actions. The `.clarity-protocol/` directory is the contract.
- **Graduated depth.** Checklist → focused analysis → full process. Every integration starts light and goes deeper on demand.
- **MCP as the universal connector.** One server, many clients. The same `run_thinker()` call works whether invoked by a PM in Claude, an engineer in Cursor, or a CI bot in GitHub Actions.

### Risk patterns

Three recurring risks cut across all personas:

**The discoverability paradox.** The personas who need Clarity most (citizen devs) are least likely to invoke it voluntarily. Integrations that don't require invocation (rules files, deploy gates) deliver less depth. The context-aware linter/conversation toggle is the key mechanism — maximize depth at the moments the system *detects* depth is needed.

**Alert fatigue is the recurring threat.** Rules files, deploy gates, PR review bots, and staleness tracking all risk becoming noise. The graduated depth model has to be genuinely selective, not just graduated in theory.

**Persistence is the PM gap.** The light expression is the fastest path to PMs, but without persistence it's a thinking tool that forgets. MCP closes this gap but adds friction. A lightweight export/import convention may be a middle ground.

### Compatibility reality

The extensibility primitives are more universal than initially assumed — particularly for professional engineers. Four observations:

1. **The most "vibe coder" tools are the most closed.** Bolt, Lovable, Replit, and v0 support almost none of the primitives (rules files, MCP, skills). The citizen developer strategy has real holes for these platforms.
2. **MCP has become near-universal for professional tools.** As of April 2026, Claude Code, Cursor, Windsurf, Cline, Zed, Copilot, VS Code, and JetBrains all support MCP. Google Gemini Code Assist inherits MCP support through its VS Code/JetBrains plugins. The "MCP as universal connector" thesis is now the strongest integration strategy for professional engineers — build one MCP server and reach the vast majority of the market.
3. **Tool-agnostic integrations remain the most reliable.** Deploy gates, PR review, and post-incident all work everywhere because they operate at the CI/infrastructure layer, not inside the editor. This is critical for reaching tools that don't support MCP (Amazon Q, Tabnine) and autonomous agents (Devin) where it may be the *only* viable surface.
4. **Autonomous agents break the intervention model.** Devin and similar tools remove the human from the loop entirely. The current strategy assumes a person sees the speed bump. For autonomous agents, Clarity must either be a mandatory tool call (MCP agent-to-agent) or a hard deploy gate. This is an unsolved design problem.
5. **Enterprise tools need infrastructure-layer integration.** Augment Code, Sourcegraph Cody, Tabnine, and Amazon Q each have their own extensibility models or limited extensibility. Trying to build adapters for each is not viable. The deploy gate, PR review, and protocol-as-repo-artifact strategies reach these tools without tool-specific work.

### Tool prioritization criteria

The tool landscape for Sections 1 and 3 was surveyed in April 2026. Each tool was assessed against five criteria to determine its relevance to the Clarity integration strategy:

1. **Developer adoption.** How many people are actually using this tool? Widely-adopted tools are worth investing in; niche tools may not justify dedicated integration work. Adoption data is drawn from developer surveys and industry reports where available, and from qualitative market positioning where hard numbers don't exist.
2. **Extensibility surface.** Does the tool support the primitives Clarity needs — MCP, rules files, skills/slash commands? Tools with strong extensibility can be reached by the same MCP server and rules files; closed ecosystems require fundamentally different (and more expensive) approaches.
3. **Risk surface.** Does the tool produce software that faces real users — handling auth, payments, user data, external APIs? Tools that generate throwaway prototypes are lower priority than tools whose output gets deployed to production.
4. **Effort-to-reach ratio.** How much Clarity-specific work is needed to integrate, relative to how many users it reaches? A tool that supports MCP natively costs almost nothing to reach. A closed-ecosystem tool that requires a custom adapter may not be worth the investment unless adoption is very high.
5. **Unique strategic relevance.** Does the tool represent a new category or challenge that the current integration strategy doesn't address? Autonomous agents (Devin) and enterprise-scale tools (Augment Code) may have low individual adoption but force important design questions.

---

## Open Questions

- How does the context-aware linter/conversation toggle work mechanically? Is it a disposition in the rules file, or does the MCP tool return metadata that the agent interprets?
- What's the minimum viable MCP server surface? Which tools does it need to expose for the citizen developer use case vs. the full engineering use case?
- How do we handle protocol format as a handoff contract when the PM and engineer are in different tools? What happens when the PM's protocol and the engineer's protocol diverge?
- Should the deploy gate be a Clarity product, or should Clarity produce artifacts that existing deploy gates (GitHub Actions, etc.) can consume?
- What's the right relationship between the light expression (for PMs) and the rules-file expression (for vibe coders)? Are these two different Layer 2 derivations, or is the vibe-coder surface a subset of the light expression?
- How do we reach citizen developers on closed-ecosystem platforms (Bolt, Lovable, Replit, v0) that don't support the extensibility primitives?
- How does Clarity intervene in fully autonomous agent workflows (Devin, Emergent) where no human is in the loop? Is MCP agent-to-agent viable, or is a hard deploy gate the only realistic surface?
- With MCP now supported across nearly all professional engineering tools, should the MCP server be the primary investment over rules files and slash commands?
- How should Clarity handle enterprise tools with limited extensibility (Amazon Q, Tabnine, Augment Code)? Is protocol-as-repo-artifact sufficient, or do these tools need platform-specific adapters?
- As GitHub Spark and Firebase Studio mature, do they open new integration paths via their parent platforms (GitHub Actions, Google Cloud Build)?

### How to think about autonomous agents

**Devin** and similar fully autonomous AI engineers (e.g., Emergent) represent a category your current intervention model doesn't address [3][7]. These systems plan, implement, test, and deploy with minimal or no human in the loop. The core assumption — that a human sees the checklist or speed bump — breaks down entirely.

For autonomous agents:
- **Rules files and skills are irrelevant** — there's no human to invoke them or read the output.
- **Deploy gates become the primary (possibly only) integration point.** The gate must be hard enough to block deployment, not just warn.
- **MCP as an agent-to-agent channel** may work if the autonomous agent supports tool calls — Clarity becomes a tool the agent *must* consult, not one a human chooses to invoke. This is speculative; Devin's extensibility model is still maturing.
- **The risk profile is uniquely high.** Autonomous agents can ship entire applications in hours. If Clarity can't intervene, the "no security instinct" problem scales dramatically.

## Added thoughts on integration points
### Why MCP matters alongside REST

MCP is what makes Clarity a *thinking partner* inside the coding agent rather than an external service the developer must remember to consult. The existing REST API is powerful but invisible to the agent's reasoning loop. MCP makes it visible:

| | REST API | MCP Server |
|---|---|---|
| **Who calls it** | GitHub Actions, ChatGPT Actions, Copilot M365 plugins, Notion integrations, CI/CD, any webhook | AI coding agents (Copilot, Cursor, Claude Code, Windsurf, Cline, Zed) |
| **How it's discovered** | Documentation, manual configuration | Auto-discovered by the agent — tools, schemas, and descriptions appear natively in the agent's available capabilities |
| **How it's invoked** | HTTP requests constructed by code or plugins | Agent calls tools as part of its reasoning loop — no human constructs anything, no glue code required |
| **Context passing** | Explicit in request payload | Implicit — the agent passes what it's working on (current file, user intent, project state) naturally |
| **Build cost** | Already exists | Thin translation layer over the REST API |

The MCP server doesn't replace the REST API — it's a facade over it. Every MCP tool call (`clarity_check()`, `record_decision()`, etc.) delegates to the existing REST API under the hood. This means the architecture can consolidate around a single REST API backend.

Example for future integration points:

```
REST API (core — already exists)
  ├── MCP Server (thin adapter → AI coding agents)
  ├── GitHub Action (direct REST calls → CI/CD safety net)
  ├── ChatGPT Action (direct REST calls → PMs)
  ├── Copilot M365 plugin (REST via Graph → PMs)
  └── Rules files (trigger the agent to call MCP, which calls REST)
```

**Opportunities the REST API opens for PM tools.** Because the REST API already exists, several previously dismissed PM integration points become significantly cheaper:

- **ChatGPT Custom GPT / Actions** — ChatGPT Actions *are* REST calls. Building a ChatGPT Action becomes configuration, not engineering. PMs using ChatGPT get Clarity for near-zero additional cost.
- **Copilot M365 agent/plugin** — Copilot plugins call REST APIs via Microsoft Graph. The existing API is most of the work. The highest-strategic-value PM integration is now feasible as a near-term follow-on.
- **Notion integrations** — Notion automations can call webhooks/REST. A Notion-to-Clarity bridge becomes possible without a dedicated adapter.

These don't change the recommendation, but they shorten the path to PM tools from "requires dedicated platform-specific engineering" to "requires configuration and a thin wrapper."

### Other integration points considered

The following integration approaches were evaluated during the strategy process. Each has merit and may be worth revisiting as the landscape evolves.

| Integration point | Reach | Alignment with Clarity's core value | Gaps / drawbacks |
|---|---|---|---|
| **GitHub Actions / PR review bot** | Universal — every tool, every persona, including closed ecosystems (Lovable, Bolt, Replit) and autonomous agents (Devin) | ⚠️ Low. Only activates at PR review and deploy time. Users don't get Clarity's thinking partnership during the building — they get a flag after the fact. | Reactive, not generative. Can't walk the user through ambiguity or evolve the protocol. Risks becoming a checkbox people dismiss. Valuable as a future complement but can't carry the core experience. |
| **Copilot M365 agent/plugin** | PMs in Microsoft orgs (Teams, Word, Outlook) — strategically the highest-value PM surface | ✅ High. Could deliver Clarity's conversational thinking partnership where PMs already work — challenging vague specs, surfacing missing stakeholders, producing protocol artifacts. | PM toolchain too fragmented to justify as the lead investment. No MCP support — requires building a Copilot plugin. REST API makes this cheaper as a follow-on. |
| **VS Code extension (protocol sidebar)** | Engineers in VS Code (72–76% market share) | ⚠️ Low. Passive display — shows protocol state but doesn't prompt action or intervene during reasoning. Users must choose to look at it. | Risks becoming furniture the engineer stops seeing. The Rules + MCP approach actively intervenes at decision moments; a sidebar adds visibility but not the partnership. |
| **ChatGPT Custom GPT / Actions** | PMs using ChatGPT (~49% regular AI use among PMs) | ✅ High. ChatGPT's conversational interface is a natural fit for Clarity's thinking partnership. Users could work through ambiguity, challenge assumptions, and produce protocol artifacts. | No MCP — requires REST/Actions adapter. Session-centric (no persistent project context). REST API makes this near-zero cost to build if PM reach becomes a priority. |
| **Slash commands (`/clarity`, `/fail-check`)** | Engineers in Claude Code (Skills), partial in Cursor/Windsurf | ⚠️ Medium. Right depth when invoked, but requires the user to know commands exist and choose to use them. Citizen devs — the persona who needs Clarity most — won't discover or invoke these. | The MCP server already exposes the same capabilities as tool calls. Rules files trigger them automatically, removing the discoverability problem. Slash commands add nothing the Rules + MCP approach doesn't already deliver. |
| **Notion AI / Notion MCP** | PMs using Notion (fastest-growing PM doc tool, 35% YoY growth) | ✅ High. Clarity's output and the PM's working docs could coexist in one workspace. AI operates on live content — specs, research, timelines. | MCP support is immature (community server). Notion's audience skews toward PMs, not the developer personas where the initial strategy focuses. Worth revisiting as Notion's MCP story matures. |
| **Google Gemini Gems** | PMs in Google Workspace orgs | ⚠️ Medium. Gems can host persistent instructions but lack the deep conversational back-and-forth that Clarity's thinking partnership requires. | No MCP, limited extensibility outside Google stack. Single-ecosystem audience. Would require a Google-specific adapter. |
| **Post-incident integration** | Universal (reads postmortems from any source) | ⚠️ Low. Activates after the damage is done. Checks whether failures were anticipated, but can't help the user think through them in the moment. | Requires postmortem discipline many teams lack. Risk of blame-framing. Closes a feedback loop but doesn't deliver the core experience of being present during building. |
| **Closed-platform adapters (Lovable, Bolt, Replit)** | Citizen devs on the highest-risk vibe coding platforms | ✅ High if achievable. These are the users who need Clarity most — shipping production software with no security instinct. | None of these tools support MCP, rules files, or any extensibility primitive. Would require reverse-engineering proprietary APIs or negotiating partnerships. Effort-to-reach ratio is poor, and without MCP the core experience (agent-native reasoning partnership) can't be delivered. |
| **Devin / autonomous agent MCP** | Autonomous AI engineers (Devin, Emergent) | ✅ High if achievable. Agent-to-agent MCP would make Clarity a tool Devin *must* consult — the right model for a workflow with no human in the loop. | Devin's extensibility model is still maturing. The design problem (intervening in a fully autonomous workflow without a human to hold the conversation) is unsolved. Speculative but worth monitoring. |
