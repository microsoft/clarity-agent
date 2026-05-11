## Turn 1

**User:**
Hey — I want to spec out a tool for my engineering team. Basically a lightweight dashboard where everyone can see what each person is working on. I've got some wireframes already, so I'm not starting from scratch — I just want to nail down the design: what fields to show, how data gets in, permissions model, that kind of thing. Can you help me get this to something buildable?

**Assistant:**
Good context — let me capture this and ask a few targeted questions so we can move fast.A few questions to lock in the design:

1. **Data source** — Where does work data live today? JIRA, Linear, GitHub issues, or are people expected to enter things manually?

2. **The "what I'm working on" field** — What do the wireframes show per person? (e.g., one active item? A short list? A status + sprint goal + blockers?) What's under debate?

3. **Permissions** — Who sees this dashboard? Just the team itself, or broader (managers, other teams, the whole company)? And can people edit each other's entries, or only their own?

4. **Team size and shape** — Roughly how many people, and is this one team or multiple teams?

## Turn 2

**User:**
Good questions. Quick answers:

1. We use Jira, but honestly people don't keep it up to date — it's aspirational at best. So yes, I'm expecting manual entry, at least to start. Maybe we pull in Jira ticket numbers as a reference, but the actual status text would be hand-entered.

2. Wireframes show one "primary focus" item per person (free text, ~140 chars), a status dropdown (on track / blocked / in review), an optional blockers field, and a "last updated" timestamp. Maybe a secondary item slot but that felt like scope creep.

3. Team sees full detail. My VP and other managers get read access — that's actually a big motivator, I want to be able to pull this up in exec reviews without scrambling. No cross-team editing, people own their own rows.

4. Seven engineers, one team. But I'd want it to be usable if we ever split or I pick up another team.

**Assistant:**
Solid. I have enough to write the core documents. Let me do that, then flag the remaining questions that would actually block a builder.Now the open questions that would actually block a builder:Good — documents are written. Three open questions to close before this is truly buildable:

**Q1: Auth** — Does your team use Google Workspace, GitHub, or something else for shared identity? That's almost certainly the right OAuth provider. Or is this internal enough that you'd just want an admin to set up accounts manually?

**Q2: Multi-team layout** — When you imagine picking up a second team: do you picture a separate dashboard for each team (you tab between them), or one big board where both teams appear with a divider? The second is simpler to build and better for cross-team visibility; the first gives cleaner separation.

**Q3: Staleness** — Just show the timestamp and let humans notice? Or should rows visually dim/warn after, say, 3 days without an update? (The nudge version is a bit more engineering but also more honest about the tool's purpose.)

## Turn 3

**User:**
Google Workspace for auth, easy call.

Multi-team: one board with a divider. Less fuss and honestly I'd want to see cross-team blockers anyway.

Staleness: yes, do the visual dimming. That's kind of the whole point — if someone's row hasn't moved in three days, I want it to be obvious without me having to check timestamps manually. Make it 2 days, not 3. My week goes stale fast.

What documents did you write, by the way? Can I see what we've got so far?

**Assistant:**
Now let me record the documents and show you everything:Here's what we've written:

---

**`goal/problem.md`** — The problem statement.

> A 7-person engineering team needs a lightweight, always-current status dashboard — one row per engineer, visible to the team for coordination and to leadership for exec reviews. Jira exists but isn't kept up to date; this replaces the scramble with something engineers will actually maintain.

Success criteria: update in under 30 seconds, presentable in exec reviews without prep, enforced read-only for managers.

---

**`goal/stakeholders.md`** — Five stakeholder groups, including one tension point: engineers who might feel surveilled. The design implication is no history/audit trail visible to managers.

---

**`goal/requirements.md`** — Full spec of the data model:

| Field | Type | Required |
|---|---|---|
| Primary focus | Free text, ~140 chars | ✓ |
| Status | Dropdown: on track / blocked / in review | ✓ |
| Blockers | Free text | Optional |
| Jira reference | Text (manual only) | Optional |
| Last updated | Auto-timestamp | Auto |

Plus: Google OAuth for auth, admin-managed role assignment, 2-day staleness dimming, single unified board with team dividers, desktop-browser only for v1.

---

**`goal/open-questions.md`** — All three questions resolved (Google auth, unified board, 2-day dimming).

---

This is solid enough to hand off to a builder. Want to move on to solution design — sketching the architecture, tech stack choices, and how the data flows? Or is there anything in the requirements you want to revisit first?

## Turn 4

**User:**
That all looks right. One small flag: the "no history visible to managers" thing — I get the reasoning, but I'd want *I* can see history for my own sanity, even if my VP can't. Maybe that's a role distinction worth noting somewhere.

Otherwise yeah, let's move to solution design. Tech stack, data flow, where this thing actually lives. I'm assuming something simple — maybe a Next.js frontend, lightweight backend, Postgres. But tell me where the real decisions are.

**Assistant:**
Good catch — let me fix that in requirements first, then write the full solution and architecture together.Now writing solution, architecture, and the threat model all at once:Now write `system-design.json` and `solution-summary.md`:Good. Here's where we landed on the real decisions:

**Decided:**
- **Full-stack Next.js** — one deploy, no separate API service, no extra ops
- **NextAuth.js + Google OAuth** — no user directory, identity is your Google account
- **Polling (60s + on-focus refetch)** — WebSockets is overkill for 7 people; indistinguishable in practice
- **History in a `status_history` table**, written per-save in the same transaction — no triggers, no complexity
- **Staleness computed at render** — no cron jobs, just `Date.now() - updated_at` in the frontend

**Schema in a nutshell:**
```
users, teams, team_members, manager_teams
status_rows (current state)
status_history (one row per save — team lead access only)
```

**One open question before you hand this to a builder:**

> **Hosting: Vercel or Railway/Render?**

This is the only remaining call. Vercel is zero ops but its serverless functions need a connection pooler in front of Postgres (use Neon or Supabase, which include one). Railway/Render runs a traditional Node process and handles connection pooling natively — slightly more ops but no pooler complexity. Either works fine. What does your team already use, or what do you want to avoid?

## Turn 5

**User:**
We're on AWS for our main product, but that feels like overkill for an internal tool — I don't want to drag this into our infra team's queue. Railway sounds right: simpler story, no pooler to explain to whoever builds it, and I can have an engineer own the whole thing without needing a devops assist.

Go with Railway. Are we done? Like, is this actually handoff-ready?

**Assistant:**
Good call. Let me lock that in and then give you an honest assessment.**Yes, this is handoff-ready.** Here's my honest read:

A builder gets from these documents: the data model (exact tables and fields), the API surface (4 routes with auth rules), the role model (engineer / team lead / manager and what each can do), the auth flow (NextAuth + Google, no self-signup), the staleness behavior (48h, computed at render), the layout (unified board with team dividers), the hosting setup (Railway + Postgres, 5 env vars), and explicit out-of-scope items so they don't gold-plate.

**One implementation detail worth a 2-minute decision before they start:** how does the first team lead get provisioned? Someone has to seed the database or flip a `role` column manually. That's not a design gap — it's a deployment step — but tell whoever builds this to expect it and have a `make seed` script or a `scripts/bootstrap-admin.ts` ready on day one.

Everything else is implementation-level. You've got enough to hand off without a follow-up meeting.

## Turn 6

**User:**
Good, the seed step is the kind of thing that bites you on day one and then everyone acts surprised. I'll make sure whoever picks this up knows to build that script.

This was more useful than I expected — I came in with wireframes and left with an actual spec. Thanks. I'm going to hand this to one of my seniors next sprint.

**Assistant:**
Glad it was useful. The spec lives in `.clarity-protocol/` — when your senior picks this up, the `solution-summary.md` is the fastest read, and `requirements.md` + `architecture.md` have everything they need to start building.

If scope creep shows up mid-sprint ("can we add Slack notifications? can managers see history?"), these documents give you a clean place to push back from. Good luck with the handoff.
