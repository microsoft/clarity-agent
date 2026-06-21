"""Desktop app build for Clarity.

Builds a native desktop application for the current platform using
PyInstaller (Python backend sidecar) and Tauri (native shell).

  macOS   → .app bundle + .dmg
  Windows → .exe (NSIS) installer (per-user)
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
    """Return the Rust target triple to build for.

    Honours the ``CLARITY_TARGET_TRIPLE`` env var (used by CI to force a
    specific arch — e.g. the macOS matrix passes ``aarch64-apple-darwin``
    on the arm64 leg and ``x86_64-apple-darwin`` on the Intel leg so each
    leg produces a native bundle). Falls back to the rustc host triple for
    local builds.
    """
    override = os.environ.get("CLARITY_TARGET_TRIPLE", "").strip()
    if override:
        return override
    r = subprocess.run(
        ["rustc", "--print", "host-tuple"],
        capture_output=True, text=True, encoding="utf8",
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
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf8")
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
    # Capture whether we are running in CI *before* setdefault mutates the
    # environment.  setdefault is used solely so the DMG bundler skips
    # Finder/AppleScript interaction in headless builds; the separate CI
    # check below uses the *original* env value so local builds still get
    # all bundle types.
    # Use an explicit check so that CI=false / CI=0 is treated as non-CI.
    _in_ci = os.environ.get("CI", "").lower() in ("1", "true", "yes")

    # Set CI=true so the DMG bundler skips Finder/AppleScript interaction
    # (which opens windows and can hang in headless environments).
    os.environ.setdefault("CI", "true")

    cmd = ["npx", "--prefix", str(source_dir / "web"), "tauri", "build"]
    if not release:
        cmd.append("--debug")

    # In non-release CI builds on macOS, skip the DMG bundle. hdiutil DMG
    # creation is slower and occasionally flaky in headless runners, and
    # the .app alone is sufficient for build verification on PR/dev CI.
    # Release CI builds (the Official pipeline, which passes --release) DO
    # need the .dmg for ESRP signing and end-user distribution, so we honour
    # the full target list from tauri.conf.json (currently ["dmg", "app"]).
    if _in_ci and sys.platform == "darwin" and not release:
        cmd.extend(["--bundles", "app"])

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
        d = bundle_dir / "nsis"
        if d.exists():
            for f in d.iterdir():
                if f.suffix == ".exe":
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
# Persistence + install
# ---------------------------------------------------------------------------

def _persistence_target() -> Path:
    """Where built bundles get moved before installation.

    The build runs from a tmpdir when invoked via ``install.sh`` —
    the ``dist/`` directory ends up inside ``$WORK`` and gets nuked
    on script exit, so the user has nothing to install from.  Move
    the artifacts to the platform's stable user data location
    instead, alongside the rest of Clarity's persistent state.
    """
    from clarity_agent.app_paths import clarity_data_dir
    return clarity_data_dir() / "builds" / "dist"


def _persist_dist(source_dir: Path) -> StepResult:
    """Move the built bundle out of the (potentially-tmp) source dir."""
    src = source_dir / "dist"
    if not src.exists() or not any(src.iterdir()):
        return StepResult(Outcome.WARN, "No dist/ to persist (build produced no artifacts)")
    dst = _persistence_target()
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return StepResult(Outcome.OK, f"Bundle persisted to {dst}")


def _open_installer(persisted_dist: Path) -> StepResult:
    """Hand off to the platform's standard install flow.

    macOS: ``open Clarity.dmg`` (Finder shows the drag-to-Applications
    window).  Windows: ``start Clarity.exe`` (NSIS installer — per-user,
    no UAC).  Linux: print the install commands — there's no
    universal Linux installer GUI, and silently auto-installing would
    need ``sudo``.

    Falls back to printing the path when the platform's open command
    is missing (e.g. headless CI).
    """
    if sys.platform == "darwin":
        dmg = next(iter(persisted_dist.glob("*.dmg")), None)
        if dmg is None:
            return StepResult(
                Outcome.WARN,
                f"No .dmg found in {persisted_dist} — open the .app there manually",
            )
        try:
            subprocess.run(["open", str(dmg)], check=True, timeout=30)
            return StepResult(
                Outcome.OK,
                f"Opened {dmg.name} — drag Clarity into Applications",
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return StepResult(
                Outcome.WARN,
                f"Could not launch 'open' — install manually from {dmg}",
            )

    if sys.platform == "win32":
        exe = next(iter(persisted_dist.glob("*.exe")), None)
        if exe is None:
            return StepResult(
                Outcome.WARN,
                f"No .exe found in {persisted_dist}",
            )
        try:
            subprocess.run(["cmd", "/c", "start", "", str(exe)], check=True, timeout=30)
            return StepResult(
                Outcome.OK, f"Launched {exe.name} installer wizard",
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return StepResult(
                Outcome.WARN,
                f"Could not launch installer — run {exe} manually",
            )

    # Linux: print instructions for whatever's in the dist.
    deb = next(iter(persisted_dist.glob("*.deb")), None)
    appimage = next(iter(persisted_dist.glob("*.AppImage")), None)
    instructions: list[str] = []
    if deb is not None:
        instructions.append(f"sudo dpkg -i {deb}")
    if appimage is not None:
        instructions.append(f"chmod +x {appimage}  # then run it directly")
    if not instructions:
        return StepResult(
            Outcome.WARN,
            f"No .deb or .AppImage in {persisted_dist}",
        )
    return StepResult(
        Outcome.OK,
        "Install with: " + "  OR  ".join(instructions),
    )


def _auto_install(persisted_dist: Path) -> StepResult:
    """Install directly into the platform's standard location.

    macOS: copy ``.app`` to ``/Applications`` (falls back to
    ``~/Applications`` if no write permission), and strip the
    ``com.apple.quarantine`` attr so the app launches without the
    "downloaded from internet" Gatekeeper prompt.

    Windows: run NSIS ``<file>.exe /S`` for a per-user silent install
    (no UAC; lands under ``%LOCALAPPDATA%\\Programs\\Clarity``).

    Linux: ``sudo dpkg -i <file>.deb`` (errors out if no sudo /
    user is not in sudoers — that's the operator's problem to
    resolve).  AppImage gets ``chmod +x`` and is left in place.
    """
    if sys.platform == "darwin":
        app = next(iter(persisted_dist.glob("*.app")), None)
        if app is None:
            return StepResult(Outcome.FAIL, f"No .app found in {persisted_dist}")
        # Try /Applications first, fall back to ~/Applications on
        # permission denial.  Prefer the global install when possible
        # — that's what users expect from a "real" installation.
        for target in (Path("/Applications"), Path.home() / "Applications"):
            try:
                target.mkdir(parents=True, exist_ok=True)
                dst = target / app.name
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(app, dst)
                # Best-effort quarantine strip — fine if xattr is missing.
                subprocess.run(
                    ["xattr", "-dr", "com.apple.quarantine", str(dst)],
                    capture_output=True,
                )
                return StepResult(
                    Outcome.OK, f"Installed to {dst}",
                )
            except PermissionError:
                continue
        return StepResult(
            Outcome.FAIL,
            "Could not write to /Applications or ~/Applications",
        )

    if sys.platform == "win32":
        exe = next(iter(persisted_dist.glob("*.exe")), None)
        if exe is None:
            return StepResult(Outcome.FAIL, f"No .exe found in {persisted_dist}")
        # NSIS/MSI installers traditionally emit MUI strings in the
        # system ANSI code page (cp1252 on US Windows, cp932 on JP,
        # …), not UTF-8.  Forcing utf-8 like the rest of the codebase
        # would mojibake or raise on the failure path.  Capture bytes
        # and decode with errors="replace" only when we actually
        # surface output to the user — robust against any code page
        # the installer happens to use.
        r = subprocess.run(
            [str(exe), "/S"],
            capture_output=True, timeout=300,
        )
        if r.returncode != 0:
            stderr = r.stderr.decode("utf8", errors="replace").strip()
            stdout = r.stdout.decode("utf8", errors="replace").strip()
            return StepResult(
                Outcome.FAIL,
                f"installer exit {r.returncode}: "
                f"{(stderr or stdout) or 'no output'}",
            )
        return StepResult(Outcome.OK, f"Installed {exe.name}")

    # Linux
    deb = next(iter(persisted_dist.glob("*.deb")), None)
    appimage = next(iter(persisted_dist.glob("*.AppImage")), None)
    if deb is not None:
        r = subprocess.run(
            ["sudo", "dpkg", "-i", str(deb)],
            capture_output=True, text=True, timeout=120, encoding="utf8",
        )
        if r.returncode != 0:
            return StepResult(
                Outcome.FAIL,
                f"dpkg exit {r.returncode}: {(r.stderr or '').strip()}",
            )
        return StepResult(Outcome.OK, f"Installed {deb.name}")
    if appimage is not None:
        appimage.chmod(appimage.stat().st_mode | 0o111)
        return StepResult(
            Outcome.OK,
            f"{appimage.name} marked executable in {persisted_dist}",
        )
    return StepResult(
        Outcome.FAIL, f"No .deb or .AppImage in {persisted_dist}",
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_desktop_install(
    source_dir: Path,
    *,
    release: bool = False,
    auto_install: bool = False,
    on_step: Callable[[StepResult], None] | None = None,
) -> list[StepResult]:
    """Build the Clarity desktop app for the current platform.

    Args:
        source_dir:   The clarity-agent repo root.
        release:      If True, produce an optimized release build.
        auto_install: If True, after building, copy the .app into
                      /Applications (or run the NSIS installer silently
                      on Windows, dpkg on Linux) directly instead of
                      opening the installer for the user to drive.
                      Convenient for developers.
        on_step:      Optional callback for real-time progress output.
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
    if results[-1].outcome == Outcome.FAIL:
        return results

    # Move dist/ out of source_dir.  Critical when source_dir is a
    # tmpdir (e.g. install.sh's $WORK), where the artifacts would
    # otherwise be deleted on script exit.
    _record(_persist_dist(source_dir))
    if results[-1].outcome == Outcome.FAIL:
        return results

    # Final step: hand off to the platform's install flow, or
    # auto-install if the operator asked for it.
    persisted = _persistence_target()
    if auto_install:
        _record(_auto_install(persisted))
    else:
        _record(_open_installer(persisted))

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
    parser.add_argument(
        "--auto-install",
        action="store_true",
        help=(
            "Install the built bundle directly into the platform's "
            "standard location (/Applications on macOS, NSIS silent "
            "install on Windows, dpkg on Linux) instead of opening "
            "the installer for the user.  Convenient for developers."
        ),
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

    results = run_desktop_install(
        source_dir,
        release=args.release,
        auto_install=args.auto_install,
        on_step=emit,
    )

    if any(r.outcome == Outcome.FAIL for r in results):
        print()
        info("Build failed. See errors above.")
        raise SystemExit(1)

    print()
    info("Build complete!")
    print()

    # source_dir/dist/ has been moved to the persisted location by
    # _persist_dist; show the operator where to find the artifacts.
    persisted = _persistence_target()
    if persisted.exists():
        print(f"  Outputs in: {persisted}/")
        for f in sorted(persisted.iterdir()):
            if not f.name.startswith("."):
                size_mb = sum(
                    p.stat().st_size for p in (f.rglob("*") if f.is_dir() else [f]) if p.is_file()
                ) / (1024 * 1024)
                print(f"    {f.name}  ({size_mb:.0f} MB)")
    print()
