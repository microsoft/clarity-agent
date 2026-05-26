"""Tests for the ``_write_crash_log`` helper in ``clarity.py``.

The helper turns a silent ``SystemExit(1)`` (which is all the user sees
when the Tauri sidecar dies on Windows) into a readable traceback on
disk.  These tests pin down the file location, the contents, and the
must-never-raise contract.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_clarity_module():
    """Load ``clarity.py`` from the repo root without polluting ``sys.path``.

    ``clarity.py`` lives at the repo root (not under ``src/``) and isn't
    a package, so a plain ``import clarity`` would depend on pytest's
    rootdir behavior.  Loading by path is explicit and order-independent.
    """
    spec = importlib.util.spec_from_file_location("clarity", _REPO_ROOT / "clarity.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def clarity_module():
    return _load_clarity_module()


def test_writes_traceback_to_data_dir(clarity_module, tmp_path: Path) -> None:
    # conftest already points CLARITY_DATA_DIR at a per-test tmp dir.
    try:
        raise ValueError("synthetic boom")
    except ValueError as exc:
        log_path = clarity_module._write_crash_log(exc)

    assert log_path is not None
    assert log_path.exists()
    assert log_path.name == "clarity-crash.log"
    assert log_path.parent == Path(os.environ["CLARITY_DATA_DIR"])

    content = log_path.read_text(encoding="utf-8")
    assert "ValueError" in content
    assert "synthetic boom" in content
    assert "===" in content  # timestamp header marker


def test_appends_across_invocations(clarity_module) -> None:
    """A second crash adds to the file rather than overwriting it."""
    try:
        raise RuntimeError("first")
    except RuntimeError as exc:
        clarity_module._write_crash_log(exc)
    try:
        raise RuntimeError("second")
    except RuntimeError as exc:
        log_path = clarity_module._write_crash_log(exc)

    assert log_path is not None
    content = log_path.read_text(encoding="utf-8")
    assert "first" in content
    assert "second" in content


def test_swallows_failure(monkeypatch: pytest.MonkeyPatch, clarity_module) -> None:
    """An unwritable data dir must return ``None``, never raise.

    Otherwise the crash logger would mask the very exception we're
    trying to surface in ``main()``.
    """
    from clarity_agent import app_paths

    def _broken() -> Path:
        raise OSError("disk on fire")

    monkeypatch.setattr(app_paths, "clarity_data_dir", _broken)

    try:
        raise ValueError("boom")
    except ValueError as exc:
        result = clarity_module._write_crash_log(exc)

    assert result is None
