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
from collections.abc import Iterator
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
from clarity_agent.transcript.events import Event, parse_event, serialize_event

_LOG = logging.getLogger(__name__)


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
