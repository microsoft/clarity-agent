"""Tests for clarity_agent.setup.desktop."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from clarity_agent.setup.desktop import (
    _auto_install,
    _build_tauri,
    _open_installer,
    _persist_dist,
    _persistence_target,
    run_desktop_install,
)
from clarity_agent.setup.installer import Outcome


class TestRunDesktopInstall:
    def test_fails_without_cargo(self, tmp_path: Path) -> None:
        """Build fails early if Rust is not installed."""
        with patch("clarity_agent.setup.desktop.shutil.which", return_value=None):
            results = run_desktop_install(tmp_path)

        assert any(r.outcome == Outcome.FAIL for r in results)
        assert any("cargo" in r.message.lower() for r in results)

    def test_fails_without_pyinstaller_spec(self, tmp_path: Path) -> None:
        """Build fails if the .spec file is missing."""
        ok = subprocess.CompletedProcess([], 0, stdout="", stderr="")

        # Create web dir so web steps pass (npm ci is skipped, npm build is mocked).
        tauri_cli = tmp_path / "web" / "node_modules" / "@tauri-apps" / "cli"
        tauri_cli.mkdir(parents=True)

        with patch("clarity_agent.setup.desktop.shutil.which", return_value="/usr/bin/dummy"), \
             patch("clarity_agent.setup.desktop._get_target_triple",
                   return_value="aarch64-apple-darwin"), \
             patch("clarity_agent.setup.desktop.subprocess.run", return_value=ok):
            results = run_desktop_install(tmp_path)

        fail_msgs = [r.message for r in results if r.outcome == Outcome.FAIL]
        assert any("spec" in m.lower() for m in fail_msgs)

    def test_on_step_callback(self, tmp_path: Path) -> None:
        """on_step is called for each build step."""
        called: list = []

        with patch("clarity_agent.setup.desktop.shutil.which", return_value=None):
            run_desktop_install(tmp_path, on_step=called.append)

        assert len(called) > 0
        assert all(hasattr(r, "outcome") for r in called)

    def test_orchestrator_routes_to_open_installer_by_default(
        self, tmp_path: Path,
    ) -> None:
        """Without --auto-install, the open-installer step runs and the
        auto-install step does not.  Verifies the routing in
        ``run_desktop_install`` rather than re-testing the helpers
        themselves."""
        ok = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        sidecar_dir = tmp_path / "build" / "pyinstaller"
        sidecar_dir.mkdir(parents=True)
        (sidecar_dir / "clarity-server").write_bytes(b"\x00" * 100)
        (tmp_path / "clarity-server.spec").write_text("# spec")
        (tmp_path / "web" / "node_modules" / "@tauri-apps" / "cli").mkdir(parents=True)
        bundle_dir = tmp_path / "src-tauri" / "target" / "debug" / "bundle" / "macos"
        bundle_dir.mkdir(parents=True)
        (bundle_dir / "Clarity.app" / "Contents" / "MacOS").mkdir(parents=True)
        (bundle_dir / "Clarity.app" / "Contents" / "MacOS" / "clarity").write_bytes(b"\x00")

        with patch("clarity_agent.setup.desktop.shutil.which", return_value="/usr/bin/dummy"), \
             patch("clarity_agent.setup.desktop._get_target_triple",
                   return_value="aarch64-apple-darwin"), \
             patch("clarity_agent.setup.desktop.subprocess.run", return_value=ok), \
             patch("clarity_agent.setup.desktop.sys") as mock_sys, \
             patch("clarity_agent.setup.desktop._open_installer",
                   return_value=__import__("clarity_agent.setup.installer", fromlist=["StepResult"]).StepResult(Outcome.OK, "opened")) as mock_open, \
             patch("clarity_agent.setup.desktop._auto_install") as mock_auto:
            mock_sys.platform = "darwin"
            mock_sys.executable = sys.executable
            run_desktop_install(tmp_path, auto_install=False)

        assert mock_open.called, "default flow must call _open_installer"
        assert not mock_auto.called, "default flow must NOT call _auto_install"

    def test_orchestrator_routes_to_auto_install_when_flag_set(
        self, tmp_path: Path,
    ) -> None:
        """With --auto-install, the auto-install step runs and the
        open-installer step does not."""
        ok = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        sidecar_dir = tmp_path / "build" / "pyinstaller"
        sidecar_dir.mkdir(parents=True)
        (sidecar_dir / "clarity-server").write_bytes(b"\x00" * 100)
        (tmp_path / "clarity-server.spec").write_text("# spec")
        (tmp_path / "web" / "node_modules" / "@tauri-apps" / "cli").mkdir(parents=True)
        bundle_dir = tmp_path / "src-tauri" / "target" / "debug" / "bundle" / "macos"
        bundle_dir.mkdir(parents=True)
        (bundle_dir / "Clarity.app" / "Contents" / "MacOS").mkdir(parents=True)
        (bundle_dir / "Clarity.app" / "Contents" / "MacOS" / "clarity").write_bytes(b"\x00")

        installer_mod = __import__(
            "clarity_agent.setup.installer", fromlist=["StepResult"],
        )
        with patch("clarity_agent.setup.desktop.shutil.which", return_value="/usr/bin/dummy"), \
             patch("clarity_agent.setup.desktop._get_target_triple",
                   return_value="aarch64-apple-darwin"), \
             patch("clarity_agent.setup.desktop.subprocess.run", return_value=ok), \
             patch("clarity_agent.setup.desktop.sys") as mock_sys, \
             patch("clarity_agent.setup.desktop._open_installer") as mock_open, \
             patch("clarity_agent.setup.desktop._auto_install",
                   return_value=installer_mod.StepResult(Outcome.OK, "installed")) as mock_auto:
            mock_sys.platform = "darwin"
            mock_sys.executable = sys.executable
            run_desktop_install(tmp_path, auto_install=True)

        assert mock_auto.called, "--auto-install must call _auto_install"
        assert not mock_open.called, "--auto-install must NOT call _open_installer"

    def test_full_build_with_mocked_steps(self, tmp_path: Path) -> None:
        """Verify the full build sequence runs when all steps succeed."""
        ok = subprocess.CompletedProcess([], 0, stdout="", stderr="")

        # Create fake sidecar binary
        sidecar_dir = tmp_path / "build" / "pyinstaller"
        sidecar_dir.mkdir(parents=True)
        sidecar = sidecar_dir / "clarity-server"
        sidecar.write_bytes(b"\x00" * 100)

        # Create fake spec file
        (tmp_path / "clarity-server.spec").write_text("# spec")

        # Create fake web dir with tauri CLI
        tauri_cli = tmp_path / "web" / "node_modules" / "@tauri-apps" / "cli"
        tauri_cli.mkdir(parents=True)

        # Create fake tauri output
        bundle_dir = tmp_path / "src-tauri" / "target" / "debug" / "bundle" / "macos"
        bundle_dir.mkdir(parents=True)
        app_dir = bundle_dir / "Clarity.app" / "Contents" / "MacOS"
        app_dir.mkdir(parents=True)
        (app_dir / "clarity").write_bytes(b"\x00" * 100)

        with patch("clarity_agent.setup.desktop.shutil.which", return_value="/usr/bin/dummy"), \
             patch("clarity_agent.setup.desktop._get_target_triple",
                   return_value="aarch64-apple-darwin"), \
             patch("clarity_agent.setup.desktop.subprocess.run", return_value=ok), \
             patch("clarity_agent.setup.desktop.sys") as mock_sys:
            mock_sys.platform = "darwin"
            mock_sys.executable = sys.executable
            results = run_desktop_install(tmp_path)

        outcomes = [r.outcome for r in results]
        assert Outcome.FAIL not in outcomes
        assert any("Outputs" in r.message or "artifacts" in r.message.lower()
                   for r in results if r.outcome in (Outcome.OK, Outcome.WARN))


class TestBuildTauri:
    """``_build_tauri`` command-line composition."""

    def test_ci_macos_non_release_skips_dmg(self, tmp_path: Path) -> None:
        """In non-release CI on macOS, --bundles app is added to skip the DMG.

        hdiutil DMG creation is unreliable in headless runners; for PR/dev
        CI the .app alone is sufficient for build verification, so we verify
        the flag is injected rather than relying on DMG creation working
        end-to-end.
        """
        captured: list[list[str]] = []

        def fake_run(cmd: list[str], **kwargs):  # type: ignore[no-untyped-def]
            captured.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)

        with patch("clarity_agent.setup.desktop._run_build", side_effect=fake_run), \
             patch("clarity_agent.setup.desktop._get_target_triple", return_value=""), \
             patch("clarity_agent.setup.desktop.sys") as mock_sys, \
             patch.dict(os.environ, {"CI": "true"}):
            mock_sys.platform = "darwin"
            _build_tauri(tmp_path, release=False)

        assert captured, "expected _run_build to be called"
        cmd = captured[0]
        assert "--bundles" in cmd
        idx = cmd.index("--bundles")
        assert cmd[idx + 1] == "app"

    def test_ci_macos_release_includes_dmg(self, tmp_path: Path) -> None:
        """In release CI on macOS, --bundles is NOT injected so the DMG is
        produced for ESRP signing / end-user distribution. The Official
        pipeline relies on this to ship .dmg artifacts."""
        captured: list[list[str]] = []

        def fake_run(cmd: list[str], **kwargs):  # type: ignore[no-untyped-def]
            captured.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)

        with patch("clarity_agent.setup.desktop._run_build", side_effect=fake_run), \
             patch("clarity_agent.setup.desktop._get_target_triple", return_value=""), \
             patch("clarity_agent.setup.desktop.sys") as mock_sys, \
             patch.dict(os.environ, {"CI": "true"}):
            mock_sys.platform = "darwin"
            _build_tauri(tmp_path, release=True)

        assert captured, "expected _run_build to be called"
        cmd = captured[0]
        assert "--bundles" not in cmd

    def test_non_ci_macos_does_not_skip_dmg(self, tmp_path: Path) -> None:
        """Outside CI on macOS, --bundles is not added so Tauri creates all
        configured bundle types (including DMG for distribution)."""
        captured: list[list[str]] = []

        def fake_run(cmd: list[str], **kwargs):  # type: ignore[no-untyped-def]
            captured.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)

        env_without_ci = {k: v for k, v in os.environ.items() if k != "CI"}
        with patch("clarity_agent.setup.desktop._run_build", side_effect=fake_run), \
             patch("clarity_agent.setup.desktop._get_target_triple", return_value=""), \
             patch("clarity_agent.setup.desktop.sys") as mock_sys, \
             patch.dict(os.environ, env_without_ci, clear=True):
            mock_sys.platform = "darwin"
            _build_tauri(tmp_path, release=True)

        assert captured, "expected _run_build to be called"
        cmd = captured[0]
        assert "--bundles" not in cmd


class TestPersistDist:
    """``_persist_dist`` moves the built bundle out of source_dir.

    Critical when source_dir is a tmpdir (install.sh's ``$WORK``):
    leaving artifacts there means they're deleted on script exit.
    """

    def test_moves_dist_to_persistence_target(self, tmp_path: Path) -> None:
        # CLARITY_DATA_DIR is set to tmp_path by the autouse fixture
        # in conftest.py, so _persistence_target lands under tmp_path.
        source_dir = tmp_path / "source"
        (source_dir / "dist").mkdir(parents=True)
        (source_dir / "dist" / "Clarity.dmg").write_bytes(b"fake")

        result = _persist_dist(source_dir)

        assert result.outcome == Outcome.OK
        target = _persistence_target()
        assert target.exists()
        assert (target / "Clarity.dmg").read_bytes() == b"fake"
        # Source dist moved away (shutil.move semantics).
        assert not (source_dir / "dist").exists()

    def test_warns_on_missing_dist(self, tmp_path: Path) -> None:
        """No build artifacts → WARN, not FAIL.  Lets the orchestrator
        continue to a meaningful "no installer to launch" message
        instead of aborting cryptically."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()  # dist/ deliberately absent

        result = _persist_dist(source_dir)

        assert result.outcome == Outcome.WARN
        assert "no dist" in result.message.lower()

    def test_replaces_existing_target(self, tmp_path: Path) -> None:
        """Re-running install overwrites the previous bundle in place
        — operator gets the freshest artifacts at the same path each
        time, no per-run subdirectories to navigate."""
        source_dir = tmp_path / "source"
        (source_dir / "dist").mkdir(parents=True)
        (source_dir / "dist" / "Clarity-new.dmg").write_bytes(b"new")

        # Pre-populate the destination with stale content.
        target = _persistence_target()
        target.mkdir(parents=True, exist_ok=True)
        (target / "Clarity-old.dmg").write_bytes(b"old")

        _persist_dist(source_dir)

        assert (target / "Clarity-new.dmg").exists()
        assert not (target / "Clarity-old.dmg").exists()


class TestWindowsInstallerSelection:
    def test_open_installer_prefers_nsis_exe(self, tmp_path: Path) -> None:
        exe = tmp_path / "Clarity.exe"
        exe.write_bytes(b"fake")
        (tmp_path / "Clarity.msi").write_bytes(b"fake")

        with patch("clarity_agent.setup.desktop.sys") as mock_sys, \
             patch("clarity_agent.setup.desktop.subprocess.run") as mock_run:
            mock_sys.platform = "win32"
            mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
            result = _open_installer(tmp_path)

        assert result.outcome == Outcome.OK
        cmd = mock_run.call_args[0][0]
        assert cmd == ["cmd", "/c", "start", "", str(exe)]

    def test_auto_install_uses_nsis_silent(self, tmp_path: Path) -> None:
        exe = tmp_path / "Clarity.exe"
        exe.write_bytes(b"fake")

        with patch("clarity_agent.setup.desktop.sys") as mock_sys, \
             patch("clarity_agent.setup.desktop.subprocess.run") as mock_run:
            mock_sys.platform = "win32"
            mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
            result = _auto_install(tmp_path)

        assert result.outcome == Outcome.OK
        cmd = mock_run.call_args[0][0]
        assert cmd == [str(exe), "/S"]

    def test_auto_install_falls_back_to_msi(self, tmp_path: Path) -> None:
        msi = tmp_path / "Clarity.msi"
        msi.write_bytes(b"fake")

        with patch("clarity_agent.setup.desktop.sys") as mock_sys, \
             patch("clarity_agent.setup.desktop.subprocess.run") as mock_run:
            mock_sys.platform = "win32"
            mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
            result = _auto_install(tmp_path)

        assert result.outcome == Outcome.OK
        cmd = mock_run.call_args[0][0]
        assert cmd == ["msiexec", "/i", str(msi), "/qb"]
