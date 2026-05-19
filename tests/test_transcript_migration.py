"""
Tests for the one-time legacy-transcript migration.

The migration parses pre-#35 ``{username-}{timestamp}.md`` files
back into structured events and folds them into chapter ``0001``,
then deletes the originals.  These tests exercise the parser on
representative legacy-format fixtures (single file, multiple files,
process boundaries, model overrides, tool lines) and the
idempotence + safety properties of the public entry point.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clarity_agent.transcript import (
    AssistantText,
    ChapterStarted,
    ModelOverride,
    ProcessStarted,
    SessionResume,
    Transcript,
    UserTurn,
    migrate_legacy_transcripts,
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return tmp_path


def _transcripts_dir(project: Path) -> Path:
    """Materialize the transcripts directory and return its path.

    Tests place legacy fixture files here before calling
    :func:`migrate_legacy_transcripts`.
    """
    # ``Transcript.directory`` resolves the correct protocol-dir
    # variant for the project (``.clarity-protocol/`` vs
    # ``Clarity Protocol/``); use it so tests don't hardcode either.
    d = Transcript(project).directory
    d.mkdir(parents=True, exist_ok=True)
    return d


def _legacy_transcript(
    date_iso: str = "2026-04-12T10:00:00",
    backend: str = "SdkChatBackend",
    body: str = "",
) -> str:
    """Render a legacy transcript file with the given header + body.

    Plain concatenation (no dedent) — multi-line body content has
    its own newlines and would defeat ``textwrap.dedent``'s
    common-prefix logic.
    """
    return (
        "# Transcript\n\n"
        f"**Date:** {date_iso}\n"
        "**Project:** /Users/test/proj\n"
        f"**Backend:** {backend}\n\n"
        "---\n\n"
        f"{body}"
    )


# ---------------------------------------------------------------------------
# No-op cases
# ---------------------------------------------------------------------------


class TestNoOp:
    def test_returns_false_when_no_transcripts_dir(self, project):
        # Brand-new project — never had any conversation.
        assert migrate_legacy_transcripts(project) is False
        # And no chapter was created.
        assert Transcript(project).is_empty

    def test_returns_false_when_no_legacy_files(self, project):
        _transcripts_dir(project)
        # An empty transcripts/ directory (nothing to migrate).
        assert migrate_legacy_transcripts(project) is False

    def test_returns_false_when_chapter_already_exists(self, project):
        # Chapter 1 already in place — either a previous migration
        # ran, or the user started fresh on the new code.  Either
        # way, no migration should fire (would overwrite!).
        t = Transcript(project)
        t.write(UserTurn(
            timestamp=__import__("datetime").datetime.now(
                tz=__import__("datetime").timezone.utc,
            ),
            content="hi",
        ))
        t.close()
        # Drop a legacy file alongside the chapter — migration must
        # still skip because chapter 1 exists.
        d = _transcripts_dir(project)
        (d / "2026-04-12T10-00-00.md").write_text(_legacy_transcript())

        assert migrate_legacy_transcripts(project) is False
        # Chapter 1 untouched.
        events = list(Transcript(project).current_events())
        assert any(
            isinstance(e, UserTurn) and e.content == "hi" for e in events
        )
        # Legacy file NOT deleted (we didn't migrate it).
        assert (d / "2026-04-12T10-00-00.md").exists()

    def test_idempotent(self, project):
        # Run twice — second call must be a no-op (chapter 1 exists
        # after first call).
        d = _transcripts_dir(project)
        (d / "20260412-100000.md").write_text(_legacy_transcript(
            body="**User:** q\n\n**Assistant:** a\n\n---\n\n",
        ))
        assert migrate_legacy_transcripts(project) is True
        assert migrate_legacy_transcripts(project) is False


# ---------------------------------------------------------------------------
# Single legacy file
# ---------------------------------------------------------------------------


class TestSingleFile:
    def test_chapter_started_event_from_header(self, project):
        d = _transcripts_dir(project)
        (d / "20260412-100000.md").write_text(_legacy_transcript(
            date_iso="2026-04-12T10:00:00",
            backend="SdkChatBackend",
            body="**User:** hi\n\n**Assistant:** hello\n\n---\n\n",
        ))
        migrate_legacy_transcripts(project)

        events = list(Transcript(project).current_events())
        assert isinstance(events[0], ChapterStarted)
        # Date parsed from header (naive timestamp → UTC).
        assert events[0].timestamp.isoformat() == "2026-04-12T10:00:00+00:00"
        assert events[0].backend == "SdkChatBackend"

    def test_user_and_assistant_turns_parsed(self, project):
        d = _transcripts_dir(project)
        body = (
            "**User:** What is X?\n\n"
            "**Assistant:** X is Y.\n\n"
            "---\n\n"
            "**User:** And Z?\n\n"
            "**Assistant:** Z is W.\n\n"
            "---\n\n"
        )
        (d / "20260412-100000.md").write_text(_legacy_transcript(body=body))
        migrate_legacy_transcripts(project)

        events = list(Transcript(project).current_events())
        kinds = [type(e).__name__ for e in events]
        # Header + two turn pairs.
        assert kinds == [
            "ChapterStarted",
            "UserTurn", "AssistantText",
            "UserTurn", "AssistantText",
        ]
        assert events[1].content == "What is X?"
        assert events[2].content == "X is Y."
        assert events[3].content == "And Z?"
        assert events[4].content == "Z is W."

    def test_tool_lines_become_tool_use_text(self, project):
        # Legacy format puts inline ``[Tool]`` lines between the
        # user message and the assistant response.  These become
        # :class:`ToolUseText` events (no structured input — the
        # legacy format flattened it).
        d = _transcripts_dir(project)
        body = (
            "**User:** read the file\n\n"
            "    [Tool] Read -> /path/to/x.md\n"
            "    [Tool] Bash -> ls -la\n"
            "**Assistant:** done\n\n"
            "---\n\n"
        )
        (d / "20260412-100000.md").write_text(_legacy_transcript(body=body))
        migrate_legacy_transcripts(project)

        events = list(Transcript(project).current_events())
        kinds = [type(e).__name__ for e in events]
        # Header, user, two tool-text, assistant.
        assert kinds == [
            "ChapterStarted",
            "UserTurn",
            "ToolUseText",
            "ToolUseText",
            "AssistantText",
        ]
        assert events[2].name == "Read"
        assert events[2].detail == "/path/to/x.md"
        assert events[3].name == "Bash"
        assert events[3].detail == "ls -la"

    def test_process_heading_becomes_process_started(self, project):
        d = _transcripts_dir(project)
        body = (
            "## Process: clarity-agent\n\n"
            "**User:** start\n\n"
            "**Assistant:** ok\n\n"
            "---\n\n"
        )
        (d / "20260412-100000.md").write_text(_legacy_transcript(body=body))
        migrate_legacy_transcripts(project)

        events = list(Transcript(project).current_events())
        process_events = [e for e in events if isinstance(e, ProcessStarted)]
        assert len(process_events) == 1
        assert process_events[0].process_name == "clarity-agent"

    def test_model_override_recorded(self, project):
        d = _transcripts_dir(project)
        body = (
            "## Process: failure-brainstorming\n\n"
            "**Model override:** claude-opus-4-7 (tier: deep)\n\n"
            "**User:** go\n\n"
            "**Assistant:** ok\n\n"
            "---\n\n"
        )
        (d / "20260412-100000.md").write_text(_legacy_transcript(body=body))
        migrate_legacy_transcripts(project)

        events = list(Transcript(project).current_events())
        overrides = [e for e in events if isinstance(e, ModelOverride)]
        assert len(overrides) == 1
        assert overrides[0].model == "claude-opus-4-7"
        assert overrides[0].tier == "deep"

    def test_legacy_file_deleted_after_migration(self, project):
        d = _transcripts_dir(project)
        legacy_path = d / "20260412-100000.md"
        legacy_path.write_text(_legacy_transcript(
            body="**User:** q\n\n**Assistant:** a\n\n---\n\n",
        ))
        migrate_legacy_transcripts(project)
        assert not legacy_path.exists()

    def test_multiline_user_message_preserved(self, project):
        # User-pasted multi-line messages embed newlines in the
        # legacy file.  These must round-trip through the parser.
        d = _transcripts_dir(project)
        body = (
            "**User:** line one\n"
            "line two\n"
            "line three\n\n"
            "**Assistant:** ok\n\n"
            "---\n\n"
        )
        (d / "20260412-100000.md").write_text(_legacy_transcript(body=body))
        migrate_legacy_transcripts(project)

        events = list(Transcript(project).current_events())
        user = next(e for e in events if isinstance(e, UserTurn))
        assert user.content == "line one\nline two\nline three"


# ---------------------------------------------------------------------------
# Multiple legacy files
# ---------------------------------------------------------------------------


class TestMultipleFiles:
    def test_chronological_order_by_header_date(self, project):
        # The first file's header → ChapterStarted; subsequent files
        # → SessionResume.  Order is determined by parsed Date, not
        # filename (legacy filenames mixed schemes; date is reliable).
        d = _transcripts_dir(project)
        (d / "alice-20260415-110000.md").write_text(_legacy_transcript(
            date_iso="2026-04-15T11:00:00",
            backend="SdkChatBackend",
            body="**User:** later\n\n**Assistant:** later-resp\n\n---\n\n",
        ))
        (d / "20260412-100000.md").write_text(_legacy_transcript(
            date_iso="2026-04-12T10:00:00",
            backend="ClientChatBackend",
            body="**User:** earlier\n\n**Assistant:** earlier-resp\n\n---\n\n",
        ))
        migrate_legacy_transcripts(project)

        events = list(Transcript(project).current_events())
        # First content event is from the EARLIER file's header
        # → ChapterStarted with the older date.
        assert isinstance(events[0], ChapterStarted)
        assert events[0].backend == "ClientChatBackend"  # earlier file
        # Find the SessionResume — should be the LATER file's
        # header and come after the earlier file's turns.
        resumes = [e for e in events if isinstance(e, SessionResume)]
        assert len(resumes) == 1
        assert resumes[0].backend == "SdkChatBackend"
        # User turns appear in chronological order.
        user_turns = [e for e in events if isinstance(e, UserTurn)]
        assert [t.content for t in user_turns] == ["earlier", "later"]
        # And both legacy files are gone.
        assert not (d / "20260412-100000.md").exists()
        assert not (d / "alice-20260415-110000.md").exists()

    def test_session_resume_between_files(self, project):
        # The marker between two files is a SessionResume event,
        # rendering as a date sub-heading in the markdown.
        d = _transcripts_dir(project)
        (d / "20260412-100000.md").write_text(_legacy_transcript(
            date_iso="2026-04-12T10:00:00",
            body="**User:** a\n\n**Assistant:** b\n\n---\n\n",
        ))
        (d / "20260413-120000.md").write_text(_legacy_transcript(
            date_iso="2026-04-13T12:00:00",
            body="**User:** c\n\n**Assistant:** d\n\n---\n\n",
        ))
        migrate_legacy_transcripts(project)

        events = list(Transcript(project).current_events())
        # The boundary is a SessionResume between the two files' turns.
        resume_index = next(
            i for i, e in enumerate(events) if isinstance(e, SessionResume)
        )
        # Events before the resume are from the first file; after,
        # from the second.
        before = events[:resume_index]
        after = events[resume_index + 1:]
        assert any(
            isinstance(e, AssistantText) and e.content == "b" for e in before
        )
        assert any(
            isinstance(e, UserTurn) and e.content == "c" for e in after
        )


# ---------------------------------------------------------------------------
# Coexistence with new-format files
# ---------------------------------------------------------------------------


class TestChapterFileIsolation:
    def test_legacy_files_dont_collide_with_chapter_files(self, project):
        # A directory containing both legacy AND new-format files
        # (only happens during a partial migration crash or
        # hand-editing).  Migration must skip new-format files —
        # they're already authoritative content.
        d = _transcripts_dir(project)
        # Pre-existing chapter file (counts as a chapter).
        (d / "0001.events.jsonl").write_text(
            '{"schema_version":"1","type":"chapter_started",'
            '"timestamp":"2026-04-12T10:00:00+00:00",'
            '"project_dir":"/","backend":"X"}\n',
        )
        (d / "0001.md").write_text("# Chapter\n")
        # Legacy file alongside.
        (d / "20260412-100000.md").write_text(_legacy_transcript(
            body="**User:** legacy\n\n**Assistant:** stuff\n\n---\n\n",
        ))

        # Chapter 1 already exists; migration must skip everything.
        assert migrate_legacy_transcripts(project) is False
        assert (d / "20260412-100000.md").exists()  # untouched
