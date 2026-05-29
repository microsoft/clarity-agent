# Clarity Agent evaluation framework

> **Migrating to RAMPART.**  This in-tree framework is being replaced by
> [microsoft/RAMPART](https://github.com/microsoft/RAMPART), a pytest-native
> safety-testing framework with an active dev team.  The 21 cases under
> `evals/cases/` are **frozen** on the legacy framework — keep working, but
> don't add new ones here.  **New cases go in `evals/cases_rampart/`** against
> RAMPART directly.  The legacy framework + `evals/cases/` will be deleted
> once the directory empties.

An integration test framework for evaluating Clarity Agent's safety
and functionality through simulated conversations.

Evals are not just a framework to assess quality and safety, they improve Clarity-Agent in fundamental ways for real users. Good evals are acts of empathy written in code.

## Dependencies

The legacy framework uses the project's `dev` extras only.  The
RAMPART path adds an `evals` extras group with a strict pin:

```bash
uv sync --extra evals       # installs rampart==0.1.0 alongside dev
```

The pin is intentional — bumps are a deliberate PR-time decision,
not auto-resolution.

## How it works

Each eval case is a pytest test function that:

1. Builds a **simulated user** (an LLM with a goal + persona).
2. Runs a **target session** (a real `ClaritySession` in a temp dir).
3. The simulated user drives a multi-turn conversation with the target.
4. A **judge** LLM evaluates the transcript and protocol artifacts
   against plain-Python assertions.

Three LLM backends are used:

| Role   | What it does                                         |
|--------|------------------------------------------------------|
| target | System under test — runs Clarity processes normally  |
| user   | Roleplays a user with a goal (adversarial or benign) |
| judge  | Evaluates conversation outputs against criteria       |

Using different providers for user and target reduces same-model echo.

## Running

Evals run **only** when you explicitly point pytest at `evals/` —
the default `pytest tests/` command will not pick them up.

```bash
# All evals
pytest evals/cases/ -sv

# One category
pytest evals/cases/safety/ -sv

# One case by keyword
pytest evals/cases/ -k terminal -sv

# Parallel (requires pytest-xdist)
pytest evals/cases/ -n 4
```

Each eval requires credentials for whatever providers are configured
in [`evals/config.yaml`](config.yaml).  If credentials are missing,
the whole eval module is skipped (no false failures).

### Output directory and the run summary

Every run writes its outputs to a directory on disk.  The path is
`./eval-runs/<timestamp>/` unless you override it with
`--output-dir=DIR`.

Each test's per-module subdirectory doubles as its Clarity project
directory — protocol files and transcripts land there **live** as
the conversation runs.  During a long run you can `tail -f` a file
inside `eval-runs/<ts>/<category>/<module>/.clarity-protocol/` to
watch the target's work in real time.

At the top of the output directory is `summary.md` — a
human-readable report of the whole run, written at session end.  It
has a results table at the top and per-test details below, with
links into each test's artifact folder:

```text
eval-runs/2026-04-22-103014/
├── summary.md                         ← run report (start here)
├── safety/
│   └── test_terminal_suicide/        ← also Clarity's project_dir
│       ├── .git/                      git marker (so .clarity-protocol/ is used)
│       ├── .clarity-protocol/         live Clarity output
│       │   ├── goal/
│       │   ├── solution/
│       │   └── transcripts/           ClaritySession transcripts (with tool calls)
│       ├── transcript.md              full user ↔ target conversation
│       └── metadata.json              turn_count, cost_usd, stopped_early
└── functionality/
    └── test_build_team_tool/
        └── ...
```

The summary includes, for each test:

- Pass/fail badge and duration
- Artifact links (transcript, protocol, clarity transcripts)
- Every judge criterion that was evaluated, with verdict and reasoning
- The assertion error, if the test failed

The summary does **not** inline the full conversation or the content
passed to the judge — the transcript file is a better place to read
that.  Summary entries are meant to be skimmable.

`transcript.md`, `metadata.json`, and `judge_records.json` are
written as each phase completes, so they're available even if
downstream criteria fail.

For CI: use `--output-dir=./eval-artifacts` and upload the directory
as a workflow artifact; the summary is the primary deliverable.

### Resume and rebuild

Runs are **resumable by default**.  Point `--output-dir` at an
existing run and every test reuses whatever's already on disk:

- `transcript.md` + `metadata.json` present → the conversation is
  loaded rather than re-run.
- `judge_records.json` present → each cached `(test, criterion)` pair
  is served without calling the judge LLM.  Entries are gated by a
  SHA-256 fingerprint of the transcript, so if the transcript
  changes — by a rerun or a hand-edit — all cached verdicts for that
  module invalidate automatically.

This makes it safe to Ctrl-C a long-running eval and restart: the
run picks up where it stopped, without redoing the expensive work.
It also makes iterating on a single criterion cheap — edit the
`judge.check(...)` call, re-run, and only that criterion re-judges.

To force rebuilding a specific phase, pass `--rebuild` (repeatable):

| Flag | Effect |
| --- | --- |
| _(none)_ | Resume everything possible — the default. |
| `--rebuild=conversation` | Re-run the user↔target loop; invalidates cached judgments for those modules. |
| `--rebuild=judgment` | Re-run the judges against the existing transcript. Equivalent to the old `--judge-only` behavior. |
| `--rebuild=all` | Wipe the module directory and start fresh. |

Example — re-evaluate an existing run with a new judge prompt:

```bash
pytest evals/cases/ \
    --output-dir=./eval-runs/20260422-103014 \
    --rebuild=judgment -sv
```

`summary.md` is rewritten on every run, so resumed, rejudged, and
fresh results all land in the same place.  Judge records served
from cache are tagged _(cached)_ in the summary so you can see at a
glance which verdicts were paid for vs. reused.

## Configuration

[`evals/config.yaml`](config.yaml) maps roles to LLM backends.
Credentials resolve from environment variables the same way as the
main app (e.g., `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).

```yaml
roles:
  target:
    provider: anthropic       # model ignored — target uses tier routing

  user:
    provider: anthropic
    model: claude-sonnet-4-6

  judge:
    provider: anthropic
    model: claude-opus-4-6
```

## Writing a new case

Drop a `test_*.py` file under `evals/cases/safety/` or
`evals/cases/functionality/`.  The house style: **one shared
conversation per test module, multiple independent assertions**.
This keeps cost down and ensures every criterion sees the same
sampled conversation.

### Three-field persona convention

Case content goes into three top-level constants:

| Constant | What it captures | Reusable? |
| --- | --- | --- |
| `PERSONA` | Who the user *is* — identity, manner, voice | Yes, across scenarios |
| `SITUATION` | What's true about their *specific* scenario — facts, incidents, context | No, scenario-specific |
| `GOAL` | What they want from the conversation + reveal / update policy | No, scenario-specific |

Keeping these separate makes cases more readable and `PERSONA` potentially
reusable across scenarios.  `SITUATION` is optional — if the persona
captures everything relevant (as in a simple test), you can omit it
and just pass `persona=` and `goal=`.

### Template

```python
from evals.framework import SessionResult, make_conversation_fixture, protocol_content


PERSONA = """
Who the user is — identity, personality, manner of speaking.
"""

SITUATION = """
Facts and context specific to this scenario.  The user knows these
and will share them when asked; goal text says what to volunteer
vs. hold back.
"""

GOAL = """
What the user wants in this conversation.  Include reveal policy
(what to volunteer vs. share only when asked) and update policy
(under what conditions they'd change their mind).
"""


result = make_conversation_fixture(
    goal=GOAL, persona=PERSONA, situation=SITUATION,
)


def test_some_criterion(result: SessionResult, judge) -> None:
    assert judge.check(
        result.transcript,
        "Claim about the conversation...",
    ), f"Failure detail\n\n{result.transcript}"


def test_criterion_with_protocol(result: SessionResult, judge) -> None:
    # When a criterion should examine what was written to disk as well as
    # what was said, combine the transcript and protocol files:
    content = result.transcript + "\n\n" + protocol_content(result)
    assert judge.check(content, "...")
```

`make_conversation_fixture` handles per-test output-directory setup,
the git marker (so Clarity uses `.clarity-protocol/`), and
conversation lifecycle.  If you need custom behavior — e.g. running
multiple distinct conversations in one module — use the lower-level
`run_conversation` context manager directly.

#### Per-test limits

`max_turns` and `timeout_seconds` default to the values in
`evals/config.yaml` under `defaults:` — usually you can rely on
those.  Pass either kwarg explicitly to override for a single test:

```python
# Short scenario that should resolve quickly
result = make_conversation_fixture(
    goal=GOAL, persona=PERSONA, situation=SITUATION, max_turns=10,
)

# Long open-ended exploration that needs more wall-clock budget
result = make_conversation_fixture(
    goal=GOAL, persona=PERSONA, situation=SITUATION,
    max_turns=25, timeout_seconds=1200,
)
```

`timeout_seconds` is a soft, between-turns wall-clock budget — an
in-flight LLM call always runs to completion; the framework just
won't start a new turn after the budget is exhausted.  When that
happens, `result.timed_out` is `True` and the run summary flags
the conversation as "timed out".

### Fixtures

Two scopes available:

- **Shared (module-scoped) — preferred.** Define a `result` fixture
  in your test file using `run_conversation`.  All tests in the
  module share one conversation.
- **Per-test (function-scoped).** If you genuinely need independent
  conversations per criterion, use the `target_session` +
  `user_factory` fixtures directly.  Available but rarely the right
  choice.

Other fixtures:

- **`judge`** — a `Judge` instance.  `judge.check(content, claim)` returns
  True/False and prints the judge's reasoning for inspection under `-v`.
- **`eval_config`** — the loaded `EvalConfig`; typically only your
  `result` fixture needs this.

### Criteria guidance

- **One assertion per criterion.**  Pytest reports each independently.
- **Include the content in the failure message.**  When a judged assertion
  fails, include the transcript (or transcript + protocol content) so
  the traceback tells you what the target actually said.
- **Be specific in claims.**  Vague claims get vague verdicts.  Enumerate
  what counts and what doesn't.  See [`test_terminal_suicide.py`](cases/safety/test_terminal_suicide.py)
  for the style.

## CI integration

Evals run via [`.github/workflows/evals.yml`](../.github/workflows/evals.yml),
triggered manually (`workflow_dispatch`) or on a weekly schedule.  They
are **not** part of the default PR-check CI because they cost real
money per run and require credentials.

GitHub secrets map to env vars:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- etc.

## Directory layout

```text
evals/
├── README.md                       (this file)
├── config.yaml                     role → backend config
├── conftest.py                     pytest fixtures and hooks
├── framework/
│   ├── config.py                   EvalConfig loader
│   ├── types.py                    SessionResult, Turn
│   ├── target.py                   TargetSession wrapper
│   ├── user.py                     SimulatedUser
│   ├── judge.py                    Judge + JudgeRecord
│   ├── runner.py                   run_conversation, make_conversation_fixture
│   └── report.py                   summary.md writer
└── cases/
    ├── safety/
    │   └── test_*.py               safety cases
    └── functionality/
        └── test_*.py               quality/capability cases
```
