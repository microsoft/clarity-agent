"""Tests for the ``clarity web`` refuse-to-start guard (issue #88).

When the frontend hasn't been built (no ``web/dist/``), ``clarity web``
used to bind its port and serve nothing in "API-only mode".  Because the
desktop app points its webview at this same server, the symptom was a
silent blank window with only a console warning that's easy to miss.

It now refuses to start unless ``--api-only`` is passed explicitly.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_clarity_module():
    """Load ``clarity.py`` from the repo root (it isn't an importable package)."""
    spec = importlib.util.spec_from_file_location("clarity", _REPO_ROOT / "clarity.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def clarity_module():
    return _load_clarity_module()


@pytest.fixture
def captured_launch(clarity_module, monkeypatch):
    """Stub both web entrypoints so ``web`` never binds a real port.

    Records the ``static_dir`` the launcher was called with; stays empty
    if the command refused to start before reaching a launcher.
    """
    captured: dict[str, object] = {}

    def _capture(args, clarity_agent_dir, static_dir, theme, uvicorn):
        captured["static_dir"] = static_dir

    monkeypatch.setattr(clarity_module, "_cmd_web_launcher", _capture)
    monkeypatch.setattr(clarity_module, "_cmd_web_single", _capture)
    return captured


def _run_web(clarity_module, monkeypatch, clarity_agent_dir: Path, *extra: str) -> None:
    """Drive ``main()`` for ``clarity web`` — exercises real arg parsing too."""
    argv = ["clarity", "web", "--clarity-agent", str(clarity_agent_dir), *extra]
    monkeypatch.setattr(clarity_module.sys, "argv", argv)
    clarity_module.main()


def test_web_refuses_when_frontend_not_built(
    clarity_module, monkeypatch, captured_launch, tmp_path: Path
) -> None:
    # tmp_path has no web/dist/, so the server would serve a blank page.
    with pytest.raises(SystemExit) as exc:
        _run_web(clarity_module, monkeypatch, tmp_path)

    # Exits with an actionable message and never reaches a launcher.
    assert exc.value.code not in (0, None)
    assert "web/dist" in str(exc.value.code)
    assert "static_dir" not in captured_launch


def test_api_only_flag_starts_headless_without_frontend(
    clarity_module, monkeypatch, captured_launch, tmp_path: Path
) -> None:
    # Explicit opt-in: start the headless server even with no UI built.
    _run_web(clarity_module, monkeypatch, tmp_path, "--api-only")

    assert captured_launch["static_dir"] is None


def test_web_serves_built_frontend(
    clarity_module, monkeypatch, captured_launch, tmp_path: Path
) -> None:
    # A real build is present → serve it, no flag needed.
    (tmp_path / "web" / "dist").mkdir(parents=True)
    _run_web(clarity_module, monkeypatch, tmp_path)

    assert captured_launch["static_dir"] == tmp_path.resolve() / "web" / "dist"
