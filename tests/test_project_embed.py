"""Tests for clarity embed MCP json generation and pip detection."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

from clarity_agent.setup.installer import Outcome
from clarity_agent.setup.layout import (
    PROTOCOL_DIR_DOT,
    Mode,
    ProjectLayout,
)
from clarity_agent.setup.project import (
    _is_pip_installed,
    _mcp_json_pip,
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
    """Deterministic detection of pip vs. uv install mode.

    No runtime interpreter probing — the result is a pure function of
    the agent directory's contents, so the chosen mode is reproducible.
    """

    def test_returns_false_when_pyproject_has_tool_uv(self, tmp_path: Path) -> None:
        """A pyproject.toml with [tool.uv] signals a uv-managed checkout."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n\n[tool.uv]\n")
        assert _is_pip_installed(tmp_path) is False

    def test_returns_false_when_uv_lock_present(self, tmp_path: Path) -> None:
        """A uv.lock alone signals a uv-managed checkout."""
        (tmp_path / "uv.lock").write_text("")
        assert _is_pip_installed(tmp_path) is False

    def test_returns_true_when_pyproject_lacks_tool_uv(self, tmp_path: Path) -> None:
        """No [tool.uv] section and no uv.lock means pip mode."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")
        assert _is_pip_installed(tmp_path) is True

    def test_returns_true_when_no_uv_markers(self, tmp_path: Path) -> None:
        """An agent dir with neither pyproject nor uv.lock means pip mode."""
        assert _is_pip_installed(tmp_path) is True

    def test_none_agent_dir_defaults_to_pip(self) -> None:
        """When agent_dir is unknown, default to the pinned pip invocation."""
        assert _is_pip_installed(None) is True


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

    def test_merges_into_empty_existing_file(self, tmp_path: Path) -> None:
        """An existing empty-object mcp.json gets clarity-agent added."""
        project = self._make_project(tmp_path)
        vscode = project / ".vscode"
        vscode.mkdir()
        (vscode / "mcp.json").write_text("{}")
        with patch("clarity_agent.setup.project._is_pip_installed", return_value=True):
            result = create_mcp_json(_layout(project, tmp_path))
        assert result.outcome == Outcome.OK
        assert "Added" in result.message
        content = json.loads((vscode / "mcp.json").read_text())
        assert "clarity-agent" in content["servers"]

    def test_preserves_other_servers(self, tmp_path: Path) -> None:
        """Other MCP servers in the file survive the merge."""
        project = self._make_project(tmp_path)
        vscode = project / ".vscode"
        vscode.mkdir()
        existing = {
            "servers": {
                "other-tool": {"type": "stdio", "command": "other"}
            },
            "inputs": [{"id": "foo"}],
        }
        (vscode / "mcp.json").write_text(json.dumps(existing, indent=2))
        with patch("clarity_agent.setup.project._is_pip_installed", return_value=True):
            result = create_mcp_json(_layout(project, tmp_path))
        assert result.outcome == Outcome.OK
        content = json.loads((vscode / "mcp.json").read_text())
        # Our server added.
        assert "clarity-agent" in content["servers"]
        # Their server preserved.
        assert content["servers"]["other-tool"]["command"] == "other"
        # Top-level keys preserved.
        assert content["inputs"] == [{"id": "foo"}]

    def test_idempotent_when_already_current(self, tmp_path: Path) -> None:
        """Re-running embed when clarity-agent is already correct is a no-op."""
        project = self._make_project(tmp_path)
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        with patch("clarity_agent.setup.project._is_pip_installed", return_value=True):
            create_mcp_json(_layout(project, agent_dir))
            mtime = (project / ".vscode" / "mcp.json").stat().st_mtime_ns
            result = create_mcp_json(_layout(project, agent_dir))
        assert result.outcome == Outcome.OK
        assert "already has current" in result.message
        assert (project / ".vscode" / "mcp.json").stat().st_mtime_ns == mtime

    def test_updates_stale_entry(self, tmp_path: Path) -> None:
        """A stale clarity-agent entry is replaced on re-embed."""
        project = self._make_project(tmp_path)
        vscode = project / ".vscode"
        vscode.mkdir()
        stale = {"servers": {"clarity-agent": {"command": "python", "args": []}}}
        (vscode / "mcp.json").write_text(json.dumps(stale))
        with patch("clarity_agent.setup.project._is_pip_installed", return_value=True):
            result = create_mcp_json(_layout(project, tmp_path))
        assert result.outcome == Outcome.OK
        assert "Updated" in result.message
        content = json.loads((vscode / "mcp.json").read_text())
        assert content["servers"]["clarity-agent"]["command"] != "python"

    def test_warns_on_unparseable_jsonc(self, tmp_path: Path) -> None:
        """JSONC with comments is left untouched; a WARN shows the block."""
        project = self._make_project(tmp_path)
        vscode = project / ".vscode"
        vscode.mkdir()
        original = '// This is a JSONC comment\n{"servers": {}}'
        (vscode / "mcp.json").write_text(original)
        with patch("clarity_agent.setup.project._is_pip_installed", return_value=True):
            result = create_mcp_json(_layout(project, tmp_path))
        assert result.outcome == Outcome.WARN
        assert "not strict JSON" in result.message
        assert "clarity-agent" in result.message
        # File untouched.
        assert (vscode / "mcp.json").read_text() == original

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
        # Pinned to the resolved absolute interpreter, never the bare string "python".
        expected = str(Path(sys.executable).resolve())
        assert server["command"] == expected
        assert server["command"] != "python"
        assert server["args"] == ["-m", "clarity_agent.mcp"]

    def test_uv_mode_content(self, tmp_path: Path) -> None:
        project = self._make_project(tmp_path)
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        with patch("clarity_agent.setup.project._is_pip_installed", return_value=False):
            create_mcp_json(_layout(project, agent_dir))
        content = json.loads((project / ".vscode" / "mcp.json").read_text())
        server = content["servers"]["clarity-agent"]
        assert server["command"] == "uv"



class TestMcpJsonPipEdgeCases:
    """Stress tests for _mcp_json_pip across sys.executable variants."""

    @staticmethod
    def _server(raw: str) -> dict:
        return json.loads(raw)["servers"]["clarity-agent"]

    @staticmethod
    def _noop_resolve(p: Path) -> Path:
        """Stub out Path.resolve so fake Windows paths aren't mangled on Linux."""
        return p

    def test_path_with_spaces(self) -> None:
        with patch.object(sys, "executable", "C:\\Program Files\\Python311\\python.exe"), \
             patch.object(Path, "resolve", self._noop_resolve):
            s = self._server(_mcp_json_pip())
            assert s["command"] == "C:\\Program Files\\Python311\\python.exe"

    def test_unicode_path(self) -> None:
        with patch.object(sys, "executable", "C:\\Users\\\u00e9v\u00e9\\python.exe"), \
             patch.object(Path, "resolve", self._noop_resolve):
            s = self._server(_mcp_json_pip())
            assert s["command"] == "C:\\Users\\\u00e9v\u00e9\\python.exe"

    def test_empty_executable(self) -> None:
        """Empty sys.executable (embedded Python) doesn't crash."""
        with patch.object(sys, "executable", ""), \
             patch.object(Path, "resolve", self._noop_resolve):
            s = self._server(_mcp_json_pip())
            assert s["command"] == "."

    def test_native_separators_preserved(self) -> None:
        """Path.resolve() returns native separators; no slash conversion."""
        with patch.object(sys, "executable", "C:\\Users\\eve\\.venv\\Scripts\\python.exe"), \
             patch.object(Path, "resolve", self._noop_resolve):
            s = self._server(_mcp_json_pip())
            # On Windows the backslashes would be native; we no longer convert.
            assert s["command"] == "C:\\Users\\eve\\.venv\\Scripts\\python.exe"

    def test_json_structure(self) -> None:
        """Output is always valid JSON with expected keys."""
        parsed = json.loads(_mcp_json_pip())
        server = parsed["servers"]["clarity-agent"]
        assert server["type"] == "stdio"
        assert server["env"]["CLARITY_PROJECT_DIR"] == "${workspaceFolder}"
