"""Thread-safe log broadcaster for WebSocket clients."""

from __future__ import annotations

import asyncio
import logging
import re
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_MAX_LOG_CHARS = 1_200
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(authorization\s*:\s*bearer\s+)[^\s]+", re.IGNORECASE), r"\1[redacted]"),
    (re.compile(r"((?:api[_-]?key|token|secret)\s*[=:]\s*)[^\s&]+", re.IGNORECASE), r"\1[redacted]"),
    (re.compile(r"((?:OPENAI|ANTHROPIC|AZURE|GITHUB|GH)_[A-Z0-9_]*KEY=)[^\s]+"), r"\1[redacted]"),
    (re.compile(r"((?:GITHUB|GH|CLAUDE|COPILOT)_[A-Z0-9_]*TOKEN=)[^\s]+"), r"\1[redacted]"),
)


@dataclass(frozen=True)
class _Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[dict[str, Any]]


def sanitize_log_message(message: str) -> str:
    """Strip control sequences, redact obvious secrets, and bound length."""
    cleaned = _ANSI_RE.sub("", message).strip()
    for pattern, replacement in _SECRET_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    if len(cleaned) > _MAX_LOG_CHARS:
        cleaned = f"{cleaned[: _MAX_LOG_CHARS - 3]}..."
    return cleaned


class WebLogBroadcaster:
    """Fan out backend log events to any active WebSocket subscribers."""

    def __init__(self, *, default_source: str = "backend", max_lines: int = 200) -> None:
        self.default_source = default_source
        self._buffer: deque[dict[str, Any]] = deque(maxlen=max_lines)
        self._subscribers: dict[int, _Subscriber] = {}
        self._lock = threading.Lock()
        self._next_token = 0

    def publish(
        self,
        message: str,
        *,
        source: str | None = None,
        level: str = "info",
    ) -> None:
        """Publish one log line to the replay buffer and live subscribers."""
        cleaned = sanitize_log_message(message)
        if not cleaned:
            return
        event = {
            "type": "log",
            "source": source or self.default_source,
            "level": level.lower(),
            "message": cleaned,
        }
        with self._lock:
            self._buffer.append(event)
            subscribers = list(self._subscribers.values())
        for subscriber in subscribers:
            subscriber.loop.call_soon_threadsafe(subscriber.queue.put_nowait, event)

    def subscribe(
        self,
        *,
        replay: bool = True,
    ) -> tuple[asyncio.Queue[dict[str, Any]], Callable[[], None]]:
        """Subscribe the current event loop to future events."""
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        with self._lock:
            token = self._next_token
            self._next_token += 1
            self._subscribers[token] = _Subscriber(loop=loop, queue=queue)
            replay_events = list(self._buffer) if replay else []

        for event in replay_events:
            queue.put_nowait(event)

        def unsubscribe() -> None:
            with self._lock:
                self._subscribers.pop(token, None)

        return queue, unsubscribe


class BroadcastLogHandler(logging.Handler):
    """Logging handler that forwards records to a WebLogBroadcaster."""

    def __init__(self, broadcaster: WebLogBroadcaster, *, source: str) -> None:
        super().__init__()
        self.broadcaster = broadcaster
        self.source = source
        self.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.broadcaster.publish(
                self.format(record),
                source=self.source,
                level=record.levelname.lower(),
            )
        except Exception:
            self.handleError(record)


def install_logging_broadcaster(
    broadcaster: WebLogBroadcaster,
    *,
    source: str = "backend",
    logger_names: tuple[str, ...] = ("uvicorn.access", "uvicorn.error", "clarity_agent"),
) -> None:
    """Attach a broadcaster handler to selected Python loggers once."""
    marker = "_clarity_web_log_broadcaster_id"
    broadcaster_id = id(broadcaster)
    for name in logger_names:
        logger = logging.getLogger(name)
        if any(
            getattr(handler, marker, None) == broadcaster_id
            for handler in logger.handlers
        ):
            continue
        handler = BroadcastLogHandler(broadcaster, source=source)
        setattr(handler, marker, broadcaster_id)
        logger.addHandler(handler)
