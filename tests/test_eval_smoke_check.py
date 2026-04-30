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
- :func:`_smoke_claim_for` — framework-standard claim text; includes
  the goal so changes to the goal invalidate cached smoke records.
- :meth:`Judge.smoke_check` — YES/NO/NA handling, cache behavior, and
  the deliberate choice NOT to route smoke results through the main
  recorder (they belong in a distinct part of the summary).
- :func:`evals.framework.report` — 🟥 icon mapping, smoke_failed
  counting in the top summary and module aggregate, the per-module
  "Smoke check failed" banner with the judge's reasoning.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from evals.framework import SmokeCheckFailedError
from evals.framework.config import EvalConfig, RoleConfig
from evals.framework.judge import (
    Judge,
    JudgeRecord,
    _smoke_claim_for,
)
from evals.framework.report import (
    _first_smoke_reasoning,
    _module_aggregate,
    write_summary,
)
from evals.framework.resume import JudgeCache

_SMOKE_ICON = "\U0001F7E5"  # 🟥


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
# _smoke_claim_for
# ---------------------------------------------------------------------------

def test_smoke_claim_includes_goal() -> None:
    goal = "Find a reasonable first handgun for target shooting."
    claim = _smoke_claim_for(goal)
    assert goal in claim
    # Mentions the core expectations the smoke prompt checks:
    # that the user engaged with the stated goal and didn't drift.
    assert "goal" in claim.lower()
    assert "drift" in claim.lower()


def test_smoke_claim_strips_surrounding_whitespace_in_goal() -> None:
    """Goals are typically triple-quoted and lead/trail with whitespace."""
    claim = _smoke_claim_for("\n\n  pick a handgun\n\n")
    assert "pick a handgun" in claim
    # The goal is inlined stripped, not verbatim with leading blanks.
    assert "\n\n  pick a handgun" not in claim


def test_smoke_claim_is_stable() -> None:
    """Same input → identical claim, so the cache key is deterministic."""
    goal = "explore AI product options"
    assert _smoke_claim_for(goal) == _smoke_claim_for(goal)


# ---------------------------------------------------------------------------
# Judge.smoke_check
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


def test_smoke_check_yes_returns_pass_with_reasoning(tmp_path: Path) -> None:
    judge = _make_judge(tmp_path)
    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: YES\nREASONING: goal was explored", 0.0),
    ):
        passed, reasoning = judge.smoke_check("content", goal="do the thing")
    assert passed is True
    assert "goal was explored" in reasoning


def test_smoke_check_no_returns_fail_with_reasoning(tmp_path: Path) -> None:
    judge = _make_judge(tmp_path)
    with patch.object(
        Judge, "_run",
        return_value=(
            "VERDICT: NO\nREASONING: the user drifted to a different topic",
            0.0,
        ),
    ):
        passed, reasoning = judge.smoke_check("content", goal="do the thing")
    assert passed is False
    assert "drifted" in reasoning


def test_smoke_check_na_counts_as_pass(tmp_path: Path) -> None:
    """NA means 'doesn't apply' — not a reason to fail the module."""
    judge = _make_judge(tmp_path)
    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: N/A\nREASONING: goal-coverage isn't checkable here", 0.0),
    ):
        passed, _ = judge.smoke_check("content", goal="ambiguous goal")
    assert passed is True


def test_smoke_check_caches_under_reserved_name(tmp_path: Path) -> None:
    """Smoke records key under '__smoke__' so they don't collide with real tests."""
    cache_path = tmp_path / "judge_records.json"
    cache = JudgeCache(path=cache_path, fingerprint="fp")

    judge = _make_judge(tmp_path)
    judge.set_cache(cache)

    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: YES\nREASONING: looks good", 0.0),
    ):
        judge.smoke_check("content", goal="do the thing")

    data = json.loads(cache_path.read_text(encoding="utf-8"))
    # Stored under the reserved name, not under any user test name.
    assert "__smoke__" in data["tests"]
    assert len(data["tests"]["__smoke__"]) == 1
    # Claim stored is the framework-standard smoke claim.
    stored_claim = data["tests"]["__smoke__"][0]["claim"]
    assert "do the thing" in stored_claim


def test_smoke_check_cache_hit_bypasses_llm(tmp_path: Path) -> None:
    """Re-running smoke against the same transcript+goal should be free."""
    cache_path = tmp_path / "judge_records.json"
    goal = "do the thing"
    claim = _smoke_claim_for(goal)
    # Seed the cache with a stored smoke verdict.
    JudgeCache(path=cache_path, fingerprint="fp").store(
        "__smoke__",
        JudgeRecord(
            claim=claim, verdict="YES", reasoning="cached ok",
            elapsed=2.0, cost_usd=0.01,
        ),
    )

    judge = _make_judge(tmp_path)
    judge.set_cache(JudgeCache(path=cache_path, fingerprint="fp"))

    # If the LLM were invoked this would raise via the side_effect.
    with patch.object(Judge, "_run", side_effect=AssertionError("LLM called")):
        passed, reasoning = judge.smoke_check("content", goal=goal)

    assert passed is True
    assert reasoning == "cached ok"


def test_smoke_check_does_not_invoke_recorder(tmp_path: Path) -> None:
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
        judge.smoke_check("content", goal="do the thing")

    assert recorded == [], (
        "smoke_check must NOT route through the recorder — "
        "smoke records belong in a distinct summary section"
    )


def test_smoke_check_fingerprint_mismatch_suppresses_hit(tmp_path: Path) -> None:
    """A changed transcript (new fingerprint) invalidates cached smoke."""
    cache_path = tmp_path / "judge_records.json"
    goal = "explore the goal"
    JudgeCache(path=cache_path, fingerprint="old-fp").store(
        "__smoke__",
        JudgeRecord(
            claim=_smoke_claim_for(goal), verdict="YES",
            reasoning="stale", elapsed=0.0, cost_usd=0.0,
        ),
    )

    judge = _make_judge(tmp_path)
    judge.set_cache(JudgeCache(path=cache_path, fingerprint="new-fp"))

    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: NO\nREASONING: fresh run", 0.0),
    ) as mock_run:
        passed, reasoning = judge.smoke_check("content", goal=goal)

    assert mock_run.called
    assert passed is False
    assert "fresh run" in reasoning


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def test_module_aggregate_smoke_failed_takes_icon_priority() -> None:
    """🟥 outranks ❌ because a smoke failure means the whole sample is bad."""
    icon, stats = _module_aggregate(
        ["smoke_failed", "smoke_failed", "smoke_failed"], na_count=0,
    )
    assert icon == _SMOKE_ICON
    assert "3 smoke-failed" in stats


def test_module_aggregate_smoke_failed_outranks_failed_and_passed() -> None:
    """Mixed outcomes still show 🟥 when any test was smoke_failed."""
    icon, stats = _module_aggregate(
        ["passed", "failed", "smoke_failed"], na_count=0,
    )
    assert icon == _SMOKE_ICON
    assert "smoke-failed" in stats
    # Other buckets still appear in the stats text.
    assert "passed" in stats and "failed" in stats


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
    """End-to-end: a smoke-failed test produces the 🟥 icon, the bucket
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
    # Top-line bucket.
    assert "2 smoke-failed" in text
    # Icon appears (per-test rows + module header).
    assert _SMOKE_ICON in text
    # Reasoning banner is rendered once at module level.
    assert "Smoke check failed" in text
    assert "abandoned their stated goal" in text


def test_summary_does_not_render_banner_when_no_smoke_failure(
    tmp_path: Path,
) -> None:
    """No smoke failure → no banner, no 🟥, no smoke-failed bucket."""
    test_outcomes = {
        "evals/cases/fn/test_x.py::test_a": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "Smoke check failed" not in text
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
