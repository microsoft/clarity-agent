"""
End-to-end smoke tests for issue #35 Phase 1.

These exercise the **integrated** flow through ``WebSessionAdapter``
→ ``ClaritySession`` → ``Transcript`` → events on disk → reading
back.  They are deliberately not isolated unit tests of any single
component — that's what the other test files cover.  The goal here
is to catch regressions in the seams between components, especially:

- The async ``adapter.chat()`` boundary that runs ``backend.chat()``
  in a thread-pool executor and writes events back to the
  transcript from the worker thread.
- The cold-start → chat → close → reopen → continuation cycle that
  is the central correctness promise of issue #35 ("always
  continuing the prior conversation").
- The legacy-migration path firing automatically on first
  ``Transcript`` construction.
- The "Start new chapter" rollover ending one chapter cleanly and
  opening the next with a fresh SDK session.
- Structured tool-use events landing with their provider id +
  structured input dict intact through the executor thread.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from clarity_agent.llm.chat import ChatBackend
from clarity_agent.llm.types import ToolUseBlock
from clarity_agent.transcript import (
    AssistantText,
    ChapterStarted,
    SessionResume,
    ToolUse,
    Transcript,
    UserTurn,
)
from clarity_agent.web.session_manager import WebSessionAdapter
from clarity_agent.web.session_state import load_session_state


# ---------------------------------------------------------------------------
# Test stubs
# ---------------------------------------------------------------------------


class _SmokeBackend(ChatBackend):
    """Backend stub that simulates the SDK's session-id assignment.

    Real backends (e.g., :class:`SdkChatBackend`) capture the SDK's
    ``session_id`` from a ``ResultMessage`` after the first chat
    completes.  This stub mimics that behavior so smoke tests can
    verify the "persisted session id lets the next launch resume"
    flow without spinning up a real LLM.

    Optionally fires preconfigured tool calls during ``chat``, so
    tests can verify ToolUse events land correctly through the
    executor thread.
    """

    supports_tools = True
    TIER_DEFAULTS = {"default": "stub-model", "deep": "stub-deep", "fast": "stub-fast"}

    def __init__(
        self,
        response: str = "ok",
        session_id_to_set: str = "sdk-test-id",
        tool_calls: list[ToolUseBlock] | None = None,
    ) -> None:
        self._session_id: str | None = None
        self._response = response
        self._session_id_to_set = session_id_to_set
        self._tool_calls = tool_calls or []
        self.on_tool_use = None
        self.on_tool_call = None
        self.on_text_delta = None
        self.on_cost = None
        self.on_usage = None
        self.on_warning = None
        self.on_status = None

    @property
    def llm_session_id(self) -> str | None:
        return self._session_id

    @llm_session_id.setter
    def llm_session_id(self, value: str | None) -> None:
        self._session_id = value

    def chat(
        self,
        user_message: str,
        system_prompt: str | None = None,
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_handler: Any = None,
    ) -> str:
        # Fire tool callbacks for preconfigured tool calls — mirrors
        # how real backends call on_tool_call from inside chat().
        for block in self._tool_calls:
            if self.on_tool_call is not None:
                self.on_tool_call(block)
            if self.on_tool_use is not None:
                self.on_tool_use(block.name, str(block.input))
        # Simulate SDK assigning a session id on the first call.
        if self._session_id is None:
            self._session_id = self._session_id_to_set
        return self._response


class _SmokeLLMConfig:
    """Minimal :class:`LLMConfig`-shaped stub."""

    provider = "stub"
    tiers = {"default": "stub-model", "deep": "stub-deep", "fast": "stub-fast"}

    def __init__(self, backend_factory=None) -> None:
        # Allow tests to substitute their own backend (e.g., one with
        # preconfigured tool calls) without redefining the whole
        # config class each time.
        self._backend_factory = backend_factory or (lambda: _SmokeBackend())
        self.last_backend: _SmokeBackend | None = None

    def create_chat_backend(
        self, *, project_dir: Path, clarity_agent_dir: Path,
    ) -> _SmokeBackend:
        self.last_backend = self._backend_factory()
        return self.last_backend

    def resolve(self, process_name: str) -> str:
        return "stub-model"

    def resolve_tier(self, process_name: str) -> str:
        return "default"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return tmp_path


def _run(coro):
    """Run an async coroutine to completion — pytest-anyio shorthand."""
    return asyncio.run(coro)


def _full_lifecycle(adapter: WebSessionAdapter, *messages: str) -> list[str]:
    """Start an adapter, send each message in order, return responses.

    Used by smoke tests that need to drive a full conversation
    without writing the boilerplate inline.  The adapter is left
    open after — callers close it (or just discard) when done.
    """
    async def go() -> list[str]:
        await adapter.start()
        responses = []
        for m in messages:
            responses.append(await adapter.chat(m))
        return responses
    return _run(go())


# ---------------------------------------------------------------------------
# Cold start → chat → close → reopen → continuation
# ---------------------------------------------------------------------------


class TestColdStartChatReopen:
    """The central correctness promise: opening a project always
    continues the prior conversation."""

    def test_chat_persists_to_disk(self, project):
        # First adapter: send one message, then drop.
        cfg = _SmokeLLMConfig()
        adapter = WebSessionAdapter(project, project, cfg)
        _full_lifecycle(adapter, "hello world")

        # Open a fresh Transcript on the same project — disk-level
        # source of truth, not going through the adapter.
        events = list(Transcript(project).current_events())
        kinds = [type(e).__name__ for e in events]
        # ChapterStarted (from adapter.start()) + UserTurn + AssistantText.
        assert kinds == ["ChapterStarted", "UserTurn", "AssistantText"]
        assert events[1].content == "hello world"
        assert events[2].content == "ok"

    def test_reopening_resumes_via_persisted_sdk_session(self, project):
        # First adapter chats, captures an SDK session id, and
        # persists it.  Second adapter constructed on the same
        # project should pick up that id from session_state.json
        # and skip the context-restore injection entirely.
        cfg1 = _SmokeLLMConfig()
        adapter1 = WebSessionAdapter(project, project, cfg1)
        _full_lifecycle(adapter1, "first")

        # Verify the SDK session id was persisted.
        persisted = load_session_state(project)
        assert persisted == "sdk-test-id"

        # Second adapter: no llm_session_id passed in, but the
        # session_state.json should be picked up automatically.
        cfg2 = _SmokeLLMConfig()
        adapter2 = WebSessionAdapter(project, project, cfg2)
        _run(adapter2.start())

        # Backend got the persisted id propagated to it.
        assert cfg2.last_backend is not None
        assert cfg2.last_backend.llm_session_id == "sdk-test-id"
        # And no context-restore blob was loaded (SDK resume covers it).
        assert adapter2._transcript_context is None

    def test_session_resume_event_recorded_on_reopen(self, project):
        # Each cold reopen on an existing project writes a
        # SessionResume marker into the current chapter — gives the
        # markdown a visible "you came back" boundary without
        # ending the chapter.
        _full_lifecycle(
            WebSessionAdapter(project, project, _SmokeLLMConfig()),
            "first",
        )
        _full_lifecycle(
            WebSessionAdapter(project, project, _SmokeLLMConfig()),
            "second",
        )

        events = list(Transcript(project).current_events())
        # One ChapterStarted (first adapter), one SessionResume (second).
        chapter_starteds = [e for e in events if isinstance(e, ChapterStarted)]
        session_resumes = [e for e in events if isinstance(e, SessionResume)]
        assert len(chapter_starteds) == 1
        assert len(session_resumes) == 1
        # Both user turns survived.
        user_turns = [e for e in events if isinstance(e, UserTurn)]
        assert [t.content for t in user_turns] == ["first", "second"]


# ---------------------------------------------------------------------------
# Legacy migration end-to-end
# ---------------------------------------------------------------------------


class TestLegacyMigrationFlow:
    """Project arrives with pre-#35 timestamp-named transcripts.
    First adapter construction triggers migration; the next chat
    continues coherently in chapter 1."""

    def test_legacy_files_fold_into_chapter_one_on_first_adapter_start(self, project):
        # Drop a legacy transcript onto disk before any adapter
        # exists — simulates upgrading the app on a project that
        # has pre-#35 conversation history.
        d = Transcript(project).directory
        d.mkdir(parents=True, exist_ok=True)
        (d / "20260412-100000.md").write_text(
            "# Transcript\n\n"
            "**Date:** 2026-04-12T10:00:00\n"
            "**Project:** /Users/test/proj\n"
            "**Backend:** SdkChatBackend\n\n"
            "---\n\n"
            "**User:** legacy question\n\n"
            "**Assistant:** legacy answer\n\n"
            "---\n\n",
        )

        # First adapter on the upgraded code: construction triggers
        # migration; chat adds to chapter 1.
        adapter = WebSessionAdapter(project, project, _SmokeLLMConfig())
        _full_lifecycle(adapter, "follow up")

        events = list(Transcript(project).current_events())
        contents = [
            (type(e).__name__, getattr(e, "content", None))
            for e in events
        ]
        # Legacy content + adapter's SessionResume marker + new turn.
        assert ("UserTurn", "legacy question") in contents
        assert ("AssistantText", "legacy answer") in contents
        assert ("UserTurn", "follow up") in contents
        assert ("AssistantText", "ok") in contents
        # Legacy file deleted; the merged chapter is now the source of truth.
        assert not (d / "20260412-100000.md").exists()

    def test_legacy_migration_triggers_context_restore_on_first_chat(self, project):
        # After migration, the chapter is non-empty.  When the new
        # adapter has no SDK session yet (which it doesn't — this
        # is the first adapter on the upgraded code), the
        # context-restore path should inject the migrated content
        # as the first message's system prompt.
        d = Transcript(project).directory
        d.mkdir(parents=True, exist_ok=True)
        (d / "20260412-100000.md").write_text(
            "# Transcript\n\n"
            "**Date:** 2026-04-12T10:00:00\n"
            "**Backend:** SdkChatBackend\n\n"
            "---\n\n"
            "**User:** earlier work\n\n"
            "**Assistant:** earlier result\n\n"
            "---\n\n",
        )

        adapter = WebSessionAdapter(project, project, _SmokeLLMConfig())
        _run(adapter.start())

        # Context-restore blob populated from the migrated chapter.
        assert adapter._transcript_context is not None
        assert "earlier work" in adapter._transcript_context
        assert "earlier result" in adapter._transcript_context


# ---------------------------------------------------------------------------
# Start new chapter mid-conversation
# ---------------------------------------------------------------------------


class TestStartNewChapterFlow:
    """The user clicks "Start new chapter" after some conversation
    in chapter 1.  Subsequent chats land in chapter 2; chapter 1
    archives cleanly with its prior content intact."""

    def test_rollover_isolates_chapters(self, project):
        cfg = _SmokeLLMConfig()
        adapter = WebSessionAdapter(project, project, cfg)

        # All async work runs inside a single asyncio.run() — the
        # adapter captures the running event loop in start() and
        # uses it for run_in_executor; constructing a new loop
        # between chat() calls would orphan the executor.
        async def lifecycle() -> None:
            await adapter.start()
            await adapter.chat("ch1 message")
            adapter.start_new_chapter()
            await adapter.chat("ch2 message")
        _run(lifecycle())

        t = Transcript(project)
        ch1 = list(t.chapter_events(1))
        ch2 = list(t.chapter_events(2))

        # Chapter 1 contains the first turn; chapter 2 contains the second.
        assert any(
            isinstance(e, UserTurn) and e.content == "ch1 message" for e in ch1
        )
        assert any(
            isinstance(e, UserTurn) and e.content == "ch2 message" for e in ch2
        )
        # Cross-contamination check: neither turn leaks into the
        # other chapter.
        assert not any(
            isinstance(e, UserTurn) and e.content == "ch2 message" for e in ch1
        )
        assert not any(
            isinstance(e, UserTurn) and e.content == "ch1 message" for e in ch2
        )

    def test_rollover_resets_sdk_session(self, project):
        # The whole point of "New chapter" is a fresh SDK
        # conversation.  Verify the backend acquires a NEW session
        # id after rollover rather than carrying the old one over.
        cfg = _SmokeLLMConfig()
        adapter = WebSessionAdapter(project, project, cfg)

        recorded: dict[str, Any] = {}

        async def lifecycle() -> None:
            await adapter.start()
            await adapter.chat("ch1 message")
            # Backend captured the first session id.
            assert cfg.last_backend is not None
            recorded["first"] = cfg.last_backend.llm_session_id

            adapter.start_new_chapter()
            # SDK session id was cleared.
            assert cfg.last_backend.llm_session_id is None

            await adapter.chat("ch2 message")
            recorded["second"] = cfg.last_backend.llm_session_id
        _run(lifecycle())

        # Backend captured a session id on each chapter; the rollover
        # cleared it in between (verified inside the lifecycle).
        assert recorded["first"] is not None
        assert recorded["second"] is not None
        # Persisted state reflects whatever the second chapter saved.
        assert load_session_state(project) == recorded["second"]


# ---------------------------------------------------------------------------
# Tool-use fidelity through the executor thread
# ---------------------------------------------------------------------------


class TestToolUseFidelity:
    """The structured ToolUse event with provider id + input dict
    must land correctly in the transcript even though tool callbacks
    fire from the executor thread, not the event loop thread."""

    def test_tool_call_during_chat_lands_with_structured_input(self, project):
        # Configure the backend to fire one tool call during chat().
        # The transcript layer must capture it as a structured
        # ``ToolUse`` event with the original id and input dict.
        tool_block = ToolUseBlock(
            id="toolu_smoke_1",
            name="Read",
            input={"file_path": "/x/y.md", "limit": 100},
        )
        cfg = _SmokeLLMConfig(
            backend_factory=lambda: _SmokeBackend(tool_calls=[tool_block]),
        )
        adapter = WebSessionAdapter(project, project, cfg)
        _full_lifecycle(adapter, "please read the file")

        events = list(Transcript(project).current_events())
        tool_events = [e for e in events if isinstance(e, ToolUse)]
        assert len(tool_events) == 1
        assert tool_events[0].tool_use_id == "toolu_smoke_1"
        assert tool_events[0].name == "Read"
        assert tool_events[0].input == {"file_path": "/x/y.md", "limit": 100}

    def test_tool_event_falls_between_user_and_assistant(self, project):
        # Legacy ordering: User → tool events → Assistant.  Must be
        # preserved through the executor + transcript writer so the
        # rendered markdown looks the way users are used to.
        tool_block = ToolUseBlock(
            id="t1", name="Bash", input={"command": "ls"},
        )
        cfg = _SmokeLLMConfig(
            backend_factory=lambda: _SmokeBackend(tool_calls=[tool_block]),
        )
        adapter = WebSessionAdapter(project, project, cfg)
        _full_lifecycle(adapter, "list files")

        events = list(Transcript(project).current_events())
        kinds = [type(e).__name__ for e in events]
        # ChapterStarted, UserTurn, ToolUse, AssistantText.
        assert kinds == ["ChapterStarted", "UserTurn", "ToolUse", "AssistantText"]


# ---------------------------------------------------------------------------
# Markdown sidecar stays in sync with the JSONL
# ---------------------------------------------------------------------------


class TestMarkdownSidecar:
    """The ``.md`` sidecar is written synchronously alongside the
    JSONL.  After a full session lifecycle, both files should agree
    on the events that landed."""

    def test_md_contains_rendered_content(self, project):
        adapter = WebSessionAdapter(project, project, _SmokeLLMConfig())
        _full_lifecycle(adapter, "hi there")

        md_path = Transcript(project).chapter_md_path(1)
        md = md_path.read_text(encoding="utf-8")
        # Both the legacy-style speaker prefixes appear in the
        # rendered markdown.
        assert "**User:** hi there" in md
        assert "**Assistant:** ok" in md
        # Chapter header rendered at top.
        assert "# Chapter" in md
