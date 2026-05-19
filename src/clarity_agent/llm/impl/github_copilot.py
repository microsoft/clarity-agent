"""GitHub Copilot SDK chat backend.

Provides a :class:`ChatBackend` implementation that uses the GitHub
Copilot SDK for conversations.  Like the Claude SDK backend, this
wraps an agent runtime rather than a raw messages API — there is no
corresponding :class:`LLMClient`.

Authentication uses the GitHub CLI (``gh auth token``), a
``GITHUB_TOKEN`` / ``GH_TOKEN`` env var, or the Copilot SDK's
built-in OAuth flow.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Coroutine
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Deferred behind ``TYPE_CHECKING`` to break the cycle through
# ``clarity_agent.transcript._render`` → ``clarity_agent.llm.client``;
# see the matching comment in ``clarity_agent.llm.chat``.
if TYPE_CHECKING:
    from clarity_agent.transcript import Transcript

from copilot import CopilotClient
from copilot.generated.session_events import SessionEvent, SessionEventType
from copilot.session import (
    CopilotSession,
    PermissionHandler,
    SystemMessageCustomizeConfig,
)

from clarity_agent.llm.chat import ChatBackend
from clarity_agent.llm.types import CompactionInfo, ToolHandler, ToolUseBlock

_GITHUB_TIER_DEFAULTS: dict[str, str] = {
    "default": "claude-sonnet-4.6",
    "deep": "claude-opus-4.6",
    "fast": "claude-sonnet-4.6",
}

# Context-window size in tokens.  Copilot serves Claude family
# models with the standard 200K window; uses ``.`` rather than ``-``
# in its model names, hence the separate map from the Anthropic
# table.
_GITHUB_MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "claude-sonnet-4.6": 200_000,
    "claude-opus-4.6": 200_000,
}

# Default number of seconds with NO streaming activity from the peer
# before we declare a turn stuck and raise TimeoutError.  Reset on every
# SDK event, so a long turn with steady streaming — common for deep
# Clarity sessions that chain many tool calls — never trips this.  The
# timer only fires if the Copilot SDK stops emitting events entirely,
# which is the "process is wedged / network is dead" case we actually
# want to surface.  Override via ``CopilotChatBackend(idle_timeout_seconds=...)``.
_DEFAULT_IDLE_TIMEOUT_SECONDS = 300.0

# Number of times to kill + recreate the SDK session on an idle
# timeout before giving up on the turn entirely.  A real retry —
# destroys the wedged session, builds a fresh one, replays every
# prior user message so the SDK has the same conversation state,
# then retries the message that hung.  Expensive (N-turn replays
# take N-turns of SDK time) but correct: the sole reliable way to
# unstick a wedged Copilot session is to throw it away.
_DEFAULT_MAX_RPC_RETRIES = 1


async def _wait_for_done_with_idle_timeout(
    done: asyncio.Event,
    activity_timestamp: list[float],
    idle_timeout_seconds: float,
) -> None:
    """Wait for ``done`` to be set, failing if the peer stops streaming.

    ``activity_timestamp`` is a single-element mutable list holding the
    monotonic time of the most recent peer activity.  The caller's
    event handler must update ``activity_timestamp[0]`` whenever the
    peer emits any signal — a text delta, a tool-use start, anything.
    If the gap between ``time.monotonic()`` and that timestamp ever
    exceeds *idle_timeout_seconds*, raise :class:`TimeoutError`.

    Passed as a list rather than a scalar because Python closures close
    over names, not values — mutating ``list[0]`` from the event
    handler is the simplest way to give this coroutine a live view of
    the last-activity time without a lock or a queue.
    """
    while not done.is_set():
        elapsed_since_activity = time.monotonic() - activity_timestamp[0]
        remaining = idle_timeout_seconds - elapsed_since_activity
        if remaining <= 0:
            raise TimeoutError(
                f"No peer activity for {idle_timeout_seconds:.0f}s — "
                f"backend appears stuck"
            )
        try:
            await asyncio.wait_for(done.wait(), timeout=remaining)
        except TimeoutError:
            # An event may have arrived during the wait, refreshing
            # activity_timestamp[0].  Loop and recompute.
            continue


def get_gh_cli_token(*, raise_on_failure: bool = False) -> str | None:
    """Retrieve a GitHub token from the ``gh`` CLI.

    Returns the token string, or ``None`` if the token could not be
    obtained.  When *raise_on_failure* is True, raises a
    :class:`RuntimeError` with a user-facing explanation instead of
    returning ``None``.
    """
    if not shutil.which("gh"):
        if raise_on_failure:
            raise RuntimeError(
                "The GitHub CLI (gh) is not installed.\n"
                "Install it from https://cli.github.com/ and run 'gh auth login'."
            )
        return None

    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired as exc:
        if raise_on_failure:
            raise RuntimeError("'gh auth token' timed out.") from exc
        return None

    if result.returncode != 0 or not result.stdout.strip():
        if raise_on_failure:
            stderr = result.stderr.strip()
            raise RuntimeError(
                "Not logged in to GitHub.\n"
                "Run 'gh auth login' to authenticate."
                + (f"\n\ngh stderr: {stderr}" if stderr else "")
            )
        return None

    return result.stdout.strip()


class CopilotChatBackend(ChatBackend):
    """Chat backend using the GitHub Copilot SDK.

    Uses :class:`CopilotClient` sessions for multi-turn conversations.
    The SDK manages the Copilot CLI process lifecycle and
    authentication automatically.
    """

    supports_tools: bool = True
    TIER_DEFAULTS = _GITHUB_TIER_DEFAULTS
    MODEL_CONTEXT_WINDOWS = _GITHUB_MODEL_CONTEXT_WINDOWS

    def __init__(
        self,
        *,
        project_dir: Path,
        clarity_agent_dir: Path,
        token: str | None = None,
        idle_timeout_seconds: float | None = None,
        max_rpc_retries: int | None = None,
        transcript: Transcript | None = None,
    ) -> None:
        super().__init__(transcript=transcript)
        self.project_dir = project_dir
        self.clarity_agent_dir = clarity_agent_dir
        self._token = token
        # Per-turn idle timeout: the peer must emit *some* SDK event
        # within this many seconds, or we abort the turn.  Resets on
        # every event — long-but-streaming turns are fine, only truly
        # silent hangs trip it.  ``None`` → use the module default.
        self._idle_timeout_seconds: float = (
            idle_timeout_seconds
            if idle_timeout_seconds is not None
            else _DEFAULT_IDLE_TIMEOUT_SECONDS
        )
        # Recovery budget: on idle-timeout, kill the wedged session,
        # build a new one, replay every prior user message so the SDK
        # has the same conversation state, then retry the one that hung.
        # Expensive (replay costs N turns of SDK time for the Nth turn)
        # but it's the only reliable way to unwedge the SDK.
        self._max_rpc_retries: int = (
            max_rpc_retries
            if max_rpc_retries is not None
            else _DEFAULT_MAX_RPC_RETRIES
        )
        self._client: CopilotClient | None = None
        self._session: CopilotSession | None = None
        self._current_system_prompt: str | None = None
        # User messages in send-order for the current session, so we
        # can replay them verbatim if we have to rebuild the session
        # after a wedge.  Cleared whenever the session is reset
        # (system-prompt change, disconnect, kill-and-retry).
        self._user_messages: list[str] = []
        # The Copilot SDK's jsonrpc client captures a reference to the
        # first event loop it touches (via run_in_executor for the
        # write path).  Using a fresh asyncio.run() per chat call means
        # the second call tries to reuse the now-closed loop.  Instead
        # we run one loop on a dedicated thread for the backend's
        # lifetime and submit work via run_coroutine_threadsafe.
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None

    @property
    def llm_session_id(self) -> str | None:
        return None  # Session management is internal to the SDK.

    @llm_session_id.setter
    def llm_session_id(self, _value: str | None) -> None:
        pass

    def connect(self) -> None:
        """Start the background event loop for this backend."""
        if self._loop is not None:
            return

        ready = threading.Event()

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            ready.set()
            try:
                loop.run_forever()
            finally:
                for task in asyncio.all_tasks(loop):
                    task.cancel()
                loop.close()

        thread = threading.Thread(
            target=_run, name="copilot-loop", daemon=True,
        )
        thread.start()
        if not ready.wait(timeout=5) or self._loop is None:
            raise RuntimeError(
                "CopilotChatBackend: background event loop failed to start"
            )
        self._loop_thread = thread

    def _run_coro(self, coro: Coroutine[Any, Any, Any]) -> Any:
        """Submit *coro* to the background loop and block for its result."""
        if self._loop is None:
            self.connect()
        assert self._loop is not None
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    async def _destroy_session(self) -> None:
        """Drop the current session; safe to call when none exists.

        Centralized so ``_cleanup_async``, system-prompt changes, and
        the kill-and-retry path all handle errors the same way — a
        destroy failing on an already-wedged session is expected and
        must not prevent forward progress.
        """
        if self._session is None:
            return
        try:
            await self._session.destroy()
        except Exception:
            pass
        self._session = None

    async def _cleanup_async(self) -> None:
        """Tear down session + client on the backend's own loop."""
        await self._destroy_session()
        if self._client is not None:
            try:
                await self._client.stop()
            except Exception:
                pass
            self._client = None

    def disconnect(self) -> None:
        if self._loop is None:
            return
        try:
            self._run_coro(self._cleanup_async())
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._loop_thread is not None:
            self._loop_thread.join(timeout=5)
        self._loop = None
        self._loop_thread = None
        self._session = None
        self._client = None
        self._current_system_prompt = None
        self._user_messages = []

    def _build_system_prompt(self, system_prompt: str | None = None) -> str:
        from clarity_agent.app_paths import protocol_dir as _protocol_dir
        pd = _protocol_dir(self.project_dir)
        base: str = (
            "You are running the Clarity Agent framework.  Clarity "
            "helps users think through any kind of project that "
            "involves consequential decisions — a product launch, a "
            "research direction, a hiring plan, a career pivot, a "
            "policy question, a software system, or anything else "
            "where the thinking IS the work.  Do NOT assume the user "
            "is building software or writing code unless they tell "
            "you they are; let them describe the project in their own "
            "terms.\n\n"
            f"The project directory is: {self.project_dir}\n"
            f"The protocol directory is: {pd}\n\n"
            f"The clarity-agent installation directory is: {self.clarity_agent_dir}\n"
            f"Process guides are at: {self.clarity_agent_dir / 'processes'}/\n"
            f"Thinker guides are at: {self.clarity_agent_dir / 'thinkers'}/\n\n"
            "Follow the process guides exactly as written. "
            f"Create actual files in the protocol directory ({pd}) as specified."
        )
        if system_prompt:
            base += f"\n\n{system_prompt}"
        return base

    async def _ensure_client(self) -> CopilotClient:
        if self._client is not None:
            return self._client
        self._client = CopilotClient()
        await self._client.start()
        return self._client

    async def _create_session(self, model: str) -> None:
        """Build a fresh SDK session using the current system prompt.

        Sets ``self._session``.  Does not clear ``self._user_messages`` —
        callers that want history-cleared-too (system-prompt change,
        disconnect) must reset it themselves; the kill-and-retry path
        deliberately keeps history so it can replay.
        """
        client = await self._ensure_client()
        sys_msg: SystemMessageCustomizeConfig = {
            "mode": "customize",
            "content": self._current_system_prompt or "",
        }
        self._session = await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model=model,
            system_message=sys_msg,
            streaming=True,
            working_directory=str(self.project_dir),
        )

    async def _send_and_wait(self, message: str) -> str:
        """Send one message to the live session and collect the response.

        No retry — a timeout here propagates to the caller, which
        decides whether to kill + replay or give up.  Assumes
        :attr:`_session` is non-None.
        """
        assert self._session is not None, (
            "_send_and_wait called without an active session"
        )
        text_parts: list[str] = []
        done = asyncio.Event()
        # Tracks wall-clock time of the most recent SDK event.  The
        # idle-timeout helper reads this via closure; any callback
        # firing resets the clock.  List-wrapped because Python closures
        # close over names rather than values — mutating [0] is the
        # simplest way to share a single monotonic counter.
        activity_timestamp: list[float] = [time.monotonic()]
        # Coalesced status: only emit a status callback when the
        # high-level phase changes (e.g. "reasoning" → "tool:read_file"),
        # not on every SDK event.
        current_phase: list[str] = [""]

        def _emit_phase(phase: str) -> None:
            """Emit a status callback if the phase changed."""
            if phase != current_phase[0]:
                current_phase[0] = phase
                if self.on_status:
                    self.on_status(phase)

        def on_event(event: SessionEvent) -> None:
            # Any event counts as liveness, even ones we don't act on.
            # Keep this update first so the timestamp refreshes before
            # any dispatch that might raise.
            activity_timestamp[0] = time.monotonic()

            if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                # SessionEvent.data is a discriminated-union ``Data``
                # whose concrete fields depend on event.type; pyright
                # in CI doesn't see the per-type narrowing, so use
                # getattr (matches the pattern in the other branches
                # below).
                delta = getattr(event.data, "delta_content", None)
                if delta:
                    text_parts.append(delta)
                    if self.on_text_delta:
                        self.on_text_delta(delta)
            elif event.type == SessionEventType.ASSISTANT_MESSAGE:
                content = getattr(event.data, "content", None)
                if content and isinstance(content, str) and not text_parts:
                    text_parts.append(content)
                    if self.on_text_delta:
                        self.on_text_delta(content)
            elif event.type == SessionEventType.TOOL_EXECUTION_START:
                tool_name = getattr(event.data, "tool_name", None) or ""
                if self.on_tool_use:
                    self.on_tool_use(tool_name, "executing")
                # Structured callback for the transcript layer.
                # The Copilot SDK's TOOL_EXECUTION_START event carries
                # only ``tool_name`` — no id, no input dict — so we
                # synthesize a degraded :class:`ToolUseBlock`.  The
                # transcript will record that the tool was invoked
                # but the input is empty.  Honest about its limit:
                # the id is prefixed ``copilot_`` so a later replay
                # path can recognize these as non-round-trippable.
                if self.on_tool_call:
                    self.on_tool_call(ToolUseBlock(
                        id=f"copilot_{tool_name}_{id(event)}",
                        name=tool_name,
                        input={},
                    ))
                _emit_phase(f"tool:{tool_name}" if tool_name else "executing tool")
            elif event.type == SessionEventType.SESSION_IDLE:
                done.set()

            # Coalesced status for events that don't generate other
            # frontend messages — gives visibility into long-running
            # turns without flooding the UI.
            elif event.type == SessionEventType.ASSISTANT_TURN_START:
                _emit_phase("thinking")
            elif event.type in (
                SessionEventType.ASSISTANT_REASONING,
                SessionEventType.ASSISTANT_REASONING_DELTA,
            ):
                _emit_phase("reasoning")
            elif event.type == SessionEventType.TOOL_EXECUTION_COMPLETE:
                _emit_phase("thinking")
            elif event.type == SessionEventType.TOOL_EXECUTION_PROGRESS:
                pass  # stay in current tool phase, just refreshes activity_timestamp
            elif event.type == SessionEventType.SUBAGENT_STARTED:
                _emit_phase("sub-agent working")
            elif event.type == SessionEventType.SUBAGENT_COMPLETED:
                _emit_phase("thinking")
            elif event.type == SessionEventType.SESSION_COMPACTION_START:
                _emit_phase("compacting context")
            elif event.type == SessionEventType.SESSION_COMPACTION_COMPLETE:
                # Copilot's compaction event carries the full
                # summary content and a count of messages removed —
                # no transcript-file parsing needed (unlike the
                # Claude SDK path).  We record the provider's
                # summary directly on our transcript and fire UI
                # callbacks around it.
                #
                # Skip on failure or when summary content is missing
                # (defensive — the SDK marks ``success: False`` if
                # its own compaction LLM call errored; we don't want
                # to record a bogus summary in that case).
                success = getattr(event.data, "success", False)
                summary_content = getattr(event.data, "summary_content", None)
                if success and summary_content:
                    messages_removed = getattr(
                        event.data, "messages_removed", None,
                    )
                    source_turn_count = (
                        int(messages_removed)
                        if messages_removed is not None else None
                    )
                    self._record_provider_compaction(
                        summary_content, source_turn_count,
                    )

        unsubscribe = self._session.on(on_event)
        try:
            await self._session.send(message)
            await _wait_for_done_with_idle_timeout(
                done, activity_timestamp, self._idle_timeout_seconds,
            )
        finally:
            unsubscribe()

        return "".join(text_parts)

    def _record_provider_compaction(
        self, summary: str, source_turn_count: int | None,
    ) -> None:
        """Translate Copilot's compaction signal into our transcript.

        Fires the UI started/complete callbacks around the
        :meth:`Transcript.external_compaction_occurred` write so
        the orchestrator can render progress + outcome.  Without a
        transcript bound, the compaction stays purely internal to
        Copilot.
        """
        if self._transcript is None:
            return
        if self.on_compaction_started:
            self.on_compaction_started()
        result = self._transcript.external_compaction_occurred(
            summary=summary, source_turn_count=source_turn_count,
        )
        if self.on_compaction_complete:
            self.on_compaction_complete(CompactionInfo(
                summary=result.summary,
                source_turn_count=result.source_turn_count,
            ))

    async def _retry_after_kill(self, model: str) -> str:
        """Kill the wedged session, build a new one, replay, retry.

        Each retry attempt starts from a fresh SDK session and replays
        every prior user message so the SDK catches up to the same
        conversation state it was in pre-wedge.  Replays themselves
        have no retry budget — if a replay hangs, this attempt fails
        and the next one (if any) starts over from scratch.
        """
        total = self._max_rpc_retries
        turn_index = len(self._user_messages)
        replay_count = turn_index - 1
        for attempt in range(1, total + 1):
            print(
                f"  [copilot] idle timeout on turn {turn_index} — "
                f"killing session and retrying ({attempt}/{total}); "
                f"will replay {replay_count} prior turn(s)",
                file=sys.stderr, flush=True,
            )
            await self._destroy_session()
            try:
                await self._create_session(model)
                for prior in self._user_messages[:-1]:
                    await self._send_and_wait(prior)
                return await self._send_and_wait(self._user_messages[-1])
            except TimeoutError:
                if attempt >= total:
                    raise TimeoutError(
                        f"Copilot session wedged after {total} retry "
                        f"attempt(s) on turn {turn_index}; giving up"
                    ) from None
                # Fall through to the next attempt — fresh session,
                # replay from scratch.

        # Unreachable: loop always either returns or re-raises.
        raise AssertionError("retry loop exited without returning")

    async def _async_chat(
        self,
        user_message: str,
        system_prompt: str | None = None,
        *,
        model: str | None = None,
    ) -> str:
        # System-prompt change = hard reset: new session AND new
        # history (the prior messages belonged to a different session
        # and must not be replayed into this one).
        if system_prompt:
            full_prompt = self._build_system_prompt(system_prompt)
            if full_prompt != self._current_system_prompt:
                await self._destroy_session()
                self._current_system_prompt = full_prompt
                self._user_messages = []

        resolved_model = self.resolve_model(model)
        if self._session is None:
            await self._create_session(resolved_model)

        # Record the message BEFORE sending so a wedge + retry knows
        # to replay through this turn.
        self._user_messages.append(user_message)

        try:
            return await self._send_and_wait(user_message)
        except TimeoutError:
            if self._max_rpc_retries <= 0:
                raise
            return await self._retry_after_kill(resolved_model)

    def chat(
        self,
        user_message: str,
        system_prompt: str | None = None,
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,  # noqa: ARG002 — SDK manages tools
        tool_handler: ToolHandler | None = None,  # noqa: ARG002
    ) -> str:
        """Send a message and return the response."""
        return self._run_coro(
            self._async_chat(user_message, system_prompt, model=model),
        )
