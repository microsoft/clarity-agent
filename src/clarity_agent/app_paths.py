"""Platform-aware path resolution for Clarity data and configuration.

All code that needs to locate user data (API keys, project registry, budget),
the agent installation, or the default project workspace should use these
functions instead of hardcoding paths.

Resolution priority for the data directory:

1. ``CLARITY_DATA_DIR`` environment variable (set by platform launchers).
2. Platform-specific default:
   - **macOS**: ``~/Library/Application Support/Clarity/``
   - **Windows**: ``%LOCALAPPDATA%\\Clarity\\data\\``
   - **Linux / fallback**: ``~/.clarity/``
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """Return True if running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_bundle_dir() -> Path:
    """Return the root directory of the application.

    - **Frozen (PyInstaller)**: the temp directory where PyInstaller
      unpacks bundled data files (``sys._MEIPASS``).  Data files like
      ``processes/``, ``thinkers/``, and ``web/dist/`` live here.
    - **Normal (development)**: the repository root, derived by walking
      up from this file.
    """
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # Development: this file is at src/clarity_agent/app_paths.py
    # → repo root is two levels up from the package.
    return Path(__file__).resolve().parent.parent.parent


def clarity_data_dir() -> Path:
    """Return the directory for persistent user data.

    This is where ``projects.json``, ``settings.json``, and (in desktop
    packaging mode) the ``.env`` file live.  The directory is **outside**
    the application bundle so it survives upgrades.
    """
    env = os.environ.get("CLARITY_DATA_DIR")
    if env:
        return Path(env)

    # macOS: ~/Library/Application Support/Clarity/
    # This is the standard macOS location for persistent app data.
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Clarity"

    # Windows: %LOCALAPPDATA%\Clarity\data\
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidate = Path(local_app_data) / "Clarity" / "data"
            if candidate.parent.is_dir():
                return candidate

    # Linux / developer fallback.
    return Path.home() / ".clarity"

def clarity_env_path() -> Path:
    """Return the path to the ``.env`` file for LLM credentials.

    In desktop packaging (``CLARITY_DATA_DIR`` is set), the ``.env`` file
    lives in the data directory.  In developer mode, it stays at the
    agent repo root alongside ``clarity.py``.
    """
    env = os.environ.get("CLARITY_DATA_DIR")
    if env:
        return Path(env) / ".env"

    # Developer mode: .env at the repo root.
    return get_bundle_dir() / ".env"


def clarity_projects_dir() -> Path:
    """Return the default directory for user project workspaces.

    Always ``~/Clarity Projects/`` — project directories are the user's
    documents and survive uninstall on all platforms.
    """
    if sys.platform == "darwin" or sys.platform == "win32":
        return Path.home() / "Documents" / "Clarity Projects"
    else:
        return Path.home() / "Clarity Projects"


# The two possible names for the protocol directory.
_PROTOCOL_DIR_DOT = ".clarity-protocol"
_PROTOCOL_DIR_VISIBLE = "Clarity Protocol"


def protocol_dir(project_dir: Path) -> Path:
    """Return the protocol directory for a project.

    Existing projects keep whichever name they already use.  For new projects
    (neither directory exists yet), the name is chosen by context:
    - Git repositories use the hidden ``".clarity-protocol/"`` name so the
      directory doesn't clutter the working tree for developers.
    - Non-git directories (e.g. ``~/Clarity Projects/My Work/``) use the
      visible ``"Clarity Protocol/"`` name so non-technical users can find it.
    """
    dot = project_dir / _PROTOCOL_DIR_DOT
    visible = project_dir / _PROTOCOL_DIR_VISIBLE

    if dot.exists():
        return dot
    if visible.exists():
        return visible

    # New project — choose based on whether it's inside a git repo.
    git_dir = project_dir / ".git"
    if git_dir.exists():
        return dot
    return visible


def find_protocol_dir(start: Path | None = None) -> Path:
    """Walk up from *start* (default: cwd) to find an existing protocol directory.

    Checks both ``".clarity-protocol/"`` and ``"Clarity Protocol/"`` at each
    level.  Falls back to ``protocol_dir(cwd)`` if nothing is found.
    """
    cwd = start or Path.cwd()
    for d in [cwd, *cwd.parents]:
        for name in (_PROTOCOL_DIR_DOT, _PROTOCOL_DIR_VISIBLE):
            candidate = d / name
            if candidate.is_dir():
                return candidate
    return protocol_dir(cwd)
