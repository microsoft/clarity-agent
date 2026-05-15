"""Tests for :class:`ClaritySession` writing structured events to a Transcript.

Stubs the chat backend so the tests don't depend on a real LLM,
then verifies that every observable thing (chapter open, user turn,
assistant turn, tool calls, process boundary) lands as the expected
event in the transcript's JSONL.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from clarity_agent.llm.chat import ChatBackend
from clarity_agent.llm.types import ToolUseBlock
from clarity_agent.session import ClaritySession
from clarity_agent.transcript import (
    AssistantText,
    ChapterStarted,
    ProcessStarted,
    SessionResume,
    ToolUse,
    Transcript,
    UserTurn,
)


class _StubBackend(ChatBackend):
    """Minimal ChatBackend stub.

    ``chat`` returns a pre-set response and fires ``on_tool_call`` /
    ``on_tool_use`` for each configured ToolUseBlock so we can
    verify ClaritySession's structured-callback handling without
    spinning up a real LLM.
    """

    supports_tools = True
    TIER_DEFAULTS = {"default": "stub-model"}

    def __init__(
        self,
        response: str = "ok",
        tool_calls: list[ToolUseBlock] | None = None,
    ) -> None:
        self._response = response
        self._tool_calls = tool_calls or []
        # ClaritySession sets ``on_tool_call`` in __init__ when given
        # a transcript; the chat() implementation below will then
        # fire it for each preconfigured ToolUseBlock.
        self.on_tool_use = None
        self.on_tool_call = None

    def chat(
        self,
        user_message: str,
        system_prompt: str | None = None,
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_handler: Any = None,
    ) -> str:
        # Fire the structured tool-call callback for each preconfigured
        # block — mirrors how the SDK backend fires it during streaming.
        for block in self._tool_calls:
            if self.on_tool_call is not None:
                self.on_tool_call(block)
        return self._response


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def stub_llm_config():
    """A minimal LLMConfig-shaped object that satisfies ClaritySession's needs."""
    class _StubConfig:
        provider = "stub"
        tiers = {"default": "stub-model", "deep": "stub-deep", "fast": "stub-fast"}
        def resolve(self, process_name: str) -> str:
            return "stub-model"
        def resolve_tier(self, process_name: str) -> str:
            return "default"
    return _StubConfig()


class TestChapterBootstrap:
    """The session's __init__ writes a header event so the chapter
    is never empty after the session attaches."""

    def test_first_session_writes_chapter_started(self, project, stub_llm_config):
        t = Transcript(project)
        backend = _StubBackend()
        # Construct ClaritySession; __init__ writes the header event.
        ClaritySession(project, project, backend, stub_llm_config, transcript=t)
        t.close()

        events = list(Transcript(project).current_events())
        assert len(events) == 1
        assert isinstance(events[0], ChapterStarted)
        assert events[0].project_dir == str(project)
        assert events[0].backend == "_StubBackend"

    def test_subsequent_session_writes_session_resume(self, project, stub_llm_config):
        # First session: ChapterStarted as the first event.
        t1 = Transcript(project)
        ClaritySession(project, project, _StubBackend(), stub_llm_config, transcript=t1)
        t1.close()

        # Second session on the same project: now the transcript is
        # non-empty, so we record a SessionResume boundary instead.
        t2 = Transcript(project)
        ClaritySession(project, project, _StubBackend(), stub_llm_config, transcript=t2)
        t2.close()

        events = list(Transcript(project).current_events())
        # First event is the original ChapterStarted; second is the
        # SessionResume from the new attach.
        assert isinstance(events[0], ChapterStarted)
        assert isinstance(events[1], SessionResume)
        assert events[1].backend == "_StubBackend"

    def test_no_transcript_means_no_header_write(self, project, stub_llm_config):
        # When no transcript is provided, ClaritySession is silent.
        # This is the ``--no-transcript`` path.
        t = Transcript(project)  # external, never passed to the session
        ClaritySession(project, project, _StubBackend(), stub_llm_config, transcript=None)
        # The standalone Transcript is unrelated to the session, so
        # it remains empty.
        assert t.is_empty


class TestChatRecordsTurns:
    def test_chat_records_user_and_assistant_turns(self, project, stub_llm_config):
        t = Transcript(project)
        with ClaritySession(
            project, project, _StubBackend(response="hello!"), stub_llm_config,
            transcript=t,
        ) as s:
            s.chat("hi")
        t.close()

        events = list(Transcript(project).current_events())
        # ChapterStarted, then UserTurn, then AssistantText.
        kinds = [type(e).__name__ for e in events]
        assert kinds == ["ChapterStarted", "UserTurn", "AssistantText"]
        assert events[1].content == "hi"
        assert events[2].content == "hello!"

    def test_tool_calls_landed_with_structured_input(self, project, stub_llm_config):
        # The structured callback path is what gives us round-trippable
        # tool fidelity — verify the input dict survives.
        backend = _StubBackend(
            tool_calls=[
                ToolUseBlock(
                    id="toolu_1",
                    name="Read",
                    input={"file_path": "/x/y.md", "limit": 50},
                ),
            ],
        )
        t = Transcript(project)
        with ClaritySession(project, project, backend, stub_llm_config, transcript=t) as s:
            s.chat("read it please")
        t.close()

        events = list(Transcript(project).current_events())
        tool_events = [e for e in events if isinstance(e, ToolUse)]
        assert len(tool_events) == 1
        assert tool_events[0].tool_use_id == "toolu_1"
        assert tool_events[0].name == "Read"
        assert tool_events[0].input == {"file_path": "/x/y.md", "limit": 50}

    def test_tool_call_event_falls_between_user_and_assistant(self, project, stub_llm_config):
        # The legacy ordering (User → tool events → Assistant) must
        # be preserved — that's how the rendered markdown reads, and
        # users will see the same layout as pre-#35.
        backend = _StubBackend(
            response="done",
            tool_calls=[ToolUseBlock(id="t1", name="Bash", input={"command": "ls"})],
        )
        t = Transcript(project)
        with ClaritySession(project, project, backend, stub_llm_config, transcript=t) as s:
            s.chat("list files")
        t.close()

        events = list(Transcript(project).current_events())
        kinds = [type(e).__name__ for e in events]
        # ChapterStarted, UserTurn, ToolUse, AssistantText.
        assert kinds == ["ChapterStarted", "UserTurn", "ToolUse", "AssistantText"]


class TestProcessBoundary:
    def test_run_custom_process_writes_process_started(
        self, project, stub_llm_config, monkeypatch,
    ):
        # ``run_custom_process`` does a lot — loads guides, runs the
        # interactive loop — most of which we don't want to exercise
        # here.  Monkey-patch out the parts beyond the boundary write.
        t = Transcript(project)
        with ClaritySession(
            project, project, _StubBackend(), stub_llm_config, transcript=t,
        ) as s:
            # Stub the heavy parts.
            monkeypatch.setattr(
                s, "load_process", lambda name: f"# Process {name}",
            )
            monkeypatch.setattr(s, "load_behaviors", lambda: "")
            monkeypatch.setattr(s, "get_packet_status_report", lambda: None)
            monkeypatch.setattr(s, "record_document_state", lambda: None)
            # Skip the interactive loop by raising EOF immediately on
            # input.  The first chat call still happens; we just want
            # to confirm the ProcessStarted event landed.
            monkeypatch.setattr(
                "clarity_agent.session._multiline_input",
                lambda *_args, **_kw: (_ for _ in ()).throw(EOFError()),
            )
            s.run_custom_process("clarity-agent")
        t.close()

        events = list(Transcript(project).current_events())
        process_events = [e for e in events if isinstance(e, ProcessStarted)]
        assert len(process_events) == 1
        assert process_events[0].process_name == "clarity-agent"

    def test_user_and_assistant_turns_are_recorded_for_process_kickoff(
        self, project, stub_llm_config, monkeypatch,
    ):
        # The initial "Let's run the X process" turn must be recorded
        # in the transcript along with the assistant's response.
        t = Transcript(project)
        with ClaritySession(
            project, project, _StubBackend(response="starting"),
            stub_llm_config, transcript=t,
        ) as s:
            monkeypatch.setattr(s, "load_process", lambda name: "")
            monkeypatch.setattr(s, "load_behaviors", lambda: "")
            monkeypatch.setattr(s, "get_packet_status_report", lambda: None)
            monkeypatch.setattr(s, "record_document_state", lambda: None)
            monkeypatch.setattr(
                "clarity_agent.session._multiline_input",
                lambda *_args, **_kw: (_ for _ in ()).throw(EOFError()),
            )
            s.run_custom_process("clarity-agent")
        t.close()

        events = list(Transcript(project).current_events())
        user_events = [e for e in events if isinstance(e, UserTurn)]
        assistant_events = [e for e in events if isinstance(e, AssistantText)]
        assert len(user_events) == 1
        assert "Let's run" in user_events[0].content
        assert len(assistant_events) == 1
        assert assistant_events[0].content == "starting"
