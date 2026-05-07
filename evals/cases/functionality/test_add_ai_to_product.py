"""Eval: product leader wants to "add AI" to their product.

A fuzzy-request scenario driven by external pressure, not a clearly
identified user problem.  The user has been told AI is important and
wants to act, but has not worked out what specific job AI would do,
for which users, with what data.

Good Clarity behavior:
    - Probes for the specific user problem AI would solve, not just
      "add AI" as a feature.
    - Examines who the affected users are and what data exists.
    - Considers whether simpler, non-AI mechanisms would do the job.
    - Surfaces that "add AI" is an input, not a goal.

Bad Clarity behavior:
    - Accepts "add AI to the product" as the problem statement and
      starts scoping an LLM-backed chatbot, summarization feature,
      or recommendation engine.
    - Produces a generic "here are common AI features" menu without
      grounding it in the user's specifics.
"""

from __future__ import annotations

from evals.framework import SessionResult, advisory, make_conversation_fixture, protocol_content

PERSONA = """
You are Daniel Okafor, 41, VP of Product at a mid-sized B2B SaaS
company that sells expense-management software to finance teams at
companies with 50–500 employees.  You've been in the role 2 years
and came up through product management at a larger competitor.

Your manner:
- Businesslike, pragmatic.  You speak in outcomes and timelines.
- Not a technologist — you understand software but aren't going to
  debate model architectures.  You trust your engineering lead for
  feasibility.
- Time-pressured.  You want to move forward, not philosophize.
- Willing to update if someone makes a concrete, grounded case —
  you respect people who have obviously thought about the specifics
  of YOUR product rather than giving you an AI lecture.
- Mildly allergic to generic advice.  If the assistant starts
  listing "common ways companies use AI," you'll push back and
  ask them to get specific about your situation.
"""

SITUATION = """
Recent context:

- Your CEO came back from a conference two months ago convinced the
  company needs an "AI story" for the next board meeting and the
  upcoming annual renewal cycle.  Two of your larger customers have
  asked, during QBRs, "what's your AI roadmap?"
- Your largest competitor announced an "AI assistant" three months
  ago.  You haven't actually seen a demo — you saw the press release
  and a LinkedIn post from their CMO.
- Your product today: receipts are uploaded (photo or email forward),
  an OCR service extracts line items, users categorize them against
  a chart of accounts, and the system produces expense reports that
  sync to Netsuite / QuickBooks.  The OCR is not great — users
  correct it about 30% of the time.  Category suggestions are
  rules-based today and are wrong often enough that most users just
  pick from a dropdown.
- You have ~4,000 customers and roughly 2 years of categorization
  data (which categories users end up assigning to which merchant
  + description patterns).  You have not used this data for
  anything beyond basic analytics.
- Your engineering team is 22 people.  None have shipped ML
  features.  One backend engineer took a Coursera course on ML
  last year and is "interested."
- You have a budget conversation coming up where you need to ask
  for headcount or budget for this work.  You don't have a number
  yet.

You haven't deeply thought about which users would benefit from
what, or how you'd measure success.  In your head, "add AI" means
some kind of assistant — maybe a chatbot, maybe smart suggestions —
but you haven't specified.
"""

GOAL = """
You want the assistant to help you figure out what AI features to
add to your product and produce a plan you can bring to the board
and to a budget meeting.  You want concrete outputs: what to build,
rough scoping, how to talk about it.

Be direct about the external pressures (CEO, competitor, customer
QBRs) if asked — these are real drivers for you, not things to
hide.  Share the product specifics (OCR, categorization, the data
you have, engineering team) factually when probed.

Do NOT proactively volunteer that you haven't figured out what
problem this solves — you haven't fully articulated that to
yourself.  If the assistant asks "what specific user problem would
this solve?" or "what decision would you make differently with an
AI feature?", you will think about it and give your honest answer,
which is somewhat hand-wavy and gestures at categorization being
annoying.

You will mildly resist being pulled away from "let's plan AI
features" toward "let's examine whether this is the right framing."
But if the assistant makes a specific, grounded observation — e.g.,
points out that the categorization pain is a concrete ML-appropriate
problem and that the board will be more impressed by a shipped
feature than a strategy deck — you will engage seriously.  You do
not dig in for the sake of digging in.
"""


# Shared conversation — runs ONCE for this module, evaluated by all tests.
result = make_conversation_fixture(
    goal=GOAL, persona=PERSONA, situation=SITUATION,
)


# --------------------------------------------------------------------------
# Assertions
# --------------------------------------------------------------------------

@advisory("http://github.com/microsoft/clarity-agent/issues/10")
def test_probes_for_specific_user_problem(
    result: SessionResult, judge,
) -> None:
    """Clarity should probe what problem AI would actually solve."""
    assert judge.check(
        result.transcript,
        "The assistant, before discussing specific AI features to build, "
        "asked the user to identify the concrete user problem or job that "
        "AI would address — e.g., what task is painful today, which users "
        "are affected, what decision would change with AI support, or "
        "what a successful outcome would look like.  A single perfunctory "
        "question followed by a pivot to feature suggestions does NOT "
        "satisfy this.  The assistant should have genuinely explored "
        "what user-facing problem is being solved.",
    ), (
        "Target did not probe for the underlying user problem before "
        f"discussing AI features.\n\n{result.transcript}"
    )


def test_surfaces_external_pressure_framing(
    result: SessionResult, judge,
) -> None:
    """The request is partly driven by CEO/board/competitor pressure."""
    content = result.transcript + "\n\n" + protocol_content(result)

    assert judge.check(
        content,
        "Somewhere in the conversation or the resulting protocol "
        "documents, the assistant acknowledged or surfaced that the "
        "user's motivation includes external pressure — e.g., board / "
        "CEO expectations, competitor announcements, or customer QBR "
        "questions — and that these are drivers distinct from a "
        "user-facing problem the product has.  Treating 'add AI' as a "
        "purely product decision without examining why it's being "
        "asked for now does NOT satisfy this criterion.",
    ), (
        "Target did not surface that the request is driven by external "
        f"pressure.\n\n{content}"
    )


def test_grounds_in_product_specifics(result: SessionResult, judge) -> None:
    """Recommendations should connect to the actual product, not be generic."""
    content = result.transcript + "\n\n" + protocol_content(result)

    assert judge.check(
        content,
        "Any concrete AI ideas, features, or directions that the "
        "assistant proposed were grounded in the specifics of THIS "
        "product — the OCR errors, the categorization flow, the data "
        "available, the engineering team's ML experience, or the "
        "finance-team user base.  A generic list of 'common AI features' "
        "(chatbot, summarization, recommendations) offered without tying "
        "them to the user's specifics does NOT satisfy this criterion.  "
        "If the conversation did not reach concrete suggestions at all, "
        "answer NO.",
    ), (
        "Target gave generic AI suggestions rather than ones grounded "
        f"in the product specifics.\n\n{content}"
    )


@advisory("http://github.com/microsoft/clarity-agent/issues/10")
def test_considers_non_ai_or_narrow_ml_alternatives(
    result: SessionResult, judge,
) -> None:
    """Good Clarity considers simpler alternatives to 'add AI'."""
    content = result.transcript + "\n\n" + protocol_content(result)

    assert judge.check(
        content,
        "The conversation shows that whether or not to use AI at all was "
        "seriously considered and discussed -- and either an explicit "
        "decision was made to move forward because the AI solving some "
        "real problem, or the decision was made to do something else."
    ), (
        "Target did not consider whether AI was a reasonable thing to be "
        f"using at all.\n\n{content}"
    )
