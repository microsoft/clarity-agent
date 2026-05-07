"""Tests for the ``NA`` ("doesn't apply") judge verdict.

NA exists for *conditional* criteria — claims of the form "if the
user did X, the assistant should have done Y."  When the precondition
(X) doesn't happen in the conversation, the criterion can't be
evaluated, so the judge returns NA.  The framework treats NA as a
pass (so ``assert judge.check(...)`` succeeds) but counts and renders
it distinctly in the run summary so reviewers can see at a glance
which verdicts were "doesn't apply" rather than "satisfied."

Surfaces under test:

- :func:`Judge.check` parsing — accepts both ``NA`` and ``N/A`` from
  the judge LLM and canonicalizes to the stored form ``NA``.  NA
  returns True from ``check()`` (pass semantics).
- :class:`JudgeCache` roundtrip — NA verdicts persist and replay as
  cached records, with the same pass-as-True behavior.
- :func:`evals.framework.report` rendering — NA gets the heavy-minus
  icon, counts in the aggregate buckets at every level (top summary,
  per-module aggregate text).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from evals.framework.config import EvalConfig, RoleConfig
from evals.framework.judge import Judge, JudgeRecord
from evals.framework.report import (
    _count_na_records,
    _module_aggregate,
    _verdict_icon,
    write_summary,
)
from evals.framework.resume import JudgeCache

_NA_ICON = "\u2796"


# ---------------------------------------------------------------------------
# Judge: parsing + check semantics
# ---------------------------------------------------------------------------

def _make_judge(
    tmp_path: Path, *, current_test_id: str = "tests/x.py::test_x",
) -> Judge:
    eval_config = EvalConfig(
        roles={"_judge": RoleConfig(
            provider="openai", model="m", auth_mode="api_key",
        )},
    )
    return Judge(
        eval_config,
        project_dir=tmp_path,
        clarity_agent_dir=tmp_path,
        current_test_getter=lambda: current_test_id,
    )


def test_judge_parses_na_verdict_canonical(tmp_path: Path) -> None:
    """Judge LLM saying ``VERDICT: NA`` → stored as ``NA``, check() True."""
    judge = _make_judge(tmp_path)
    recorded: list[JudgeRecord] = []
    judge._recorder = recorded.append

    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: NA\nREASONING: precondition X never happened", 0.0),
    ):
        result = judge.check("content", "if X then Y")

    assert result is True  # NA → pass
    assert len(recorded) == 1
    assert recorded[0].verdict == "NA"


def test_judge_parses_n_slash_a_verdict_to_canonical(tmp_path: Path) -> None:
    """``N/A`` (with slash) is also accepted and stored as ``NA``."""
    judge = _make_judge(tmp_path)
    recorded: list[JudgeRecord] = []
    judge._recorder = recorded.append

    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: N/A\nREASONING: doesn't apply", 0.0),
    ):
        result = judge.check("content", "if X then Y")

    assert result is True
    assert recorded[0].verdict == "NA"


def test_judge_unknown_verdict_defaults_to_no(tmp_path: Path) -> None:
    """Unparseable judge output stays NO (a missing verdict isn't NA)."""
    judge = _make_judge(tmp_path)
    recorded: list[JudgeRecord] = []
    judge._recorder = recorded.append

    with patch.object(
        Judge, "_run",
        return_value=("the judge returned garbage", 0.0),
    ):
        result = judge.check("content", "claim")

    assert result is False
    assert recorded[0].verdict == "NO"


def test_judge_yes_and_no_unaffected(tmp_path: Path) -> None:
    """Existing YES/NO behavior unchanged."""
    judge = _make_judge(tmp_path)
    recorded: list[JudgeRecord] = []
    judge._recorder = recorded.append

    with patch.object(
        Judge, "_run", return_value=("VERDICT: YES\nREASONING: ok", 0.0),
    ):
        assert judge.check("c", "claim") is True
    assert recorded[-1].verdict == "YES"

    with patch.object(
        Judge, "_run", return_value=("VERDICT: NO\nREASONING: bad", 0.0),
    ):
        assert judge.check("c", "claim2") is False
    assert recorded[-1].verdict == "NO"


# ---------------------------------------------------------------------------
# JudgeCache: NA roundtrips
# ---------------------------------------------------------------------------

def test_cache_stores_and_replays_na_verdict(tmp_path: Path) -> None:
    """NA verdicts cache like any other verdict; reload sees them."""
    cache_path = tmp_path / "judge_records.json"
    cache = JudgeCache(path=cache_path, fingerprint="fp")
    cache.store(
        "test_x",
        JudgeRecord(
            claim="if X then Y", verdict="NA",
            reasoning="X never happened", elapsed=1.0, cost_usd=0.0,
        ),
    )

    # Stored on disk with the NA verdict intact.
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    assert data["tests"]["test_x"][0]["verdict"] == "NA"

    # New cache instance serves the same record as a hit.
    reloaded = JudgeCache(path=cache_path, fingerprint="fp")
    hit = reloaded.lookup("test_x", "if X then Y")
    assert hit is not None
    assert hit.verdict == "NA"
    assert hit.cached is True


def test_judge_cache_hit_with_na_returns_true(tmp_path: Path) -> None:
    """Cache-served NA verdict still passes the assertion."""
    cache_path = tmp_path / "judge_records.json"
    JudgeCache(path=cache_path, fingerprint="fp").store(
        "test_x",
        JudgeRecord(
            claim="claim", verdict="NA", reasoning="r",
            elapsed=0.0, cost_usd=0.0,
        ),
    )
    judge = _make_judge(tmp_path, current_test_id="t::test_x")
    judge.set_cache(JudgeCache(path=cache_path, fingerprint="fp"))

    # If the LLM is invoked, the assert below will fire.
    with patch.object(Judge, "_run", side_effect=AssertionError("LLM called")):
        assert judge.check("content", "claim") is True


# ---------------------------------------------------------------------------
# Report: icon mapping + counts
# ---------------------------------------------------------------------------

def test_verdict_icon_mapping() -> None:
    assert _verdict_icon("YES") == "\u2705"  # ✅
    assert _verdict_icon("NO") == "\u274C"   # ❌
    assert _verdict_icon("NA") == _NA_ICON   # ➖


def test_verdict_icon_unknown_falls_back_to_no() -> None:
    """Unknown verdicts render as NO — closer to a fail than a pass."""
    assert _verdict_icon("???") == "\u274C"


def test_count_na_records_aggregates_across_tests() -> None:
    """Counts NA verdicts across the given nodeids' records."""
    records = {
        "mod::test_a": [
            JudgeRecord("c1", "YES", "", 0.0),
            JudgeRecord("c2", "NA", "", 0.0),
        ],
        "mod::test_b": [
            JudgeRecord("c3", "NA", "", 0.0),
            JudgeRecord("c4", "NA", "", 0.0),
        ],
        "other::test_c": [
            JudgeRecord("c5", "NA", "", 0.0),  # not in nodeids — excluded
        ],
    }
    assert _count_na_records(["mod::test_a", "mod::test_b"], records) == 3
    assert _count_na_records([], records) == 0
    assert _count_na_records(["mod::test_a"], records) == 1


def test_module_aggregate_appends_na_bucket() -> None:
    """``N N/A criteria`` joins the parts list when na_count > 0."""
    icon, stats = _module_aggregate(
        ["passed", "passed", "passed"], na_count=2,
    )
    assert "passed" in stats
    assert "2 N/A criteria" in stats
    # NA never overrides the icon — these are all passes.
    assert icon == "\u2705"


def test_module_aggregate_omits_na_bucket_when_zero() -> None:
    icon, stats = _module_aggregate(["passed", "passed"], na_count=0)
    assert "N/A" not in stats
    assert icon == "\u2705"


def test_module_aggregate_na_does_not_promote_failed_icon() -> None:
    """A failing test stays the worst — NA criteria don't outrank fail."""
    icon, _ = _module_aggregate(["passed", "failed"], na_count=5)
    assert icon == "\u274C"


def test_summary_header_includes_na_count(tmp_path: Path) -> None:
    """OK bullet's sub-list breaks out tests with N/A criteria.

    A test that passed but had at least one N/A judge verdict is
    counted as a sub-category of "passing" — it passed (N/A doesn't
    fail) but the breakdown surfaces "criterion didn't apply" as a
    separately-meaningful signal.  The count is at the TEST level,
    not the criterion level: a test with 5 N/A criteria contributes
    1 to the "N N/A" sub-count, not 5.
    """
    test_outcomes: dict = {
        "evals/cases/x/test_a.py::t1": {
            "outcome": "passed", "duration": 1.0, "error": None,
        },
        "evals/cases/x/test_a.py::t2": {
            "outcome": "passed", "duration": 1.0, "error": None,
        },
    }
    judge_records: dict = {
        "evals/cases/x/test_a.py::t1": [
            JudgeRecord("claim1", "YES", "", 0.0),
            JudgeRecord("claim2", "NA", "", 0.0),
        ],
        "evals/cases/x/test_a.py::t2": [
            JudgeRecord("claim3", "NA", "", 0.0),
        ],
    }
    write_summary(tmp_path, test_outcomes, judge_records)

    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # OK bullet count is the test count (2 passed → 2 OK).  Both
    # tests had at least one N/A verdict, so "2 N/A" appears in the
    # sub-list.
    assert "**2 OK**" in text
    assert "2 N/A" in text
    # Per-criterion icon for the NA verdicts is the heavy minus.
    assert _NA_ICON in text
    # Per-criterion label uses the slash form for readability.
    assert "**N/A**" in text


def test_per_test_row_annotates_na_count(tmp_path: Path) -> None:
    """When a test passes with some NA criteria, the Results row shows it.

    ``✅ passed`` becomes ``✅ passed (N/A)`` so reviewers scanning
    the top-level table can see conditional-skip outcomes without
    opening the Details section.
    """
    test_outcomes: dict = {
        "evals/cases/x/test_a.py::t1": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
    }
    judge_records: dict = {
        "evals/cases/x/test_a.py::t1": [
            JudgeRecord("c1", "YES", "", 0.0),
            JudgeRecord("c2", "NA", "", 0.0),
            JudgeRecord("c3", "NA", "", 0.0),
        ],
    }
    write_summary(tmp_path, test_outcomes, judge_records)

    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # The annotated cell appears in the Results table row.
    assert "passed (N/A)" in text


def test_per_test_row_no_annotation_when_no_na(tmp_path: Path) -> None:
    """No NA criteria → clean ``✅ passed`` in the Results row."""
    test_outcomes: dict = {
        "evals/cases/x/test_a.py::t1": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
    }
    judge_records: dict = {
        "evals/cases/x/test_a.py::t1": [
            JudgeRecord("c1", "YES", "", 0.0),
            JudgeRecord("c2", "YES", "", 0.0),
        ],
    }
    write_summary(tmp_path, test_outcomes, judge_records)

    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # "passed" still present; NA-annotation parens are NOT.
    assert "passed" in text
    assert f"({_NA_ICON}" not in text


def test_per_test_row_does_not_annotate_failed_test(tmp_path: Path) -> None:
    """A failed test with NA criteria shouldn't get the annotation —
    annotation is only for *passed with NA*, to distinguish it from
    *pure passed*.  Failed tests have their own outcome cell."""
    test_outcomes: dict = {
        "evals/cases/x/test_a.py::t1": {
            "outcome": "failed", "duration": 0.1, "error": "assertion",
        },
    }
    judge_records: dict = {
        "evals/cases/x/test_a.py::t1": [
            JudgeRecord("c1", "NO", "", 0.0),
            JudgeRecord("c2", "NA", "", 0.0),
        ],
    }
    write_summary(tmp_path, test_outcomes, judge_records)

    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # Failed cell does NOT carry the NA annotation.
    assert f"failed ({_NA_ICON}" not in text


def test_summary_header_omits_na_when_zero(tmp_path: Path) -> None:
    """No NA verdicts → no NA bucket in the summary line."""
    test_outcomes: dict = {
        "evals/cases/x/test_a.py::t1": {
            "outcome": "passed", "duration": 1.0, "error": None,
        },
    }
    judge_records: dict = {
        "evals/cases/x/test_a.py::t1": [
            JudgeRecord("claim", "YES", "", 0.0),
        ],
    }
    write_summary(tmp_path, test_outcomes, judge_records)

    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "N/A" not in text  # neither in summary line nor per-criterion
    assert _NA_ICON not in text
