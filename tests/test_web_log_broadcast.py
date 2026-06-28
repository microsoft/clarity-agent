from __future__ import annotations

import asyncio
import logging

from clarity_agent.web.log_broadcast import (
    WebLogBroadcaster,
    install_logging_broadcaster,
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
