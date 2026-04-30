"""Check for and apply clarity-agent updates.

In development (git checkout): compares local HEAD against origin/main,
and orchestrates git pull + pip install + web rebuild when updating.

In frozen (PyInstaller) builds: queries the GitHub Releases API to check
for a newer version, and provides a download URL.

**Stdlib-only** — same constraint as installer.py: no third-party imports.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from clarity_agent.setup.installer import (
    Outcome,
    StepResult,
    build_web_frontend,
    install_python_deps,
)

# GitHub repo for release checks.
_GITHUB_REPO = "microsoft/clarity-agent"


@dataclass
class UpdateStatus:
    """Result of checking for available updates."""

    available: bool
    local_sha: str
    remote_sha: str | None
    commit_count: int  # number of commits behind origin/main
    # Fields used only in frozen mode:
    frozen: bool = False
    current_version: str | None = None
    latest_version: str | None = None
    download_url: str | None = None


def _git_head(cwd: Path) -> str:
    """Return the current HEAD commit SHA."""
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=cwd, text=True, timeout=10,
    ).strip()


def _git_current_branch(cwd: Path) -> str | None:
    """Return the current branch name, or None if in detached HEAD state."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, text=True, timeout=10,
        ).strip() or None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def _git_fetch(cwd: Path, *, timeout: int = 30) -> None:
    """Fetch from origin (quiet)."""
    subprocess.run(
        ["git", "fetch", "--quiet"], cwd=cwd, timeout=timeout,
        capture_output=True, check=True,
    )


def _parse_version(tag: str) -> tuple[int, ...]:
    """Parse a version tag like 'v1.2.3' into a comparable tuple."""
    return tuple(int(x) for x in tag.lstrip("v").split(".") if x.isdigit())


def _check_github_release() -> UpdateStatus:
    """Check GitHub Releases for a newer version (used in frozen builds)."""

    # Read current version from pyproject.toml metadata or package
    try:
        from importlib.metadata import version as pkg_version
        current = pkg_version("clarity-agent")
    except Exception:
        current = "0.0.0"

    url = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return UpdateStatus(
            available=False, local_sha=current, remote_sha=None,
            commit_count=0, frozen=True, current_version=current,
        )

    latest_tag = data.get("tag_name", "")
    html_url = data.get("html_url", "")

    if _parse_version(latest_tag) > _parse_version(current):
        return UpdateStatus(
            available=True, local_sha=current, remote_sha=latest_tag,
            commit_count=0, frozen=True,
            current_version=current, latest_version=latest_tag.lstrip("v"),
            download_url=html_url,
        )

    return UpdateStatus(
        available=False, local_sha=current, remote_sha=latest_tag,
        commit_count=0, frozen=True,
        current_version=current, latest_version=latest_tag.lstrip("v"),
    )


def _check_git_updates(agent_dir: Path) -> UpdateStatus:
    """Check git origin/main for newer commits (used in dev checkouts)."""
    local_sha = _git_head(agent_dir)

    try:
        _git_fetch(agent_dir)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return UpdateStatus(
            available=False, local_sha=local_sha, remote_sha=None, commit_count=0,
        )

    try:
        remote_sha = subprocess.check_output(
            ["git", "rev-parse", "origin/main"], cwd=agent_dir, text=True, timeout=10,
        ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return UpdateStatus(
            available=False, local_sha=local_sha, remote_sha=None, commit_count=0,
        )

    if local_sha == remote_sha:
        return UpdateStatus(
            available=False, local_sha=local_sha, remote_sha=remote_sha, commit_count=0,
        )

    try:
        count_str = subprocess.check_output(
            ["git", "rev-list", "--count", "HEAD..origin/main"],
            cwd=agent_dir, text=True, timeout=10,
        ).strip()
        commit_count = int(count_str)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        commit_count = 0

    return UpdateStatus(
        available=True,
        local_sha=local_sha,
        remote_sha=remote_sha,
        commit_count=commit_count,
    )


def check_for_updates(agent_dir: Path) -> UpdateStatus:
    """Check whether a newer version is available.

    In frozen (PyInstaller) builds, queries the GitHub Releases API.
    In development, uses git fetch + rev-parse against origin/main.
    """
    from clarity_agent.app_paths import is_frozen

    if is_frozen():
        return _check_github_release()
    return _check_git_updates(agent_dir)


# ---------------------------------------------------------------------------
# Update execution
# ---------------------------------------------------------------------------

def _detect_pip_spec(agent_dir: Path) -> tuple[Path, Path, str]:
    """Detect venv location and pip install spec for this installation.

    Returns (venv_dir, pip_cwd, pip_spec).
    """
    # Embedded install: agent_dir is <project>/.clarity-agent/
    # In that case the venv and pip spec live relative to the project root.
    parent = agent_dir.parent
    embedded_venv = agent_dir / ".venv"
    standalone_venv = agent_dir / ".venv"

    if embedded_venv.exists():
        # Could be either mode — check for the project-root venv pattern.
        parent_venv = parent / ".venv"
        if parent_venv.exists() and agent_dir.name == ".clarity-agent":
            # Embedded mode: pip cwd is the project root.
            return parent_venv, parent, "./.clarity-agent[cli,web,brainstorm,docx,openai,azure]"

    if standalone_venv.exists():
        return standalone_venv, agent_dir, ".[dev]"

    # Fallback: assume standalone from current Python.
    return Path(sys.prefix), agent_dir, ".[dev]"


def run_update(
    agent_dir: Path,
    *,
    on_step: Callable[[StepResult], None] | None = None,
) -> list[StepResult]:
    """Pull latest code, reinstall deps, and rebuild the web frontend.

    Args:
        agent_dir: Path to the clarity-agent repository.
        on_step: Optional callback for real-time progress output.

    Returns:
        List of all step results.
    """
    results: list[StepResult] = []

    def _record(result: StepResult) -> None:
        results.append(result)
        if on_step:
            on_step(result)

    # -- Branch check ----------------------------------------------------
    branch = _git_current_branch(agent_dir)
    if branch is None:
        _record(StepResult(
            Outcome.FAIL,
            "Detached HEAD state — cannot update. Check out a branch first.",
        ))
        return results
    if branch != "main":
        _record(StepResult(
            Outcome.FAIL,
            f"On branch '{branch}', not 'main'. "
            "Switch to main before updating to avoid overwriting your work.",
        ))
        return results

    old_sha = _git_head(agent_dir)

    # -- Git pull --------------------------------------------------------
    r = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=agent_dir, capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        stderr = r.stderr.strip()
        if "not possible to fast-forward" in stderr or "Cannot fast-forward" in stderr:
            _record(StepResult(
                Outcome.FAIL,
                "Cannot fast-forward — you may have local changes. "
                "Try 'git stash' in the clarity-agent directory first.",
            ))
        else:
            _record(StepResult(Outcome.FAIL, f"git pull failed: {stderr}"))
        return results

    new_sha = _git_head(agent_dir)
    if old_sha == new_sha:
        _record(StepResult(Outcome.OK, "Already up to date"))
        return results

    _record(StepResult(Outcome.OK, f"Updated {old_sha[:8]} → {new_sha[:8]}"))

    # -- Pip install -----------------------------------------------------
    venv_dir, pip_cwd, pip_spec = _detect_pip_spec(agent_dir)
    r = install_python_deps(pip_cwd, venv_dir, pip_spec)
    _record(r)
    if r.outcome == Outcome.FAIL:
        return results

    # -- Web frontend rebuild -------------------------------------------
    web_dir = agent_dir / "web"
    r = build_web_frontend(web_dir)
    _record(r)

    # Future: could show a changelog summary here using
    # git log --oneline {old_sha}..{new_sha}

    return results


# ---------------------------------------------------------------------------
# Server restart
# ---------------------------------------------------------------------------

def schedule_restart(*, delay: float = 0.5) -> None:
    """Replace the current process with a fresh one after a short delay.

    The delay allows the calling HTTP handler to send its response before
    the process is replaced.  Uses ``os.execv`` so the new process inherits
    the same PID (on Unix) and command-line arguments.
    """
    def _do_restart() -> None:
        os.execv(sys.executable, [sys.executable, *sys.argv])

    t = threading.Timer(delay, _do_restart)
    t.daemon = True
    t.start()
