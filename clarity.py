#!/usr/bin/env python3
"""
Clarity CLI — helps you think clearly about what you're building.

Usage::

    clarity                           # launch multi-project web UI (default)
    clarity web                       # same, explicit
    clarity web <project_dir>         # single-project mode (developer shortcut)
    clarity cli [project_dir]         # interactive command-line session
    clarity process NAME [project_dir]# run a single process by name
    clarity packet [project_dir]      # generate a review packet
    clarity install [--mode MODE]     # install clarity as a desktop app
    clarity embed <project-dir>       # embed clarity into a git repo
    clarity update                    # update clarity-agent to latest version
    clarity doctor                    # diagnose the installation
    clarity help                      # show this help
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

# Make the clarity_agent package importable when running without pip install.
# In frozen (PyInstaller) mode, imports are handled by the bundle.
# Note: can't use app_paths.is_frozen() here — this check must run *before*
# clarity_agent is importable, since the sys.path.insert is what enables it.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from clarity_agent.app_paths import clarity_env_path, get_bundle_dir
from clarity_agent.env_path import ensure_tool_paths

# Ensure Homebrew, ~/.local/bin, etc. are visible — macOS GUI apps
# (Tauri desktop) inherit a minimal PATH that excludes them.
ensure_tool_paths()

# Root directory containing processes/, thinkers/, web/dist/, etc.
# In development this is the repo root; in a frozen build it's sys._MEIPASS.
_SCRIPT_DIR: Path = get_bundle_dir()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _add_project_args(parser: argparse.ArgumentParser) -> None:
    """Arguments shared by all commands that operate on a project."""
    parser.add_argument(
        "project_dir",
        nargs="?",
        default="./test-project",
        help="Project directory (default: ./test-project)",
    )
    parser.add_argument(
        "--clarity-agent",
        default="",
        help="Path to clarity agent installation (default: auto-detect)",
    )


def _add_llm_args(parser: argparse.ArgumentParser) -> None:
    """Add LLM configuration arguments."""
    from clarity_agent.llm import LLMConfig
    LLMConfig.add_arguments(parser)


def _resolve_dirs(args: argparse.Namespace) -> tuple[Path, Path]:
    """Resolve and validate project_dir and clarity_agent_dir from *args*."""
    project_dir = Path(args.project_dir).resolve()
    if not project_dir.exists():
        print(f"Creating project directory: {project_dir}")
        project_dir.mkdir(parents=True, exist_ok=True)

    clarity_agent_dir = Path(args.clarity_agent or _SCRIPT_DIR).resolve()
    if not clarity_agent_dir.exists():
        raise FileNotFoundError(
            f"Clarity agent directory not found: {clarity_agent_dir}\n"
            "Make sure you've cloned the clarity-agent repository."
        )

    return project_dir, clarity_agent_dir


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def _cmd_doctor(_args: argparse.Namespace) -> None:
    from clarity_agent.setup.doctor import cli_main
    cli_main()


def _cmd_install(args: argparse.Namespace) -> None:
    """Run the CLI install, the desktop build, or both.

    Each phase delegates to its own ``_cli_main`` so behavior matches
    invoking the underlying tools directly (color output, auth prompt,
    final messaging).  Phases run in order — CLI first, then desktop —
    because the desktop build's ``_ensure_build_deps`` step pip-installs
    into the venv that the CLI install creates.

    Either phase raising ``SystemExit(non-zero)`` propagates out and
    short-circuits the rest, so a failed CLI install never wastes time
    on an unbuildable desktop app.
    """
    source_dir = _SCRIPT_DIR.resolve()
    do_cli = args.mode in ("all", "cli")
    do_desktop = args.mode in ("all", "desktop")

    if do_cli:
        from clarity_agent.setup.installer import _cli_main as cli_install

        if do_desktop:
            print("\n=== Phase 1 of 2: CLI install ===\n")
        cli_argv: list[str] = [
            "--mode", "standalone",
            "--target", str(source_dir),
        ]
        if args.skip_tests:
            cli_argv.append("--skip-tests")
        cli_install(cli_argv)

    if do_desktop:
        from clarity_agent.setup.desktop import _cli_main as desktop_install

        if do_cli:
            print("\n=== Phase 2 of 2: desktop app build ===\n")
        desktop_argv: list[str] = []
        if args.release:
            desktop_argv.append("--release")
        if args.auto_install:
            desktop_argv.append("--auto-install")
        desktop_install(desktop_argv, source_dir=source_dir)


def _cmd_embed(args: argparse.Namespace) -> None:
    from clarity_agent.setup.project import _cli_main as project_embed

    project_embed([str(args.project_dir)], agent_dir=_SCRIPT_DIR.resolve())


def _cmd_update(args: argparse.Namespace) -> None:
    from clarity_agent.setup.installer import Outcome
    from clarity_agent.setup.updater import check_for_updates, run_update

    agent_dir = _SCRIPT_DIR.resolve()

    use_color = "NO_COLOR" not in os.environ and sys.stdout.isatty()
    _FMT = {
        Outcome.OK:   ("\033[1;32m  \u2713 {}\033[0m", "  OK: {}"),
        Outcome.WARN: ("\033[1;33m  \u26a0 {}\033[0m", "  WARN: {}"),
        Outcome.FAIL: ("\033[1;31m  \u2717 {}\033[0m", "  FAIL: {}"),
        Outcome.SKIP: ("\033[1;33m  - {}\033[0m",      "  SKIP: {}"),
    }

    def emit(result):
        color_fmt, plain_fmt = _FMT[result.outcome]
        print((color_fmt if use_color else plain_fmt).format(result.message))

    def info(msg: str) -> None:
        if use_color:
            print(f"\033[1;34m==> {msg}\033[0m")
        else:
            print(f"==> {msg}")

    if args.check:
        info("Checking for updates...")
        status = check_for_updates(agent_dir)

        if status.available:
            behind = f" ({status.commit_count} commit{'s' if status.commit_count != 1 else ''} behind)" if status.commit_count else ""
            print(f"  Update available{behind}")
            print(f"  Local:  {status.local_sha[:8]}")
            print(f"  Remote: {status.remote_sha[:8] if status.remote_sha else 'unknown'}")
            print("\n  Run 'clarity update' to install the update.")
        else:
            print("  Already up to date.")
        return

    info("Updating clarity-agent...")
    results = run_update(agent_dir, on_step=emit)

    if any(r.outcome == Outcome.FAIL for r in results):
        print()
        info("Update failed. See errors above.")
        raise RuntimeError("Update failed")

    if results and results[0].message == "Already up to date":
        return

    print()
    info("Update complete!")
    print("  Restart 'clarity web' to use the new version.")
    print()


def _cmd_app(args: argparse.Namespace) -> None:
    sys.exit(
        "The 'clarity app' command has been replaced by the Tauri desktop app.\n"
        "Launch Clarity.app directly, or use 'clarity web' for browser mode."
    )


def _cmd_web(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except ImportError as e:
        raise ImportError(
            f"{e}\nInstall with: pip install 'clarity-agent[web]'"
        ) from e

    from clarity_agent.settings import Settings

    clarity_agent_dir = Path(args.clarity_agent or _SCRIPT_DIR).resolve()
    theme = args.theme or Settings.current().theme
    web_dist = clarity_agent_dir / "web" / "dist"
    static_dir: Path | None = web_dist if web_dist.exists() else None

    if static_dir is None and not args.api_only:
        # ``web/dist/`` is built locally — not checked into the repo —
        # so a fresh clone won't have one until either ``clarity install``
        # runs (which builds it) or the user builds the frontend by hand.
        # Without it the server still binds its port but serves a blank
        # page — and the desktop app points its webview here too — so
        # refuse to start rather than fail silently. ``--api-only`` opts
        # into the headless server for API/development use.
        sys.exit(
            "No built web UI found at web/dist/.\n"
            "Build it with 'cd web && npm install && npm run build',\n"
            "or run 'python clarity.py install' to set everything up.\n"
            "Pass --api-only to start the server without a web UI."
        )

    if static_dir is None:
        # Reached only with --api-only: start headless, but say so
        # explicitly so a blank page later isn't a mystery.
        print("Starting in API-only mode (no web UI).\n")

    # No project_dir → launcher mode (multi-project).
    # Explicit project_dir → single-project mode (developer shortcut).
    if args.project_dir is None:
        _cmd_web_launcher(args, clarity_agent_dir, static_dir, theme, uvicorn)
    else:
        _cmd_web_single(args, clarity_agent_dir, static_dir, theme, uvicorn)


def _cmd_web_launcher(
    args: argparse.Namespace,
    clarity_agent_dir: Path,
    static_dir: Path | None,
    theme: str,
    uvicorn: Any,
) -> None:
    """Start the multi-project launcher."""
    from clarity_agent.web import create_launcher

    app = create_launcher(
        clarity_agent_dir=clarity_agent_dir,
        static_dir=static_dir,
        env_path=clarity_env_path(),
        theme=theme,
    )

    print(f"\n  Clarity Launcher: http://{args.host}:{args.port}")
    print("  Mode: multi-project (select projects in the UI)")
    print(f"  Clarity Agent: {clarity_agent_dir}")
    print(f"  Theme: {theme}\n")
    uvicorn.run(app, host=args.host, port=args.port)


def _cmd_web_single(
    args: argparse.Namespace,
    clarity_agent_dir: Path,
    static_dir: Path | None,
    theme: str,
    uvicorn: Any,
) -> None:
    """Start a single-project server directly (no launcher)."""
    from clarity_agent.llm import LLMConfig
    from clarity_agent.web import create_app

    project_dir = Path(args.project_dir).resolve()
    if not project_dir.is_dir():
        sys.exit(
            f"Project directory not found: {project_dir}\n"
            "Create a project from the launcher or use 'clarity embed <dir>'."
        )

    if not clarity_agent_dir.exists():
        raise FileNotFoundError(
            f"Clarity agent directory not found: {clarity_agent_dir}\n"
            "Make sure you've cloned the clarity-agent repository."
        )

    # Try to create LLM config. If no provider is configured, start
    # the server anyway so the setup wizard can guide configuration.
    from clarity_agent.llm.config import LLMConfigError
    try:
        llm_config: LLMConfig = LLMConfig.create(args)
        unconfigured = False
    except LLMConfigError as e:
        print(f"LLM configuration error: {e}")
        llm_config = LLMConfig(provider="none", api_key=None, tiers={"default": "unknown"})
        unconfigured = True

    app = create_app(
        project_dir=project_dir,
        clarity_agent_dir=clarity_agent_dir,
        llm_config=llm_config,
        static_dir=static_dir,
        theme=theme,
        env_path=clarity_env_path(),
        llm_session_id=getattr(args, "session_id", None),
    )

    print(f"\n  Clarity Web UI: http://{args.host}:{args.port}")
    print("  Mode: single-project")
    print(f"  Project: {project_dir}")
    print(f"  Clarity Agent: {clarity_agent_dir}")
    if unconfigured:
        print("  LLM Provider: not configured (setup wizard will guide you)")
    else:
        print(f"  LLM Provider: {llm_config.provider}")
    print(f"  Theme: {theme}\n")
    uvicorn.run(app, host=args.host, port=args.port)


def _cmd_cli(args: argparse.Namespace) -> None:
    from clarity_agent.llm import LLMConfig
    from clarity_agent.session import ClaritySession

    project_dir, clarity_agent_dir = _resolve_dirs(args)
    llm_config = LLMConfig.create(args)
    backend = llm_config.create_chat_backend(
        project_dir=project_dir, clarity_agent_dir=clarity_agent_dir,
    )
    transcript_dir = _transcript_dir(args, project_dir)

    with backend, ClaritySession(
        project_dir, clarity_agent_dir, backend, llm_config, transcript_dir,
    ) as session:
        session.interactive_mode()


def _cmd_process(args: argparse.Namespace) -> None:
    from clarity_agent.llm import LLMConfig
    from clarity_agent.session import ClaritySession

    project_dir, clarity_agent_dir = _resolve_dirs(args)
    llm_config = LLMConfig.create(args)
    backend = llm_config.create_chat_backend(
        project_dir=project_dir, clarity_agent_dir=clarity_agent_dir,
    )
    transcript_dir = _transcript_dir(args, project_dir)

    with backend, ClaritySession(
        project_dir, clarity_agent_dir, backend, llm_config, transcript_dir,
    ) as session:
        session.run_custom_process(args.name)


def _cmd_packet(args: argparse.Namespace) -> None:
    from clarity_agent.llm import LLMConfig
    from clarity_agent.session import ClaritySession

    project_dir, clarity_agent_dir = _resolve_dirs(args)
    llm_config = LLMConfig.create(args)
    backend = llm_config.create_chat_backend(
        project_dir=project_dir, clarity_agent_dir=clarity_agent_dir,
    )
    transcript_dir = _transcript_dir(args, project_dir)

    include: list[str] | None = (
        args.sections.split(",") if args.sections else None
    )

    with backend, ClaritySession(
        project_dir, clarity_agent_dir, backend, llm_config, transcript_dir,
    ) as session:
        session.run_packet(
            include=include,
            output=args.output,
            fmt=args.format,
            show_list=args.list,
        )


def _transcript_dir(args: argparse.Namespace, project_dir: Path):
    """Return a :class:`Transcript` for the project, or ``None`` if disabled.

    Function name kept (rather than the more accurate ``_make_transcript``)
    only to minimize diff churn — callers pass the result through as
    the ``transcript`` keyword argument to :class:`ClaritySession`.
    The returned object encapsulates directory creation, file
    naming, structured event persistence, and the one-time fold of
    any pre-#35 timestamp-named transcripts into chapter 1.
    """
    if getattr(args, "no_transcript", False):
        return None
    from clarity_agent.transcript import Transcript
    return Transcript(project_dir)


# ---------------------------------------------------------------------------
# Crash logging
# ---------------------------------------------------------------------------

def _write_crash_log(exc: BaseException) -> Path | None:
    """Append *exc*'s traceback to the per-user crash log.

    The Tauri sidecar runs without an attached console on Windows, so a
    bare ``print(Error: ...)`` leaves users (and us) blind to startup
    failures.  Writing the traceback to a known on-disk location turns
    silent exit codes into something we can ask users to read back.

    Best-effort: any failure during logging is swallowed so a broken
    logger never masks the real exception.
    """
    try:
        from clarity_agent.app_paths import clarity_data_dir
        log_path = clarity_data_dir() / "clarity-crash.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.now().isoformat(timespec='seconds')} ===\n")
            f.write("".join(traceback.format_exception(exc)))
        return log_path
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Subcommand registry
# ---------------------------------------------------------------------------

_SUBCOMMANDS = ("app", "web", "cli", "process", "packet", "install", "embed", "update", "doctor", "help")
_DEFAULT_COMMAND = "web"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="clarity",
        description=(
            "Clarity — a structured security review agent for software "
            "projects.\n\n"
            "Run 'clarity <command> --help' for command-specific options."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
    )

    # ---- clarity doctor ------------------------------------------------
    subparsers.add_parser(
        "doctor",
        help="Diagnose the installation and fix common problems",
    )

    # ---- clarity app (desktop webview) ---------------------------------
    app_parser = subparsers.add_parser(
        "app",
        help="Launch Clarity in a native desktop window (used by the .app bundle)",
    )
    app_parser.add_argument(
        "--clarity-agent",
        default="",
        help="Path to clarity agent installation (default: auto-detect)",
    )
    app_parser.add_argument(
        "--port", type=int, default=8420,
        help="Server port (default: 8420)",
    )
    app_parser.add_argument(
        "--host", default="127.0.0.1",
        help="Server host (default: 127.0.0.1)",
    )
    app_parser.add_argument(
        "--theme", default=None,
        help="UI color theme (env: CLARITY_THEME, default: sage)",
    )

    # ---- clarity web (default) -----------------------------------------
    web_parser = subparsers.add_parser(
        "web",
        help="Launch the web UI (default command)",
    )
    # project_dir is optional for web: omitting it starts the multi-project
    # launcher; providing it starts a single-project server directly.
    web_parser.add_argument(
        "project_dir",
        nargs="?",
        default=None,
        help="Project directory (omit for multi-project launcher mode)",
    )
    web_parser.add_argument(
        "--clarity-agent",
        default="",
        help="Path to clarity agent installation (default: auto-detect)",
    )
    web_parser.add_argument(
        "--port", type=int, default=8420,
        help="Server port (default: 8420)",
    )
    web_parser.add_argument(
        "--host", default="127.0.0.1",
        help="Server host (default: 127.0.0.1)",
    )
    web_parser.add_argument(
        "--theme", default=None,
        help="UI color theme (env: CLARITY_THEME, default: sage)",
    )
    web_parser.add_argument(
        "--session-id", default=None,
        help="SDK session ID to resume (used by launcher for session continuity)",
    )
    web_parser.add_argument(
        "--api-only", action="store_true",
        help="Start the server without a web UI (headless API mode). "
        "By default 'web' refuses to start when the UI hasn't been built.",
    )
    _add_llm_args(web_parser)

    # ---- clarity cli ---------------------------------------------------
    cli_parser = subparsers.add_parser(
        "cli",
        help="Interactive command-line session",
    )
    _add_project_args(cli_parser)
    cli_parser.add_argument(
        "--no-transcript", action="store_true",
        help="Disable saving conversation transcript",
    )
    _add_llm_args(cli_parser)

    # ---- clarity process -----------------------------------------------
    process_parser = subparsers.add_parser(
        "process",
        help="Run a single process by name",
    )
    process_parser.add_argument(
        "name",
        help="Name of the process to run",
    )
    _add_project_args(process_parser)
    process_parser.add_argument(
        "--no-transcript", action="store_true",
        help="Disable saving conversation transcript",
    )
    _add_llm_args(process_parser)

    # ---- clarity packet ------------------------------------------------
    packet_parser = subparsers.add_parser(
        "packet",
        help="Generate a review packet",
    )
    _add_project_args(packet_parser)
    packet_parser.add_argument(
        "--sections", default=None, metavar="SECTIONS",
        help="Comma-separated sections to include (default: all)",
    )
    packet_parser.add_argument(
        "--format", default="markdown", metavar="FORMAT",
        help="Output format (default: markdown)",
    )
    packet_parser.add_argument(
        "--list", action="store_true",
        help="List available packet sources and formats, then exit",
    )
    packet_parser.add_argument(
        "-o", "--output",
        help="Output file (default: packet.{ext})",
    )
    packet_parser.add_argument(
        "--no-transcript", action="store_true",
        help="Disable saving conversation transcript",
    )
    _add_llm_args(packet_parser)

    # ---- clarity install --------------------------------------------------
    install_parser = subparsers.add_parser(
        "install",
        help="Install Clarity (CLI tooling and/or the desktop app)",
        description=(
            "Install the Clarity CLI tooling, the desktop app, or both.  "
            "Default mode 'all' runs the CLI install first (creates a "
            "venv, pip-installs runtime deps, sets up .env, drops a "
            "`clarity` shim on PATH) and then builds the desktop app "
            "(PyInstaller sidecar + Tauri .app/.dmg/.msi/.deb).  Use "
            "--mode to install just one component."
        ),
    )
    install_parser.add_argument(
        "--mode",
        choices=["all", "cli", "desktop"],
        default="all",
        help=(
            "Which components to install.  'all' (default) does both; "
            "'cli' only sets up the CLI install (venv + shim + .env); "
            "'desktop' only builds the native app."
        ),
    )
    install_parser.add_argument(
        "--release",
        action="store_true",
        help=(
            "Produce an optimized release build of the desktop app "
            "(default: debug).  Ignored in --mode cli."
        ),
    )
    install_parser.add_argument(
        "--skip-tests",
        action="store_true",
        help=(
            "Skip the test run that the CLI install performs in dev "
            "mode.  Ignored in --mode desktop."
        ),
    )
    install_parser.add_argument(
        "--auto-install",
        action="store_true",
        help=(
            "After building the desktop app, install it directly into "
            "the platform's standard location (/Applications on macOS, "
            "via msiexec /qb on Windows, dpkg/AppImage copy on Linux) "
            "rather than opening the installer for the user to drive.  "
            "Convenient for developers; may need elevated privileges "
            "on Windows/Linux.  Ignored in --mode cli."
        ),
    )

    # ---- clarity embed ----------------------------------------------------
    embed_parser = subparsers.add_parser(
        "embed",
        help="Embed Clarity into an existing git repository",
    )
    embed_parser.add_argument(
        "project_dir",
        type=Path,
        help="Path to the git repository to embed Clarity into",
    )

    # ---- clarity update ---------------------------------------------------
    update_parser = subparsers.add_parser(
        "update",
        help="Update clarity-agent to the latest version",
    )
    update_parser.add_argument(
        "--check", action="store_true",
        help="Check for updates without installing them",
    )

    # ---- clarity help (alias for --help) ----------------------------------
    subparsers.add_parser(
        "help",
        help="Show this help message",
    )

    # Default to web when no subcommand is given.
    if len(sys.argv) >= 2 and sys.argv[1] == "help":
        sys.argv[1] = "--help"
    if len(sys.argv) < 2 or sys.argv[1] not in (*_SUBCOMMANDS, "-h", "--help"):
        sys.argv.insert(1, _DEFAULT_COMMAND)

    args = parser.parse_args()

    # Load settings once at startup. Everything downstream uses
    # Settings.current() to access them.
    from clarity_agent.settings import Settings
    Settings.load(env_path=clarity_env_path())

    dispatch = {
        "doctor": _cmd_doctor,
        "app": _cmd_app,
        "web": _cmd_web,
        "cli": _cmd_cli,
        "process": _cmd_process,
        "packet": _cmd_packet,
        "install": _cmd_install,
        "embed": _cmd_embed,
        "update": _cmd_update,
    }
    try:
        dispatch[args.command](args)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        crash_log = _write_crash_log(e)
        print(f"Error: {e}", file=sys.stderr)
        if crash_log is not None:
            print(f"Full traceback written to: {crash_log}", file=sys.stderr)
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
