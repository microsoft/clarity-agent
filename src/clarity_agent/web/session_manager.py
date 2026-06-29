"""
Async bridge between the synchronous ClaritySession and the FastAPI WebSocket.

:class:`WebSessionAdapter` wraps a :class:`ClaritySession` and its backend,
running blocking ``chat()`` calls in a thread-pool executor while forwarding
tool-use events to an :class:`asyncio.Queue` that the WebSocket handler drains.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from clarity_agent.app_paths import protocol_dir as _protocol_dir
from clarity_agent.llm import ChatBackend, LLMConfig
from clarity_agent.llm.config import get_auth_mode_info
from clarity_agent.llm.types import TokenUsage, ToolHandler
from clarity_agent.session import ClaritySession
from clarity_agent.transcript import ChapterStarted, Transcript
from clarity_agent.web.session_state import (
    clear_session_state,
    load_session_state,
    save_session_state,
)

_APPROX_CHARS_PER_TOKEN = 4
_PROVIDER_MANAGED_CONTEXT_PROVIDERS = {"anthropic", "github"}
_PROVIDER_MANAGED_CONTEXT_BACKENDS = {"CopilotChatBackend", "SdkChatBackend"}


@dataclass(frozen=True)
class _ContextSegment:
    name: str
    role: str
    chars: int | None
    source: str
    position: str | None = None


class WebSessionAdapter:
    """Adapts ClaritySession for asynchronous web use.

    Runs synchronous ``backend.chat()`` in a single-worker thread pool.
    Tool-use events are pushed onto an :pyclass:`asyncio.Queue` so the
    WebSocket handler can stream them to the client in real time.
    """

    def __init__(
        self,
        project_dir: Path,
        clarity_agent_dir: Path,
        llm_config: LLMConfig,
        *,
        llm_session_id: str | None = None,
    ) -> None:
        self.project_dir = project_dir
        self.clarity_agent_dir = clarity_agent_dir
        self.llm_config = llm_config
        self._initial_llm_session_id = llm_session_id
        self.current_process: str | None = None
        self.model_override: str | None = None
        self.active_model: str = llm_config.tiers["default"]
        self.active_tier: str = "default"

        self._executor = ThreadPoolExecutor(max_workers=1)
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._backend: ChatBackend | None = None
        self._session: ClaritySession | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tools: list[dict[str, Any]] | None = None
        self._tool_handler: ToolHandler | None = None
        # Warnings accumulated during a chat turn (written from executor thread,
        # read from the event loop after run_in_executor completes — safe because
        # the single-worker executor serializes all writes before we read).
        self._pending_warnings: list[str] = []
        # Transcript context to inject on the first chat call when no session
        # could be resumed.  Set during start(), consumed on first chat().
        self._transcript_context: str | None = None
        # Set to True when the user clicks Stop.  The drain loop checks this
        # and stops forwarding events; the backend thread finishes on its own.
        self._cancelled = False
        # Partial text accumulated from events before cancellation.
        self._partial_text: list[str] = []
        self._stream_started = False
        self._stream_chunk_count = 0
        self._stream_char_count = 0

    def _setup_feedback_tools(self) -> None:
        """Set up the feedback tool as baseline for all chat calls."""
        from clarity_agent.ai_actions.feedback import (
            create_feedback_handler,
            create_feedback_tools,
        )

        self._feedback_tools = create_feedback_tools()
        self._feedback_handler = create_feedback_handler(
            self.project_dir,
            provider=self.llm_config.provider,
            model=self.llm_config.tiers.get("default"),
            active_model=self.active_model,
            active_tier=self.active_tier,
            on_tool_use=self._backend.on_tool_use if self._backend else None,
        )
        # Install as baseline tools.
        self._tools = list(self._feedback_tools)
        self._tool_handler = self._feedback_handler

    async def start(self) -> None:
        """Initialize backend and session.

        Transactional: on failure, any state that was already
        allocated (live backend thread/loop, entered session
        context) is rolled back via :meth:`_rollback_partial_start`
        before re-raising.  Callers therefore see "succeeded or
        nothing happened" semantics and don't need to clean up after
        an exception themselves — important for the WebSocket entry
        point in ``web/app.py``, which keeps the socket open after a
        start failure to surface a classified error_event (see
        issue #47).  Without the rollback, a half-started backend
        (notably Copilot, which spawns a daemon thread in
        :meth:`connect`) would leak per failed connection attempt.
        """
        self._loop = asyncio.get_running_loop()

        # Build the Transcript first so we can hand it to the backend
        # at construction time — the backend owns compaction
        # bookkeeping (threshold checks, provider-signal recording),
        # so it needs the binding from the start to avoid races
        # against any first-turn events.  Snapshot emptiness BEFORE
        # ClaritySession's construction appends its header event
        # below — that's how we tell "fresh project, nothing to
        # inject" apart from "existing project with prior
        # conversation, rebuild context from it."
        #
        # The Transcript object itself is lazy — file handles aren't
        # opened until the first write — so leaving it on the
        # adapter after a rollback doesn't leak anything.  The
        # writer, if it was opened by a ClaritySession that managed
        # to construct before raising, is closed by
        # ``_rollback_partial_start`` via the session's __exit__.
        self._project_transcript = Transcript(self.project_dir)
        transcript_was_empty = self._project_transcript.is_empty

        # Reconcile the project's AGENTS.md against the current
        # :class:`ProjectLayout` before the LLM has a chance to read
        # it.  Detection is read-only — if no layout is present yet
        # (neither ``.clarity-protocol/`` nor ``Clarity Protocol/``
        # nor ``.clarity-agent/``), we skip the reconcile rather than
        # implicitly creating one: per-mode setup belongs in the
        # explicit entry points (``clarity install --embedded`` for
        # git repos, the desktop "new project" flow for userspace),
        # not in every session-open.  Failures here log but don't
        # block the session — a stale AGENTS.md is preferable to a
        # failed session start.
        self._ensure_agents_md_best_effort()

        try:
            backend = self.llm_config.create_chat_backend(
                project_dir=self.project_dir,
                clarity_agent_dir=self.clarity_agent_dir,
                transcript=self._project_transcript,
            )
            # Stash the backend BEFORE :meth:`connect` so a raise
            # from connect itself (or any later step) leaves the
            # rollback path with something to disconnect.  Both
            # :class:`CopilotChatBackend` and :class:`ClientChatBackend`
            # implement ``disconnect`` to be idempotent / no-op on a
            # backend whose connect() never completed, so calling it
            # speculatively is safe.
            self._backend = backend
            backend.connect()

            # Restore a previously persisted SDK session ID so the
            # backend resumes the conversation instead of starting
            # fresh.
            session_id = self._initial_llm_session_id or load_session_state(
                self.project_dir,
            )
            if session_id:
                backend.llm_session_id = session_id

            self._session = ClaritySession(
                self.project_dir,
                self.clarity_agent_dir,
                backend,
                self.llm_config,
                transcript=self._project_transcript,
            )
            self._session.__enter__()

            # Bridge backend callbacks to the WebSocket event queue.
            # ClaritySession sets backend.on_tool_call (structured) for
            # transcript persistence; we set on_tool_use (flattened)
            # for the UI's real-time display.  The two callbacks fire
            # in parallel — no chaining needed since they have
            # different signatures and different consumers.
            backend.on_tool_use = self._on_tool_use
            backend.on_text_delta = self._on_text_delta
            backend.on_cost = self._on_cost
            backend.on_usage = self._on_usage
            backend.on_warning = self._on_warning
            backend.on_status = self._on_status
            backend.on_compaction_started = self._on_compaction_started
            backend.on_compaction_complete = self._on_compaction_complete

            # Context-restore path: when the SDK has no session to
            # resume AND there's prior conversation in the transcript,
            # synthesize a prior conversation context out of that
            # transcript and prepend it to the system prompt on the
            # first chat call (see :meth:`chat`).  When the transcript
            # was empty before this session attached, there's nothing
            # meaningful to inject (the just-written ChapterStarted
            # is just a header), so we skip.  ``context_summary`` reads
            # transcript files, which can raise — kept inside the
            # transactional block so a failure here also rolls back.
            if not backend.llm_session_id and not transcript_was_empty:
                self._transcript_context = self._project_transcript.context_summary()
            else:
                self._transcript_context = None

            # Install the feedback tool so it's available in all chat
            # calls.
            self._setup_feedback_tools()
        except BaseException:
            self._rollback_partial_start()
            raise

    def _rollback_partial_start(self) -> None:
        """Undo whatever portion of :meth:`start` completed.

        Called from :meth:`start`'s except clause after any failure
        during backend construction, ``connect``, session
        construction, or post-setup steps.  Each cleanup is wrapped
        in its own ``try/except`` so a failure in one step still
        lets the next step run — and so the rollback never replaces
        the original exception with a cleanup-time one.  Resets
        instance attributes to their pre-start values so the adapter
        looks "not started" to any caller that re-checks (e.g. the
        WS handler that keeps the socket open and may otherwise be
        tempted to reuse a half-dead adapter).
        """
        if self._session is not None:
            try:
                self._session.__exit__(None, None, None)
            except Exception:
                # __exit__ is currently a no-op but may grow side
                # effects; swallow rather than mask the real error.
                pass
            self._session = None
        if self._backend is not None:
            try:
                self._backend.disconnect()
            except Exception:
                # ``disconnect`` already swallows its own failures
                # (see ``CopilotChatBackend.disconnect``); this
                # outer guard catches anything that escapes — e.g.
                # a backend whose ``connect`` raised partway through
                # leaving an invariant the disconnect path doesn't
                # expect.
                pass
            self._backend = None
        # ``_project_transcript`` is intentionally NOT cleared: file
        # handles, if any were opened, were closed by the session's
        # __exit__ above (the writer is owned by the chapter context
        # the session entered).  Holding the reference is harmless
        # and lets diagnostics inspect the partial state.
        self._transcript_context = None

    def _ensure_agents_md_best_effort(self) -> None:
        """Reconcile ``project_dir/AGENTS.md`` against the current
        layout before backend construction, so the LLM sees the
        current rendering on its first turn.

        Defense-in-depth: in production the same call also runs at
        the top of :func:`~clarity_agent.web.app.create_app`, which
        fires once per sidecar startup (i.e. per "open this
        directory" event) — that's the primary place.  This hook
        covers callers that construct an adapter directly without
        going through ``create_app`` (notably tests, but also any
        future programmatic embedding).  Both paths are idempotent
        (no write when nothing's changed), so double-execution is
        cheap.

        Delegates to :func:`~clarity_agent.setup.snippet.ensure_for_project`,
        which centralises the dogfooding skip, the no-layout
        short-circuit, and OSError swallowing — see that function's
        docstring for the policy.  This wrapper only adds the
        startup-log line for non-no-op outcomes so contributors can
        see what happened on each session open.
        """
        from clarity_agent.setup.snippet import (
            EnsureStatus,
            ensure_for_project,
        )

        status = ensure_for_project(
            self.project_dir, self.clarity_agent_dir,
        )
        if status is not None and status is not EnsureStatus.UNCHANGED:
            print(
                f"  [agents.md] {status.value}: "
                f"{self.project_dir / 'AGENTS.md'}",
                flush=True,
            )

    @property
    def llm_session_id(self) -> str | None:
        """Return the backend's SDK session ID, if any."""
        if self._backend is not None:
            return self._backend.llm_session_id
        return self._initial_llm_session_id

    def start_new_chapter(self) -> int:
        """Roll over the conversation thread to a new chapter.

        The current chapter becomes a read-only archive; the backend's
        SDK session is cleared so the next user message starts a
        brand-new conversation with no carried-over context.  The
        previously-loaded context-restore blob (if any) is discarded
        for the same reason — the user has explicitly asked for a
        clean slate.

        Returns the new chapter number.  The new chapter is seeded
        with a :class:`ChapterStarted` event so it's never "empty"
        from the consumer's perspective.

        Idempotent in the sense that calling repeatedly produces
        further new chapters; not idempotent in the sense that each
        call genuinely rolls over (consequence: the UI should gate
        this behind a confirmation dialog).
        """
        backend_name = (
            type(self._backend).__name__ if self._backend is not None else "unknown"
        )
        new_chapter = self._project_transcript.start_new_chapter()
        self._project_transcript.write(ChapterStarted(
            timestamp=datetime.now(UTC),
            project_dir=str(self.project_dir),
            backend=backend_name,
        ))

        # Reset the SDK session so the next turn starts fresh.  Clear
        # the persisted state too — otherwise the next process start
        # would resume the now-archived conversation.
        if self._backend is not None:
            self._backend.llm_session_id = None
        clear_session_state(self.project_dir)

        # Drop any pending context-restore blob the start() path may
        # have loaded — it would inject prior-chapter content into
        # the brand-new chapter's first message, undoing the rollover.
        self._transcript_context = None

        return new_chapter

    def _on_tool_use(self, tool_name: str, detail: str) -> None:
        """Synchronous callback invoked from the executor thread.

        Bridges to the asyncio event loop using ``call_soon_threadsafe``.
        """
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(
            self._event_queue.put_nowait,
            {"type": "tool_use", "tool": tool_name, "detail": detail},
        )

    def _log_generation(self, detail: str) -> None:
        print(f"[generation] {detail}", flush=True)

    def _credential_summary(self) -> str:
        provider = getattr(self.llm_config, "provider", "unknown")
        auth_mode = getattr(self.llm_config, "auth_mode", None) or "default"
        mode_info = get_auth_mode_info(provider, auth_mode) or {}
        credential_name = mode_info.get("env_var") or auth_mode
        api_key = getattr(self.llm_config, "api_key", None)
        if api_key:
            return f"{credential_name}=configured(redacted)"
        if auth_mode in ("api_key", "token"):
            return f"{credential_name}=missing"
        return f"{auth_mode}=configured(no-api-key)"

    def _endpoint_summary(self) -> str:
        endpoint = getattr(self.llm_config, "endpoint", None)
        if not endpoint:
            return "none"
        try:
            parsed = urlsplit(endpoint)
        except ValueError:
            return "configured(redacted-invalid-url)"
        if not parsed.scheme or not parsed.netloc:
            return "configured(redacted-invalid-url)"
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))

    def _generation_start_detail(
        self,
        *,
        model: str,
        message: str,
        system_prompt: str | None,
    ) -> str:
        provider = getattr(self.llm_config, "provider", "unknown")
        auth_mode = getattr(self.llm_config, "auth_mode", None) or "default"
        process = self.current_process or "chat"
        tool_count = len(self._tools or [])
        return (
            "llm.request start "
            f"provider={provider} "
            f"model={model} "
            f"tier={self.active_tier} "
            f"process={process} "
            f"auth_mode={auth_mode} "
            f"credential={self._credential_summary()} "
            f"endpoint={self._endpoint_summary()} "
            f"tools={tool_count} "
            f"user_message_chars={len(message)} "
            f"system_prompt_chars={len(system_prompt or '')}"
        )

    @staticmethod
    def _estimate_tokens(chars: int) -> int:
        if chars <= 0:
            return 0
        return max(1, (chars + _APPROX_CHARS_PER_TOKEN - 1) // _APPROX_CHARS_PER_TOKEN)

    @staticmethod
    def _serialized_char_count(value: Any) -> int:
        try:
            return len(json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ))
        except (TypeError, ValueError):
            return len(repr(value))

    def _backend_system_prompt_chars(self) -> int | None:
        backend = self._backend
        build_system_prompt = getattr(backend, "_build_system_prompt", None)
        if not callable(build_system_prompt):
            return None
        try:
            built_prompt = build_system_prompt(None)
        except Exception:
            return None
        if isinstance(built_prompt, str):
            return len(built_prompt)
        return len(str(built_prompt))

    def _project_behaviors_chars(self) -> int:
        session = self._session
        if session is None:
            return 0
        return len(session.load_behaviors())

    def _known_history_chars(self) -> int | None:
        history = getattr(self._backend, "conversation_history", None)
        if not isinstance(history, list):
            return None
        return self._serialized_char_count(history)

    def _context_window_tokens(self, model: str) -> int:
        backend = self._backend
        if backend is None:
            return ChatBackend.DEFAULT_CONTEXT_WINDOW
        return backend.context_window_for(model)

    def _provider_manages_context(self) -> bool:
        provider = getattr(self.llm_config, "provider", "unknown")
        backend_name = type(self._backend).__name__ if self._backend is not None else ""
        return (
            provider in _PROVIDER_MANAGED_CONTEXT_PROVIDERS
            or backend_name in _PROVIDER_MANAGED_CONTEXT_BACKENDS
        )

    @staticmethod
    def _position_label(start_tokens: int, end_tokens: int, context_window: int) -> str:
        if context_window <= 0:
            return "unknown"
        return f"{start_tokens / context_window:.1%}-{end_tokens / context_window:.1%}"

    def _context_segment_details(
        self,
        segments: list[_ContextSegment],
        *,
        context_window_tokens: int,
    ) -> tuple[list[str], int]:
        details: list[str] = []
        cursor = 0
        known_tokens = 0
        for index, segment in enumerate(segments, start=1):
            if segment.chars is None:
                details.append(
                    "llm.context_segment "
                    f"index={index} "
                    f"name={segment.name} "
                    f"role={segment.role} "
                    "chars=unknown "
                    "estimated_tokens=unknown "
                    f"position={segment.position or 'unknown'} "
                    f"source={segment.source}"
                )
                continue

            tokens = self._estimate_tokens(segment.chars)
            known_tokens += tokens
            if segment.position is None:
                position = self._position_label(
                    cursor,
                    cursor + tokens,
                    context_window_tokens,
                )
                cursor += tokens
            else:
                position = segment.position
            details.append(
                "llm.context_segment "
                f"index={index} "
                f"name={segment.name} "
                f"role={segment.role} "
                f"chars={segment.chars} "
                f"estimated_tokens={tokens} "
                f"position={position} "
                f"source={segment.source}"
            )
        return details, known_tokens

    def _context_manifest_details(
        self,
        *,
        model: str,
        message: str,
        turn_system_prompt: str | None,
        transcript_context_chars: int,
    ) -> list[str]:
        context_window_tokens = self._context_window_tokens(model)
        provider_managed_context = self._provider_manages_context()
        segments: list[_ContextSegment] = []

        backend_system_chars = self._backend_system_prompt_chars()
        if backend_system_chars is not None:
            segments.append(_ContextSegment(
                name="backend_system_prompt",
                role="system",
                chars=backend_system_chars,
                source="backend_static",
            ))

        tool_schema_chars = (
            self._serialized_char_count(self._tools)
            if self._tools
            else 0
        )
        if tool_schema_chars:
            segments.append(_ContextSegment(
                name="tool_schemas",
                role="tools",
                chars=tool_schema_chars,
                source="adapter_passed_tools",
                position="provider_specific",
            ))

        behavior_chars = self._project_behaviors_chars()
        if behavior_chars:
            segments.append(_ContextSegment(
                name="project_behaviors",
                role="system",
                chars=behavior_chars,
                source="project_AGENTS",
            ))

        if transcript_context_chars:
            segments.append(_ContextSegment(
                name="transcript_restore",
                role="system",
                chars=transcript_context_chars,
                source="prior_transcript",
            ))

        turn_system_chars = len(turn_system_prompt or "")
        if turn_system_chars:
            segments.append(_ContextSegment(
                name="turn_system_prompt",
                role="system",
                chars=turn_system_chars,
                source="process_or_call",
            ))

        history_chars = self._known_history_chars()
        if history_chars is None or provider_managed_context:
            segments.append(_ContextSegment(
                name="provider_session_history",
                role="messages",
                chars=None,
                source="provider_runtime",
                position="provider_managed",
            ))
        else:
            segments.append(_ContextSegment(
                name="prior_messages",
                role="messages",
                chars=history_chars,
                source="backend_conversation_history",
            ))

        segments.append(_ContextSegment(
            name="current_user_message",
            role="user",
            chars=len(message),
            source="current_turn",
        ))

        segment_details, known_tokens = self._context_segment_details(
            segments,
            context_window_tokens=context_window_tokens,
        )
        provider_visibility = (
            "not_visible"
            if provider_managed_context
            else "visible_to_clarity"
        )
        manifest = (
            "llm.context_manifest "
            "visibility=clarity_assembled "
            f"context_window_tokens={context_window_tokens} "
            f"known_estimated_tokens={known_tokens} "
            f"known_window_fraction={known_tokens / context_window_tokens:.1%} "
            f"provider_internal_context={provider_visibility} "
            "token_estimate=chars_div_4 "
            "raw_prompt_content=omitted"
        )
        return [manifest, *segment_details]

    def _on_text_delta(self, text: str) -> None:
        """Synchronous callback for streaming text chunks from the executor thread."""
        if self._loop is None or self._cancelled:
            return
        if not self._stream_started:
            self._stream_started = True
            self._log_generation(
                "llm.stream first_text_delta "
                f"provider={getattr(self.llm_config, 'provider', 'unknown')} "
                f"model={self.active_model}"
            )
        self._stream_chunk_count += 1
        self._stream_char_count += len(text)
        self._loop.call_soon_threadsafe(
            self._event_queue.put_nowait,
            {"type": "text_delta", "content": text},
        )

    def _on_cost(self, cost_usd: float) -> None:
        """Synchronous callback for cost events from the executor thread."""
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(
            self._event_queue.put_nowait,
            {"type": "cost", "cost_usd": cost_usd},
        )

    def _on_status(self, phase: str) -> None:
        """Synchronous callback for coalesced status updates.

        Ephemeral: the frontend should display the latest phase
        transiently (overwriting the previous one), not append to
        chat history.
        """
        if self._loop is None or self._cancelled:
            return
        self._loop.call_soon_threadsafe(
            self._event_queue.put_nowait,
            {"type": "status", "phase": phase},
        )

    def _on_usage(self, usage: TokenUsage) -> None:
        """Synchronous callback for token usage events from the executor thread."""
        if self._loop is None:
            return
        self._log_generation(
            "llm.usage "
            f"input_tokens={usage.input_tokens} "
            f"output_tokens={usage.output_tokens}"
        )
        self._loop.call_soon_threadsafe(
            self._event_queue.put_nowait,
            {
                "type": "usage",
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            },
        )

    def _on_compaction_started(self) -> None:
        """Backend is starting compaction — surface the phase to the UI.

        Fires from whichever thread the backend uses (executor for
        :class:`ClientChatBackend`, the SDK event thread for the
        Claude/Copilot backends).  Bridges to the asyncio loop via
        ``call_soon_threadsafe`` for safe queue access.
        """
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(
            self._event_queue.put_nowait,
            {"type": "status", "phase": "Summarizing earlier conversation"},
        )

    def _on_compaction_complete(self, info: Any) -> None:
        """Backend has finished writing the compaction to the transcript.

        Emit the ``compaction_complete`` event so the frontend can
        render its persistent system message.  No further session
        cleanup is needed — the backend has already updated its own
        state (conversation history, SDK session reset, etc.).
        """
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(
            self._event_queue.put_nowait,
            {
                "type": "compaction_complete",
                "summary": info.summary,
                "source_turn_count": info.source_turn_count,
            },
        )

    def _on_warning(self, message: str) -> None:
        """Synchronous callback for non-fatal backend warnings from the executor thread.

        Appends to ``_pending_warnings`` rather than the event queue directly,
        because the warning fires before ``chat()`` queues the ``response``
        event.  The main loop flushes pending warnings into the queue (before
        the response event) once ``run_in_executor`` completes.
        """
        self._pending_warnings.append(message)

    def _resolve_model(self, process_name: str | None = None) -> str:
        """Resolve the model to use for the next chat call.

        If a manual override is set, use that.  Otherwise resolve from the
        config for the given process.  The returned value may be a tier name
        or model string; the backend's ``resolve_model()`` handles both.
        """
        if self.model_override:
            return self.model_override
        if process_name:
            return self.llm_config.resolve(process_name)
        return self.llm_config.tiers["default"]

    def _update_active_model(
        self, model_override: str | None, process_name: str | None = None,
    ) -> None:
        """Update active_model and active_tier tracking fields."""
        backend = self._backend
        if model_override:
            # Resolve tier names to concrete models for display
            if backend:
                self.active_model = backend.resolve_model(model_override)
            else:
                self.active_model = model_override
            # Determine the tier name
            tiers = self.llm_config.tiers
            self.active_tier = next(
                (k for k, v in tiers.items() if v == model_override),
                model_override if model_override in ("deep", "fast", "default") else "custom",
            )
        elif process_name:
            self.active_tier = self.llm_config.resolve_tier(process_name)
            resolved = self.llm_config.resolve(process_name)
            if backend:
                self.active_model = backend.resolve_model(resolved)
            else:
                self.active_model = resolved
        else:
            self.active_tier = "default"
            self.active_model = self.llm_config.tiers["default"]

    def cancel(self) -> None:
        """Signal that the current turn should be stopped.

        The in-flight backend call continues (we can't interrupt a thread),
        but the drain loop stops forwarding events and a partial response
        is synthesized from whatever text has been received so far.
        """
        self._cancelled = True

    async def chat(self, message: str, system_prompt: str | None = None) -> str:
        """Send a chat message, running the blocking call in a thread."""
        assert self._session is not None
        self._cancelled = False
        self._partial_text.clear()
        self._stream_started = False
        self._stream_chunk_count = 0
        self._stream_char_count = 0

        turn_system_prompt = system_prompt
        transcript_context_chars = 0
        # On the first call, inject transcript context if we have it.
        if self._transcript_context is not None:
            ctx = self._transcript_context
            transcript_context_chars = len(ctx)
            self._transcript_context = None  # consume — only inject once
            # Signal the UI so the user sees why startup takes longer.
            await self._event_queue.put({
                "type": "tool_use",
                "tool": "context_restore",
                "detail": "Re-reading prior session transcripts",
            })
            if system_prompt:
                system_prompt = f"{ctx}\n\n{system_prompt}"
            else:
                system_prompt = ctx

        model = self._resolve_model(self.current_process)
        self._update_active_model(model, self.current_process)
        self._log_generation(
            self._generation_start_detail(
                model=model,
                message=message,
                system_prompt=system_prompt,
            )
        )
        for detail in self._context_manifest_details(
            model=model,
            message=message,
            turn_system_prompt=turn_system_prompt,
            transcript_context_chars=transcript_context_chars,
        ):
            self._log_generation(detail)

        func = partial(
            self._session.chat, message, system_prompt, model=model,
            tools=self._tools, tool_handler=self._tool_handler,
        )
        started_at = perf_counter()
        try:
            response = await self._loop.run_in_executor(  # type: ignore[union-attr]
                self._executor, func,
            )
        except Exception as exc:
            duration_ms = int((perf_counter() - started_at) * 1000)
            self._log_generation(
                "llm.response failed "
                f"provider={getattr(self.llm_config, 'provider', 'unknown')} "
                f"model={self.active_model} "
                f"duration_ms={duration_ms} "
                f"error_type={type(exc).__name__}"
            )
            raise

        duration_ms = int((perf_counter() - started_at) * 1000)
        self._log_generation(
            "llm.response complete "
            f"provider={getattr(self.llm_config, 'provider', 'unknown')} "
            f"model={self.active_model} "
            f"duration_ms={duration_ms} "
            f"response_chars={len(response)} "
            f"stream_chunks={self._stream_chunk_count} "
            f"stream_chars={self._stream_char_count}"
        )

        # Persist the session ID so the next app launch can resume.
        save_session_state(self.project_dir, self.llm_session_id)

        # Flush any non-fatal warnings accumulated during the turn.  These are
        # queued before the response event so _drain_events() sees them first.
        for warn_msg in self._pending_warnings:
            await self._event_queue.put({"type": "warning", "message": warn_msg})
        self._pending_warnings.clear()

        await self._event_queue.put({"type": "response", "content": response})

        # Threshold-based compaction (for backends that don't
        # auto-compact internally).  Runs on the executor since it
        # may issue a blocking summarization LLM call.  No-op for
        # SDK / Copilot backends, which compact during the chat call
        # itself.  Status events are bridged via on_compaction_*.
        assert self._backend is not None
        await self._loop.run_in_executor(  # type: ignore[union-attr]
            self._executor, self._backend.maybe_compact_after_chat,
        )

        return response

    async def start_process(self, process_name: str) -> str:
        """Begin a process (loads guide, sends initial message).

        Does NOT enter an interactive loop — the web frontend replaces
        the loop by sending individual ``chat`` messages.
        """
        assert self._session is not None
        self._cancelled = False
        self._partial_text.clear()

        process_content = self._session.load_process(process_name)
        prev_process = self.current_process
        self.current_process = process_name

        # Emit model_changed when switching processes or on first process start
        old_model = self.active_model
        model = self._resolve_model(process_name)
        self._update_active_model(model, process_name)
        if self.active_model != old_model or prev_process is None:
            await self._event_queue.put({
                "type": "model_changed",
                "tier": self.active_tier,
                "model": self.active_model,
                "auto": self.model_override is None,
            })

        # Reset to baseline feedback tools; process-specific tools are
        # merged below.
        self._setup_feedback_tools()
        specialists: list[Any] = []

        # For failure-brainstorming, add tools so the AI can record
        # findings with controlled formatting.
        if process_name == "failure-brainstorming":
            from clarity_agent.ai_actions.brainstorm import (
                create_brainstorm_handler,
                create_brainstorm_tools,
            )
            from clarity_agent.protocol.thinker_registry import select_thinkers

            all_thinkers = select_thinkers(
                self.clarity_agent_dir,
                _protocol_dir(self.project_dir),
                mode="deep",
            )
            specialists = [t for t in all_thinkers if t.name != "general-thinker"]

            brainstorm_tools = create_brainstorm_tools(specialists or None)
            brainstorm_handler = create_brainstorm_handler(
                _protocol_dir(self.project_dir),
                self.clarity_agent_dir,
                on_tool_use=self._backend.on_tool_use if self._backend else None,
            )

            # Merge brainstorm tools with baseline feedback tools.
            assert self._tools is not None  # set by _setup_feedback_tools above
            self._tools.extend(brainstorm_tools)
            feedback_handler = self._feedback_handler

            def _combined_handler(tc: Any) -> str:
                if tc.name == "send_feedback":
                    return feedback_handler(tc)
                return brainstorm_handler(tc)

            self._tool_handler = _combined_handler

        behaviors: str = self._session.load_behaviors()
        behaviors_block: str = f"{behaviors}\n\n" if behaviors else ""

        system_prompt: str = (
            f"{behaviors_block}"
            f"You are running the {process_name} process. "
            f"Here is the process guide:\n\n{process_content}\n\n"
            f"Follow this process step by step.\n\n"
            f"The clarity-agent directory (containing process guides and "
            f"thinker definitions) is: {self.clarity_agent_dir}\n"
            f"Process guides: {self.clarity_agent_dir / 'processes'}/\n"
            f"Thinker guides: {self.clarity_agent_dir / 'thinkers'}/"
        )

        status_report = self._session.get_packet_status_report()
        if status_report:
            system_prompt += (
                f"\n\nThe following packet status analysis was performed by checking "
                f"content hashes against the document dependency graph. Use this "
                f"to inform your assessment:\n\n{status_report}"
            )

        # For failure-brainstorming, append methodology and specialist info.
        if process_name == "failure-brainstorming":
            from clarity_agent.ai_actions.brainstorm import (
                format_available_thinkers as _fmt_thinkers,
            )

            methodology_path = (
                self.clarity_agent_dir / "processes" / "failure-reasoning-guidelines.md"
            )
            if methodology_path.exists():
                system_prompt += (
                    f"\n\n## Failure Reasoning Methodology\n\n"
                    f"{methodology_path.read_text()}"
                )
            if specialists:
                system_prompt += f"\n\n{_fmt_thinkers(specialists)}"

        initial_message: str = f"Let's run the {process_name} process."

        return await self.chat(
            initial_message,
            system_prompt=system_prompt,
        )

    async def get_events(self) -> AsyncIterator[dict[str, Any]]:
        """Async generator yielding events from the queue.

        Yields tool_use events as they arrive, then yields the final
        response event and returns.
        """
        while True:
            event = await self._event_queue.get()
            yield event
            if event.get("type") == "response":
                break

    async def stop(self) -> None:
        """Clean up resources."""
        if self._session is not None:
            self._session.__exit__(None, None, None)
            self._session = None
        if self._backend is not None:
            self._backend.disconnect()
            self._backend = None
        self._executor.shutdown(wait=False)
