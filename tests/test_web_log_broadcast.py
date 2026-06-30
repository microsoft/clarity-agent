from __future__ import annotations

import asyncio
import io
import logging
import sys

import pytest

from clarity_agent.web.log_broadcast import (
    WebLogBroadcaster,
    install_logging_broadcaster,
    install_stdio_broadcaster,
    sanitize_log_message,
)


def test_sanitize_log_message_redacts_common_token_shapes() -> None:
    message = sanitize_log_message(
        "Authorization: Bearer abc.def token=secret OPENAI_API_KEY=sk-test",
    )

    assert "abc.def" not in message
    assert "secret" not in message
    assert "sk-test" not in message
    assert "[redacted]" in message


def test_subscriber_receives_replay_and_live_events() -> None:
    async def run() -> list[dict[str, object]]:
        broadcaster = WebLogBroadcaster(default_source="backend", max_lines=5)
        broadcaster.publish("before subscribe", source="launcher")
        queue, unsubscribe = broadcaster.subscribe()
        try:
            replay = await asyncio.wait_for(queue.get(), timeout=1)
            broadcaster.publish("after subscribe", source="backend", level="warning")
            live = await asyncio.wait_for(queue.get(), timeout=1)
            return [replay, live]
        finally:
            unsubscribe()

    replay, live = asyncio.run(run())

    assert replay == {
        "type": "log",
        "source": "launcher",
        "level": "info",
        "message": "before subscribe",
    }
    assert live == {
        "type": "log",
        "source": "backend",
        "level": "warning",
        "message": "after subscribe",
    }


def test_logging_handler_publishes_records_once() -> None:
    async def run() -> dict[str, object]:
        broadcaster = WebLogBroadcaster(default_source="backend", max_lines=5)
        logger_name = "clarity_agent.tests.web_log_broadcast"
        install_logging_broadcaster(
            broadcaster,
            source="backend",
            logger_names=(logger_name,),
        )
        queue, unsubscribe = broadcaster.subscribe(replay=False)
        try:
            logger = logging.getLogger(logger_name)
            logger.warning("something happened")
            return await asyncio.wait_for(queue.get(), timeout=1)
        finally:
            unsubscribe()

    event = asyncio.run(run())

    assert event == {
        "type": "log",
        "source": "backend",
        "level": "warning",
        "message": "WARNING: something happened",
    }


def test_stdio_broadcaster_publishes_complete_stdout_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> tuple[dict[str, object], str]:
        broadcaster = WebLogBroadcaster(default_source="backend", max_lines=5)
        fake_stdout = io.StringIO()
        monkeypatch.setattr(sys, "stdout", fake_stdout)
        restore = install_stdio_broadcaster(broadcaster)
        queue, unsubscribe = broadcaster.subscribe(replay=False)
        try:
            print("terminal line")
            event = await asyncio.wait_for(queue.get(), timeout=1)
            return event, fake_stdout.getvalue()
        finally:
            unsubscribe()
            restore()

    event, terminal_output = asyncio.run(run())

    assert terminal_output == "terminal line\n"
    assert event == {
        "type": "log",
        "source": "stdout",
        "level": "info",
        "message": "terminal line",
    }


def test_stdio_broadcaster_buffers_partial_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> dict[str, object]:
        broadcaster = WebLogBroadcaster(default_source="backend", max_lines=5)
        fake_stdout = io.StringIO()
        monkeypatch.setattr(sys, "stdout", fake_stdout)
        restore = install_stdio_broadcaster(broadcaster)
        queue, unsubscribe = broadcaster.subscribe(replay=False)
        try:
            sys.stdout.write("partial")
            assert queue.empty()
            sys.stdout.write(" line\n")
            return await asyncio.wait_for(queue.get(), timeout=1)
        finally:
            unsubscribe()
            restore()

    event = asyncio.run(run())

    assert event == {
        "type": "log",
        "source": "stdout",
        "level": "info",
        "message": "partial line",
    }


def test_stdio_broadcaster_flushes_partial_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> dict[str, object]:
        broadcaster = WebLogBroadcaster(default_source="backend", max_lines=5)
        fake_stdout = io.StringIO()
        monkeypatch.setattr(sys, "stdout", fake_stdout)
        restore = install_stdio_broadcaster(broadcaster)
        queue, unsubscribe = broadcaster.subscribe(replay=False)
        try:
            sys.stdout.write("partial")
            sys.stdout.flush()
            return await asyncio.wait_for(queue.get(), timeout=1)
        finally:
            unsubscribe()
            restore()

    event = asyncio.run(run())

    assert event == {
        "type": "log",
        "source": "stdout",
        "level": "info",
        "message": "partial",
    }


def test_stdio_broadcaster_publishes_stderr_as_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> dict[str, object]:
        broadcaster = WebLogBroadcaster(default_source="backend", max_lines=5)
        fake_stderr = io.StringIO()
        monkeypatch.setattr(sys, "stderr", fake_stderr)
        restore = install_stdio_broadcaster(broadcaster)
        queue, unsubscribe = broadcaster.subscribe(replay=False)
        try:
            sys.stderr.write("terminal error\n")
            return await asyncio.wait_for(queue.get(), timeout=1)
        finally:
            unsubscribe()
            restore()

    event = asyncio.run(run())

    assert event == {
        "type": "log",
        "source": "stderr",
        "level": "info",
        "message": "terminal error",
    }
