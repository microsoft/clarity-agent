# Messaging

## Audience: Budget Meeting (End of Month)

**Who they are:** Finance decision-makers and executive leadership who control the purse strings. They've approved technology investments before and know what "we need budget for AI" usually means: a speculative bet with unclear returns, dressed up in buzzwords.

**What's on their mind:** ROI, risk, and whether this is a "nice to have" or a real business driver. They're also worried about security and compliance — they've read about AI breaches. They want to know that the team has thought this through, not just seen a competitor announce something.

**The narrative:**

We're not here to add AI because everyone else is. We're here because two specific things in our product are broken — our OCR and our categorization — and we have the data to fix them in a way no one else can. Every month, 100 million expense receipts flow through our system. That's our training set. Competitors using off-the-shelf AI APIs will converge on commodity quality. We can build something that only works because of data only we have.

The investment case is phased so each dollar is committed only after the previous phase shows results. Phase 1 — fixing OCR and training an initial categorization model — can begin immediately with the team we have, with data scientists we can borrow internally. We will measure accuracy before and after, so you'll see exactly what we got for the investment. Phase 2 requires one or two ML engineering hires, which is the central budget ask. Phase 3, the competitive moat, follows from Phases 1 and 2.

The risk of not investing is concrete: we are already losing prospects who cite competitors' "AI-powered insights" as a reason to consider switching. We have low churn today. We don't want to discover how high it can get once customers have spent a year being told by competitors that our product is behind the times.

**The ask:** $480K–$925K over 12 months, primarily in two ML engineering hires and managed infrastructure. We will begin recruiting immediately and have candidates in the pipeline before the board meeting. This is a staged commitment — the first phase succeeds or we stop.

**Handling the compliance question:** We've thought about this. No customer expense data goes to third-party AI providers without a signed Data Processing Agreement. Our long-term strategy — and the source of our competitive advantage — is building on our own infrastructure. By Phase 3, we will have reduced our third-party AI dependencies to near zero.

---

## Audience: Board of Directors (Six Weeks)

**Who they are:** Board members whose job is to assess whether the company is positioned to win over a 3-5 year horizon. They're evaluating management's judgment, not just the plan. They'll be skeptical of AI initiatives that sound reactive or vague. They respond to defensible strategic logic.

**What's on their mind:** Is this company going to be able to compete as AI reshapes the software landscape? Is management thinking strategically or chasing trends? What's the downside scenario?

**The narrative:**

Expense management software is becoming a commodity market. The companies that win in the next five years will be those whose software learns from their customers' data in ways that off-the-shelf tools cannot replicate. We're positioned to be one of those companies — but only if we start building the capability now.

Here's why we're positioned: 100 million expense receipts per month, accumulated over years, in a domain most AI companies have never touched. A large language model trained on general internet text doesn't know the difference between a business meal and a personal dinner, or between a legitimate vendor and a fraudulent one. Our data does. That's not a feature we're planning to build. It's an asset we already have.

The roadmap has three phases. In the first, we fix the known problems — OCR accuracy and categorization — using our existing data and team, with two targeted hires. In the second, we ship the intelligence layer: anomaly detection, policy compliance, spend insights — the features our competitors are marketing. In the third, we complete the transition to proprietary models trained on our corpus, which will outperform anything a competitor can license.

We've done the risk analysis. The failure modes are real: execution is hard without ML expertise, data privacy requires discipline, and timelines can slip. We have mitigations in place for each. Every AI feature launches in suggestion mode and earns automation only after accuracy is demonstrated. Data governance controls are non-negotiable prerequisites, not afterthoughts. Phase 2 doesn't begin until Phase 1 delivers measurable results.

The cost of doing nothing is not zero. It is a growing gap between our product's capabilities and what competitors are shipping. Our customers are noticing. Our prospects are mentioning it. If we wait another year, we'll spend twice as much to close a gap that was preventable.

**Key differentiator message:** Our competitors can buy the same APIs we can. They cannot buy our data.

---

## Audience: CEO

**Who they are:** Someone who is already convinced AI matters and wants to move fast. The risk here isn't skepticism — it's impatience leading to shortcuts that undermine quality and trust.

**What's on their mind:** When will we have something to show? What's the story for the next all-hands or customer announcement?

**The narrative:**

Here's the story: We are not catching up to competitors — we are taking a different path that will put us ahead of them. They're layering AI APIs on top of rules-based systems. We're building AI that only we can build, because only we have our data. That's the announcement when it's ready, and it's a better announcement than anything we could make today.

The first thing we can announce — in 4-6 weeks — is that we've upgraded our OCR. That's a real, visible improvement for customers. It's not the AI story, but it's the first chapter. The AI story ships with Phase 2.

What we need from you: patience for Phase 1 to be done right, so Phase 2 can be launched confidently. The worst outcome is shipping AI features in auto-apply mode before they're accurate enough, burning customer trust, and spending a year recovering it. The plan has accuracy thresholds before any automation turns on — that's not timidity, that's how you build something customers will actually use.

---

## Audience: Engineering Team

**Who they are:** 22 engineers who built the current system and will be responsible for everything that comes next. Some are excited about AI; some are skeptical; some are worried about being left behind or made redundant.

**What's on their mind:** Will this be a death march? Will ML make my skills obsolete? Is this a real initiative or another leadership whim that gets cut in six months?

**The narrative:**

The plan doesn't ask the team to become ML researchers. Phase 1 is a data pipeline and API integration problem — exactly what this team is good at. The categorization model training in Phase 1 is owned by data scientists we're borrowing; the team's job is to get them clean data and integrate what they build. Phase 2 ML engineering hires are additive, not replacements.

The real opportunity here is that the team is sitting on one of the most interesting data assets in B2B SaaS. Nobody on the team has seen what a well-trained model does with 100 million domain-specific receipts. That's an interesting problem to be close to.

What we need: every engineer to help instrument accuracy baselines before Phase 1 ships, and to treat AI feature rollouts with the same care as any other launch — measure, observe, and be ready to roll back.
