"""Tests for the GitHub Copilot backend's idle-timeout + retry logic.

Two surfaces under test:

- :func:`_wait_for_done_with_idle_timeout` — the per-turn wait helper.
  Its contract is "fail only if the peer goes silent for too long";
  any SDK event resets the clock.  Exercised here with an
  :class:`asyncio.Event` standing in for ``done`` and a mutable list
  for the activity timestamp (same types the real event handler uses).

- :class:`CopilotChatBackend` retry orchestration — when a turn times
  out, the backend kills the session, builds a new one, replays every
  prior user message, and retries the wedged turn.  We mock
  :meth:`_send_and_wait`, :meth:`_create_session`, and
  :meth:`_destroy_session` so the orchestration can be exercised
  without a live Copilot SDK.

Tests use small sub-second timeouts so the whole file runs quickly.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from clarity_agent.llm.impl.github_copilot import (
    CopilotChatBackend,
    _wait_for_done_with_idle_timeout,
)


def test_returns_immediately_when_done_already_set() -> None:
    """Pre-set done → no waiting, no timeout chance."""
    async def runner() -> None:
        done = asyncio.Event()
        done.set()
        # Tiny idle timeout — would fail quickly if the helper even
        # entered its wait loop.
        await _wait_for_done_with_idle_timeout(
            done, [time.monotonic()], idle_timeout_seconds=0.01,
        )
    asyncio.run(runner())


def test_returns_when_done_fires_before_idle_timeout() -> None:
    async def runner() -> None:
        done = asyncio.Event()
        activity = [time.monotonic()]

        async def fire_done_soon() -> None:
            await asyncio.sleep(0.02)
            done.set()

        await asyncio.gather(
            _wait_for_done_with_idle_timeout(done, activity, 0.5),
            fire_done_soon(),
        )
    asyncio.run(runner())


def test_raises_timeout_when_no_activity() -> None:
    """No events, no done → TimeoutError after idle_timeout."""
    async def runner() -> None:
        done = asyncio.Event()
        # Timestamp never advances — simulate a peer that hangs before
        # emitting anything.
        activity = [time.monotonic()]
        with pytest.raises(TimeoutError, match="No peer activity"):
            await _wait_for_done_with_idle_timeout(
                done, activity, idle_timeout_seconds=0.05,
            )
    asyncio.run(runner())


def test_activity_resets_the_clock() -> None:
    """Sustained activity → helper outlasts idle_timeout without raising.

    Drives activity every 20ms with idle_timeout=50ms for 200ms total.
    A plain 50ms timeout would have fired ~3x; the idle reset makes it
    survive.  Then done is set and the helper returns cleanly.
    """
    async def runner() -> None:
        done = asyncio.Event()
        activity = [time.monotonic()]

        async def keep_alive() -> None:
            for _ in range(10):
                await asyncio.sleep(0.02)
                activity[0] = time.monotonic()
            done.set()

        await asyncio.gather(
            _wait_for_done_with_idle_timeout(
                done, activity, idle_timeout_seconds=0.05,
            ),
            keep_alive(),
        )
    asyncio.run(runner())


def test_raises_after_activity_stops() -> None:
    """Active briefly, then silent → times out, despite earlier activity.

    Validates the whole point of the idle timer: steady activity resets
    it, but when activity stops, the ceiling applies from the last
    event — not from the start of the turn.
    """
    async def runner() -> None:
        done = asyncio.Event()
        activity = [time.monotonic()]

        async def active_then_silent() -> None:
            # Nudge activity twice, then go silent.
            for _ in range(2):
                await asyncio.sleep(0.02)
                activity[0] = time.monotonic()
            # No further updates — the helper's clock should now run out.

        async def wait_and_expect_timeout() -> None:
            with pytest.raises(TimeoutError, match="No peer activity"):
                await _wait_for_done_with_idle_timeout(
                    done, activity, idle_timeout_seconds=0.05,
                )

        await asyncio.gather(
            wait_and_expect_timeout(),
            active_then_silent(),
        )
    asyncio.run(runner())


def test_error_message_includes_timeout_value() -> None:
    """Error tells the operator what threshold was tripped."""
    async def runner() -> None:
        done = asyncio.Event()
        activity = [time.monotonic()]
        with pytest.raises(TimeoutError) as exc_info:
            await _wait_for_done_with_idle_timeout(
                done, activity, idle_timeout_seconds=0.03,
            )
        assert "0s" in str(exc_info.value) or "0.0s" in str(exc_info.value)
    asyncio.run(runner())


# ---------------------------------------------------------------------------
# Retry orchestration on CopilotChatBackend
#
# We don't have a real Copilot SDK in unit tests, so we mock the three
# methods _async_chat depends on: _create_session, _destroy_session,
# and _send_and_wait.  This lets us drive the kill-and-replay logic
# precisely (control which sends "succeed" or "time out") and assert
# the right sequence of calls happens — destroy → create → replay
# every prior message → retry the wedged one.
# ---------------------------------------------------------------------------


def _make_backend(tmp_path: Path, *, max_rpc_retries: int = 1) -> CopilotChatBackend:
    """Construct a backend without touching the real Copilot SDK.

    No connect() — we never invoke the real event loop.  The tests
    drive ``_async_chat`` directly via ``asyncio.run`` and rely on
    method mocks rather than the background loop.
    """
    return CopilotChatBackend(
        project_dir=tmp_path,
        clarity_agent_dir=tmp_path,
        idle_timeout_seconds=1.0,
        max_rpc_retries=max_rpc_retries,
    )


def _install_mocks(
    backend: CopilotChatBackend,
    *,
    send_side_effects: list[Any],
) -> tuple[AsyncMock, AsyncMock, AsyncMock]:
    """Replace the three SDK touchpoints with AsyncMock instances.

    ``send_side_effects`` is consumed one entry per ``_send_and_wait``
    call — strings become returned text; exceptions raise.  Lets a
    test script "first send hangs, second succeeds" without needing
    timing.
    """
    send = AsyncMock(side_effect=send_side_effects)
    create = AsyncMock(side_effect=lambda _model: _set_session(backend))
    destroy = AsyncMock(side_effect=lambda: _clear_session(backend))
    backend._send_and_wait = send  # type: ignore[method-assign]
    backend._create_session = create  # type: ignore[method-assign]
    backend._destroy_session = destroy  # type: ignore[method-assign]
    return send, create, destroy


def _set_session(backend: CopilotChatBackend) -> None:
    # Sentinel object — _async_chat only checks `is None`, never calls methods.
    backend._session = object()  # type: ignore[assignment]


def _clear_session(backend: CopilotChatBackend) -> None:
    backend._session = None


# ---- import Any after defining helpers (kept here for locality) ----
from typing import Any  # noqa: E402


def test_async_chat_returns_immediately_on_success(tmp_path: Path) -> None:
    """No timeout → no retry, no destroy/recreate ceremony."""
    backend = _make_backend(tmp_path)
    backend._current_system_prompt = "sys"
    send, create, destroy = _install_mocks(
        backend, send_side_effects=["the response"],
    )

    result = asyncio.run(backend._async_chat("hello"))

    assert result == "the response"
    assert send.await_count == 1
    assert create.await_count == 1  # initial session creation
    assert destroy.await_count == 0
    assert backend._user_messages == ["hello"]


def test_async_chat_retries_after_first_timeout(tmp_path: Path) -> None:
    """First send wedges, retry succeeds → destroy + create + replay 0 + retry."""
    backend = _make_backend(tmp_path, max_rpc_retries=1)
    backend._current_system_prompt = "sys"
    send, create, destroy = _install_mocks(
        backend, send_side_effects=[
            TimeoutError("idle"),  # initial send
            "recovered response",  # retry of the same message in fresh session
        ],
    )

    result = asyncio.run(backend._async_chat("hello"))

    assert result == "recovered response"
    assert send.await_count == 2
    assert destroy.await_count == 1
    assert create.await_count == 2  # initial + after-kill
    # History stays intact across the retry — same message, replayed once.
    assert backend._user_messages == ["hello"]


def test_async_chat_replays_full_history_on_retry(tmp_path: Path) -> None:
    """Mid-conversation wedge → replay every prior message in order, then retry."""
    backend = _make_backend(tmp_path, max_rpc_retries=1)
    backend._current_system_prompt = "sys"

    # Three successful turns, then turn 4 wedges.
    # On retry: destroy + create + send turns 1, 2, 3 (replays), then
    # send turn 4 again successfully.
    send, _, destroy = _install_mocks(
        backend, send_side_effects=[
            "r1", "r2", "r3",          # initial three turns
            TimeoutError("wedge"),     # turn 4 first attempt
            "replay-1", "replay-2", "replay-3",  # replays in fresh session
            "r4",                       # turn 4 retry
        ],
    )

    asyncio.run(backend._async_chat("turn 1"))
    asyncio.run(backend._async_chat("turn 2"))
    asyncio.run(backend._async_chat("turn 3"))
    result = asyncio.run(backend._async_chat("turn 4"))

    assert result == "r4"
    assert backend._user_messages == ["turn 1", "turn 2", "turn 3", "turn 4"]
    # 3 normal sends + 1 wedge + 3 replays + 1 retry = 8.
    assert send.await_count == 8
    # Sends in order — the replay phase repeats turns 1, 2, 3 verbatim.
    sent_messages = [c.args[0] for c in send.await_args_list]
    assert sent_messages == [
        "turn 1", "turn 2", "turn 3",       # original
        "turn 4",                            # wedged
        "turn 1", "turn 2", "turn 3",       # replay
        "turn 4",                            # retry
    ]
    assert destroy.await_count == 1


def test_async_chat_gives_up_after_max_retries(tmp_path: Path) -> None:
    """Persistent wedge → final TimeoutError after exhausting the budget."""
    backend = _make_backend(tmp_path, max_rpc_retries=2)
    backend._current_system_prompt = "sys"
    # Every send hangs — initial + 2 retries = 3 total send attempts at
    # the wedged message.
    send, _, destroy = _install_mocks(
        backend, send_side_effects=[
            TimeoutError("wedge"),
            TimeoutError("wedge"),
            TimeoutError("wedge"),
        ],
    )

    with pytest.raises(TimeoutError, match="wedged after 2 retry"):
        asyncio.run(backend._async_chat("hello"))

    # 1 initial + 2 retry attempts = 3 sends.  No replays — history was
    # empty before the call.
    assert send.await_count == 3
    # One destroy per retry attempt.
    assert destroy.await_count == 2


def test_async_chat_no_retry_when_budget_zero(tmp_path: Path) -> None:
    """max_rpc_retries=0 → disable retry entirely (original behavior)."""
    backend = _make_backend(tmp_path, max_rpc_retries=0)
    backend._current_system_prompt = "sys"
    send, _, destroy = _install_mocks(
        backend, send_side_effects=[TimeoutError("wedge")],
    )

    with pytest.raises(TimeoutError, match="No peer activity|wedge"):
        asyncio.run(backend._async_chat("hello"))

    assert send.await_count == 1
    assert destroy.await_count == 0


def test_replay_failure_consumes_a_retry_attempt(tmp_path: Path) -> None:
    """If a replay hangs, that whole attempt fails; next attempt restarts."""
    backend = _make_backend(tmp_path, max_rpc_retries=2)
    backend._current_system_prompt = "sys"

    # Setup: send turn 1 successfully, then turn 2 wedges.
    # Attempt 1 of retry: replay turn 1 hangs → attempt 1 fails.
    # Attempt 2 of retry: replay turn 1 succeeds, retry turn 2 succeeds.
    send, _, destroy = _install_mocks(
        backend, send_side_effects=[
            "r1",                       # initial turn 1
            TimeoutError("wedge"),      # initial turn 2 wedges
            TimeoutError("replay hangs"),  # attempt 1: replay turn 1
            "replay-r1",                # attempt 2: replay turn 1
            "r2",                       # attempt 2: retry turn 2
        ],
    )

    asyncio.run(backend._async_chat("turn 1"))
    result = asyncio.run(backend._async_chat("turn 2"))

    assert result == "r2"
    # 1 initial t1 + 1 wedged t2 + 1 failed-replay + 1 successful-replay + 1 retry = 5.
    assert send.await_count == 5
    # Two destroys: one per retry attempt.
    assert destroy.await_count == 2


def test_history_resets_on_system_prompt_change(tmp_path: Path) -> None:
    """A different system prompt → fresh session AND fresh history.

    Otherwise the next retry would replay messages that belonged to a
    different conversation entirely.
    """
    backend = _make_backend(tmp_path)
    send, create, destroy = _install_mocks(
        backend, send_side_effects=["r1", "r2"],
    )

    asyncio.run(backend._async_chat("hello", system_prompt="prompt A"))
    assert backend._user_messages == ["hello"]
    assert backend._current_system_prompt is not None
    first_prompt = backend._current_system_prompt

    asyncio.run(backend._async_chat("world", system_prompt="prompt B"))
    # New session built; history reflects only the post-change message.
    assert backend._user_messages == ["world"]
    assert backend._current_system_prompt != first_prompt
    # Destroy fires on every prompt change (even the first, when
    # there's no session yet — the no-op early-return still counts as
    # a call from the mock's perspective).  Create fires twice:
    # once per distinct prompt.
    assert destroy.await_count == 2
    assert create.await_count == 2


def test_history_preserved_across_same_system_prompt(tmp_path: Path) -> None:
    """Identical system prompts (or none) keep the conversation going."""
    backend = _make_backend(tmp_path)
    _install_mocks(backend, send_side_effects=["r1", "r2", "r3"])

    asyncio.run(backend._async_chat("a", system_prompt="same"))
    asyncio.run(backend._async_chat("b", system_prompt="same"))
    asyncio.run(backend._async_chat("c"))  # no system_prompt — no reset

    assert backend._user_messages == ["a", "b", "c"]
