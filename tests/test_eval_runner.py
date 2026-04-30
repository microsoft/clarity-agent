"""Tests for eval-framework helpers that aren't end-to-end evals.

The round-trip test guards the coupling between
:attr:`SessionResult.transcript` (the format we write to
``transcript.md``) and :func:`_parse_transcript_md` (the inverse,
used by the resume path to reconstruct ``SessionResult`` from
preserved files).  If either side changes, the other must change
in lockstep, and this test catches drift.
"""

from __future__ import annotations

import json
from pathlib import Path

from evals.framework.runner import (
    _load_session_result,
    _parse_transcript_md,
    _project_dir_path_for,
)
from evals.framework.types import SessionResult, Turn


def test_transcript_roundtrip_single_turn() -> None:
    original = [Turn(user="hello", target="hi there")]
    result = SessionResult(turns=original)
    parsed = _parse_transcript_md(result.transcript)
    assert parsed == original


def test_transcript_roundtrip_multi_turn() -> None:
    original = [
        Turn(user="opening", target="response one"),
        Turn(user="follow up", target="response two"),
        Turn(user="thanks", target="you're welcome"),
    ]
    result = SessionResult(turns=original)
    parsed = _parse_transcript_md(result.transcript)
    assert parsed == original


def test_transcript_roundtrip_multiline_content() -> None:
    original = [
        Turn(
            user="line one\nline two\n\nline four",
            target="reply line one\nreply line two",
        ),
        Turn(
            user="another\nmultiline",
            target="and\nanother\nmultiline reply",
        ),
    ]
    result = SessionResult(turns=original)
    parsed = _parse_transcript_md(result.transcript)
    assert parsed == original


def test_load_session_result_returns_none_when_missing(tmp_path: Path) -> None:
    """No transcript.md → None, so the runner falls through to a fresh run."""
    assert _load_session_result(tmp_path) is None


def test_load_session_result_reconstructs_from_disk(tmp_path: Path) -> None:
    original_turns = [
        Turn(user="a", target="b"),
        Turn(user="c\nwith newline", target="d"),
    ]
    src = SessionResult(
        turns=original_turns, cost_usd=0.123,
        stopped_early=True, duration_seconds=42.5,
    )
    (tmp_path / "transcript.md").write_text(src.transcript, encoding="utf-8")
    (tmp_path / "metadata.json").write_text(
        json.dumps({
            "turn_count": src.turn_count,
            "cost_usd": src.cost_usd,
            "stopped_early": src.stopped_early,
            "duration_seconds": src.duration_seconds,
        }),
        encoding="utf-8",
    )

    loaded = _load_session_result(tmp_path)
    assert loaded is not None
    assert loaded.turns == original_turns
    assert loaded.cost_usd == 0.123
    assert loaded.stopped_early is True
    assert loaded.duration_seconds == 42.5
    assert loaded.project_dir == tmp_path
    # No .clarity-protocol/ on disk → protocol_dir is None
    assert loaded.protocol_dir is None


def test_load_session_result_picks_up_protocol_dir(tmp_path: Path) -> None:
    (tmp_path / "transcript.md").write_text(
        SessionResult(turns=[Turn(user="x", target="y")]).transcript,
        encoding="utf-8",
    )
    (tmp_path / ".clarity-protocol").mkdir()
    loaded = _load_session_result(tmp_path)
    assert loaded is not None
    assert loaded.protocol_dir == tmp_path / ".clarity-protocol"


def test_project_dir_path_for_under_cases(tmp_path: Path) -> None:
    """Pure path helper — no I/O."""
    module = Path("evals/cases/safety/test_terminal_suicide.py")
    out = _project_dir_path_for(tmp_path, module)
    assert out == tmp_path / "safety" / "test_terminal_suicide"
    # Path-only — directory must NOT have been created.
    assert not out.exists()


def test_project_dir_path_for_outside_cases(tmp_path: Path) -> None:
    module = Path("/some/random/path/test_thing.py")
    out = _project_dir_path_for(tmp_path, module)
    assert out == tmp_path / "test_thing"
