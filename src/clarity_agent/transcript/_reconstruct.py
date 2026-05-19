"""
Internal: rebuild conversation context for the backend from a chapter's events.

Used by :class:`Transcript`'s ``context_summary`` and
``anthropic_messages`` methods.  Not part of the public API —
callers should use the :class:`Transcript` methods.

There are two distinct backend shapes to support:

1. **Claude SDK CLI backend** (the default when no ``ANTHROPIC_API_KEY``
   is set; used inside Claude Code).  The SDK exposes ``resume=session_id``
   for continuing a conversation but has *no* API to seed a fresh
   session with a list of prior messages.  When the cached session id
   is lost (process restart, SDK eviction, version change), the best
   we can do is start a brand-new SDK session with the prior
   conversation rendered as context and prepended to the first user
   message or system prompt.

   For this path, :func:`build_context_summary` produces a markdown
   blob — readable to the model, similar to the legacy
   ``_load_transcript_context`` output but operating on structured
   events instead of raw markdown files.

2. **Anthropic API backend** (used when ``ANTHROPIC_API_KEY`` is
   available, see :file:`llm/impl/claude_sdk.py` ``_arun_tool_loop_api``).
   Here we *do* control the message list and could in principle
   replay the chapter as faithful API messages, including structured
   ``tool_use`` / ``tool_result`` blocks.

   :func:`build_anthropic_messages` is the stub for this path; it
   produces the correct shape but is **not yet wired into a backend
   that consumes it**.  Used today only for testing the conversion
   logic; will become the entry point for Phase 2 compaction
   (which can re-emit a compacted-chapter message list).

In both cases the input is the chapter's event stream; the output
differs in shape and fidelity.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from clarity_agent.transcript._render import render_event
from clarity_agent.transcript.events import (
    AssistantText,
    CompactionSummary,
    Event,
    ToolResult,
    ToolUse,
    ToolUseText,
    UserTurn,
)

# Character budget for the SDK-path context summary.  Matches the
# legacy ``_load_transcript_context`` cap in
# ``web/session_manager.py:211``.  Rough rule of thumb at GPT-style
# tokenization: 50K chars ≈ 12-15K tokens, comfortably under any
# current context window even after the rest of the system prompt
# is added.
DEFAULT_MAX_CONTEXT_CHARS = 50_000

# Intro paragraph prepended to the rendered events when building a
# context summary.  Explains to the model that this is *not* fresh
# user input — it's a recap.  Wording mirrors what
# ``_load_transcript_context`` produces today so the model behaves
# similarly post-cutover.
_CONTEXT_INTRO = (
    "Below is the prior conversation on this project. Continue from "
    "there — the user has not retyped this; they're picking up "
    "where you left off.\n\n"
)


def build_context_summary(
    events: Iterable[Event],
    *,
    max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> str | None:
    """Render an event stream to a context-recap markdown blob.

    Selection strategy: render events into markdown fragments, walk
    them in reverse chronological order, keep accumulating until the
    character budget is exhausted, then emit in original order.
    The most recent turns are guaranteed to fit; oldest ones may be
    elided with a ``[earlier turns omitted]`` note.

    Returns ``None`` when the iterable yields no events — callers can
    distinguish "fresh chapter, no context to inject" from "have
    context, please inject."
    """
    # Materialize the rendered fragments alongside their events so we
    # don't render twice.  For a typical chapter (hundreds of events,
    # each rendering to ~50-500 chars) this stays well under a meg.
    fragments: list[str] = [render_event(e) for e in events]
    if not fragments:
        return None

    # Walk newest-to-oldest, taking until the budget is exhausted.
    selected: list[str] = []
    total = len(_CONTEXT_INTRO)
    truncated = False
    for frag in reversed(fragments):
        if total + len(frag) > max_chars:
            # We're about to bust the budget; everything from here
            # back (= earlier) gets elided.
            truncated = total > len(_CONTEXT_INTRO) or len(frag) > max_chars
            break
        selected.append(frag)
        total += len(frag)
    # ``selected`` is newest-first; flip to chronological for the
    # rendered output so the model reads the conversation forward.
    selected.reverse()

    parts: list[str] = [_CONTEXT_INTRO]
    if truncated:
        parts.append("*[earlier turns omitted]*\n\n")
    parts.extend(selected)
    return "".join(parts)


def build_anthropic_messages(events: Iterable[Event]) -> list[dict[str, Any]]:
    """Convert a chapter's event stream to an Anthropic API messages list.

    Used by the Anthropic-API backend path (and, in Phase 2, by the
    compaction pipeline which re-emits a shortened message history).
    Produces the structured shape ``messages.create(messages=[...])``
    expects:

    * ``UserTurn`` → ``{"role": "user", "content": str}``
    * Run of ``AssistantText`` / ``ToolUse`` since the last
      ``UserTurn`` → one ``{"role": "assistant", "content": [<blocks>]}``
      message with text + tool_use blocks in their original order.
    * Run of ``ToolResult`` events → one ``{"role": "user", "content":
      [<tool_result blocks>]}`` message paired with the prior
      assistant tool_use ids.

    Metadata events (``ChapterStarted``, ``SessionResume``,
    ``ProcessStarted``, ``ModelOverride``) are skipped — they don't
    correspond to messages in the conversation.

    :class:`CompactionSummary` events become a single labeled user
    message at their position in the stream, so the rebuilt
    conversation includes the digest of the prior chapter as
    visible context.

    Legacy ``ToolUseText`` events become ``tool_use`` blocks with
    synthesized ids; the ``input`` is a single ``{"detail": ...}``
    field carrying the original string.  These never round-trip back
    through the API faithfully — they exist only so the rendered
    history shows what tools the assistant invoked, with a clearly
    marked "legacy" structure.
    """
    messages: list[dict[str, Any]] = []
    # Accumulator for the current assistant message's content blocks.
    # Flushed (emitted as a message) when we hit a UserTurn or
    # ToolResult that signals a new role boundary.
    assistant_blocks: list[dict[str, Any]] = []
    # Accumulator for consecutive tool_result blocks (one Anthropic
    # message can carry multiple results).
    tool_result_blocks: list[dict[str, Any]] = []
    legacy_tool_counter = 0  # for synthesizing tool_use_ids for legacy events

    def flush_assistant() -> None:
        if assistant_blocks:
            messages.append({"role": "assistant", "content": list(assistant_blocks)})
            assistant_blocks.clear()

    def flush_tool_results() -> None:
        if tool_result_blocks:
            messages.append({"role": "user", "content": list(tool_result_blocks)})
            tool_result_blocks.clear()

    for event in events:
        if isinstance(event, CompactionSummary):
            # Compaction summary: emitted as a clearly-labeled user
            # message at the start of the rebuilt conversation.  The
            # Anthropic API has no "summary" role, so prefixing with
            # an explicit label is the cleanest way to signal to the
            # model that the content is recap, not fresh user input.
            # A future refinement could surface this via the system
            # prompt instead, but that requires the caller to take
            # responsibility for the system slot — out of scope for
            # what this function does in isolation.
            flush_assistant()
            flush_tool_results()
            messages.append({
                "role": "user",
                "content": (
                    f"[Summary of prior conversation "
                    f"(chapter {event.source_chapter}, "
                    f"{event.source_turn_count} turns):]\n\n"
                    f"{event.summary}"
                ),
            })
        elif isinstance(event, UserTurn):
            # Boundary: any pending assistant or tool-result content
            # must be emitted before the user turn that follows it.
            flush_assistant()
            flush_tool_results()
            messages.append({"role": "user", "content": event.content})
        elif isinstance(event, AssistantText):
            # Tool results from a prior assistant turn (if any) must
            # be flushed before we open a new assistant message.
            flush_tool_results()
            assistant_blocks.append({"type": "text", "text": event.content})
        elif isinstance(event, ToolUse):
            flush_tool_results()
            assistant_blocks.append({
                "type": "tool_use",
                "id": event.tool_use_id,
                "name": event.name,
                "input": event.input,
            })
        elif isinstance(event, ToolUseText):
            # Legacy fallback: structured fields aren't available, so
            # synthesize an id and stash the detail string under a
            # ``detail`` key.  Flagged as legacy via the id prefix.
            flush_tool_results()
            legacy_tool_counter += 1
            assistant_blocks.append({
                "type": "tool_use",
                "id": f"legacy_{legacy_tool_counter}",
                "name": event.name,
                "input": {"detail": event.detail},
            })
        elif isinstance(event, ToolResult):
            # Results follow their tool_use; close out the assistant
            # block they belong to first.
            flush_assistant()
            tool_result_blocks.append({
                "type": "tool_result",
                "tool_use_id": event.tool_use_id,
                "content": event.content,
                "is_error": event.is_error,
            })
        # Other event types (ChapterStarted, SessionResume,
        # ProcessStarted, ModelOverride) are metadata — they don't
        # generate API messages.  Intentionally fall through with no
        # action.

    # End of stream: emit any pending blocks.
    flush_assistant()
    flush_tool_results()
    return messages
