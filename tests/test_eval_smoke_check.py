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
    _persona_adoption_claim_for,
    _smoke_claim_for,
)
from evals.framework.report import (
    _first_smoke_reasoning,
    _load_smoke_gate_records,
    _module_aggregate,
    _smoke_anchor,
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


# ---------------------------------------------------------------------------
# _persona_adoption_claim_for
# ---------------------------------------------------------------------------

def test_persona_claim_includes_persona_text() -> None:
    """The persona text is inlined so the claim is self-contained."""
    persona = "Marcus, 29, community organizer"
    claim = _persona_adoption_claim_for(persona, situation="")
    assert persona in claim
    # Names the central question — fidelity to persona, not goal.
    assert "persona" in claim.lower()
    assert "fidelity" in claim.lower()


def test_persona_claim_omits_situation_block_when_empty() -> None:
    """No situation → no empty situation header in the claim."""
    claim = _persona_adoption_claim_for("a persona", situation="   ")
    assert "Their situation" not in claim
    # Persona is still present.
    assert "a persona" in claim


def test_persona_claim_includes_situation_when_given() -> None:
    claim = _persona_adoption_claim_for(
        "a persona",
        situation="Recently separated, lives alone in a small Midwestern city.",
    )
    assert "Their situation" in claim
    assert "Midwestern" in claim


def test_persona_claim_is_stable() -> None:
    """Same inputs → identical claim, so the cache key is deterministic."""
    a = _persona_adoption_claim_for("Marcus", situation="organizing a march")
    b = _persona_adoption_claim_for("Marcus", situation="organizing a march")
    assert a == b


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
    """NA collapses to pass — same semantics as smoke_check."""
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
    # Reserved key — distinct from __smoke__ and from any user test.
    assert "__persona_adoption__" in data["tests"]
    assert "__smoke__" not in data["tests"]


def test_persona_check_does_not_invoke_recorder(tmp_path: Path) -> None:
    """Persona-adoption verdicts belong in framework machinery, not the
    per-test criterion list — same as smoke_check.
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
    # Generic banner appears once at module level — covers both the
    # turn-1 persona-adoption gate and the post-conversation smoke
    # gate, since both raise SmokeCheckFailedError.
    assert "Smoke gate failed" in text
    assert "module aborted" in text


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
        tests["__smoke__"] = [
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
    assert [name for name, _, _ in records] == [
        "__persona_adoption__", "__smoke__",
    ]
    assert records[0][2] is not None
    assert records[0][2].claim == "persona claim"
    assert records[1][2] is not None
    assert records[1][2].claim == "smoke claim"


def test_load_smoke_gate_records_handles_missing_persona(
    tmp_path: Path,
) -> None:
    """Resumed runs skip persona-adoption — loader returns None for it."""
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
    assert records[1][2] is not None  # smoke present


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
    a = _smoke_anchor("safety/test_x", "__smoke__")
    b = _smoke_anchor("safety/test_x", "__persona_adoption__")
    c = _smoke_anchor("safety/test_y", "__smoke__")
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
    assert "smoke check" in text
    # Separator row between smoke and assertions.
    assert "— assertions ↓ —" in text

    # Order: persona-adoption row appears BEFORE smoke row, both
    # appear BEFORE the user assertion row.
    persona_idx = text.find("persona-adoption check")
    smoke_idx = text.find("smoke check")
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
    assert "🔬 smoke check" in text
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
    # The smoke row's outcome cell pairs ❌ with NO.
    # Find the smoke row and check it has the failure marker.
    smoke_row_start = text.find("smoke check")
    smoke_row_end = text.find("\n", smoke_row_start)
    smoke_row = text[smoke_row_start:smoke_row_end]
    assert "❌" in smoke_row
    assert "NO" in smoke_row
