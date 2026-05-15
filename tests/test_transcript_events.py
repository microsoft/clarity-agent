"""Tests for the structured transcript event schema."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from clarity_agent.transcript.events import (
    AssistantText,
    ChapterStarted,
    CompactionSummary,
    ModelOverride,
    ProcessStarted,
    SessionResume,
    ToolResult,
    ToolUse,
    ToolUseText,
    UserTurn,
    parse_event,
    serialize_event,
)


# A fixed timestamp keeps snapshot assertions stable across CI runs.
T0 = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


def _round_trip(event):
    """Serialize → JSON line → parse back; assert equality."""
    line = serialize_event(event)
    # JSONL invariant: the line must be valid JSON with no newlines.
    assert "\n" not in line
    data = json.loads(line)
    back = parse_event(data)
    assert back == event
    return back


class TestRoundTrip:
    """Every event type must survive serialize → parse round-trip."""

    def test_chapter_started(self):
        ev = ChapterStarted(
            timestamp=T0,
            project_dir="/Users/foo/proj",
            backend="SdkChatBackend",
        )
        _round_trip(ev)

    def test_session_resume(self):
        ev = SessionResume(
            timestamp=T0,
            backend="SdkChatBackend",
            llm_session_id="abc123",
        )
        _round_trip(ev)

    def test_session_resume_without_session_id(self):
        # When the backend hasn't yet produced a session id (Claude CLI
        # case), session_resume is recorded with None.  Round-trip must
        # preserve None faithfully.
        ev = SessionResume(timestamp=T0, backend="SdkChatBackend")
        back = _round_trip(ev)
        assert back.llm_session_id is None

    def test_user_turn(self):
        ev = UserTurn(timestamp=T0, content="hello clarity")
        _round_trip(ev)

    def test_assistant_text(self):
        ev = AssistantText(timestamp=T0, content="hi! what should we work on?")
        _round_trip(ev)

    def test_tool_use_with_structured_input(self):
        # Structured ToolUse must preserve the input dict verbatim,
        # including nested values — that's the whole point of switching
        # away from the flattened legacy format.
        ev = ToolUse(
            timestamp=T0,
            tool_use_id="toolu_01ABCDEF",
            name="Bash",
            input={"command": "ls -la", "timeout": 30, "options": {"sudo": False}},
        )
        back = _round_trip(ev)
        assert back.input == ev.input
        assert back.input["options"]["sudo"] is False

    def test_tool_result(self):
        ev = ToolResult(
            timestamp=T0,
            tool_use_id="toolu_01ABCDEF",
            content="total 8\ndrwxr-xr-x ...",
            is_error=False,
        )
        _round_trip(ev)

    def test_tool_result_error(self):
        ev = ToolResult(
            timestamp=T0,
            tool_use_id="toolu_01ABCDEF",
            content="command not found",
            is_error=True,
        )
        back = _round_trip(ev)
        assert back.is_error is True

    def test_tool_use_text_legacy(self):
        # Legacy migration shape: detail is just a string.  No
        # tool_use_id, no structured input — best we can recover from
        # pre-#35 transcripts.
        ev = ToolUseText(
            timestamp=T0,
            name="Bash",
            detail="ls -la → total 8...",
        )
        _round_trip(ev)

    def test_process_started_minimal(self):
        ev = ProcessStarted(timestamp=T0, process_name="clarity-agent")
        back = _round_trip(ev)
        assert back.tier is None
        assert back.model is None

    def test_process_started_with_tier_and_model(self):
        ev = ProcessStarted(
            timestamp=T0,
            process_name="failure-brainstorming",
            tier="deep",
            model="claude-opus-4-7",
        )
        _round_trip(ev)

    def test_model_override(self):
        ev = ModelOverride(timestamp=T0, tier="fast", model="claude-haiku-4-5")
        _round_trip(ev)

    def test_compaction_summary(self):
        # Compaction-summary events carry the digest of an earlier
        # chapter as the first content event of the chapter that
        # replaces it.  Round-trip preserves the summary text and
        # source-chapter bookkeeping.
        ev = CompactionSummary(
            timestamp=T0,
            summary=(
                "User and Clarity agreed to ship the auth refactor "
                "by Friday; protocol decisions D-1..D-7 captured."
            ),
            source_chapter=1,
            source_turn_count=42,
        )
        back = _round_trip(ev)
        assert back.summary.startswith("User and Clarity")
        assert back.source_chapter == 1
        assert back.source_turn_count == 42


class TestDiscriminator:
    """The ``type`` field must dispatch to the right class on parse."""

    def test_dispatches_to_user_turn(self):
        ev = parse_event(
            {"type": "user_turn", "timestamp": T0.isoformat(), "content": "x"},
        )
        assert isinstance(ev, UserTurn)

    def test_dispatches_to_tool_use(self):
        ev = parse_event({
            "type": "tool_use",
            "timestamp": T0.isoformat(),
            "tool_use_id": "id",
            "name": "Read",
            "input": {"file_path": "/x"},
        })
        assert isinstance(ev, ToolUse)

    def test_unknown_type_raises(self):
        # An event type that isn't in the discriminated union must fail
        # validation rather than silently dropping to a generic shape —
        # otherwise typos in stored data go undetected.
        with pytest.raises(ValidationError):
            parse_event({
                "type": "definitely_not_a_real_event",
                "timestamp": T0.isoformat(),
            })

    def test_missing_required_field_raises(self):
        # UserTurn requires ``content``; omitting it should fail loudly.
        with pytest.raises(ValidationError):
            parse_event({"type": "user_turn", "timestamp": T0.isoformat()})


class TestSerialization:
    """JSONL line-shape invariants the writer relies on."""

    def test_no_embedded_newlines_in_string_content(self):
        # User content can legitimately contain newlines.  The JSON
        # encoder must escape them so the JSONL one-line-per-event
        # invariant holds.  Without this, a multi-line user message
        # would corrupt the file structure.
        ev = UserTurn(timestamp=T0, content="line 1\nline 2\nline 3")
        line = serialize_event(ev)
        assert "\n" not in line
        back = parse_event(json.loads(line))
        assert back.content == "line 1\nline 2\nline 3"

    def test_unicode_preserved(self):
        # ``ensure_ascii=False`` keeps unicode readable in the file
        # (utf-8 by convention); round-trip must still match.
        ev = UserTurn(timestamp=T0, content="naïve résumé — 日本語")
        back = _round_trip(ev)
        assert back.content == "naïve résumé — 日本語"

    def test_timestamp_serializes_as_iso(self):
        # We rely on ISO 8601 in the on-disk format so other tooling
        # (jq, scripts, etc.) can read it without a Python deserializer.
        ev = UserTurn(timestamp=T0, content="x")
        data = json.loads(serialize_event(ev))
        assert data["timestamp"].startswith("2026-05-14T12:00:00")

    def test_schema_version_emitted(self):
        # Every serialized event must carry the schema version so a
        # future reader can dispatch on it.
        ev = UserTurn(timestamp=T0, content="x")
        data = json.loads(serialize_event(ev))
        assert data["schema_version"] == "1"
