"""Desktop app build for Clarity.

Builds a native desktop application for the current platform using
PyInstaller (Python backend sidecar) and Tauri (native shell).

  macOS   → .app bundle + .dmg
  Windows → .msi installer
  Linux   → .AppImage / .deb

Entry point: ``clarity install [--release]``

Cross-compilation is not supported — the build always targets the
platform it runs on.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from clarity_agent.setup.installer import (
    Outcome,
    StepResult,
)

_PLATFORM_LABEL = {
    "darwin": "macOS",
    "win32": "Windows",
    "linux": "Linux",
}.get(sys.platform, sys.platform)


# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

def _check_command(name: str, help_text: str) -> StepResult:
    """Check that a command is available on PATH."""
    if shutil.which(name):
        return StepResult(Outcome.OK, f"{name} found")
    return StepResult(Outcome.FAIL, f"{name} not found. {help_text}")


def _check_prerequisites() -> list[StepResult]:
    """Verify that Rust, Node.js, and uv are available."""
    results: list[StepResult] = []

    # Rust — try sourcing cargo env if not on PATH
    if not shutil.which("cargo"):
        env_file = Path.home() / ".cargo" / "env"
        if env_file.exists():
            cargo_bin = Path.home() / ".cargo" / "bin"
            os.environ["PATH"] = f"{cargo_bin}{os.pathsep}{os.environ.get('PATH', '')}"

    results.append(_check_command(
        "cargo",
        "Install Rust: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh",
    ))
    results.append(_check_command(
        "rustc",
        "Install Rust: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh",
    ))

    # Node.js
    results.append(_check_command(
        "npx", "Install Node.js from https://nodejs.org/",
    ))

    return results


def _get_target_triple() -> str:
    """Return the Rust target triple for the current platform."""
    r = subprocess.run(
        ["rustc", "--print", "host-tuple"],
        capture_output=True, text=True,
    )
    return r.stdout.strip()


# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------

# On Windows, npm/npx are .cmd scripts that need shell=True to resolve.
_SHELL = sys.platform == "win32"


def _run_build(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int = 600,
    label: str = "command",
) -> StepResult:
    """Run a build command, streaming output to the terminal.

    Unlike capture_output=True, this avoids pipe-buffer deadlocks on
    long-running builds (e.g. Cargo compiling hundreds of crates).
    """
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            timeout=timeout,
            shell=_SHELL,
        )
        if r.returncode != 0:
            return StepResult(Outcome.FAIL, f"{label} failed (exit code {r.returncode})")
    except FileNotFoundError as exc:
        return StepResult(Outcome.FAIL, f"{label}: {exc}")
    except subprocess.TimeoutExpired:
        return StepResult(Outcome.FAIL, f"{label} timed out ({timeout}s limit)")
    return StepResult(Outcome.OK, f"{label} complete")


# ---------------------------------------------------------------------------
# Build steps
# ---------------------------------------------------------------------------

def _ensure_build_deps(source_dir: Path) -> StepResult:
    """Ensure all build-time Python dependencies are installed.

    The ``dev`` extra pulls in every optional group (web, cli, brainstorm,
    docx, bundle, etc.) so PyInstaller can trace and bundle them.
    """
    try:
        import anthropic  # noqa: F401
        import fastapi  # noqa: F401
        import PyInstaller  # noqa: F401
        return StepResult(Outcome.OK, "Build dependencies already installed")
    except ImportError:
        pass
    # Prefer uv pip (works in uv-managed venvs), fall back to pip.
    pkg = f"{source_dir}[dev]"
    if shutil.which("uv"):
        cmd = ["uv", "pip", "install", "-e", pkg]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "-e", pkg, "--quiet"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return StepResult(Outcome.FAIL, f"Failed to install build deps: {r.stderr.strip()}")
    return StepResult(Outcome.OK, "Build dependencies installed")


def _build_pyinstaller_sidecar(source_dir: Path) -> StepResult:
    """Run PyInstaller to produce the sidecar binary."""
    spec_file = source_dir / "clarity-server.spec"
    if not spec_file.exists():
        return StepResult(Outcome.FAIL, f"PyInstaller spec not found: {spec_file}")

    dist_dir = source_dir / "build" / "pyinstaller"
    work_dir = source_dir / "build" / "pyinstaller-work"

    result = _run_build(
        [
            sys.executable, "-m", "PyInstaller",
            str(spec_file),
            "--noconfirm",
            "--log-level", "WARN",
            "--distpath", str(dist_dir),
            "--workpath", str(work_dir),
        ],
        cwd=source_dir,
        label="PyInstaller",
    )
    if result.outcome == Outcome.FAIL:
        return result

    if sys.platform == "win32":
        # One-directory mode: exe is inside the output directory.
        sidecar = dist_dir / "clarity-server" / "clarity-server.exe"
    else:
        sidecar = dist_dir / "clarity-server"

    if not sidecar.exists():
        return StepResult(Outcome.FAIL, f"Expected sidecar not found: {sidecar}")

    size_mb = sidecar.stat().st_size / (1024 * 1024)
    return StepResult(Outcome.OK, f"Sidecar built ({size_mb:.0f} MB): {sidecar}")


def _link_sidecar(source_dir: Path) -> StepResult:
    """Create the platform-specific symlink/copy for Tauri's externalBin."""
    target_triple = _get_target_triple()
    if not target_triple:
        return StepResult(Outcome.FAIL, "Could not determine Rust target triple")

    binaries_dir = source_dir / "src-tauri" / "binaries"
    binaries_dir.mkdir(parents=True, exist_ok=True)

    try:
        if sys.platform == "win32":
            # One-directory build: copy the exe and its _internal/ directory.
            sidecar_dir = source_dir / "build" / "pyinstaller" / "clarity-server"
            sidecar = sidecar_dir / "clarity-server.exe"
            if not sidecar.exists():
                return StepResult(Outcome.FAIL, f"Sidecar binary not found: {sidecar}")

            link_name = f"clarity-server-{target_triple}.exe"
            link_path = binaries_dir / link_name
            if link_path.exists():
                link_path.unlink()
            shutil.copy2(sidecar, link_path)

            # Copy the _internal directory (Python runtime + dependencies).
            internal_src = sidecar_dir / "_internal"
            internal_dest = binaries_dir / "_internal"
            if internal_dest.exists():
                shutil.rmtree(internal_dest)
            if internal_src.exists():
                shutil.copytree(internal_src, internal_dest)
        else:
            # One-file build: single binary, symlink for Tauri.
            sidecar = source_dir / "build" / "pyinstaller" / "clarity-server"
            if not sidecar.exists():
                return StepResult(Outcome.FAIL, f"Sidecar binary not found: {sidecar}")

            link_name = f"clarity-server-{target_triple}"
            link_path = binaries_dir / link_name
            if link_path.exists() or link_path.is_symlink():
                link_path.unlink()
            link_path.symlink_to(sidecar.resolve())

            # tauri.conf.json declares ``binaries/_internal/`` as a
            # bundle resource, which the Windows one-directory build
            # populates with the Python runtime + dependencies.  The
            # macOS/Linux one-file build is self-contained and has
            # no _internal/, but Tauri still resolves the resource
            # at bundle time and fails ("resource path doesn't
            # exist") if the dir is absent.  Create an empty
            # placeholder to satisfy it — bundles a no-op directory
            # into the .app, no runtime impact.
            internal_placeholder = binaries_dir / "_internal"
            internal_placeholder.mkdir(exist_ok=True)

        return StepResult(Outcome.OK, f"Sidecar linked: {link_name}")
    except Exception as exc:
        return StepResult(Outcome.FAIL, f"Failed to link sidecar: {exc}")


def _ensure_web_deps(source_dir: Path) -> StepResult:
    """Install web/ npm dependencies if needed."""
    web_dir = source_dir / "web"
    if (web_dir / "node_modules" / "@tauri-apps" / "cli").exists():
        return StepResult(Outcome.OK, "Web dependencies already installed")

    return _run_build(
        ["npm", "ci"],
        cwd=web_dir,
        timeout=120,
        label="npm ci",
    )


def _build_web(source_dir: Path) -> StepResult:
    """Build the React frontend into web/dist/.

    Tauri's ``frontendDist`` is set to ``"loading"`` (a static splash page),
    so the Tauri build does NOT run Vite.  The Python sidecar serves
    ``web/dist/`` at runtime, so we must build it explicitly here.
    """
    web_dir = source_dir / "web"
    return _run_build(
        ["npm", "run", "build"],
        cwd=web_dir,
        timeout=120,
        label="Web build (Vite)",
    )


def _build_tauri(source_dir: Path, *, release: bool = False) -> StepResult:
    """Run tauri build to produce the native app bundle."""
    # Set CI=true so the DMG bundler skips Finder/AppleScript interaction
    # (which opens windows and can hang in headless environments).
    os.environ.setdefault("CI", "true")

    cmd = ["npx", "--prefix", str(source_dir / "web"), "tauri", "build"]
    if not release:
        cmd.append("--debug")

    # Ensure the Tauri build targets the same architecture as the Rust
    # toolchain.  Without this, ARM64 Windows with an x86_64 Rust
    # toolchain causes a mismatch: the sidecar is x86_64 but WiX
    # defaults to the native ARM64.
    target_triple = _get_target_triple()
    if target_triple:
        cmd.extend(["--target", target_triple])

    profile = "release" if release else "debug"

    result = _run_build(
        cmd,
        cwd=source_dir,
        timeout=900,  # Rust compilation can be slow on CI
        label=f"Tauri build ({profile})",
    )
    return result


def _collect_outputs(source_dir: Path, *, release: bool = False) -> StepResult:
    """Copy final artifacts from Tauri's output to dist/."""
    profile = "release" if release else "debug"

    # When --target is passed, Tauri nests output under the target triple.
    target_triple = _get_target_triple()
    target_dir = source_dir / "src-tauri" / "target"
    if target_triple:
        candidate = target_dir / target_triple / profile / "bundle"
        if candidate.exists():
            bundle_dir = candidate
        else:
            bundle_dir = target_dir / profile / "bundle"
    else:
        bundle_dir = target_dir / profile / "bundle"

    dist_dir = source_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    collected: list[str] = []

    if sys.platform == "darwin":
        # .app bundle
        macos_dir = bundle_dir / "macos"
        if macos_dir.exists():
            for app in macos_dir.glob("*.app"):
                dest = dist_dir / app.name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(app, dest)
                size_mb = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) / (1024 * 1024)
                collected.append(f"{dest.name} ({size_mb:.0f} MB)")

        # .dmg
        dmg_dir = bundle_dir / "dmg"
        if dmg_dir.exists():
            for dmg in dmg_dir.glob("*.dmg"):
                dest = dist_dir / dmg.name
                shutil.copy2(dmg, dest)
                size_mb = dest.stat().st_size / (1024 * 1024)
                collected.append(f"{dest.name} ({size_mb:.0f} MB)")

    elif sys.platform == "win32":
        # .msi / .exe installers
        for subdir in ("msi", "nsis"):
            d = bundle_dir / subdir
            if d.exists():
                for f in d.iterdir():
                    if f.suffix in (".msi", ".exe"):
                        dest = dist_dir / f.name
                        shutil.copy2(f, dest)
                        size_mb = dest.stat().st_size / (1024 * 1024)
                        collected.append(f"{dest.name} ({size_mb:.0f} MB)")

    else:
        # Linux: .AppImage, .deb
        for subdir in ("appimage", "deb"):
            d = bundle_dir / subdir
            if d.exists():
                for f in d.iterdir():
                    if f.suffix in (".AppImage", ".deb"):
                        dest = dist_dir / f.name
                        shutil.copy2(f, dest)
                        size_mb = dest.stat().st_size / (1024 * 1024)
                        collected.append(f"{dest.name} ({size_mb:.0f} MB)")

    if not collected:
        return StepResult(Outcome.WARN, "No artifacts found to collect")

    return StepResult(Outcome.OK, "Outputs: " + ", ".join(collected))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_desktop_install(
    source_dir: Path,
    *,
    release: bool = False,
    on_step: Callable[[StepResult], None] | None = None,
) -> list[StepResult]:
    """Build the Clarity desktop app for the current platform.

    Args:
        source_dir: The clarity-agent repo root.
        release:    If True, produce an optimized release build.
        on_step:    Optional callback for real-time progress output.
    """
    results: list[StepResult] = []

    def _record(result: StepResult) -> None:
        results.append(result)
        if on_step:
            on_step(result)

    def _record_all(batch: list[StepResult]) -> None:
        for r in batch:
            _record(r)

    # Prerequisites
    prereqs = _check_prerequisites()
    _record_all(prereqs)
    if any(r.outcome == Outcome.FAIL for r in prereqs):
        return results

    # Ensure all Python build dependencies (PyInstaller, runtime libs) are
    # installed before any build step that needs them.
    _record(_ensure_build_deps(source_dir))
    if results[-1].outcome == Outcome.FAIL:
        return results

    # Web dependencies + build (must come before PyInstaller, which
    # bundles web/dist/ into the sidecar binary).
    _record(_ensure_web_deps(source_dir))
    if results[-1].outcome == Outcome.FAIL:
        return results

    _record(_build_web(source_dir))
    if results[-1].outcome == Outcome.FAIL:
        return results

    # PyInstaller sidecar (bundles web/dist/ built above)
    _record(_build_pyinstaller_sidecar(source_dir))
    if results[-1].outcome == Outcome.FAIL:
        return results

    # Link sidecar for Tauri
    _record(_link_sidecar(source_dir))
    if results[-1].outcome == Outcome.FAIL:
        return results

    # Tauri build
    _record(_build_tauri(source_dir, release=release))
    if results[-1].outcome == Outcome.FAIL:
        return results

    # Collect outputs
    _record(_collect_outputs(source_dir, release=release))

    return results


# ---------------------------------------------------------------------------
# CLI entry point (called by ``clarity install``)
# ---------------------------------------------------------------------------

def _cli_main(argv: Sequence[str] | None = None, source_dir: Path | None = None) -> None:
    """Parse args and build the desktop app."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Build Clarity as a desktop application",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Produce an optimized release build",
    )
    args = parser.parse_args(argv)

    if source_dir is None:
        source_dir = Path(__file__).resolve().parents[3]

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

    info(f"Building Clarity for {_PLATFORM_LABEL}")

    results = run_desktop_install(source_dir, release=args.release, on_step=emit)

    if any(r.outcome == Outcome.FAIL for r in results):
        print()
        info("Build failed. See errors above.")
        raise SystemExit(1)

    print()
    info("Build complete!")
    print()

    dist_dir = source_dir / "dist"
    print(f"  Outputs in: {dist_dir}/")
    if dist_dir.exists():
        for f in sorted(dist_dir.iterdir()):
            if not f.name.startswith("."):
                size_mb = sum(
                    p.stat().st_size for p in (f.rglob("*") if f.is_dir() else [f]) if p.is_file()
                ) / (1024 * 1024)
                print(f"    {f.name}  ({size_mb:.0f} MB)")
    if sys.platform == "darwin":
        app = dist_dir / "Clarity.app"
        if app.exists():
            print(f'\n  To run: open "{app}"')
    print()
