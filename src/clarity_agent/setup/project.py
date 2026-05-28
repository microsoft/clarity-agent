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

from clarity_agent.setup.installer import (
    Outcome,
    StepResult,
    insert_agent_snippet,
    update_gitignore,
)
from clarity_agent.setup.layout import (
    PROTOCOL_DIR_DOT,
    PROTOCOL_DIR_VISIBLE,
    Mode,
    ProjectLayout,
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

def _mcp_json_pip() -> str:
    """Generate mcp.json content for pip-style installs.

    Pins the absolute interpreter that owns ``clarity_agent``
    (``sys.executable``) rather than the bare string ``"python"``, so
    VS Code can't resolve a different interpreter on PATH at launch
    time.
    """
    import json as _json

    python = str(Path(sys.executable).resolve())
    config = {
        "servers": {
            "clarity-agent": {
                "type": "stdio",
                "command": python,
                "args": ["-m", "clarity_agent.mcp"],
                "env": {
                    "CLARITY_PROJECT_DIR": "${workspaceFolder}"
                },
            }
        }
    }
    return _json.dumps(config, indent=2)


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
    return _json.dumps(config, indent=2)


def _is_pip_installed(agent_dir: Path | None = None) -> bool:
    """Return True when embed should use the pip-style MCP invocation.

    Deterministic, no runtime interpreter probing — the chosen mode
    must be reproducible. A uv-managed source checkout (``agent_dir``
    has a ``uv.lock`` or a ``pyproject.toml`` with a ``[tool.uv]``
    section) uses the uv invocation (returns False); anything else,
    including the case where ``agent_dir`` is unknown, uses the
    pip invocation pinned to :data:`sys.executable` (returns True).
    """
    if agent_dir is None:
        return True
    if (agent_dir / "uv.lock").exists():
        return False
    pyproject = agent_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            if "[tool.uv]" in pyproject.read_text(encoding="utf-8"):
                return False
        except OSError:
            pass
    return True


# ---------------------------------------------------------------------------
# USERSPACE setup — the lightweight counterpart to embedded install
# ---------------------------------------------------------------------------

def setup_userspace_project(
    project_dir: Path,
    clarity_agent_dir: Path,
) -> ProjectLayout:
    """Set up a USERSPACE-mode Clarity project at *project_dir*.

    Creates the project directory if absent, lays down
    ``Clarity Protocol/`` and its template structure (via
    :func:`~clarity_agent.protocol.initialize.init_protocol`), and
    reconciles ``AGENTS.md`` against the rendered snippet.
    Idempotent — safe to call on an existing userspace project, in
    which case it just refreshes anything stale.

    Returns the :class:`ProjectLayout` so callers can register it
    or pass it to follow-up steps.

    This is the lightweight counterpart to :func:`run_project_embed`,
    which does the heavy embedded install (clone + venv + pip).
    Both are explicit setup entry points; ``ensure_for_project`` at
    runtime never invokes either.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    # Create ``Clarity Protocol/`` *before* delegating to
    # ``init_protocol``, so ``app_paths.protocol_dir`` (which picks
    # whichever name exists) returns the visible name we want for
    # USERSPACE — keeps the strict mode↔name mapping intact even
    # for the rare case of opening as USERSPACE inside a git repo.
    protocol = project_dir / PROTOCOL_DIR_VISIBLE
    protocol.mkdir(exist_ok=True)

    # ``init_protocol`` populates the template structure
    # (``goal/``, ``solution/``, ``failures/``, ``decisions/``, …)
    # and writes ``config.json``; it also calls
    # ``ensure_agents_md`` so the AGENTS.md block is current
    # before we return.
    from clarity_agent.protocol.initialize import init_protocol
    init_protocol(project_dir, clarity_agent_dir=clarity_agent_dir)

    return ProjectLayout(
        mode=Mode.USERSPACE,
        project_dir=project_dir,
        clarity_agent_dir=clarity_agent_dir,
        protocol_dir=protocol,
    )


# ---------------------------------------------------------------------------
# Individual steps
# ---------------------------------------------------------------------------

def create_protocol_dir(layout: ProjectLayout) -> StepResult:
    """Create the protocol directory if it doesn't exist.

    Path + name come from *layout* so we never duplicate the
    dotted-vs-visible name resolution that
    :class:`~clarity_agent.setup.layout.ProjectLayout` owns.
    """
    protocol = layout.protocol_dir
    dir_name = protocol.name
    if protocol.exists():
        return StepResult(Outcome.OK, f"{dir_name}/ already exists")
    try:
        protocol.mkdir()
        (protocol / ".gitkeep").touch()
        return StepResult(Outcome.OK, f"Created {dir_name}/")
    except Exception as exc:
        return StepResult(Outcome.FAIL, f"{dir_name}/: {exc}")


def create_project_wrapper(layout: ProjectLayout) -> StepResult:
    """Create a thin clarity wrapper in the project root."""
    project_dir = layout.project_dir
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


def create_mcp_json(layout: ProjectLayout) -> StepResult:
    """Create or update .vscode/mcp.json for MCP server integration.

    Merges the ``clarity-agent`` server entry into any existing
    ``.vscode/mcp.json``, preserving other servers and top-level keys
    (e.g. ``inputs``).  Behavior per edge case:

    - **No file**: writes a fresh config.
    - **Existing file, parseable JSON**: merges only the
      ``clarity-agent`` key under ``servers``, keeping everything
      else.  Writes only when the content would change (idempotent).
    - **Existing file, unparseable** (JSONC with comments, malformed):
      leaves the file untouched and returns a WARN with the block to
      paste manually.  We never reformat or clobber a file we can't
      round-trip safely.
    """
    import json as _json

    project_dir = layout.project_dir
    agent_dir = layout.clarity_agent_dir
    vscode_dir = project_dir / ".vscode"
    mcp_json = vscode_dir / "mcp.json"

    # Build the clarity-agent server entry for the detected mode.
    if _is_pip_installed(agent_dir):
        our_full = _json.loads(_mcp_json_pip())
        mode = "pip"
    else:
        our_full = _json.loads(_mcp_json_uv(agent_dir))
        mode = "uv"
    our_entry = our_full["servers"]["clarity-agent"]

    try:
        if mcp_json.exists():
            raw = mcp_json.read_text(encoding="utf-8")
            try:
                existing = _json.loads(raw)
            except (ValueError, _json.JSONDecodeError):
                # Unparseable (JSONC comments, malformed, etc.).
                # Don't touch; show the user what to add manually.
                block = _json.dumps({"clarity-agent": our_entry}, indent=2)
                return StepResult(
                    Outcome.WARN,
                    f".vscode/mcp.json exists but is not strict JSON; "
                    f"add this to the \"servers\" object manually:\n{block}",
                )
            # Merge: ensure "servers" exists, then set our key.
            servers = existing.setdefault("servers", {})
            if servers.get("clarity-agent") == our_entry:
                return StepResult(
                    Outcome.OK,
                    ".vscode/mcp.json already has current clarity-agent config",
                )
            servers["clarity-agent"] = our_entry
            content = _json.dumps(existing, indent=2) + "\n"
            verb = "Updated" if "clarity-agent" in raw else "Added"
        else:
            vscode_dir.mkdir(exist_ok=True)
            content = _json.dumps(our_full, indent=2) + "\n"
            verb = "Created"

        mcp_json.write_text(content, encoding="utf-8")
        msg = f"{verb} .vscode/mcp.json (clarity-agent, {mode} mode)"
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

    Builds a single :class:`ProjectLayout` at the top and threads it
    through every step — there's exactly one place in this file
    that knows about the protocol-dir name, the ``.clarity-agent``
    subdir, or any other layout-dependent path.

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

    # The embed command is by definition an EMBEDDED-mode install:
    # the user explicitly asked to put Clarity inside a git repo,
    # so the protocol dir is the dotted name and the layout is
    # rooted at this project_dir + agent_dir.
    layout = ProjectLayout(
        mode=Mode.EMBEDDED,
        project_dir=project_dir,
        clarity_agent_dir=agent_dir,
        protocol_dir=project_dir / PROTOCOL_DIR_DOT,
    )

    _record(create_protocol_dir(layout))
    if results[-1].outcome == Outcome.FAIL:
        return results

    _record(insert_agent_snippet(layout))
    _record(create_project_wrapper(layout))
    _record(create_mcp_json(layout))
    for r in update_gitignore(layout):
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
