"""Tests for the eval framework's resume / checkpoint support.

Covers:

- :func:`compute_fingerprint`: stable across identical content, different
  across any modification.
- :class:`JudgeCache`: lookup/store semantics, fingerprint-gated staleness,
  atomic write, roundtrip through the on-disk JSON format.
- :class:`Judge`: cache hits bypass the LLM call, cache misses store
  fresh records, per-test scoping works under the ``current_test_getter``
  indirection that the real conftest uses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from evals.framework.config import EvalConfig, RoleConfig
from evals.framework.judge import Judge, JudgeRecord
from evals.framework.resume import JudgeCache, compute_fingerprint

# ---------------------------------------------------------------------------
# compute_fingerprint
# ---------------------------------------------------------------------------

def test_fingerprint_is_deterministic() -> None:
    assert compute_fingerprint("hello") == compute_fingerprint("hello")


def test_fingerprint_differs_on_any_change() -> None:
    base = "the transcript"
    assert compute_fingerprint(base) != compute_fingerprint(base + " ")
    assert compute_fingerprint(base) != compute_fingerprint(base.upper())


def test_fingerprint_is_hex_sha256_shape() -> None:
    fp = compute_fingerprint("x")
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


# ---------------------------------------------------------------------------
# JudgeCache
# ---------------------------------------------------------------------------

def _make_record(claim: str = "c", verdict: str = "YES") -> JudgeRecord:
    return JudgeRecord(
        claim=claim, verdict=verdict, reasoning="r",
        elapsed=1.0, cost_usd=0.001,
    )


def test_cache_empty_when_file_missing(tmp_path: Path) -> None:
    cache = JudgeCache(path=tmp_path / "judge_records.json", fingerprint="fp")
    assert cache.lookup("test_x", "any claim") is None


def test_cache_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "judge_records.json"
    cache = JudgeCache(path=path, fingerprint="fp-a")
    cache.store("test_one", _make_record(claim="criterion one"))
    cache.store("test_one", _make_record(claim="criterion two", verdict="NO"))
    cache.store("test_two", _make_record(claim="other"))

    # File exists and is well-formed JSON.
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["conversation_fingerprint"] == "fp-a"
    assert set(data["tests"].keys()) == {"test_one", "test_two"}

    # A fresh cache instance sees the stored records as cache hits.
    reloaded = JudgeCache(path=path, fingerprint="fp-a")
    hit = reloaded.lookup("test_one", "criterion one")
    assert hit is not None
    assert hit.verdict == "YES"
    assert hit.cached is True  # loaded records are flagged as cached


def test_cache_ignores_entries_when_fingerprint_mismatches(tmp_path: Path) -> None:
    path = tmp_path / "judge_records.json"
    original = JudgeCache(path=path, fingerprint="fp-original")
    original.store("test_x", _make_record(claim="c"))

    # Simulate the transcript having changed since — fingerprint differs.
    stale = JudgeCache(path=path, fingerprint="fp-different")
    assert stale.lookup("test_x", "c") is None


def test_cache_store_advances_fingerprint_on_stale_file(tmp_path: Path) -> None:
    """After storing under a new fingerprint, the file reflects it.

    Otherwise a rejudgment against a new transcript would leave stale
    fingerprint metadata and future lookups would keep missing.
    """
    path = tmp_path / "judge_records.json"
    JudgeCache(path=path, fingerprint="fp-old").store(
        "test_x", _make_record(claim="c"),
    )
    # Rejudge against a new transcript.
    new_cache = JudgeCache(path=path, fingerprint="fp-new")
    assert new_cache.lookup("test_x", "c") is None  # stale from old fp
    new_cache.store("test_x", _make_record(claim="c", verdict="NO"))
    # Reload: now-fresh record is visible.
    reloaded = JudgeCache(path=path, fingerprint="fp-new")
    hit = reloaded.lookup("test_x", "c")
    assert hit is not None
    assert hit.verdict == "NO"


def test_cache_tolerates_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "judge_records.json"
    path.write_text("{not valid json", encoding="utf-8")
    # Should not raise — treat corrupt file as empty.
    cache = JudgeCache(path=path, fingerprint="fp")
    assert cache.lookup("test_x", "c") is None
    # Writing still works.
    cache.store("test_x", _make_record(claim="c"))
    assert json.loads(path.read_text(encoding="utf-8"))["tests"]["test_x"]


def test_cache_writes_are_atomic(tmp_path: Path) -> None:
    """No .tmp files left behind after a successful write."""
    path = tmp_path / "judge_records.json"
    cache = JudgeCache(path=path, fingerprint="fp")
    cache.store("test_x", _make_record(claim="c"))
    tmps = list(tmp_path.glob("*.tmp"))
    assert tmps == [], f"stray tmp files: {tmps}"


# ---------------------------------------------------------------------------
# JudgeCache.prune_unseen — stale-entry cleanup
#
# When a smoke-gate or judge claim is rewritten between runs, the new
# claim's record gets stored alongside the old one (JudgeCache keys
# by (test_name, claim)).  prune_unseen removes the on-disk records
# left behind, but only for test_names that saw at least one lookup
# this session — test_names with zero activity are left untouched
# because there's no evidence their records are stale.
# ---------------------------------------------------------------------------

def test_prune_unseen_drops_records_with_unseen_claims(
    tmp_path: Path,
) -> None:
    """A test_name that was looked up under one claim drops other claims
    under the same test_name.  Models the claim-rewrite scenario:
    old claim's record sits on disk, new claim's record is stored
    fresh — prune drops the old."""
    path = tmp_path / "judge_records.json"
    seed = JudgeCache(path=path, fingerprint="fp")
    seed.store("__user_pursued__", _make_record(claim="OLD claim text"))
    seed.store("__user_pursued__", _make_record(claim="NEW claim text"))

    # Fresh cache, simulating a new session: only the NEW claim is
    # looked up.
    cache = JudgeCache(path=path, fingerprint="fp")
    cache.lookup("__user_pursued__", "NEW claim text")
    cache.prune_unseen()

    data = json.loads(path.read_text(encoding="utf-8"))
    claims_on_disk = [
        e["claim"] for e in data["tests"]["__user_pursued__"]
    ]
    assert claims_on_disk == ["NEW claim text"], (
        f"expected only NEW claim retained, got {claims_on_disk}"
    )


def test_prune_unseen_leaves_untouched_test_names_alone(
    tmp_path: Path,
) -> None:
    """A test_name with zero lookups in this session keeps all its
    records.  Models a smoke-gate that doesn't fire on this run
    (e.g., __refusal__ for non-refusal-acceptable modules) — we
    don't have evidence those records are stale, just unused."""
    path = tmp_path / "judge_records.json"
    seed = JudgeCache(path=path, fingerprint="fp")
    seed.store("__refusal__", _make_record(claim="some refusal claim"))
    seed.store("__user_pursued__", _make_record(claim="user claim"))

    cache = JudgeCache(path=path, fingerprint="fp")
    # Only __user_pursued__ is touched this session.
    cache.lookup("__user_pursued__", "user claim")
    cache.prune_unseen()

    data = json.loads(path.read_text(encoding="utf-8"))
    # __refusal__ records remain untouched.
    assert "__refusal__" in data["tests"]
    refusal_claims = [e["claim"] for e in data["tests"]["__refusal__"]]
    assert refusal_claims == ["some refusal claim"]


def test_prune_unseen_no_writes_when_nothing_to_drop(
    tmp_path: Path,
) -> None:
    """Idempotent: if no stale entries, prune doesn't rewrite the file.

    Defensive against churning the file's mtime or wear on the disk
    when there's no actual cleanup to do.
    """
    path = tmp_path / "judge_records.json"
    cache = JudgeCache(path=path, fingerprint="fp")
    cache.store("__user_pursued__", _make_record(claim="C"))
    cache.lookup("__user_pursued__", "C")  # mark as seen
    mtime_before = path.stat().st_mtime_ns
    cache.prune_unseen()
    mtime_after = path.stat().st_mtime_ns
    assert mtime_before == mtime_after, (
        "prune_unseen rewrote the file when there was nothing to drop"
    )


def test_prune_unseen_records_lookup_misses_too(
    tmp_path: Path,
) -> None:
    """A lookup that misses still counts as 'seen' — important so
    that after a fresh judge call follows the miss, the new claim's
    record is retained on a subsequent prune."""
    path = tmp_path / "judge_records.json"
    seed = JudgeCache(path=path, fingerprint="fp")
    seed.store("__user_pursued__", _make_record(claim="OLD"))

    cache = JudgeCache(path=path, fingerprint="fp")
    # Lookup for the NEW claim text — this is a miss against the
    # seed (which has only OLD), but the lookup should still mark
    # NEW as seen.
    assert cache.lookup("__user_pursued__", "NEW") is None
    # Now the judge would normally store a fresh record for NEW.
    cache.store("__user_pursued__", _make_record(claim="NEW"))
    cache.prune_unseen()

    data = json.loads(path.read_text(encoding="utf-8"))
    claims_on_disk = sorted(
        e["claim"] for e in data["tests"]["__user_pursued__"]
    )
    assert claims_on_disk == ["NEW"], (
        f"expected OLD pruned and NEW retained, got {claims_on_disk}"
    )


# ---------------------------------------------------------------------------
# Judge integration
# ---------------------------------------------------------------------------

def _make_judge(
    tmp_path: Path,
    *,
    recorded: list[JudgeRecord] | None = None,
    current_test_id: str | None = None,
) -> Judge:
    """Build a Judge with minimal scaffolding and a no-op recorder list."""
    eval_config = EvalConfig(
        roles={"_judge": RoleConfig(provider="openai", model="judge-model",
                                     auth_mode="api_key")},
    )
    recorder: Any = None
    if recorded is not None:
        def _record(rec: JudgeRecord) -> None:
            recorded.append(rec)
        recorder = _record
    return Judge(
        eval_config,
        project_dir=tmp_path,
        clarity_agent_dir=tmp_path,
        recorder=recorder,
        current_test_getter=lambda: current_test_id,
    )


def test_judge_cache_hit_bypasses_llm(tmp_path: Path) -> None:
    # Seed the cache with a pre-existing record.
    cache_path = tmp_path / "judge_records.json"
    JudgeCache(path=cache_path, fingerprint="fp").store(
        "test_criterion",
        JudgeRecord(
            claim="the claim", verdict="YES", reasoning="seeded",
            elapsed=2.0, cost_usd=0.01,
        ),
    )

    recorded: list[JudgeRecord] = []
    judge = _make_judge(
        tmp_path, recorded=recorded,
        current_test_id="tests/test_x.py::test_criterion",
    )
    judge.set_cache(JudgeCache(path=cache_path, fingerprint="fp"))

    # If the LLM backend were invoked, this patch would raise.
    with patch.object(Judge, "_run", side_effect=AssertionError("LLM called")):
        assert judge.check("content ignored", "the claim") is True

    # Recorder saw the cached record (so summary.md is populated).
    assert len(recorded) == 1
    assert recorded[0].cached is True
    assert recorded[0].verdict == "YES"


def test_judge_cache_miss_stores_fresh_record(tmp_path: Path) -> None:
    cache_path = tmp_path / "judge_records.json"
    cache = JudgeCache(path=cache_path, fingerprint="fp")
    judge = _make_judge(
        tmp_path, current_test_id="tests/test_x.py::test_new_criterion",
    )
    judge.set_cache(cache)

    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: YES\nREASONING: because", 0.0),
    ):
        assert judge.check("content", "fresh claim") is True

    # The cache now has the record on disk, keyed by the test function.
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    assert data["tests"]["test_new_criterion"][0]["claim"] == "fresh claim"
    assert data["tests"]["test_new_criterion"][0]["verdict"] == "YES"
    # Stored as non-cached since this call produced it.
    assert data["tests"]["test_new_criterion"][0]["cached"] is False
    assert data["conversation_fingerprint"] == "fp"


def test_judge_cache_miss_on_stale_fingerprint_reinvokes(tmp_path: Path) -> None:
    """A cache entry under a different fingerprint must not be served.

    Otherwise a run after editing the transcript would silently reuse
    verdicts that judged something else.
    """
    cache_path = tmp_path / "judge_records.json"
    # Seed under old fingerprint.
    JudgeCache(path=cache_path, fingerprint="fp-old").store(
        "test_x",
        JudgeRecord(claim="c", verdict="YES", reasoning="", elapsed=0, cost_usd=0),
    )

    judge = _make_judge(tmp_path, current_test_id="t::test_x")
    # New cache pointed at the same file but a *different* fingerprint.
    judge.set_cache(JudgeCache(path=cache_path, fingerprint="fp-new"))

    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: NO\nREASONING: different transcript", 0.0),
    ) as mock_run:
        result = judge.check("new content", "c")

    # LLM WAS called (no stale hit) and the NO verdict won.
    assert mock_run.called
    assert result is False


def test_judge_without_cache_always_runs_llm(tmp_path: Path) -> None:
    """Backward-compat: a Judge with no cache installed works as before."""
    judge = _make_judge(tmp_path, current_test_id="t::test_x")
    # set_cache not called → self._cache stays None.
    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: YES\nREASONING: ok", 0.0),
    ) as mock_run:
        judge.check("content", "claim")
    assert mock_run.called


def test_judge_with_no_current_test_skips_cache(tmp_path: Path) -> None:
    """Defensive: if the test tracker can't resolve a name, don't cache.

    We can't key a cache entry without a test name, so the safe move is
    to always invoke the LLM — never silently mis-attribute.
    """
    cache_path = tmp_path / "judge_records.json"
    JudgeCache(path=cache_path, fingerprint="fp").store(
        "test_x",
        JudgeRecord(claim="c", verdict="YES", reasoning="", elapsed=0, cost_usd=0),
    )
    judge = _make_judge(tmp_path, current_test_id=None)
    judge.set_cache(JudgeCache(path=cache_path, fingerprint="fp"))

    with patch.object(
        Judge, "_run",
        return_value=("VERDICT: NO\nREASONING: ok", 0.0),
    ) as mock_run:
        judge.check("content", "c")
    assert mock_run.called


# ---------------------------------------------------------------------------
# Runner helpers exercised outside of pytest
# ---------------------------------------------------------------------------

def test_wipe_conversation_artifacts_clears_expected(tmp_path: Path) -> None:
    """Keeps .git marker and unrelated files; drops cached conversation."""
    from evals.framework.runner import _wipe_conversation_artifacts

    (tmp_path / ".git").mkdir()
    (tmp_path / ".clarity-protocol").mkdir()
    (tmp_path / ".clarity-protocol" / "x.md").write_text("x")
    (tmp_path / "transcript.md").write_text("t")
    (tmp_path / "metadata.json").write_text("{}")
    (tmp_path / "judge_records.json").write_text("{}")
    (tmp_path / "unrelated.txt").write_text("keep me")

    _wipe_conversation_artifacts(tmp_path)

    assert (tmp_path / ".git").is_dir()
    assert (tmp_path / "unrelated.txt").exists()
    assert not (tmp_path / ".clarity-protocol").exists()
    assert not (tmp_path / "transcript.md").exists()
    assert not (tmp_path / "metadata.json").exists()
    assert not (tmp_path / "judge_records.json").exists()


def test_wipe_conversation_artifacts_idempotent(tmp_path: Path) -> None:
    """Safe to call on a dir that's already clean."""
    from evals.framework.runner import _wipe_conversation_artifacts

    _wipe_conversation_artifacts(tmp_path)  # no-op
    # Second call also fine.
    _wipe_conversation_artifacts(tmp_path)
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# User-LLM dialogue spool: tmp-first, move into project_dir at end
#
# The streaming dialogue log MUST be written outside project_dir while
# the conversation is in flight — the Clarity target reads files in
# its working directory and would learn the persona, the goal, and
# "this is a test" framing if the spool lived there mid-conversation.
# These guards catch any regression that would put the file back in
# project_dir during the run.
# ---------------------------------------------------------------------------

def test_spool_path_lives_outside_project_dir(tmp_path: Path) -> None:
    """The spool MUST NOT be under project_dir during the run."""
    import tempfile

    from evals.framework.runner import _make_spool_path

    project_dir = tmp_path / "module"
    project_dir.mkdir()
    spool = _make_spool_path(project_dir)
    try:
        assert spool.exists()  # mkstemp creates the file
        # CRITICAL: spool is in the system tmp dir, not under project_dir.
        # If this assertion ever fires, the Clarity target will see
        # the user's persona mid-conversation — corrupting evals.
        assert not str(spool).startswith(str(project_dir))
        assert str(spool).startswith(tempfile.gettempdir())
    finally:
        spool.unlink(missing_ok=True)


def test_spool_path_includes_module_slug_for_identifiability(
    tmp_path: Path,
) -> None:
    """Operator should be able to tell which test a spool belongs to."""
    from evals.framework.runner import _make_spool_path

    project_dir = tmp_path / "test_some_unique_module"
    project_dir.mkdir()
    spool = _make_spool_path(project_dir)
    try:
        assert "test_some_unique_module" in spool.name
        assert spool.name.startswith("clarity-eval-user-dialogue-")
        assert spool.suffix == ".md"
    finally:
        spool.unlink(missing_ok=True)


def test_spool_path_uses_eval_runs_relative_slug_when_present(
    tmp_path: Path,
) -> None:
    """When project_dir is under an eval-runs/ root, slug from that
    point on; gives the operator a more informative filename when the
    same test runs in two different output dirs."""
    from evals.framework.runner import _make_spool_path

    project_dir = tmp_path / "eval-runs" / "20260424-120300" / "safety" / "test_x"
    project_dir.mkdir(parents=True)
    spool = _make_spool_path(project_dir)
    try:
        # Slug joins everything after eval-runs.
        assert "20260424-120300" in spool.name
        assert "safety" in spool.name
        assert "test_x" in spool.name
    finally:
        spool.unlink(missing_ok=True)


def test_spool_paths_are_unique_across_calls(tmp_path: Path) -> None:
    """Two SimulatedUser instances mid-flight in the same module
    must not share a spool — mkstemp guarantees uniqueness."""
    from evals.framework.runner import _make_spool_path

    a = _make_spool_path(tmp_path)
    b = _make_spool_path(tmp_path)
    try:
        assert a != b
    finally:
        a.unlink(missing_ok=True)
        b.unlink(missing_ok=True)


def test_move_spool_into_project_dir(tmp_path: Path) -> None:
    """Successful move places the file at <project_dir>/user_llm_dialogue.md."""
    from evals.framework.runner import (
        _make_spool_path,
        _move_spool_into_project,
    )

    project_dir = tmp_path / "module"
    project_dir.mkdir()
    spool = _make_spool_path(project_dir)
    spool.write_text("dialog content", encoding="utf-8")

    _move_spool_into_project(spool, project_dir)

    final = project_dir / "user_llm_dialogue.md"
    assert final.exists()
    assert final.read_text(encoding="utf-8") == "dialog content"
    assert not spool.exists()  # source removed by shutil.move


def test_move_spool_no_op_when_missing(tmp_path: Path) -> None:
    """Missing spool is silently ignored — no exception, no file written."""
    from evals.framework.runner import _move_spool_into_project

    project_dir = tmp_path / "module"
    project_dir.mkdir()
    nonexistent = tmp_path / "nope.md"

    # Doesn't raise.
    _move_spool_into_project(nonexistent, project_dir)

    # Doesn't create the destination either.
    assert not (project_dir / "user_llm_dialogue.md").exists()


def test_move_spool_creates_project_dir_if_needed(tmp_path: Path) -> None:
    """If the destination directory disappeared somehow, mkdir it back."""
    from evals.framework.runner import (
        _make_spool_path,
        _move_spool_into_project,
    )

    project_dir = tmp_path / "future_module"
    # NB: project_dir does not exist yet.
    spool = _make_spool_path(project_dir)
    spool.write_text("x", encoding="utf-8")

    _move_spool_into_project(spool, project_dir)

    assert (project_dir / "user_llm_dialogue.md").exists()


# ---------------------------------------------------------------------------
# Conversation artifact migration: working_dir → project_dir
#
# The conversation runs in a tmp working dir so the target can't see
# anything in project_dir's name (e.g. "test_murder_brother_in_law")
# that would leak the test's intent.  These tests exercise the helper
# that finalizes the run by moving artifacts into project_dir and
# updating the SessionResult's path attributes to match.
# ---------------------------------------------------------------------------

def _make_working_dir_with_artifacts(
    tmp_path: Path,
    *,
    include_protocol: bool = True,
    include_transcript: bool = True,
    include_metadata: bool = True,
) -> Path:
    """Build a synthetic working_dir populated with conversation output."""
    working = tmp_path / "working"
    working.mkdir()
    if include_protocol:
        pd = working / ".clarity-protocol"
        pd.mkdir()
        (pd / "problem.md").write_text("# Problem\n", encoding="utf-8")
        (pd / "config.json").write_text("{}", encoding="utf-8")
        (pd / "transcripts").mkdir()
        (pd / "transcripts" / "dialog.md").write_text(
            "# Session transcript\n", encoding="utf-8",
        )
    if include_transcript:
        (working / "transcript.md").write_text(
            "## Turn 1\n**User:**\nhi\n", encoding="utf-8",
        )
    if include_metadata:
        (working / "metadata.json").write_text("{}", encoding="utf-8")
    return working


def test_move_conversation_artifacts_populates_project_dir(
    tmp_path: Path,
) -> None:
    """All three artifacts land under project_dir after the move."""
    from evals.framework.runner import _move_conversation_artifacts_to_final

    working = _make_working_dir_with_artifacts(tmp_path)
    project_dir = tmp_path / "final"
    project_dir.mkdir()

    _move_conversation_artifacts_to_final(working, project_dir, None)

    assert (project_dir / ".clarity-protocol" / "problem.md").exists()
    assert (project_dir / "transcript.md").exists()
    assert (project_dir / "metadata.json").exists()
    # Source artifacts consumed by shutil.move.
    assert not (working / ".clarity-protocol").exists()
    assert not (working / "transcript.md").exists()
    assert not (working / "metadata.json").exists()


def test_move_conversation_artifacts_replaces_stale_destinations(
    tmp_path: Path,
) -> None:
    """Same-named files/dirs in project_dir are overwritten by the move.

    Covers the case where project_dir has stale content (e.g., from a
    half-wiped prior run) when the fresh conversation finishes.  The
    final state is exactly the fresh artifacts — no merge, no append.
    """
    from evals.framework.runner import _move_conversation_artifacts_to_final

    working = _make_working_dir_with_artifacts(tmp_path)
    project_dir = tmp_path / "final"
    (project_dir / ".clarity-protocol").mkdir(parents=True)
    (project_dir / ".clarity-protocol" / "STALE.md").write_text(
        "should be gone", encoding="utf-8",
    )
    (project_dir / "transcript.md").write_text("stale transcript")

    _move_conversation_artifacts_to_final(working, project_dir, None)

    # Stale files removed; fresh content present.
    assert not (project_dir / ".clarity-protocol" / "STALE.md").exists()
    assert (project_dir / ".clarity-protocol" / "problem.md").exists()
    assert (project_dir / "transcript.md").read_text(
        encoding="utf-8",
    ).startswith("## Turn 1")


def test_move_conversation_artifacts_updates_result_paths(
    tmp_path: Path,
) -> None:
    """SessionResult path attributes are re-anchored to project_dir.

    Before the move, ``result.project_dir`` / ``protocol_dir`` /
    ``transcript_file`` point at the tmp working_dir.  After the
    move, they should point at the final project_dir — otherwise
    downstream consumers (tests, summary rendering, resume loader)
    would look in the wrong place.
    """
    from evals.framework.runner import _move_conversation_artifacts_to_final
    from evals.framework.types import SessionResult

    working = _make_working_dir_with_artifacts(tmp_path)
    project_dir = tmp_path / "final"
    project_dir.mkdir()

    result = SessionResult(
        project_dir=working,
        protocol_dir=working / ".clarity-protocol",
        transcript_file=working / ".clarity-protocol" / "transcripts" / "dialog.md",
    )

    _move_conversation_artifacts_to_final(working, project_dir, result)

    assert result.project_dir == project_dir
    assert result.protocol_dir == project_dir / ".clarity-protocol"
    assert result.transcript_file == (
        project_dir / ".clarity-protocol" / "transcripts" / "dialog.md"
    )


def test_move_conversation_artifacts_handles_missing_sources(
    tmp_path: Path,
) -> None:
    """Failure case: converse_with raised before writing some artifacts.

    The helper should move what's present and silently skip what's
    not.  Used with result=None in the failure-preservation path.
    """
    from evals.framework.runner import _move_conversation_artifacts_to_final

    # Only the protocol dir exists — the target wrote partial state
    # before the conversation failed.  No transcript.md, no metadata.
    working = _make_working_dir_with_artifacts(
        tmp_path, include_transcript=False, include_metadata=False,
    )
    project_dir = tmp_path / "final"

    # result=None signals "partial / failed run".
    _move_conversation_artifacts_to_final(working, project_dir, None)

    # Partial artifact preserved for debugging.
    assert (project_dir / ".clarity-protocol" / "problem.md").exists()
    # Missing artifacts stay missing — no placeholder files created.
    assert not (project_dir / "transcript.md").exists()
    assert not (project_dir / "metadata.json").exists()


def test_move_conversation_artifacts_creates_project_dir(
    tmp_path: Path,
) -> None:
    """Destination mkdir on demand — helper is safe to call before the
    fixture has ensured project_dir exists."""
    from evals.framework.runner import _move_conversation_artifacts_to_final

    working = _make_working_dir_with_artifacts(tmp_path)
    project_dir = tmp_path / "nonexistent" / "nested" / "final"

    _move_conversation_artifacts_to_final(working, project_dir, None)

    assert project_dir.is_dir()
    assert (project_dir / "transcript.md").exists()


def test_move_conversation_artifacts_tolerates_transcript_outside_working_dir(
    tmp_path: Path,
) -> None:
    """Defensive: if transcript_file points somewhere unexpected, leave it.

    Shouldn't happen in practice (ClaritySession always writes under
    its own working dir) but guards against a confusing KeyError or
    incorrect path rewrite if the invariant ever breaks.
    """
    from evals.framework.runner import _move_conversation_artifacts_to_final
    from evals.framework.types import SessionResult

    working = _make_working_dir_with_artifacts(tmp_path)
    project_dir = tmp_path / "final"
    project_dir.mkdir()

    # transcript_file points at some external location.
    external_transcript = tmp_path / "somewhere_else.md"
    external_transcript.write_text("external", encoding="utf-8")
    result = SessionResult(
        project_dir=working,
        transcript_file=external_transcript,
    )

    _move_conversation_artifacts_to_final(working, project_dir, result)

    # transcript_file left as-is (not re-anchored) since it wasn't under working.
    assert result.transcript_file == external_transcript
    assert result.project_dir == project_dir


def test_partial_prior_run_does_not_resume(tmp_path: Path) -> None:
    """Regression: a previous run that wrote .clarity-protocol/ but
    died before transcript.md must NOT look resumable.

    If we did treat this as resumable, the Clarity target would load
    the stale protocol and act as if it were continuing, while the
    simulated user started from turn 1 — a silent desync.  The fix
    is a combination of: ``_load_session_result`` returning None when
    the transcript is missing (enforced here) AND the runner wiping
    conversation artifacts before starting a fresh run (the other
    half of the fix, covered structurally by the fixture's code path).
    """
    from evals.framework.runner import (
        _load_session_result,
        _wipe_conversation_artifacts,
    )

    # Simulate the interrupted-run state: protocol files on disk,
    # no transcript.md.
    (tmp_path / ".clarity-protocol").mkdir()
    (tmp_path / ".clarity-protocol" / "problem.md").write_text(
        "# Stale problem statement from the aborted run",
    )
    (tmp_path / ".clarity-protocol" / "config.json").write_text("{}")

    # Resume is rejected — the fixture falls through to the fresh path.
    assert _load_session_result(tmp_path) is None

    # The fresh path then wipes before invoking run_conversation.
    # After the wipe, the target will see a clean project dir (no
    # stale protocol) just like a first-time run.
    _wipe_conversation_artifacts(tmp_path)
    assert not (tmp_path / ".clarity-protocol").exists()


# ---------------------------------------------------------------------------
# Smoke test for the module public API
# ---------------------------------------------------------------------------

def test_public_api_exports() -> None:
    """Resume pieces are reachable from the framework package root."""
    from evals.framework import JudgeCache as ExportedCache
    from evals.framework import compute_fingerprint as exported_fp

    assert ExportedCache is JudgeCache
    assert exported_fp is compute_fingerprint
    # Silence "imported but unused" for static analyzers.
    _ = (ExportedCache, exported_fp, pytest)
