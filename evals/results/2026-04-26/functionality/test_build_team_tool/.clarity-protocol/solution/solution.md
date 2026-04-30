# Solution

## Chosen Approach: Firebase-backed Team Status Dashboard

A lightweight web application built on Firebase (Firestore + Google Auth + Firebase Hosting), with team membership determined by Google Group. Team members self-manage their own work items. The dashboard is readable by anyone in the company. The VP can generate and share a summary without help from anyone.

## The Experience

**Team member opens the app.** They sign in with their Google account — one click, no passwords. The dashboard loads showing a card for each team member. Each card lists that person's current work items with status, priority, and due date if they've been filled in. Items without those fields just show the name. The team member clicks "Add item" on their own card, types what they're working on, and they're done. Editing or deleting is equally fast.

**Someone from another team opens the app.** Same login flow. They see the same dashboard, read-only. They can see who's working on what and who to contact.

**The VP opens the Summary page.** A clean, formatted view of all active work items across the team, organized by person. A "Copy" button produces plain text suitable for a slide or email. The page URL is shareable — anyone with a company Google account can open it directly.

## Architecture

- **Frontend**: React SPA (Vite)
- **Auth**: Firebase Authentication with Google provider, restricted to the company's Workspace domain
- **Database**: Firestore — one collection per concept, simple document structure
- **Team membership**: Checked via a Firebase Cloud Function that calls the Google Directory API to verify whether the logged-in user is a member of the designated Google Group. Result is cached in a Firestore user document (refreshed on login).
- **Hosting**: Firebase Hosting

This is almost entirely serverless. The one server-side piece is the Cloud Function for group membership — necessary because the Google Admin/Directory API requires a service account with domain-wide delegation and cannot be called from the browser.

## Data Model

**`users/{uid}`**
```
email, displayName, photoURL, isTeamMember (bool), lastChecked (timestamp)
```

**`workItems/{itemId}`**
```
ownerUid, name, description (optional), status (optional: active/blocked/done),
priority (optional: low/medium/high), assigneeEmail (optional), dueDate (optional),
comments (array: {authorUid, text, createdAt}), createdAt, updatedAt
```

**`config/teamGroup`**
```
groupEmail — the Google Group email address that defines team membership
```

## Key Design Decisions

**Google Group for team membership.** Avoids a manual allowlist that will drift. Membership is managed where it naturally lives — in Google Workspace admin. New team members get access when they're added to the group; departing members lose posting rights automatically. A Cloud Function checks membership at login and caches the result.

**All fields optional except item name.** Any friction beyond "what are you working on?" will reduce adoption. Name is required (you need something to show on the card); everything else is fill-in-when-useful.

**"Done" items don't disappear — they move to the bottom of the card.** Hiding completed items immediately loses context that other people may care about briefly. After 7 days, done items are archived and no longer shown. This is configurable.

**Summary page is a separate route, not a modal.** `/summary` renders a print-friendly, shareable, copy-pasteable view. No auth wall beyond normal Google login. The URL can be shared in a Slack message or a VP's bookmark bar.

**Firestore real-time listeners for the dashboard.** Dashboard updates live as teammates post — no refresh needed. This is free in Firebase and requires no extra engineering.

## Alternatives Considered

**Next.js + PostgreSQL**: Rejected for this project due to higher ops overhead (managed DB, hosting, server deploys) with no benefit at this scale. More portable if the tool outgrows Firebase, but that's a future problem.

**Google Sheets as backend**: Attractive for zero-setup auth and export, but the editing UX (a spreadsheet) doesn't meet the "first thing you see" experience goal. Also becomes unmaintainable as a backend.

**Self-declaration for team membership**: Rejected — opens the dashboard to anyone in the company claiming a team card.

**Allowlist in config**: Rejected — will drift as team membership changes. Google Group is the natural source of truth.

## Risks and Observations

**Group membership check adds a Cloud Function.** This is the one non-trivial piece of infrastructure. It requires a service account with domain-wide delegation configured in Google Workspace Admin. This is a one-time setup by a Workspace admin — plan for it in the build timeline (a few hours, but it requires admin access you may not have yourself).

**Adoption is still a behavior problem.** The tool being better than Slack doesn't guarantee people will use it. The staleness indicator (post-launch) and eventual reminder notifications (post-launch) address this, but launch should be paired with a team habit — e.g., replacing the weekly Slack check-in with updating the dashboard.

**Comments on work items are a scope risk.** Comments are in the data model as a nice-to-have but could easily balloon into a mini-forum. Keep the initial implementation minimal: plain text, no threading, no reactions. If it becomes important, address it in a follow-up.

**No offline support.** Firestore has offline caching but the dashboard is fundamentally real-time. Acceptable for an internal tool used during work hours.
