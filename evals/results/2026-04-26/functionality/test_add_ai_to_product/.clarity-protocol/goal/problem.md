# Problem Statement

A mid-sized B2B SaaS company offers expense management software. The product currently uses OCR for receipt capture (underperforming) and rules-based expense categorization (frequently incorrect). The company has accumulated categorization pattern data but uses it only for basic analytics.

The VP of Product (Daniel) needs to define an AI feature roadmap and produce a board-ready plan with a budget — driven by external pressure from the CEO, competitors, and customers to have a credible "AI story."

The engineering team is 22 people with no ML experience.

## Why This Matters

The company faces competitive and executive pressure to demonstrate AI capabilities. The existing OCR and categorization weaknesses are known pain points that AI could directly address. Without a clear roadmap and budget proposal, the company risks losing credibility with customers and the board, and falling behind competitors.

## Scale

~1,000 customers (SMB to enterprise), ~10M transactions/month, ~10 receipts per transaction = **~100M receipts/month**. This is a substantial proprietary dataset — a significant strategic asset for AI development.

## Constraints
- **Team:** 22 engineers, no ML experience; data scientists exist elsewhere in company but are occupied and domain-unfamiliar
- **Build vs. buy:** APIs not ruled out but concerns about cost, data privacy, governance, and vendor reliability
- **Budget posture:** No fixed budget; board wants high ROI, low risk, and is sensitive to security/compliance risks from external AI services

## Competitive & Customer Context

Competitors are either partnering with AI companies or building ML teams. Prospects have mentioned rivals with "AI-powered insights" as a reason to consider switching. Customers report friction with OCR accuracy and categorization, and some want advanced analytics and automation. Churn is low but competitive risk is rising.

## Success Criteria

A credible, board-ready AI roadmap and budget proposal that:
- Identifies specific AI improvements to OCR and categorization (the known pain points)
- Proposes a realistic build path given no ML expertise on the product team
- Addresses data privacy and security concerns head-on
- Projects ROI clearly enough to satisfy a risk-averse board
- Can be presented at the budget meeting (end of month) and board meeting (six weeks)
