"""
Tests for :class:`WebSessionAdapter` context-restore behavior.

Verifies the three resume cases that matter for issue #35's Model B
("transcripts are the source of truth; SDK session is a derived
cache"):

1. **Fresh project**: no chapters, no SDK session → nothing to
   inject.  The first message starts a brand-new SDK conversation
   with no priming.

2. **Existing chapter, no SDK session**: prior conversation exists
   but the SDK session id was lost / never persisted → rebuild
   path.  ``Transcript.context_summary()`` produces a markdown blob
   that gets injected on the first chat call's system prompt.

3. **Existing chapter, valid SDK session id**: the SDK has the
   conversation already → skip context injection, let the SDK
   resume natively.

The :class:`WebSessionAdapter`'s ``start()`` is async, so these
tests use ``asyncio.run``.  A stub LLMConfig + ChatBackend keeps
the tests off the network.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from clarity_agent.llm.chat import ChatBackend
from clarity_agent.transcript import (
    AssistantText,
    Transcript,
    UserTurn,
)
from clarity_agent.web.session_manager import WebSessionAdapter


T0 = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


class _StubBackend(ChatBackend):
    """Minimal ChatBackend stub for resume-path testing."""

    supports_tools = True
    TIER_DEFAULTS = {"default": "stub-model", "deep": "stub-deep", "fast": "stub-fast"}

    def __init__(self) -> None:
        # ``_session_id`` mirrors the real backends' settable id.
        self._session_id: str | None = None

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
        return "ok"


class _StubLLMConfig:
    """Minimal :class:`LLMConfig`-shaped object the adapter needs."""

    provider = "stub"
    tiers = {"default": "stub-model", "deep": "stub-deep", "fast": "stub-fast"}

    def __init__(self) -> None:
        self.last_backend: _StubBackend | None = None

    def create_chat_backend(
        self,
        *,
        project_dir: Path,
        clarity_agent_dir: Path,
    ) -> _StubBackend:
        # Stash the backend so tests can interrogate it post-start.
        self.last_backend = _StubBackend()
        return self.last_backend

    def resolve(self, process_name: str) -> str:
        return "stub-model"

    def resolve_tier(self, process_name: str) -> str:
        return "default"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return tmp_path


def _start_adapter(
    project_dir: Path,
    *,
    llm_session_id: str | None = None,
) -> WebSessionAdapter:
    """Construct an adapter and run its async start() to completion."""
    cfg = _StubLLMConfig()
    adapter = WebSessionAdapter(
        project_dir, project_dir, cfg, llm_session_id=llm_session_id,
    )
    asyncio.run(adapter.start())
    return adapter


class TestResumeFreshProject:
    def test_no_chapters_no_session_injects_no_context(self, project):
        # Cold start on a brand-new project.  The transcript is empty
        # before start(), so the rebuild path mustn't fabricate
        # context — the user is genuinely starting from scratch.
        adapter = _start_adapter(project)
        assert adapter._transcript_context is None

    def test_first_chapter_created_by_start(self, project):
        # As a side-effect of ClaritySession's construction, chapter 1
        # exists after start().  The ChapterStarted event is its
        # first entry — but that doesn't count as "prior conversation"
        # for context-injection purposes.
        _start_adapter(project)
        t = Transcript(project)
        assert t.current_chapter == 1


class TestResumeExistingChapterNoSession:
    def test_existing_chapter_no_session_injects_context_summary(self, project):
        # Simulate "user chatted, then the SDK session was lost"
        # by writing some events to the transcript directly (no
        # session_state.json, no llm_session_id passed in).
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="earlier question"))
        t.write(AssistantText(timestamp=T0, content="earlier answer"))
        t.close()

        adapter = _start_adapter(project)
        assert adapter._transcript_context is not None
        # The blob carries the prior conversation through to the
        # first chat call — verify it captured the actual content.
        assert "earlier question" in adapter._transcript_context
        assert "earlier answer" in adapter._transcript_context

    def test_session_resume_event_appears_in_context(self, project):
        # ClaritySession.__init__ writes a SessionResume marker into
        # the current chapter when one already exists.  The context
        # summary should reflect this — gives the model a visible
        # boundary like "you came back the next day" inside the
        # injected blob.
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="hi"))
        t.close()

        adapter = _start_adapter(project)
        assert adapter._transcript_context is not None
        # ``SessionResume`` renders as a ``## YYYY-MM-DD — backend``
        # markdown sub-heading.
        assert "_StubBackend" in adapter._transcript_context


class TestResumeWithValidSdkSession:
    def test_session_id_skips_context_injection(self, project):
        # When an SDK session id is available, the SDK handles
        # conversation continuity natively — no need to inject
        # context.  Re-injecting would *also* feed the prior
        # conversation as raw text on top of the SDK's own memory,
        # which would confuse the model.
        t = Transcript(project)
        t.write(UserTurn(timestamp=T0, content="earlier question"))
        t.close()

        adapter = _start_adapter(project, llm_session_id="restored-session-abc")
        assert adapter._transcript_context is None

    def test_session_id_propagates_to_backend(self, project):
        cfg = _StubLLMConfig()
        adapter = WebSessionAdapter(
            project, project, cfg, llm_session_id="my-session",
        )
        asyncio.run(adapter.start())
        # The backend should have received the session id so its
        # next chat call resumes via ``resume=session_id``.
        assert cfg.last_backend is not None
        assert cfg.last_backend.llm_session_id == "my-session"
