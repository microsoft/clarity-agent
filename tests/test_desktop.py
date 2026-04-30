"""Tests for clarity_agent.setup.desktop."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from clarity_agent.setup.desktop import run_desktop_install
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
