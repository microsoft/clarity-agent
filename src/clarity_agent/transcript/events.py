"""
Structured event schema for transcript JSONL files.

Each event represents one observable thing that happened in a
conversation: a user message arrived, the assistant emitted text or
called a tool, a tool returned a result, the user changed the model,
a new SDK session was started for an existing chapter, etc.

Events are stored as one-line JSON in the ``NNNN.events.jsonl`` file
alongside their human-readable rendering in ``NNNN.md``.  The JSONL
is canonical; the markdown is derived.

Schema versioning
-----------------
Every event carries a ``schema_version`` so future changes to the
event format remain readable.  Today there's only ``"1"``.  When we
need to add a field with a behavioral change, bump the version and
let the parser dispatch on it.

Discriminated union
-------------------
Pydantic's discriminator on the ``type`` field lets us load any event
from raw JSON into the right typed class without manual dispatch:

    >>> ev = parse_event({"type": "user_turn", "timestamp": "...",
    ...                   "content": "hello"})
    >>> isinstance(ev, UserTurn)
    True

Tool-use fidelity
-----------------
The Anthropic SDK / API delivers structured tool-use blocks with
``tool_use_id``, ``name``, and ``input`` (a JSON object).  We
preserve that structure verbatim in :class:`ToolUse` so a future
"replay this chapter via the API" path can reconstruct messages
faithfully.

:class:`ToolUseText` is a *legacy-only* fallback: events produced
during migration from old timestamp-named transcripts where only the
flattened ``[Tool] name -> detail`` string was available.  New writes
always use :class:`ToolUse`.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

SCHEMA_VERSION: Literal["1"] = "1"


# ---------------------------------------------------------------------------
# Event types
#
# Each event subclasses :class:`_BaseEvent` to inherit the common fields
# (``schema_version``, ``type``, ``timestamp``) and adds its own payload.
# ``type`` is a ``Literal`` so Pydantic's discriminated-union machinery can
# select the right class when parsing.
# ---------------------------------------------------------------------------


class _BaseEvent(BaseModel):
    """Common fields on every event.

    ``timestamp`` is the wall-clock time the event was recorded, in
    ISO 8601 with timezone.  Used for display and (later) for ordering
    when merging legacy transcripts during migration.
    """

    schema_version: Literal["1"] = SCHEMA_VERSION
    type: str
    timestamp: datetime


class ChapterStarted(_BaseEvent):
    """First event in a brand-new chapter file.

    Records the metadata that used to live in the legacy markdown
    transcript header: when the chapter began, which project, and the
    backend in use at chapter open.  The backend may change later
    (recorded via :class:`SessionResume` events); this captures the
    initial state.
    """

    type: Literal["chapter_started"] = "chapter_started"
    project_dir: str
    backend: str


class SessionResume(_BaseEvent):
    """A new backend SDK session is attaching to this chapter.

    Recorded whenever the user reopens the project after the
    previously-cached SDK session was lost (expired, cleared, or
    process restarted).  The markdown renderer turns these into the
    ``## YYYY-MM-DD — backend`` sub-headings users see when scrolling
    a long chapter.
    """

    type: Literal["session_resume"] = "session_resume"
    backend: str
    # When a backend can rebuild from prior events with a structured
    # message list, this carries the new SDK session id once it's
    # assigned.  When the backend is the Claude SDK CLI (no rebuild
    # path), this stays ``None`` until the first real assistant turn
    # produces a session id we can cache.
    llm_session_id: str | None = None


class UserTurn(_BaseEvent):
    """A user message arriving from the UI (or CLI)."""

    type: Literal["user_turn"] = "user_turn"
    content: str


class AssistantText(_BaseEvent):
    """A text block emitted by the assistant.

    The SDK and API both deliver assistant output as a sequence of
    blocks: text, tool_use, more text, etc.  Each text block becomes
    one :class:`AssistantText` event so the chapter preserves the
    interleaving with tool calls in the order they actually occurred.
    """

    type: Literal["assistant_text"] = "assistant_text"
    content: str


class ToolUse(_BaseEvent):
    """The assistant invoked a tool with structured input.

    ``tool_use_id`` is the SDK/API-assigned id that links a
    :class:`ToolUse` to its eventual :class:`ToolResult`.  ``input`` is
    the structured argument dict the model produced.

    When the underlying backend is the Claude SDK CLI, the CLI
    executes built-in tools (Read, Write, Bash, etc.) internally; we
    observe these as ToolUse events but no matching ToolResult comes
    back to us — only the SDK sees the result.  That's expected and
    fine; the event still records *what the assistant tried to do*,
    which is the part useful for rebuilding context later.
    """

    type: Literal["tool_use"] = "tool_use"
    tool_use_id: str
    name: str
    input: dict[str, Any]


class ToolResult(_BaseEvent):
    """A tool returned a result, paired with a prior ToolUse by id.

    Emitted when the calling layer (e.g., the Anthropic API backend's
    tool loop) sees the result before passing it back to the model.
    Not emitted for tools the SDK CLI handles internally.
    """

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


class ToolUseText(_BaseEvent):
    """Legacy fallback: a tool call recovered from an old transcript.

    Produced only by the one-time migration that converts pre-#35
    timestamp-named ``.md`` transcripts into the new chapter format.
    The historical files captured tool calls as flattened strings
    (``[Tool] name -> detail``), so the structured ``tool_use_id`` /
    ``input`` data is unrecoverable.  Renders to markdown the same
    way the legacy transcript did.  Going forward, all new tool
    invocations write :class:`ToolUse` events instead.
    """

    type: Literal["tool_use_text"] = "tool_use_text"
    name: str
    detail: str


class ProcessStarted(_BaseEvent):
    """A named process (clarity-agent, failure-brainstorming, etc.) began.

    Marks a logical section boundary within a chapter: the user (or
    the agent itself via handoff) invoked a specific process guide.
    Renders as the ``## Process: <name>`` heading in the legacy
    markdown format.
    """

    type: Literal["process_started"] = "process_started"
    process_name: str
    # ``tier`` is the resolved tier ("default"/"deep"/"fast"/...) the
    # process was started with; ``model`` is the concrete model id
    # the tier resolved to.  Both may be ``None`` if the process
    # accepted whatever the session default was.
    tier: str | None = None
    model: str | None = None


class ModelOverride(_BaseEvent):
    """The user (or a process) overrode the active model mid-chapter.

    Different from :class:`ProcessStarted` because the override may
    persist across turns rather than scoping to one process.
    """

    type: Literal["model_override"] = "model_override"
    tier: str
    model: str


# Discriminated union of all known event types.  Adding a new event:
# (1) define the class with a ``type: Literal["new_type"]`` field,
# (2) append it here, (3) extend the markdown renderer to handle it.
Event = Annotated[
    Union[
        ChapterStarted,
        SessionResume,
        UserTurn,
        AssistantText,
        ToolUse,
        ToolResult,
        ToolUseText,
        ProcessStarted,
        ModelOverride,
    ],
    Field(discriminator="type"),
]


# Pydantic ``TypeAdapter`` lets us validate/parse an arbitrary dict
# into the right ``Event`` subtype using the discriminator.  Built
# once at import time and reused; the alternative (calling
# ``parse_obj_as`` per event) is significantly slower at scale.
_EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)


def parse_event(data: dict[str, Any]) -> Event:
    """Parse a raw dict (e.g., from ``json.loads``) into a typed Event.

    Raises :class:`pydantic.ValidationError` if the data doesn't match
    any known event schema.  Callers reading legacy JSONL should
    wrap this in a try/except and skip lines that fail rather than
    refusing to load the whole chapter.
    """
    return _EVENT_ADAPTER.validate_python(data)


def serialize_event(event: Event) -> str:
    """Serialize an Event to a single JSONL line (no trailing newline).

    The output is ``json.dumps``-compatible: stable key ordering by
    Pydantic's ``model_dump_json``, no trailing whitespace, ASCII-safe.
    Append a ``"\\n"`` at the call site when writing to a JSONL file.
    """
    # ``mode="json"`` ensures datetimes serialize as ISO 8601 strings
    # rather than as Python objects that ``json.dumps`` can't handle.
    payload = event.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
