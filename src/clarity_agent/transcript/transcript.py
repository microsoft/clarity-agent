"""
The :class:`Transcript` — one project's persistent conversation thread.

This is the public entry point for everything transcript-related.
Bind it to a project directory once and use the methods to enumerate
chapters, read events, write events, and rebuild conversation
context for the backend.

A *transcript* is the ordered set of *chapters* under
``<project>/.clarity-protocol/transcripts/``.  Each chapter is a
file pair:

* ``NNNN.events.jsonl`` — canonical structured event log (source of
  truth).  One JSON object per line, discriminated by ``type``.
* ``NNNN.md`` — human-readable rendering, written synchronously
  alongside the JSONL.

The current chapter is implicitly the highest-numbered one.  Older
chapters are read-only.  :meth:`start_new_chapter` rolls over to a
fresh chapter file; nothing is ever overwritten.

Construction is cheap — no I/O.  File handles only exist between
the first :meth:`write` (or :meth:`start_new_chapter`) call and the
matching :meth:`close`.  Use :class:`Transcript` as a context
manager for guaranteed cleanup::

    with Transcript(project_dir) as t:
        t.write(UserTurn(...))
        t.write(AssistantText(...))
        # ... t.close() runs on scope exit ...

Or hold it open across a long-running session (e.g., from
:class:`WebSessionAdapter`) and ``close()`` explicitly when the
session ends.

The rest of this module is internal: path conventions, JSONL
parsing, the per-chapter writer with its file handles + lock.  None
of it is exported from :mod:`clarity_agent.transcript` — callers
talk to :class:`Transcript`.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any

from pydantic import ValidationError

from clarity_agent.transcript._reconstruct import (
    DEFAULT_MAX_CONTEXT_CHARS,
    build_anthropic_messages,
    build_context_summary,
)
from clarity_agent.transcript._render import render_event
from clarity_agent.transcript.events import (
    CompactionSummary,
    Event,
    parse_event,
    serialize_event,
)

_LOG = logging.getLogger(__name__)


@dataclass
class CompactionResult:
    """Outcome of a compaction run.

    Returned by :meth:`Transcript.compact_with_summarizer` and
    :meth:`Transcript.external_compaction_occurred` so the caller
    has everything it needs to signal the UI uniformly regardless
    of which path produced the summary.

    Attributes:
        summary: The summary text that was stored on the new
            chapter's :class:`CompactionSummary` event.
        source_chapter: The chapter that was just archived.
        source_turn_count: How many message-shaped events the
            summary covers.
        new_chapter: The chapter the conversation has rolled over
            into.  Subsequent writes append here.
    """

    summary: str
    source_chapter: int
    source_turn_count: int
    new_chapter: int


# ---------------------------------------------------------------------------
# Chapter file conventions
#
# Internal: callers never deal with these names directly.  Kept here
# rather than in a separate module because (a) they're small, (b) they're
# tightly coupled to Transcript's logic, and (c) they're not part of the
# public API.
# ---------------------------------------------------------------------------

# Chapters are numbered ``0001``, ``0002``, ...  Four zero-padded
# digits comfortably handles any plausible per-project chapter count
# (rolling over a fresh chapter every day for ~27 years).  Wider
# padding only kicks in if a user blows past 9999.
_CHAPTER_NUMBER_WIDTH = 4
_CHAPTER_FILENAME_RE = re.compile(r"^(\d{4,})\.events\.jsonl$")


def _transcripts_dir(project_dir: Path) -> Path:
    """Path to the transcripts directory inside a project."""
    # Imported lazily to avoid a circular import — ``app_paths``
    # reaches into other parts of ``clarity_agent``.
    from clarity_agent.app_paths import protocol_dir as _protocol_dir
    return _protocol_dir(project_dir) / "transcripts"


def _chapter_jsonl_path(project_dir: Path, chapter: int) -> Path:
    name = f"{chapter:0{_CHAPTER_NUMBER_WIDTH}d}.events.jsonl"
    return _transcripts_dir(project_dir) / name


def _chapter_md_path(project_dir: Path, chapter: int) -> Path:
    name = f"{chapter:0{_CHAPTER_NUMBER_WIDTH}d}.md"
    return _transcripts_dir(project_dir) / name


def _list_chapters(project_dir: Path) -> list[int]:
    """Return all chapter numbers present, sorted ascending.

    Defined by the ``.events.jsonl`` files only — a stray ``.md``
    without its JSONL companion doesn't count as a chapter, since
    the JSONL is the source of truth.
    """
    d = _transcripts_dir(project_dir)
    if not d.exists():
        return []
    chapters: list[int] = []
    for path in d.iterdir():
        m = _CHAPTER_FILENAME_RE.match(path.name)
        if m and path.is_file():
            chapters.append(int(m.group(1)))
    chapters.sort()
    return chapters


# ---------------------------------------------------------------------------
# Internal: JSONL reading
# ---------------------------------------------------------------------------


def _read_events(jsonl_path: Path) -> Iterator[Event]:
    """Stream events from a JSONL file, skipping malformed lines.

    Returns an empty iterator if the file doesn't exist.  Malformed
    JSON and unknown event types are logged-and-skipped, never
    raised — so a partial-write at the tail (interrupted process,
    crash mid-flush) doesn't take down the rest of the chapter.
    """
    if not jsonl_path.exists():
        return
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.rstrip("\n")
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                _LOG.warning(
                    "Skipping malformed JSONL line %d in %s: %s",
                    line_no, jsonl_path, e,
                )
                continue
            try:
                yield parse_event(data)
            except ValidationError as e:
                _LOG.warning(
                    "Skipping unparseable event on line %d in %s: %s",
                    line_no, jsonl_path, e,
                )
                continue


# ---------------------------------------------------------------------------
# Internal: per-chapter file-handle writer
# ---------------------------------------------------------------------------


class _ChapterWriter:
    """Holds open file handles for one chapter; appends events atomically.

    Internal to :class:`Transcript`.  The Transcript owns at most
    one of these at a time — opens lazily on first write, swaps it
    out on :meth:`Transcript.start_new_chapter`, closes on
    :meth:`Transcript.close`.

    Each :meth:`write` call appends one event to the JSONL file and
    the markdown file, flushing both before returning.  Concurrent
    callers (the executor-thread tool callback and the main turn-
    boundary writes) serialize on the internal lock.
    """

    def __init__(self, project_dir: Path, chapter: int) -> None:
        self.chapter = chapter
        # ``a`` (append) creates the file if it doesn't exist and
        # appends if it does — correct for both new and resumed
        # chapters.  ``newline=""`` disables newline translation so
        # JSONL lines are exactly one ``\n`` regardless of platform.
        self._jsonl = open(
            _chapter_jsonl_path(project_dir, chapter),
            "a", encoding="utf-8", newline="",
        )
        self._md = open(
            _chapter_md_path(project_dir, chapter),
            "a", encoding="utf-8", newline="",
        )
        self._lock = threading.Lock()
        self._closed = False

    def write(self, event: Event) -> None:
        """Append one event to both files; flush both before return."""
        with self._lock:
            if self._closed:
                raise ValueError(
                    "Transcript writer is closed; cannot write further events",
                )
            # JSONL first: it's the canonical source.  If something
            # blows up between the two writes, the JSONL is the
            # version we trust.
            self._jsonl.write(serialize_event(event))
            self._jsonl.write("\n")
            self._jsonl.flush()
            self._md.write(render_event(event))
            self._md.flush()

    def close(self) -> None:
        """Close both handles; idempotent."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                self._jsonl.close()
            finally:
                # Always attempt to close markdown even if JSONL
                # close raised — otherwise an error on one would
                # leak the other handle.
                self._md.close()

    def __del__(self) -> None:
        # Defensive cleanup for a leaked instance.  ``close`` is
        # idempotent and __del__ must never raise.
        try:
            self.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public API: the Transcript class
# ---------------------------------------------------------------------------


class Transcript:
    """The conversation thread for one project.

    See module docstring for the conceptual model (chapters, file
    pairs, source-of-truth invariants) and lifecycle pattern
    (construction is cheap; file handles only exist while open;
    use as a context manager or call :meth:`close` explicitly).
    """

    def __init__(self, project_dir: Path | str) -> None:
        # Defensive copy via ``Path()`` so callers can pass a str
        # and get consistent ``Path`` semantics back.
        self._project_dir = Path(project_dir)
        # Open lazily on first write or start_new_chapter.  Stays
        # ``None`` for read-only usage.
        self._writer: _ChapterWriter | None = None
        # Fold any pre-#35 timestamp-named transcripts into chapter
        # 1 before doing anything else with this project.  Idempotent
        # and a no-op after first run — just a directory check on
        # subsequent constructions — so it's safe to live in the
        # constructor rather than be a per-caller responsibility.
        # Imported lazily to avoid an import cycle (migration uses
        # this class).
        from clarity_agent.transcript._migrate import migrate_legacy_transcripts
        migrate_legacy_transcripts(self._project_dir)

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def project_dir(self) -> Path:
        """The project this transcript belongs to."""
        return self._project_dir

    @property
    def directory(self) -> Path:
        """Path to the ``transcripts/`` directory (may not yet exist)."""
        return _transcripts_dir(self._project_dir)

    def chapter_jsonl_path(self, chapter: int) -> Path:
        """File path for a chapter's structured event log.

        Stable on-disk filename convention; exposed for code that
        needs to point external tooling at a specific chapter (e.g.,
        eval reports linking to the conversation file).  Callers
        rarely need this — most should iterate via
        :meth:`chapter_events` or read from
        :meth:`chapter_md_path`.
        """
        return _chapter_jsonl_path(self._project_dir, chapter)

    def chapter_md_path(self, chapter: int) -> Path:
        """File path for a chapter's human-readable markdown rendering.

        Same purpose as :meth:`chapter_jsonl_path` but for the ``.md``
        sidecar — useful for opening the rendered conversation in a
        viewer or linking it from reports.
        """
        return _chapter_md_path(self._project_dir, chapter)

    # ------------------------------------------------------------------
    # Chapter enumeration
    # ------------------------------------------------------------------

    @property
    def chapters(self) -> list[int]:
        """All chapter numbers present on disk, sorted ascending."""
        return _list_chapters(self._project_dir)

    @property
    def current_chapter(self) -> int | None:
        """The current (writeable) chapter number, or ``None`` if none exists yet."""
        chapters = _list_chapters(self._project_dir)
        return chapters[-1] if chapters else None

    @property
    def is_empty(self) -> bool:
        """``True`` iff no chapters exist yet (fresh project, never written)."""
        return self.current_chapter is None

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def chapter_events(self, chapter: int) -> Iterator[Event]:
        """Stream events from a specific chapter, in order.

        Returns an empty iterator when the chapter file doesn't
        exist; doesn't raise.
        """
        return _read_events(_chapter_jsonl_path(self._project_dir, chapter))

    def current_events(self) -> Iterator[Event]:
        """Stream events from the current chapter.

        Returns an empty iterator when no chapter exists yet.
        """
        chapter = self.current_chapter
        if chapter is None:
            return iter(())
        return self.chapter_events(chapter)

    def all_events(self) -> Iterator[Event]:
        """Stream events from every chapter, oldest chapter first.

        Walks chapters in ascending number order; within each
        chapter, events stream in their original order.  Useful for
        building a complete history view or for offline analysis.
        Not used by the live conversation paths — those operate on
        :meth:`current_events` only.
        """
        for chapter in self.chapters:
            yield from self.chapter_events(chapter)

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def write(self, event: Event) -> None:
        """Append an event to the current chapter.

        Opens the chapter writer lazily on the first call.  When no
        chapter exists yet on disk, the first write creates chapter
        ``0001``.  Subsequent writes append to whichever chapter
        :meth:`current_chapter` currently points to.

        Thread-safe — the underlying writer serializes concurrent
        writes via a lock.
        """
        self._ensure_writer()
        assert self._writer is not None
        self._writer.write(event)

    def start_new_chapter(self) -> int:
        """Roll over to a brand-new chapter.

        Closes the current writer (if any), allocates the next
        sequential chapter number, and opens a writer pointed at the
        new (empty) file pair.  The caller is responsible for writing
        the appropriate :class:`ChapterStarted` event as the first
        entry of the new chapter — this method intentionally doesn't,
        because the metadata it would need (backend name, etc.) is
        the caller's concern.

        Returns the new chapter number.
        """
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        # Figure out the next number from disk state, then create
        # the directory if needed before opening.
        new_chapter = self._next_chapter_number()
        self._ensure_directory()
        self._writer = _ChapterWriter(self._project_dir, new_chapter)
        return new_chapter

    def should_compact(
        self,
        *,
        threshold_tokens: int,
        input_tokens: int = 0,
    ) -> bool:
        """Decide whether compaction should fire now.

        Two-sided trigger:
        * ``input_tokens`` — what the LLM just reported processing on
          its last turn (the live-session signal).  Passed by the
          orchestrator from its ``on_usage`` capture.  ``0`` if the
          orchestrator doesn't have a value yet, in which case only
          the transcript-size half can trip.
        * :meth:`estimated_token_count` — what a rebuild from this
          transcript would consume.  Catches the case where the
          backend is auto-compacting (so ``input_tokens`` stays
          cold) but our on-disk record is growing unboundedly.

        Either trigger fires compaction.  The threshold is supplied
        by the caller (typically ``int(0.85 * model_context_window)``)
        — kept out of the transcript so callers can lower it for
        small-context-window models without changing the transcript
        layer.
        """
        if input_tokens > threshold_tokens:
            return True
        if self.estimated_token_count() > threshold_tokens:
            return True
        return False

    def compact_with_summarizer(
        self,
        *,
        threshold_tokens: int,
        summarize_fn: Callable[[list[Event]], str],
        input_tokens: int = 0,
        summarize_fraction: float = 0.70,
    ) -> CompactionResult | None:
        """Check thresholds and, if exceeded, run compaction.

        Composes :meth:`should_compact` + :meth:`compact` with an
        injected ``summarize_fn`` that produces the summary text
        from the events being folded away.  Returns ``None`` when
        no compaction was needed; otherwise a :class:`CompactionResult`
        describing what happened.

        ``summarize_fn`` is the orchestrator's bridge to the LLM
        layer — it typically calls ``backend.chat`` with a
        summarization prompt while suppressing UI-facing callbacks.
        Kept as an injection point so the transcript layer stays
        free of LLM dependencies.
        """
        if not self.should_compact(
            threshold_tokens=threshold_tokens,
            input_tokens=input_tokens,
        ):
            return None
        to_summarize = self._select_events_to_summarize(summarize_fraction)
        summary = summarize_fn(to_summarize)
        source_chapter = self.compact(
            summary=summary,
            source_turn_count=len(to_summarize),
            summarize_fraction=summarize_fraction,
        )
        return CompactionResult(
            summary=summary,
            source_chapter=source_chapter,
            source_turn_count=len(to_summarize),
            new_chapter=self.current_chapter or 0,
        )

    def external_compaction_occurred(
        self,
        *,
        summary: str,
        source_turn_count: int | None = None,
        summarize_fraction: float = 0.70,
    ) -> CompactionResult:
        """Record a compaction the backend performed on its side.

        Same chapter mechanics as :meth:`compact`, but the summary
        text comes from the provider (e.g., the Claude Agent SDK's
        ``isCompactSummary`` transcript entry) rather than from a
        local summarization call.  No threshold check — the backend
        already decided this was needed; we just keep our transcript
        in sync.

        ``source_turn_count=None`` lets the transcript derive the
        count from its own 70/30 split — the SDK's JSONL doesn't
        make the exact count cheap to extract, so the SDK detection
        path uses this default.

        Returns a :class:`CompactionResult` so the orchestrator can
        signal the UI uniformly with the threshold-driven path.
        """
        # Compute the effective count from the split before calling
        # ``compact`` (which would also do this internally), so the
        # CompactionResult we return carries the resolved number
        # rather than ``None``.
        if source_turn_count is None:
            source_turn_count = len(
                self._select_events_to_summarize(summarize_fraction),
            )
        source_chapter = self.compact(
            summary=summary,
            source_turn_count=source_turn_count,
            summarize_fraction=summarize_fraction,
        )
        return CompactionResult(
            summary=summary,
            source_chapter=source_chapter,
            source_turn_count=source_turn_count,
            new_chapter=self.current_chapter or 0,
        )

    def _select_events_to_summarize(self, summarize_fraction: float) -> list[Event]:
        """The older portion of message events that would be folded
        into a summary at the given split fraction.

        Same selection rule :meth:`compact` uses internally; exposed
        as a helper so :meth:`compact_with_summarizer` can hand the
        slice to ``summarize_fn`` without recomputing the split.
        """
        from clarity_agent.transcript.events import (
            ChapterStarted,
            CompactionSummary as _CSEvent,
            ModelOverride,
            ProcessStarted,
            SessionResume,
        )
        metadata_types = (
            ChapterStarted, SessionResume, _CSEvent,
            ProcessStarted, ModelOverride,
        )
        message_events = [
            e for e in self.current_events() if not isinstance(e, metadata_types)
        ]
        split_idx = int(len(message_events) * summarize_fraction)
        return message_events[:split_idx]

    def compact(
        self,
        *,
        summary: str,
        source_turn_count: int | None = None,
        summarize_fraction: float = 0.70,
    ) -> int:
        """Roll the current chapter, folding the older portion into a summary.

        Splits the current chapter's message-shaped events at
        ``summarize_fraction`` (default 70/30): everything before
        becomes the summary (the caller supplies the summary text);
        everything after is copied verbatim into the new chapter so
        recent context is preserved.

        ``summary`` is the caller's responsibility — it might come
        from an LLM-generated digest (the threshold-based path in
        :class:`WebSessionAdapter`), or from a backend's own
        provider-side compaction signal.  This method only handles
        the file-mechanics half.

        Metadata events (:class:`ChapterStarted`, :class:`SessionResume`,
        :class:`CompactionSummary`, :class:`ProcessStarted`,
        :class:`ModelOverride`) are excluded from both halves —
        they're bookkeeping, not turns.  The new chapter gets its
        own fresh header via the :meth:`start_compacted_chapter`
        call beneath the hood.

        Returns the source chapter number (the one that was just
        archived) so the caller can refer to it in UI signaling or
        diagnostic output.
        """
        from clarity_agent.transcript.events import (
            ChapterStarted,
            CompactionSummary,
            ModelOverride,
            ProcessStarted,
            SessionResume,
        )
        metadata_types = (
            ChapterStarted, SessionResume, CompactionSummary,
            ProcessStarted, ModelOverride,
        )
        all_events = list(self.current_events())
        message_events = [
            e for e in all_events if not isinstance(e, metadata_types)
        ]
        split_idx = int(len(message_events) * summarize_fraction)
        tail = message_events[split_idx:]
        source_chapter = self.current_chapter or 0
        if source_turn_count is None:
            source_turn_count = split_idx

        # ``start_compacted_chapter`` writes the ``CompactionSummary``
        # as the new chapter's first entry; subsequent writes append
        # the verbatim tail.
        self.start_compacted_chapter(
            summary=summary,
            source_chapter=source_chapter,
            source_turn_count=source_turn_count,
        )
        for event in tail:
            self.write(event)
        return source_chapter

    def start_compacted_chapter(
        self,
        summary: str,
        *,
        source_chapter: int | None = None,
        source_turn_count: int | None = None,
    ) -> int:
        """Start a new chapter seeded with a :class:`CompactionSummary`.

        This is the compaction primitive (Phase 2 trigger logic
        elsewhere; this method just persists the result).  It:

        1. Closes the current chapter's writer (if any).
        2. Allocates the next chapter number.
        3. Writes a :class:`CompactionSummary` event as the new
           chapter's first entry.

        After this returns, subsequent :meth:`write` calls append to
        the new chapter.  The old chapter remains on disk as an
        archive — readable via :meth:`chapter_events` for the
        History view, but no longer part of the active read path
        used by :meth:`context_summary` or :meth:`anthropic_messages`.

        ``source_chapter`` defaults to the chapter that was current
        immediately before this call — the natural choice.  Pass
        explicitly when compacting a chapter that isn't the current
        one (unusual; not currently expected).
        ``source_turn_count`` is informational and defaults to a
        count of message-producing events in the source chapter so
        UI can show "summary of N prior turns" without re-scanning.

        Returns the new chapter number.
        """
        # Derive defaults from current state BEFORE rolling over.
        if source_chapter is None:
            source_chapter = self.current_chapter or 0
        if source_turn_count is None and source_chapter > 0:
            # Count only message-shaped events (user turns + assistant
            # text + tool uses).  Metadata events (ChapterStarted,
            # SessionResume, ProcessStarted, ModelOverride) aren't
            # "turns" from the user's perspective.
            source_turn_count = sum(
                1 for ev in self.chapter_events(source_chapter)
                if type(ev).__name__ in {
                    "UserTurn", "AssistantText", "ToolUse",
                    "ToolResult", "ToolUseText",
                }
            )
        elif source_turn_count is None:
            source_turn_count = 0

        new_chapter = self.start_new_chapter()
        self.write(CompactionSummary(
            timestamp=datetime.now(timezone.utc),
            summary=summary,
            source_chapter=source_chapter,
            source_turn_count=source_turn_count,
        ))
        return new_chapter

    def close(self) -> None:
        """Release any open file handles.

        Idempotent.  After ``close()``, the instance can still be
        used for reading (:meth:`current_events`, :meth:`chapters`,
        etc.); a subsequent :meth:`write` will lazily re-open the
        writer.
        """
        if self._writer is not None:
            self._writer.close()
            self._writer = None

    # ------------------------------------------------------------------
    # Reconstruction (backend context rebuild)
    # ------------------------------------------------------------------

    def context_summary(
        self, *, max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    ) -> str | None:
        """Render the current chapter as a context-recap markdown blob.

        For the Claude SDK CLI backend path: when the cached SDK
        session is lost, the rebuild path is "start a new SDK session
        with this string prepended to the first user message or
        system prompt."

        Returns ``None`` if the current chapter is empty — callers
        can distinguish "fresh chapter, nothing to inject" from
        "have context."
        """
        return build_context_summary(
            self.current_events(), max_chars=max_chars,
        )

    def anthropic_messages(self) -> list[dict[str, Any]]:
        """Render the current chapter as an Anthropic API messages list.

        For the Anthropic-API backend path (and the future Phase 2
        compaction pipeline).  Produces the structured
        ``messages.create(messages=...)`` shape with ``tool_use`` /
        ``tool_result`` blocks preserved and metadata events skipped.

        Returns an empty list when the current chapter has no
        message-producing events.
        """
        return build_anthropic_messages(self.current_events())

    def estimated_token_count(self) -> int:
        """Rough estimate of the current chapter's content size in tokens.

        Sums the character length of message-shaped events (UserTurn,
        AssistantText, ToolUse, ToolUseText, CompactionSummary) in
        the current chapter and divides by 4 — a conservative
        chars-per-token ratio that fits English text well and is
        usually a slight over-estimate (good — we'd rather compact
        a bit early than too late).

        Used by the compaction orchestrator as the "rebuild safety"
        trigger: if a rebuild via :meth:`context_summary` or
        :meth:`anthropic_messages` would produce output close to the
        model's context window, fire compaction even if the live
        session's ``input_tokens`` are still under control (which
        happens when the provider is compacting internally but our
        transcript is growing).

        Metadata events (ChapterStarted, SessionResume,
        ProcessStarted, ModelOverride) are skipped — they contribute
        only sub-headings to the rendered output, not bulk content.
        """
        from clarity_agent.transcript.events import (
            AssistantText,
            CompactionSummary,
            ToolUse,
            ToolUseText,
            UserTurn,
        )

        total_chars = 0
        for event in self.current_events():
            if isinstance(event, (UserTurn, AssistantText)):
                total_chars += len(event.content)
            elif isinstance(event, ToolUse):
                # ``str(input)`` is a rough proxy — tool inputs are
                # dicts that go through extract_tool_detail when
                # rendered, but for a size estimate the raw repr is
                # close enough and avoids the rendering cost on
                # every check.
                total_chars += len(event.name) + len(str(event.input))
            elif isinstance(event, ToolUseText):
                total_chars += len(event.name) + len(event.detail)
            elif isinstance(event, CompactionSummary):
                total_chars += len(event.summary)
        return total_chars // 4

    def chat_messages(self) -> list[dict[str, Any]]:
        """Render the current chapter as chat-message dicts for the UI.

        Shape matches the frontend's ``ChatMessage`` interface so the
        web UI can directly populate its message list at mount,
        giving the user immediate continuity with their prior
        conversation rather than the empty-chat false-start the
        legacy auto-flow produced.

        Grouping rules:
        * Each :class:`UserTurn` becomes a ``{role: "user", ...}`` entry.
        * :class:`ToolUse` / :class:`ToolUseText` events accumulate
          into a ``toolEvents`` list that attaches to the *next*
          :class:`AssistantText` — matching the legacy ordering
          (User → tools → Assistant in the same turn).
        * Trailing tools without a paired assistant text (rare —
          would mean an assistant turn that ended with only tool
          calls) are emitted as an assistant message with empty
          content and the tools attached, so they aren't silently
          dropped.
        * Metadata events (:class:`ChapterStarted`, :class:`SessionResume`,
          :class:`ProcessStarted`, :class:`ModelOverride`,
          :class:`CompactionSummary`) are skipped — they aren't user-visible
          chat turns.
        * :class:`ToolResult` events are skipped too — the SDK backend
          handles tool results internally and they don't render as
          separate chat messages today.

        Returns an empty list when the current chapter has no
        message-producing events (fresh chapter, or one that only
        contains a header so far).
        """
        # Imported lazily to keep the optional chat-rendering path
        # from forcing the LLM-client dependency into every
        # Transcript caller.
        from clarity_agent.llm.client import extract_tool_detail
        from clarity_agent.transcript.events import (
            AssistantText,
            ToolUse,
            ToolUseText,
            UserTurn,
        )

        # ``uuid4`` ids match what the frontend generates for live
        # messages, so the union of "loaded history" + "new live
        # messages" has uniform shape.
        import uuid as _uuid

        messages: list[dict[str, Any]] = []
        pending_tools: list[dict[str, str]] = []

        # Track the most recent timestamp we've seen so unanchored
        # trailing tools (rare flush path) inherit a sensible time.
        last_ts_ms: int | None = None

        def _ts_ms(dt: datetime) -> int:
            """Event timestamp → JS-style milliseconds since epoch.

            The frontend's ``ChatMessage.timestamp`` is a JS number
            (ms).  Pydantic gives us a Python ``datetime``; convert.
            """
            return int(dt.timestamp() * 1000)

        def flush_tools_only() -> None:
            """Emit pending tools as an empty assistant message.

            Rare path: tools accumulated but no assistant text
            arrived to anchor them.  Could happen on a turn that
            ended in only tool calls, or on a transcript that was
            interrupted mid-turn.  Either way, don't drop them.
            """
            if pending_tools:
                messages.append({
                    "id": _uuid.uuid4().hex,
                    "role": "assistant",
                    "content": "",
                    "toolEvents": list(pending_tools),
                    "timestamp": last_ts_ms or 0,
                })
                pending_tools.clear()

        for event in self.current_events():
            if isinstance(event, UserTurn):
                # New user turn closes any unanchored tool sequence.
                flush_tools_only()
                last_ts_ms = _ts_ms(event.timestamp)
                messages.append({
                    "id": _uuid.uuid4().hex,
                    "role": "user",
                    "content": event.content,
                    "timestamp": last_ts_ms,
                })
            elif isinstance(event, ToolUse):
                last_ts_ms = _ts_ms(event.timestamp)
                pending_tools.append({
                    "tool": event.name,
                    "detail": extract_tool_detail(event.name, event.input),
                })
            elif isinstance(event, ToolUseText):
                # Legacy migrated tool entries already have a flat
                # ``detail`` string — render verbatim.
                last_ts_ms = _ts_ms(event.timestamp)
                pending_tools.append({
                    "tool": event.name,
                    "detail": event.detail,
                })
            elif isinstance(event, AssistantText):
                last_ts_ms = _ts_ms(event.timestamp)
                msg: dict[str, Any] = {
                    "id": _uuid.uuid4().hex,
                    "role": "assistant",
                    "content": event.content,
                    "timestamp": last_ts_ms,
                }
                if pending_tools:
                    msg["toolEvents"] = list(pending_tools)
                    pending_tools.clear()
                messages.append(msg)
            # Metadata events fall through silently — they don't
            # belong in the chat view.

        # End of stream: drain trailing tools (if any).
        flush_tools_only()
        return messages

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "Transcript":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def __del__(self) -> None:
        # Defensive: a leaked Transcript (no context manager, no
        # explicit close) shouldn't leak file handles to process exit.
        try:
            self.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_directory(self) -> None:
        """Materialize the transcripts directory if it doesn't exist."""
        d = self.directory
        d.mkdir(parents=True, exist_ok=True)

    def _next_chapter_number(self) -> int:
        """The number a brand-new chapter should be assigned."""
        current = self.current_chapter
        return 1 if current is None else current + 1

    def _ensure_writer(self) -> None:
        """Open the writer if it's not already open.

        Opens the current chapter when one exists; bootstraps chapter
        ``0001`` otherwise.  Idempotent.
        """
        if self._writer is not None:
            return
        chapter = self.current_chapter
        if chapter is None:
            # No chapter exists yet — bootstrap chapter 1.  This is
            # the first-write-creates-chapter behavior; the caller
            # is expected to write a ChapterStarted event first.
            chapter = 1
        self._ensure_directory()
        self._writer = _ChapterWriter(self._project_dir, chapter)
