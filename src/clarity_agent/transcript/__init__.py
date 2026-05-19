"""
Conversation thread persistence (chapters + structured events).

A *thread* is the user's persistent conversation with Clarity for a
project.  It is organized into ordered *chapters*; each chapter is a
file pair on disk under ``.clarity-protocol/transcripts/``:

* ``NNNN.events.jsonl`` — canonical, structured event log (source of
  truth).  One JSON object per line, discriminated by ``type``.
* ``NNNN.md`` — human-readable rendering, written synchronously beside
  the JSONL.  Can be regenerated from the JSONL if it drifts.

The current chapter is implicitly the highest-numbered file pair.
Older chapters are read-only.  When the user starts a new chapter
the next-numbered pair is opened; nothing is ever overwritten.

Public API
----------
Only two things are exported from this package:

* :class:`Transcript` — the binding of a project directory to its
  conversation thread.  Use it to enumerate chapters, read events,
  write events, start a new chapter, and rebuild conversation
  context for the backend.  See its docstring for the lifecycle
  pattern (construction is cheap; file handles only exist while
  open).

* Event types and helpers from :mod:`.events` — :class:`UserTurn`,
  :class:`AssistantText`, :class:`ToolUse`, etc., plus the
  :data:`Event` type alias and :func:`parse_event` /
  :func:`serialize_event` for tests and migration tooling.

The rest (rendering, JSONL parsing, file-handle management,
reconstruction algorithms) is private to this package and lives in
``_*.py`` files / inside ``transcript.py``.

See GitHub issue #35 and the design comment at
https://github.com/microsoft/clarity-agent/issues/35#issuecomment-4455572128.
"""

from clarity_agent.transcript._migrate import migrate_legacy_transcripts
from clarity_agent.transcript.events import (
    AssistantText,
    ChapterStarted,
    CompactionSummary,
    Event,
    ModelOverride,
    ProcessStarted,
    SessionResume,
    ToolResult,
    ToolUse,
    ToolUseText,
    UserTurn,
    parse_event,
    serialize_event,
)
from clarity_agent.transcript.transcript import CompactionResult, Transcript

__all__ = [
    # The headline class.
    "Transcript",
    "CompactionResult",
    # Event types — needed by any caller that writes events.
    "AssistantText",
    "ChapterStarted",
    "CompactionSummary",
    "Event",
    "ModelOverride",
    "ProcessStarted",
    "SessionResume",
    "ToolResult",
    "ToolUse",
    "ToolUseText",
    "UserTurn",
    # Low-level event helpers — for tests and the legacy-transcript
    # migration tooling.
    "migrate_legacy_transcripts",
    "parse_event",
    "serialize_event",
]
