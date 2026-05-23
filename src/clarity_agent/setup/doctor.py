"""Diagnostic checks for a clarity-agent installation.

Provides :func:`run_all_checks` to validate the health of the
clarity-agent setup — Python version, dependencies, LLM provider
configuration, and backend connectivity.  Each check returns a
:class:`CheckResult` with a status, human-readable message, and an
optional auto-fix function.

The check library is intentionally LLM-free: a broken LLM connection
is one of the most common problems users hit, so the doctor must work
without one.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

# ``EMBEDDED_AGENT_SUBDIR`` is the canonical name of the in-repo
# clarity-agent install directory (``.clarity-agent``).  Importing it
# here keeps both ``check_installation_type`` call sites from
# duplicating the literal — the test for "is this an embedded install"
# is one place, period.  The module is stdlib-only and has no cycle
# risk, so a regular import works.
from .layout import EMBEDDED_AGENT_SUBDIR

if TYPE_CHECKING:
    # Imported under TYPE_CHECKING so type-checkers can resolve the
    # ``ProjectLayout`` annotation on ``_refresh_snippet_fix`` without
    # importing the module at runtime (it's already imported lazily
    # inside the function that needs the type).
    from .layout import ProjectLayout

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class Status(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""

    name: str
    status: Status
    message: str
    fix_hint: str | None = None
    fix_fn: Callable[[], bool] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _try_import(module_name: str) -> bool:
    """Return True if *module_name* can be imported."""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def _find_git_root(path: Path) -> Path | None:
    """Walk upward from *path* looking for a ``.git`` directory."""
    current = path.resolve()
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _make_pip_install_fn(spec: str) -> Callable[[], bool]:
    """Return a callable that runs ``pip install <spec>``."""
    def _install() -> bool:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", spec],
            capture_output=True, timeout=120,
        )
        return r.returncode == 0
    return _install


def _prompt(text: str) -> str:
    """Read a line of input, using prompt_toolkit if available."""
    try:
        from prompt_toolkit import prompt as pt_prompt
        return pt_prompt(text)
    except ImportError:
        return input(text)


def _confirm(text: str) -> bool:
    """Ask a yes/no question, defaulting to no."""
    return _prompt(f"{text} [y/N] ").strip().lower() in ("y", "yes")


def _update_env_var(env_path: Path, key: str, value: str) -> bool:
    """Set *key*=*value* in *env_path*, creating the file if needed.

    If the key already exists, its line is replaced.  Otherwise a new
    line is appended.
    """
    lines: list[str] = []
    replaced = False
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith(f"{key}=") or line.startswith(f"# {key}="):
                lines.append(f"{key}={value}")
                replaced = True
            else:
                lines.append(line)
    if not replaced:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n")
    os.environ[key] = value
    return True


# ---------------------------------------------------------------------------
# Check: installation type
# ---------------------------------------------------------------------------

def check_installation_type(agent_dir: Path) -> list[CheckResult]:
    """Determine standalone vs in-repo installation and validate."""
    results: list[CheckResult] = []

    if not (agent_dir / ".git").exists():
        results.append(CheckResult(
            name="Installation type",
            status=Status.WARN,
            message=f"Not a git repo at {agent_dir} (running from extracted archive?)",
        ))
        return results

    # Check if agent_dir lives inside a parent git repo.
    parent_git = _find_git_root(agent_dir.parent)
    is_embedded = parent_git is not None and agent_dir.name == EMBEDDED_AGENT_SUBDIR

    if is_embedded:
        assert parent_git is not None  # guaranteed by is_embedded check
        results.append(CheckResult(
            name="Installation type",
            status=Status.PASS,
            message=f"In-repo installation inside {parent_git}",
        ))
        # Sub-check: Clarity block in the host repo's AGENTS.md.  Now
        # delegates to the same ``ensure_agents_md`` reconcile loop the
        # runtime uses, so the doctor and the runtime agree on what
        # "in sync" means.  Embedded mode → relative paths in the
        # rendered block.
        from .layout import (
            PROTOCOL_DIR_DOT,
            Mode,
            ProjectLayout,
        )
        from .snippet import has_snippet, snippet_path
        layout = ProjectLayout(
            mode=Mode.EMBEDDED,
            project_dir=parent_git,
            clarity_agent_dir=agent_dir,
            protocol_dir=parent_git / PROTOCOL_DIR_DOT,
        )
        target = layout.agents_md
        if has_snippet(target):
            # Distinguish "in sync" from "present but drifted".  We
            # don't actually rewrite here — that would be a side
            # effect inside a check; the fix_fn does the rewriting if
            # the user opts in.
            from .snippet import _current_meta, _extract_block, parse_meta
            existing_block = _extract_block(target.read_text(encoding="utf-8"))
            existing_meta = parse_meta(existing_block) if existing_block else None
            if existing_meta == _current_meta(layout):
                results.append(CheckResult(
                    name="Agent config",
                    status=Status.PASS,
                    message=f"{target.name} contains current clarity snippet",
                ))
            else:
                results.append(CheckResult(
                    name="Agent config",
                    status=Status.WARN,
                    message=f"{target.name} clarity snippet is stale",
                    fix_hint=f"Refresh clarity snippet in {target.name}",
                    fix_fn=_refresh_snippet_fix(layout),
                ))
        else:
            fix_fn: Callable[[], bool] | None = None
            if snippet_path().exists():
                fix_fn = _refresh_snippet_fix(layout)
            if target.exists():
                results.append(CheckResult(
                    name="Agent config",
                    status=Status.WARN,
                    message=f"{target.name} exists but has no clarity snippet",
                    fix_hint=f"Insert clarity snippet into {target.name}",
                    fix_fn=fix_fn,
                ))
            else:
                results.append(CheckResult(
                    name="Agent config",
                    status=Status.WARN,
                    message=f"No {target.name} in {parent_git}",
                    fix_hint=f"Create {target.name} with clarity snippet",
                    fix_fn=fix_fn,
                ))
    else:
        results.append(CheckResult(
            name="Installation type",
            status=Status.PASS,
            message=f"Standalone installation at {agent_dir}",
        ))

    return results


def _refresh_snippet_fix(layout: ProjectLayout) -> Callable[[], bool]:
    """Build a fix_fn that runs ``ensure_agents_md`` against *layout*.

    Wrapping it lets ``check_installation_type`` reuse the same fixer
    for the "no snippet" and "stale snippet" branches, and keeps the
    closure capture explicit.
    """
    from .snippet import EnsureStatus, ensure_agents_md

    def _fix() -> bool:
        return ensure_agents_md(layout) is not EnsureStatus.UNCHANGED

    return _fix


# ---------------------------------------------------------------------------
# Check: repo freshness
# ---------------------------------------------------------------------------

def check_repo_freshness(agent_dir: Path) -> CheckResult:
    """Check if the clarity-agent repo is up to date with its remote."""
    if not (agent_dir / ".git").exists():
        return CheckResult(
            name="Repo freshness",
            status=Status.WARN,
            message="Not a git repo; cannot check freshness",
        )

    try:
        subprocess.run(
            ["git", "fetch", "--quiet"],
            cwd=agent_dir, capture_output=True, timeout=15,
        )
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..@{u}"],
            cwd=agent_dir, capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return CheckResult(
                name="Repo freshness",
                status=Status.WARN,
                message="Could not determine freshness (no upstream branch?)",
            )
        behind = int(result.stdout.strip())
        if behind == 0:
            return CheckResult(
                name="Repo freshness",
                status=Status.PASS,
                message="Up to date with remote",
            )

        def _pull(_d: Path = agent_dir) -> bool:
            r = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=_d, capture_output=True, timeout=30,
            )
            return r.returncode == 0

        return CheckResult(
            name="Repo freshness",
            status=Status.WARN,
            message=f"{behind} commit(s) behind remote",
            fix_hint="Run 'git pull --ff-only' to update",
            fix_fn=_pull,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        return CheckResult(
            name="Repo freshness",
            status=Status.WARN,
            message="Could not check freshness (git error or timeout)",
        )


# ---------------------------------------------------------------------------
# Check: Python version
# ---------------------------------------------------------------------------

def check_python_version() -> CheckResult:
    """Verify Python >= 3.12."""
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 12):
        return CheckResult(
            name="Python version",
            status=Status.PASS,
            message=f"Python {major}.{minor}",
        )
    return CheckResult(
        name="Python version",
        status=Status.FAIL,
        message=f"Python {major}.{minor} found, but 3.12+ is required",
        fix_hint="Install Python 3.12+ from https://www.python.org/downloads/",
    )


# ---------------------------------------------------------------------------
# Check: Python dependencies
# ---------------------------------------------------------------------------

# (import_name, pip_name)
_CORE_DEPS: list[tuple[str, str]] = [
    ("prompt_toolkit", "prompt-toolkit"),
]

_CLI_DEPS: list[tuple[str, str]] = [
    ("anthropic", "anthropic"),
    ("dotenv", "python-dotenv"),
    ("claude_agent_sdk", "claude-agent-sdk"),
]


def check_python_dependencies(agent_dir: Path) -> list[CheckResult]:
    """Check that required Python packages are importable."""
    results: list[CheckResult] = []

    # Core dependencies — FAIL if missing.
    for import_name, pip_name in _CORE_DEPS:
        if _try_import(import_name):
            results.append(CheckResult(
                name=f"Package: {pip_name}",
                status=Status.PASS,
                message=f"{pip_name} is installed",
            ))
        else:
            results.append(CheckResult(
                name=f"Package: {pip_name}",
                status=Status.FAIL,
                message=f"Core dependency {pip_name} is not installed",
                fix_hint=f"pip install {pip_name}",
                fix_fn=_make_pip_install_fn(pip_name),
            ))

    # CLI dependencies — WARN if missing.
    for import_name, pip_name in _CLI_DEPS:
        if _try_import(import_name):
            results.append(CheckResult(
                name=f"Package: {pip_name}",
                status=Status.PASS,
                message=f"{pip_name} is installed",
            ))
        else:
            install_spec = f"{agent_dir}[cli]"
            results.append(CheckResult(
                name=f"Package: {pip_name}",
                status=Status.WARN,
                message=f"CLI dependency {pip_name} is not installed",
                fix_hint=f"pip install '{install_spec}'",
                fix_fn=_make_pip_install_fn(install_spec),
            ))

    # Provider-specific: check packages for auth modes that have credentials.
    from clarity_agent.llm.config import _PROVIDERS, _has_package
    for prov_name, prov_info in _PROVIDERS.items():
        for mode in prov_info["auth_modes"]:
            pkg = mode.get("package")
            if not pkg:
                continue
            ev = mode.get("env_var")
            # Only warn if the auth mode might be active (has non-key auth,
            # or its env var is set).
            might_use = (
                mode["name"] != "api_key"
                or (ev and os.environ.get(ev))
            )
            if might_use and not _has_package(pkg):
                if prov_name in ("azure", "openai"):
                    spec = f"{agent_dir}[{prov_name}]"
                else:
                    spec = pkg.replace(".", "-")
                results.append(CheckResult(
                    name=f"Package: {pkg} ({prov_name}/{mode['name']})",
                    status=Status.WARN,
                    message=(
                        f"Auth mode '{mode['name']}' for {prov_name} requires "
                        f"package '{pkg}' which is not installed"
                    ),
                    fix_hint=f"pip install '{spec}'",
                    fix_fn=_make_pip_install_fn(spec),
                ))

    return results


# ---------------------------------------------------------------------------
# Check: NPM / web dependencies
# ---------------------------------------------------------------------------

def check_npm_dependencies(agent_dir: Path) -> list[CheckResult]:
    """Check Node.js, npm, and web/ dependencies (all WARN-level)."""
    results: list[CheckResult] = []
    web_dir = agent_dir / "web"

    if not (web_dir / "package.json").exists():
        # Web UI is not present in this installation.
        return results

    # Node.js installed?
    if not shutil.which("node"):
        results.append(CheckResult(
            name="Node.js",
            status=Status.WARN,
            message="Node.js not found (needed for web UI)",
            fix_hint="Install Node.js 22+ from https://nodejs.org/",
        ))
        return results

    # Node.js version >= 22?
    try:
        ver_out = subprocess.run(
            ["node", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        ver_str = ver_out.stdout.strip().lstrip("v")
        major = int(ver_str.split(".")[0])
        if major >= 22:
            results.append(CheckResult(
                name="Node.js version",
                status=Status.PASS,
                message=f"Node.js {ver_str}",
            ))
        else:
            results.append(CheckResult(
                name="Node.js version",
                status=Status.WARN,
                message=f"Node.js {ver_str} found, but 22+ is recommended",
                fix_hint="Install Node.js 22+ from https://nodejs.org/",
            ))
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass

    # node_modules present?
    if not (web_dir / "node_modules").exists():
        def _npm_install(_d: Path = web_dir) -> bool:
            r = subprocess.run(
                ["npm", "install"], cwd=_d,
                capture_output=True, timeout=120,
            )
            return r.returncode == 0

        results.append(CheckResult(
            name="NPM packages",
            status=Status.WARN,
            message="web/node_modules not found",
            fix_hint="Run 'npm install' in web/",
            fix_fn=_npm_install,
        ))
    else:
        results.append(CheckResult(
            name="NPM packages",
            status=Status.PASS,
            message="web/node_modules exists",
        ))

    # web/dist built?
    if not (web_dir / "dist").exists():
        def _npm_build(_d: Path = web_dir) -> bool:
            r = subprocess.run(
                ["npm", "run", "build"], cwd=_d,
                capture_output=True, timeout=120,
            )
            return r.returncode == 0

        results.append(CheckResult(
            name="Web build",
            status=Status.WARN,
            message="web/dist not found (web UI not built)",
            fix_hint="Run 'npm run build' in web/",
            fix_fn=_npm_build,
        ))
    else:
        results.append(CheckResult(
            name="Web build",
            status=Status.PASS,
            message="web/dist exists",
        ))

    return results


# ---------------------------------------------------------------------------
# Check: clarity wrapper command
# ---------------------------------------------------------------------------

def check_clarity_command(agent_dir: Path) -> CheckResult:
    """Check that the ``clarity`` wrapper script exists and is runnable."""
    # For standalone installs the wrapper lives in agent_dir itself;
    # for embedded installs (.clarity-agent/) it lives in the host repo root.
    parent_git = _find_git_root(agent_dir.parent)
    is_embedded = parent_git is not None and agent_dir.name == EMBEDDED_AGENT_SUBDIR

    if is_embedded and parent_git is not None:
        wrapper_path = parent_git / "clarity"
    else:
        wrapper_path = agent_dir / "clarity"

    if wrapper_path.exists() and os.access(wrapper_path, os.X_OK):
        return CheckResult(
            name="Clarity command",
            status=Status.PASS,
            message=f"Wrapper script found at {wrapper_path}",
        )

    # Maybe it's on PATH even if not at the expected location.
    which_clarity = shutil.which("clarity")
    if which_clarity is not None:
        return CheckResult(
            name="Clarity command",
            status=Status.PASS,
            message=f"'clarity' found on PATH at {which_clarity}",
        )

    # Determine which install script to suggest.
    install_script = agent_dir / "install.sh"
    if is_embedded:
        fix_hint = (
            f"Run the installation script to create the wrapper:\n"
            f"  bash {install_script}"
        )
    else:
        fix_hint = (
            f"Run the installation script to create the wrapper:\n"
            f"  bash {install_script}"
        )

    def _create_wrapper(
        _agent_dir: Path = agent_dir,
        _wrapper_path: Path = wrapper_path,
        _is_embedded: bool = is_embedded,
    ) -> bool:
        if _is_embedded:
            # Embedded: wrapper at host repo root, points into .clarity-agent
            content = (
                "#!/usr/bin/env bash\n"
                f'DIR="{_agent_dir}"\n'
                'exec "$DIR/.venv/bin/python" "$DIR/clarity.py" "$@"\n'
            )
        else:
            # Standalone: wrapper in agent_dir itself
            content = (
                "#!/usr/bin/env bash\n"
                'DIR="$(cd "$(dirname "$0")" && pwd)"\n'
                'exec "$DIR/.venv/bin/python" "$DIR/clarity.py" "$@"\n'
            )
        _wrapper_path.write_text(content)
        _wrapper_path.chmod(0o755)
        return _wrapper_path.exists()

    return CheckResult(
        name="Clarity command",
        status=Status.WARN,
        message=f"'clarity' wrapper not found at {wrapper_path}",
        fix_hint=fix_hint,
        fix_fn=_create_wrapper,
    )


# ---------------------------------------------------------------------------
# Check: LLM provider
# ---------------------------------------------------------------------------

def _make_configure_provider_fn(agent_dir: Path) -> Callable[[], bool]:
    """Return a fix function that interactively configures an LLM provider."""
    from clarity_agent.llm.config import _PROVIDERS

    def _configure() -> bool:
        choices = list(_PROVIDERS.items())

        print("\n    Available providers:")
        for i, (_name, info) in enumerate(choices, 1):
            print(f"      {i}. {info['display_name']}")
        print(f"      {len(choices) + 1}. Cancel")

        selection = _prompt(f"\n    Select provider [1-{len(choices) + 1}]: ").strip()
        try:
            idx = int(selection) - 1
        except ValueError:
            print("    Invalid selection.")
            return False
        if idx < 0 or idx >= len(choices):
            print("    Cancelled.")
            return False

        name, info = choices[idx]
        env_path = agent_dir / ".env"

        # Find the api_key auth mode for CLI configuration.
        api_key_mode = None
        for mode in info["auth_modes"]:
            if mode["name"] == "api_key":
                api_key_mode = mode
                break

        if api_key_mode is None:
            print(f"    {name} doesn't support API key configuration via CLI.")
            print("    Use the web UI preferences panel instead.")
            return False

        env_var = api_key_mode["env_var"]
        api_key = _prompt(f"    Enter {env_var}: ").strip()
        if not api_key:
            print("    No key provided.")
            return False
        _update_env_var(env_path, env_var, api_key)

        if info.get("endpoint_env_var"):
            endpoint = _prompt(f"    Enter {info['endpoint_env_var']}: ").strip()
            if not endpoint:
                print("    No endpoint provided.")
                return False
            _update_env_var(env_path, info["endpoint_env_var"], endpoint)

        print(f"    Wrote {name} credentials to {env_path}")
        return True

    return _configure


def _detect_provider() -> tuple[str, str] | None:
    """Detect the best available (provider, auth_mode) for the doctor.

    Like :func:`_auto_detect_provider` from ``llm.config``, but also
    recognises the Claude SDK when ``claude_agent_sdk`` is installed —
    even without the ``CLAUDECODE`` env var that the runtime sets.
    This lets the doctor validate a Claude SDK installation from a
    normal terminal.
    """
    from clarity_agent.llm.config import _auto_detect_provider, _has_package

    result = _auto_detect_provider()
    if result is not None:
        return result

    # _auto_detect_provider requires CLAUDECODE to be set, but that
    # only exists inside a running Claude Code session.  If the SDK
    # package is importable, the user likely has it configured via
    # `claude login` and simply isn't running inside Claude Code.
    if _has_package("claude_agent_sdk"):
        return ("anthropic", "claude_sdk")

    return None


def check_llm_provider(agent_dir: Path) -> CheckResult:
    """Verify that a usable provider can be detected."""
    detected = _detect_provider()
    if detected is None:
        return CheckResult(
            name="LLM provider",
            status=Status.FAIL,
            message="No LLM provider could be auto-detected",
            fix_hint=(
                "Configure one of:\n"
                "  ANTHROPIC_API_KEY  (in .env or environment)\n"
                "  OPENAI_API_KEY    (in .env or environment)\n"
                "  AZURE_AI_API_KEY + AZURE_AI_ENDPOINT\n"
                "  Install the Claude Agent SDK (pip install claude-agent-sdk)"
            ),
            fix_fn=_make_configure_provider_fn(agent_dir),
        )
    provider, auth_mode = detected
    return CheckResult(
        name="LLM provider",
        status=Status.PASS,
        message=f"Auto-detected provider: {provider} (auth: {auth_mode})",
    )


# ---------------------------------------------------------------------------
# Check: backend health
# ---------------------------------------------------------------------------

def _classify_error(error: Exception, provider: str) -> str:
    """Return a targeted fix hint for common backend errors."""
    msg = str(error).lower()
    if "auth" in msg or "api key" in msg or "401" in msg or "403" in msg:
        return f"Your API key for {provider} may be invalid or expired."
    if "connection" in msg or "timeout" in msg or "resolve" in msg:
        return f"Network error connecting to {provider}. Check your internet connection."
    if "rate" in msg or "429" in msg:
        return f"Rate-limited by {provider}. Try again in a few minutes."
    if "billing" in msg or "payment" in msg or "quota" in msg:
        return f"Billing issue with {provider}. Check your account status."
    return f"{type(error).__name__}: {str(error)[:200]}"


def _is_auth_error(error: Exception) -> bool:
    """Return True if *error* looks like an authentication failure."""
    msg = str(error).lower()
    return any(s in msg for s in ("auth", "api key", "401", "403"))


def _make_update_key_fn(
    agent_dir: Path, provider: str,
) -> Callable[[], bool]:
    """Return a fix function that prompts for a new API key."""
    from clarity_agent.llm.config import get_auth_mode_info

    mode_info = get_auth_mode_info(provider, "api_key")
    env_var: str | None = mode_info.get("env_var") if mode_info else None
    if not env_var:
        return lambda: False

    def _update() -> bool:
        new_key = _prompt(f"    Enter new {env_var}: ").strip()
        if not new_key:
            print("    No key provided.")
            return False
        _update_env_var(agent_dir / ".env", env_var, new_key)
        print(f"    Updated {env_var} in {agent_dir / '.env'}")
        return True

    return _update


def check_backend_health(agent_dir: Path) -> CheckResult:
    """Probe the detected provider with a trivial API call."""
    detected = _detect_provider()
    if detected is None:
        return CheckResult(
            name="Backend health",
            status=Status.FAIL,
            message="Skipped: no provider detected",
        )

    provider, auth_mode = detected
    try:
        if provider == "anthropic" and auth_mode == "claude_sdk":
            return _probe_sdk(agent_dir)
        if provider == "github":
            return _probe_copilot(agent_dir)
        return _probe_api(agent_dir, provider)
    except Exception as e:
        fix_fn: Callable[[], bool] | None = None
        if _is_auth_error(e):
            fix_fn = _make_update_key_fn(agent_dir, provider)
        return CheckResult(
            name="Backend health",
            status=Status.FAIL,
            message=f"Probe failed: {type(e).__name__}: {str(e)[:200]}",
            fix_hint=_classify_error(e, provider),
            fix_fn=fix_fn,
        )


def _probe_api(agent_dir: Path, provider: str) -> CheckResult:
    """Probe an API-based provider with a trivial create_message call."""
    from clarity_agent.llm.config import _PROVIDERS, LLMConfig
    from clarity_agent.llm.factory import get_provider_tier_defaults

    info = _PROVIDERS[provider]
    # Collect API key from any auth mode's env_var.
    api_key: str | None = None
    for mode in info["auth_modes"]:
        ev = mode.get("env_var")
        if ev:
            api_key = os.environ.get(ev)
            if api_key:
                break
    endpoint = (
        os.environ.get(info["endpoint_env_var"])
        if info.get("endpoint_env_var") else None
    )
    tier_defaults = get_provider_tier_defaults(provider)
    default_model = tier_defaults.get("default", "unknown")

    # Honour CLARITY_MODEL_* env overrides — the user may have a deployment
    # name that differs from the hardcoded provider defaults.
    default_model = os.environ.get("CLARITY_MODEL_DEFAULT", default_model)

    config = LLMConfig(
        provider=provider,
        api_key=api_key,
        endpoint=endpoint,
        tiers={"default": default_model},
    )

    client = config.create_client()
    asyncio.run(client.create_message(
        messages=[{"role": "user", "content": "Say ok"}],
        model=config.tiers.get("default", "unknown"),
        max_tokens=64,
        system="Respond with exactly: ok",
    ))
    # Any non-error response means the connection works.  The model may
    # not reply with the exact word "ok" (especially reasoning models that
    # use internal thought tokens), so treat any successful round-trip as
    # a pass.
    return CheckResult(
        name="Backend health",
        status=Status.PASS,
        message=f"Provider {provider} responded successfully",
    )


def _probe_sdk(agent_dir: Path) -> CheckResult:
    """Probe the Claude SDK by spinning up a SdkChatBackend."""
    from clarity_agent.llm.impl.claude_sdk import SdkChatBackend

    backend = SdkChatBackend(
        project_dir=agent_dir,
        clarity_agent_dir=agent_dir,
    )
    try:
        reply = backend.chat(
            "Say ok",
            system_prompt="Respond with exactly: ok",
            model="fast",
        )
    finally:
        backend.disconnect()

    print(f"    Received reply from Claude SDK: {reply}")

    if reply is not None and reply.strip() == "ok":
        return CheckResult(
            name="Backend health",
            status=Status.PASS,
            message="Claude SDK responded successfully",
        )
    elif not reply:
        return CheckResult(
            name="Backend health",
            status=Status.WARN,
            message="Claude SDK returned an empty response",
        )
    else:
        return CheckResult(
            name="Backend health",
            status=Status.WARN,
            message=f"Claude SDK returned unexpected response: {reply[:200]}",
        )


def _probe_copilot(agent_dir: Path) -> CheckResult:
    """Probe the GitHub Copilot SDK by spinning up a CopilotChatBackend."""
    from clarity_agent.llm.impl.github_copilot import CopilotChatBackend, get_gh_cli_token

    token = os.environ.get("GITHUB_TOKEN") or get_gh_cli_token(raise_on_failure=True)

    backend = CopilotChatBackend(
        project_dir=agent_dir,
        clarity_agent_dir=agent_dir,
        token=token,
    )
    try:
        reply = backend.chat(
            "Say ok",
            system_prompt="Respond with exactly: ok",
            model="fast",
        )
    finally:
        backend.disconnect()

    if reply is not None and reply.strip():
        return CheckResult(
            name="Backend health",
            status=Status.PASS,
            message="GitHub Copilot responded successfully",
        )
    return CheckResult(
        name="Backend health",
        status=Status.WARN,
        message="GitHub Copilot returned an empty response",
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_all_checks(agent_dir: Path | None = None) -> list[CheckResult]:
    """Run all diagnostic checks in dependency order.

    Args:
        agent_dir: Path to the clarity-agent installation root.
            If ``None``, auto-detected via :func:`get_agent_dir`.

    Returns:
        List of all :class:`CheckResult` objects.
    """
    if agent_dir is None:
        from clarity_agent import get_agent_dir
        agent_dir = get_agent_dir()

    results: list[CheckResult] = []

    # 1. Installation type (and AGENTS.md sub-check).
    results.extend(check_installation_type(agent_dir))

    # 2. Repo freshness.
    results.append(check_repo_freshness(agent_dir))

    # 3. Python version.
    results.append(check_python_version())

    # 4. Python dependencies.
    results.extend(check_python_dependencies(agent_dir))

    # 5. NPM / web dependencies.
    results.extend(check_npm_dependencies(agent_dir))

    # 6. Clarity wrapper command.
    results.append(check_clarity_command(agent_dir))

    # 7. LLM provider detection.
    provider_result = check_llm_provider(agent_dir)
    results.append(provider_result)

    # 8. Backend health — only if a provider was detected.
    if provider_result.status == Status.PASS:
        results.append(check_backend_health(agent_dir))
    else:
        results.append(CheckResult(
            name="Backend health",
            status=Status.FAIL,
            message="Skipped: no LLM provider configured",
        ))

    return results


# ---------------------------------------------------------------------------
# CLI output & interactive repair
# ---------------------------------------------------------------------------

_ICONS = {
    Status.PASS: ("PASS", "\033[1;32m"),  # green
    Status.WARN: ("WARN", "\033[1;33m"),  # yellow
    Status.FAIL: ("FAIL", "\033[1;31m"),  # red
}
_RESET = "\033[0m"


def _use_color() -> bool:
    return "NO_COLOR" not in os.environ and sys.stdout.isatty()


def _print_result(result: CheckResult) -> None:
    label, color = _ICONS[result.status]
    if _use_color():
        print(f"  {color}{label}{_RESET}  {result.name}: {result.message}")
    else:
        print(f"  [{label}]  {result.name}: {result.message}")
    if result.fix_hint and result.status != Status.PASS:
        for line in result.fix_hint.splitlines():
            print(f"        {line}")


def _print_summary(results: list[CheckResult]) -> None:
    passes = sum(1 for r in results if r.status == Status.PASS)
    warns = sum(1 for r in results if r.status == Status.WARN)
    fails = sum(1 for r in results if r.status == Status.FAIL)

    parts = [f"{passes} passed"]
    if warns:
        parts.append(f"{warns} warning(s)")
    if fails:
        parts.append(f"{fails} failed")
    print(f"\n  Summary: {', '.join(parts)}")


def _cli_confirm(prompt_text: str) -> bool:
    """Ask user for yes/no confirmation (CLI version)."""
    try:
        from prompt_toolkit import prompt as pt_prompt
        answer = pt_prompt(f"{prompt_text} [y/N] ")
    except ImportError:
        answer = input(f"{prompt_text} [y/N] ")
    return answer.strip().lower() in ("y", "yes")


def _run_repairs(results: list[CheckResult]) -> list[CheckResult]:
    """Offer to fix each failed/warned check that has a fix_fn."""
    fixable = [
        r for r in results
        if r.status != Status.PASS and r.fix_fn is not None
    ]
    if not fixable:
        return []

    print(f"\n  {len(fixable)} issue(s) can be fixed automatically:\n")

    repaired: list[CheckResult] = []
    for result in fixable:
        label = "WARN" if result.status == Status.WARN else "FAIL"
        print(f"  [{label}] {result.name}: {result.message}")
        if result.fix_hint:
            print(f"    Fix: {result.fix_hint}")

        if _cli_confirm("    Apply this fix?"):
            print("    Applying fix...")
            try:
                assert result.fix_fn is not None
                success = result.fix_fn()
                if success:
                    print("    Done.")
                    repaired.append(result)
                else:
                    print("    Fix reported failure. Check manually.")
            except Exception as e:
                print(f"    Fix failed: {e}")
        else:
            print("    Skipped.")
        print()

    return repaired


def cli_main() -> None:
    """Full doctor CLI: run checks, display results, offer repairs."""
    from clarity_agent import get_agent_dir

    agent_dir = get_agent_dir()

    print()
    print("  Clarity Doctor")
    print(f"  Installation: {agent_dir}")
    print()

    results = run_all_checks(agent_dir)

    for result in results:
        _print_result(result)

    _print_summary(results)

    # Interactive repair phase.
    has_issues = any(r.status != Status.PASS for r in results)
    if has_issues:
        repaired = _run_repairs(results)

        if repaired:
            print("\n  Re-running checks after repairs...\n")
            results = run_all_checks(agent_dir)
            for result in results:
                _print_result(result)
            _print_summary(results)

    print()
    fails = sum(1 for r in results if r.status == Status.FAIL)
    if fails:
        raise SystemExit(1)
