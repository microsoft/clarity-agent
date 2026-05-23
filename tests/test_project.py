"""Tests for clarity_agent.setup.project."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from clarity_agent.setup.installer import CLARITY_DIR, Outcome
from clarity_agent.setup.layout import (
    PROTOCOL_DIR_DOT,
    Mode,
    ProjectLayout,
)
from clarity_agent.setup.project import (
    create_project_wrapper,
    create_protocol_dir,
    run_project_embed,
)


def _layout(target: Path, agent: Path | None = None) -> ProjectLayout:
    """EMBEDDED-mode layout for *target* — matches what
    ``run_project_embed`` builds at the top of its orchestrator."""
    return ProjectLayout(
        mode=Mode.EMBEDDED,
        project_dir=target,
        clarity_agent_dir=agent if agent is not None else target / CLARITY_DIR,
        protocol_dir=target / PROTOCOL_DIR_DOT,
    )

# ---------------------------------------------------------------------------
# create_protocol_dir
# ---------------------------------------------------------------------------

class TestCreateProtocolDir:
    def test_creates_directory(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        r = create_protocol_dir(_layout(tmp_path))
        assert r.outcome == Outcome.OK
        assert (tmp_path / ".clarity-protocol").is_dir()

    def test_idempotent(self, tmp_path: Path) -> None:
        (tmp_path / ".clarity-protocol").mkdir()
        r = create_protocol_dir(_layout(tmp_path))
        assert r.outcome == Outcome.OK
        assert "already" in r.message


# ---------------------------------------------------------------------------
# create_project_wrapper
# ---------------------------------------------------------------------------

class TestCreateProjectWrapper:
    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-only")
    def test_unix_wrapper_is_executable(self, tmp_path: Path) -> None:
        r = create_project_wrapper(_layout(tmp_path, tmp_path))
        assert r.outcome == Outcome.OK
        wrapper = tmp_path / "clarity"
        assert wrapper.exists()
        assert wrapper.stat().st_mode & 0o111
        content = wrapper.read_text()
        assert "command -v clarity" in content
        assert "not installed" in content

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_windows_wrappers_created(self, tmp_path: Path) -> None:
        r = create_project_wrapper(_layout(tmp_path, tmp_path))
        assert r.outcome == Outcome.OK
        assert (tmp_path / "clarity.ps1").exists()
        assert (tmp_path / "clarity.bat").exists()


# ---------------------------------------------------------------------------
# run_project_embed
# ---------------------------------------------------------------------------

class TestRunProjectEmbed:
    def test_happy_path(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        agent = tmp_path  # snippet template lives here

        results = run_project_embed(tmp_path, agent)

        assert not any(r.outcome == Outcome.FAIL for r in results)
        assert (tmp_path / ".clarity-protocol").is_dir()

    def test_fails_when_dir_missing(self, tmp_path: Path) -> None:
        results = run_project_embed(tmp_path / "nope", tmp_path)
        assert results[0].outcome == Outcome.FAIL
        assert "not found" in results[0].message

    def test_fails_when_not_a_git_repo(self, tmp_path: Path) -> None:
        results = run_project_embed(tmp_path, tmp_path)
        assert results[0].outcome == Outcome.FAIL
        assert "Not a git repository" in results[0].message

    def test_on_step_callback(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        called = []
        run_project_embed(tmp_path, tmp_path, on_step=called.append)
        assert len(called) > 0

    def test_idempotent(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        run_project_embed(tmp_path, tmp_path)
        results = run_project_embed(tmp_path, tmp_path)
        assert not any(r.outcome == Outcome.FAIL for r in results)
