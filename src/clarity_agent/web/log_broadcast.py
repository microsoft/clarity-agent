"""Thread-safe log broadcaster for WebSocket clients."""

from __future__ import annotations

import asyncio
import logging
import re
import sys
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


@dataclass(frozen=True)
class _StreamPublisher:
    broadcaster: WebLogBroadcaster
    source: str
    level: str


class BroadcastStream:
    """Text stream wrapper that tees terminal output to log subscribers."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self._publishers: dict[int, _StreamPublisher] = {}
        self._line_buffer = ""
        self._lock = threading.Lock()

    @property
    def wrapped(self) -> Any:
        return self._stream

    @property
    def has_publishers(self) -> bool:
        return bool(self._publishers)

    def add_publisher(
        self,
        broadcaster: WebLogBroadcaster,
        *,
        source: str,
        level: str,
    ) -> None:
        with self._lock:
            self._publishers[id(broadcaster)] = _StreamPublisher(
                broadcaster=broadcaster,
                source=source,
                level=level,
            )

    def remove_publisher(self, broadcaster: WebLogBroadcaster) -> None:
        with self._lock:
            self._publishers.pop(id(broadcaster), None)

    def write(self, text: str) -> int:
        written = self._stream.write(text)
        self._publish(text)
        return written

    def flush(self) -> None:
        self._stream.flush()
        self.flush_pending()

    def flush_pending(self) -> None:
        with self._lock:
            if not self._line_buffer:
                return
            line = self._line_buffer
            self._line_buffer = ""
            publishers = list(self._publishers.values())

        for publisher in publishers:
            publisher.broadcaster.publish(
                line,
                source=publisher.source,
                level=publisher.level,
            )

    def _publish(self, text: str) -> None:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        with self._lock:
            buffered = self._line_buffer + normalized
            lines = buffered.split("\n")
            self._line_buffer = lines.pop()
            publishers = list(self._publishers.values())

        for line in lines:
            for publisher in publishers:
                publisher.broadcaster.publish(
                    line,
                    source=publisher.source,
                    level=publisher.level,
                )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def install_stdio_broadcaster(
    broadcaster: WebLogBroadcaster,
    *,
    stdout_source: str = "stdout",
    stderr_source: str = "stderr",
) -> Callable[[], None]:
    """Mirror process stdout and stderr into a broadcaster until restored."""
    restore_stdout = _install_stream_broadcaster(
        "stdout",
        broadcaster,
        source=stdout_source,
        level="info",
    )
    restore_stderr = _install_stream_broadcaster(
        "stderr",
        broadcaster,
        source=stderr_source,
        level="info",
    )

    def restore() -> None:
        restore_stdout()
        restore_stderr()

    return restore


def _install_stream_broadcaster(
    stream_name: str,
    broadcaster: WebLogBroadcaster,
    *,
    source: str,
    level: str,
) -> Callable[[], None]:
    current = getattr(sys, stream_name)
    if isinstance(current, BroadcastStream):
        stream = current
    else:
        stream = BroadcastStream(current)
        setattr(sys, stream_name, stream)

    stream.add_publisher(broadcaster, source=source, level=level)

    def restore() -> None:
        active = getattr(sys, stream_name)
        if active is not stream:
            return
        stream.flush_pending()
        stream.remove_publisher(broadcaster)
        if not stream.has_publishers:
            setattr(sys, stream_name, stream.wrapped)

    return restore


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
