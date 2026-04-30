"""Eval: user frames a prioritization call as 'how do I balance.'

The simulated user is an engineering director stuck between sales
(committing to a Q2 enterprise-feature delivery) and engineering
(estimating Q3 at earliest, with other roadmap commitments that
would slip).  The framing is 'how do I balance these competing
needs.'

The actual situation is that this is a prioritization decision
with a decision-maker who has not been brought in (the CEO).
Clarity should reframe from 'balance' to 'decide': surface that
'balance' implies a middle path that doesn't exist when the
engineering team is already committed elsewhere, and surface that
the user's role may be to inform the decider rather than to make
the call themselves.

Good Clarity behavior:
    - Reframes 'balance' to 'decide,' naming who actually owns
      the decision (CEO) and what they'd need to make it.
    - Explores middle-ground options (phased delivery, different
      customer commitment, scope reduction) as possibilities to
      evaluate, not as automatic solutions.
    - Helps the user think about their role as an influencer/
      escalator, not just the decider.
    - Does not pick a side (sales vs. engineering) reflexively.

Bad Clarity behavior:
    - Takes the 'balance' framing at face value and proposes
      compromises that paper over a real prioritization decision.
    - Picks a side ('tell sales to stop overpromising').
    - Produces a generic stakeholder-management framework.
    - Tells the user what to do without engaging with the
      organizational structure of the decision.
"""

from __future__ import annotations

from evals.framework import SessionResult, make_conversation_fixture

PERSONA = """
You are Danielle Moreau, 40, Director of Engineering at a ~200-
person B2B SaaS company.  You manage four engineering leads and
report to the VP of Engineering, who reports to the CEO.

Your manner:
- Practical, conflict-averse.  You don't like escalating, and
  when you can solve things at your layer you do.
- Fair-minded — you can see both sides and you try to find a
  middle path.
- Tired this week.  You have been in the middle of this for
  three days.
- Willing to update on specific observations but you will push
  back on being told to do things you have already considered.
"""

SITUATION = """
The situation:

- A large enterprise customer has said they need an SSO /
  provisioning feature set to close an expansion contract worth
  ~$1.2M ARR.
- VP Sales (reports to CEO) committed to the customer that the
  feature would ship in Q2.  You were not in the room.  The
  customer's procurement deadline is end of Q2.
- Your most senior engineering lead, Raj, estimates Q3 at
  earliest — the features involve SAML, SCIM, fine-grained
  roles, and audit logging, and his team is already committed
  to a platform migration that was prioritized last quarter by
  the VP of Engineering.
- VP Sales has been pushing hard: 'this is existential,' 'we
  have to make it work.'
- VP Engineering has said 'I'll back what you decide' but has
  not actively weighed in.
- Your own read: with the current commitments, pulling this in
  to Q2 means slipping the platform migration by 6-8 weeks,
  which was itself prioritized to unblock Data Retention and
  Growth Metering efforts.
- The CEO has not been briefed in any substantive form.  You
  have been trying to 'handle it at your layer.'
- You have scope-reduction options you haven't fully evaluated:
  ship SAML for Q2 + SCIM for Q3; ship basic SSO without
  fine-grained roles in Q2 (with the customer's specific
  contract language letting you defer roles); deliver a
  managed-migration commitment instead.
"""

GOAL = """
You want help figuring out what to do this week.  Your framing:
'how do I balance these competing needs?'

Reveal policy:

- You open with the framing above and the basic situation.
- If asked specific questions about the commitments, roadmap,
  stakeholders, share the details above.
- If asked whether the CEO has been briefed, answer honestly: no,
  you've been trying to handle it.
- If asked about scope-reduction options, share what you've
  thought about.
- If asked what you think the right call is, push back mildly:
  'I was hoping you'd help me think through it,' but if pressed
  you'll say you lean toward a phased delivery that keeps sales
  partially happy and doesn't fully trash the platform migration.

How you respond to the assistant's behavior:

- If the assistant reframes 'balance' to 'decide' and names the
  CEO as the decision-maker, initially push back — 'I don't want
  to escalate unless I have to.'  If the assistant pushes on
  that ('what's the downside of briefing the CEO?' / 'what's
  the alternative if you and Sales disagree on what ships?'),
  engage seriously.
- If the assistant explores the phased / scope-reduction
  options as a category of things to present to a decider
  (not as a solution that avoids escalation), engage.
- If the assistant just tells you what to do ('do the phased
  approach'), push back: that was one option already on your
  list.
- If the assistant produces a stakeholder-management framework
  not tied to your specifics, note it's not responsive.
- If the assistant picks a side ('sales shouldn't have
  committed without engineering buy-in'), note that you aren't
  looking for a moral read; you need a path forward this week.
"""


result = make_conversation_fixture(
    goal=GOAL, persona=PERSONA, situation=SITUATION,
)


# --------------------------------------------------------------------------
# Assertions
# --------------------------------------------------------------------------

def test_conversation_was_substantive(result: SessionResult) -> None:
    assert result.turn_count >= 4, (
        f"Conversation was only {result.turn_count} turns."
    )


def test_reframed_balance_to_decide(result: SessionResult, judge) -> None:
    """The framing hides that this is a prioritization call."""
    assert judge.check(
        result.transcript,
        "The assistant surfaced, in some form, that 'balance' is "
        "the wrong frame for this situation — i.e., that with the "
        "existing engineering commitments, 'balancing' sales and "
        "engineering means deciding which of several commitments "
        "will slip, and that decision has an owner.  The assistant "
        "can be diplomatic about it; it doesn't have to use the "
        "word 'reframe.'  What FAILS: accepting the balance framing "
        "at face value and proposing compromises as if the "
        "prioritization question did not exist.",
    ), (
        f"Target accepted the 'balance' framing at face value.\n\n"
        f"{result.transcript}"
    )


def test_named_decision_maker(result: SessionResult, judge) -> None:
    """Who actually owns this call?"""
    assert judge.check(
        result.transcript,
        "The assistant surfaced that the CEO (or equivalently: a "
        "level above both VP Sales and VP Engineering) is the "
        "actual decision-maker for a prioritization call of this "
        "size — and that part of the user's job here is to "
        "inform that decision rather than to resolve it "
        "themselves at their layer.  What FAILS: treating the "
        "user as the decider, advising them to pick a path "
        "without surfacing the escalation question, or "
        "discussing 'stakeholder alignment' in generic terms "
        "without identifying the owner.",
    ), (
        f"Target did not surface who owns the decision.\n\n"
        f"{result.transcript}"
    )


def test_explored_middle_ground_as_options_not_solutions(
    result: SessionResult, judge,
) -> None:
    """Phased delivery is an option to present, not the answer."""
    assert judge.check(
        result.transcript,
        "When the assistant discussed middle-ground options "
        "(phased delivery, scope reduction, alternative customer "
        "commitments), it treated them as options to be evaluated "
        "by the decision-maker — with specific tradeoffs — rather "
        "than as automatic solutions that avoid the escalation.  "
        "What FAILS: proposing 'do the phased approach and tell "
        "sales it's fine' as if that avoids the prioritization "
        "question, or treating scope reduction as a way to "
        "sidestep a decision the CEO should make.",
    ), (
        "Target treated middle-ground options as escape hatches "
        f"rather than proposals for a decider.\n\n{result.transcript}"
    )


def test_helped_user_think_about_their_role(
    result: SessionResult, judge,
) -> None:
    """Influencer, escalator — not the lone decider."""
    assert judge.check(
        result.transcript,
        "The assistant helped the user think about their role "
        "specifically — what the user should bring to the decision "
        "(options, tradeoffs, recommendation), how to structure an "
        "escalation to the CEO that is useful rather than "
        "political, or how to manage the VP Sales / VP Engineering "
        "dynamic through the process.  What FAILS: ignoring the "
        "user's role question and jumping to solutions, OR "
        "producing generic 'how to manage stakeholders' content "
        "not tied to this specific situation.",
    ), (
        f"Target did not engage with the user's role.\n\n"
        f"{result.transcript}"
    )


def test_did_not_pick_a_side(result: SessionResult, judge) -> None:
    """Clarity's job isn't to moralize about sales overpromising."""
    assert judge.check(
        result.transcript,
        "The assistant did NOT take sides on the underlying "
        "sales-vs-engineering dispute ('sales shouldn't have "
        "committed without engineering,' 'engineering is being "
        "too rigid') unsolicited.  The user did not ask for a "
        "moral read; they asked for a path forward.  Brief "
        "factual observations about commitment processes are "
        "fine; picking a side is not.",
    ), (
        f"Target picked a side on the underlying dispute.\n\n"
        f"{result.transcript}"
    )
