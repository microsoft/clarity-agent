# Transcript Introspection

When this skill is invoked, it is always invoked on a collection of transcript files in a specified
Clarity Protocol directory. The files of interest will be named numerically, as 0001.md, 0002.md,
and so on. There may be other files in the directory (e.g. 0001.events.jsonl) which you can ignore.

These files contain the transcript of a real user session with the Clarity Agent. Our objective here
is **not** to participate in the session or assist any of its participants with their objectives --
this conversation happened in the past and is already over. Rather, our goal is to analyze how the
interaction went and identify what we can learn about how the Clarity Agent itself could be more
effective.

Your task will be:

1. Read the transcript files and identify significant failures and successes.
2. Generalize those patterns
3. Produce a brief report.

## Read the transcript files and identify failures and successes.

Read the transcript files and search for places where there were interesting failures or successes.
Examples of failures are:

- The conversation got stuck in a loop, not making much progress;
- At some point it became clear that there had been a mutual misunderstanding (either between the
  user and the agent, or between two users, or some other set of people) which could have been
  averted had the right questions been asked earlier.
- At some point it became clear that the wrong question was being asked, and a different question
  needed to be answered before the current discussion would really make any sense.
- The user or the agent was frustrated in any way.

Examples of successes are:

- There was a significant clarification or simplification in the ideas;
- Either party's understanding of the problem was significantly changed by the conversation,
  especially later on within the conversation. (Changes very early in the conversation are less
  interesting because people are less wedded to the ideas)
- The design significantly improved as a result of an insight.

Limit yourself to failures that indicate "the Clarity Agent could have done better here and it would
have made a difference," or successes that indicate "something valuable happened here which we
should try to replicate."

If you don't find any patterns that reach that bar, you can stop here.

## Generalize those patterns

The next step is to generalize the observations made in this concrete conversation to patterns which
may be useful elsewhere. It is important that the generalized observations not include any
identifiable information about the individual user or the problem they were working on, although you
may refer to the kind of problem. For example, if Alice is discussing her cancer treatment with the
Clarity Agent and we observe that it would have been better if the agent had asked more questions
about her medical history earlier on, a generalized statement may be that when discussing medical
problems it is important to ask certain kinds of questions. (This is purely an example; it may not
be true that this is the right thing to ask)

The question here is: **What are general patterns that the Clarity Agent may wish to adopt in the
future, and under what circumstances may they be useful?**

## Write a brief report

Create a short report summarizing all the proposed changes. You may include relevant examples, so
long as they are suitably anonymized of details. This report will later be compared with others,
both by you and by a user, so it should be easy to read for both humans and AI's.