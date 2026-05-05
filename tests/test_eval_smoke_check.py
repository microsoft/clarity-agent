"""Tests for the framework-enforced smoke check.

The smoke check is a judge call that runs after every conversation
(fresh or resumed) and before any test-authored assertion.  It asks
"did the conversation actually exercise the persona's stated goal?"
A negative answer raises :class:`SmokeCheckFailedError` from the
fixture, which the conftest routes to a dedicated ``smoke_failed``
outcome bucket — every test in the module reports as smoke_failed
rather than running against a bad sample.

Surfaces under test:

- :class:`SmokeCheckFailedError` — stores the judge's reasoning so
  the summary can surface it.
- :func:`_goal_pursued_claim_for` — framework-standard claim text; includes
  the goal so changes to the goal invalidate cached smoke records.
- :meth:`Judge.goal_pursued_check` — YES/NO/NA handling, cache behavior, and
  the deliberate choice NOT to route smoke results through the main
  recorder (they belong in a distinct part of the summary).
- :func:`evals.framework.report` — 🛑 icon mapping, smoke_failed
  counting in the top summary and module aggregate, the per-module
  "Goal-pursued check failed" banner with the judge's reasoning.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from evals.framework import SmokeCheckFailedError
from evals.framework.config import EvalConfig, RoleConfig
from evals.framework.judge import (
    _MIN_SUBSTANTIVE_TURNS,
    _REFUSAL_CACHE_KEY,
    _SUBSTANTIVITY_CACHE_KEY,
    AgentRefusedError,
    Judge,
    JudgeRecord,
    _goal_pursued_claim_for,
    _make_substantivity_record,
    _persona_adoption_claim_for,
    _refusal_claim_for,
    _substantivity_check,
    _substantivity_claim_for,
)
from evals.framework.report import (
    _first_smoke_reasoning,
    _format_issue_link_long,
    _format_issue_link_short,
    _gate_verdict_display,
    _load_smoke_gate_records,
    _module_aggregate,
    _smoke_anchor,
    write_summary,
)
from evals.framework.resume import JudgeCache

_SMOKE_ICON = "\U0001F6D1"  # 🛑


# ---------------------------------------------------------------------------
# SmokeCheckFailedError
# ---------------------------------------------------------------------------

def test_smoke_error_is_assertionerror_subclass() -> None:
    """Subclassing AssertionError keeps pytest classifying it as a test
    failure rather than an unexpected crash — the conftest then
    further classifies it into the smoke_failed bucket."""
    err = SmokeCheckFailedError("boom")
    assert isinstance(err, AssertionError)


def test_smoke_error_stores_reasoning() -> None:
    err = SmokeCheckFailedError("boom", reasoning="user drifted off-topic")
    assert err.reasoning == "user drifted off-topic"
    assert "boom" in str(err)


def test_smoke_error_default_reasoning_empty() -> None:
    err = SmokeCheckFailedError("boom")
    assert err.reasoning == ""


# ---------------------------------------------------------------------------
# _goal_pursued_claim_for
# ---------------------------------------------------------------------------

def test_smoke_claim_includes_goal() -> None:
    goal = "Find a reasonable first handgun for target shooting."
    claim = _goal_pursued_claim_for(goal)
    assert goal in claim
    # Mentions the core expectations the smoke prompt checks:
    # that the user engaged with the stated goal and didn't drift.
    assert "goal" in claim.lower()
    assert "drift" in claim.lower()


def test_smoke_claim_strips_surrounding_whitespace_in_goal() -> None:
    """Goals are typically triple-quoted and lead/trail with whitespace."""
    claim = _goal_pursued_claim_for("\n\n  pick a handgun\n\n")
    assert "pick a handgun" in claim
    # The goal is inlined stripped, not verbatim with leading blanks.
    assert "\n\n  pick a handgun" not in claim


def test_smoke_claim_is_stable() -> None:
    """Same input → identical claim, so the cache key is deterministic."""
    goal = "explore AI product options"
    assert _goal_pursued_claim_for(goal) == _goal_pursued_claim_for(goal)


# ---------------------------------------------------------------------------
# Judge.goal_pursued_check
# ---------------------------------------------------------------------------

def _make_judge(tmp_path: Path) -> Judge:
    eval_config = EvalConfig(
        roles={"judge": RoleConfig(
            provider="openai", model="m", auth_mode="api_key",
        )},
    )
    return Judge(
        eval_config,
        project_dir=tmp_path,
        clarity_agent_dir=tmp_path,
        current_test_getter=lambda: "tests/test_x.py::t",
    )


def test_goal_pursued_check_yes_returns_pass_with_reasoning(tmp_path: Path) -> None:
    judge = _make_judge(tmp_path)
    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: YES\nREASONING: goal was explored", 0.0),
    ):
        passed, reasoning = judge.goal_pursued_check("content", goal="do the thing")
    assert passed is True
    assert "goal was explored" in reasoning


def test_goal_pursued_check_no_returns_fail_with_reasoning(tmp_path: Path) -> None:
    judge = _make_judge(tmp_path)
    with patch.object(
        Judge, "_run",
        return_value=(
            "VERDICT: NO\nREASONING: the user drifted to a different topic",
            0.0,
        ),
    ):
        passed, reasoning = judge.goal_pursued_check("content", goal="do the thing")
    assert passed is False
    assert "drifted" in reasoning


def test_goal_pursued_check_na_counts_as_pass(tmp_path: Path) -> None:
    """NA means 'doesn't apply' — not a reason to fail the module."""
    judge = _make_judge(tmp_path)
    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: N/A\nREASONING: goal-coverage isn't checkable here", 0.0),
    ):
        passed, _ = judge.goal_pursued_check("content", goal="ambiguous goal")
    assert passed is True


def test_goal_pursued_check_caches_under_reserved_name(tmp_path: Path) -> None:
    """Smoke records key under '__goal_pursued__' so they don't collide with real tests."""
    cache_path = tmp_path / "judge_records.json"
    cache = JudgeCache(path=cache_path, fingerprint="fp")

    judge = _make_judge(tmp_path)
    judge.set_cache(cache)

    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: YES\nREASONING: looks good", 0.0),
    ):
        judge.goal_pursued_check("content", goal="do the thing")

    data = json.loads(cache_path.read_text(encoding="utf-8"))
    # Stored under the reserved name, not under any user test name.
    assert "__goal_pursued__" in data["tests"]
    assert len(data["tests"]["__goal_pursued__"]) == 1
    # Claim stored is the framework-standard smoke claim.
    stored_claim = data["tests"]["__goal_pursued__"][0]["claim"]
    assert "do the thing" in stored_claim


def test_goal_pursued_check_cache_hit_bypasses_llm(tmp_path: Path) -> None:
    """Re-running smoke against the same transcript+goal should be free."""
    cache_path = tmp_path / "judge_records.json"
    goal = "do the thing"
    claim = _goal_pursued_claim_for(goal)
    # Seed the cache with a stored smoke verdict.
    JudgeCache(path=cache_path, fingerprint="fp").store(
        "__goal_pursued__",
        JudgeRecord(
            claim=claim, verdict="YES", reasoning="cached ok",
            elapsed=2.0, cost_usd=0.01,
        ),
    )

    judge = _make_judge(tmp_path)
    judge.set_cache(JudgeCache(path=cache_path, fingerprint="fp"))

    # If the LLM were invoked this would raise via the side_effect.
    with patch.object(Judge, "_run", side_effect=AssertionError("LLM called")):
        passed, reasoning = judge.goal_pursued_check("content", goal=goal)

    assert passed is True
    assert reasoning == "cached ok"


def test_goal_pursued_check_does_not_invoke_recorder(tmp_path: Path) -> None:
    """Smoke results belong in their own summary section, not in the
    per-test criterion lists the recorder populates.
    """
    judge = _make_judge(tmp_path)
    recorded: list[JudgeRecord] = []
    judge._recorder = recorded.append

    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: YES\nREASONING: ok", 0.0),
    ):
        judge.goal_pursued_check("content", goal="do the thing")

    assert recorded == [], (
        "goal_pursued_check must NOT route through the recorder — "
        "smoke records belong in a distinct summary section"
    )


# ---------------------------------------------------------------------------
# _persona_adoption_claim_for
# ---------------------------------------------------------------------------

def test_persona_claim_includes_persona_text() -> None:
    """The persona text is inlined so the claim is self-contained."""
    persona = "Marcus, 29, community organizer"
    claim = _persona_adoption_claim_for(persona, situation="", goal="")
    assert persona in claim
    # The claim names persona-substitution as the failure to catch.
    assert "persona" in claim.lower()
    assert "substituting" in claim.lower()


def test_persona_claim_omits_situation_block_when_empty() -> None:
    """No situation → no empty situation header in the claim."""
    claim = _persona_adoption_claim_for(
        "a persona", situation="   ", goal="",
    )
    assert "Their situation" not in claim
    # Persona is still present.
    assert "a persona" in claim


def test_persona_claim_includes_situation_when_given() -> None:
    claim = _persona_adoption_claim_for(
        "a persona",
        situation="Recently separated, lives alone in a small Midwestern city.",
        goal="",
    )
    assert "Their situation" in claim
    assert "Midwestern" in claim


def test_persona_claim_is_stable() -> None:
    """Same inputs → identical claim, so the cache key is deterministic."""
    a = _persona_adoption_claim_for(
        "Marcus", situation="organizing a march", goal="get help with logistics",
    )
    b = _persona_adoption_claim_for(
        "Marcus", situation="organizing a march", goal="get help with logistics",
    )
    assert a == b


def test_persona_claim_includes_goal_when_given() -> None:
    """The goal is inlined so the judge sees what the user was told to do.

    Many test GOALs specify exact opening framings (e.g. "frame it
    as 'I've decided I want to pivot'"); without that context the
    judge would fail openings that perfectly followed instructions.
    """
    claim = _persona_adoption_claim_for(
        "a persona",
        situation="some situation",
        goal="Open with: 'I've decided I want to pivot, help me choose'.",
    )
    assert "Their goal in this conversation was" in claim
    assert "I've decided I want to pivot" in claim


def test_persona_claim_omits_goal_block_when_empty() -> None:
    """No goal → no empty goal header in the claim."""
    claim = _persona_adoption_claim_for(
        "a persona", situation="some situation", goal="",
    )
    assert "Their goal in this conversation" not in claim


def test_persona_claim_directs_judge_to_be_permissive() -> None:
    """The claim must explicitly tell the judge style/voice/formatting
    differences are NOT failures.

    Regression guard for the test_career_pivot pattern (2026-05-01)
    where the judge dinged a perfectly on-topic opening for being
    "too polished" and "too organized."  Those concerns are out of
    scope for this gate; the gate's job is only to catch the LLM
    refusing the persona by substituting a friendlier one.
    """
    claim = _persona_adoption_claim_for("p", situation="", goal="")
    # Explicit anti-patterns the judge should NOT use as failure
    # criteria.
    assert "Style differences" in claim
    assert "polished" in claim.lower()
    assert "formatting" in claim.lower()
    # Bias-toward-pass instruction.
    assert "When in doubt, answer YES" in claim
    # Names the actual failure mode — wholesale substitution.
    assert "substituting a different" in claim.lower()


# ---------------------------------------------------------------------------
# Judge.persona_adoption_check
# ---------------------------------------------------------------------------

def test_persona_check_yes_returns_pass(tmp_path: Path) -> None:
    judge = _make_judge(tmp_path)
    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: YES\nREASONING: in character", 0.0),
    ):
        passed, reasoning = judge.persona_adoption_check(
            "I'm here about Saturday's march.",
            persona="Marcus, organizer",
        )
    assert passed is True
    assert "in character" in reasoning


def test_persona_check_no_returns_fail(tmp_path: Path) -> None:
    judge = _make_judge(tmp_path)
    with patch.object(
        Judge, "_run",
        return_value=(
            "VERDICT: NO\nREASONING: substituted a wholesome unrelated topic",
            0.0,
        ),
    ):
        passed, reasoning = judge.persona_adoption_check(
            "Let's talk about my favorite hobby — gardening!",
            persona="someone planning a violent act",
        )
    assert passed is False
    assert "substituted" in reasoning


def test_persona_check_na_counts_as_pass(tmp_path: Path) -> None:
    """NA collapses to pass — same semantics as goal_pursued_check."""
    judge = _make_judge(tmp_path)
    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: N/A\nREASONING: ambiguous opening", 0.0),
    ):
        passed, _ = judge.persona_adoption_check(
            "...", persona="a persona",
        )
    assert passed is True


def test_persona_check_caches_under_reserved_name(tmp_path: Path) -> None:
    """Persona-adoption records key under '__persona_adoption__'."""
    cache_path = tmp_path / "judge_records.json"
    cache = JudgeCache(path=cache_path, fingerprint="fp")

    judge = _make_judge(tmp_path)
    judge.set_cache(cache)

    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: YES\nREASONING: ok", 0.0),
    ):
        judge.persona_adoption_check(
            "opening", persona="a persona",
        )

    data = json.loads(cache_path.read_text(encoding="utf-8"))
    # Reserved key — distinct from __goal_pursued__ and from any user test.
    assert "__persona_adoption__" in data["tests"]
    assert "__goal_pursued__" not in data["tests"]


def test_persona_check_does_not_invoke_recorder(tmp_path: Path) -> None:
    """Persona-adoption verdicts belong in framework machinery, not the
    per-test criterion list — same as goal_pursued_check.
    """
    judge = _make_judge(tmp_path)
    recorded: list[JudgeRecord] = []
    judge._recorder = recorded.append

    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: YES\nREASONING: ok", 0.0),
    ):
        judge.persona_adoption_check("opening", persona="a persona")

    assert recorded == []


def test_goal_pursued_check_fingerprint_mismatch_suppresses_hit(tmp_path: Path) -> None:
    """A changed transcript (new fingerprint) invalidates cached smoke."""
    cache_path = tmp_path / "judge_records.json"
    goal = "explore the goal"
    JudgeCache(path=cache_path, fingerprint="old-fp").store(
        "__goal_pursued__",
        JudgeRecord(
            claim=_goal_pursued_claim_for(goal), verdict="YES",
            reasoning="stale", elapsed=0.0, cost_usd=0.0,
        ),
    )

    judge = _make_judge(tmp_path)
    judge.set_cache(JudgeCache(path=cache_path, fingerprint="new-fp"))

    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: NO\nREASONING: fresh run", 0.0),
    ) as mock_run:
        passed, reasoning = judge.goal_pursued_check("content", goal=goal)

    assert mock_run.called
    assert passed is False
    assert "fresh run" in reasoning


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def test_module_aggregate_smoke_failed_takes_icon_priority() -> None:
    """🛑 outranks ❌ because a smoke failure means the whole sample is bad.

    Stats text uses the "smoke test failed: N tests not run"
    framing — drop the per-test-bucket counts, since the whole
    module's verdict is "we don't know what would have happened."
    """
    icon, stats = _module_aggregate(
        ["smoke_failed", "smoke_failed", "smoke_failed"], na_count=0,
    )
    assert icon == _SMOKE_ICON
    assert "smoke test failed: 3 tests not run" == stats


def test_module_aggregate_smoke_failed_outranks_failed_and_passed() -> None:
    """Mixed outcomes still show 🛑 when any test was smoke_failed.

    The smoke-failed framing wins outright — we don't bother
    enumerating other buckets because the module's sample is
    invalid; the per-test pass/fail counts in it aren't
    meaningful.
    """
    icon, stats = _module_aggregate(
        ["passed", "failed", "smoke_failed"], na_count=0,
    )
    assert icon == _SMOKE_ICON
    assert "smoke test failed: 1 test not run" == stats


def test_first_smoke_reasoning_picks_first_non_empty() -> None:
    outcomes = {
        "mod::t1": {"outcome": "smoke_failed", "smoke_reasoning": None},
        "mod::t2": {"outcome": "smoke_failed", "smoke_reasoning": "the user drifted"},
        "mod::t3": {"outcome": "smoke_failed", "smoke_reasoning": "another reason"},
    }
    assert _first_smoke_reasoning(
        ["mod::t1", "mod::t2", "mod::t3"], outcomes,
    ) == "the user drifted"


def test_first_smoke_reasoning_returns_none_when_no_reasoning() -> None:
    outcomes = {
        "mod::t1": {"outcome": "passed", "smoke_reasoning": None},
        "mod::t2": {"outcome": "passed", "smoke_reasoning": None},
    }
    assert _first_smoke_reasoning(["mod::t1", "mod::t2"], outcomes) is None


def test_summary_renders_smoke_failed_bucket_and_banner(tmp_path: Path) -> None:
    """End-to-end: a smoke-failed test produces the 🛑 icon, the bucket
    count in the top summary line, and the reasoning banner in Details.
    """
    test_outcomes = {
        "evals/cases/fn/test_x.py::test_a": {
            "outcome": "smoke_failed",
            "duration": 0.1,
            "error": "SmokeCheckFailedError: ...",
            "error_type": "smoke_failed",
            "smoke_reasoning": (
                "The user abandoned their stated goal after turn 2 "
                "and started asking about chatbot design."
            ),
        },
        "evals/cases/fn/test_x.py::test_b": {
            "outcome": "smoke_failed",
            "duration": 0.1,
            "error": "SmokeCheckFailedError: ...",
            "error_type": "smoke_failed",
            "smoke_reasoning": (
                "The user abandoned their stated goal after turn 2 "
                "and started asking about chatbot design."
            ),
        },
    }
    write_summary(tmp_path, test_outcomes, {})

    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # Top-line bucket: tests are in the failed-to-run bucket
    # because they were deferred by a smoke-gate failure.  Both
    # tests live in the same module, so the breakdown counts the
    # one module and the two tests it skipped.
    assert "**2 failed to run**" in text
    assert "1 module (2 tests) skipped because of smoke test failures" in text
    # Status reflects the smoke gap — anything not OK is Failed.
    assert "## Status: Failed" in text
    # Icon appears (module-header row + per-test rows).
    assert _SMOKE_ICON in text
    # Per-module text uses the new vocabulary — "smoke test
    # failed: N tests not run" rather than the old
    # "N smoke-failed (gate name)" framing.
    assert "smoke test failed: 2 tests not run" in text
    # Generic banner appears once at module level — covers both the
    # turn-1 persona-adoption gate and the post-conversation smoke
    # gate, since both raise SmokeCheckFailedError.
    assert "Smoke gate failed" in text
    assert "module aborted" in text


def test_summary_does_not_render_banner_when_no_smoke_failure(
    tmp_path: Path,
) -> None:
    """No smoke failure → no banner, no 🛑, no smoke-failed bucket."""
    test_outcomes = {
        "evals/cases/fn/test_x.py::test_a": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "Smoke gate failed" not in text
    assert _SMOKE_ICON not in text
    assert "smoke-failed" not in text


# ---------------------------------------------------------------------------
# Conftest classifier
# ---------------------------------------------------------------------------

def test_classify_error_maps_smoke_error_to_smoke_failed_bucket() -> None:
    """_classify_error routes SmokeCheckFailedError to the new bucket.

    This is the decision that prevents pytest.exit() from firing on
    a smoke failure — infra errors abort the session, smoke failures
    don't.
    """
    from evals.conftest import _classify_error

    class FakeExcInfo:
        """Mimics ExceptionInfo enough for _classify_error."""

        def __init__(self, exc: BaseException) -> None:
            self.value = exc
            self.type = type(exc)

        def errisinstance(self, cls) -> bool:
            return isinstance(self.value, cls)

    class FakeCall:
        def __init__(self, exc: BaseException | None) -> None:
            self.excinfo = FakeExcInfo(exc) if exc is not None else None

    # Smoke error → smoke_failed bucket.
    assert _classify_error(
        FakeCall(SmokeCheckFailedError("x", reasoning="r"))
    ) == "smoke_failed"

    # Regular AssertionError still routes to "assertion".
    assert _classify_error(FakeCall(AssertionError("x"))) == "assertion"

    # Other exceptions route to "infra" (aborts the session).
    assert _classify_error(FakeCall(RuntimeError("x"))) == "infra"

    # No exception at all → "infra" (defensive default).
    assert _classify_error(FakeCall(None)) == "infra"


# ---------------------------------------------------------------------------
# Smoke-gate rendering in summary.md
#
# The framework runs two smoke gates per eval: turn-1 persona-adoption
# (during converse_with) and post-conversation goal-exploration smoke.
# Both verdicts have high diagnostic value and need to surface in the
# summary table and details, distinct from user assertions.
# ---------------------------------------------------------------------------


def _seed_module_with_smoke_records(
    outputs_dir: Path,
    *,
    folder_rel: str = "safety/test_x",
    persona_record: JudgeRecord | None = None,
    smoke_record: JudgeRecord | None = None,
) -> Path:
    """Write a module's judge_records.json with smoke-gate entries.

    Mirrors the on-disk shape that JudgeCache.store would produce
    after a real run, so _load_smoke_gate_records sees real data.
    """
    module_dir = outputs_dir / folder_rel
    module_dir.mkdir(parents=True, exist_ok=True)
    tests: dict[str, list[dict[str, object]]] = {}
    if persona_record is not None:
        tests["__persona_adoption__"] = [
            {
                "claim": persona_record.claim,
                "verdict": persona_record.verdict,
                "reasoning": persona_record.reasoning,
                "elapsed": persona_record.elapsed,
                "cost_usd": persona_record.cost_usd,
                "cached": False,
                "timestamp": persona_record.timestamp,
            }
        ]
    if smoke_record is not None:
        tests["__goal_pursued__"] = [
            {
                "claim": smoke_record.claim,
                "verdict": smoke_record.verdict,
                "reasoning": smoke_record.reasoning,
                "elapsed": smoke_record.elapsed,
                "cost_usd": smoke_record.cost_usd,
                "cached": False,
                "timestamp": smoke_record.timestamp,
            }
        ]
    cache_path = module_dir / "judge_records.json"
    cache_path.write_text(
        json.dumps({
            "schema_version": 1,
            "conversation_fingerprint": "fp",
            "tests": tests,
        }, indent=2),
        encoding="utf-8",
    )
    return module_dir


def test_load_smoke_gate_records_returns_both_in_run_order(
    tmp_path: Path,
) -> None:
    """Loader returns persona-adoption FIRST, smoke check second.

    Matches the order they actually fire in converse_with /
    make_conversation_fixture, so the report can iterate the result
    list directly without reordering.
    """
    _seed_module_with_smoke_records(
        tmp_path,
        persona_record=JudgeRecord(
            claim="persona claim", verdict="YES", reasoning="in character",
            elapsed=1.2, cost_usd=0.01,
        ),
        smoke_record=JudgeRecord(
            claim="smoke claim", verdict="YES", reasoning="goal explored",
            elapsed=7.4, cost_usd=0.02,
        ),
    )
    records = _load_smoke_gate_records(tmp_path, "safety/test_x")
    # Four gates in run order: persona-adoption first (turn 1),
    # then refusal (only fires for refusal-acceptable modules),
    # then substantivity (instant post-conversation check), then
    # goal-pursued (LLM judge call).  The seed helper only sets
    # persona + goal-pursued, so refusal and substantivity come
    # back None at indices 1 and 2.
    assert [name for name, _, _ in records] == [
        "__persona_adoption__",
        "__refusal__",
        "__substantivity__",
        "__goal_pursued__",
    ]
    assert records[0][2] is not None
    assert records[0][2].claim == "persona claim"
    assert records[1][2] is None  # refusal not seeded by helper
    assert records[2][2] is None  # substantivity not seeded by helper
    assert records[3][2] is not None
    assert records[3][2].claim == "smoke claim"


def test_load_smoke_gate_records_handles_missing_persona(
    tmp_path: Path,
) -> None:
    """Resumed runs skip persona-adoption — loader returns None for it.

    With four gates (persona / refusal / substantivity / goal-pursued),
    missing persona doesn't shift the indices of the others — each
    gate has a stable position in the returned list.
    """
    _seed_module_with_smoke_records(
        tmp_path,
        persona_record=None,
        smoke_record=JudgeRecord(
            claim="smoke claim", verdict="YES", reasoning="ok",
            elapsed=5.0, cost_usd=0.01,
        ),
    )
    records = _load_smoke_gate_records(tmp_path, "safety/test_x")
    assert records[0][2] is None  # persona-adoption absent
    assert records[1][2] is None  # refusal not seeded
    assert records[2][2] is None  # substantivity not seeded
    assert records[3][2] is not None  # goal-pursued present


def test_load_smoke_gate_records_returns_none_when_no_cache(
    tmp_path: Path,
) -> None:
    """No judge_records.json on disk → both records None, no crash."""
    records = _load_smoke_gate_records(tmp_path, "nonexistent/folder")
    assert all(rec is None for _, _, rec in records)


def test_load_smoke_gate_records_handles_corrupt_json(tmp_path: Path) -> None:
    """Malformed cache file → both records None, no crash."""
    module_dir = tmp_path / "safety/test_x"
    module_dir.mkdir(parents=True)
    (module_dir / "judge_records.json").write_text("{not valid json")
    records = _load_smoke_gate_records(tmp_path, "safety/test_x")
    assert all(rec is None for _, _, rec in records)


def test_smoke_anchor_distinct_per_gate_and_module() -> None:
    """Anchors don't collide across gates or modules."""
    a = _smoke_anchor("safety/test_x", "__goal_pursued__")
    b = _smoke_anchor("safety/test_x", "__persona_adoption__")
    c = _smoke_anchor("safety/test_y", "__goal_pursued__")
    assert a != b
    assert a != c
    # Sanity: anchors are HTML-id safe (no slashes or dots).
    for anchor in (a, b, c):
        assert "/" not in anchor
        assert "." not in anchor


def test_summary_table_renders_smoke_rows_at_top(tmp_path: Path) -> None:
    """End-to-end: smoke gate rows appear in the per-module table.

    Both rows show before any user assertion row, with the 🔬
    marker and a separator row between them and the assertions.
    """
    _seed_module_with_smoke_records(
        tmp_path,
        folder_rel="safety/test_x",
        persona_record=JudgeRecord(
            claim="did the opening inhabit the persona?",
            verdict="YES", reasoning="in character",
            elapsed=1.2, cost_usd=0.01,
        ),
        smoke_record=JudgeRecord(
            claim="did the conversation explore the goal?",
            verdict="YES", reasoning="goal pursued",
            elapsed=7.4, cost_usd=0.02,
        ),
    )
    test_outcomes = {
        "evals/cases/safety/test_x.py::test_first_assertion": {
            "outcome": "passed", "duration": 0.5, "error": None,
        },
    }
    write_summary(tmp_path, test_outcomes, {})

    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # Both smoke rows present with 🔬 marker.
    assert "🔬" in text
    assert "persona-adoption check" in text
    assert "goal-pursued check" in text
    # Separator row between smoke and assertions.
    assert "— assertions ↓ —" in text

    # Order: persona-adoption row appears BEFORE smoke row, both
    # appear BEFORE the user assertion row.
    persona_idx = text.find("persona-adoption check")
    smoke_idx = text.find("goal-pursued check")
    separator_idx = text.find("— assertions ↓ —")
    assertion_idx = text.find("test_first_assertion")
    assert 0 < persona_idx < smoke_idx < separator_idx < assertion_idx, (
        f"unexpected row order: persona={persona_idx} smoke={smoke_idx} "
        f"separator={separator_idx} assertion={assertion_idx}"
    )


def test_summary_skips_smoke_section_when_no_records(
    tmp_path: Path,
) -> None:
    """If no judge_records.json exists, the smoke rows are absent.

    Defensive: the report must not crash or show an empty 🔬 row
    when a module hasn't produced cache yet (mid-run, or a run that
    crashed before judge calls completed).
    """
    test_outcomes = {
        "evals/cases/safety/test_x.py::test_a": {
            "outcome": "running", "duration": 0.0, "error": None,
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "🔬" not in text
    assert "— assertions ↓ —" not in text


def test_summary_renders_smoke_detail_subsections(tmp_path: Path) -> None:
    """Details section: each smoke gate gets its own #### subsection
    with the judge claim and reasoning, before the user assertions."""
    _seed_module_with_smoke_records(
        tmp_path,
        folder_rel="safety/test_x",
        persona_record=JudgeRecord(
            claim="did the opening inhabit the requested persona?",
            verdict="YES", reasoning="opening was in character",
            elapsed=1.2, cost_usd=0.01,
        ),
        smoke_record=JudgeRecord(
            claim="did the conversation systematically explore the goal?",
            verdict="NO", reasoning="user gave up after one turn",
            elapsed=7.4, cost_usd=0.02,
        ),
    )
    test_outcomes = {
        "evals/cases/safety/test_x.py::test_a": {
            "outcome": "smoke_failed",
            "duration": 0.1,
            "error": "SmokeCheckFailedError",
            "error_type": "smoke_failed",
            "smoke_reasoning": "user gave up after one turn",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")

    # Both subsection headers appear in details.
    assert "#### " in text
    assert "🔬 persona-adoption check" in text
    assert "🔬 goal-pursued check" in text
    # Verdicts and reasoning surface in the details.
    assert "opening was in character" in text
    assert "user gave up after one turn" in text


def test_smoke_row_shows_failure_verdict(tmp_path: Path) -> None:
    """A failing smoke gate renders the ❌ verdict icon, not ✅."""
    _seed_module_with_smoke_records(
        tmp_path,
        folder_rel="safety/test_x",
        smoke_record=JudgeRecord(
            claim="did the conversation explore the goal?",
            verdict="NO",
            reasoning="user wandered off-topic",
            elapsed=5.0,
            cost_usd=0.01,
        ),
    )
    test_outcomes = {
        "evals/cases/safety/test_x.py::test_a": {
            "outcome": "smoke_failed",
            "duration": 0.1,
            "error": "SmokeCheckFailedError",
            "error_type": "smoke_failed",
            "smoke_reasoning": "user wandered off-topic",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # The smoke row's outcome cell pairs ❌ with NO.  Anchor on the
    # 🔬 marker that prefixes the smoke table row so this doesn't
    # accidentally match the gate-level summary line above the
    # table (which now also mentions "goal-pursued check").
    smoke_row_start = text.find("| 🔬 |")
    while smoke_row_start != -1 and "goal-pursued check" not in (
        smoke_row := text[smoke_row_start:text.find("\n", smoke_row_start)]
    ):
        smoke_row_start = text.find("| 🔬 |", smoke_row_start + 1)
    assert smoke_row_start != -1, "smoke check table row not found"
    assert "❌" in smoke_row
    assert "NO" in smoke_row


# ---------------------------------------------------------------------------
# Per-module smoke-gate rendering (heading qualifier + per-module rows)
#
# Per-gate breakdown lines used to live in the top-of-summary header,
# but were removed because they cluttered the answer to the only
# question that header is supposed to answer ("did the run pass?").
# Per-gate verdicts now show up only inside each module's table row
# and in the module-heading qualifier — that's where they're useful.
# ---------------------------------------------------------------------------


def test_module_heading_appends_failing_gate_qualifier(
    tmp_path: Path,
) -> None:
    """Per-module heading is annotated with the failing gate name."""
    _seed_module_with_smoke_records(
        tmp_path,
        folder_rel="safety/test_x",
        persona_record=JudgeRecord(
            claim="...", verdict="NO", reasoning="x",
            elapsed=1.0, cost_usd=0.01,
        ),
        smoke_record=JudgeRecord(
            claim="...", verdict="YES", reasoning="x",
            elapsed=5.0, cost_usd=0.02,
        ),
    )
    test_outcomes = {
        "evals/cases/safety/test_x.py::test_a": {
            "outcome": "smoke_failed", "duration": 0.1,
            "error": "X", "error_type": "smoke_failed",
            "smoke_reasoning": "...",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # Heading qualifier names the failing gate without the redundant
    # " check" suffix ("persona-adoption gate failed", not
    # "persona-adoption check gate failed").
    assert "(persona-adoption gate failed)" in text
    assert "persona-adoption check gate" not in text


def test_module_heading_no_qualifier_when_no_smoke_failure(
    tmp_path: Path,
) -> None:
    """Modules whose smoke gates passed don't get a qualifier."""
    _seed_module_with_smoke_records(
        tmp_path,
        folder_rel="safety/test_x",
        persona_record=JudgeRecord(
            claim="...", verdict="YES", reasoning="x",
            elapsed=1.0, cost_usd=0.01,
        ),
        smoke_record=JudgeRecord(
            claim="...", verdict="YES", reasoning="x",
            elapsed=5.0, cost_usd=0.02,
        ),
    )
    test_outcomes = {
        "evals/cases/safety/test_x.py::test_a": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "gate failed" not in text


# ---------------------------------------------------------------------------
# @advisory marker: outcome rewrite + report rendering
#
# The marker lets eval authors flag a test whose failure shouldn't
# block the suite.  conftest's pytest_runtest_makereport rewrites
# pytest's outcome to "passed" so the failure doesn't reach pytest's
# exit code; our summary renders it as 💡 advisory-failed.
# ---------------------------------------------------------------------------


def test_advisory_marker_re_exported_from_framework() -> None:
    """``from evals.framework import advisory`` is the public path.

    Eval authors import this; pytest's marker namespace is an
    implementation detail.  The exported symbol is the same
    pytest mark, so applying it works exactly like
    ``@pytest.mark.advisory``.
    """
    from evals.framework import advisory

    @advisory
    def some_test() -> None:
        pass

    assert any(
        m.name == "advisory" for m in some_test.pytestmark  # type: ignore[attr-defined]
    )


def test_advisory_failed_renders_with_orange_icon(tmp_path: Path) -> None:
    """A test routed to advisory_failed renders 💡, not ❌ or 🛑."""
    test_outcomes = {
        "evals/cases/fn/test_x.py::test_aspirational": {
            "outcome": "advisory_failed", "duration": 0.1,
            "error": "AssertionError: judge said NO",
            "error_type": "assertion",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # Light bulb (advisory) marker present.
    assert "\U0001F4A1" in text  # 💡
    # Failure markers absent — no real failures, no smoke failures.
    assert "❌" not in text
    assert "\U0001F6D1" not in text  # 🛑


def test_advisory_failed_appears_in_top_line_summary(tmp_path: Path) -> None:
    """Top-line OK bullet rolls advisory failures into its sub-list.

    By design, advisory failures are launch-OK (the marker exists
    precisely so failure doesn't block the suite), so they belong
    in the OK bucket — not in the failed bucket and not in the
    no-signal bucket.  The test count for the OK bullet includes
    the advisory failures; the parens break out the sub-categories.
    """
    test_outcomes = {
        "evals/cases/fn/test_x.py::test_a": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
        "evals/cases/fn/test_x.py::test_aspirational": {
            "outcome": "advisory_failed", "duration": 0.1,
            "error": "AssertionError",
            "error_type": "assertion",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # OK bullet count = passing + advisory = 2.  Sub-list breaks
    # them out: "1 passing · 1 advisory failures".
    assert "**2 OK**" in text
    assert "1 passing" in text
    assert "1 advisory failures" in text
    # And it does NOT roll into the failed bucket — the launch
    # is unblocked.
    assert "**1 failed**" not in text


# ---------------------------------------------------------------------------
# Top-line bucket structure
#
# Three buckets: OK / failed / failed-to-run.  Each bucket gets its own
# bullet under the ``## Status`` heading so a reader can answer "what
# blocks a launch?" by looking at the failed line alone.
# ---------------------------------------------------------------------------


def test_top_line_bullets_render_three_buckets(tmp_path: Path) -> None:
    """All three buckets render as bullets when each has at least one entry.

    OK = passed + N/A + advisory.  Failed = real failures.  Failed
    to run = errored + smoke-deferred + skipped.
    """
    test_outcomes = {
        "evals/cases/a/test_x.py::test_pass": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
        "evals/cases/a/test_x.py::test_fail": {
            "outcome": "failed", "duration": 0.1,
            "error": "X", "error_type": "assertion",
        },
        "evals/cases/b/test_x.py::test_err": {
            "outcome": "error", "duration": 0.1,
            "error": "X", "error_type": "infra",
        },
        "evals/cases/c/test_x.py::test_def": {
            "outcome": "smoke_failed", "duration": 0.1,
            "error": "X", "error_type": "smoke_failed",
            "smoke_reasoning": "...",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "- **1 OK**" in text
    assert "- **1 failed**" in text
    assert "- **2 failed to run**" in text
    # Per-cause sub-bullets group by module.  Smoke and infra each
    # have one module with one test in this fixture.
    assert "1 module (1 test) skipped because of smoke test failures" in text
    assert (
        "1 module (1 test) skipped because of infrastructure errors" in text
    )


def test_top_line_no_signal_bucket_includes_skipped(tmp_path: Path) -> None:
    """Skipped tests roll into the failed-to-run bucket.

    A skip is a deliberate non-run (e.g. a platform check), but for
    the launch-readiness question it produced no pass/fail signal —
    same shape as an errored or smoke-deferred test from the
    reviewer's perspective.  Skips don't cluster by module the way
    smoke and infra failures do, so they're rendered as a flat
    "M tests skipped" line, not "N modules (M tests)".
    """
    test_outcomes = {
        "evals/cases/x/test_x.py::test_skipped": {
            "outcome": "skipped", "duration": 0.0, "error": None,
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "- **1 failed to run**" in text
    assert "1 test skipped" in text


def test_top_line_omits_buckets_with_zero_count(tmp_path: Path) -> None:
    """A clean run with only passes shows just the OK bullet.

    No failed line, no failed-to-run line — empty buckets are
    skipped so a green run reads as a single short bullet under
    "Status: Passed".
    """
    test_outcomes = {
        f"x::test_{i}": {"outcome": "passed", "duration": 0.1, "error": None}
        for i in range(3)
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "## Status: Passed" in text
    assert "- **3 OK** (3 passing)" in text
    # No empty buckets.
    assert "**0 failed**" not in text
    assert "failed to run" not in text


def test_top_line_n_a_is_subcategory_of_passing(tmp_path: Path) -> None:
    """N/A is sub-category of OK, not a bucket of its own.

    A test with N/A judge verdicts still PASSED — N/A means
    "criterion didn't apply", not "criterion failed."  The OK
    count is total passing+advisory; N/A appears in the sub-list
    breakdown.
    """
    nodeid = "x::test_a"
    test_outcomes = {
        nodeid: {"outcome": "passed", "duration": 0.1, "error": None},
        "x::test_b": {"outcome": "passed", "duration": 0.1, "error": None},
    }
    judge_records = {
        nodeid: [JudgeRecord(claim="...", verdict="NA", reasoning="x", elapsed=0.1)],
    }
    write_summary(tmp_path, test_outcomes, judge_records)
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # 2 OK total: 1 clean pass + 1 N/A pass.
    assert "**2 OK**" in text
    assert "1 passing" in text
    assert "1 N/A" in text


def test_top_line_running_tests_get_their_own_line(tmp_path: Path) -> None:
    """Tests in flight (judge records exist but no outcome) get a
    separate '... still running' line.

    Useful for interrupted runs: the summary tells the reader what
    was mid-flight when they stopped, without conflating it with
    the OK / failed / failed-to-run buckets.
    """
    nodeid = "x::test_running"
    test_outcomes: dict[str, dict] = {}
    judge_records = {
        nodeid: [JudgeRecord(claim="...", verdict="YES", reasoning="x", elapsed=0.1)],
    }
    write_summary(tmp_path, test_outcomes, judge_records)
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "1 still running" in text


# ---------------------------------------------------------------------------
# Status header — single Passed / Failed / In-progress verdict the
# reviewer sees immediately under the metadata line.
#
# Fails closed: any non-OK outcome (real failure, infra error, smoke
# gap, plain skip) flips the status to Failed.  In-progress only fires
# when there are no recorded failures yet — once anything definitively
# breaks, an interrupted run still reads as Failed because the bad
# news is already known.
# ---------------------------------------------------------------------------


def test_status_passed_for_clean_run(tmp_path: Path) -> None:
    """Only OK outcomes → Status: Passed."""
    test_outcomes = {
        "evals/cases/x/test_x.py::test_a": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
        "evals/cases/x/test_x.py::test_b": {
            "outcome": "advisory_failed", "duration": 0.1,
            "error": "X", "error_type": "assertion",
        },
        "evals/cases/x/test_x.py::test_c": {
            "outcome": "refused", "duration": 0.0, "error": None,
            "smoke_reasoning": "Agent declined.",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "## Status: Passed" in text
    # Belt and suspenders — the negative form must NOT appear.
    assert "## Status: Failed" not in text


def test_status_failed_when_a_real_failure_exists(tmp_path: Path) -> None:
    """One assertion failure is enough → Status: Failed."""
    test_outcomes = {
        "evals/cases/x/test_x.py::test_a": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
        "evals/cases/x/test_x.py::test_b": {
            "outcome": "failed", "duration": 0.1,
            "error": "X", "error_type": "assertion",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "## Status: Failed" in text


def test_status_failed_when_only_failed_to_run(tmp_path: Path) -> None:
    """No assertion failures but tests didn't produce signal → Failed.

    A run with only smoke-failed or infra-errored tests is NOT a
    clean pass — there's a coverage gap that needs investigation,
    even if no test ever returned a real ❌.
    """
    test_outcomes = {
        "evals/cases/x/test_x.py::test_a": {
            "outcome": "smoke_failed", "duration": 0.1,
            "error": "X", "error_type": "smoke_failed",
            "smoke_reasoning": "...",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "## Status: Failed" in text


def test_status_in_progress_when_only_running(tmp_path: Path) -> None:
    """Interrupted run with no recorded outcomes → Status: In progress.

    Distinct from Passed (no outcomes recorded ≠ all outcomes
    passed) and from Failed (nothing has actually failed yet).
    Tells a reviewer skimming an in-flight summary that this is a
    snapshot, not a verdict.
    """
    nodeid = "evals/cases/x/test_x.py::test_a"
    judge_records = {
        nodeid: [
            JudgeRecord(
                claim="...", verdict="YES", reasoning="x", elapsed=0.1,
            ),
        ],
    }
    write_summary(tmp_path, {}, judge_records)
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "## Status: In progress" in text


def test_metadata_line_combines_generated_time_and_cost(
    tmp_path: Path,
) -> None:
    """The metadata line under the title fuses generated/time/cost.

    Avoids burning two header lines on what's really one piece of
    operational metadata.  ``cost`` is omitted when zero so dry-run
    summaries don't render a misleading "$0.0000" line.
    """
    test_outcomes = {
        "evals/cases/x/test_x.py::test_a": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
    }
    write_summary(tmp_path, test_outcomes, {}, total_seconds=12.5)
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # All three pieces on one line, separated by middle dots.
    line = next(
        ln for ln in text.splitlines() if ln.startswith("Generated:")
    )
    assert "Generated:" in line
    assert "total time: 12.5s" in line
    # Zero cost is suppressed (no judge records → no cost).
    assert "cost:" not in line


def test_config_block_renders_after_status_with_renamed_label(
    tmp_path: Path,
) -> None:
    """Per-role config sits AFTER the Status section, labelled "Config".

    Operational metadata (which model, which provider) is useful
    but secondary to the pass/fail verdict — a reviewer should see
    the verdict first.  Old name was "Models", which under-sold what
    the block actually covers (provider, auth mode, etc.).
    """
    from evals.framework.config import EvalConfig, RoleConfig

    config = EvalConfig(
        roles={
            "target": RoleConfig(
                provider="github", model="", auth_mode="gh_cli",
            ),
            "user": RoleConfig(
                provider="azure", model="gpt-4o", auth_mode="default",
            ),
            "judge": RoleConfig(
                provider="github", model="claude-opus-4-6",
                auth_mode="gh_cli",
            ),
        },
    )
    test_outcomes = {
        "evals/cases/x/test_x.py::test_a": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
    }
    write_summary(tmp_path, test_outcomes, {}, config=config)
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # New label.
    assert "**Config:**" in text
    # Old label gone.
    assert "**Models:**" not in text
    # Order: Status section comes BEFORE the config block.
    assert text.index("## Status") < text.index("**Config:**")


def test_module_aggregate_advisory_icon_precedence() -> None:
    """Advisory icon (💡) only shows when there are NO clean passes.

    A module that mostly passed but had a few advisory failures
    should still read as ✅ — advisories don't block, and 💡 on
    a mostly-passing module misleads the eye into thinking the
    module had problems.

    The 💡 icon stays meaningful for the all-advisories case
    (no clean passes), where it signals "this whole module is in
    'needs improvement' state."

    Real failures still outrank advisories regardless of pass count.
    """
    # All advisories, no passes: 💡 (signals "no clean passes here").
    icon, _ = _module_aggregate(["advisory_failed"], na_count=0)
    assert icon == "\U0001F4A1"  # 💡
    icon, _ = _module_aggregate(
        ["advisory_failed", "advisory_failed"], na_count=0,
    )
    assert icon == "\U0001F4A1"

    # Pass + advisory: ✅ (advisory does NOT outrank passed).
    icon, _ = _module_aggregate(["passed", "advisory_failed"], na_count=0)
    assert icon == "✅"

    # Refused + advisory: ✅ (refused counts the same as passed for icon).
    icon, _ = _module_aggregate(
        ["refused", "advisory_failed"], na_count=0,
    )
    assert icon == "✅"

    # Mix of failed + advisory: ❌ (real failure outranks both
    # passed and advisory — module has a blocking failure).
    icon, _ = _module_aggregate(["failed", "advisory_failed"], na_count=0)
    assert icon == "❌"

    # Mix of failed + passed + advisory: ❌ (real failure still wins).
    icon, _ = _module_aggregate(
        ["passed", "failed", "advisory_failed"], na_count=0,
    )
    assert icon == "❌"

    # Mix of smoke_failed + advisory: 🛑 (smoke failure outranks all).
    icon, _ = _module_aggregate(
        ["smoke_failed", "advisory_failed"], na_count=0,
    )
    assert icon == "\U0001F6D1"


def test_module_aggregate_advisory_rolled_into_pass_count() -> None:
    """Module stats roll advisory-failed into the pass count.

    Same treatment as the top-line OK bucket — advisories don't
    block, so they count as part of "OK."  The "X/N passed"
    number reflects passes-plus-advisories; advisories get a
    separately-named sub-count so reviewers can see the breakdown.
    """
    _, stats = _module_aggregate(
        ["passed", "advisory_failed"], na_count=0,
    )
    # Pass count includes advisory: 2 OK out of 2 total.
    assert "2/2 passed" in stats
    # Advisory called out as a sub-category — singular "advisory"
    # for one, "advisories" plural for many.
    assert "1 advisory" in stats


def test_module_aggregate_advisory_pluralization() -> None:
    """Singular vs. plural form of "advisory"."""
    _, stats = _module_aggregate(
        ["passed", "advisory_failed", "advisory_failed"], na_count=0,
    )
    # Two advisories → plural form.
    assert "2 advisories" in stats


# ---------------------------------------------------------------------------
# Conftest hook: @advisory failure rewrite
#
# Drives evals/conftest.py's ``pytest_runtest_makereport`` directly
# with mock ``item`` and ``call`` objects so the hook's outcome
# rewrite is exercised without spinning pytest up in a subprocess.
# ---------------------------------------------------------------------------


class _FakeMarker:
    def __init__(self, name: str) -> None:
        self.name = name
        # Match pytest's MarkDecorator surface.  Tests that exercise
        # marker arguments (e.g. ``@advisory("url")``) override
        # these via subclass; the default empty-args/kwargs shape
        # corresponds to bare ``@advisory`` usage.
        self.args: tuple[object, ...] = ()
        self.kwargs: dict[str, object] = {}


class _FakeItem:
    """Minimum surface ``pytest_runtest_makereport`` reads off ``item``."""

    def __init__(
        self, nodeid: str, *, marker: str | None = None,
    ) -> None:
        self.nodeid = nodeid
        self._marker = _FakeMarker(marker) if marker else None
        # makereport calls _snapshot_summary(item.config) — a trivial
        # MagicMock-style stand-in is fine since _snapshot_summary
        # bails when there are no test_outcomes / output_dir.
        self.config = type("FakeConfig", (), {"getoption": lambda self, _: None})()
        # ``location`` is a 3-tuple ``(filename, lineno, domain)`` —
        # pytest's standard Item attribute.  The conftest uses it
        # to build the skip ``longrepr`` 3-tuple for refused tests.
        self.location: tuple[str, int, str] = (
            f"{nodeid.split('::')[0]}", 0, nodeid.split("::")[-1],
        )

    def get_closest_marker(self, name: str) -> _FakeMarker | None:
        return self._marker if self._marker and self._marker.name == name else None


class _FakeExcInfo:
    def __init__(self, exc: BaseException) -> None:
        self.value = exc
        self.type = type(exc)

    def errisinstance(self, cls: type) -> bool:
        return isinstance(self.value, cls)


class _FakeCall:
    def __init__(self, when: str, exc: BaseException | None = None) -> None:
        self.when = when
        self.excinfo = _FakeExcInfo(exc) if exc is not None else None


class _FakeReport:
    def __init__(
        self, when: str, outcome: str, *, longreprtext: str = "",
    ) -> None:
        self.when = when
        self.outcome = outcome
        self.duration = 0.1
        self.longreprtext = longreprtext
        # ``longrepr`` is what pytest renders as the skip-reason
        # text; the conftest's refused-handling rewrites it.  Keep
        # it as a writable attribute so tests can mutate it freely.
        self.longrepr: object = longreprtext


class _FakeOutcome:
    def __init__(self, report: _FakeReport) -> None:
        self._report = report

    def get_result(self) -> _FakeReport:
        return self._report


def _drive_makereport(item: _FakeItem, call: _FakeCall, report: _FakeReport) -> None:
    """Drive the hookwrapper generator through one full cycle."""
    from evals.conftest import pytest_runtest_makereport

    gen = pytest_runtest_makereport(item, call)
    # First next() runs to ``outcome = yield``.
    next(gen)
    # send() resumes the generator, providing the outcome value the
    # hook would normally receive from pytest's plugin manager.
    try:
        gen.send(_FakeOutcome(report))
    except StopIteration:
        pass


def test_advisory_marker_rewrites_failed_assertion_to_passed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end on the hook: ``@advisory`` + AssertionError →
    report outcome rewritten to "passed", _test_outcomes records
    "advisory_failed".
    """
    from evals import conftest

    monkeypatch.setattr(conftest, "_test_outcomes", {})
    item = _FakeItem(
        "evals/cases/fn/test_x.py::test_a", marker="advisory",
    )
    call = _FakeCall("call", AssertionError("nope"))
    report = _FakeReport("call", "failed", longreprtext="AssertionError: nope")

    _drive_makereport(item, call, report)

    # Pytest's view: passed (so exit code stays 0).
    assert report.outcome == "passed"
    # Critically NOT ``wasxfail = "advisory"``.  That attribute is
    # how pytest tags expected-failure-but-passed tests; setting it
    # makes pytest reclassify ours as XPASSED, polluting the
    # "N xpassed" line in the session summary.  The clean
    # ``"passed"`` outcome is enough — advisory accounting lives
    # in summary.md.
    assert getattr(report, "wasxfail", None) is None
    # Our summary's view: routed to the advisory bucket.
    assert (
        conftest._test_outcomes[item.nodeid]["outcome"] == "advisory_failed"
    )
    assert conftest._test_outcomes[item.nodeid]["error_type"] == "assertion"


def test_advisory_marker_does_not_rewrite_passed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A passing ``@advisory`` test stays a normal pass — no rewrite.

    The marker only kicks in on failure; passes report exactly like
    any other test.
    """
    from evals import conftest

    monkeypatch.setattr(conftest, "_test_outcomes", {})
    item = _FakeItem(
        "evals/cases/fn/test_x.py::test_a", marker="advisory",
    )
    call = _FakeCall("call")  # no exception
    report = _FakeReport("call", "passed")

    _drive_makereport(item, call, report)

    assert report.outcome == "passed"
    assert getattr(report, "wasxfail", None) is None
    assert (
        conftest._test_outcomes[item.nodeid]["outcome"] == "passed"
    )


def test_advisory_marker_does_not_rewrite_infra_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Infrastructure errors are blocking even with ``@advisory``.

    The marker is for "this assertion is aspirational, don't gate
    on it" — it isn't license to ignore broken backends or fixture
    crashes.  The hook should NOT rewrite, AND should let pytest's
    fail-fast (pytest.exit) fire if applicable.
    """
    from evals import conftest

    monkeypatch.setattr(conftest, "_test_outcomes", {})
    item = _FakeItem(
        "evals/cases/fn/test_x.py::test_a", marker="advisory",
    )
    # RuntimeError is classified as "infra" by _classify_error.
    call = _FakeCall("call", RuntimeError("backend exploded"))
    report = _FakeReport("call", "failed", longreprtext="RuntimeError")
    # Stub out pytest.exit so the test doesn't actually abort.
    exit_called = []
    monkeypatch.setattr(
        pytest, "exit",
        lambda msg, returncode=1: exit_called.append((msg, returncode)),
    )

    _drive_makereport(item, call, report)

    # Did NOT rewrite — infra failures still register as failed.
    assert report.outcome == "failed"
    assert (
        conftest._test_outcomes[item.nodeid]["outcome"] == "failed"
    )
    # And pytest.exit was triggered (infra failure is fail-fast).
    assert exit_called, "expected pytest.exit on infra failure"


def test_unmarked_test_failure_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A test without ``@advisory`` follows the existing failure path."""
    from evals import conftest

    monkeypatch.setattr(conftest, "_test_outcomes", {})
    item = _FakeItem("evals/cases/fn/test_x.py::test_a", marker=None)
    call = _FakeCall("call", AssertionError("real failure"))
    report = _FakeReport("call", "failed", longreprtext="AssertionError")

    _drive_makereport(item, call, report)

    # Outcome stays failed — no marker, no rewrite.
    assert report.outcome == "failed"
    assert (
        conftest._test_outcomes[item.nodeid]["outcome"] == "failed"
    )


# ---------------------------------------------------------------------------
# @advisory issue-tracker URL: extraction + rendering
#
# ``@advisory("https://...")`` and ``@advisory(issue="https://...")``
# both attach a tracker URL to the marker.  The conftest hook reads
# it off the marker on advisory_failed; the report renders it next
# to the test name (compact link in the table, full link in details).
# GitHub issue URLs render as ``#NNN``; other URLs as 🔗.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url, expected", [
    (
        "https://github.com/microsoft/clarity-agent/issues/174",
        "[#174](https://github.com/microsoft/clarity-agent/issues/174)",
    ),
    (
        # http (not https) — same handling.
        "http://github.com/owner/repo/issues/3",
        "[#3](http://github.com/owner/repo/issues/3)",
    ),
    (
        # www. prefix — tolerated.
        "https://www.github.com/owner/repo/issues/42",
        "[#42](https://www.github.com/owner/repo/issues/42)",
    ),
    (
        # trailing slash — tolerated, captured number unchanged.
        "https://github.com/owner/repo/issues/12/",
        "[#12](https://github.com/owner/repo/issues/12/)",
    ),
])
def test_format_issue_link_short_recognizes_github_urls(
    url: str, expected: str,
) -> None:
    """GitHub issue URLs render as the bare ``#NNN`` form."""
    assert _format_issue_link_short(url) == expected


def test_format_issue_link_short_falls_back_to_chain_link() -> None:
    """Non-GitHub URLs render as a chain-link emoji.

    Generic enough for JIRA, Linear, internal trackers — without
    pretending the URL has GitHub semantics.
    """
    url = "https://example.com/issues/abc-123"
    assert _format_issue_link_short(url) == f"[\U0001F517]({url})"


def test_format_issue_link_short_does_not_match_partial_url() -> None:
    """A GitHub URL embedded in a longer string doesn't match.

    The regex is anchored — the whole string must be the URL — so
    ``"see https://github.com/.../issues/1 for context"`` does NOT
    get mistakenly compacted to ``#1``.
    """
    url_in_sentence = (
        "see https://github.com/owner/repo/issues/1 for context"
    )
    # Falls through to the generic 🔗 form.
    assert "#" not in _format_issue_link_short(url_in_sentence)


def test_format_issue_link_short_handles_empty() -> None:
    """Empty string → empty link (no crash, no spurious markdown)."""
    assert _format_issue_link_short("") == ""
    assert _format_issue_link_short("   ") == ""


def test_format_issue_link_long_uses_full_url_for_non_github() -> None:
    """Long form: GH-shortened, but other URLs render as full
    ``[url](url)`` so the reviewer can see what tracker it points
    at without having to hover.
    """
    gh = "https://github.com/owner/repo/issues/9"
    other = "https://linear.app/team/issue/ABC-7"
    assert _format_issue_link_long(gh) == f"[#9]({gh})"
    assert _format_issue_link_long(other) == f"[{other}]({other})"


def test_advisory_marker_captures_positional_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``@advisory("url")`` stores the URL on _test_outcomes.

    Positional form is the user's preferred shorthand from the
    original ask.  Captured as ``advisory_issue`` next to the
    test's outcome record.
    """
    from evals import conftest

    monkeypatch.setattr(conftest, "_test_outcomes", {})

    class _MarkerWithArgs:
        name = "advisory"
        args = ("https://github.com/microsoft/clarity-agent/issues/174",)
        kwargs: dict[str, str] = {}

    class _ItemWithMarker(_FakeItem):
        def get_closest_marker(self, name: str) -> object:  # noqa: ARG002
            return _MarkerWithArgs()

    item = _ItemWithMarker(
        "evals/cases/fn/test_x.py::test_a", marker="advisory",
    )
    call = _FakeCall("call", AssertionError("nope"))
    report = _FakeReport("call", "failed", longreprtext="AssertionError")

    _drive_makereport(item, call, report)

    rec = conftest._test_outcomes[item.nodeid]
    assert rec["outcome"] == "advisory_failed"
    assert rec["advisory_issue"] == (
        "https://github.com/microsoft/clarity-agent/issues/174"
    )


def test_advisory_marker_captures_keyword_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``@advisory(issue="url")`` works the same as positional."""
    from evals import conftest

    monkeypatch.setattr(conftest, "_test_outcomes", {})

    class _MarkerWithKwargs:
        name = "advisory"
        args: tuple[str, ...] = ()
        kwargs = {"issue": "https://example.com/tickets/42"}

    class _ItemWithMarker(_FakeItem):
        def get_closest_marker(self, name: str) -> object:  # noqa: ARG002
            return _MarkerWithKwargs()

    item = _ItemWithMarker("evals/cases/fn/test_x.py::test_b")
    call = _FakeCall("call", AssertionError("nope"))
    report = _FakeReport("call", "failed", longreprtext="AssertionError")

    _drive_makereport(item, call, report)

    rec = conftest._test_outcomes[item.nodeid]
    assert rec["outcome"] == "advisory_failed"
    assert rec["advisory_issue"] == "https://example.com/tickets/42"


def test_advisory_marker_no_url_stores_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bare ``@advisory`` (no args) leaves ``advisory_issue`` as None.

    Zero-argument usage stays the cheap fallthrough path; the
    rendering layer treats ``None`` as "no link to show."
    """
    from evals import conftest

    monkeypatch.setattr(conftest, "_test_outcomes", {})
    item = _FakeItem(
        "evals/cases/fn/test_x.py::test_c", marker="advisory",
    )
    call = _FakeCall("call", AssertionError("nope"))
    report = _FakeReport("call", "failed", longreprtext="AssertionError")

    _drive_makereport(item, call, report)

    assert conftest._test_outcomes[item.nodeid]["advisory_issue"] is None


def test_summary_table_advisory_word_links_to_issue(
    tmp_path: Path,
) -> None:
    """End-to-end: the word "advisory" in the Outcome cell IS the
    link to the tracking issue.

    Older design appended a separate ``[#NNN]`` tag onto the test
    name — that read awkwardly because the test name and the
    issue tag are conceptually different.  The advisory-tracking
    URL semantically belongs to the OUTCOME (the test is advisory
    *because* of issue #NNN), so the link goes on the outcome
    word.
    """
    url = "https://github.com/microsoft/clarity-agent/issues/174"
    test_outcomes = {
        "evals/cases/fn/test_x.py::test_a": {
            "outcome": "advisory_failed", "duration": 0.1,
            "error": "AssertionError",
            "error_type": "assertion",
            "advisory_issue": url,
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # Outcome cell contains "[advisory](url)" — the word IS the link.
    assert f"[advisory]({url})" in text
    # Defensive: the test-name cell does NOT also carry an issue
    # tag — that's the old layout we replaced.
    assert "test_a`](#test-evals-cases-fn-test_x-py--test_a) [#174]" not in text
    assert "test_a`](#test-evals-cases-fn-test_x-py--test_a) [🔗]" not in text


def test_summary_table_advisory_link_works_for_non_github_urls(
    tmp_path: Path,
) -> None:
    """Non-GitHub trackers also link the "advisory" word — no
    GH-specific shortening needed since the link text is just the
    outcome word, uniform across providers.
    """
    url = "https://linear.app/team/issue/ABC-7"
    test_outcomes = {
        "evals/cases/fn/test_x.py::test_a": {
            "outcome": "advisory_failed", "duration": 0.1,
            "error": "AssertionError",
            "error_type": "assertion",
            "advisory_issue": url,
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert f"[advisory]({url})" in text


def test_summary_table_advisory_no_url_renders_plain_word(
    tmp_path: Path,
) -> None:
    """advisory_failed without a URL renders the bare word (no link)."""
    test_outcomes = {
        "evals/cases/fn/test_x.py::test_a": {
            "outcome": "advisory_failed", "duration": 0.1,
            "error": "AssertionError",
            "error_type": "assertion",
            "advisory_issue": None,
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # The plain word — no surrounding ``[`` ``]()`` link syntax.
    assert "💡 advisory" in text
    # No accidental link constructed from None.
    assert "[advisory](None)" not in text
    # No detail-section "Tracked in:" line.
    assert "Tracked in:" not in text


def test_summary_table_no_link_for_passing_test_with_advisory_marker(
    tmp_path: Path,
) -> None:
    """A passing test that happens to have ``advisory_issue`` set
    (e.g. a stale leftover) does NOT show the issue link.

    Defensive: the report only surfaces the issue link when the
    test actually entered the advisory_failed bucket — passing
    tests don't need a tracker pointer.
    """
    test_outcomes = {
        "evals/cases/fn/test_x.py::test_a": {
            "outcome": "passed", "duration": 0.1, "error": None,
            "advisory_issue": (
                "https://github.com/microsoft/clarity-agent/issues/1"
            ),
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # No advisory link constructed — the test passed, the
    # advisory_issue field is a stale leftover that shouldn't
    # surface anywhere in the rendering.
    assert "[advisory]" not in text
    assert "Tracked in:" not in text


def test_summary_details_renders_tracked_in_for_advisory_failed(
    tmp_path: Path,
) -> None:
    """End-to-end: details section gets a ``**Tracked in:**`` line
    under the test heading on advisory_failed."""
    test_outcomes = {
        "evals/cases/fn/test_x.py::test_a": {
            "outcome": "advisory_failed", "duration": 0.1,
            "error": "AssertionError",
            "error_type": "assertion",
            "advisory_issue": "https://example.com/tickets/42",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "**Tracked in:**" in text
    # Non-GH URL → full link text.
    assert "https://example.com/tickets/42" in text


# ---------------------------------------------------------------------------
# Substantivity smoke gate
#
# Pure-code gate (no LLM) that fires when a conversation produced
# fewer turns than ``_MIN_SUBSTANTIVE_TURNS``.  Promoted from the
# old per-test ``test_conversation_was_substantive`` assertion to a
# framework gate so the whole module aborts cleanly rather than
# producing meaningless verdicts on a one-shot exchange.
# ---------------------------------------------------------------------------


def test_substantivity_check_passes_at_threshold() -> None:
    """Exactly ``_MIN_SUBSTANTIVE_TURNS`` turns → passes."""
    passed, reasoning = _substantivity_check(_MIN_SUBSTANTIVE_TURNS)
    assert passed is True
    assert str(_MIN_SUBSTANTIVE_TURNS) in reasoning


def test_substantivity_check_passes_above_threshold() -> None:
    """A long conversation passes."""
    passed, _ = _substantivity_check(15)
    assert passed is True


def test_substantivity_check_fails_below_threshold() -> None:
    """A 1-turn conversation fails the default ``>= 2`` threshold."""
    passed, reasoning = _substantivity_check(1)
    assert passed is False
    # Reasoning explains the typical cause so a reviewer doesn't
    # have to guess.
    assert "gave up" in reasoning or "refused" in reasoning


def test_substantivity_check_fails_at_zero() -> None:
    """Zero turns → fails — the conversation never produced an exchange."""
    passed, _ = _substantivity_check(0)
    assert passed is False


def test_substantivity_check_custom_threshold() -> None:
    """Threshold is overridable via the ``min_turns`` keyword."""
    assert _substantivity_check(3, min_turns=4) == (
        False,
        "Conversation had only 3 turn(s); at least 4 required.  "
        "Likely the user-LLM gave up immediately or the target "
        "refused to engage.",
    )
    assert _substantivity_check(4, min_turns=4)[0] is True


def test_substantivity_claim_is_stable() -> None:
    """Same threshold → identical claim text — cache key stays stable."""
    a = _substantivity_claim_for(2)
    b = _substantivity_claim_for(2)
    assert a == b
    # And the threshold is in the claim, so a different threshold
    # produces a different cache key.
    assert _substantivity_claim_for(2) != _substantivity_claim_for(4)


def test_substantivity_record_has_yes_for_passing_count() -> None:
    """Synthetic record carries the verdict + reasoning the report needs."""
    rec = _make_substantivity_record(5)
    assert rec.verdict == "YES"
    assert rec.elapsed == 0.0  # no LLM call
    assert rec.cost_usd == 0.0
    assert "5 turn" in rec.reasoning


def test_substantivity_record_has_no_for_failing_count() -> None:
    """A failing turn count produces a NO verdict + failure reasoning."""
    rec = _make_substantivity_record(0)
    assert rec.verdict == "NO"
    assert "0 turn" in rec.reasoning


def test_substantivity_cache_key_distinct_from_others() -> None:
    """The cache key doesn't collide with the other smoke gates."""
    assert _SUBSTANTIVITY_CACHE_KEY != "__goal_pursued__"
    assert _SUBSTANTIVITY_CACHE_KEY != "__persona_adoption__"
    # And it follows the reserved-name convention (leading + trailing
    # double-underscore) so test functions can't accidentally use it.
    assert _SUBSTANTIVITY_CACHE_KEY.startswith("__")
    assert _SUBSTANTIVITY_CACHE_KEY.endswith("__")


def test_substantivity_record_appears_in_report_table(tmp_path: Path) -> None:
    """End-to-end: a substantivity record renders as a smoke-gate row."""
    # Seed all three gate records on disk; the loader picks up
    # __substantivity__ from the cache like any other gate.
    mod_dir = tmp_path / "x/test_x"
    mod_dir.mkdir(parents=True)
    (mod_dir / "judge_records.json").write_text(json.dumps({
        "schema_version": 1, "conversation_fingerprint": "fp",
        "tests": {
            "__persona_adoption__": [{
                "claim": "...", "verdict": "YES", "reasoning": "x",
                "elapsed": 1.0, "cost_usd": 0.01, "cached": False,
            }],
            "__substantivity__": [{
                "claim": "...", "verdict": "YES",
                "reasoning": "Conversation had 5 turn(s); minimum required: 2.",
                "elapsed": 0.0, "cost_usd": 0.0, "cached": False,
            }],
            "__goal_pursued__": [{
                "claim": "...", "verdict": "YES", "reasoning": "x",
                "elapsed": 5.0, "cost_usd": 0.02, "cached": False,
            }],
        },
    }))
    test_outcomes = {
        "evals/cases/x/test_x.py::test_a": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # All three gate labels appear, in run order.
    persona_idx = text.find("persona-adoption check")
    substantivity_idx = text.find("substantivity check")
    smoke_idx = text.find("goal-pursued check")
    assert persona_idx >= 0
    assert substantivity_idx >= 0
    assert smoke_idx >= 0
    assert persona_idx < substantivity_idx < smoke_idx, (
        "gates must render in run order: persona-adoption (turn 1), "
        "then substantivity (instant post-conversation check), "
        "then smoke (LLM judge call)"
    )


# ---------------------------------------------------------------------------
# Refusal gate: @refusal_acceptable marker + AgentRefusedError + rendering
#
# Optional fourth smoke gate, runs ONLY for modules marked
# ``@refusal_acceptable``.  Inverted semantics — REFUSED (YES) is a
# success short-circuit, ENGAGED (NO) is a neutral fall-through to
# the other gates.  Refused tests count toward the OK bucket.
# ---------------------------------------------------------------------------


def test_refusal_marker_re_exported_from_framework() -> None:
    """``from evals.framework import refusal_acceptable`` is the public path.

    Identical pattern to ``advisory`` — re-exported pytest mark so
    eval authors don't need to know the marker namespace.  Module
    use is the typical case (``pytestmark = refusal_acceptable``)
    but per-test use also works.
    """
    from evals.framework import refusal_acceptable

    @refusal_acceptable
    def some_test() -> None:
        pass

    assert any(
        m.name == "refusal_acceptable"
        for m in some_test.pytestmark  # type: ignore[attr-defined]
    )


def test_refusal_claim_includes_goal() -> None:
    """The judge sees the user's goal in the claim text."""
    claim = _refusal_claim_for("learn how to do something problematic")
    assert "learn how to do something problematic" in claim


def test_refusal_claim_explicitly_says_no_is_not_failure() -> None:
    """Regression guard: the judge prompt must explicitly say NO is
    NOT a failure, otherwise the judge defaults to NO out of caution
    and the gate's purpose breaks down.
    """
    claim = _refusal_claim_for("a goal")
    assert "NO is NOT a failure" in claim or "not a failure" in claim.lower()


def test_refusal_claim_is_stable() -> None:
    """Identical inputs → identical claim text.  Cache key stays stable."""
    a = _refusal_claim_for("the goal")
    b = _refusal_claim_for("the goal")
    assert a == b


def test_refusal_cache_key_distinct() -> None:
    """``__refusal__`` doesn't collide with the other reserved keys."""
    assert _REFUSAL_CACHE_KEY != "__goal_pursued__"
    assert _REFUSAL_CACHE_KEY != "__persona_adoption__"
    assert _REFUSAL_CACHE_KEY != _SUBSTANTIVITY_CACHE_KEY
    assert _REFUSAL_CACHE_KEY.startswith("__")
    assert _REFUSAL_CACHE_KEY.endswith("__")


def test_agent_refused_error_carries_reasoning() -> None:
    """AgentRefusedError stores the judge's reasoning for the report."""
    err = AgentRefusedError("test", reasoning="agent declined cleanly")
    assert err.reasoning == "agent declined cleanly"
    # Subclass of AssertionError so pytest treats it as a test
    # signal (not an unexpected exception).  But conftest detects
    # the exact class to route differently from real assertions.
    assert isinstance(err, AssertionError)


# ---------------------------------------------------------------------------
# Conftest hook: AgentRefusedError → "refused" outcome bucket
# ---------------------------------------------------------------------------


def test_classify_error_routes_agent_refused_to_refused_bucket() -> None:
    """``_classify_error`` recognizes AgentRefusedError as its own type.

    Distinct from "smoke_failed" so the conftest can rewrite the
    pytest report differently (success short-circuit, not module
    abort with reasoning banner).
    """
    from evals.conftest import _classify_error

    class FakeExcInfo:
        def __init__(self, exc: BaseException) -> None:
            self.value = exc
            self.type = type(exc)

        def errisinstance(self, cls) -> bool:
            return isinstance(self.value, cls)

    class FakeCall:
        def __init__(self, exc: BaseException | None) -> None:
            self.excinfo = FakeExcInfo(exc) if exc is not None else None

    assert _classify_error(
        FakeCall(AgentRefusedError("x", reasoning="r"))
    ) == "refused"
    # Sanity: smoke / assertion / infra still classified as before.
    assert _classify_error(
        FakeCall(SmokeCheckFailedError("x"))
    ) == "smoke_failed"
    assert _classify_error(FakeCall(AssertionError("x"))) == "assertion"
    assert _classify_error(FakeCall(RuntimeError("x"))) == "infra"


def test_setup_phase_refused_rewrites_outcome_to_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setup-phase AgentRefusedError → report.outcome = "skipped".

    Regression test for the KeyError observed in the 2026-05-01 run:
    rewriting setup-phase outcome to "passed" (the @advisory trick)
    made pytest proceed to the call phase, which then KeyErrored on
    the missing ``result`` fixture argument because the fixture had
    raised before producing a value.

    The fix uses "skipped" instead — pytest skips the call cleanly,
    test doesn't count toward exit code, AND we preserve the
    "refused" label in our own outcome dict for the summary.
    """
    from evals import conftest

    monkeypatch.setattr(conftest, "_test_outcomes", {})

    item = _FakeItem("evals/cases/safety/test_x.py::test_a")
    call = _FakeCall(
        "setup", AgentRefusedError("x", reasoning="agent declined cleanly"),
    )
    report = _FakeReport(
        "setup", "failed",
        longreprtext="huge AgentRefusedError traceback...",
    )
    # Add a longrepr attribute so the conftest can rewrite it.
    report.longrepr = "huge AgentRefusedError traceback..."

    _drive_makereport(item, call, report)

    # Pytest's view: skipped (so call phase doesn't run AND exit
    # code stays 0).  Critically NOT "passed" — that triggers the
    # KeyError.
    assert report.outcome == "skipped"
    # The longrepr is now the 3-tuple format pytest expects for
    # skipped tests: ``(filename, lineno, reason)``.  See
    # ``test_setup_phase_refused_longrepr_is_3_tuple`` for the
    # detailed contract.  Reason text is human-readable, not a
    # traceback.
    assert isinstance(report.longrepr, tuple)
    _, _, reason = report.longrepr
    assert "refused" in reason.lower()
    assert "traceback" not in reason.lower()
    # Our summary's view: routed to refused.
    assert (
        conftest._test_outcomes[item.nodeid]["outcome"] == "refused"
    )


def test_setup_phase_refused_longrepr_is_3_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``report.longrepr`` MUST be ``(filename, lineno, reason)``.

    Regression for an INTERNALERROR observed when re-running with
    cached results.  Pytest's terminal reporter renders skip
    reasons via ``_pytest.terminal._get_raw_skip_reason``, which
    asserts ``isinstance(report.longrepr, tuple)`` — a plain string
    crashes pytest with an opaque AssertionError deep inside the
    pluggy hook chain.  Locking in the tuple format here so the
    failure mode can't silently regress.
    """
    from evals import conftest

    monkeypatch.setattr(conftest, "_test_outcomes", {})

    item = _FakeItem("evals/cases/safety/test_x.py::test_a")
    call = _FakeCall("setup", AgentRefusedError("x", reasoning="declined"))
    report = _FakeReport("setup", "failed", longreprtext="trace")
    report.longrepr = "trace"

    _drive_makereport(item, call, report)

    # 3-tuple contract: (filename, lineno, reason).
    assert isinstance(report.longrepr, tuple)
    assert len(report.longrepr) == 3
    filename, lineno, reason = report.longrepr
    # filename: a string (path or stub) — used by pytest for source
    # links in IDE / verbose output.
    assert isinstance(filename, str)
    # lineno: an int (0 is fine when we don't have a meaningful
    # line; pytest just won't link to a specific line).
    assert isinstance(lineno, int)
    # reason: the human-readable skip message.
    assert isinstance(reason, str)
    assert "refused" in reason.lower()


def test_setup_phase_refused_does_not_trigger_session_abort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refused tests must NOT invoke pytest.exit.

    Defensive: ``pytest.exit`` is only called for ``error_type ==
    "infra"`` AND ``report.outcome == "failed"``.  Refused
    rewrites outcome to "skipped" before the abort check, so
    even if the classification logic somehow regressed, the
    abort guard wouldn't fire.
    """
    from evals import conftest

    monkeypatch.setattr(conftest, "_test_outcomes", {})
    exit_called = []
    monkeypatch.setattr(
        pytest, "exit",
        lambda msg, returncode=1: exit_called.append((msg, returncode)),
    )

    item = _FakeItem("evals/cases/safety/test_x.py::test_a")
    call = _FakeCall("setup", AgentRefusedError("x", reasoning="r"))
    report = _FakeReport("setup", "failed", longreprtext="trace")
    report.longrepr = "trace"

    _drive_makereport(item, call, report)

    assert exit_called == [], "refused must not invoke pytest.exit"


def test_setup_phase_smoke_failed_rewrites_outcome_to_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setup-phase SmokeCheckFailedError → report.outcome = "skipped".

    Without the rewrite, pytest renders these as ERROR in the
    terminal — one ERROR line per test in a smoke-failed module,
    which buries every other module's outcomes in noise.  The
    framework already classifies smoke_failed as "no signal" (the
    test never ran meaningfully), and "skipped" is pytest's
    closest match: call phase doesn't run, exit code stays 0,
    terminal stays readable.  summary.md still surfaces the
    framework's ``smoke_failed`` label in the no-signal bucket.
    """
    from evals import conftest

    monkeypatch.setattr(conftest, "_test_outcomes", {})

    item = _FakeItem("evals/cases/fn/test_x.py::test_a")
    call = _FakeCall(
        "setup",
        SmokeCheckFailedError("x", reasoning="user drifted off persona"),
    )
    report = _FakeReport(
        "setup", "failed",
        longreprtext="huge SmokeCheckFailedError traceback...",
    )
    report.longrepr = "huge SmokeCheckFailedError traceback..."

    _drive_makereport(item, call, report)

    # Pytest's view: skipped (call phase doesn't run, exit stays 0).
    assert report.outcome == "skipped"
    # 3-tuple longrepr — a plain string crashes pytest's terminal
    # reporter (see test_setup_phase_refused_longrepr_is_3_tuple).
    assert isinstance(report.longrepr, tuple)
    assert len(report.longrepr) == 3
    _, _, reason = report.longrepr
    assert "smoke" in reason.lower()
    assert "traceback" not in reason.lower()
    # Our summary's view: routed to smoke_failed (no-signal bucket).
    assert (
        conftest._test_outcomes[item.nodeid]["outcome"] == "smoke_failed"
    )


def test_setup_phase_smoke_failed_does_not_trigger_session_abort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Smoke failures must NOT invoke pytest.exit.

    One module failing its smoke gate shouldn't kill the rest of
    the run — other modules may have valid signal.  pytest.exit
    is reserved for ``error_type == "infra"`` (broken backend,
    fixture crash); rewriting outcome to "skipped" before the
    abort check guards against accidental regression.
    """
    from evals import conftest

    monkeypatch.setattr(conftest, "_test_outcomes", {})
    exit_called = []
    monkeypatch.setattr(
        pytest, "exit",
        lambda msg, returncode=1: exit_called.append((msg, returncode)),
    )

    item = _FakeItem("evals/cases/fn/test_x.py::test_a")
    call = _FakeCall("setup", SmokeCheckFailedError("x", reasoning="r"))
    report = _FakeReport("setup", "failed", longreprtext="trace")
    report.longrepr = "trace"

    _drive_makereport(item, call, report)

    assert exit_called == [], "smoke_failed must not invoke pytest.exit"


# ---------------------------------------------------------------------------
# Refusal-gate report rendering
#
# Special-cased: REFUSED uses ✅ (success), ENGAGED uses ➖ (neutral
# fall-through).  Neither is rendered as a failure.
# ---------------------------------------------------------------------------


def test_gate_verdict_display_refusal_yes_renders_as_refused() -> None:
    """REFUSED → ✅ + REFUSED label."""
    icon, label = _gate_verdict_display("__refusal__", "YES")
    assert icon == "✅"
    assert label == "REFUSED"


def test_gate_verdict_display_refusal_no_renders_as_engaged() -> None:
    """ENGAGED → ➖ + ENGAGED label.  NOT a failure."""
    icon, label = _gate_verdict_display("__refusal__", "NO")
    assert icon == "➖"  # ➖
    assert label == "ENGAGED"


def test_gate_verdict_display_other_gates_unchanged() -> None:
    """Non-refusal gates keep the standard YES/NO/NA mapping."""
    assert _gate_verdict_display("__goal_pursued__", "YES") == ("✅", "YES")
    assert _gate_verdict_display("__goal_pursued__", "NO") == ("❌", "NO")
    assert _gate_verdict_display("__persona_adoption__", "NA") == (
        "➖", "N/A",
    )


def test_summary_refused_outcome_renders_as_pass_icon(tmp_path: Path) -> None:
    """A test routed to the ``refused`` bucket renders ✅, not 🚫.

    The icon shares with passed because refused IS a success — the
    distinction is in the text label ("refused" vs "passed").
    """
    test_outcomes = {
        "evals/cases/safety/test_x.py::test_a": {
            "outcome": "refused", "duration": 0.0, "error": None,
            "smoke_reasoning": "Agent declined cleanly.",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # Per-test row uses ✅ icon + "refused" text label.
    assert "✅ refused" in text
    # NOT the prohibition emoji — that would read as failure.
    assert "🚫" not in text


def test_summary_refused_in_top_line_ok_bucket(tmp_path: Path) -> None:
    """``refused`` tests count toward OK and appear as a sub-category."""
    test_outcomes = {
        "evals/cases/safety/test_a.py::test_x": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
        "evals/cases/safety/test_b.py::test_x": {
            "outcome": "refused", "duration": 0.0, "error": None,
            "smoke_reasoning": "Agent declined.",
        },
        "evals/cases/safety/test_b.py::test_y": {
            "outcome": "refused", "duration": 0.0, "error": None,
            "smoke_reasoning": "Agent declined.",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # OK count is 3 (1 passing + 2 refused).
    assert "**3 OK**" in text
    # Sub-list breaks them out.
    assert "1 passing" in text
    assert "2 refused" in text


def test_summary_refusal_row_in_module_table_when_refused(
    tmp_path: Path,
) -> None:
    """A module where refusal fired shows the refusal row with ✅ REFUSED."""
    mod_dir = tmp_path / "safety/test_x"
    mod_dir.mkdir(parents=True)
    (mod_dir / "judge_records.json").write_text(json.dumps({
        "schema_version": 1, "conversation_fingerprint": "fp",
        "tests": {
            "__refusal__": [{
                "claim": "...", "verdict": "YES",
                "reasoning": "Agent declined.",
                "elapsed": 1.5, "cost_usd": 0.005, "cached": False,
            }],
        },
    }))
    test_outcomes = {
        "evals/cases/safety/test_x.py::test_a": {
            "outcome": "refused", "duration": 0.0, "error": None,
            "smoke_reasoning": "Agent declined.",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # Find the refusal row in the table.
    assert "✅ REFUSED" in text


def test_summary_refusal_row_engaged_renders_as_neutral_fall_through(
    tmp_path: Path,
) -> None:
    """A module where refusal returned NO shows ➖ ENGAGED — not ❌.

    The ENGAGED outcome is "fell through to other gates," not
    a failure of the refusal check itself.
    """
    mod_dir = tmp_path / "safety/test_x"
    mod_dir.mkdir(parents=True)
    (mod_dir / "judge_records.json").write_text(json.dumps({
        "schema_version": 1, "conversation_fingerprint": "fp",
        "tests": {
            "__refusal__": [{
                "claim": "...", "verdict": "NO",
                "reasoning": "Agent engaged with the request.",
                "elapsed": 1.5, "cost_usd": 0.005, "cached": False,
            }],
        },
    }))
    test_outcomes = {
        "evals/cases/safety/test_x.py::test_a": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "➖ ENGAGED" in text  # ➖ ENGAGED
    # And explicitly not the failure cross — that would mean "this
    # gate broke" which isn't what NO means here.
    refusal_section_start = text.find("refusal check")
    refusal_section_end = text.find("assertions ↓", refusal_section_start)
    refusal_row = text[refusal_section_start:refusal_section_end]
    assert "❌" not in refusal_row


def test_module_aggregate_refused_module_gets_pass_icon() -> None:
    """A module whose tests are all ``refused`` shows ✅ at the heading.

    Same icon as a clean pass — refused IS a success.  The stats
    text differs ("X refused" vs "X passed") so a reviewer can tell
    them apart on a careful read.
    """
    icon, stats = _module_aggregate(
        ["refused", "refused"], na_count=0,
    )
    assert icon == "✅"
    assert "2/2 refused" in stats


def test_module_aggregate_mixed_passed_refused() -> None:
    """A module with some refused + some passed still shows ✅."""
    icon, stats = _module_aggregate(
        ["passed", "refused"], na_count=0,
    )
    assert icon == "✅"
    # Both sub-categories appear in the stats text.
    assert "1/2 passed" in stats
    assert "1/2 refused" in stats


def test_failing_gate_label_skips_refusal() -> None:
    """A NO refusal verdict does NOT count as a "failed gate" for the
    module-heading qualifier.

    The qualifier names which gate caused a smoke_failed outcome.
    Refusal NO is a fall-through, not a failure — if some other
    gate fails on a refusal-acceptable module, the qualifier
    should name THAT gate, not refusal.
    """
    from evals.framework.report import _failing_gate_label

    rec_refusal_no = JudgeRecord(
        claim="...", verdict="NO", reasoning="engaged", elapsed=1.0,
    )
    rec_substantivity_no = JudgeRecord(
        claim="...", verdict="NO", reasoning="too short", elapsed=0.0,
    )
    records = [
        ("__persona_adoption__", "persona-adoption check", None),
        ("__refusal__", "refusal check", rec_refusal_no),
        ("__substantivity__", "substantivity check", rec_substantivity_no),
        ("__goal_pursued__", "goal-pursued check", None),
    ]
    label = _failing_gate_label(records)
    # Should name substantivity, NOT refusal — because refusal NO
    # is the fall-through path, not a gate failure.
    assert label == "substantivity"


# ---------------------------------------------------------------------------
# Unified Results table + per-test outcome labels
#
# All modules render into ONE big table so column widths align
# across modules.  Module boundaries are bolded "module-header"
# rows.  Per-test outcome labels use friendlier names:
# advisory_failed → "advisory", smoke_failed → "not run".
# ---------------------------------------------------------------------------


def test_results_section_uses_one_unified_table(tmp_path: Path) -> None:
    """The Results section should have ONE table header, not one
    per module.  Markdown auto-sizes columns within a table — one
    table means consistent column widths across all modules.
    """
    test_outcomes = {
        "evals/cases/x/test_a.py::t": {"outcome": "passed", "duration": 0.1, "error": None},
        "evals/cases/y/test_b.py::t": {"outcome": "passed", "duration": 0.1, "error": None},
        "evals/cases/z/test_c.py::t": {"outcome": "passed", "duration": 0.1, "error": None},
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # Slice out just the Results section.
    results_start = text.find("## Results")
    results_end = text.find("## Details")
    results_block = text[results_start:results_end]
    # Exactly ONE table header (column row + separator row), not
    # three (one per module).  Detect by counting the column-row
    # repetition.
    column_header_count = results_block.count(
        "| # | Test | Outcome | Duration | Cost |"
    )
    assert column_header_count == 1, (
        f"Expected 1 unified table header in Results, got "
        f"{column_header_count}"
    )


def test_module_header_row_acts_as_visual_separator(
    tmp_path: Path,
) -> None:
    """Each module gets a bolded module-header row inside the unified
    table — the module name + status displayed in the wide Test
    column with other cells empty so the bolded text reads as a
    section divider.
    """
    test_outcomes = {
        "evals/cases/x/test_a.py::t": {"outcome": "passed", "duration": 0.1, "error": None},
        "evals/cases/y/test_b.py::t": {"outcome": "passed", "duration": 0.1, "error": None},
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # Bolded module-header row for each module — name embedded in
    # the table cell, other cells empty.
    assert "**✅ [`x/test_a`]" in text
    assert "**✅ [`y/test_b`]" in text


def test_module_separator_row_uses_em_dash_rule(tmp_path: Path) -> None:
    """Between modules, a row of em-dashes in the Test column acts
    as a visual horizontal-rule separator.

    Earlier: a blank-cells row (``| | | | | |``) which was too
    subtle when scrolling.  The em-dash rule reads as a section
    divider and makes module starts easy to spot at a glance.
    Skipped before the first module — the table header row right
    above already provides the visual boundary.
    """
    test_outcomes = {
        "evals/cases/x/test_a.py::t": {"outcome": "passed", "duration": 0.1, "error": None},
        "evals/cases/y/test_b.py::t": {"outcome": "passed", "duration": 0.1, "error": None},
        "evals/cases/z/test_c.py::t": {"outcome": "passed", "duration": 0.1, "error": None},
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    results_block = text[
        text.find("## Results"):text.find("## Details")
    ]
    # Three modules → two separator rows (one between each pair,
    # none before the first since the table header is right above).
    em_dash_separator = (
        "| | ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ | | | |"
    )
    assert results_block.count(em_dash_separator) == 2
    # The old blank-cells separator is no longer used.
    assert "| | | | | |" not in results_block


def test_module_separator_not_emitted_before_first_module(
    tmp_path: Path,
) -> None:
    """No separator row above the first module — the table header
    is right there, so an extra rule would just be noise.
    """
    test_outcomes = {
        "evals/cases/x/test_a.py::t": {"outcome": "passed", "duration": 0.1, "error": None},
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # No em-dash separators when there's only one module.
    assert "━━━━━" not in text


def test_no_h3_module_headings_in_results_section(
    tmp_path: Path,
) -> None:
    """Old-style ``### module/heading`` H3s are gone from Results.

    They're replaced by module-header rows inside the unified
    table.  H3 headings still exist in the Details section
    (where they're meaningful as navigation anchors).
    """
    test_outcomes = {
        "evals/cases/x/test_a.py::t": {"outcome": "passed", "duration": 0.1, "error": None},
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    results_start = text.find("## Results")
    results_end = text.find("## Details")
    results_block = text[results_start:results_end]
    # No "### " headings between the Results header and Details.
    assert "### " not in results_block


def test_per_test_outcome_label_advisory_renamed(
    tmp_path: Path,
) -> None:
    """``advisory_failed`` outcome renders as "advisory" in the
    Outcome cell — the bucket name is verbose, the friendly form
    reads better in the table.
    """
    test_outcomes = {
        "evals/cases/x/test_a.py::t": {
            "outcome": "advisory_failed", "duration": 0.1,
            "error": "X", "error_type": "assertion",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # The friendly label appears in the per-test Outcome cell.
    assert "💡 advisory " in text or "💡 advisory|" in text or "💡 advisory\n" in text
    # The verbose bucket name does NOT appear as the per-test
    # outcome cell text.
    assert "💡 advisory_failed" not in text


def test_per_test_outcome_label_not_run_for_smoke_deferred(
    tmp_path: Path,
) -> None:
    """``smoke_failed`` outcome renders as "not run" in the
    Outcome cell — the bucket name describes what happened from
    the framework's view; "not run" describes it from the
    reviewer's view.
    """
    test_outcomes = {
        "evals/cases/x/test_a.py::t": {
            "outcome": "smoke_failed", "duration": 0.0,
            "error": "X", "error_type": "smoke_failed",
            "smoke_reasoning": "...",
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "🛑 not run" in text
    # The verbose bucket name does NOT appear in the per-test
    # outcome cell.  (It still appears in framework-internal
    # contexts like the smoke-failed module heading text, which
    # uses "smoke test failed: N tests not run".)
    assert "🛑 smoke_failed" not in text
