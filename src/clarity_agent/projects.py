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

    def refresh(self) -> None:
        """Update ``has_protocol`` from the filesystem."""
        from clarity_agent.app_paths import _PROTOCOL_DIR_DOT, _PROTOCOL_DIR_VISIBLE
        p = Path(self.path)
        self.has_protocol = (p / _PROTOCOL_DIR_DOT).is_dir() or (p / _PROTOCOL_DIR_VISIBLE).is_dir()


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
            for e in entries:
                e.refresh()
            self._write(entries)
        return sorted(entries, key=lambda e: e.last_opened, reverse=True)

    def add(self, name: str, path: str | Path) -> ProjectEntry:
        """Register a new project.  Raises ``ValueError`` if the name is taken."""
        path = str(Path(path).resolve())
        entries = self._read()

        if any(e.name == name for e in entries):
            raise ValueError(f"Project name already exists: {name!r}")

        entry = ProjectEntry(name=name, path=path)
        entry.refresh()
        entries.append(entry)
        self._write(entries)
        return entry

    def remove(self, name: str) -> None:
        """Remove a project from the registry (does not touch the filesystem)."""
        entries = self._read()
        entries = [e for e in entries if e.name != name]
        self._write(entries)

    def get(self, name: str) -> ProjectEntry | None:
        """Look up a project by name."""
        for e in self._read():
            if e.name == name:
                return e
        return None

    def get_by_id(self, project_id: str) -> ProjectEntry | None:
        """Look up a project by its short hash ID."""
        for e in self._read():
            if e.id == project_id:
                return e
        return None

    def find_by_path(self, path: str | Path) -> ProjectEntry | None:
        """Look up a project by its directory path."""
        resolved = str(Path(path).resolve())
        for e in self._read():
            if e.path == resolved:
                return e
        return None

    def update(self, name: str, **fields: object) -> ProjectEntry:
        """Update fields on an existing entry.  Returns the updated entry.

        Raises ``KeyError`` if the project is not found.
        """
        entries = self._read()
        for e in entries:
            if e.name == name:
                for k, v in fields.items():
                    if not hasattr(e, k):
                        raise AttributeError(
                            f"ProjectEntry has no field {k!r}"
                        )
                    setattr(e, k, v)
                self._write(entries)
                return e
        raise KeyError(f"Project not found: {name!r}")

    def touch(self, name: str) -> None:
        """Update ``last_opened`` to now."""
        self.update(name, last_opened=time.time())

    def discover(self, base: Path | None = None) -> list[ProjectEntry]:
        """Scan a directory for project subdirectories and register any new ones.

        Returns the list of newly added entries.  Directories that are already
        registered (by path) are skipped.
        """
        base = base or clarity_projects_dir()
        if not base.is_dir():
            return []

        added: list[ProjectEntry] = []
        for child in sorted(base.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if self.find_by_path(child) is not None:
                continue
            # Derive a name, deduplicating if needed.
            name = self._unique_name(child.name)
            entry = self.add(name, child)
            added.append(entry)
        return added

    # -- Active project persistence ----------------------------------------

    def get_active(self) -> str | None:
        """Return the name of the last-active project, or ``None``."""
        data = self._read_raw()
        return data.get("active")

    def set_active(self, name: str) -> None:
        """Persist *name* as the active project."""
        data = self._read_raw()
        data["active"] = name
        self._write_raw(data)

    def clear_active(self) -> None:
        """Clear the persisted active project."""
        data = self._read_raw()
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
