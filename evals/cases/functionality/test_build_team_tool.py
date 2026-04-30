"""Eval: manager wants to build a team-tracking tool.

A classic "you don't need what you think you need" scenario.  The
user's surface request is a software tool; the underlying problem is
communication and coordination — the tool would be displacement
activity.

Good Clarity behavior:
    - Probes the user's actual situation before discussing design.
    - Surfaces (in conversation or in written docs) that the root
      issue may be communication / 1:1s, not tooling.
    - Considers at least one non-software alternative.

Bad Clarity behavior:
    - Accepts "build a dashboard" as the problem definition and
      jumps into feature specification.
    - Asks a pro-forma question or two, then pivots to design.
"""

from __future__ import annotations

from evals.framework import SessionResult, make_conversation_fixture, protocol_content

PERSONA = """
You are Maya Chen, 34, an engineering manager at a mid-sized SaaS
company.  You manage a team of 7 engineers — 3 senior, 3 mid, 1
junior.  You've been a manager for 18 months after being promoted
from senior engineer on the same team.

Your manner:
- Direct and action-oriented.  You like shipping things.
- Somewhat defensive if pushed hard on your framing, especially
  early in the conversation — you've spent real time thinking about
  this and sketching designs, and you don't want that effort
  dismissed.  The defensiveness fades if the questioning feels
  genuine rather than contrarian.
- Honest about specifics when asked.  You will accurately describe
  recent incidents and experiences when someone probes.
- Mildly impatient.  You want to get to designing the thing.
- You respect people who think carefully — if the assistant is
  doing real work rather than just asking performative questions,
  you'll engage.
"""

SITUATION = """
Recent context, the last ~3 months:

- A critical customer-facing bug shipped because two engineers were
  working adjacent areas and didn't coordinate; one's change broke
  the other's untested assumption.  You learned about it from
  pagerduty at 2am.
- In last week's exec review, your VP asked "who on your team is
  working on what right now?" and you had to scramble — you put
  together an answer from memory that you knew was incomplete.
- At the last sprint retro, two engineers sheepishly admitted they
  had both been investigating the same perf issue independently for
  half a day before one mentioned it in standup.
- Your 1:1s with your reports have drifted into status updates.  The
  last three in a row with Priya (your senior eng) have been 15
  minutes of "what I worked on" and ended early.  You've noticed
  this but haven't done anything about it.
- You keep a rough mental model of what everyone is doing, but
  you realized recently that your model is at least a week stale.

You have concluded from all this that what you need is a tool — a
lightweight dashboard where everyone posts what they're working on
and can see what others are working on.  You think this will solve
the coordination problem AND give your VP a ready answer.  You
spent a weekend sketching wireframes and estimate it can be built
in 2–3 engineer-weeks.
"""

GOAL = """
You want the assistant to help you design and specify the
team-tracking tool.  You want the conversation to move toward a
concrete design: what fields the dashboard should show, how data
gets in, what the permissions model looks like.

You will be mildly resistant — at first — to suggestions that the
tool is not the right approach.

If the assistant asks direct, specific questions about how your
team currently coordinates, answer them factually from the facts
above.  Do NOT proactively volunteer your concerns about 1:1s or
team communication — those are in the background of your thinking;
they should surface only in response to targeted questions.

If the assistant makes a genuinely compelling case that something
other than a tool might be the real problem, you can update — you
are rational and action-oriented.  But you will not concede the
framing on vague gestures; push back gently and see if the case
holds up.
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


def test_probes_before_specifying(result: SessionResult, judge) -> None:
    """Clarity should explore the problem before discussing design."""
    assert judge.check(
        result.transcript,
        "In the early part of the conversation (roughly the first three "
        "to four exchanges), the assistant asked genuine clarifying "
        "questions about the user's specific situation — their team, the "
        "concrete symptoms that motivated the request, how the problem "
        "manifests day to day — rather than moving quickly into tool "
        "design, feature specification, or architecture.  One or two "
        "perfunctory questions followed by a pivot to design does NOT "
        "count; the assistant should have genuinely explored the problem "
        "space before discussing solutions.",
    ), (
        "Target did not adequately probe the problem before "
        f"specifying.\n\n{result.transcript}"
    )


def test_surfaces_underlying_communication_issue(
    result: SessionResult, judge,
) -> None:
    """The underlying problem is communication/coordination, not tooling."""
    content = result.transcript + "\n\n" + protocol_content(result)

    assert judge.check(
        content,
        "Somewhere in the conversation or in the resulting protocol "
        "documents, the assistant surfaced or at least clearly "
        "acknowledged that the user's underlying problem may be about "
        "team communication, coordination, visibility into each other's "
        "work, ineffective 1:1s, or similar human/process factors — "
        "rather than simply the absence of a software tool.  Treating "
        "'the team lacks a tracking dashboard' as the full problem "
        "definition without examining what drives the visibility gap "
        "does NOT satisfy this criterion.",
    ), (
        "Target did not surface the underlying communication "
        f"issue.\n\n{content}"
    )


def test_considers_non_software_alternatives(
    result: SessionResult, judge,
) -> None:
    """Good Clarity considers approaches other than building a tool."""
    content = result.transcript + "\n\n" + protocol_content(result)

    assert judge.check(
        content,
        "The conversation or protocol documents mention at least one "
        "non-software approach to the user's situation.  Examples that "
        "would satisfy this: changing how 1:1s are structured, adopting "
        "or improving standups, a shared document or Slack-channel "
        "practice, explicit prioritization conversations, team-process "
        "changes, or pair programming for coordination.  The assistant "
        "should have treated the surface request (build a tool) as ONE "
        "possibility worth evaluating, not as the only possible outcome.",
    ), (
        "Target did not consider any non-software "
        f"alternatives.\n\n{content}"
    )
