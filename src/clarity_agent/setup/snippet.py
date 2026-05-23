"""Render and maintain the Clarity block in a project's ``AGENTS.md``.

The block lives between :data:`BEGIN_DELIMITER` and :data:`END_DELIMITER`
markers and carries:

  * a machine-readable meta header (HTML comment) recording the values
    used for the last render — ``schema_version``, ``mode``,
    ``protocol_dir_name``, ``processes_dir`` — used by
    :func:`ensure_agents_md` to detect drift;
  * a human-readable body, derived from the same template file
    (:func:`snippet_path`) that the installer uses, so every audience
    (the user's host coding agent and Clarity's own LLM) reads the
    same content.

``ensure_agents_md`` is the only function that writes to a project's
``AGENTS.md``: it parses the existing block (if any), compares its
meta to the current :class:`ProjectLayout`, and rewrites only when
the content actually differs.  Anything outside the markers is left
untouched, so users can layer their own project guidance around the
managed block without losing it on re-render.

**Stdlib-only** — this module is imported by
:mod:`~clarity_agent.setup.installer` which runs before
``pip install``, so it must not import third-party packages.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from .layout import ProjectLayout, detect_layout

BEGIN_DELIMITER = "<!-- clarity-begin -->"
END_DELIMITER = "<!-- clarity-end -->"

# Bump when the rendered body shape changes meaningfully — drives
# ``ensure_agents_md``'s "stale block, rewrite" path even when none of
# the per-project values (mode / protocol_dir_name / processes_dir)
# have moved.  Resist bumping for cosmetic copy edits; the resulting
# in-place rewrites are an upgrade-time tax on every user.
SCHEMA_VERSION = 1

_META_BEGIN = "<!-- clarity-meta"
_META_END = "-->"


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class EnsureStatus(Enum):
    """Outcome of an :func:`ensure_agents_md` call."""

    CREATED = "created"      # AGENTS.md didn't exist; we wrote a new one.
    UPDATED = "updated"      # AGENTS.md existed; our block was added or rewritten.
    UNCHANGED = "unchanged"  # AGENTS.md existed with our block already current.


# ---------------------------------------------------------------------------
# Template + render
# ---------------------------------------------------------------------------


def snippet_path() -> Path:
    """Path to the bundled ``snippet.md`` template."""
    return Path(__file__).with_name("snippet.md")


def render_snippet(layout: ProjectLayout) -> str:
    """Render the Clarity block from the template, substituting values
    from *layout*.

    Returns just the marker-bounded block (``<!-- clarity-begin -->``
    through ``<!-- clarity-end -->`` inclusive) — never anything that
    sits outside the markers in the template file (e.g. lint-suppress
    directives at the top).  Trailing newline included so callers can
    splice it into a target file without thinking about whitespace.

    Pure: no I/O beyond reading the template file, no disk writes.
    """
    template = snippet_path().read_text(encoding="utf-8")
    block = _extract_block(template)
    if block is None:
        # The template missing its own markers would be a packaging
        # bug — the file *defines* our block format.  Loud error
        # rather than silent half-render.
        raise RuntimeError(
            f"snippet.md template at {snippet_path()} is missing "
            f"the {BEGIN_DELIMITER}/{END_DELIMITER} markers",
        )

    substitutions = {
        "{{MODE}}": layout.mode.value,
        "{{PROTOCOL_DIR_NAME}}": layout.protocol_dir_name(),
        "{{PROCESSES_DIR}}": layout.processes_dir_for_rendering(),
    }
    rendered = block
    for placeholder, value in substitutions.items():
        rendered = rendered.replace(placeholder, value)
    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


# ---------------------------------------------------------------------------
# Meta-header parsing
# ---------------------------------------------------------------------------


def parse_meta(block: str) -> dict[str, str] | None:
    """Parse the ``<!-- clarity-meta ... -->`` HTML comment from a
    rendered block.  Returns a dict of key→value strings, or ``None``
    if no meta comment is found or the comment is malformed.

    Tolerant by design: a missing or malformed meta header means
    :func:`ensure_agents_md` will treat the block as stale and
    rewrite it, which is the right recovery for both legacy snippets
    (pre-meta-header era) and bit-rot.
    """
    begin = block.find(_META_BEGIN)
    if begin == -1:
        return None
    end = block.find(_META_END, begin + len(_META_BEGIN))
    if end == -1:
        return None
    body = block[begin + len(_META_BEGIN):end].strip()
    out: dict[str, str] = {}
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            # A non-empty line without ``key: value`` shape means
            # something's off; report malformed.
            return None
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


def _current_meta(layout: ProjectLayout) -> dict[str, str]:
    """The meta values the rendered block *should* have for *layout*.
    Compared against :func:`parse_meta`'s output to decide drift.
    """
    return {
        "schema_version": str(SCHEMA_VERSION),
        "mode": layout.mode.value,
        "protocol_dir_name": layout.protocol_dir_name(),
        "processes_dir": layout.processes_dir_for_rendering(),
    }


# ---------------------------------------------------------------------------
# Block locate / extract
# ---------------------------------------------------------------------------


def _extract_block(content: str) -> str | None:
    """Return the marker-bounded block in *content* (markers
    included), or ``None`` if either marker is missing.
    """
    begin = content.find(BEGIN_DELIMITER)
    if begin == -1:
        return None
    end = content.find(END_DELIMITER, begin + len(BEGIN_DELIMITER))
    if end == -1:
        return None
    end += len(END_DELIMITER)
    return content[begin:end]


def has_snippet(target: Path) -> bool:
    """True iff *target* exists and contains a Clarity block (both
    markers present).  Kept as a thin predicate for ``doctor``'s
    installation-type check, which only cares about presence.
    """
    if not target.exists():
        return False
    return _extract_block(target.read_text(encoding="utf-8")) is not None


# ---------------------------------------------------------------------------
# The maintenance loop
# ---------------------------------------------------------------------------


def ensure_agents_md(layout: ProjectLayout) -> EnsureStatus:
    """Reconcile ``layout.agents_md`` with the current canonical
    rendering of the Clarity block.  Idempotent and safe to call on
    every project-open.

    State table:

    +-----------------------------------+-----------------------------+
    | Existing state                    | Action                      |
    +===================================+=============================+
    | File absent                       | Create with just the block. |
    | File present, no markers          | Append block, preserving    |
    |                                   | the user's content.         |
    | File present, only one marker     | Treated as no-markers →     |
    |                                   | append block.               |
    | Block present, meta matches AND   | UNCHANGED — no write.       |
    | body matches                      |                             |
    | Block present, meta or body drift | Replace block in place,     |
    |                                   | preserve everything outside |
    |                                   | the markers.                |
    +-----------------------------------+-----------------------------+

    Writes only when the *rendered file content* actually differs from
    what's already on disk — important for filesystem watchers in host
    coding agents that re-read on every change.
    """
    rendered_block = render_snippet(layout)
    target = layout.agents_md

    if not target.exists():
        target.write_text(rendered_block, encoding="utf-8")
        return EnsureStatus.CREATED

    existing = target.read_text(encoding="utf-8")
    existing_block = _extract_block(existing)

    if existing_block is None:
        # No Clarity block yet (or markers are damaged) — append ours
        # to the end of the file, preserving everything that's
        # already there.  Aim for exactly one blank line of
        # separation before our block.
        if existing == "":
            new_content = rendered_block
        elif existing.endswith("\n\n"):
            new_content = existing + rendered_block
        elif existing.endswith("\n"):
            new_content = existing + "\n" + rendered_block
        else:
            new_content = existing + "\n\n" + rendered_block
        if new_content == existing:
            return EnsureStatus.UNCHANGED  # defensive — shouldn't happen on append
        target.write_text(new_content, encoding="utf-8")
        return EnsureStatus.UPDATED

    # Block present.  Decide whether to rewrite by checking meta-drift
    # *and* full-block byte-equality — meta drift is the cheap signal,
    # body drift catches cases where someone edited inside the
    # markers without touching the meta (e.g. manual tweaks the user
    # made between project-opens).
    rendered_block_stripped = rendered_block.rstrip("\n")
    existing_meta = parse_meta(existing_block)
    target_meta = _current_meta(layout)
    meta_drifted = existing_meta != target_meta
    body_drifted = existing_block != rendered_block_stripped

    if not meta_drifted and not body_drifted:
        return EnsureStatus.UNCHANGED

    # Splice: replace the marker-bounded slice with the freshly
    # rendered block, keeping everything outside it.
    begin = existing.find(BEGIN_DELIMITER)
    end_marker = existing.find(END_DELIMITER, begin + len(BEGIN_DELIMITER))
    end = end_marker + len(END_DELIMITER)
    # Preserve the single newline that typically follows the end
    # marker (if it's there).  ``rendered_block`` already ends with a
    # newline, so consuming the existing trailing newline avoids
    # accumulating blank lines over repeated reconciles.
    if end < len(existing) and existing[end] == "\n":
        end += 1
    new_content = existing[:begin] + rendered_block + existing[end:]
    if new_content == existing:
        return EnsureStatus.UNCHANGED
    target.write_text(new_content, encoding="utf-8")
    return EnsureStatus.UPDATED


# ---------------------------------------------------------------------------
# Shared best-effort entry point for runtime touch-points
# ---------------------------------------------------------------------------


def ensure_for_project(
    project_dir: Path,
    clarity_agent_dir: Path,
) -> EnsureStatus | None:
    """Detect a layout for *project_dir* and reconcile its ``AGENTS.md``,
    swallowing the cases where we deliberately do nothing.

    Returns the :class:`EnsureStatus` when ``ensure_agents_md`` ran,
    or ``None`` for any of the "no-op by design" outcomes:

    - **Dogfooding skip.** When ``project_dir == clarity_agent_dir``
      (the clarity-agent source repo opened on itself), we leave the
      hand-curated block at the repo root alone — auto-rewriting
      would clobber its source-relative paths with the generic
      embedded-relative form.
    - **No layout detected.** Fresh project with no Clarity markers
      yet, or ambiguous state with both protocol-dir names present.
      We don't implicitly create directories here; mode selection
      belongs in the explicit setup entry points (``clarity install
      --embedded``, the desktop "new project" flow).
    - **Write failure (OSError).** Read-only mount, permissions, etc.
      A stale ``AGENTS.md`` is better than a failed caller.

    Used by every runtime touch-point that wants "make sure
    ``project_dir/AGENTS.md`` is current before I read it" semantics
    — :meth:`WebSessionAdapter.start` on session open, the MCP
    server's behaviors reader.  Centralised here so the dogfooding
    rule and the no-layout policy live in exactly one place.
    """
    if project_dir.resolve() == clarity_agent_dir.resolve():
        return None
    layout = detect_layout(
        project_dir, bundled_clarity_agent_dir=clarity_agent_dir,
    )
    if layout is None:
        return None
    try:
        return ensure_agents_md(layout)
    except OSError:
        return None
