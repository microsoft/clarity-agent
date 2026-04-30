"""Persist and restore LLM session state across app restarts.

Stores session metadata in ``.clarity-protocol/session_state.json`` so the
backend can resume a prior Claude SDK conversation instead of starting from
scratch.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from clarity_agent.app_paths import protocol_dir as _protocol_dir


def _state_path(project_dir: Path) -> Path:
    return _protocol_dir(project_dir) / "session_state.json"


def save_session_state(project_dir: Path, llm_session_id: str | None) -> None:
    """Persist the current LLM session ID for later restoration."""
    if llm_session_id is None:
        # Nothing to persist — don't overwrite a good saved state.
        return
    path = _state_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "llm_session_id": llm_session_id,
        "updated": time.time(),
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_session_state(project_dir: Path) -> str | None:
    """Load a previously persisted LLM session ID, or None."""
    path = _state_path(project_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("llm_session_id")
    except (json.JSONDecodeError, OSError):
        return None


def clear_session_state(project_dir: Path) -> None:
    """Remove persisted session state (e.g. after a failed resume)."""
    path = _state_path(project_dir)
    if path.exists():
        path.unlink(missing_ok=True)
