"""
Internal: one-time migration of pre-#35 timestamp-named transcripts.

Before issue #35, each :class:`ClaritySession` opened its own
``{username-}{timestamp}.md`` file under ``transcripts/`` and wrote
free-form markdown into it.  The new world has one chapter file pair
per logical "Start new chapter" boundary, with structured JSONL
alongside.  This module bridges the two: when a project has legacy
files but no chapter files yet, parse the legacy markdown back into
structured events and write them as the project's chapter 1.

The migration is **idempotent** (safe to call repeatedly — does
nothing once chapter 1 exists) and **lossy for tool calls** — the
legacy format flattened tool invocations to a single
``[Tool] name -> detail`` line, so the rebuilt events carry only
the name + detail string as :class:`ToolUseText`, with no
``tool_use_id`` or structured ``input``.  Going forward, fresh
tool calls write full-fidelity :class:`ToolUse` events.

Migration runs once per project at startup (called by the CLI's
transcript helper and by :class:`WebSessionAdapter.start`).  The
caller doesn't have to check whether legacy files exist — this
module handles all the no-op paths.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from clarity_agent.transcript.events import (
    AssistantText,
    ChapterStarted,
    Event,
    ModelOverride,
    ProcessStarted,
    SessionResume,
    ToolUseText,
    UserTurn,
)

_LOG = logging.getLogger(__name__)

# Matches new-format chapter files (``0001.md``, ``0042.md``, ...).
# Anything matching this is NOT a legacy file and is skipped.
_CHAPTER_MD_RE = re.compile(r"^\d{4,}\.md$")

# Markers we recognize inside a legacy transcript body.  All other
# lines are accumulated as content of whichever turn we're in.
_USER_PREFIX = "**User:** "
_ASSISTANT_PREFIX = "**Assistant:** "
_PROCESS_HEADING_PREFIX = "## Process: "
_MODEL_OVERRIDE_PREFIX = "**Model override:** "
_TOOL_LINE_RE = re.compile(r"^\s+\[Tool\]\s+(\S+)\s+->\s+(.*)$")
_MODEL_OVERRIDE_RE = re.compile(
    r"^\*\*Model override:\*\*\s+(.+?)\s+\(tier:\s+(.+)\)\s*$",
)

# File header fields (top of every legacy transcript).
_HEADER_DATE_PREFIX = "**Date:** "
_HEADER_BACKEND_PREFIX = "**Backend:** "

# How many lines into the file we'll look for header fields before
# giving up.  Legacy transcripts always have them in the first ~10
# lines; bounding the scan keeps malformed files from confusing the
# parser.
_HEADER_SCAN_LINES = 30


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def migrate_legacy_transcripts(project_dir: Path) -> bool:
    """Run one-time migration if applicable.

    Detects pre-#35 timestamp-named ``.md`` files under
    ``<project>/.clarity-protocol/transcripts/``, parses them into
    structured events, and writes them as chapter ``0001`` (both
    ``0001.md`` and ``0001.events.jsonl``).  Deletes the legacy
    files on success.

    Returns ``True`` if migration ran, ``False`` if it was a no-op
    (no legacy files OR chapter 0001 already exists OR transcripts
    directory missing).

    Safe to call repeatedly — once chapter 1 exists, no further
    action is taken on any subsequent call.

    Called automatically from :class:`Transcript.__init__`; callers
    rarely need to invoke this directly.  Exposed for tests and for
    any tooling that wants to migrate without constructing a
    :class:`Transcript` first.
    """
    # Direct imports of the internal helpers — going through
    # ``Transcript`` would loop forever (its constructor calls back
    # here).  These are package-internal helpers; this module is
    # also internal, so the underscore-prefix import is appropriate.
    from clarity_agent.transcript.transcript import (
        _ChapterWriter,
        _list_chapters,
        _transcripts_dir,
    )

    # Idempotence guard: if chapter 1 already exists on disk we've
    # already migrated (or the project was started fresh on the new
    # code).  Either way, nothing to do.
    if _list_chapters(project_dir):
        return False

    transcripts_dir = _transcripts_dir(project_dir)
    legacy_files = _find_legacy_files(transcripts_dir)
    if not legacy_files:
        return False

    # Parse every legacy file.  The first becomes the chapter
    # opener (with a synthesized ``ChapterStarted`` event from its
    # header); each subsequent file contributes a ``SessionResume``
    # boundary plus its body events.
    events: list[Event] = []
    sorted_files = _sort_legacy_files(legacy_files)
    for i, (path, header_date, backend) in enumerate(sorted_files):
        timestamp = header_date or datetime.fromtimestamp(
            path.stat().st_mtime, tz=UTC,
        )
        backend_name = backend or "unknown"
        if i == 0:
            events.append(ChapterStarted(
                timestamp=timestamp,
                project_dir=str(project_dir),
                backend=backend_name,
            ))
        else:
            events.append(SessionResume(
                timestamp=timestamp,
                backend=backend_name,
                llm_session_id=None,  # not preserved in legacy files
            ))
        events.extend(_parse_legacy_body(path, timestamp))

    # Write all events to chapter 1.  Use the internal writer
    # directly so we don't re-enter the migration path through
    # ``Transcript`` construction.  Same dual-file atomicity
    # guarantees as the normal write path.
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    writer = _ChapterWriter(project_dir, 1)
    try:
        for event in events:
            writer.write(event)
    finally:
        writer.close()

    # Delete legacy files after successful write.  Done last so a
    # crash mid-write leaves us recoverable: legacy files still
    # present, chapter 1 partial.  On the next startup, the idempotence
    # guard sees chapter 1 exists and skips — the user can manually
    # remove ``0001.*`` to retry if needed.
    for path, _date, _backend in sorted_files:
        try:
            path.unlink()
        except OSError as e:
            _LOG.warning(
                "Could not delete legacy transcript %s after migration: %s",
                path, e,
            )

    _LOG.info(
        "Migrated %d legacy transcript file(s) into chapter 1 of %s",
        len(sorted_files), project_dir,
    )
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_legacy_files(transcripts_dir: Path) -> list[Path]:
    """Return all ``.md`` files in the directory that aren't new-format
    chapter files.

    Excludes anything matching ``NNNN.md`` (the new chapter
    convention) so a partial state with both file kinds present
    won't accidentally treat a chapter file as legacy.
    """
    if not transcripts_dir.exists():
        return []
    return [
        p for p in transcripts_dir.glob("*.md")
        if p.is_file() and not _CHAPTER_MD_RE.match(p.name)
    ]


def _sort_legacy_files(
    files: list[Path],
) -> list[tuple[Path, datetime | None, str | None]]:
    """Sort legacy files chronologically by their parsed ``**Date:**``.

    Falls back to filesystem ``mtime`` for any file whose header
    date can't be parsed.  Returns ``(path, header_date, backend)``
    tuples so callers don't have to re-read the header.
    """
    annotated: list[tuple[Path, datetime | None, str | None]] = []
    for path in files:
        date, backend = _read_legacy_header(path)
        annotated.append((path, date, backend))

    def sort_key(item: tuple[Path, datetime | None, str | None]) -> float:
        path, date, _ = item
        if date is not None:
            return date.timestamp()
        # mtime fallback when the header is unreadable — better than
        # arbitrary filename ordering, especially since legacy
        # filenames mixed ``username-YYYYMMDD`` and bare ``YYYYMMDD``
        # forms that sort differently.
        return path.stat().st_mtime

    annotated.sort(key=sort_key)
    return annotated


def _read_legacy_header(path: Path) -> tuple[datetime | None, str | None]:
    """Parse the top-of-file ``**Date:**`` and ``**Backend:**`` lines."""
    date: datetime | None = None
    backend: str | None = None
    try:
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f):
                if line_no >= _HEADER_SCAN_LINES:
                    break
                line = line.rstrip("\n")
                if line.startswith(_HEADER_DATE_PREFIX):
                    raw = line[len(_HEADER_DATE_PREFIX):].strip()
                    date = _parse_iso(raw)
                elif line.startswith(_HEADER_BACKEND_PREFIX):
                    backend = line[len(_HEADER_BACKEND_PREFIX):].strip()
                if date is not None and backend is not None:
                    break
    except OSError:
        # Unreadable file — caller will fall back to mtime/unknown.
        pass
    return date, backend


def _parse_iso(raw: str) -> datetime | None:
    """Parse a Python ``datetime.isoformat()`` string back to a datetime.

    Handles both naive (``2026-04-12T10:00:00``) and tz-aware
    (``2026-04-12T10:00:00+00:00``) forms; naive timestamps are
    coerced to UTC so downstream events have a consistent tz.
    """
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _parse_legacy_body(path: Path, fallback_timestamp: datetime) -> list[Event]:
    """Parse a legacy transcript's body into structured events.

    Skips the file's top-of-file header block (handled separately
    by :func:`_read_legacy_header` so the caller can synthesize the
    appropriate ``ChapterStarted``/``SessionResume`` boundary).
    """
    events: list[Event] = []
    state = "outside"
    # Buffer for whichever turn we're currently accumulating.
    buf: list[str] = []
    # All inline body events use the same fallback timestamp — we
    # don't have per-event timestamps in the legacy format.  The
    # caller passes the file's parsed-header date (or mtime), which
    # is the best we can do.
    ts = fallback_timestamp

    def flush() -> None:
        nonlocal buf, state
        if not buf:
            state = "outside"
            return
        content = "\n".join(buf).strip()
        buf = []
        if state == "in_user" and content:
            events.append(UserTurn(timestamp=ts, content=content))
        elif state == "in_assistant" and content:
            events.append(AssistantText(timestamp=ts, content=content))
        state = "outside"

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        _LOG.warning("Could not read legacy transcript %s: %s", path, e)
        return events

    # Skip past the file header.  Legacy transcripts always end the
    # header with ``\n---\n\n``; everything after that is the body.
    body_start = text.find("\n---\n")
    body = text[body_start + 5:] if body_start != -1 else text

    for line in body.split("\n"):
        # Tool line — flushes any pending user accumulation, then
        # emits a :class:`ToolUseText` event.  These always appear
        # between a user turn and the assistant's response in the
        # legacy format, so the buffered turn is always a user one.
        m = _TOOL_LINE_RE.match(line)
        if m and state in ("in_user", "in_tools"):
            if state == "in_user":
                flush()
            events.append(ToolUseText(
                timestamp=ts, name=m.group(1), detail=m.group(2),
            ))
            state = "in_tools"
            continue

        if line.startswith(_USER_PREFIX):
            flush()
            buf = [line[len(_USER_PREFIX):]]
            state = "in_user"
        elif line.startswith(_ASSISTANT_PREFIX):
            flush()
            buf = [line[len(_ASSISTANT_PREFIX):]]
            state = "in_assistant"
        elif line.startswith(_PROCESS_HEADING_PREFIX):
            flush()
            events.append(ProcessStarted(
                timestamp=ts,
                process_name=line[len(_PROCESS_HEADING_PREFIX):].strip(),
            ))
        elif line.startswith(_MODEL_OVERRIDE_PREFIX):
            # Standalone model-override line — separate from a
            # process boundary, recorded as :class:`ModelOverride`.
            mo = _MODEL_OVERRIDE_RE.match(line.rstrip())
            if mo:
                events.append(ModelOverride(
                    timestamp=ts, model=mo.group(1), tier=mo.group(2),
                ))
        elif line.strip() == "---":
            # Turn-separator marker.  Flushes the current turn.
            flush()
        elif state in ("in_user", "in_assistant"):
            # Continuation of whatever turn we're in — append to buf.
            buf.append(line)
        # Lines outside any turn (blank lines between sections,
        # stray formatting) are ignored.

    flush()
    return events
