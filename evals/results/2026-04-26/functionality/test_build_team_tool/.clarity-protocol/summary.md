# Team Status Dashboard

We're building an internal dashboard that finally answers the question everyone on a growing engineering team eventually asks: "What is everyone actually working on right now?"

The team's current setup — a Slack channel for status updates, a project tracker for high-level goals — has a gap right in the middle. Individual day-to-day work is invisible unless you ask. That makes coordination harder than it needs to be, makes it easy to miss who to loop in on something, and means the team lead has to scramble whenever the VP wants a read on team activity.

The fix is simple: a web app where each engineer maintains a live card showing what they're working on. No mandatory fields, no process to follow — just a name for the item and whatever details feel useful. Everyone in the company can see the dashboard, and the VP can pull a formatted summary at any time from a bookmarkable URL and paste it straight into a slide deck.

It's built on Firebase with Google Workspace auth, so there's no new account system, no separate login, and almost no infrastructure to run. Team membership is tied to an existing Google Group, so it stays current automatically. The whole thing should ship in 2–3 engineer-weeks.
