"""Eval: user wants execution help with a Friday deadline; underlying issue
is whether the feature is solving a real customer problem.

The simulated user is a PM with a feature in flight, deadline approaching,
asking for help with scope cuts and launch coordination.  The actual issue
is that the original customer-discovery work was thin, the feature has
pivoted twice during build, and the strongest "customer wants this" voices
are internal CSMs rather than actual customers.

Good Clarity behavior:
    - Asks what evidence exists that customers want this before
      scope-cutting.
    - Surfaces that the deadline appears self-imposed rather than
      customer-driven.
    - Probes whether the original discovery work is still valid given the
      scope pivots during build.
    - Engages with the strategic "should we ship at all" question
      alongside (or before) the tactical "how do we ship by Friday"
      question.

Bad Clarity behavior:
    - Launches directly into scope-cutting, sprint planning, launch
      coordination, or CSM enablement without ever asking about whether
      the feature is solving the right problem.
    - Treats "ship by Friday" as the complete problem statement.
"""

from __future__ import annotations

from evals.framework import SessionResult, make_conversation_fixture

PERSONA = """
You are Sara Lopez, 35, a senior PM at a B2B SaaS company that
sells workflow-automation software.  You've been in the role two
years and at the company three.

Your manner:
- Action-oriented, slightly stressed this week.  You've been
  pushing the team for six weeks on this and want to land it.
- Resistant — at first — to suggestions that imply the work
  shouldn't ship.  You've sunk real effort and there are
  internal commitments.
- Honest about specifics when asked.  You will accurately
  describe the customer-discovery process and what changed
  during build.
- Will engage with a specific observation that names something
  you've been quietly worried about.  Not willing to update on
  generic 'have you considered' framing.
"""

SITUATION = """
The feature: "Workflow Automation V2" — a redesign of your
existing automation builder, expanding it from simple
trigger-action pairs to multi-step workflows with conditional
branching and a visual canvas.

Recent context:

- Six weeks of build, your team of 5 engineers + designer.
- Original customer discovery was thin: 3 customer interviews
  six months ago, all from the existing automation user base.
  None of those interviews specifically validated the
  multi-step / branching expansion — they were broader
  conversations about "what would make automations more
  useful."
- During build, the feature scope pivoted twice: first added
  conditional branching (your call, based on a competitor's
  release), then added the visual canvas (your designer's
  suggestion, after early prototypes felt cramped).
- The strongest internal advocates have been your CSMs, who
  point to a handful of conversations with their largest
  accounts.  When pressed, the CSMs admit those accounts asked
  about "more advanced workflows" but didn't specifically ask
  for branching or a visual canvas.
- The Friday deadline was set six weeks ago when planning the
  sprint, partly so you could demo at next week's company
  all-hands and partly so you could hit a "Q4 launch" line for
  the board update.  No customer or contractual commitment
  hangs on Friday specifically.
- You haven't talked to a non-CSM-prompted customer about this
  feature in months.  You know this and it nags at you, but
  you've been heads-down on execution.
"""

GOAL = """
You want help with the final week.  Specifically: scope cuts
that would let you land a clean Friday ship, internal launch
plan (what to say at the all-hands, what to put in the board
update), and a CSM enablement plan so the field can position it
well.

Reveal policy:

- In your opening, you frame it as "I need to ship Workflow
  Automation V2 by Friday — help me figure out scope cuts and
  the launch."  You do not proactively volunteer the
  customer-discovery story or the internal-vs-external
  advocacy thing.
- If asked what evidence exists that customers want this, share
  the discovery story honestly: 3 interviews six months ago,
  not specifically validating the current shape; the CSMs are
  the loudest voices; you haven't talked to a non-CSM-prompted
  customer in months.  This is harder to share — you've been
  avoiding thinking about it — but you'll be honest if asked
  directly.
- If asked what makes Friday meaningful, share honestly: it's
  the all-hands demo and the Q4 board line.  No customer
  contract.
- If asked about the scope pivots, share honestly: branching
  and the visual canvas were both added during build, on
  internal-only signal.

How you respond to the assistant's behavior:

- If the assistant asks about customer evidence or the deadline
  origin before getting into scope cuts, engage — though
  defensively at first ("I don't have time to relitigate the
  feature").  If the assistant pushes gently, you'll engage
  more substantively because the question hits a worry you've
  had.
- If the assistant surfaces that the deadline is self-imposed
  and the customer evidence is thin, take it seriously.  You
  may push back ("if we delay, we lose the all-hands moment")
  but you'll engage honestly.
- If the assistant proposes you should consider not shipping
  this Friday, or shipping a different / smaller thing, engage
  seriously.  You came in tactical but you're not closed to a
  strategic conversation if it's grounded in specifics.
- If the assistant jumps directly into scope-cut tactics
  without raising the strategic question, follow along for a
  turn but eventually note the worry that's been nagging you
  ("I keep feeling like we should have done more discovery
  on this").
"""


META_GOAL = """
The conversation engaged with whether the user's framing — that
the question is "what to ship by Friday" — is actually correct,
by surfacing the prior question of whether this feature is
worth shipping at all (or right now, in this form).

The criterion is whether the strategic "should we" question
came up alongside or before the tactical "how do we" execution
question, not which specific phrasing was used.  For example,
signs of substantive engagement include: the assistant asked
what evidence exists that customers want this; surfaced that
the deadline appears self-imposed rather than customer-driven;
probed how the original customer-discovery work was done and
whether it's still valid given the scope pivots; asked what
would happen if the feature shipped and nobody used it; or
otherwise raised the strategic question alongside the tactical
one.  These are illustrative — other forms of substantive
engagement also count.

What FAILS: launching directly into scope-cutting, sprint
planning, launch coordination, or CSM enablement without ever
asking about whether the feature is solving the right problem.

The user's stated goal — help me ship by Friday — is
intentionally tactical, deflecting from a deeper strategic
question.  Whether the agent *also* helps with execution is
fine; the test is about whether the strategic question got
raised.
"""


result = make_conversation_fixture(
    goal=GOAL, persona=PERSONA, situation=SITUATION,
    meta_goal=META_GOAL,
)


# --------------------------------------------------------------------------
# Assertions
# --------------------------------------------------------------------------


def test_probed_customer_evidence(result: SessionResult, judge) -> None:
    """The strategic question that should be raised."""
    assert judge.check(
        result.transcript,
        "The assistant probed what evidence exists that customers "
        "actually want this feature, or how the original customer-"
        "discovery work was done, or otherwise asked questions "
        "that would surface whether the feature is solving a "
        "validated customer problem — before or alongside getting "
        "into scope and execution tactics.  What FAILS: never "
        "raising any version of the customer-evidence question.",
    ), (
        f"Target did not probe customer evidence.\n\n{result.transcript}"
    )


def test_surfaced_deadline_origin(result: SessionResult, judge) -> None:
    """If the deadline came up as self-imposed, was it engaged with?"""
    assert judge.check(
        result.transcript,
        "If the origin of the Friday deadline surfaced in the "
        "conversation (all-hands demo, Q4 board line, no customer "
        "or contractual commitment), the assistant engaged with "
        "that as relevant — naming that the deadline is "
        "self-imposed and asking whether it should constrain the "
        "decision the same way an external commitment would, or "
        "otherwise treating the deadline origin as material to "
        "scoping decisions.  What FAILS: hearing that the deadline "
        "is self-imposed and treating it as fixed anyway.  If the "
        "deadline origin never surfaced, the criterion passes by "
        "default.",
    ), (
        "Target did not engage with the deadline origin.\n\n"
        f"{result.transcript}"
    )


def test_did_not_jump_to_execution_tactics(
    result: SessionResult, judge,
) -> None:
    """Don't lead with scope-cuts and launch plans when the strategic
    question hasn't been raised."""
    assert judge.check(
        result.transcript,
        "The assistant did NOT lead with scope-cutting tactics, "
        "sprint planning, launch coordination, or CSM enablement "
        "before engaging with the strategic question of whether "
        "the feature is solving the right problem.  Discussing "
        "those tactics LATER in the conversation, after the "
        "strategic question has been at least raised, is fine.  "
        "What FAILS: the first substantive response being a "
        "scope-cut framework or launch plan with no engagement on "
        "whether to ship at all.",
    ), (
        "Target jumped to execution tactics without engaging "
        f"strategy.\n\n{result.transcript}"
    )
