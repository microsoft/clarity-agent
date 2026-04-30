"""Embed Clarity into an existing git project.

This is the lightweight counterpart to the desktop installer. It does not
create a venv or copy the agent code — it assumes Clarity is already
installed on the machine. It only adds the project-side artifacts:

  - ``.clarity-protocol/``  directory (for protocol outputs)
  - ``CLAUDE.md`` / ``AGENTS.md``  updated with the Clarity snippet
  - A thin ``clarity`` wrapper that delegates to the system install

The link to the system Clarity install is PATH-based, so it is never stored
in the git repo.  If Clarity isn't on PATH the wrapper gives a helpful error.

Entry point: ``clarity embed <project-dir>``
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from clarity_agent.app_paths import protocol_dir as _protocol_dir
from clarity_agent.setup.installer import (
    Outcome,
    StepResult,
    insert_agent_snippet,
    update_gitignore,
)

_IS_WINDOWS = sys.platform == "win32"

# The wrapper script placed in the project root. It finds the system Clarity
# install via PATH and delegates to it, so the link is never stored in git.
_UNIX_WRAPPER = """\
#!/usr/bin/env bash
# Clarity project wrapper — delegates to the system Clarity install.
# Check PATH first, then the standard macOS/Linux install location.
CLARITY="$(command -v clarity 2>/dev/null)"
if [ -z "$CLARITY" ] && [ -x "$HOME/.local/bin/clarity" ]; then
    CLARITY="$HOME/.local/bin/clarity"
fi
if [ -n "$CLARITY" ]; then
    exec "$CLARITY" "$@"
fi
echo "Clarity is not installed on this machine."
echo "Install it at: https://github.com/microsoft/clarity-agent"
exit 1
"""

_WINDOWS_WRAPPER_PS1 = """\
# Clarity project wrapper — delegates to the system Clarity install.
if (Get-Command clarity -ErrorAction SilentlyContinue) {
    & clarity @args
} else {
    Write-Host "Clarity is not installed on this machine."
    Write-Host "Install it at: https://github.com/microsoft/clarity-agent"
    exit 1
}
"""

_WINDOWS_WRAPPER_BAT = """\
@echo off
where clarity >nul 2>&1
if %errorlevel% == 0 (
    clarity %*
) else (
    echo Clarity is not installed on this machine.
    echo Install it at: https://github.com/microsoft/clarity-agent
    exit /b 1
)
"""

_MCP_JSON_PIP = """\
{
  "servers": {
    "clarity-agent": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "clarity_agent.mcp"],
      "env": {
        "CLARITY_PROJECT_DIR": "${workspaceFolder}"
      }
    }
  }
}
"""


def _mcp_json_uv(agent_dir: Path) -> str:
    """Generate mcp.json content for uv-based dev installs."""
    import json as _json

    # Use forward slashes even on Windows — VS Code and Node handle them fine.
    dir_str = str(agent_dir).replace("\\", "/")
    config = {
        "servers": {
            "clarity-agent": {
                "type": "stdio",
                "command": "uv",
                "args": [
                    "run", "--extra", "mcp",
                    "--directory", dir_str,
                    "python", "-m", "clarity_agent.mcp",
                    "--project-dir", "${workspaceFolder}",
                ],
            }
        }
    }
    return _json.dumps(config, indent=2) + "\n"


def _is_pip_installed(agent_dir: Path | None = None) -> bool:
    """Check if clarity-agent is globally pip-installed.

    Returns False (defaulting to uv mode) when the agent directory
    contains a pyproject.toml with a ``[tool.uv]`` section, which
    indicates a uv-managed source checkout rather than a pip install.
    Otherwise probes the system Python to verify the MCP module is
    importable.
    """
    import shutil
    import subprocess

    if agent_dir is not None:
        pyproject = agent_dir / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding="utf-8")
                if "[tool.uv]" in content:
                    return False
            except OSError:
                pass

    python = shutil.which("python")
    if not python:
        return False
    try:
        r = subprocess.run(
            [python, "-m", "clarity_agent.mcp", "--help"],
            capture_output=True, timeout=3,
        )
        return r.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Individual steps
# ---------------------------------------------------------------------------

def create_protocol_dir(project_dir: Path) -> StepResult:
    """Create the protocol directory if it doesn't exist."""
    protocol = _protocol_dir(project_dir)
    dir_name = protocol.name
    if protocol.exists():
        return StepResult(Outcome.OK, f"{dir_name}/ already exists")
    try:
        protocol.mkdir()
        (protocol / ".gitkeep").touch()
        return StepResult(Outcome.OK, f"Created {dir_name}/")
    except Exception as exc:
        return StepResult(Outcome.FAIL, f"{dir_name}/: {exc}")


def create_project_wrapper(project_dir: Path, agent_dir: Path) -> StepResult:
    """Create a thin clarity wrapper in the project root."""
    try:
        if _IS_WINDOWS:
            ps1 = project_dir / "clarity.ps1"
            bat = project_dir / "clarity.bat"
            ps1.write_text(_WINDOWS_WRAPPER_PS1, encoding="utf-8")
            bat.write_text(_WINDOWS_WRAPPER_BAT, encoding="utf-8")
            return StepResult(Outcome.OK, "Created clarity.ps1 and clarity.bat")
        else:
            wrapper = project_dir / "clarity"
            wrapper.write_text(_UNIX_WRAPPER)
            wrapper.chmod(0o755)
            return StepResult(Outcome.OK, f"Created {wrapper}")
    except Exception as exc:
        return StepResult(Outcome.FAIL, f"Wrapper: {exc}")


def create_mcp_json(project_dir: Path, agent_dir: Path) -> StepResult:
    """Create .vscode/mcp.json for MCP server integration.

    Detects whether clarity is pip-installed or running from a local
    clone, and generates the appropriate MCP server configuration.
    """
    vscode_dir = project_dir / ".vscode"
    mcp_json = vscode_dir / "mcp.json"
    if mcp_json.exists():
        return StepResult(Outcome.OK, ".vscode/mcp.json already exists")
    try:
        vscode_dir.mkdir(exist_ok=True)
        if _is_pip_installed(agent_dir):
            content = _MCP_JSON_PIP
            mode = "pip"
        else:
            content = _mcp_json_uv(agent_dir)
            mode = "uv"
        mcp_json.write_text(content, encoding="utf-8")
        msg = f"Created .vscode/mcp.json (MCP config, {mode} mode)"
        if mode == "uv":
            dir_str = str(agent_dir).replace("\\", "/")
            msg += f". Note: references {dir_str}, re-run embed if you move it"
        return StepResult(Outcome.OK, msg)
    except Exception as exc:
        return StepResult(Outcome.FAIL, f".vscode/mcp.json: {exc}")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_project_embed(
    project_dir: Path,
    agent_dir: Path,
    *,
    on_step: Callable[[StepResult], None] | None = None,
) -> list[StepResult]:
    """Embed Clarity into an existing git project.

    Args:
        project_dir: Root of the git project to embed into.
        agent_dir:   The clarity-agent installation (for the snippet template).
        on_step:     Optional callback for real-time progress output.
    """
    results: list[StepResult] = []

    def _record(result: StepResult) -> None:
        results.append(result)
        if on_step:
            on_step(result)

    if not project_dir.exists():
        _record(StepResult(Outcome.FAIL, f"Directory not found: {project_dir}"))
        return results
    if not (project_dir / ".git").exists():
        _record(StepResult(Outcome.FAIL, f"Not a git repository: {project_dir}"))
        return results

    _record(create_protocol_dir(project_dir))
    if results[-1].outcome == Outcome.FAIL:
        return results

    _record(insert_agent_snippet(project_dir, agent_dir))
    _record(create_project_wrapper(project_dir, agent_dir))
    for r in update_gitignore(project_dir):
        _record(r)

    return results


# ---------------------------------------------------------------------------
# CLI entry point (called by ``clarity embed``)
# ---------------------------------------------------------------------------

def _cli_main(argv: Sequence[str] | None = None, agent_dir: Path | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Embed Clarity into a git project",
    )
    parser.add_argument(
        "project_dir",
        type=Path,
        help="Path to the git repository to embed Clarity into",
    )
    args = parser.parse_args(argv)

    project_dir = args.project_dir.resolve()
    if agent_dir is None:
        agent_dir = Path(__file__).resolve().parents[4]

    use_color = "NO_COLOR" not in os.environ and sys.stdout.isatty()

    _FMT = {
        Outcome.OK:   ("\033[1;32m  \u2713 {}\033[0m", "  OK: {}"),
        Outcome.WARN: ("\033[1;33m  \u26a0 {}\033[0m", "  WARN: {}"),
        Outcome.FAIL: ("\033[1;31m  \u2717 {}\033[0m", "  FAIL: {}"),
        Outcome.SKIP: ("\033[1;33m  - {}\033[0m",      "  SKIP: {}"),
    }

    def info(msg: str) -> None:
        print(f"\033[1;34m==> {msg}\033[0m" if use_color else f"==> {msg}")

    def emit(result: StepResult) -> None:
        color_fmt, plain_fmt = _FMT[result.outcome]
        print((color_fmt if use_color else plain_fmt).format(result.message))

    info(f"Embedding Clarity into {project_dir}")
    results = run_project_embed(project_dir, agent_dir, on_step=emit)

    if any(r.outcome == Outcome.FAIL for r in results):
        print()
        info("Failed. See errors above.")
        raise SystemExit(1)

    print()
    info("Done!")
    print()
    print("  Next steps:")
    print(f"    cd {project_dir}")
    next_step_cmd = ".\\clarity web ." if _IS_WINDOWS else "./clarity web ."
    print(f"    {next_step_cmd}      # launch the web UI for this project")
    print()
