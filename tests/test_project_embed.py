"""Tests for clarity embed MCP json generation and pip detection."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from clarity_agent.setup.installer import CLARITY_DIR, Outcome
from clarity_agent.setup.layout import (
    PROTOCOL_DIR_DOT,
    Mode,
    ProjectLayout,
)
from clarity_agent.setup.project import (
    _is_pip_installed,
    _mcp_json_uv,
    create_mcp_json,
)


def _layout(project: Path, agent: Path) -> ProjectLayout:
    """EMBEDDED-mode layout for *project* with *agent* as the
    clarity-agent install dir — mirrors what ``run_project_embed``
    builds at its orchestrator top."""
    return ProjectLayout(
        mode=Mode.EMBEDDED,
        project_dir=project,
        clarity_agent_dir=agent,
        protocol_dir=project / PROTOCOL_DIR_DOT,
    )


class TestIsPipInstalled:
    """Detection of pip vs. uv install mode."""

    def test_returns_false_when_pyproject_has_tool_uv(self, tmp_path: Path) -> None:
        """A pyproject.toml with [tool.uv] signals a uv-managed checkout."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n\n[tool.uv]\n")
        assert _is_pip_installed(tmp_path) is False

    def test_returns_true_when_pyproject_lacks_tool_uv(self, tmp_path: Path) -> None:
        """No [tool.uv] section means pip mode, if subprocess succeeds."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            assert _is_pip_installed(tmp_path) is True

    def test_returns_false_when_no_python_on_path(self, tmp_path: Path) -> None:
        """No python binary on PATH means not pip-installed."""
        with patch("shutil.which", return_value=None):
            assert _is_pip_installed(tmp_path) is False

    def test_returns_false_when_subprocess_fails(self, tmp_path: Path) -> None:
        """Subprocess returning non-zero means not pip-installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            assert _is_pip_installed(tmp_path) is False

    def test_returns_false_when_subprocess_times_out(self, tmp_path: Path) -> None:
        """Subprocess timeout means not pip-installed."""
        with patch("subprocess.run", side_effect=Exception("timeout")):
            assert _is_pip_installed(tmp_path) is False

    def test_none_agent_dir_skips_pyproject_check(self) -> None:
        """When agent_dir is None, skip pyproject check and probe system."""
        with patch("shutil.which", return_value=None):
            assert _is_pip_installed(None) is False


class TestMcpJsonUv:
    """The uv-mode mcp.json content."""

    def test_contains_uv_command(self, tmp_path: Path) -> None:
        content = _mcp_json_uv(tmp_path)
        parsed = json.loads(content)
        server = parsed["servers"]["clarity-agent"]
        assert server["command"] == "uv"
        assert "run" in server["args"]

    def test_uses_forward_slashes(self, tmp_path: Path) -> None:
        content = _mcp_json_uv(tmp_path)
        assert "\\\\" not in content


class TestCreateMcpJson:
    """The create_mcp_json embed step."""

    def _make_project(self, tmp_path: Path) -> Path:
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        return project

    def test_creates_file_when_missing(self, tmp_path: Path) -> None:
        project = self._make_project(tmp_path)
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        with patch("clarity_agent.setup.project._is_pip_installed", return_value=True):
            result = create_mcp_json(_layout(project, agent_dir))
        assert result.outcome == Outcome.OK
        assert (project / ".vscode" / "mcp.json").exists()
        assert "pip" in result.message

    def test_skips_when_exists(self, tmp_path: Path) -> None:
        project = self._make_project(tmp_path)
        vscode = project / ".vscode"
        vscode.mkdir()
        (vscode / "mcp.json").write_text("{}")
        result = create_mcp_json(_layout(project, tmp_path))
        assert result.outcome == Outcome.OK
        assert "already exists" in result.message

    def test_uv_mode_includes_path_warning(self, tmp_path: Path) -> None:
        project = self._make_project(tmp_path)
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        with patch("clarity_agent.setup.project._is_pip_installed", return_value=False):
            result = create_mcp_json(_layout(project, agent_dir))
        assert result.outcome == Outcome.OK
        assert "uv" in result.message
        assert "re-run embed" in result.message

    def test_pip_mode_content(self, tmp_path: Path) -> None:
        project = self._make_project(tmp_path)
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        with patch("clarity_agent.setup.project._is_pip_installed", return_value=True):
            create_mcp_json(_layout(project, agent_dir))
        content = json.loads((project / ".vscode" / "mcp.json").read_text())
        server = content["servers"]["clarity-agent"]
        assert server["command"] == "python"

    def test_uv_mode_content(self, tmp_path: Path) -> None:
        project = self._make_project(tmp_path)
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        with patch("clarity_agent.setup.project._is_pip_installed", return_value=False):
            create_mcp_json(_layout(project, agent_dir))
        content = json.loads((project / ".vscode" / "mcp.json").read_text())
        server = content["servers"]["clarity-agent"]
        assert server["command"] == "uv"
