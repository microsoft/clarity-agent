# Problem Statement

Daniel (VP of Product) at a mid-market expense management SaaS company needs to build a credible AI roadmap — one that's honest, executable, and serves three simultaneous audiences: a CEO energized by conference hype, customers asking "what's your AI story?" in QBRs, and a board meeting requiring budget justification.

The company's core product: finance teams at 50–500 employee companies photograph receipts or forward emails, OCR extracts line items, users categorize against their chart of accounts, and data syncs to NetSuite or QuickBooks. 4,000 customers. Competition is primarily a retention battle — switcher cost is real, but so is churn risk if a competitor tells a better story. The largest competitor announced an "AI assistant" three months ago (press release only, no known demo).

Engineering team: 22 people, no ML background, one engineer with a Coursera ML course and genuine interest. No ML infrastructure. No budget allocated yet — the budget number is an output of this process, not an input.

The core tension: the AI pressure is entirely vague. No customer has described a specific capability they want. The CEO and customers are reacting to category momentum, not a concrete gap. The risk is building a roadmap that chases a competitor's press release rather than genuine user value — or building a narrative that can't survive a "show me" moment.

## Why This Matters

Churn risk is the existential pressure. If customers believe a competitor has a materially better AI story and act on that belief, retention suffers — even if the competitor's actual product isn't better. Simultaneously, overpromising AI capabilities creates its own churn risk when customers don't see the promised value. The roadmap needs to thread this needle: credible enough to defend against competitive pressure, grounded enough to actually ship.

The board meeting and budget conversation are time-bounded forcing functions. This needs to be concrete enough to walk into a room with numbers.

## Success Criteria

- A roadmap document Daniel can walk into a board meeting with in ~6 weeks that is specific, honest, and holds up to follow-up questions
- A budget number (or range) to bring into a budget conversation
- A customer-facing narrative for QBRs — an answer to "what's your AI story?" that's compelling but doesn't overpromise
- Clarity on what to build vs. buy (e.g., OCR improvement is likely "buy better," categorization improvement is likely "build on proprietary data")
- Confidence that the roadmap is anchored in genuine user pain, not competitor press release chasing

## Key Insight (Emerged in Conversation)

The natural AI anchor is **smarter categorization**, not a chatbot. Two pain points drive this:
1. OCR error rate ~30% — manual correction is the first thing users do every time
2. Rules-based category suggestions fail often enough that users have abandoned them; finance managers clean up miscategorizations at month-end

The company has two years of categorization history (merchant + description → chosen category) across 4,000 customers — a proprietary labeled dataset that could train a classification model. This data is a genuine competitive moat. The instinct to build an "AI assistant" chatbot came from competitor/conference pressure, not user need; it's a weaker anchor for this team and this product stage.
