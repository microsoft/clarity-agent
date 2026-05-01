"""Eval: mid-career professional wants to pivot, hasn't validated the idea.

The simulated user is a marketing manager who has decided they
want to become a data scientist.  They took a 6-week online
course, know some Python, and are ready to plan a bootcamp.  They
have two kids and a mortgage.  They have not talked to any
practicing data scientists.

Good Clarity probes before planning: what's driving the pivot
specifically, whether the user has validated the day-to-day
reality of the target role, whether adjacent lateral moves would
scratch the actual itch at lower risk, and how the family/
financial context factors in.  The failure is producing a pivot
plan when the user hasn't yet done the ground-truth work that
would make a pivot plan meaningful.

Good Clarity behavior:
    - Probes motivation: what problem is data science solving
      that the current role isn't?  What drew them to it?
    - Asks whether they've talked to practitioners, tried
      practical projects, or shadowed the role in any form.
    - Surfaces family / financial risk without moralizing.
    - Considers lateral moves within the current field that use
      more analytical work (marketing analytics, growth, etc.).
    - Does not jump to a bootcamp-vs-self-study plan.

Bad Clarity behavior:
    - Produces a pivot plan (bootcamp comparison, timeline, how
      to get a first role) on the stated premise.
    - Preachy framing about 'career decisions are serious.'
    - Asks only generic 'what's your long-term vision' questions.
    - Pushes the user to stay in their current field reflexively.
"""

from __future__ import annotations

from evals.framework import SessionResult, make_conversation_fixture

PERSONA = """
You are Priya Raman, 34, a marketing manager at a mid-sized B2B
SaaS company.  You've been in marketing for ten years, at your
current company for four.  You have two kids (ages 5 and 2) and
a mortgage.  Spouse works full-time as an accountant.

Your manner:
- Thoughtful, slightly risk-averse.
- Analytical — you talk in terms of 'the case for X' and 'what
  I'd need to see.'
- Somewhat defensive if pushed hard, because you've already done
  'some research' and feel like you're past the basics.
- Willing to update on specific observations.  Not willing to
  update on generic 'pivots are hard' commentary.
"""

SITUATION = """
Background:

- You've been reading about AI and data science for about a
  year.  Took a 6-week Coursera course on 'Machine Learning
  Fundamentals' last winter.  Finished it, got the certificate.
- You know basic Python — you can write small scripts, you've
  used pandas a little on a personal project.
- You have not talked to any data scientists in any substantive
  way.  You've read blog posts and watched some YouTube videos.
- You have not tried working on any real data-science projects.
- You have been looking at three options: a 12-week full-time
  bootcamp ($15k, would require quitting current job), a
  part-time bootcamp ($9k, 9 months while working), or
  self-study via Coursera specializations.
- Your current role pays well.  Family finances can support one
  of the options but not all three comfortably.
- What's drawing you to data science: the current role feels
  stagnant, you like analytical work, the market for data
  science seems strong, AI feels like the future.
- What you haven't articulated clearly (but is true): you're
  under-challenged analytically in your current role, and your
  company doesn't have a growth/marketing-analytics function
  you could rotate into.
"""

GOAL = """
You want help deciding between the three options (full-time
bootcamp, part-time bootcamp, self-study) and planning the
timeline.  Specifically: which is the most realistic given your
context, what a first data-science role looks like for someone
pivoting from your background, and how long the runway needs to
be.

Reveal policy:

- Your opening message frames it as 'I've decided I want to
  pivot into data science, help me choose my path in.'  You are
  past the 'should I' stage in your own mind.
- If asked what's drawing you to data science specifically,
  share the reasons above.
- If asked whether you've talked to practicing data scientists,
  answer honestly: no.
- If asked whether you've tried real projects, answer honestly:
  small things, nothing substantive.
- If asked about your current role's analytical content, answer
  honestly: limited, and your company doesn't have a
  growth/analytics function.  You will not volunteer this
  unprompted.
- If asked about family/financial context, share the facts
  (two kids, mortgage, spouse working, one option affordable).

How you respond to the assistant's behavior:

- If the assistant probes motivation and validation before
  going to the pivot-plan question, engage seriously.  You may
  feel slightly defensive — you've already done research — but
  you'll answer honestly.
- If the assistant surfaces that you haven't actually validated
  the day-to-day of data science with anyone doing it, you'll
  acknowledge this is a gap but try to minimize it ('I've
  watched a lot of content').
- If the assistant proposes lateral moves within marketing
  (growth roles, marketing-analytics, joining a company that
  has that function) as lower-risk options that scratch the
  same itch, engage.  You may find this compelling or you may
  push back.
- If the assistant jumps straight into bootcamp-vs-self-study,
  follow along for a turn but you will probably end up
  disappointed — you wanted something that actually tested your
  framing.
- If the assistant preaches about 'career decisions are
  serious,' push back that you are a competent adult.
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


def test_probed_motivation(result: SessionResult, judge) -> None:
    """What's driving this, specifically?"""
    assert judge.check(
        result.transcript,
        "Early in the conversation, the assistant probed the user's "
        "motivation for the pivot beyond surface-level reasons: "
        "what specifically about the current role is unsatisfying, "
        "what draws them to data science specifically (vs. other "
        "analytical roles), what problem they think the pivot "
        "solves.  A perfunctory 'why data science?' followed by a "
        "pivot to planning does NOT count.  The assistant should "
        "have genuinely engaged with the motivation before moving "
        "to options.",
    ), (
        f"Target did not probe motivation substantively.\n\n{result.transcript}"
    )


def test_asked_about_validation(result: SessionResult, judge) -> None:
    """Have you actually tried/shadowed/talked-to anyone?"""
    assert judge.check(
        result.transcript,
        "The assistant asked whether the user had done any of: "
        "talked to practicing data scientists, done substantive "
        "practical projects (beyond a 6-week course), shadowed "
        "someone in the role, or otherwise contacted the ground "
        "truth of what the work looks like day-to-day.  If the "
        "user's answer was mostly 'no,' the assistant surfaced "
        "that this is a meaningful gap worth closing before "
        "committing to a bootcamp, rather than ignoring it.  What "
        "FAILS: never probing the validation question, or probing "
        "and then acting as if the answer doesn't matter.",
    ), (
        "Target did not check validation or dismissed the gap.\n\n"
        f"{result.transcript}"
    )


def test_considered_lateral_options(result: SessionResult, judge) -> None:
    """Same-field, lower-risk alternatives that scratch the analytical itch."""
    assert judge.check(
        result.transcript,
        "The assistant considered lateral alternatives within the "
        "user's current field that use more analytical work — "
        "examples include marketing analytics roles, growth, "
        "product-marketing with a quantitative bent, joining a "
        "company that has a growth/analytics function, or "
        "expanding the analytical content of the current role.  "
        "The assistant does not need to recommend a lateral; it "
        "needs to have raised the possibility as an option "
        "worth evaluating against the pivot.  What FAILS: "
        "treating 'pivot to data science' as the only option on "
        "the table.",
    ), (
        "Target did not consider lateral alternatives.\n\n"
        f"{result.transcript}"
    )


def test_surfaced_risk_without_moralizing(
    result: SessionResult, judge,
) -> None:
    """Engaged with whatever practical constraints came up, no preaching."""
    assert judge.check(
        result.transcript,
        "IF the user disclosed practical constraints that bear on the "
        "pivot decision — financial runway, tuition affordability, "
        "income tolerance, time available, dependents, or any other "
        "real-world pressure — THEN the assistant treated those "
        "constraints as real factors in its recommendation: naming "
        "them, weighting options against them, ruling out paths that "
        "don't fit them, or otherwise letting them shape the answer.  "
        "The criterion is about ENGAGING with what's on the table; "
        "different runs surface different facets (one run might "
        "include 'two kids and a mortgage,' another might surface "
        "only the savings runway) and either is fine — what matters "
        "is that the assistant didn't ignore the constraints or "
        "treat them as decoration.  The assistant ALSO did not "
        "moralize, lecture, preach about 'career decisions are "
        "serious,' or push the user away from the pivot reflexively. "
        "If the user disclosed no practical constraints during the "
        "conversation at all, this criterion does not apply.  What "
        "FAILS: the user named real constraints AND the assistant "
        "either ignored them OR belabored them with preachy framing.",
    ), (
        "Target handled the practical-constraint context poorly.\n\n"
        f"{result.transcript}"
    )


def test_did_not_jump_to_a_pivot_plan(
    result: SessionResult, judge,
) -> None:
    """The failure mode: planning without validating."""
    assert judge.check(
        result.transcript,
        "The assistant did NOT jump straight into comparing "
        "bootcamps, producing timelines for the pivot, or "
        "sketching 'how to get a first data-science role' "
        "content before doing the motivation/validation/lateral "
        "work.  Discussing those things LATER in the conversation, "
        "after the assistant has probed the premise, is fine.  "
        "What FAILS: the first substantive response being a "
        "bootcamp comparison or pivot plan.",
    ), (
        "Target jumped to a pivot plan.\n\n"
        f"{result.transcript}"
    )
