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
from datetime import UTC, datetime
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

T0 = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


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
        transcript: object = None,
    ) -> _StubBackend:
        # Stash the backend so tests can interrogate it post-start.
        self.last_backend = _StubBackend()
        self.last_backend._transcript = transcript
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


class TestStartNewChapter:
    """``WebSessionAdapter.start_new_chapter`` is the persistence
    primitive behind the "Start new chapter" UI button (#27).
    Verifies the rollover side-effects: new chapter number, archived
    old chapter, cleared SDK session, dropped context-restore blob."""

    def test_rolls_over_to_next_chapter(self, project):
        # Start a session and put some content into chapter 1 (the
        # adapter's start() writes a ChapterStarted as the first
        # event).  Then roll over.
        adapter = _start_adapter(project)
        # Sanity: chapter 1 exists with at least the header event.
        from clarity_agent.transcript import Transcript
        assert Transcript(project).current_chapter == 1

        new_chapter = adapter.start_new_chapter()

        assert new_chapter == 2
        assert Transcript(project).current_chapter == 2

    def test_new_chapter_seeded_with_chapter_started(self, project):
        # Every chapter (new or freshly-attached) must start with a
        # header event.  start_new_chapter writes it directly so the
        # new chapter is never "empty" from a consumer's perspective.
        from clarity_agent.transcript import ChapterStarted, Transcript
        adapter = _start_adapter(project)
        adapter.start_new_chapter()

        events = list(Transcript(project).current_events())
        assert isinstance(events[0], ChapterStarted)
        # Backend name reflects the test stub class.
        assert events[0].backend == "_StubBackend"

    def test_clears_backend_sdk_session(self, project):
        # The whole point of "Start new chapter" is a fresh
        # conversation — the backend's SDK session id must be
        # cleared so the next chat doesn't resume the archived
        # conversation.
        adapter = _start_adapter(project, llm_session_id="old-session")
        assert adapter.llm_session_id == "old-session"

        adapter.start_new_chapter()
        assert adapter.llm_session_id is None

    def test_clears_persisted_session_state_file(self, project):
        # The on-disk session_state.json file must also be wiped —
        # otherwise the next time the project loads it would
        # resume the now-archived SDK conversation.
        from clarity_agent.web.session_state import (
            load_session_state,
            save_session_state,
        )
        save_session_state(project, "persisted-session")
        assert load_session_state(project) == "persisted-session"

        adapter = _start_adapter(project, llm_session_id="persisted-session")
        adapter.start_new_chapter()
        assert load_session_state(project) is None

    def test_drops_pending_context_restore(self, project):
        # When start() loads a context-restore blob (existing
        # transcript, no SDK session), and the user then clicks
        # "Start new chapter" before sending any message, the
        # buffered context must be discarded — injecting it into
        # the brand-new chapter's first message would defeat the
        # whole purpose of starting fresh.
        from datetime import datetime

        from clarity_agent.transcript import Transcript, UserTurn

        # Seed the transcript with prior content so start() loads
        # a context blob.
        t = Transcript(project)
        t.write(UserTurn(
            timestamp=datetime.now(tz=UTC), content="prior turn",
        ))
        t.close()

        adapter = _start_adapter(project)
        assert adapter._transcript_context is not None

        adapter.start_new_chapter()
        assert adapter._transcript_context is None

    def test_archived_chapter_remains_readable(self, project):
        # The old chapter doesn't get deleted — it's archived,
        # browsable via History.  Verify chapter 1 still exists
        # after rolling over to chapter 2.
        from datetime import datetime

        from clarity_agent.transcript import Transcript, UserTurn

        adapter = _start_adapter(project)
        # Add a recognizable event to chapter 1.
        adapter._project_transcript.write(UserTurn(
            timestamp=datetime.now(tz=UTC), content="in chapter 1",
        ))

        adapter.start_new_chapter()

        # Chapter 1 still has the seeded event.
        ch1_events = list(Transcript(project).chapter_events(1))
        assert any(
            isinstance(e, UserTurn) and e.content == "in chapter 1"
            for e in ch1_events
        )


class TestStartTransactional:
    """``start()`` rolls back partial state on failure.

    Regression coverage for the PR #49 reviewer concern: if
    ``start()`` raises *after* the backend has been connected (e.g.
    Copilot's daemon thread has been spawned), the half-initialized
    backend must not leak — otherwise the WS handler that catches
    the error and keeps the socket open accumulates a thread per
    failed attempt.  ``start`` is contract-bound to be transactional:
    succeed cleanly or roll back to the pre-start state.
    """

    def test_rollback_disconnects_backend_when_post_connect_step_fails(
        self, project, monkeypatch,
    ):
        # Make a step *after* ``backend.connect()`` fail — pick
        # ``ClaritySession.__init__`` since it runs after connect
        # and is easy to monkeypatch.  The stub backend records
        # whether disconnect was called, which is the leak we're
        # guarding against.
        cfg = _StubLLMConfig()
        adapter = WebSessionAdapter(project, project, cfg)

        disconnect_calls: list[None] = []

        def _track_disconnect(self: _StubBackend) -> None:
            disconnect_calls.append(None)

        monkeypatch.setattr(_StubBackend, "disconnect", _track_disconnect, raising=False)
        monkeypatch.setattr(
            "clarity_agent.web.session_manager.ClaritySession.__init__",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        with pytest.raises(RuntimeError, match="boom"):
            asyncio.run(adapter.start())

        # Backend was connected (factory returned it, ``start`` stored
        # it) — the rollback must have called disconnect.
        assert disconnect_calls == [None]
        # Adapter is back to its pre-start state — no stale backend
        # reference that a re-check could mistake for a live session.
        assert adapter._backend is None
        assert adapter._session is None

    def test_rollback_when_connect_itself_raises(self, project, monkeypatch):
        # ``connect()`` raising is the SDK / Copilot scenario where the
        # CLI is missing.  The backend was assigned to ``self._backend``
        # *before* connect was called (so the rollback has something
        # to find), but disconnect must still be safe to call on a
        # backend whose connect failed.  Verify the rollback runs
        # without itself raising — the real disconnect implementations
        # are already guarded to no-op on a never-connected backend.
        cfg = _StubLLMConfig()
        adapter = WebSessionAdapter(project, project, cfg)

        disconnect_calls: list[None] = []

        def _failing_connect(self: _StubBackend) -> None:
            raise RuntimeError("CLI not installed")

        def _track_disconnect(self: _StubBackend) -> None:
            disconnect_calls.append(None)

        monkeypatch.setattr(_StubBackend, "connect", _failing_connect, raising=False)
        monkeypatch.setattr(_StubBackend, "disconnect", _track_disconnect, raising=False)

        with pytest.raises(RuntimeError, match="CLI not installed"):
            asyncio.run(adapter.start())

        # The backend was stashed pre-connect, so rollback can find
        # and disconnect it.  Without the pre-connect assignment the
        # backend would leak.
        assert disconnect_calls == [None]
        assert adapter._backend is None

    def test_rollback_when_factory_itself_raises_does_not_call_disconnect(
        self, project, monkeypatch,
    ):
        # Failure in ``create_chat_backend`` itself (the most common
        # #47 case — gh CLI missing) happens before any backend has
        # been built, so there's nothing to disconnect.  Verify the
        # rollback handles this case without trying to call disconnect
        # on ``None``.
        cfg = _StubLLMConfig()
        adapter = WebSessionAdapter(project, project, cfg)

        def _failing_factory(self: _StubLLMConfig, **kw: object) -> _StubBackend:
            raise RuntimeError("gh not installed")

        monkeypatch.setattr(
            _StubLLMConfig, "create_chat_backend", _failing_factory,
        )

        with pytest.raises(RuntimeError, match="gh not installed"):
            asyncio.run(adapter.start())

        # No backend ever existed, so nothing to clean up.  The
        # rollback should have left ``_backend`` as ``None`` without
        # raising a NoneType.disconnect AttributeError.
        assert adapter._backend is None


class TestCompactionBridge:
    """Adapter forwards backend compaction callbacks to the WebSocket
    event queue.  The decision to compact and the transcript
    mechanics now live in the backend
    (:meth:`ChatBackend.maybe_compact_after_chat`); the adapter's job
    is purely to surface ``compaction_started`` / ``compaction_complete``
    to the UI.  See ``test_client_chat_backend_compaction.py`` for
    the decision-and-mechanics tests.
    """

    def test_started_callback_emits_status_event(self, project):
        # When the backend fires on_compaction_started, the adapter
        # should queue a "Summarizing earlier conversation" status
        # event for the WebSocket drain loop to pick up.
        cfg = _StubLLMConfig()
        adapter = WebSessionAdapter(project, project, cfg)

        async def lifecycle() -> dict:
            await adapter.start()
            # call_soon_threadsafe defers to the loop; await a tick
            # so it runs before we drain.
            adapter._on_compaction_started()
            await asyncio.sleep(0)
            return adapter._event_queue.get_nowait()

        evt = asyncio.run(lifecycle())
        assert evt == {
            "type": "status",
            "phase": "Summarizing earlier conversation",
        }

    def test_complete_callback_emits_compaction_complete_event(self, project):
        # When the backend fires on_compaction_complete with a
        # CompactionInfo payload, the adapter queues a
        # ``compaction_complete`` event carrying the summary
        # + source turn count for the frontend's persistent banner.
        from clarity_agent.llm.types import CompactionInfo

        cfg = _StubLLMConfig()
        adapter = WebSessionAdapter(project, project, cfg)

        async def lifecycle() -> dict:
            await adapter.start()
            adapter._on_compaction_complete(CompactionInfo(
                summary="provider-produced summary text",
                source_turn_count=42,
            ))
            await asyncio.sleep(0)
            return adapter._event_queue.get_nowait()

        evt = asyncio.run(lifecycle())
        assert evt == {
            "type": "compaction_complete",
            "summary": "provider-produced summary text",
            "source_turn_count": 42,
        }

    def test_backend_wired_to_callbacks_at_start(self, project):
        # ``start()`` wires the adapter's bridge methods onto the
        # backend's ``on_compaction_*`` attributes so backend-side
        # compaction surfaces through the WebSocket.
        adapter = _start_adapter(project)
        backend = adapter._backend
        assert backend is not None
        assert backend.on_compaction_started == adapter._on_compaction_started
        assert backend.on_compaction_complete == adapter._on_compaction_complete

    def test_backend_receives_transcript_at_construction(self, project):
        # The transcript binding is passed to the backend at
        # creation time (not via a later setter) so backend-side
        # compaction can record into it without racing the first
        # turn's events.
        adapter = _start_adapter(project)
        cfg = adapter.llm_config
        assert cfg.last_backend is not None
        # Stub records the transcript kwarg on a dedicated attr.
        assert cfg.last_backend._transcript is adapter._project_transcript
