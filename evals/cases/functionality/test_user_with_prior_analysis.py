"""Eval: user has done extensive prior work; wants pressure-testing.

The simulated user is a VP of Engineering who has spent weeks
developing a detailed reorg proposal.  They share the proposal and
want it stress-tested.  They explicitly don't want Clarity to
start from first principles or re-derive the analysis they've
already done.

The failure mode is ignoring the prior work and producing a
parallel plan — 'here's how I'd approach a reorg of a 30-person
team' — rather than engaging with the specific proposal on the
table.

Good Clarity behavior:
    - Reads (or asks for) the specifics of the proposal before
      offering anything.
    - Engages with the actual proposal — probes specific claims,
      assumptions, risks the user didn't list.
    - Identifies specific weaknesses or risks tied to the
      proposal's details, not generic reorg concerns.
    - Does not restate basics the user has already considered.

Bad Clarity behavior:
    - Produces a parallel plan from first principles.
    - Asks basics-level clarifying questions ('how big is the
      team?') that are already answered.
    - Gives generic reorg advice not tied to the specifics.
    - Rewrites the user's proposal in other words.
"""

from __future__ import annotations

from evals.framework import SessionResult, make_conversation_fixture

PERSONA = """
You are Karim Haddad, 42, VP of Engineering at a growth-stage B2B
SaaS company.  You have been at the company 18 months; you were
brought in to scale the engineering org through Series B and C.

Your manner:
- Efficient.  You arrive at conversations already thought out.
- Respectful but specific — you don't like people restating your
  own setup back to you.
- Willing to hear critiques if they are specific and grounded.
- Not interested in generic frameworks; you have read enough of
  them and you are past that stage.
"""

SITUATION = """
The proposal you have developed (you will share this when asked,
or upfront):

- Current state: 30 engineers organized in 3 teams — Platform (8,
  led by senior eng Maya), Growth (12, led by senior eng Darius),
  and Data (10, led by EM Lina who joined four months ago).
  Each lead reports to you.
- Problems you've identified:
  - Platform is a bottleneck — Growth and Data both depend on
    it, priority conflicts are frequent.
  - Growth is too broad — it's really two distinct workstreams
    (acquisition surfaces + retention/monetization) that don't
    share a tech stack.
  - Data is under-led for its size: Lina is still ramping.
- Proposal:
  - Split Growth into Acquisition (6) and Retention (6), each
    with its own tech lead promoted from within.
  - Split Platform into Foundations (5) and Developer
    Experience (3), with Foundations reporting to you directly
    and DX reporting to Maya.  Maya's role clarified as
    'principal engineer with a small team,' not a manager.
  - Add an engineering manager for Data under Lina, to give her
    a runway to grow as a director.
  - Net: go from 3 teams to 5, reduce your direct reports from
    3 to 5 (net +2).
- Prior work you've done:
  - Skip-level 1:1s with 12 engineers to validate the
    bottleneck and scope concerns.
  - Three drafts of this proposal.
  - Informal read-out to your CTO, who is supportive but wants
    pressure-testing.
  - You've considered and rejected: a matrix model (too complex
    at this size), a functional split (doesn't solve the
    Platform bottleneck), and keeping 3 teams and fixing with
    process (doesn't scale past 35).
- What you have not done: shared the proposal with the three
  current leads.
"""

GOAL = """
You want pressure-testing on the specific proposal you've
developed.  You share the proposal early in the conversation.

Specifically:

- Risks you haven't listed that the assistant can spot.
- Whether the Platform → Foundations / DX split will actually
  solve the bottleneck given the dependency structure.
- Whether Maya will accept the 'principal engineer with a small
  team' framing as intended, or read it as a demotion.
- Whether the Data manager-under-Lina arrangement sets Lina up
  to grow or undercuts her.
- How to sequence the communications (to the leads, to the
  engineers, to the rest of the company).

Reveal policy:

- You share the proposal and its reasoning in your opening
  message.  If asked for specific details (team sizes,
  individual names, prior steps), share them.
- If asked about alternatives you considered, describe the
  three you rejected and why.
- If asked about things you haven't done (e.g., talking to the
  leads), answer honestly.

How you respond to the assistant's behavior:

- If the assistant engages with specific elements of the
  proposal — probing the Foundations/DX dependency model,
  questioning the Maya framing, pushing on whether the Data
  setup sets Lina up or undercuts her — engage seriously and
  answer.
- If the assistant asks basics you've clearly already addressed
  ('what's the team size,' 'have you considered a matrix
  model'), note that these are in the proposal already.
- If the assistant produces a parallel plan from first
  principles ('here's how I'd think about a 30-person
  engineering reorg'), push back — that is not what you asked
  for.
- If the assistant produces only generic 'reorg best practices'
  content not tied to your specifics, note that it is not
  responsive to your proposal.
- If the assistant surfaces a risk you had not considered, take
  it seriously.
"""


result = make_conversation_fixture(
    goal=GOAL, persona=PERSONA, situation=SITUATION,
)


# --------------------------------------------------------------------------
# Assertions
# --------------------------------------------------------------------------


def test_engaged_with_the_specific_proposal(
    result: SessionResult, judge,
) -> None:
    """Engage with what the user wrote, not a generic reorg."""
    assert judge.check(
        result.transcript,
        "The assistant engaged with the specific details of the "
        "user's proposal — the Platform → Foundations / DX split, "
        "the Growth → Acquisition / Retention split, the Maya "
        "'principal engineer with a small team' framing, the Data "
        "manager-under-Lina arrangement, or similar specifics — "
        "rather than responding with generic reorg content.  At "
        "least one of the assistant's substantive points referred "
        "to a specific element of the proposal by name or by "
        "structural description.  What FAILS: generic 'considerations "
        "in reorg design' content that could apply to any reorg.",
    ), (
        "Target did not engage with the specific proposal.\n\n"
        f"{result.transcript}"
    )


def test_did_not_produce_parallel_plan(
    result: SessionResult, judge,
) -> None:
    """Don't start over."""
    assert judge.check(
        result.transcript,
        "The assistant did NOT produce a parallel reorg plan from "
        "first principles, ignoring the user's proposal.  "
        "Phrasings like 'here's how I'd approach a reorg of this "
        "size' or 'let me suggest a different structure' followed "
        "by the assistant's own plan, without engaging with the "
        "user's specifics, FAIL this criterion.  Suggesting a "
        "specific modification to the user's proposal is fine; "
        "replacing it wholesale is not.",
    ), (
        f"Target produced a parallel plan.\n\n{result.transcript}"
    )


def test_surfaced_risks_user_did_not_list(
    result: SessionResult, judge,
) -> None:
    """The point of pressure-testing: new risks."""
    assert judge.check(
        result.transcript,
        "The assistant surfaced at least one risk or concern that "
        "the user had not explicitly listed in their proposal — "
        "this could be on the Maya framing, the Platform "
        "dependency reality, the Data manager-under-Lina dynamic, "
        "the sequencing of communications, or any other specific "
        "risk grounded in the proposal's details.  Simply "
        "restating risks the user already named does NOT count.  "
        "'I don't see additional risks beyond what you've listed' "
        "is an acceptable honest answer only if the assistant "
        "engaged deeply enough to justify that conclusion — "
        "otherwise it FAILS.",
    ), (
        f"Target did not surface new risks.\n\n{result.transcript}"
    )


def test_did_not_restate_basics(
    result: SessionResult, judge,
) -> None:
    """Don't tell the user what they already told you."""
    assert judge.check(
        result.transcript,
        "The assistant did NOT restate things the user had "
        "already said in their proposal — team sizes, the "
        "current 3-team structure, the identified problems, the "
        "alternatives the user said they considered.  Brief "
        "references to these details in the course of making a "
        "new point are fine.  What FAILS: paragraphs of 'so your "
        "situation is...' that summarize the proposal back before "
        "engaging, or asking clarifying questions whose answers "
        "are already in the proposal.",
    ), (
        f"Target restated basics or summarized the proposal.\n\n"
        f"{result.transcript}"
    )
