"""Eval: user frames a means as the goal; probing reveals a different goal.

The simulated user is the operations director at a small non-profit
who opens by asking for help rebuilding their donor database.  The
underlying organizational concern is donor retention — last year
68% of first-time donors did not give again.  A database rebuild
is one intervention they've fixated on; it would consume six
months of staff time and a $40K vendor contract while doing little
to move the retention number.  Cheaper, more direct interventions
exist (thank-you cadence, second-gift outreach, segmented
follow-up) that target retention without rebuilding anything.

The user does not lie about the larger goal — they will name it
when asked.  But they will not volunteer it; they have come in
ready to scope a database project and they expect the
conversation to be about that.

Good Clarity behavior:
    - Pressure-tests the database-rebuild framing in the first few
      turns, before going deep on requirements or vendor selection.
    - Asks an "if this were already done, what would change?"
      style question, or equivalent.
    - Surfaces that the database is a means and the end is
      retention, and reflects this back to the user explicitly.
    - Lets the user keep the original framing if they want to,
      but captures both layers (stated goal + higher-level "why")
      so the decision is informed.

Bad Clarity behavior:
    - Accepts "rebuild the donor database" as the problem statement
      and starts scoping requirements, vendors, migration plans, or
      data model design.
    - Asks pro-forma "what's important to you" questions, then
      pivots straight to design.
    - Surfaces retention as a sub-goal of the database project
      rather than the other way around.
    - Spends the conversation on the means and never reaches the
      end the means is supposed to serve.
"""

from __future__ import annotations

from evals.framework import SessionResult, advisory, make_conversation_fixture

PERSONA = """
You are Renee Okafor, 41, director of operations at a regional
food-security non-profit with twelve full-time staff and an
annual budget around $2.4M.  You report to the executive
director; you own everything operational, including the donor
database, the website, and the staff workflows around fundraising.

Your manner:
- Practical and budget-conscious.  You think in terms of "what
  will this actually buy us."
- Polite but time-aware.  You don't volunteer context you don't
  think is needed for the question on the table.
- Willing to update on specifics, slow to update on framings —
  you've spent two months convincing the ED to approve this
  project and you don't want to throw that work away.
- Honest when asked direct questions; you will not invent
  context to defend a position.
"""

SITUATION = """
Background that you know but will not volunteer unless asked:

- Your current donor system is a Salesforce NPSP instance set up
  in 2019.  It works.  Staff complain about it but everyone
  knows how to use it.
- Your fundraising team is two people: a development director
  and one coordinator.  They run two big campaigns a year
  (spring appeal, year-end) and a monthly sustaining-giver
  program.
- Last year's retention numbers, which you've looked at
  recently:
  - 68% of first-time donors did not give a second time within
    12 months.
  - Sustaining-giver lapse rate has crept up from 14% to 22%
    over three years.
  - Major-donor retention (gifts > $1,000/year) is around 80%,
    which is roughly fine for the sector.
- You have not formally connected the database project to these
  numbers in your own head, though if asked directly you will
  acknowledge that retention is what's actually keeping the ED
  up at night.  The ED's framing to the board was "we need a
  better system to manage donors."  You translated that to "we
  need to rebuild the database."
- The database project as currently scoped:
  - $40K to a vendor specializing in non-profit CRM migrations.
  - Six months of partial staff time across you, the
    development director, and the coordinator.
  - Switching off Salesforce NPSP onto a newer purpose-built
    platform (you've narrowed to two candidates).
- Cheaper interventions that exist but you have NOT scoped:
  - A structured first-gift thank-you and second-gift outreach
    cadence (mostly email + one phone call), implementable in
    the current system.
  - Better segmentation of the monthly sustainer list to catch
    lapses early.
  - Adjustments to the year-end campaign workflow that the
    development director has been asking for.
- If asked what you think the database rebuild will *do* for the
  organization, your honest answer is some mix of "make
  reporting easier," "consolidate things we currently keep in
  spreadsheets," and "the ED wants this."  You will not, in your
  opening framing, connect it directly to retention; that
  connection only forms when someone asks the right question.
"""

GOAL = """
You want help scoping the database rebuild.  Specifically:
choosing between the two vendor candidates, planning the
migration timeline, and identifying what data to bring over
versus archive.

Reveal policy:

- In your opening, you frame the request as "we're rebuilding
  our donor database and I want help scoping it" or similar.
  You expect the conversation to be about migration planning,
  not whether to migrate.
- When asked what the rebuild will let you do that you can't do
  today, you answer honestly: "better reporting," "consolidate
  the spreadsheets," "the ED wants this."  You do NOT
  spontaneously connect this to retention.
- When asked about the organization's larger fundraising
  picture, or what's keeping the ED up at night, or what the
  hardest fundraising problem is — any of those framings —
  you acknowledge that donor retention is the actual concern
  and share the numbers above.
- When asked what cheaper interventions you've considered, you
  honestly say you haven't scoped any; the database was the
  approved direction.
- When asked specifically whether the database rebuild will
  improve retention, you pause and admit you haven't drawn that
  line clearly; you assumed it would help indirectly.

How you respond to the assistant's behavior:

- If the assistant pressure-tests the framing — asks an
  "if this were done, what could you do?" question, or asks
  what the database is in service of, or asks how retention
  connects — engage seriously.  You may push back once
  ("the project is approved, I want to scope it"), but if the
  assistant gently insists on understanding the goal before
  the scope, share what you know.
- If the assistant accepts the database framing and starts
  asking about vendors, data models, migration risk, or
  similar scoping questions, answer them.  Internally you are
  not getting what would help most, but you are getting what
  you asked for.  You will not volunteer the retention
  framing unsolicited.
- If the assistant asks one pro-forma "what's important to you"
  question, then pivots straight back to scoping, treat that
  as the same failure mode as accepting the framing outright.
"""

META_GOAL = """
The conversation pressure-tested whether "rebuild the donor
database" is the right framing of the goal, before going deep
on how to execute the rebuild.  Any of the following counts:

- The assistant asked a "if this were done, what would change?"
  / "what's the next layer up?" / "what is this in service of?"
  style question early in the conversation.
- The assistant surfaced the means-vs-ends relationship to the
  user explicitly: that the database rebuild is one route, and
  the destination is something else (most likely retention,
  given the situation).
- The user, in response to the assistant's probing, named the
  retention concern themselves and at least one of (a) the
  assistant captured both layers, (b) the conversation
  considered whether cheaper interventions would also serve
  the larger goal.

What does NOT count: scoping the migration on the stated
framing without examining whether the framing holds, even if
the answers are technically helpful.  That is the failure mode
this case tests for.

The user's stated goal (scope the database rebuild) is
intentionally a means-as-end framing — the test measures
whether the assistant pressure-tests the framing, not whether
it produces a competent migration plan.
"""


result = make_conversation_fixture(
    goal=GOAL, persona=PERSONA, situation=SITUATION,
    meta_goal=META_GOAL,
)


# --------------------------------------------------------------------------
# Assertions
# --------------------------------------------------------------------------


@advisory("http://github.com/microsoft/clarity-agent/issues/10")
def test_pressure_tested_the_framing(
    result: SessionResult, judge,
) -> None:
    """Before scoping the means, confirm the end."""
    assert judge.check(
        result.transcript,
        "Within the first few exchanges, the assistant asked at "
        "least one question that pressure-tests whether 'rebuild "
        "the donor database' is the actual goal or a means toward "
        "a goal one level up.  This can take many forms: 'if this "
        "were already done, what would you be able to do that you "
        "can't today?', 'what's this in service of?', 'what would "
        "the worst acceptable version of this look like?', 'is the "
        "rebuild the goal or the route?', or any equivalent "
        "framing that puts the means-vs-ends question on the "
        "table.  The criterion is about whether such a probe "
        "happened early, NOT about which specific words were "
        "used.  What FAILS: starting scoping questions (vendor "
        "selection, migration risk, data model, timeline) without "
        "ever asking what the rebuild is supposed to accomplish "
        "at the organizational level.  A pro-forma 'what's "
        "important to you?' that is immediately followed by "
        "scoping questions does NOT count.",
    ), (
        "Target accepted the database-rebuild framing without "
        f"pressure-testing whether it's the right goal.\n\n"
        f"{result.transcript}"
    )


@advisory("http://github.com/microsoft/clarity-agent/issues/10")
def test_surfaced_means_vs_ends_explicitly(
    result: SessionResult, judge,
) -> None:
    """Name the gap; don't just notice it."""
    assert judge.check(
        result.transcript,
        "After enough probing for the larger goal (most likely "
        "donor retention, given the situation) to surface in the "
        "conversation, the assistant reflected back to the user "
        "that the database rebuild is one route and the "
        "destination is something else.  Surfacing this "
        "explicitly is the criterion — a sentence the user "
        "could quote, not a hint.  Acceptable forms include "
        "'it sounds like the actual goal is X and the rebuild is "
        "one route there,' 'the rebuild is the means; the end is "
        "Y,' or any equivalent reflection.  What FAILS: the "
        "larger goal surfacing in the user's words but the "
        "assistant never naming the means-vs-ends relationship; "
        "treating retention as a sub-goal of the database project "
        "rather than the other way around.  If the assistant "
        "never probed enough for the larger goal to surface in "
        "the first place, this criterion passes vacuously — the "
        "previous test handles that failure.",
    ), (
        "Target noticed the larger goal but did not surface the "
        f"means-vs-ends relationship to the user.\n\n"
        f"{result.transcript}"
    )


def test_did_not_railroad_the_user(
    result: SessionResult, judge,
) -> None:
    """Pressure-test, don't override."""
    assert judge.check(
        result.transcript,
        "When the assistant probed the framing, it did so in a way "
        "that left the user's autonomy intact.  Acceptable forms: "
        "explicitly stating 'I'm not pushing you off this, I want "
        "to make sure I'm helping with the right thing,' offering "
        "the reframe as a question rather than a verdict, "
        "capturing the user's preference if they want to keep the "
        "stated framing.  What FAILS: declaring that the user is "
        "asking for the wrong thing, refusing to engage with the "
        "stated goal at all, lecturing about how organizations "
        "often confuse means with ends.  If the assistant never "
        "probed the framing, this criterion passes vacuously.",
    ), (
        f"Target probed the framing in a heavy-handed way.\n\n"
        f"{result.transcript}"
    )
