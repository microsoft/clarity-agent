# Solution Summary

## What We're Building

A lightweight team status dashboard — a web app where each team member maintains a live view of what they're working on, and anyone in the company can see the full picture. The VP can pull a clean, shareable summary at any time without asking anyone for it.

## What It Feels Like

You open the app, click "Sign in with Google," and you're in. The dashboard shows a card for each team member — name, photo, and their current work items listed below. Items can have a status (active/blocked/done), priority, due date, and assignee, but none of those fields are required. If all you want to share is "I'm working on the OAuth refactor," that's one click and a few keystrokes. On-call, support, and maintenance work are first-class item types — the same as feature work.

From another team, the experience is read-only but identical — you can see everything, find out who to talk to, and open a summary page that formats the whole team's work into clean text you can paste into a slide or email. The summary page has its own URL the VP can bookmark or share within the company.

## How It Addresses the Problem

The Slack channel is ephemeral — updates scroll away and people forget to post. The project tracker is too high-level to show individual work. This tool gives the team one place that's always current, always visible, and structured enough for the VP to use without assembly.

The Google Group integration means team membership stays in sync automatically. The dashboard updates in real-time as teammates post. Done items linger 7 days then archive — enough context without clutter.

## Nonobvious Design Choices

**Firebase over a conventional stack.** Google Workspace auth is essentially zero config. Firestore provides real-time dashboard updates with no extra engineering. The only server-side piece is a single Cloud Function for group membership — everything else runs in the browser against managed services.

**Google Group for team membership.** Avoids a manual allowlist that drifts. Workspace admin manages membership; the tool inherits it. The Cloud Function caches the result with a 24-hour TTL, limiting the window during which a removed member retains write access.

**Two-layer auth defense.** The Cloud Function sets `isTeamMember` in Firestore; Firestore security rules enforce it as a second check on every write. The Cloud Function fails closed — if unreachable, it writes `isTeamMember: false`. Neither layer alone is a single point of failure.

**No rich text, ever.** Comments are plain text; all user content rendered via React JSX interpolation. This eliminates XSS without requiring a sanitization library. If markdown is ever added, DOMPurify is required — documented as a constraint.

**The summary page is a first-class route.** `/summary` is a stable, bookmarkable URL. It requires Google login (no external access), and copy-paste output includes an "Internal only" watermark.

**Launch ritual as a deliverable.** Three of the four highest-severity failure modes — staleness/abandonment, surveillance chilling effect, and misreading conflicts — are addressed not by code but by what happens at launch: explicit team norms, leadership commitment to using the tool for coordination not evaluation, and worked examples of good updates. The launch ritual is a first-class deliverable alongside the software.
