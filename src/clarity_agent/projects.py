"""Persistent registry of known Clarity projects.

Stores project metadata in ``~/.clarity/projects.json``.  This is purely a
directory-level concept — whether a project has a running server process is
tracked separately by the launcher's in-memory process table.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from clarity_agent.app_paths import clarity_data_dir, clarity_projects_dir


def _make_project_id(path: str) -> str:
    """Derive a short, stable, URL-safe project ID from a path."""
    return hashlib.sha256(path.encode()).hexdigest()[:8]

_DEFAULT_FILE = "projects.json"


@dataclass
class ProjectEntry:
    """A known project directory."""

    name: str
    path: str  # absolute path to project directory
    last_opened: float = field(default_factory=time.time)
    has_protocol: bool = False
    llm_session_id: str | None = None
    id: str = ""  # short hash of path, assigned on add()

    def __post_init__(self) -> None:
        if not self.id:
            self.id = _make_project_id(self.path)

    def refresh(self) -> bool:
        """Update ``has_protocol`` from the filesystem. Returns False if the entire entry is now bogus."""
        p = Path(self.path)
        if not p.is_dir():
            return False
        from clarity_agent.app_paths import _PROTOCOL_DIR_DOT, _PROTOCOL_DIR_VISIBLE
        self.has_protocol = (p / _PROTOCOL_DIR_DOT).is_dir() or (p / _PROTOCOL_DIR_VISIBLE).is_dir()
        return True


class ProjectRegistry:
    """Manages the persistent list of known projects.

    The registry file is read on each call (no in-memory cache) so that
    multiple processes (e.g. launcher + CLI) never see stale data.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (clarity_data_dir() / _DEFAULT_FILE)

    # -- Public API --------------------------------------------------------

    def list(self, *, refresh: bool = True) -> list[ProjectEntry]:
        """Return all known projects, sorted by most recently opened.

        If *refresh* is True (the default), ``has_protocol`` is updated from
        the filesystem for each entry before returning.
        """
        entries = self._read()
        if refresh:
            entries = [e for e in entries if e.refresh()]
        entries = sorted(entries, key=lambda e: e.last_opened, reverse=True)
        if refresh:
            self._write(entries)
        return entries

    def add(
        self, path: str | Path, *, name: str | None = None,
    ) -> ProjectEntry:
        """Register (or re-open) a project at *path*.

        Path is the primary identity — a project directory is what
        uniquely identifies a project.  Re-adding the same path is
        idempotent: returns the existing entry, so "open project"
        is safe to call against an already-registered directory.
        Re-registering an existing path with a *different* name
        renames the entry — the user is just relabeling.

        The display ``name`` defaults to the basename of *path*
        as supplied by the caller (computed *before* resolving
        symlinks, so a path like ``~/Documents/Projects/my-thing``
        gives "my-thing" rather than whatever the canonical
        target's basename happens to be).  Pass ``name=`` to
        override.

        Display names are not a uniqueness constraint — two
        projects in different directories can share a label.  Look
        a name up via :meth:`find_by_name`, which returns a list
        rather than pretending it's a key.

        Raises :class:`FileNotFoundError` if *path* doesn't exist
        on disk — the registry never holds entries for directories
        that aren't there.
        """
        raw = Path(path)
        if name is None:
            # Pre-resolve basename keeps the user's chosen label
            # (e.g. the symlink they picked).  Fall back to the
            # resolved basename for edge cases like ``"."`` or
            # ``"/"``, then to a generic label so an entry always
            # has a non-empty name.
            name = raw.name or raw.resolve().name or "project"
        path_str = str(raw.resolve())
        entries = self._read()

        for e in entries:
            if e.path == path_str:
                # Idempotent reopen.  Honor a name change if the
                # caller supplied a different one.
                if e.name != name:
                    e.name = name
                    self._write(entries)
                return e

        entry = ProjectEntry(name=name, path=path_str)
        if not entry.refresh():
            raise FileNotFoundError(f"No project directory at {path_str}")
        entries.append(entry)
        self._write(entries)
        return entry

    # -- Identity-keyed action verbs (id is the primary key) ---------------

    def get(self, project_id: str) -> ProjectEntry | None:
        """Look up a project by its short hash id.  ``None`` if
        unknown.  Id is the registry's primary key — prefer it for
        any action that has to be unambiguous."""
        for e in self._read():
            if e.id == project_id:
                return e
        return None

    def update(self, project_id: str, **fields: object) -> ProjectEntry:
        """Update fields on the entry with this id.  Returns the
        updated entry.  Raises :class:`KeyError` if the id isn't
        in the registry."""
        entries = self._read()
        for e in entries:
            if e.id == project_id:
                for k, v in fields.items():
                    if not hasattr(e, k):
                        raise AttributeError(
                            f"ProjectEntry has no field {k!r}"
                        )
                    setattr(e, k, v)
                self._write(entries)
                return e
        raise KeyError(f"Project not found: id={project_id!r}")

    def touch(self, project_id: str) -> None:
        """Update ``last_opened`` on this id to now.  Raises
        :class:`KeyError` if the id isn't in the registry."""
        self.update(project_id, last_opened=time.time())

    def remove(self, project_id: str) -> None:
        """Drop the entry with this id from the registry.  No-op
        if the id isn't present (don't raise — callers commonly
        invoke this defensively during cleanup)."""
        entries = self._read()
        entries = [e for e in entries if e.id != project_id]
        self._write(entries)

    # -- Alternate-key lookups ---------------------------------------------

    def find_by_name(self, name: str) -> list[ProjectEntry]:
        """All registered projects with this display label.

        Returns a list because display names aren't unique — two
        projects in different directories may share a label.
        Caller decides what to do with 0/1/N matches.
        """
        return [e for e in self._read() if e.name == name]

    def get_by_path(self, path: str | Path) -> ProjectEntry | None:
        """Look up the project at this directory path.  Single
        result because paths are unique by construction (they're
        what derives the id)."""
        resolved = str(Path(path).resolve())
        for e in self._read():
            if e.path == resolved:
                return e
        return None

    # -- Collection management ---------------------------------------------

    def discover(self, base: Path | None = None) -> list[ProjectEntry]:
        """Scan a directory for project subdirectories and register
        any new ones.  Returns the list of newly added entries.
        Directories that are already registered (by path) are
        skipped.
        """
        base = base or clarity_projects_dir()
        if not base.is_dir():
            return []

        added: list[ProjectEntry] = []
        for child in sorted(base.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if self.get_by_path(child) is not None:
                continue
            # Derive a name, deduplicating if needed.  ``add`` would
            # default it to ``child.name`` anyway, but we want the
            # de-duplicating suffix when a label is already taken so
            # the project list stays readable.
            name = self._unique_name(child.name)
            entry = self.add(child, name=name)
            added.append(entry)
        return added

    # -- Active project persistence ----------------------------------------

    def get_active(self) -> str | None:
        """Return the *id* of the last-active project, or ``None``.

        Persisted under the ``"active_id"`` key.  Legacy registries
        stored ``"active"`` as a project *name*; we read both forms
        for compat (preferring id when present) and migrate to id on
        the next :meth:`set_active`.  The migration is silent so
        startup never blocks on a registry rewrite.
        """
        data = self._read_raw()
        active_id = data.get("active_id")
        if active_id:
            return active_id
        # Legacy name-keyed value — try to resolve to an id so
        # consumers don't have to know about the format change.
        legacy_name = data.get("active")
        if legacy_name:
            existing = self.get(legacy_name)
            if existing is not None:
                return existing.id
        return None

    def set_active(self, project_id: str) -> None:
        """Persist *project_id* as the active project.  Clears any
        legacy ``"active"`` name field so it doesn't drift."""
        data = self._read_raw()
        data["active_id"] = project_id
        data.pop("active", None)
        self._write_raw(data)

    def clear_active(self) -> None:
        """Clear the persisted active project (both id and legacy name)."""
        data = self._read_raw()
        data.pop("active_id", None)
        data.pop("active", None)
        self._write_raw(data)

    # -- Internals ---------------------------------------------------------

    def _unique_name(self, base_name: str) -> str:
        """Return *base_name* or *base_name-N* to avoid collisions."""
        entries = self._read()
        existing = {e.name for e in entries}
        if base_name not in existing:
            return base_name
        for i in range(2, 100):
            candidate = f"{base_name}-{i}"
            if candidate not in existing:
                return candidate
        raise ValueError(f"Too many projects named {base_name!r}")

    def _read_raw(self) -> dict[str, Any]:
        """Read the registry file as a dict.  Handles legacy array format."""
        if not self._path.exists():
            return {"projects": []}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"projects": []}
        # Backward compat: old format was a bare list of project dicts.
        if isinstance(data, list):
            return {"projects": data}
        return data

    def _write_raw(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8",
        )

    def _read(self) -> list[ProjectEntry]:
        items = self._read_raw().get("projects", [])
        return [ProjectEntry(**item) for item in items]

    def _write(self, entries: Sequence[ProjectEntry]) -> None:
        data = self._read_raw()
        data["projects"] = [asdict(e) for e in entries]
        self._write_raw(data)
