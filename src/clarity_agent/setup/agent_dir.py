"""Clarity Agent — implementation library for the clarity protocol framework."""

from pathlib import Path

from clarity_agent.app_paths import get_bundle_dir


def get_agent_dir() -> Path:
    """Return the clarity-agent installation root (repo root).

    In a frozen (PyInstaller) build, this is ``sys._MEIPASS``.
    In development, derived from this file's location:
    ``src/clarity_agent/setup/agent_dir.py`` → up four levels → repo root
    containing ``processes/``, ``thinkers/``, etc.
    """
    return get_bundle_dir()
