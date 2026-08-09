"""Embed Clarity into an existing git project.

This is the lightweight counterpart to the desktop installer. It does not
create a venv or pip-install anything — it assumes Clarity is already
installed on the machine. It only adds the project-side artifacts:

  - ``.clarity-protocol/``  directory (for protocol outputs)
  - ``.clarity-agent``      link (or copy) of the machine-wide install
  - ``CLAUDE.md`` / ``AGENTS.md``  updated with the Clarity snippet
  - A thin ``clarity`` wrapper that delegates to the system install

The ``.clarity-agent`` entry is what makes the result a *clean* EMBEDDED
layout as far as :func:`~clarity_agent.setup.layout.detect_layout` is
concerned — a protocol dir without it reads as a half-finished install
and the app refuses to open the project — and it's what makes the
repo-relative ``.clarity-agent/processes`` path the AGENTS.md block
advertises resolve.  Two ways to provide it, selected by
:class:`AgentDirStyle`:

  - :data:`AgentDirStyle.LINK` (default, "light") — a symlink to the
    machine-wide install (a directory junction on Windows when symlinks
    aren't permitted).  Nothing is duplicated; re-running ``embed``
    repoints a stale link.
  - :data:`AgentDirStyle.COPY` ("heavy") — a snapshot of the install's
    protocol content (``processes/``, ``thinkers/``).  Self-contained
    and symlink-free, at the cost of going stale until the next
    ``embed``.

A link is machine-specific and gets gitignored; a copy is portable, so
it isn't — the team can commit the guidance their coding agents read.
Running ``clarity`` stays PATH-based either way; if Clarity isn't on
PATH the wrapper gives a helpful error.

Entry point: ``clarity embed [--copy] <project-dir>``
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from enum import Enum
from pathlib import Path

from clarity_agent.setup.installer import (
    Outcome,
    StepResult,
    insert_agent_snippet,
    update_gitignore,
)
from clarity_agent.setup.layout import (
    EMBEDDED_AGENT_SUBDIR,
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

    This is the USERSPACE counterpart to :func:`run_project_embed`,
    which sets up a git repo as EMBEDDED.  Both are explicit setup
    entry points; ``ensure_for_project`` at runtime never invokes
    either.
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


class AgentDirStyle(Enum):
    """How ``embed`` provides ``.clarity-agent/`` inside the project."""

    LINK = "link"
    """Symlink to the machine-wide install (junction on Windows when
    symlink creation isn't permitted).  The default: nothing is
    duplicated, and the project tracks whatever the install becomes."""

    COPY = "copy"
    """Snapshot copy of the install's protocol content.  Self-contained
    and symlink-free — for environments where symlinks are awkward
    (some Windows setups, network shares, containers that bind-mount
    only the project), or where the team wants to commit the guidance
    their coding agents read."""


# What a project-side ``.clarity-agent/`` is actually read for: the
# process and thinker guides.  An allowlist, not a denylist — the
# install root also holds a venv, a git checkout, npm/cargo caches and
# build output, none of which a project needs and any of which can be
# gigabytes.  Execution always goes through the PATH-based wrapper, so
# the copy never has to be a *runnable* install.
_COPY_INCLUDE: tuple[str, ...] = ("processes", "thinkers")

# Junk to skip inside the copied trees.
_COPY_IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", ".DS_Store",
)


def _link_target(path: Path) -> Path | None:
    """Resolved target of *path* if it's a symlink or a Windows
    directory junction, else ``None`` (a real directory, or missing).

    Junctions are deliberately included: ``Path.is_symlink()`` reports
    ``False`` for them, so a junction laid down by a previous ``embed``
    on Windows would otherwise look like a real directory and never get
    repointed.
    """
    if not path.is_symlink():
        try:
            os.readlink(path)  # succeeds for junctions, raises for real dirs
        except OSError:
            return None
    try:
        return path.resolve()
    except OSError:
        return None


def _remove_link(path: Path) -> None:
    """Remove a symlink or junction without touching its target."""
    try:
        path.unlink()
    except OSError:
        # Windows junctions can't be unlinked, but rmdir removes the
        # reparse point itself and leaves the target alone.
        os.rmdir(path)


def _create_link(dest: Path, target: Path) -> StepResult:
    """Symlink *dest* → *target*, falling back to a Windows junction."""
    try:
        os.symlink(target, dest, target_is_directory=True)
        return StepResult(
            Outcome.OK, f"Linked {EMBEDDED_AGENT_SUBDIR} -> {target}",
        )
    except OSError as exc:
        if not _IS_WINDOWS:
            return StepResult(
                Outcome.FAIL, f"{EMBEDDED_AGENT_SUBDIR}: {exc}",
            )
        symlink_error = exc

    # Windows without Developer Mode / SeCreateSymbolicLinkPrivilege:
    # a directory junction needs no privileges and is transparent to
    # every path consumer we care about.
    try:
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dest), str(target)],
            capture_output=True, text=True, timeout=30, encoding="utf8",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return StepResult(
            Outcome.FAIL,
            f"{EMBEDDED_AGENT_SUBDIR}: symlink failed ({symlink_error}); "
            f"junction fallback failed ({exc})",
        )
    if result.returncode == 0:
        return StepResult(
            Outcome.OK,
            f"Linked {EMBEDDED_AGENT_SUBDIR} -> {target} (junction)",
        )
    detail = (result.stderr or result.stdout or "").strip()
    return StepResult(
        Outcome.FAIL,
        f"{EMBEDDED_AGENT_SUBDIR}: symlink failed ({symlink_error}) and "
        f"junction fallback failed ({detail}). Enable Developer Mode, or "
        f"re-run with --copy.",
    )


def _copy_agent_dir(dest: Path, target: Path) -> StepResult:
    """Snapshot the install's protocol content from *target* into *dest*.

    Copies only :data:`_COPY_INCLUDE`, and replaces rather than merges
    each of those trees so a refresh drops guides that no longer exist
    upstream instead of leaving them to rot in the project.
    """
    present = [name for name in _COPY_INCLUDE if (target / name).is_dir()]
    if not present:
        return StepResult(
            Outcome.FAIL,
            f"{EMBEDDED_AGENT_SUBDIR}: no protocol content found in {target} "
            f"(expected {'/, '.join(_COPY_INCLUDE)}/)",
        )
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for name in present:
            sub = dest / name
            if sub.exists():
                shutil.rmtree(sub)
            shutil.copytree(target / name, sub, ignore=_COPY_IGNORE)
    except OSError as exc:
        return StepResult(Outcome.FAIL, f"{EMBEDDED_AGENT_SUBDIR}: {exc}")
    copied = ", ".join(f"{name}/" for name in present)
    return StepResult(
        Outcome.OK, f"Copied {copied} from {target} into {EMBEDDED_AGENT_SUBDIR}/",
    )


def provide_agent_dir(
    layout: ProjectLayout,
    style: AgentDirStyle = AgentDirStyle.LINK,
) -> StepResult:
    """Provide ``.clarity-agent/`` in the project, by link or by copy.

    Without it the project is only half an EMBEDDED layout:
    :func:`~clarity_agent.setup.layout.detect_layout` reports
    ``PARTIAL_EMBEDDED_INSTALL`` and the app refuses to open it.

    Idempotent, and never destructive of content it didn't create:

    - Correct link already present → no-op.
    - Stale link (install moved, or switching to ``COPY``) → replaced;
      the link's target is untouched.
    - Real directory already present (a full clone, or a previous
      ``--copy``) → refreshed under ``COPY``, left alone under ``LINK``
      with a WARN, since removing it could destroy a real checkout.
    - Non-directory in the way → FAIL.
    """
    dest = layout.project_dir / EMBEDDED_AGENT_SUBDIR
    target = layout.clarity_agent_dir.resolve()
    project = layout.project_dir.resolve()

    # Self-reference guard: the clarity-agent source repo dogfooding
    # itself has ``project_dir == clarity_agent_dir``, and linking a
    # directory into itself is at best a no-op loop.  No marker is
    # needed there — ``detect_layout`` recognizes that repo
    # structurally as CLARITY_AGENT_SOURCE before it looks for
    # ``.clarity-agent/`` at all.
    if target == project or project in target.parents:
        return StepResult(
            Outcome.SKIP,
            f"{EMBEDDED_AGENT_SUBDIR}: install lives inside the project; "
            f"no link needed",
        )

    linked = _link_target(dest)
    if linked is not None:
        if style is AgentDirStyle.LINK and linked == target:
            return StepResult(
                Outcome.OK, f"{EMBEDDED_AGENT_SUBDIR} already links to {target}",
            )
        try:
            _remove_link(dest)
        except OSError as exc:
            return StepResult(
                Outcome.FAIL,
                f"{EMBEDDED_AGENT_SUBDIR}: could not replace existing link: {exc}",
            )
    elif dest.exists():
        if not dest.is_dir():
            return StepResult(
                Outcome.FAIL,
                f"{EMBEDDED_AGENT_SUBDIR} exists and is not a directory",
            )
        if style is AgentDirStyle.LINK:
            return StepResult(
                Outcome.WARN,
                f"{EMBEDDED_AGENT_SUBDIR}/ is a real directory (full install?) "
                f"— leaving it as-is; remove it first to switch to a link",
            )

    if style is AgentDirStyle.COPY:
        return _copy_agent_dir(dest, target)
    return _create_link(dest, target)


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
    style: AgentDirStyle = AgentDirStyle.LINK,
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
        style:       Whether ``.clarity-agent/`` is a link to *agent_dir*
                     (default, light) or a copy of it (heavy).
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

    # Must succeed for the project to read as a clean EMBEDDED layout;
    # without it the app will refuse to open what we just set up.
    _record(provide_agent_dir(layout, style))
    if results[-1].outcome == Outcome.FAIL:
        return results

    _record(insert_agent_snippet(layout))
    _record(create_project_wrapper(layout))
    _record(create_mcp_json(layout))
    # A copied install is a real, portable directory the repo may want
    # to commit; a symlink never is.
    for r in update_gitignore(
        layout, ignore_agent_dir=style is AgentDirStyle.LINK,
    ):
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
    how = parser.add_mutually_exclusive_group()
    how.add_argument(
        "--link",
        dest="style",
        action="store_const",
        const=AgentDirStyle.LINK,
        help=(
            "Light install (default): .clarity-agent is a symlink to this "
            "Clarity installation"
        ),
    )
    how.add_argument(
        "--copy",
        dest="style",
        action="store_const",
        const=AgentDirStyle.COPY,
        help=(
            "Heavy install: copy this installation's process and thinker "
            "guides into .clarity-agent/ instead of linking it"
        ),
    )
    parser.set_defaults(style=AgentDirStyle.LINK)
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

    style: AgentDirStyle = args.style
    info(f"Embedding Clarity into {project_dir} ({style.value} install)")
    results = run_project_embed(
        project_dir, agent_dir, style=style, on_step=emit,
    )

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
