"""Create and manage isolated exploration workspaces.

An exploration workspace is a normal userspace project in a well-known
location under ``clarity_projects_dir()``.  It uses the real protocol
structure so the exploration demonstrates actual Clarity behavior.
"""

from __future__ import annotations

from pathlib import Path

from clarity_agent.app_paths import clarity_projects_dir

_EXPLORATION_DIR_NAME = "Clarity First Exploration"


def exploration_workspace_path() -> Path:
    """Return the canonical path for the exploration workspace."""
    return clarity_projects_dir() / _EXPLORATION_DIR_NAME


def ensure_exploration_workspace(clarity_agent_dir: Path) -> Path:
    """Create (or refresh) the exploration workspace and return its path.

    Uses :func:`~clarity_agent.setup.project.setup_userspace_project`
    so the workspace has a real ``Clarity Protocol/`` directory with
    template files, ``config.json``, and a current ``AGENTS.md``.
    Idempotent — safe to call when the workspace already exists.
    """
    from clarity_agent.setup.project import setup_userspace_project

    ws = exploration_workspace_path()
    setup_userspace_project(ws, clarity_agent_dir)
    return ws


def reset_exploration_workspace(clarity_agent_dir: Path) -> Path:
    """Delete and recreate the exploration workspace.

    Used when the user picks "try another scenario" so they get a
    clean protocol directory without leftover artifacts from the
    previous run.

    On Windows the per-project server may still hold transcript files
    open, so ``rmtree`` can fail with PermissionError.  We use
    ``ignore_errors=True`` and let ``ensure_exploration_workspace``
    overwrite the protocol templates — leftover locked files (e.g.
    transcripts) won't affect the fresh-start behavior.
    """
    import shutil

    ws = exploration_workspace_path()
    if ws.is_dir():
        shutil.rmtree(ws, ignore_errors=True)
    return ensure_exploration_workspace(clarity_agent_dir)
