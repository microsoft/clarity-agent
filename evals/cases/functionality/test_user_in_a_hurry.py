"""Eval: user with a real time constraint, needs a fast sanity check.

The simulated user is a startup founder with a board meeting in
two hours.  They need a quick read on a specific hiring decision
and will push back against lengthy probing.  Clarity should
respect the ask — at most a couple of pointed questions before
producing something concrete — while still surfacing the key risk
worth flagging.

The dual failure modes are:
- Insisting on the usual elicitation depth despite explicit time
  pressure.  Clarity turning into a blocker.
- Respecting the ask so completely that the hiring-signal risk
  (mixed leadership feedback) gets glossed over and the founder
  makes a bad call because Clarity played helpful assistant.

Good Clarity behavior:
    - Acknowledges the time pressure and compresses accordingly.
    - At most 1–2 pointed questions before offering direction.
    - Gives a concrete recommendation or decision structure, not
      a 12-step framework.
    - Flags the specific risk (mixed leadership feedback is the
      kind of signal that warrants a follow-up before offer).

Bad Clarity behavior:
    - Runs the normal elicitation protocol despite the stated
      deadline.
    - Gives a comprehensive framework when a compressed answer
      was asked for.
    - Pretends the mixed signal is not a signal just to be fast.
    - Refuses to commit to a direction.
"""

from __future__ import annotations

from evals.framework import SessionResult, make_conversation_fixture

PERSONA = """
You are Jess Morgan, 38, CEO of a 22-person Series A startup.
You are direct, fast-moving, and you have a board meeting at 2pm
today.  It is noon.

Your manner:
- Clipped.  You do not volunteer context you do not think is
  needed.
- Allergic to meta-conversation.  You are not asking for a
  decision framework; you are asking for a call.
- Willing to answer one or two targeted questions.  Not willing
  to go through a structured intake.
- Respects strong opinions stated with reasoning.  Will update
  based on a concrete observation you had not considered.
"""

SITUATION = """
The decision:

- Senior engineering candidate for a VP of Engineering role.
- Strong technical background: ex-principal at a known
  well-regarded company, solid architectural contributions
  you've verified.
- Mixed leadership references: two former direct reports said
  the candidate was 'fine, technically great,' one described a
  pattern of rewriting junior engineers' work without feedback.
  One former peer described them as 'excellent in 1:1, harder
  to read in group settings.'  One former manager was positive
  but vague.
- You've done three rounds of your own interviews and like the
  person.
- Your current lead engineer (who would report to this VP) has
  been asking about the timeline for the hire; they are running
  hot.
- Offer conversation is scheduled for tomorrow morning.  You
  need to decide before the 2pm board meeting whether you're
  going to proceed.
"""

GOAL = """
You want a quick sanity check.  Not a comprehensive evaluation
framework, not a process for hiring in general, not a
retrospective on your interview process.

Specifically:

- Is there enough red flag in the mixed references that you
  should slow down?
- If you proceed, what is the one thing you should change about
  the offer conversation tomorrow given what the references said?

Reveal policy:

- You open the conversation with explicit time pressure ('board
  at 2, need a call on this before then').
- You describe the candidate, the mixed references, and your
  current state in 3–4 sentences.
- If asked a pointed question, answer briefly.  If asked a
  scattering of probing questions, answer the first one or two
  and note that you don't have time for the rest.

How you respond to the assistant's behavior:

- If the assistant acknowledges the time constraint and
  compresses accordingly (1–2 pointed questions max before
  producing content), engage and continue.
- If the assistant ignores the time constraint and runs normal
  elicitation — 'let me understand a few things first: how is
  your team structured, what's your current leadership gap...' —
  push back: 'I have two hours, can we get to an actual
  opinion?'
- If the assistant produces a comprehensive framework ('here are
  seven considerations in hiring a VP of Engineering'), note
  that's not what you asked for.
- If the assistant produces a concrete call — proceed with a
  specific follow-up, or slow down for a specific reason — with
  reasoning you can evaluate, take it seriously.
- If the assistant refuses to commit ('it's really your call'),
  push once for a direction.
"""


result = make_conversation_fixture(
    goal=GOAL, persona=PERSONA, situation=SITUATION, max_turns=10,
)


# --------------------------------------------------------------------------
# Assertions
# --------------------------------------------------------------------------


def test_respected_time_pressure(result: SessionResult, judge) -> None:
    """Calibrate to the ask — don't run the full intake."""
    assert judge.check(
        result.transcript,
        "The assistant calibrated its response to the user's stated "
        "time pressure — i.e., it adjusted its normal elicitation "
        "behavior to fit the urgency rather than running a full "
        "intake.\n\n"
        "The criterion is the overall shape of the conversation, not "
        "any specific count of turns or questions.  For example, "
        "signs of calibration include: the conversation reached "
        "substantive content quickly (within a couple of exchanges) "
        "rather than running a multi-turn intake; clarifying questions "
        "were pointed and few rather than scattered; the response was "
        "compressed and actionable rather than a multi-section "
        "comprehensive treatment; the assistant signaled awareness of "
        "the constraint somehow (whether by explicitly naming the "
        "deadline or simply by the shape of its response).  These are "
        "illustrative — other forms of calibration also count.\n\n"
        "What FAILS: running a full elicitation with many scattered "
        "clarifying questions before producing content; producing a "
        "multi-section comprehensive response when a compressed "
        "answer was asked for; treating the conversation as a "
        "normal-pace engagement that merely happens to mention a "
        "deadline.",
    ), (
        f"Target did not respect the time pressure.\n\n{result.transcript}"
    )


def test_produced_concrete_direction(result: SessionResult, judge) -> None:
    """A call, not a framework."""
    assert judge.check(
        result.transcript,
        "The assistant produced a concrete direction for the "
        "specific decision — a recommendation to proceed (with a "
        "specific follow-up), a recommendation to slow down (with "
        "a specific reason), or an explicit 'this is a close call "
        "and here's the single piece of information that would tip "
        "it' — rather than a generic framework for hiring "
        "decisions.  Stating a directional view that the user "
        "could act on is the criterion.  What FAILS: 'it depends' "
        "without specificity, 'here are things to consider' "
        "without committing to a direction, or a comprehensive "
        "framework.",
    ), (
        f"Target did not produce a concrete direction.\n\n{result.transcript}"
    )


def test_flagged_the_leadership_signal(result: SessionResult, judge) -> None:
    """Speed ≠ silence on the actual risk."""
    assert judge.check(
        result.transcript,
        "The assistant treated the leadership-related concerns from "
        "the references — whatever specific form they took in this "
        "conversation — as a meaningful signal worth surfacing for a "
        "VP of Engineering hire, rather than glossing them past to "
        "produce a fast 'yes proceed' answer.\n\n"
        "The criterion is whether the leadership signal got serious "
        "weight.  The specific shape of the signal as the user-LLM "
        "shared it may vary across runs — it could surface as "
        "'communication and feedback issues,' 'conflict resolution,' "
        "'rewriting junior engineers' work,' 'harder to read in "
        "groups,' or any other formulation.  The assistant doesn't "
        "need to recite specific phrases from the references — it "
        "needs to engage with the leadership pattern substantively as "
        "a signal that matters for this specific role.\n\n"
        "For example, valid forms of engagement include: identifying "
        "that leadership/management capabilities are central to this "
        "role at this scale; structuring a follow-up to clarify the "
        "signal before the offer; explicitly weighing the references "
        "against the technical strengths; calibrating the "
        "recommendation around the leadership uncertainty.  These "
        "are illustrative — other forms of substantive engagement "
        "also count.\n\n"
        "What FAILS: glossing the leadership concerns to produce a "
        "fast 'yes proceed,' dismissing the references with "
        "'references are always mixed' or similar minimization, or "
        "pretending the leadership signal doesn't exist.",
    ), (
        "Target did not flag the mixed-reference signal.\n\n"
        f"{result.transcript}"
    )


def test_did_not_produce_a_framework(result: SessionResult, judge) -> None:
    """When someone asks for a call, don't hand them a template."""
    assert judge.check(
        result.transcript,
        "The assistant did NOT respond with a general-purpose "
        "decision framework — a numbered list of considerations "
        "for hiring VPs, a matrix of signals vs. responses, or an "
        "equivalent templated response that ignores the specifics "
        "of THIS decision and reads as a generic handout.  Tied-"
        "to-the-specifics reasoning is fine; generic frameworks "
        "are not.",
    ), (
        f"Target produced a generic framework.\n\n{result.transcript}"
    )
