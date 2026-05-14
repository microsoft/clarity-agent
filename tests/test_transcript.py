"""
Tests for the :class:`Transcript` public API.

The transcript subpackage exposes a small public surface:
:class:`Transcript` plus the event types.  These tests exercise the
class's behavior end-to-end — chapters, reads, writes, lifecycle,
forgiveness, threading, and conversation reconstruction.  Internal
implementation modules (``_render``, ``_reconstruct``, the
``_ChapterWriter`` class inside ``transcript.py``) are not tested
directly; we trust that exercising them through the public API
catches what matters.

Event-type round-tripping (serialization, schema-version, etc.) is
covered separately in :file:`test_transcript_events.py`.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from clarity_agent.transcript import (
    AssistantText,
    ChapterStarted,
    ModelOverride,
    ProcessStarted,
    SessionResume,
    ToolResult,
    ToolUse,
    ToolUseText,
    Transcript,
    UserTurn,
    parse_event,
)


T0 = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


def _t(offset_minutes: int = 0) -> datetime:
    return T0 + timedelta(minutes=offset_minutes)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# Construction + identity
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_construction_is_cheap_and_does_no_io(self, project):
        # No directory creation, no file open — Transcript can be
        # constructed anywhere (early in startup, in tests, etc.)
        # without lifecycle worries.
        t = Transcript(project)
        assert t.project_dir == project
        assert not t.directory.exists()

    def test_accepts_str_path(self, project):
        # Convenience: str works, returned as Path.
        t = Transcript(str(project))
        assert isinstance(t.project_dir, Path)
        assert t.project_dir == project


# ---------------------------------------------------------------------------
# Chapter enumeration
# ---------------------------------------------------------------------------


class TestChapters:
    def test_empty_state(self, project):
        t = Transcript(project)
        assert t.is_empty is True
        assert t.current_chapter is None
        assert t.chapters == []

    def test_first_write_creates_chapter_one(self, project):
        # ``write`` lazily bootstraps chapter 1 when no chapter
        # exists.  Callers don't have to call any "start" method to
        # begin writing on a fresh project.
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="hi"))
        t.close()
        assert t.current_chapter == 1
        assert t.chapters == [1]

    def test_start_new_chapter_increments(self, project):
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="ch1"))
        new = t.start_new_chapter()
        assert new == 2
        assert t.current_chapter == 2
        t.write(UserTurn(timestamp=_t(1), content="ch2"))
        t.close()
        assert t.chapters == [1, 2]

    def test_legacy_timestamp_named_files_ignored(self, project):
        # Pre-#35 transcripts have timestamp-prefixed names.  Those
        # mustn't be picked up as chapters; otherwise pre-migration
        # users would see confusing chapter numbering.
        t = Transcript(project)
        t.directory.mkdir(parents=True)
        (t.directory / "2026-04-12T15-00-00.md").write_text("legacy stuff")
        (t.directory / "alice-20260415-090000.md").write_text("more legacy")

        assert t.is_empty is True
        assert t.chapters == []

    def test_stray_md_without_jsonl_not_a_chapter(self, project):
        # The JSONL is the source of truth.  An orphan ``.md``
        # without its JSONL companion (e.g., from partial deletion)
        # mustn't be mistaken for a real chapter.
        t = Transcript(project)
        t.directory.mkdir(parents=True)
        (t.directory / "0001.md").write_text("# Chapter\n")

        assert t.is_empty is True

    def test_gap_in_numbering_resolves_to_highest(self, project):
        # If someone deletes a middle chapter, the next new chapter
        # goes past the highest existing, never filling the gap.
        # That guarantees a new chapter can't collide with a
        # historical filename.
        t = Transcript(project)
        t.directory.mkdir(parents=True)
        (t.directory / "0001.events.jsonl").touch()
        (t.directory / "0003.events.jsonl").touch()

        assert t.current_chapter == 3
        new = t.start_new_chapter()
        assert new == 4


# ---------------------------------------------------------------------------
# Writing — dual JSONL + markdown output
# ---------------------------------------------------------------------------


class TestWriting:
    def test_event_appears_in_both_files(self, project):
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="hello"))
        t.close()

        d = t.directory  # Whichever protocol-dir variant the project resolves to.
        jsonl_text = (d / "0001.events.jsonl").read_text(encoding="utf-8")
        md_text = (d / "0001.md").read_text(encoding="utf-8")

        # JSONL: one parseable line.
        line = jsonl_text.strip()
        assert "\n" not in line
        ev = parse_event(json.loads(line))
        assert isinstance(ev, UserTurn)
        assert ev.content == "hello"

        # Markdown: rendered fragment with the legacy ``**User:**`` prefix.
        assert "**User:** hello" in md_text

    def test_events_persist_across_close_and_reopen(self, project):
        # Closing the Transcript releases handles; constructing a
        # fresh instance must see everything that was written before.
        # This is the core invariant for "resume on next launch."
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="first"))
        t.close()

        t2 = Transcript(project)
        t2.write(UserTurn(timestamp=_t(1), content="second"))
        t2.close()

        events = list(Transcript(project).current_events())
        assert [e.content for e in events] == ["first", "second"]

    def test_write_after_close_lazy_reopens(self, project):
        # ``close()`` releases handles but doesn't render the
        # instance unusable.  A subsequent ``write()`` should
        # transparently re-open the writer.
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="a"))
        t.close()
        t.write(UserTurn(timestamp=_t(1), content="b"))
        t.close()
        events = list(Transcript(project).current_events())
        assert [e.content for e in events] == ["a", "b"]

    def test_close_is_idempotent(self, project):
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="x"))
        t.close()
        t.close()  # no error

    def test_start_new_chapter_isolates_writes(self, project):
        # After ``start_new_chapter``, writes go to the new file
        # only.  The old chapter remains untouched (read-only by
        # convention).
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="old"))
        t.start_new_chapter()
        t.write(UserTurn(timestamp=_t(1), content="new"))
        t.close()

        ch1 = list(t.chapter_events(1))
        ch2 = list(t.chapter_events(2))
        assert [e.content for e in ch1] == ["old"]
        assert [e.content for e in ch2] == ["new"]

    def test_context_manager_closes_on_exit(self, project):
        # The Transcript supports ``with`` for guaranteed cleanup.
        with Transcript(project) as t:
            t.write(UserTurn(timestamp=T0, content="x"))
        # After the with block, we should be able to construct a
        # fresh instance and see the written event.
        events = list(Transcript(project).current_events())
        assert len(events) == 1 and events[0].content == "x"


class TestThreading:
    def test_concurrent_writes_serialize_safely(self, project):
        """Heavy concurrent ``write`` from N threads doesn't tear JSONL.

        Reproduces the realistic scenario inside ``WebSessionAdapter``
        where the executor thread (tool callbacks) and other code
        paths race on the same Transcript.
        """
        N_THREADS = 8
        EVENTS_PER_THREAD = 25

        t = Transcript(project)
        # Force the writer open in the main thread so all worker
        # threads contend on the lock rather than racing to open.
        t.write(UserTurn(timestamp=T0, content="seed"))

        def write_many(thread_id: int) -> None:
            for i in range(EVENTS_PER_THREAD):
                t.write(UserTurn(
                    timestamp=_t(0),
                    content=f"t{thread_id}-{i}",
                ))

        threads = [
            threading.Thread(target=write_many, args=(i,))
            for i in range(N_THREADS)
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        t.close()

        # Every line must be valid JSON; no torn writes.
        jsonl_path = t.directory / "0001.events.jsonl"
        lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
        # 1 seed + N_THREADS * EVENTS_PER_THREAD.
        assert len(lines) == 1 + N_THREADS * EVENTS_PER_THREAD
        for line in lines:
            json.loads(line)  # raises on torn writes


# ---------------------------------------------------------------------------
# Reading — forgiveness, scopes
# ---------------------------------------------------------------------------


class TestReading:
    def test_current_events_empty_when_no_chapters(self, project):
        # Callers like WebSessionAdapter use this to ask "have I any
        # history?" without pre-checking file existence.
        t = Transcript(project)
        assert list(t.current_events()) == []

    def test_chapter_events_targeted(self, project):
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="ch1"))
        t.start_new_chapter()
        t.write(UserTurn(timestamp=_t(1), content="ch2"))
        t.close()
        assert [e.content for e in t.chapter_events(1)] == ["ch1"]
        assert [e.content for e in t.chapter_events(2)] == ["ch2"]

    def test_all_events_walks_chapters_in_order(self, project):
        t = Transcript(project)
        t.write(UserTurn(timestamp=_t(0), content="a"))
        t.write(UserTurn(timestamp=_t(1), content="b"))
        t.start_new_chapter()
        t.write(UserTurn(timestamp=_t(2), content="c"))
        t.close()
        assert [e.content for e in t.all_events()] == ["a", "b", "c"]


class TestReadingForgiveness:
    """The reader must tolerate corruption — partial-write tails,
    unknown event types, blank lines.  This is critical because a
    chapter file might end mid-line if the writer was interrupted."""

    def test_malformed_json_line_skipped(self, project, caplog):
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="ok before"))
        t.close()

        # Manually append a malformed line + a valid line after it.
        jsonl_path = t.directory / "0001.events.jsonl"
        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write("{this is not valid json\n")

        t2 = Transcript(project)
        t2.write(UserTurn(timestamp=_t(1), content="ok after"))
        t2.close()

        events = list(Transcript(project).current_events())
        contents = [e.content for e in events]
        assert contents == ["ok before", "ok after"]
        assert any("malformed JSONL" in r.message for r in caplog.records)

    def test_unknown_event_type_skipped(self, project, caplog):
        # Forward compatibility: a future event type we don't
        # recognize must not break loading.
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="before"))
        t.close()

        jsonl_path = t.directory / "0001.events.jsonl"
        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(
                '{"schema_version":"1","type":"future_event",'
                '"timestamp":"2026-05-14T12:00:00+00:00","payload":"x"}\n',
            )

        t2 = Transcript(project)
        t2.write(UserTurn(timestamp=_t(1), content="after"))
        t2.close()

        events = list(Transcript(project).current_events())
        assert [e.content for e in events] == ["before", "after"]
        assert any("unparseable event" in r.message for r in caplog.records)

    def test_blank_lines_skipped_silently(self, project):
        # Hand-edited files may have stray blank lines; those
        # shouldn't generate warnings, just be ignored.
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="a"))
        t.close()

        jsonl_path = t.directory / "0001.events.jsonl"
        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write("\n\n")

        t2 = Transcript(project)
        t2.write(UserTurn(timestamp=_t(1), content="b"))
        t2.close()

        events = list(Transcript(project).current_events())
        assert [e.content for e in events] == ["a", "b"]


# ---------------------------------------------------------------------------
# Reconstruction (context_summary + anthropic_messages)
# ---------------------------------------------------------------------------


class TestContextSummary:
    def test_returns_none_when_empty(self, project):
        # Lets callers distinguish "fresh transcript, nothing to
        # inject" from "have context, inject this."
        t = Transcript(project)
        assert t.context_summary() is None

    def test_includes_intro_and_events(self, project):
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="ping"))
        t.write(AssistantText(timestamp=_t(1), content="pong"))
        t.close()
        ctx = t.context_summary()
        assert ctx is not None
        assert "prior conversation" in ctx  # intro paragraph
        assert "**User:** ping" in ctx
        assert "**Assistant:** pong" in ctx

    def test_renders_chronologically(self, project):
        t = Transcript(project)
        for i, label in enumerate(["first", "middle", "last"]):
            t.write(UserTurn(timestamp=_t(i), content=label))
        t.close()
        ctx = t.context_summary()
        assert ctx is not None
        assert ctx.index("first") < ctx.index("middle") < ctx.index("last")

    def test_only_current_chapter_included(self, project):
        # "Start new chapter" means clean slate — context summary
        # must not reach into prior chapters' content.  This is the
        # whole point of chapters.
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="from old chapter"))
        t.start_new_chapter()
        t.write(UserTurn(timestamp=_t(10), content="from new chapter"))
        t.close()
        ctx = t.context_summary()
        assert ctx is not None
        assert "from new chapter" in ctx
        assert "from old chapter" not in ctx

    def test_truncates_oldest_when_budget_exceeded(self, project):
        # Newest events take priority when the budget is tight.
        t = Transcript(project)
        for i in range(200):
            t.write(UserTurn(
                timestamp=_t(i), content=f"turn-{i}-" + "x" * 1000,
            ))
        t.close()
        ctx = t.context_summary()  # default 50K budget
        assert ctx is not None
        assert "[earlier turns omitted]" in ctx
        assert "turn-199" in ctx
        assert "turn-0-" not in ctx

    def test_respects_custom_max_chars(self, project):
        t = Transcript(project)
        for i in range(10):
            t.write(UserTurn(timestamp=_t(i), content=f"t{i}"))
        t.close()
        ctx = t.context_summary(max_chars=200)
        assert ctx is not None
        # Roughly bounded by budget plus small intro + truncation marker.
        assert len(ctx) < 500


class TestAnthropicMessages:
    def test_returns_empty_for_empty_transcript(self, project):
        assert Transcript(project).anthropic_messages() == []

    def test_user_turn_becomes_user_message(self, project):
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="hello"))
        t.close()
        assert t.anthropic_messages() == [
            {"role": "user", "content": "hello"},
        ]

    def test_mixed_assistant_blocks_preserved_in_order(self, project):
        # Text/tool_use interleaving from the SDK must round-trip
        # into a single assistant message with blocks in their
        # original order — that's what the API expects when this
        # message is fed back later.
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="check the file"))
        t.write(AssistantText(timestamp=_t(1), content="Let me check."))
        t.write(ToolUse(
            timestamp=_t(2), tool_use_id="toolu_1",
            name="Read", input={"file_path": "/x"},
        ))
        t.write(AssistantText(timestamp=_t(3), content="Based on that, X."))
        t.close()

        msgs = t.anthropic_messages()
        assert msgs == [
            {"role": "user", "content": "check the file"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me check."},
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "Read",
                        "input": {"file_path": "/x"},
                    },
                    {"type": "text", "text": "Based on that, X."},
                ],
            },
        ]

    def test_tool_result_creates_user_message_after_assistant(self, project):
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="x"))
        t.write(ToolUse(
            timestamp=_t(1), tool_use_id="toolu_1", name="Read", input={},
        ))
        t.write(ToolResult(
            timestamp=_t(2), tool_use_id="toolu_1", content="data",
        ))
        t.close()

        msgs = t.anthropic_messages()
        # The tool_use closes the assistant message; the tool_result
        # opens a new user message — exact shape Anthropic API expects.
        assert msgs[-1] == {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": "data",
                "is_error": False,
            }],
        }

    def test_metadata_events_skipped(self, project):
        # Header / boundary events are bookkeeping; they don't map
        # to API messages.  Including them would confuse the API.
        t = Transcript(project)
        t.write(ChapterStarted(
            timestamp=T0, project_dir=str(project), backend="X",
        ))
        t.write(SessionResume(timestamp=_t(1), backend="Y"))
        t.write(ProcessStarted(timestamp=_t(2), process_name="clarity-agent"))
        t.write(ModelOverride(timestamp=_t(3), tier="deep", model="opus"))
        t.write(UserTurn(timestamp=_t(4), content="hi"))
        t.close()
        assert t.anthropic_messages() == [
            {"role": "user", "content": "hi"},
        ]

    def test_legacy_tool_use_text_synthesizes_id(self, project):
        # Migrated legacy data has only name+detail.  We still emit
        # a tool_use block (model sees a tool was invoked) with a
        # clearly-marked legacy id and the detail under input.detail.
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="x"))
        t.write(AssistantText(timestamp=_t(1), content="ok"))
        t.write(ToolUseText(timestamp=_t(2), name="Bash", detail="ls -la"))
        t.close()

        msgs = t.anthropic_messages()
        blocks = msgs[1]["content"]
        assert blocks[0] == {"type": "text", "text": "ok"}
        assert blocks[1]["type"] == "tool_use"
        assert blocks[1]["name"] == "Bash"
        assert blocks[1]["id"].startswith("legacy_")
        assert blocks[1]["input"] == {"detail": "ls -la"}
