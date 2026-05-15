"""
Tests for Claude SDK backend-signaled compaction detection.

Two layers:
* Unit tests for the JSONL summary-extraction helper, with the
  range of message shapes the SDK can produce.
* Backend-level tests that feed synthetic transcript files into
  ``_detect_and_report_compaction`` and verify ``on_compaction``
  fires with the right :class:`CompactionInfo`.

The PreCompact hook itself is exercised at the handler level
(``_on_pre_compact``) since wiring up a real SDK ``query()`` call
would require an LLM session and isn't appropriate for unit tests.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from clarity_agent.llm.impl.claude_sdk import (
    SdkChatBackend,
    _extract_summary_text,
)
from clarity_agent.llm.types import CompactionInfo


@pytest.fixture
def backend(tmp_path: Path) -> SdkChatBackend:
    """An SdkChatBackend instance for testing.

    Constructs without invoking the underlying SDK (the import
    happens in __init__; if claude_agent_sdk isn't available the
    test is skipped).  Project/clarity dirs point at a tmp path.

    No transcript is bound here — tests that need one (everything
    in :class:`TestDetectAndReportCompaction`) construct a fresh
    backend with a transcript via ``backend_with_transcript``.
    """
    try:
        return SdkChatBackend(project_dir=tmp_path, clarity_agent_dir=tmp_path)
    except ImportError:
        pytest.skip("claude_agent_sdk not installed")


@pytest.fixture
def backend_with_transcript(tmp_path: Path):
    """An SdkChatBackend bound to a real Transcript.

    Used for tests that exercise the
    :meth:`_record_provider_compaction` path — without a transcript,
    the backend no-ops silently (correct behavior, but not what
    those tests are checking).
    """
    try:
        from clarity_agent.transcript import Transcript
        transcript = Transcript(tmp_path)
        return SdkChatBackend(
            project_dir=tmp_path, clarity_agent_dir=tmp_path,
            transcript=transcript,
        )
    except ImportError:
        pytest.skip("claude_agent_sdk not installed")


# ---------------------------------------------------------------------------
# _extract_summary_text — message-shape coverage
# ---------------------------------------------------------------------------


class TestExtractSummaryText:
    def test_message_as_plain_string(self):
        entry = {"message": "the summary text"}
        assert _extract_summary_text(entry) == "the summary text"

    def test_message_content_as_string(self):
        entry = {"message": {"role": "user", "content": "the summary text"}}
        assert _extract_summary_text(entry) == "the summary text"

    def test_message_content_as_list_of_text_blocks(self):
        # The Anthropic API content-block shape — the SDK passes
        # these through verbatim into the JSONL.
        entry = {"message": {"content": [
            {"type": "text", "text": "first paragraph"},
            {"type": "text", "text": "second paragraph"},
        ]}}
        assert _extract_summary_text(entry) == "first paragraph\nsecond paragraph"

    def test_message_content_mixed_blocks_skips_non_text(self):
        # Defensive: if a non-text block sneaks in (image block,
        # something exotic), we don't crash — just skip it.
        entry = {"message": {"content": [
            {"type": "text", "text": "useful content"},
            {"type": "image", "source": {"data": "..."}},
            {"type": "text", "text": "more useful content"},
        ]}}
        result = _extract_summary_text(entry)
        assert "useful content" in result
        assert "more useful content" in result
        assert "image" not in result

    def test_empty_message_returns_empty_string(self):
        assert _extract_summary_text({"message": ""}) == ""
        assert _extract_summary_text({"message": None}) == ""
        assert _extract_summary_text({}) == ""

    def test_strips_surrounding_whitespace(self):
        # SDK might pad summaries with newlines; we want the clean text.
        entry = {"message": "\n\n  the summary  \n\n"}
        assert _extract_summary_text(entry) == "the summary"


# ---------------------------------------------------------------------------
# _detect_and_report_compaction — JSONL → on_compaction signal
# ---------------------------------------------------------------------------


def _write_transcript(path: Path, entries: list[dict[str, Any]]) -> None:
    """Write a list of entries as JSONL to the given path.

    Mirrors the SDK's session transcript format: one JSON object
    per line, with the fields the SDK's own parser expects
    (``type``, ``uuid``, ``parentUuid``, ``message``, etc.).
    """
    path.write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8",
    )


class TestDetectAndReportCompaction:
    """Detection happens at the end of _run_query.  When the
    PreCompact hook captured a transcript path AND the backend has
    a transcript bound, the new isCompactSummary entries get
    translated into ``Transcript.external_compaction_occurred``
    calls plus ``on_compaction_started`` / ``on_compaction_complete``
    fires for UI.

    Without a transcript bound, detection runs but no recording
    happens (correct — provider compaction stays internal).
    """

    def test_no_pending_path_is_noop(self, backend_with_transcript):
        # Nothing has signaled compaction → no-op.
        backend = backend_with_transcript
        started_calls: list[None] = []
        backend.on_compaction_started = lambda: started_calls.append(None)
        backend._detect_and_report_compaction()
        assert started_calls == []
        # Transcript got no new chapter.
        assert backend._transcript.current_chapter is None

    def test_missing_transcript_file_is_noop(self, backend_with_transcript, tmp_path):
        backend = backend_with_transcript
        backend._pending_compact_transcript_path = tmp_path / "missing.jsonl"
        started_calls: list[None] = []
        backend.on_compaction_started = lambda: started_calls.append(None)
        backend._detect_and_report_compaction()
        assert started_calls == []

    def test_records_provider_summary_on_transcript(
        self, backend_with_transcript, tmp_path,
    ):
        # Base case: one isCompactSummary entry → one chapter
        # rollover with the provider's summary, and the
        # on_compaction_complete callback fires with the result.
        from clarity_agent.transcript import CompactionSummary
        backend = backend_with_transcript

        path = tmp_path / "session.jsonl"
        _write_transcript(path, [
            {"type": "user", "uuid": "u1", "message": {"content": "hello"}},
            {
                "type": "user",
                "uuid": "compact-1",
                "isCompactSummary": True,
                "message": {"content": "summary of earlier conversation"},
            },
        ])
        backend._pending_compact_transcript_path = path
        started_calls: list[None] = []
        completed: list[CompactionInfo] = []
        backend.on_compaction_started = lambda: started_calls.append(None)
        backend.on_compaction_complete = completed.append

        backend._detect_and_report_compaction()

        # UI callbacks fired in order.
        assert started_calls == [None]
        assert len(completed) == 1
        assert completed[0].summary == "summary of earlier conversation"
        # Transcript created chapter 1 (was empty before — the
        # transcript becomes the archive of the SDK's pre-compaction
        # state).  The CompactionSummary is the new chapter's first
        # event.
        new_chapter = backend._transcript.current_chapter
        new_events = list(backend._transcript.chapter_events(new_chapter))
        assert isinstance(new_events[0], CompactionSummary)
        assert new_events[0].summary == "summary of earlier conversation"

    def test_already_seen_uuids_arent_recorded_again(
        self, backend_with_transcript, tmp_path,
    ):
        # Idempotence: same uuid seen twice → only recorded once.
        backend = backend_with_transcript

        path = tmp_path / "session.jsonl"
        _write_transcript(path, [
            {
                "type": "user",
                "uuid": "compact-1",
                "isCompactSummary": True,
                "message": {"content": "summary"},
            },
        ])
        backend._pending_compact_transcript_path = path
        completed: list[CompactionInfo] = []
        backend.on_compaction_complete = completed.append

        backend._detect_and_report_compaction()
        # Re-set the pending path (simulating a second PreCompact)
        # — same uuid is in seen, so no second recording.
        backend._pending_compact_transcript_path = path
        backend._detect_and_report_compaction()

        assert len(completed) == 1

    def test_multiple_new_summaries_each_record(
        self, backend_with_transcript, tmp_path,
    ):
        # The SDK doesn't typically emit multiple compactions in a
        # single query, but if it did, each one with a new uuid
        # should get its own chapter rollover.
        from clarity_agent.transcript import CompactionSummary
        backend = backend_with_transcript

        path = tmp_path / "session.jsonl"
        _write_transcript(path, [
            {
                "type": "user", "uuid": "compact-1",
                "isCompactSummary": True,
                "message": {"content": "first summary"},
            },
            {"type": "assistant", "uuid": "a1", "message": {"content": "..."}},
            {
                "type": "user", "uuid": "compact-2",
                "isCompactSummary": True,
                "message": {"content": "second summary"},
            },
        ])
        backend._pending_compact_transcript_path = path
        completed: list[CompactionInfo] = []
        backend.on_compaction_complete = completed.append

        backend._detect_and_report_compaction()

        assert len(completed) == 2
        assert completed[0].summary == "first summary"
        assert completed[1].summary == "second summary"
        # Two new chapters created (transcript was empty before).
        # Chapters 1 + 2 each carry one of the summaries.
        chapters = backend._transcript.chapters
        assert len(chapters) == 2
        summaries: list[str] = []
        for ch in chapters:
            for e in backend._transcript.chapter_events(ch):
                if isinstance(e, CompactionSummary):
                    summaries.append(e.summary)
                    break
        assert summaries == ["first summary", "second summary"]

    def test_non_compact_entries_ignored(
        self, backend_with_transcript, tmp_path,
    ):
        # Regular user/assistant entries don't trigger anything.
        backend = backend_with_transcript
        path = tmp_path / "session.jsonl"
        _write_transcript(path, [
            {"type": "user", "uuid": "u1", "message": {"content": "hello"}},
            {"type": "assistant", "uuid": "a1", "message": {"content": "hi"}},
        ])
        backend._pending_compact_transcript_path = path
        completed: list[CompactionInfo] = []
        backend.on_compaction_complete = completed.append

        backend._detect_and_report_compaction()

        assert completed == []

    def test_malformed_lines_skipped(self, backend_with_transcript, tmp_path):
        # Bad JSON lines in the transcript don't abort the read.
        backend = backend_with_transcript
        path = tmp_path / "session.jsonl"
        good_entry = {
            "type": "user", "uuid": "compact-1",
            "isCompactSummary": True,
            "message": {"content": "the summary"},
        }
        path.write_text(
            "{this is not valid json\n"
            + json.dumps(good_entry) + "\n",
            encoding="utf-8",
        )
        backend._pending_compact_transcript_path = path
        completed: list[CompactionInfo] = []
        backend.on_compaction_complete = completed.append

        backend._detect_and_report_compaction()

        assert len(completed) == 1
        assert completed[0].summary == "the summary"

    def test_no_transcript_bound_is_safe(self, backend, tmp_path):
        # Without a transcript, detection runs but doesn't record —
        # provider compaction stays internal to the SDK.  No
        # exceptions, no callbacks (since the rollover never
        # happens, neither does the on_compaction_complete fire).
        path = tmp_path / "session.jsonl"
        _write_transcript(path, [
            {
                "type": "user", "uuid": "compact-1",
                "isCompactSummary": True,
                "message": {"content": "summary"},
            },
        ])
        backend._pending_compact_transcript_path = path
        completed: list[CompactionInfo] = []
        backend.on_compaction_complete = completed.append
        # Should just not raise.
        backend._detect_and_report_compaction()
        assert completed == []


# ---------------------------------------------------------------------------
# PreCompact hook handler
# ---------------------------------------------------------------------------


class TestPreCompactHandler:
    """The handler the SDK calls when it's about to compact a session.

    We don't drive the real SDK here — just call the handler with
    the input shapes it would receive.  The handler's job is small:
    capture transcript_path on a PreCompact event, no-op everything
    else, always return an empty dict so the SDK proceeds.
    """

    def test_captures_transcript_path_on_precompact(self, backend, tmp_path):
        transcript_path = tmp_path / "session.jsonl"
        result = asyncio.run(backend._on_pre_compact(
            {
                "hook_event_name": "PreCompact",
                "transcript_path": str(transcript_path),
                "session_id": "test-session",
                "cwd": str(tmp_path),
                "trigger": "auto",
                "custom_instructions": None,
            },
            None,
            {"signal": None},
        ))
        assert backend._pending_compact_transcript_path == transcript_path
        # Empty output → SDK proceeds normally.
        assert result == {}

    def test_ignores_non_precompact_events(self, backend, tmp_path):
        # The SDK might call our handler for hooks other than
        # PreCompact if we accidentally register it more broadly.
        # Defensive: only act on PreCompact.
        backend._pending_compact_transcript_path = None
        result = asyncio.run(backend._on_pre_compact(
            {
                "hook_event_name": "PostToolUse",
                "transcript_path": str(tmp_path / "session.jsonl"),
                "session_id": "test-session",
                "cwd": str(tmp_path),
                "tool_name": "Read",
                "tool_input": {},
                "tool_response": None,
                "tool_use_id": "tool-1",
            },
            None,
            {"signal": None},
        ))
        assert backend._pending_compact_transcript_path is None
        assert result == {}

    def test_missing_transcript_path_doesnt_explode(self, backend):
        # If the input is malformed (no transcript_path), we
        # gracefully no-op rather than crashing the SDK's hook
        # dispatch.
        result = asyncio.run(backend._on_pre_compact(
            {"hook_event_name": "PreCompact"},
            None,
            {"signal": None},
        ))
        assert backend._pending_compact_transcript_path is None
        assert result == {}
