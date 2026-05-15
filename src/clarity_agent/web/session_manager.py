"""
Async bridge between the synchronous ClaritySession and the FastAPI WebSocket.

:class:`WebSessionAdapter` wraps a :class:`ClaritySession` and its backend,
running blocking ``chat()`` calls in a thread-pool executor while forwarding
tool-use events to an :class:`asyncio.Queue` that the WebSocket handler drains.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any

from clarity_agent.app_paths import protocol_dir as _protocol_dir
from clarity_agent.llm import ChatBackend, LLMConfig
from clarity_agent.llm.types import TokenUsage, ToolHandler
from clarity_agent.session import ClaritySession
from clarity_agent.web.session_state import load_session_state, save_session_state


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
        """Initialize backend and session."""
        self._loop = asyncio.get_running_loop()

        backend = self.llm_config.create_chat_backend(
            project_dir=self.project_dir,
            clarity_agent_dir=self.clarity_agent_dir,
        )
        backend.connect()
        self._backend = backend

        # Restore a previously persisted SDK session ID so the backend
        # resumes the conversation instead of starting fresh.
        session_id = self._initial_llm_session_id or load_session_state(
            self.project_dir,
        )
        if session_id:
            backend.llm_session_id = session_id

        # Snapshot whether the transcript already had any chapters
        # BEFORE ClaritySession's construction appends its header
        # event — that's how we tell "fresh project, nothing to
        # inject" apart from "existing project with prior
        # conversation, rebuild context from it."
        from clarity_agent.transcript import Transcript
        self._project_transcript = Transcript(self.project_dir)
        transcript_was_empty = self._project_transcript.is_empty

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
        # transcript persistence; we set on_tool_use (flattened) for
        # the UI's real-time display.  The two callbacks fire in
        # parallel — no chaining needed since they have different
        # signatures and different consumers.
        backend.on_tool_use = self._on_tool_use
        backend.on_text_delta = self._on_text_delta
        backend.on_cost = self._on_cost
        backend.on_usage = self._on_usage
        backend.on_warning = self._on_warning
        backend.on_status = self._on_status

        # Context-restore path: when the SDK has no session to resume
        # AND there's prior conversation in the transcript, synthesize
        # a prior conversation context out of that transcript and prepend
        # it to the system prompt on the first chat call (see :meth:`chat`).
        # When the transcript was empty before this session attached,
        # there's nothing meaningful to inject (the just-written
        # ChapterStarted is just a header), so we skip.
        if not backend.llm_session_id and not transcript_was_empty:
            self._transcript_context = self._project_transcript.context_summary()
        else:
            self._transcript_context = None

        # Install the feedback tool so it's available in all chat calls.
        self._setup_feedback_tools()

    @property
    def llm_session_id(self) -> str | None:
        """Return the backend's SDK session ID, if any."""
        if self._backend is not None:
            return self._backend.llm_session_id
        return self._initial_llm_session_id

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

    def _on_text_delta(self, text: str) -> None:
        """Synchronous callback for streaming text chunks from the executor thread."""
        if self._loop is None or self._cancelled:
            return
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
        self._loop.call_soon_threadsafe(
            self._event_queue.put_nowait,
            {
                "type": "usage",
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
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

        # On the first call, inject transcript context if we have it.
        if self._transcript_context is not None:
            ctx = self._transcript_context
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

        func = partial(
            self._session.chat, message, system_prompt, model=model,
            tools=self._tools, tool_handler=self._tool_handler,
        )
        response = await self._loop.run_in_executor(  # type: ignore[union-attr]
            self._executor, func,
        )

        # Persist the session ID so the next app launch can resume.
        save_session_state(self.project_dir, self.llm_session_id)

        # Flush any non-fatal warnings accumulated during the turn.  These are
        # queued before the response event so _drain_events() sees them first.
        for warn_msg in self._pending_warnings:
            await self._event_queue.put({"type": "warning", "message": warn_msg})
        self._pending_warnings.clear()

        await self._event_queue.put({"type": "response", "content": response})
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
