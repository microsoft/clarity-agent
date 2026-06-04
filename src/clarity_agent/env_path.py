"""Ensure common tool directories are on PATH at startup.

macOS GUI apps (Tauri, Electron, Finder-launched scripts) inherit a
minimal PATH — typically just ``/usr/bin:/bin:/usr/sbin:/sbin``.  Tools
installed by Homebrew (``/opt/homebrew/bin``), pip (``~/.local/bin``),
or traditional Unix packages (``/usr/local/bin``) are invisible to
``shutil.which()`` and ``subprocess.run()`` in that context.

This module augments ``os.environ["PATH"]`` with well-known directories
that exist on disk but aren't already present.  It's safe to call
unconditionally — in a normal terminal session (where PATH is already
correct) it's a no-op.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _candidate_dirs() -> list[Path]:
    """Return platform-appropriate directories to ensure are on PATH."""
    home = Path.home()

    if sys.platform == "darwin":
        return [
            Path("/opt/homebrew/bin"),
            Path("/opt/homebrew/sbin"),
            Path("/usr/local/bin"),
            home / ".local" / "bin",
            home / ".cargo" / "bin",
        ]

    if sys.platform == "linux":
        return [
            Path("/usr/local/bin"),
            home / ".local" / "bin",
            home / ".cargo" / "bin",
        ]

    if sys.platform == "win32":
        # Windows GUI apps generally inherit a usable PATH from the
        # registry, but add common user-level install dirs just in case.
        dirs: list[Path] = [home / ".local" / "bin", home / ".cargo" / "bin"]
        # GitHub CLI default install location
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        dirs.append(Path(program_files) / "GitHub CLI")
        return dirs

    return []


def ensure_tool_paths() -> None:
    """Add well-known tool directories to PATH if they exist and are missing."""
    current = os.environ.get("PATH", "")
    current_dirs = set(current.split(os.pathsep))

    additions: list[str] = []
    for candidate in _candidate_dirs():
        s = str(candidate)
        if s not in current_dirs and candidate.is_dir():
            additions.append(s)

    if additions:
        os.environ["PATH"] = os.pathsep.join([*additions, current])
