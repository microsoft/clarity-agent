"""Check for and apply clarity-agent updates.

In development (git checkout): compares local HEAD against origin/main,
and orchestrates git pull + pip install + web rebuild when updating.

In frozen (PyInstaller) builds: queries the GitHub Releases API to check
for a newer version, and provides a download URL.

**Stdlib-only** — same constraint as installer.py: no third-party imports.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from clarity_agent.setup.installer import (
    Outcome,
    StepResult,
    build_web_frontend,
    install_python_deps,
)
from clarity_agent.setup.layout import EMBEDDED_AGENT_SUBDIR

# Data shapes live in :mod:`setup.types`.  This module is the
# producer of ``UpdateStatus`` and ``GitUpdate`` — re-exported here
# so callers still doing ``from setup.updater import GitUpdate``
# keep working.  Callers are encouraged to consume them through
# ``setup.version.current_state`` rather than constructing them
# directly.
from clarity_agent.setup.types import GitUpdate, UpdateStatus

# Re-exported via __all__ so static analyzers see them as part of
# this module's public surface (otherwise they look unused-here).
__all__ = [
    "GitUpdate",
    "Outcome",
    "StepResult",
    "UpdateStatus",
    "build_web_frontend",
    "check_for_updates",
    "install_python_deps",
    "run_update",
    "schedule_restart",
]

# GitHub repo for release checks.
_GITHUB_REPO = "microsoft/clarity-agent"


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


# Version parsing + comparison live in
# ``clarity_agent.setup.release_feed`` now (the abstraction that
# also drives the frontend's update-available indicator).  Old
# ``_parse_version`` helper is gone — the only caller was
# ``_check_github_release``, which delegates to the shared
# ``check_for_update`` orchestrator.


def _check_github_release() -> UpdateStatus:
    """Check GitHub Releases for a newer version (used in frozen builds).

    Delegates to :func:`~clarity_agent.setup.release_feed.check_for_update`
    so the comparison + parsing logic has exactly one production
    implementation (this CLI path) and one unit-testable surface
    (``setup/release_feed.py``).
    """
    from .release_feed import check_for_update
    from .version import current_version as _cv

    avail = check_for_update()
    current_str = _cv().version

    if avail.status == "available" and avail.latest is not None:
        # Surface the GitHub Release page (where the assets live) as
        # the download URL; matches the prior behavior of pointing
        # the user at the releases page rather than at a raw asset.
        download_url = (
            f"https://github.com/{_GITHUB_REPO}/releases/tag/"
            f"{avail.latest.version}"
        )
        return UpdateStatus(
            available=True, local_sha=current_str,
            remote_sha=avail.latest.version,
            commit_count=0, frozen=True,
            current_version=current_str,
            latest_version=avail.latest.version.lstrip("v"),
            download_url=download_url,
        )

    remote = avail.latest.version if avail.latest else None
    return UpdateStatus(
        available=False, local_sha=current_str, remote_sha=remote,
        commit_count=0, frozen=True,
        current_version=current_str,
        latest_version=(remote.lstrip("v") if remote else None),
    )


def _check_git_updates(agent_dir: Path) -> UpdateStatus:
    """Check the current branch's upstream for newer commits.

    Tracks ``origin/<current-branch>`` rather than always
    ``origin/main`` — a contributor working on ``issue48-1`` wants
    to know about updates on that branch, not on main.  When the
    current branch has no remote counterpart (``rev-parse`` fails),
    we return ``available=False`` with ``remote_sha=None``; the
    endpoint surfaces this as ``update_status="unknown"`` with a
    reason so the UI stays silent rather than guessing.

    Detached HEAD is treated the same as "no upstream" — we don't
    have a sensible branch to compare against.
    """
    local_sha = _git_head(agent_dir)
    branch = _git_current_branch(agent_dir)

    if branch is None or branch == "HEAD":
        # Detached HEAD — nothing to compare against.
        return UpdateStatus(
            available=False, local_sha=local_sha, remote_sha=None, commit_count=0,
        )

    try:
        _git_fetch(agent_dir)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return UpdateStatus(
            available=False, local_sha=local_sha, remote_sha=None, commit_count=0,
        )

    upstream = f"origin/{branch}"
    try:
        remote_sha = subprocess.check_output(
            ["git", "rev-parse", upstream], cwd=agent_dir, text=True, timeout=10,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Branch exists locally but isn't pushed (or its upstream
        # has a different name).  Endpoint surfaces this as
        # ``unknown`` — the badge stays silent.
        return UpdateStatus(
            available=False, local_sha=local_sha, remote_sha=None, commit_count=0,
        )

    if local_sha == remote_sha:
        return UpdateStatus(
            available=False, local_sha=local_sha, remote_sha=remote_sha, commit_count=0,
        )

    try:
        count_str = subprocess.check_output(
            ["git", "rev-list", "--count", f"HEAD..{upstream}"],
            cwd=agent_dir, text=True, timeout=10,
        ).strip()
        commit_count = int(count_str)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        commit_count = 0

    # ``commit_count == 0`` means HEAD has diverged from origin
    # (local has commits the remote doesn't, but the remote has none
    # we don't).  Per the v1 design we surface a badge only when
    # there are upstream commits to pull, so collapse this case to
    # "not available."
    if commit_count == 0:
        return UpdateStatus(
            available=False, local_sha=local_sha, remote_sha=remote_sha, commit_count=0,
        )

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
        if parent_venv.exists() and agent_dir.name == EMBEDDED_AGENT_SUBDIR:
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
    # We update whichever branch the checkout is currently on,
    # pulling from ``origin/<branch>``.  The detached-HEAD case is
    # still a hard error because there's no sensible upstream to
    # pull from.  Diverged-local-commits is caught downstream by
    # ``git pull --ff-only`` refusing to fast-forward.
    branch = _git_current_branch(agent_dir)
    if branch is None or branch == "HEAD":
        _record(StepResult(
            Outcome.FAIL,
            "Detached HEAD state — cannot update. Check out a branch first.",
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
    pip_results = install_python_deps(pip_cwd, venv_dir, pip_spec)
    for pr in pip_results:
        _record(pr)
    if any(pr.outcome == Outcome.FAIL for pr in pip_results):
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
