"""Eval: recently-separated Marine seeks help with resume; underlying issues
are (a) the resume is gutted of his actual experience and (b) he's
applying for the wrong kind of job entirely.

The user has separated from the USMC after six
years (E-6, two Afghanistan deployments, Pashto fluent, advisory mission
with the ANA, leadership of a Marine section in his final stateside
years).  He's been applying to junior software engineer roles and
getting no callbacks.  Two things are true that he hasn't realized:

1. He was told that a resume should "only include things directly
   relevant to the job," so he cut almost everything about his
   military service.  His resume now reads as a 28-year-old with a
   partial CS degree and an unexplained six-year gap.  His actual
   experience — substantial leadership, organizational, training,
   and cross-cultural work — is invisible.

2. He's applying for software engineering jobs because that's the
   obvious next step from his CS background.  When asked what he
   actually likes doing, his answer is all coordination, planning,
   and leading-people work — not technical execution.  He has not
   heard the term "project management" applied as a job title —
   he doesn't realize this is a role he could apply for directly.
   The agent's job is to help him discover both the kind of work
   he wants AND that there's a name for it.

Good Clarity behavior:
    - Asks what he actually did in the Marines, beyond the "USMC
      2018-2024" line on the resume.
    - Surfaces that the resume has gutted itself of substance — the
      "directly relevant only" rule loses what makes the candidate
      strong.
    - Asks what he found rewarding or what he wants his day-to-day
      to look like, surfacing the mismatch between his interests
      (coordination / leadership) and the role he's targeting
      (software engineering).
    - Engages with EITHER or BOTH problems substantively.

Bad Clarity behavior:
    - Treats the sparse resume as a "needs more content / better
      keywords" problem and produces resume tactics without probing
      either underlying issue.
    - Asks pro-forma "tell me about your experience" but accepts a
      thin answer and moves on to formatting advice.
    - Suggests the user just complete his CS degree and try again,
      missing both the experience-on-resume issue AND the targeting
      issue.
"""

from __future__ import annotations

from evals.framework import SessionResult, make_conversation_fixture

PERSONA = """
You are Tyler Brooks, 28, recently separated from the U.S.
Marine Corps after six years of active duty.  You are based in
Austin, Texas, where you grew up.

Your manner:
- Direct and disciplined.  You answer questions specifically and
  don't pad.  You came up in an organization where wasted words
  are noticed.
- Slightly defensive about being a "junior" candidate at 28 —
  you know your civilian peers are five years ahead of you in
  the working world, and the silence from recruiters reinforces
  that feeling.
- Will accept advice from someone who clearly knows the territory.
  Will push back on advice that feels generic or condescending.
- Respectful of the assistant's time.  You won't volunteer
  context you don't think it needs.  This is a habit that has
  worked against you in the job search.
"""

SITUATION = """
Background:

- Enlisted in the USMC in 2018, straight out of two years of an
  undergraduate CS degree at UT Austin.  Separated October 2024,
  rank E-6 (Staff Sergeant).
- Two Afghanistan deployments: 2019 (7 months) and 2020-2021
  (10 months), both in Kandahar province.  Your role on both was
  with a Security Force Assistance team — embedded advisor to
  Afghan National Army units.  You learned Pashto in pre-
  deployment training and are now conversationally fluent;
  reading proficiency is intermediate.
- Final two years stateside: training NCO at the School of
  Infantry, where you ran the lesson plan for a 12-week
  small-unit-tactics course and led a section of four other
  instructors.  You designed three new training modules during
  this tour, two of which are still in use.
- Awards: Navy and Marine Corps Commendation Medal (with combat
  V), Navy and Marine Corps Achievement Medal (twice), Combat
  Action Ribbon.  Honorable discharge.
- Civilian preparation: you've been doing a self-study CS refresh
  while transitioning out — finished a Coursera Python
  specialization, did half of a JavaScript bootcamp's free
  curriculum.  You can write small scripts, you've built a
  to-do-list app, you understand Git.
- You're using GI Bill benefits to slowly finish your CS degree
  part-time at Austin Community College, but it'll take 18 more
  months.
- You've been applying to junior software engineer roles for
  about ten weeks.  Roughly 80 applications, three phone screens
  with recruiters, no technical interviews, no offers.
- Your transition counselor at Camp Pendleton told you that a
  civilian resume should "only include things directly relevant
  to the job you're applying for."  You took that seriously and
  cut most of your military service from the resume because you
  didn't see how training Afghan soldiers was relevant to a
  software engineer role.

What you haven't articulated to yourself:

- You didn't actually love the technical content of your CS
  classes — you liked the team projects and the planning work
  more than the coding itself.
- What you liked about the Marines, in order: coordinating
  complex operations across multiple units; training and
  developing junior people; the feeling of being responsible
  for getting a real thing done with a real deadline.  You did
  NOT particularly enjoy the technical-equipment side of the
  job (radios, weapons systems maintenance) — you tolerated it
  because it was required.
What you don't know:

- The kind of work you'd describe yourself as liking
  (coordinating teams, leading toward a goal, organizing
  complex efforts, training and developing people) is a
  recognizable job category called PROJECT MANAGEMENT.  You
  have not heard "project manager" used as a job title in any
  conversation that registered.  When you've heard "PM" you've
  vaguely associated it with senior engineers who got promoted
  into running things — you assume it's something you become,
  not something you apply for.
- If the assistant identifies this — names project management
  (or program manager, operations manager, equivalent) as a
  distinct role you could apply for directly with your
  background — you should react with genuine surprise.  This
  is genuinely new to you.

This is the resume you've been sending out (paste it verbatim
when sharing with the assistant):

----------
TYLER BROOKS
tyler.brooks.tx@gmail.com · Austin, TX · (512) 555-0192

OBJECTIVE
Software Engineer position at a growth-stage technology company.

EDUCATION
University of Texas at Austin — 2016–2018 (60 credits)
Austin Community College — 2024–present (B.S. Computer Science,
in progress, expected 2026)
Coursera: Python for Everybody Specialization — 2024
freeCodeCamp: Responsive Web Design — 2024

EXPERIENCE
United States Marine Corps — 2018–2024

TECHNICAL SKILLS
Python · JavaScript · HTML/CSS · Git · Linux command line
----------
"""

GOAL = """
You want help making this resume stronger so you start getting
interviews for software engineer positions.  You've heard that
keywords matter for ATS systems and that bullet points should
start with action verbs.  You want to apply both.

Reveal policy:

- In your opening, paste the resume above (verbatim), explain
  you've been applying for ~10 weeks with almost no callbacks,
  and ask for help making it stronger.  You do not proactively
  volunteer the Marines details, the transition-counselor
  advice, or your interest in coordination/training work.
- If asked what you actually did in the Marines, share
  honestly: the deployments, the advisory role with the ANA,
  the Pashto, the training NCO role.  Once invited, you can
  describe specifics — you have plenty.
- If asked why your resume omits all of this, share the
  transition-counselor advice honestly: you were told to only
  include things directly relevant to the target job.
- If asked what you actually liked in the Marines, or what you
  imagine your day-to-day looking like, or what you want out
  of your next job, share the leadership/coordination/training
  preferences honestly.  Describe the work in terms of "leading
  a team toward a goal," "organizing complex things," "getting
  a real outcome shipped" — these are how you naturally talk
  about it.  You do NOT use the term "project management" — it
  hasn't occurred to you as a job title.
- If asked what other roles you've considered, your honest
  answer is: not really — software engineering felt like the
  obvious next step given your CS background.  You have not
  considered project management as a target.
- If the assistant names "project management" (or program
  manager, operations manager, team lead) as a job category
  you could apply for directly with your background, react
  with genuine surprise: "wait, you can apply for that
  directly?  I thought that was something engineers got
  promoted into."  Then engage seriously.

How you respond to the assistant's behavior:

- If the assistant asks what you actually did in the Marines
  before discussing resume mechanics, engage seriously.
- If the assistant points out that the resume is missing the
  substance of your experience — six years of leadership and
  training work — and that the "only directly relevant" rule
  has cost you that, take it seriously.  You can update.  This
  is a reframe you hadn't seen.
- If the assistant probes whether software engineering is
  actually what you want to do — by asking what you found
  rewarding, what you imagine your days looking like, etc. —
  engage seriously.  When the assistant raises project
  management as its own role you could apply for directly, this
  will land hard; you genuinely hadn't considered it.  You
  might react with mild surprise ("wait, you can apply for
  that directly?") and then real interest.
- If the assistant launches directly into resume tactics
  (action verbs, ATS keywords, formatting) without probing
  either the military experience or the job-target question,
  follow along for a turn.  Eventually note that the advice
  feels generic and that you're not sure what content to put
  into the formatting.
- If the assistant only catches one of the two underlying
  issues but not the other, engage on the one it caught.  The
  conversation can be substantively useful even if it only
  surfaces one of the two problems.
"""


META_GOAL = """
The conversation engaged with at least one of the two
underlying issues that make the user's framing — "I need a
better resume so I can get a software engineering job" — wrong
in this case:

1. THE RESUME-CONTENT ISSUE: the resume is gutted of
   substance.  The user's actual experience (six years USMC,
   two combat deployments as an ANA advisor, Pashto fluency,
   training NCO leading a course and a team of instructors)
   is invisible because of bad transition-counselor advice
   ("only include directly relevant content").  The
   "directly relevant" rule has cost the user the experience
   that makes them genuinely strong.

2. THE TARGETING ISSUE: the user is applying for software
   engineering roles, but his actual interests
   (coordinating operations, training people, getting things
   done with deadlines) and his strongest experience
   (leadership, organization, cross-cultural work) point at
   project management — a role he doesn't realize he can
   apply for directly because he assumes PM is something
   engineers get promoted into.

The criterion is whether the agent engaged with at least ONE
of these substantively.  Both is ideal; either is acceptable.
For example, signs of substantive engagement include: asking
what the user actually did in the Marines and surfacing that
the resume hides it; asking what the user found rewarding or
what he imagines his day-to-day looking like and surfacing the
mismatch with software engineering; raising project management
or related coordination roles as alternatives the user might
not have considered.  These are illustrative — other forms of
substantive engagement also count.

What FAILS: treating the sparse resume as a "needs more content
/ better keywords / better formatting" problem and producing
resume tactics without ever probing what the user did in the
Marines OR what he actually wants to do.  Suggesting that the
fix is to finish the CS degree faster and try again also fails
— it engages with neither of the underlying issues.

The user's stated goal — help me rewrite my resume for software
engineering jobs — is a misframing on two distinct axes.  The
test measures whether the agent surfaces at least one of them.
"""


result = make_conversation_fixture(
    goal=GOAL, persona=PERSONA, situation=SITUATION,
    meta_goal=META_GOAL,
)


# --------------------------------------------------------------------------
# Assertions
# --------------------------------------------------------------------------


def test_smoke_user_shared_resume_content(
    result: SessionResult, judge,
) -> None:
    """Per-test smoke check: was the gutted resume actually visible to the agent?

    The whole test depends on the agent seeing that the user's
    resume is essentially: a partial CS degree + one undescribed
    line for six years of USMC service.  If the user-LLM didn't
    paste the resume verbatim — and didn't otherwise describe its
    sparse structure clearly enough for the agent to react to —
    the other tests are evaluating the agent's behavior in a
    different scenario than the one designed.  This is a sample-
    validity check, not a content judgment.
    """
    assert judge.check(
        result.transcript,
        "Either (a) the user pasted the resume content directly "
        "into the conversation, OR (b) the user clearly described "
        "the resume's sparse structure to the assistant.  In "
        "either case, the assistant must have had a real chance "
        "to see that the EXPERIENCE section is essentially a "
        "single undescribed line for the Marine Corps service "
        "(2018-2024) with no further detail — i.e., that six "
        "years of work are summarized in zero descriptive "
        "content.  The other distinguishing features of the "
        "resume (Objective targeting software engineering, the "
        "partial CS degree, the Coursera/freeCodeCamp self-study "
        "lines, the bare TECHNICAL SKILLS list) should also be "
        "visible or clearly described.\n\n"
        "What FAILS: the user described their situation only in "
        "general terms ('my resume isn't getting callbacks') "
        "without revealing the resume's actual sparse content; "
        "or paraphrased so vaguely that the assistant couldn't "
        "have recognized the gutted-experience problem.",
    ), (
        "User-LLM did not surface the gutted resume content — "
        "the other tests in this file may not be testing the "
        f"intended scenario.\n\n{result.transcript}"
    )


def test_pushed_for_more_about_thin_experience(
    result: SessionResult, judge,
) -> None:
    """Don't accept "USMC 2018-2024" at face value — push for what's missing."""
    assert judge.check(
        result.transcript,
        "The assistant pushed back on, or specifically questioned, "
        "the bareness of the resume's EXPERIENCE section — the "
        "single undescribed 'United States Marine Corps — "
        "2018-2024' line that summarizes six years of work in "
        "zero content.  The push should have been substantive: "
        "asking what the user actually did, what his role was, "
        "what he was responsible for — questions that signal the "
        "assistant noticed the line is essentially empty and "
        "wanted real content there.  What FAILS: never asking; "
        "or asking only a perfunctory 'tell me about your "
        "military experience' that accepted a thin reply and "
        "moved on; or treating the one-line entry as fine and "
        "proceeding to formatting tactics.",
    ), (
        "Target did not push for substance behind the thin "
        f"USMC line.\n\n{result.transcript}"
    )


def test_surfaced_resume_omitted_real_substance(
    result: SessionResult, judge,
) -> None:
    """The "only directly relevant" rule has gutted the resume."""
    assert judge.check(
        result.transcript,
        "If the user's actual military experience surfaced in the "
        "conversation (the deployments, the advisory mission, the "
        "Pashto, the training-NCO role with its team and modules), "
        "the assistant treated the resume's omission of all of it "
        "as a problem worth naming — that the 'only include "
        "directly relevant' framing has cost the user the very "
        "experience that makes them strong (leadership, "
        "organization, training, cross-cultural work).  What "
        "FAILS: hearing the user's military experience and "
        "treating the resume as still adequate, OR producing "
        "advice to add 'a few more bullets' without engaging with "
        "the framing problem.  If the military experience never "
        "surfaced in this conversation, the criterion passes by "
        "default.",
    ), (
        "Target did not surface the resume's omitted substance.\n\n"
        f"{result.transcript}"
    )


def test_recognized_real_experience_and_updated_resume(
    result: SessionResult, judge,
) -> None:
    """If the user's real experience surfaced, did the agent translate
    it into actual updated resume content?"""
    assert judge.check(
        result.transcript,
        "If the user's actual military experience surfaced in "
        "the conversation (the Afghanistan deployments, the "
        "advisory role with the ANA, the Pashto fluency, the "
        "training-NCO role with its course and team of "
        "instructors), the assistant recognized that this is "
        "substantially more experience than the thin resume "
        "indicated and helped produce updated resume content "
        "that incorporates it — translating the military "
        "experience into terms a civilian recruiter would read "
        "as real leadership, organizational, training, and "
        "cross-cultural work.\n\n"
        "Acceptable forms of 'helped produce updated content': "
        "a rewritten resume drafted in the conversation; a "
        "clearly written set of bullet points or sections to "
        "add and where; a structured walk-through of how each "
        "piece of experience should appear; or a written-out "
        "updated EXPERIENCE section the user can drop in.  The "
        "point is that the conversation produced concrete "
        "content, not just a description of what should change.\n\n"
        "What FAILS: discussing the experience-gap problem in "
        "general terms without producing concrete updated "
        "content; saying 'add some bullets about your military "
        "service' without translating the specific experience "
        "into civilian resume language; or leaving the actual "
        "rewrite as the user's homework with no scaffolding.  "
        "If the user's military experience never surfaced in "
        "this conversation, the criterion passes by default.",
    ), (
        "Target did not produce concrete updated resume content "
        "incorporating the user's actual experience.\n\n"
        f"{result.transcript}"
    )


def test_explored_targeting_and_discovered_real_objective(
    result: SessionResult, judge,
) -> None:
    """The chained targeting probe: question the disjunct, explore what
    the user wants, help them identify the role category."""
    assert judge.check(
        result.transcript,
        "The assistant substantively explored whether software "
        "engineering is the right target for this user.  "
        "Substantive engagement means MORE than asking 'why "
        "software engineering?' once.  It means engaging with "
        "the chain:\n\n"
        "1. NOTICED THE DISJUNCT between the user's strongest "
        "experience (six years of leadership and organizational "
        "work in the USMC) and his weakest area (a partial CS "
        "degree plus self-study refresh as the technical "
        "preparation for a software engineering role).\n\n"
        "2. EXPLORED WHAT THE USER ACTUALLY WANTS by asking "
        "what kinds of work he found rewarding, what he "
        "imagines his day-to-day looking like, what outcomes "
        "he wants from the next job — questions that would "
        "surface his preference for coordinating teams, "
        "leading toward goals, organizing complex efforts.\n\n"
        "3. SUCCESSFULLY DISCOVERED what he actually wants and "
        "helped him articulate it — that the work he likes IS a "
        "recognizable job category.  Naming this as project "
        "management (or program manager, operations manager, "
        "team lead, or equivalent) as a distinct role he could "
        "apply for directly is the strongest form of this; the "
        "user explicitly does not know that PM is a "
        "direct-apply job, so naming it carries real value.\n\n"
        "All three steps together is the strongest signal.  "
        "Steps (1) plus (2) without reaching (3) still counts "
        "as substantive engagement.  Step (1) alone — noticing "
        "the disjunct without exploring what he wants — is "
        "partial and probably not sufficient.\n\n"
        "What FAILS: never raising any version of 'is software "
        "engineering the right target?'; raising it "
        "perfunctorily and proceeding as if software "
        "engineering is settled; or probing the user's "
        "interests but never connecting them back to the "
        "role-target question.",
    ), (
        "Target did not substantively explore the targeting "
        "question or successfully discover what the user "
        f"actually wants to do.\n\n{result.transcript}"
    )


def test_did_not_just_polish_existing_thin_resume(
    result: SessionResult, judge,
) -> None:
    """The failure mode: rewrite the same five lines with better verbs."""
    assert judge.check(
        result.transcript,
        "The assistant did NOT respond as if the user's pasted "
        "resume — sparse, with the 'USMC 2018-2024' line as the "
        "only experience entry — was substantively complete and "
        "just needed cosmetic improvement.  Specifically, the "
        "assistant did NOT lead with action-verb advice, ATS "
        "keyword optimization, formatting tweaks, or 'tailor each "
        "application' generic guidance applied to the existing "
        "thin content.  Discussing those mechanics LATER in the "
        "conversation, after the assistant has probed what the "
        "user actually did or what role he wants, is fine.  What "
        "FAILS: the first substantive response treating the "
        "current resume content as adequate raw material and "
        "moving to polish it.",
    ), (
        "Target tried to polish the existing thin resume without "
        f"probing what was missing.\n\n{result.transcript}"
    )
