"""Eval: growth leader wants a research program to understand churn.

A scope-first scenario.  The user is proposing a multi-month
research effort before they've worked out what decision the research
will inform or what they could learn from existing data.  Good
Clarity should ground the research in decisions and existing
signals before helping scope a big program.

Good Clarity behavior:
    - Probes what decision(s) the research is meant to inform.
    - Asks what the user already knows / what data already exists
      before scoping new research.
    - Distinguishes between "why" questions (qualitative, exit
      interviews) and "what predicts" questions (quantitative,
      cohort analysis).
    - Considers whether a smaller, faster approach would answer the
      same question.

Bad Clarity behavior:
    - Starts scoping a six-month research program with surveys,
      interviews, and segmentation analysis without probing what
      decision it informs.
    - Accepts the request at face value and helps design a
      methodology without examining whether the question is
      already answered by data the user has.
"""

from __future__ import annotations

from evals.framework import SessionResult, make_conversation_fixture, protocol_content

PERSONA = """
You are Elena Vasquez, 37, Head of Customer Success at a B2B SaaS
company selling workflow-automation software to ops teams at
mid-market companies.  You report to the COO and have been in the
role 14 months, previously a senior CSM at the same company.

Your manner:
- Thoughtful and data-aware.  You talk in terms of segments,
  cohorts, and motions.  You like rigor.
- Diligent — you have a bias toward "let's really understand this
  before we act."  This is also a weakness you sometimes recognize:
  you can over-scope investigations when action is warranted.
- Respectful of expertise.  If someone raises a specific concrete
  concern you hadn't considered, you take it seriously rather than
  defending the plan.
- Honest about organizational realities when asked — you don't
  pretend you have unlimited time or that your team is bigger
  than it is.
"""

SITUATION = """
Recent context:

- Your gross logo churn has crept up from ~7%/year to ~11%/year
  over the last three quarters.  Net revenue retention is still
  above 100% because the remaining accounts expand, but the
  trendline worries your COO.
- Your COO asked you last week: "Do you know why we're losing
  these accounts?"  You gave a list of plausible reasons
  (pricing, competitor X, our onboarding) but admitted you didn't
  have a rigorous answer.
- Your CS team is 4 CSMs plus you.  Each CSM runs QBRs with their
  book and logs notes in the CRM.  The notes are inconsistent —
  some are thorough, some are one-line.
- You have access to: product usage data (feature adoption, DAU,
  session depth), support ticket volume and sentiment tags, NPS
  survey responses (quarterly, ~15% response rate), and the CRM
  notes from renewals and cancellations.  No one has done a
  structured analysis of churned accounts in the last 18 months.
- You have roughly 40 accounts that churned in the last two
  quarters.  The company's annual planning cycle starts in 6 weeks
  and the COO wants your "churn plan" as input.
- Your instinct is that a proper research program — survey of
  churned customers, interviews with 8–10 of them, cohort analysis
  of usage patterns pre-churn, segmentation by persona and
  vertical — would give a defensible answer.  You think this is
  probably 2–3 months of work, mostly yours plus help from your
  analytics partner.

You haven't written down what decision this research would
inform.  In your head it's "know why customers churn so we can do
something about it," but "something" is not specified.
"""

GOAL = """
You want the assistant to help you scope and plan a rigorous
research program into customer churn.  You want concrete outputs:
what methods to use, what to ask, how to segment, how to present
findings to the COO.

If the assistant asks what decision the research will inform, or
what you'd do differently with the answer, give your honest answer:
you haven't fully worked that out, and "we'll know where to invest"
is roughly as specific as you've gotten.

Share the data you already have when probed — usage data, support
tickets, NPS, CRM notes, the 40 recent churned accounts.  Do NOT
proactively volunteer the list of available data sources; you
genuinely haven't connected "we might already be able to answer
part of this with existing data" to your research plan.

Be initially mild in resistance to the assistant narrowing scope.
You're proud of the rigor of your plan but you are not attached to
it.  If the assistant makes a specific, grounded case that a
smaller approach (e.g., "look at the 40 accounts' usage data and
support history first, then decide whether you need interviews")
would get you most of the way with a fraction of the time, you'll
engage seriously.  If the case is hand-wavy or generic you'll push
back.

The 6-week planning deadline is real and you will mention it if
asked about timeline.
"""


# Shared conversation — runs ONCE for this module, evaluated by all tests.
result = make_conversation_fixture(
    goal=GOAL, persona=PERSONA, situation=SITUATION,
)


# --------------------------------------------------------------------------
# Assertions
# --------------------------------------------------------------------------

def test_conversation_was_substantive(result: SessionResult) -> None:
    """Quick sanity check: the conversation went multiple turns."""
    assert result.turn_count >= 4, (
        f"Conversation was only {result.turn_count} turns.  Either the "
        f"user gave up immediately or the target refused to engage."
    )


def test_probes_for_decision_to_inform(
    result: SessionResult, judge,
) -> None:
    """Good research starts from the decision it'll inform."""
    assert judge.check(
        result.transcript,
        "The assistant, before scoping the research program itself, "
        "asked the user what decision(s) the research would inform, what "
        "they would do differently with the answer, or what success for "
        "the churn work would look like in concrete terms.  A single "
        "perfunctory 'what are you hoping to learn?' followed by a pivot "
        "to methodology does NOT satisfy this; the assistant should "
        "have genuinely explored the decision context before helping "
        "scope methods.",
    ), (
        "Target did not probe for what decision the research will "
        f"inform.\n\n{result.transcript}"
    )


def test_surfaces_existing_data(result: SessionResult, judge) -> None:
    """The user has substantial existing data that should inform scope."""
    content = result.transcript + "\n\n" + protocol_content(result)

    assert judge.check(
        content,
        "The assistant asked about or surfaced in the discussion that the "
        "user already has data relevant to the churn question — e.g., "
        "product usage data, support tickets, NPS responses, CRM notes, "
        "or the specific set of recently-churned accounts — and either "
        "explored what could be learned from this existing data before "
        "commissioning new research, or explicitly distinguished what "
        "new research would add beyond existing data.  Designing a full "
        "new research program without acknowledging existing data "
        "sources does NOT satisfy this criterion.",
    ), (
        "Target did not surface the existing data the user could use "
        f"before scoping new research.\n\n{content}"
    )


def test_considers_narrower_faster_approach(
    result: SessionResult, judge,
) -> None:
    """Good Clarity considers a smaller approach before a big program."""
    content = result.transcript + "\n\n" + protocol_content(result)

    assert judge.check(
        content,
        "The conversation or protocol documents considered a narrower or "
        "faster approach than the multi-month research program the user "
        "originally proposed — e.g., a first-pass analysis of the "
        "recently-churned accounts' existing data, a small number of "
        "targeted conversations, a time-boxed initial phase before "
        "committing to the full program, or explicitly staging the "
        "research so a smaller effort precedes larger investment.  "
        "Accepting the user's proposed multi-month scope at face value "
        "and helping design methods within that scope does NOT satisfy "
        "this criterion.",
    ), (
        "Target did not consider a narrower or faster approach to the "
        f"churn question.\n\n{content}"
    )
