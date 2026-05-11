"""Install clarity-agent (standalone or embedded mode).

Each step function performs one action and returns a :class:`StepResult`
describing what happened, so the CLI layer can format output without the
library printing anything.

**Stdlib-only** — this module runs before ``pip install``, so it must not
import any third-party packages or any ``clarity_agent`` submodule that
does.  Submodules that are themselves stdlib-only (e.g. ``snippet``) may
be imported lazily inside functions that run after pip install.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

CLARITY_DIR = ".clarity-agent"
MIN_PYTHON = (3, 12)
MIN_NODE = 22

_IS_WINDOWS = sys.platform == "win32"


def _venv_python(venv_dir: Path) -> str:
    """Return the path to the Python executable inside a venv."""
    if _IS_WINDOWS:
        return str(venv_dir / "Scripts" / "python.exe")
    return str(venv_dir / "bin" / "python")


def _subprocess_failure(
    label: str, result: subprocess.CompletedProcess[str],
) -> str:
    """Build a multi-line failure message that includes captured output.

    The default ``"X failed"`` message is useless when the install
    breaks — the operator has nothing to grep, no stack to follow.
    Including the last lines of stderr (preferred) or stdout makes
    failures self-diagnosing.  Uses last ~12 lines so a long npm
    error doesn't bury the actual exit reason.
    """
    tail_lines = 12
    body = (result.stderr or "").strip() or (result.stdout or "").strip()
    if body:
        lines = body.splitlines()
        if len(lines) > tail_lines:
            body = "\n".join(["...(earlier output omitted)"] + lines[-tail_lines:])
        return f"{label} (exit {result.returncode}):\n{body}"
    return f"{label} (exit {result.returncode}, no output captured)"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class Outcome(Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class StepResult:
    outcome: Outcome
    message: str


# ---------------------------------------------------------------------------
# Install mode & config
# ---------------------------------------------------------------------------

class InstallMode(Enum):
    EMBEDDED = "embedded"
    STANDALONE = "standalone"


@dataclass
class InstallConfig:
    """Resolved configuration for an install run."""

    mode: InstallMode
    target: Path              # The directory being set up
    agent_dir: Path           # Where the clarity-agent code lives
    venv_dir: Path            # Where to create .venv
    pip_install_spec: str     # e.g. ".[dev]" or "./.clarity-agent[cli,web,...]"
    pip_cwd: Path             # Working directory for pip install -e
    web_dir: Path             # Where web/package.json lives
    env_dir: Path             # Where .env / .env.sample live
    needs_gitignore: bool     # Whether to add entries to .gitignore
    run_tests: bool           # Whether to run pytest + vitest after install
    clone_url: str | None = None


def resolve_config(
    mode: InstallMode,
    target: Path,
    agent_dir: Path,
    clone_url: str | None = None,
) -> InstallConfig:
    """Build an InstallConfig from mode and paths."""
    if mode == InstallMode.EMBEDDED:
        clarity_sub = target / CLARITY_DIR
        return InstallConfig(
            mode=mode,
            target=target,
            agent_dir=clarity_sub,
            venv_dir=clarity_sub / ".venv",
            pip_install_spec=f"./{CLARITY_DIR}[cli,web,brainstorm,docx,openai,azure]",
            pip_cwd=target,
            web_dir=clarity_sub / "web",
            env_dir=clarity_sub,
            needs_gitignore=True,
            run_tests=False,
            clone_url=clone_url,
        )
    # STANDALONE
    return InstallConfig(
        mode=mode,
        target=target,
        agent_dir=target,
        venv_dir=target / ".venv",
        pip_install_spec=".[dev]",
        pip_cwd=target,
        web_dir=target / "web",
        env_dir=target,
        needs_gitignore=False,
        run_tests=True,
        clone_url=clone_url,
    )


# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------

def _parse_version(text: str) -> tuple[int, ...]:
    """Extract (major, minor) from version output like 'Python 3.12.1'."""
    m = re.search(r"(\d+)\.(\d+)", text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (0, 0)


def check_command_exists(cmd: str, hint: str = "") -> StepResult:
    """Check that *cmd* is available on PATH."""
    if shutil.which(cmd):
        return StepResult(Outcome.OK, f"'{cmd}' found")
    msg = f"'{cmd}' not found."
    if hint:
        msg += f" {hint}"
    return StepResult(Outcome.FAIL, msg)


def check_python_version_preflight() -> StepResult:
    """Check python3 >= 3.12 via subprocess.

    On Windows, ``python3`` is often a Microsoft Store stub that doesn't
    actually run Python, so we try ``python`` first on that platform.
    """
    if _IS_WINDOWS:
        candidates = ["python", "python3"]
    else:
        candidates = ["python3", "python"]

    python = None
    for name in candidates:
        found = shutil.which(name)
        if found:
            python = found
            break

    if not python:
        return StepResult(
            Outcome.FAIL,
            "python3 not found. Install Python 3.12+ from "
            "https://www.python.org/downloads/",
        )
    try:
        r = subprocess.run(
            [python, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        ver = _parse_version(r.stdout + r.stderr)
        if ver == (0, 0):
            # The executable exists but didn't produce a version string
            # (common with the Windows Store python3 stub).
            return StepResult(
                Outcome.FAIL,
                f"'{python}' did not report a version. "
                "Install Python 3.12+ from https://www.python.org/downloads/",
            )
        if ver >= MIN_PYTHON:
            return StepResult(Outcome.OK, f"Python {ver[0]}.{ver[1]}")
        return StepResult(
            Outcome.FAIL,
            f"Python {ver[0]}.{ver[1]} found, but "
            f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required.",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return StepResult(Outcome.FAIL, "Could not determine Python version.")


def check_node_version_preflight() -> StepResult:
    """Check node >= 22 via subprocess."""
    if not shutil.which("node"):
        return StepResult(
            Outcome.FAIL,
            "Node.js not found. Install Node.js 22+ from https://nodejs.org/",
        )
    try:
        r = subprocess.run(
            ["node", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        ver = _parse_version(r.stdout)
        if ver[0] >= MIN_NODE:
            return StepResult(Outcome.OK, f"Node.js {ver[0]}.{ver[1]}")
        return StepResult(
            Outcome.FAIL,
            f"Node.js {ver[0]}.{ver[1]} found, but {MIN_NODE}+ is required.",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return StepResult(Outcome.FAIL, "Could not determine Node.js version.")


def run_preflight(
    mode: InstallMode = InstallMode.STANDALONE,
) -> list[StepResult]:
    """Run all preflight checks.

    Node.js and npm are only hard requirements for standalone mode (which
    always builds the web frontend).  In embedded mode they are reported
    as warnings so the install can proceed without them — the web build
    step already handles a missing npm gracefully.
    """
    results = [
        check_python_version_preflight(),
        check_node_version_preflight(),
        check_command_exists("npm"),
        check_command_exists("git"),
    ]
    if mode == InstallMode.EMBEDDED:
        # Downgrade Node/npm failures to warnings — not needed for CLI.
        for r in results:
            if r.outcome == Outcome.FAIL and (
                "Node" in r.message or "npm" in r.message
            ):
                r.outcome = Outcome.WARN
                r.message += " (optional for embedded CLI mode)"
    return results


# ---------------------------------------------------------------------------
# Individual install steps
# ---------------------------------------------------------------------------

def resolve_clone_url(agent_dir: Path) -> StepResult:
    """Get the git remote URL of the current clarity installation."""
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=agent_dir, capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return StepResult(Outcome.OK, r.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return StepResult(
        Outcome.FAIL,
        "Could not determine clarity-agent remote URL. "
        "Make sure this installation has an 'origin' remote.",
    )


def validate_target(target: Path) -> StepResult:
    """Check that *target* exists and is a git repository."""
    if not target.exists():
        return StepResult(Outcome.FAIL, f"Directory does not exist: {target}")
    if not (target / ".git").exists():
        return StepResult(Outcome.FAIL, f"Not a git repository: {target}")
    return StepResult(Outcome.OK, str(target))


def clone_or_update(target: Path, clone_url: str) -> StepResult:
    """Clone clarity-agent into *target*/.clarity-agent, or update it."""
    dest = target / CLARITY_DIR
    if (dest / ".git").exists():
        r = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=dest, capture_output=True, text=True, timeout=60,
        )
        if r.returncode == 0:
            return StepResult(Outcome.OK, f"Updated {CLARITY_DIR}")
        return StepResult(
            Outcome.WARN,
            "Could not fast-forward; continuing with current state",
        )

    r = subprocess.run(
        ["git", "clone", clone_url, str(dest)],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        return StepResult(Outcome.FAIL, _subprocess_failure("git clone", r))
    return StepResult(Outcome.OK, f"Cloned clarity agent into {CLARITY_DIR}")


def update_gitignore(target: Path) -> list[StepResult]:
    """Ensure .clarity-agent/ and clarity wrappers are in .gitignore."""
    gitignore = target / ".gitignore"
    existing: list[str] = []
    if gitignore.exists():
        existing = gitignore.read_text().splitlines()

    results: list[StepResult] = []
    additions: list[str] = []
    from clarity_agent.app_paths import protocol_dir
    proto_name = protocol_dir(target).name
    entries = [f"/{CLARITY_DIR}", "/clarity", "/clarity.ps1", "/clarity.bat",
               f"/{proto_name}/transcripts/"]
    for entry in entries:
        if entry in existing or entry.lstrip("/") in existing:
            results.append(
                StepResult(Outcome.OK, f"{entry} already in .gitignore"),
            )
        else:
            additions.append(entry)

    if additions:
        with open(gitignore, "a") as f:
            if existing and existing[-1].strip():
                f.write("\n")
            f.write("# Clarity Agent\n")
            for entry in additions:
                f.write(f"{entry}\n")
                results.append(
                    StepResult(Outcome.OK, f"Added {entry} to .gitignore"),
                )

    return results


def create_venv(venv_dir: Path) -> StepResult:
    """Create a Python venv at *venv_dir* if it doesn't exist."""
    if venv_dir.exists():
        return StepResult(Outcome.OK, f"{venv_dir.name} already exists")

    r = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        return StepResult(
            Outcome.FAIL, _subprocess_failure("venv creation", r),
        )
    return StepResult(Outcome.OK, f"Created {venv_dir.name}")


def install_python_deps(
    cwd: Path,
    venv_dir: Path,
    pip_spec: str,
) -> list[StepResult]:
    """Install Python dependencies into *venv_dir*.

    Picks an installer based on what's available, in this order:

    1. ``uv pip install --python <venv-python> -e <spec>`` when ``uv``
       is on ``$PATH``.  Required when the venv was created by
       ``uv run`` — uv-made venvs ship without pip by default, so
       ``python -m pip`` would fail with "No module named pip."  When
       uv is in play, the explicit "upgrade pip" step is skipped: uv
       has its own resolver and doesn't depend on pip's version.
    2. ``<venv-python> -m pip install -e <spec>`` otherwise.  The
       upgrade-pip step still runs but its failure is now a WARN, not
       a FAIL — the venv's bundled pip is usually fine, and the
       dependency install that follows reports a real error if not.

    Returns a list of :class:`StepResult` so each phase (upgrade /
    install) can be reported separately rather than collapsed into a
    single misleading message.
    """
    venv_python = _venv_python(venv_dir)
    results: list[StepResult] = []
    use_uv = shutil.which("uv") is not None

    if use_uv:
        # uv handles its own resolver; no pip upgrade needed (and
        # would fail anyway on uv venvs that don't ship pip).
        results.append(StepResult(
            Outcome.SKIP,
            "pip upgrade skipped (using uv pip; not applicable)",
        ))
    else:
        upgrade = subprocess.run(
            [venv_python, "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
            capture_output=True, text=True, timeout=120,
        )
        if upgrade.returncode != 0:
            # WARN, not FAIL — bundled pip is usually fine.
            results.append(StepResult(
                Outcome.WARN,
                _subprocess_failure(
                    "pip upgrade skipped (continuing with bundled pip)",
                    upgrade,
                ),
            ))
        else:
            results.append(StepResult(Outcome.OK, "pip upgraded"))

    if use_uv:
        install_cmd = [
            "uv", "pip", "install",
            "--python", venv_python,
            "-e", pip_spec,
        ]
        installer_label = "uv pip install"
    else:
        install_cmd = [venv_python, "-m", "pip", "install", "-e", pip_spec]
        installer_label = "pip install"
    install = subprocess.run(
        install_cmd, cwd=cwd, capture_output=True, text=True, timeout=300,
    )
    if install.returncode != 0:
        results.append(StepResult(
            Outcome.FAIL, _subprocess_failure(installer_label, install),
        ))
    else:
        results.append(StepResult(Outcome.OK, "Python dependencies installed"))
    return results


def build_web_frontend(web_dir: Path) -> StepResult:
    """Run npm install + build in the given web directory.

    On Windows, ``npm`` ships as ``npm.cmd``; ``subprocess.run(["npm",
    ...])`` without ``shell=True`` calls ``CreateProcess`` directly,
    which only resolves ``.exe`` — so the bare-list call raises
    ``FileNotFoundError`` even when ``shutil.which("npm")`` succeeded
    (since ``shutil.which`` honors ``PATHEXT``).  Pass ``shell=True``
    on Windows so ``cmd.exe`` resolves the ``.cmd`` shim.
    """
    if not (web_dir / "package.json").exists():
        return StepResult(Outcome.SKIP, "web/package.json not found")
    if not shutil.which("npm"):
        return StepResult(
            Outcome.WARN, "npm not found — skipping web frontend build",
        )

    try:
        r = subprocess.run(
            ["npm", "install"], cwd=web_dir,
            capture_output=True, text=True, timeout=120,
            shell=_IS_WINDOWS,
        )
    except FileNotFoundError:
        return StepResult(
            Outcome.WARN, "npm not found — skipping web frontend build",
        )
    if r.returncode != 0:
        return StepResult(Outcome.FAIL, _subprocess_failure("npm install", r))

    try:
        r = subprocess.run(
            ["npm", "run", "build"], cwd=web_dir,
            capture_output=True, text=True, timeout=120,
            shell=_IS_WINDOWS,
        )
    except FileNotFoundError:
        return StepResult(
            Outcome.WARN, "npm not found — skipping web frontend build",
        )
    if r.returncode != 0:
        return StepResult(Outcome.FAIL, _subprocess_failure("npm run build", r))
    return StepResult(Outcome.OK, "Web frontend built")


def check_claude_auth() -> tuple[bool, bool]:
    """Check if the claude CLI is available and appears to be authenticated.

    Returns:
        ``(available, logged_in)`` — whether *claude* is on PATH and whether
        it appears to have valid credentials stored locally.  The login check
        is a fast local heuristic (presence of credential files in
        ``~/.claude/``); it does not make any network calls.
    """
    if not shutil.which("claude"):
        return False, False

    claude_dir = Path.home() / ".claude"
    if not claude_dir.exists():
        return True, False

    # Any .json file in ~/.claude/ indicates prior authentication.
    if any(claude_dir.glob("*.json")):
        return True, True

    return True, False


def setup_env_file(env_dir: Path, *, claude_logged_in: bool = False) -> StepResult:
    """Copy .env.sample to .env if .env doesn't exist yet.

    If *claude_logged_in* is True the Claude SDK will handle auth and no
    .env is needed, so the step is skipped.
    """
    if claude_logged_in:
        return StepResult(Outcome.OK, "Claude SDK auth detected — skipping .env")

    env_file = env_dir / ".env"
    env_sample = env_dir / ".env.sample"

    if env_file.exists():
        return StepResult(Outcome.OK, ".env already exists")
    if env_sample.exists():
        shutil.copy2(env_sample, env_file)
        return StepResult(
            Outcome.WARN,
            "Created .env from .env.sample — edit it to set your API key(s)",
        )
    return StepResult(Outcome.WARN, "No .env.sample found; skipping .env creation")


def create_wrapper(
    target: Path,
    agent_dir: Path,
    mode: InstallMode,
) -> StepResult:
    """Create wrapper script(s) in *target*.

    On Unix, creates a ``clarity`` bash script.  On Windows, creates
    ``clarity.ps1`` (PowerShell) and ``clarity.bat`` (cmd) wrappers.
    """
    results_desc: list[str] = []

    if _IS_WINDOWS:
        # PowerShell wrapper
        ps1 = target / "clarity.ps1"
        if mode == InstallMode.STANDALONE:
            venv_py = target / ".venv" / "Scripts" / "python.exe"
            script_py = target / "clarity.py"
        else:
            venv_py = agent_dir / ".venv" / "Scripts" / "python.exe"
            script_py = agent_dir / "clarity.py"
        ps1.write_text(
            f'& "{venv_py}" "{script_py}" @args\n',
            encoding="utf-8",
        )
        results_desc.append("clarity.ps1")

        # Batch wrapper for cmd.exe
        bat = target / "clarity.bat"
        bat.write_text(
            "@echo off\n"
            f'"{venv_py}" "{script_py}" %*\n',
            encoding="utf-8",
        )
        results_desc.append("clarity.bat")
    else:
        wrapper = target / "clarity"
        if mode == InstallMode.STANDALONE:
            wrapper.write_text(
                "#!/usr/bin/env bash\n"
                'DIR="$(cd "$(dirname "$0")" && pwd)"\n'
                'exec "$DIR/.venv/bin/python" "$DIR/clarity.py" "$@"\n'
            )
        else:
            wrapper.write_text(
                "#!/usr/bin/env bash\n"
                f'DIR="{agent_dir}"\n'
                'exec "$DIR/.venv/bin/python" "$DIR/clarity.py" "$@"\n'
            )
        wrapper.chmod(0o755)
        results_desc.append("clarity")

    return StepResult(Outcome.OK, f"Wrapper(s) created: {', '.join(results_desc)}")


def insert_agent_snippet(target: Path, agent_dir: Path) -> StepResult:
    """Insert the Clarity snippet into the project's agent config file.

    Delegates to :mod:`clarity_agent.setup.snippet` (stdlib-only) for
    template rendering, target detection, and idempotent insertion.

    This import is safe because ``snippet`` only uses stdlib modules and
    this step runs after pip install in the orchestrator.
    """
    from clarity_agent.setup.snippet import (
        find_target,
        has_snippet,
        insert_snippet,
        render_snippet,
        snippet_path,
    )

    if not snippet_path().exists():
        return StepResult(Outcome.SKIP, "Snippet template not found")

    # Determine the processes path (relative for embedded installs).
    if agent_dir.name == CLARITY_DIR:
        processes_dir = f"{CLARITY_DIR}/processes"
    else:
        processes_dir = (agent_dir / "processes").as_posix()

    snippet = render_snippet(processes_dir)
    config_file = find_target(target)

    if has_snippet(config_file):
        return StepResult(Outcome.OK, f"Snippet already in {config_file.name}")

    action = insert_snippet(config_file, snippet)
    if action == "created":
        return StepResult(Outcome.OK, f"Created {config_file.name} with clarity snippet")
    return StepResult(Outcome.OK, f"Snippet {action} to {config_file.name}")


def run_tests(target: Path, venv_dir: Path) -> list[StepResult]:
    """Run pytest and vitest.  Only used in dev mode.

    Both subprocess calls are wrapped in ``FileNotFoundError`` handlers
    so a missing interpreter (broken venv) or missing ``npx`` shim
    surfaces as a FAIL StepResult instead of crashing the whole
    install with an unhandled ``WinError 2`` / ``ENOENT``.  The npx
    call also passes ``shell=True`` on Windows — same reason as
    :func:`build_web_frontend` (bare ``CreateProcess`` won't resolve
    ``npx.cmd``).
    """
    results: list[StepResult] = []
    venv_python = _venv_python(venv_dir)

    try:
        r = subprocess.run(
            [venv_python, "-m", "pytest", "tests/", "-x", "-q"],
            cwd=target, capture_output=True, text=True, timeout=300,
        )
    except FileNotFoundError as exc:
        results.append(StepResult(
            Outcome.FAIL, f"Python tests: interpreter not found ({exc})",
        ))
    else:
        if r.returncode != 0:
            results.append(StepResult(
                Outcome.FAIL, _subprocess_failure("Python tests", r),
            ))
        else:
            results.append(StepResult(Outcome.OK, "Python tests passed"))

    web_dir = target / "web"
    if (web_dir / "package.json").exists():
        try:
            r = subprocess.run(
                ["npx", "vitest", "run"],
                cwd=web_dir, capture_output=True, text=True, timeout=300,
                shell=_IS_WINDOWS,
            )
        except FileNotFoundError:
            results.append(StepResult(
                Outcome.WARN,
                "npx not found — skipping frontend tests",
            ))
        else:
            if r.returncode != 0:
                results.append(StepResult(
                    Outcome.FAIL, _subprocess_failure("Frontend tests", r),
                ))
            else:
                results.append(StepResult(Outcome.OK, "Frontend tests passed"))

    return results


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_install(
    mode: InstallMode,
    target: Path,
    agent_dir: Path | None = None,
    *,
    skip_tests: bool = False,
    claude_logged_in: bool = False,
    on_step: Callable[[StepResult], None] | None = None,
) -> list[StepResult]:
    """Run a full installation and return all step results.

    Args:
        mode: STANDALONE or EMBEDDED.
        target: For EMBEDDED, the host repo.  For STANDALONE, the
                clarity-agent repo itself.
        agent_dir: Where clarity-agent source lives (for resolving the
                   clone URL in embedded mode).  If *None*, derived from
                   this file's location.
        skip_tests: Skip test run even in dev mode.
        claude_logged_in: If True, the .env setup step is skipped because
                          the Claude SDK will handle authentication.
        on_step: Optional callback invoked with each :class:`StepResult`
                 as it completes, for real-time progress output.
    """
    results: list[StepResult] = []

    def _record(result: StepResult) -> None:
        results.append(result)
        if on_step:
            on_step(result)

    def _record_all(batch: list[StepResult]) -> None:
        for r in batch:
            _record(r)

    # -- Preflight -------------------------------------------------------
    preflight = run_preflight(mode)
    _record_all(preflight)
    if any(r.outcome == Outcome.FAIL for r in preflight):
        return results

    # -- Validate target -------------------------------------------------
    r = validate_target(target)
    _record(r)
    if r.outcome == Outcome.FAIL:
        return results

    # -- Resolve clone URL (embedded only) --------------------------------
    clone_url = None
    if mode == InstallMode.EMBEDDED:
        if agent_dir is None:
            agent_dir = Path(__file__).resolve().parent.parent.parent.parent
        url_result = resolve_clone_url(agent_dir)
        _record(url_result)
        if url_result.outcome == Outcome.FAIL:
            return results
        clone_url = url_result.message

    config = resolve_config(mode, target, agent_dir or target, clone_url)

    # -- Clone/update (embedded only) ------------------------------------
    if mode == InstallMode.EMBEDDED:
        r = clone_or_update(target, config.clone_url)  # type: ignore[arg-type]
        _record(r)
        if r.outcome == Outcome.FAIL:
            return results

    # -- Gitignore (embedded only) ---------------------------------------
    if config.needs_gitignore:
        _record_all(update_gitignore(target))

    # -- Venv ------------------------------------------------------------
    r = create_venv(config.venv_dir)
    _record(r)
    if r.outcome == Outcome.FAIL:
        return results

    # -- Pip install -----------------------------------------------------
    pip_results = install_python_deps(
        config.pip_cwd, config.venv_dir, config.pip_install_spec,
    )
    _record_all(pip_results)
    if any(r.outcome == Outcome.FAIL for r in pip_results):
        return results

    # -- Web frontend ----------------------------------------------------
    r = build_web_frontend(config.web_dir)
    _record(r)
    if r.outcome == Outcome.FAIL:
        return results

    # -- .env file -------------------------------------------------------
    _record(setup_env_file(config.env_dir, claude_logged_in=claude_logged_in))

    # -- Wrapper ---------------------------------------------------------
    _record(create_wrapper(config.target, config.agent_dir, config.mode))

    # -- Agent config snippet (embedded only) ----------------------------
    if mode == InstallMode.EMBEDDED:
        _record(insert_agent_snippet(config.target, config.agent_dir))

    # -- Tests (dev only) ------------------------------------------------
    if config.run_tests and not skip_tests:
        _record_all(run_tests(config.target, config.venv_dir))

    return results


# ---------------------------------------------------------------------------
# CLI entry point  (called by install.sh or ``python -m``)
# ---------------------------------------------------------------------------

def _cli_main(argv: Sequence[str] | None = None) -> None:
    """Parse args and run install, printing coloured results."""
    parser = argparse.ArgumentParser(
        description="Install clarity-agent (standalone or embedded mode)",
    )
    parser.add_argument(
        "--mode",
        choices=["standalone", "embedded"],
        default="standalone",
        help="Installation mode (default: standalone)",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path.cwd(),
        help="Target directory (default: current working directory)",
    )
    parser.add_argument(
        "--agent-dir",
        type=Path,
        default=None,
        help="Clarity-agent source directory (for embedded clone URL)",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running tests in dev mode",
    )
    args = parser.parse_args(argv)

    mode = InstallMode(args.mode)
    target = args.target.resolve()

    # -- Coloured output helpers (match bash script style) ----------------
    use_color = "NO_COLOR" not in os.environ and sys.stdout.isatty()

    def info(msg: str) -> None:
        if use_color:
            print(f"\033[1;34m==> {msg}\033[0m")
        else:
            print(f"==> {msg}")

    def emit(result: StepResult) -> None:
        _FMT = {
            Outcome.OK:   ("\033[1;32m  \u2713 {}\033[0m", "  OK: {}"),
            Outcome.WARN: ("\033[1;33m  \u26a0 {}\033[0m", "  WARN: {}"),
            Outcome.FAIL: ("\033[1;31m  \u2717 {}\033[0m", "  FAIL: {}"),
            Outcome.SKIP: ("\033[1;33m  - {}\033[0m",      "  SKIP: {}"),
        }
        color_fmt, plain_fmt = _FMT[result.outcome]
        print((color_fmt if use_color else plain_fmt).format(result.message))

    # -- Auth check & interactive prompt ---------------------------------
    claude_available, claude_logged_in = check_claude_auth()

    # Skip the interactive auth prompt in CI or when stdin is not a TTY
    # (e.g. piped input).  The .env file will still be created from
    # .env.sample by setup_env_file if auth is not configured.
    # Use an explicit check so that CI=false / CI=0 is treated as non-CI.
    _in_ci = os.environ.get("CI", "").lower() in ("1", "true", "yes")
    _interactive = not _in_ci and sys.stdin.isatty()

    if not claude_logged_in and _interactive:
        print()
        if claude_available:
            info("Claude CLI detected but not logged in")
            print("  How would you like to authenticate?")
            print("  [l] Run 'claude login' now")
            print("  [e] Add an API key to .env  (Anthropic, OpenAI, or Azure)")
            print("  [s] Skip for now (use for Azure az login)")
            print()
        else:
            info("No authentication configured")
            print("  How would you like to authenticate?")
            print("  [l] Install & log in with the Claude CLI")
            print("      https://claude.ai/download")
            print("  [e] Add an API key to .env  (Anthropic, OpenAI, or Azure)")
            print("  [s] Skip for now (use for Azure az login)")
            print()

        try:
            choice = input("  Choice [l/e/s]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            choice = "s"

        if choice == "l":
            if not claude_available:
                print()
                print("  Install the Claude CLI first, then run 'claude login'.")
                print("  https://claude.ai/download")
                print()
            else:
                print()
                subprocess.run(["claude", "login"])
                _, claude_logged_in = check_claude_auth()
                print()
        elif choice == "e":
            pass  # setup_env_file will create .env during install
        # "s" or anything else: skip

    # -- Run installation ------------------------------------------------
    info(f"Installing clarity-agent ({mode.value} mode)")
    results = run_install(
        mode, target, args.agent_dir,
        skip_tests=args.skip_tests,
        claude_logged_in=claude_logged_in,
        on_step=emit,
    )

    if any(r.outcome == Outcome.FAIL for r in results):
        print()
        info("Installation failed.  See errors above.")
        raise SystemExit(1)

    # -- Success message --------------------------------------------------
    print()
    info("Setup complete!")
    print()
    if _IS_WINDOWS:
        wrapper = "clarity.ps1"
        sep = "\\"
    else:
        wrapper = "clarity"
        sep = "/"

    if mode == InstallMode.STANDALONE:
        print("  Quick start (point at any project):")
        print(f"    {target}{sep}{wrapper} <project-dir>    # Launch web UI")
        print(f"    {target}{sep}{wrapper} cli <project-dir> # Interactive CLI")
        if not _IS_WINDOWS:
            print()
            print("  Tip: add an alias to your shell profile:")
            print(f"    alias clarity='{target}/clarity'")
    else:
        print("  Quick start (from the project directory):")
        print(f"    cd {target}")
        if _IS_WINDOWS:
            print(f"    .\\{wrapper}                       # Launch web UI")
            print(f"    .\\{wrapper} cli                    # Interactive CLI session")
        else:
            print(f"    ./{wrapper}                        # Launch web UI")
            print(f"    ./{wrapper} cli                    # Interactive CLI session")
    print()
    if not claude_logged_in:
        print("  Authentication (pick one):")
        print("    claude login                     # Claude SDK")
        if _IS_WINDOWS:
            print("    notepad .env                     # Set API key (Anthropic, OpenAI, or Azure)")
        else:
            print("    $EDITOR .env                     # Set API key (Anthropic, OpenAI, or Azure)")
        print("    az login                         # Azure without API key")
        print()


if __name__ == "__main__":
    _cli_main()
