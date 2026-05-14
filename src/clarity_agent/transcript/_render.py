"""
Internal: render structured events to human-readable markdown.

Used by :class:`Transcript`'s writer to produce the ``NNNN.md``
sidecar alongside each JSONL append.  Not part of the public API —
callers should reach :class:`Transcript` for any rendering they need
(currently exposed indirectly via ``Transcript.context_summary``).

Each event renders to a self-contained markdown fragment.
Renderings are deliberately *stateless* — the fragment for event N
doesn't depend on event N-1.  This keeps the writer simple and
means the markdown can be regenerated from JSONL with a pure
``"".join(render_event(e) for e in events)``.

Style notes
-----------
The format intentionally echoes the legacy pre-#35 transcripts
(``**User:**``, ``**Assistant:**``, ``    [Tool] name -> detail``) so
migrated chapters look familiar and existing user habits (grepping
for ``**User:**``, etc.) still work.  Tool inputs are rendered to a
short string via the same ``extract_tool_detail`` helper the legacy
write path used; the structured form lives in the JSONL only.

Statelessness has one user-visible cost: when an assistant turn
contains multiple text blocks interleaved with tool calls, each text
block re-prints ``**Assistant:**``.  In practice this is fine — the
prefix simply reads as a "speaker label" on each block, similar to a
play script.  A future renderer could batch consecutive same-speaker
events; for v1 we accept the small redundancy in exchange for
trivial reconstruction logic.
"""

from __future__ import annotations

from clarity_agent.llm.client import extract_tool_detail, truncate
from clarity_agent.transcript.events import (
    AssistantText,
    ChapterStarted,
    Event,
    ModelOverride,
    ProcessStarted,
    SessionResume,
    ToolResult,
    ToolUse,
    ToolUseText,
    UserTurn,
)


def render_event(event: Event) -> str:
    """Return the markdown fragment for ``event``.

    Every fragment ends with appropriate trailing whitespace so the
    next fragment can be appended without extra logic.  Concatenating
    all fragments in order produces a complete, well-formed chapter
    markdown.
    """
    # Dispatch by exact class.  isinstance ordering matters when types
    # are subclasses; our event types are all siblings under
    # ``_BaseEvent``, so the order below is just by frequency.
    if isinstance(event, UserTurn):
        return _render_user_turn(event)
    if isinstance(event, AssistantText):
        return _render_assistant_text(event)
    if isinstance(event, ToolUse):
        return _render_tool_use(event)
    if isinstance(event, ToolUseText):
        return _render_tool_use_text(event)
    if isinstance(event, ToolResult):
        return _render_tool_result(event)
    if isinstance(event, ChapterStarted):
        return _render_chapter_started(event)
    if isinstance(event, SessionResume):
        return _render_session_resume(event)
    if isinstance(event, ProcessStarted):
        return _render_process_started(event)
    if isinstance(event, ModelOverride):
        return _render_model_override(event)
    # Should be unreachable given the discriminated union, but a
    # graceful fallback keeps the file readable even if a future
    # event type slips through unhandled.
    return f"<!-- unrenderable event: {type(event).__name__} -->\n\n"


def _render_user_turn(event: UserTurn) -> str:
    return f"**User:** {event.content}\n\n"


def _render_assistant_text(event: AssistantText) -> str:
    return f"**Assistant:** {event.content}\n\n"


def _render_tool_use(event: ToolUse) -> str:
    # ``extract_tool_detail`` flattens the structured input to a
    # short readable string (e.g., ``Read -> /path/to/file``).
    # ``truncate`` caps long details so massive Bash outputs don't
    # bloat the rendered markdown — the full structured ``input``
    # is preserved in the JSONL anyway.
    detail = truncate(extract_tool_detail(event.name, event.input))
    return f"    [Tool] {event.name} -> {detail}\n"


def _render_tool_use_text(event: ToolUseText) -> str:
    # Legacy migration shape: the detail was already a flat string in
    # the pre-#35 transcript, so we render it verbatim.  Matches the
    # ToolUse rendering exactly so readers can't tell the two apart
    # visually — only the JSONL distinguishes them.
    return f"    [Tool] {event.name} -> {truncate(event.detail)}\n"


def _render_tool_result(event: ToolResult) -> str:
    # The legacy format never recorded tool results inline; the SDK
    # CLI handled them internally and they were invisible.  Under the
    # new schema, when we *do* see a result (Anthropic API tool-loop
    # path), surface it briefly so the markdown reflects the actual
    # turn structure.  Tagged with the tool_use_id so users can
    # match it to a prior tool call.
    prefix = "      [Result"
    if event.is_error:
        prefix += " ERROR"
    return f"{prefix}] {truncate(event.content)}\n"


def _render_chapter_started(event: ChapterStarted) -> str:
    # First lines of a brand-new chapter file.  Includes the kind of
    # metadata the legacy transcripts put in their header block.
    return (
        "# Chapter\n\n"
        f"**Started:** {event.timestamp.isoformat()}\n"
        f"**Project:** {event.project_dir}\n"
        f"**Backend:** {event.backend}\n\n"
        "---\n\n"
    )


def _render_session_resume(event: SessionResume) -> str:
    # Sub-heading marking a fresh attach to this chapter — gives the
    # reader a visible "I came back the next day with a different
    # model" boundary without ending the chapter.  Date-only (not
    # full timestamp) keeps the heading short; the full datetime is
    # still in the JSONL.
    date_str = event.timestamp.date().isoformat()
    return f"## {date_str} — {event.backend}\n\n"


def _render_process_started(event: ProcessStarted) -> str:
    # Process boundary heading.  Tier/model only included when they
    # were explicitly set — matches the legacy "**Model override:**"
    # line's conditional rendering.
    out = f"## Process: {event.process_name}\n\n"
    if event.tier and event.tier != "default" and event.model:
        out += f"**Model override:** {event.model} (tier: {event.tier})\n\n"
    return out


def _render_model_override(event: ModelOverride) -> str:
    return f"**Model override:** {event.model} (tier: {event.tier})\n\n"
