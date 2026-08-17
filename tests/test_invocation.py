"""Tests for environment-correct packet-status invocation.

Regression coverage for the desktop-build failure where process guides told
the agent to run ``python -m clarity_agent.protocol.packet_status`` — a command
with no ``python`` on the GUI PATH and no importable ``clarity_agent`` in the
frozen bundle.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from clarity_agent.protocol.invocation import (
    GUIDE_COMMAND,
    packet_status_command,
    python_path_entry,
    render_guide,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def frozen(monkeypatch: pytest.MonkeyPatch):
    """Make the process look like a PyInstaller one-file bundle."""
    def _apply(meipass: Path, executable: str = "/Apps/Clarity.app/MacOS/clarity-server"):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
        monkeypatch.setattr(sys, "executable", executable)
    return _apply


class TestPacketStatusCommand:
    def test_development_uses_the_running_interpreter(self):
        # Not bare "python": that name does not exist on a stock macOS PATH.
        assert packet_status_command() == (
            f"{shlex.quote(sys.executable)} -m clarity_agent.protocol.packet_status"
        )

    def test_frozen_uses_the_bundle_subcommand(self, frozen, tmp_path: Path):
        frozen(tmp_path)
        # No external interpreter, and no dependence on clarity_agent being
        # importable from outside the bundle.
        assert packet_status_command() == (
            "/Apps/Clarity.app/MacOS/clarity-server status"
        )

    def test_frozen_path_with_spaces_is_quoted(self, frozen, tmp_path: Path):
        frozen(tmp_path, executable="/Apps/My Clarity.app/MacOS/clarity-server")
        command = packet_status_command()
        # Must survive being pasted into a shell by the agent.
        assert shlex.split(command) == [
            "/Apps/My Clarity.app/MacOS/clarity-server", "status",
        ]


class TestPythonPathEntry:
    def test_development_points_at_src(self):
        assert python_path_entry() == str(REPO_ROOT / "src")

    def test_explicit_agent_dir_is_honoured(self, tmp_path: Path):
        assert python_path_entry(tmp_path) == str(tmp_path / "src")

    def test_frozen_points_at_the_bundle_root_not_src(self, frozen, tmp_path: Path):
        frozen(tmp_path)
        # The regression: `<_MEIPASS>/src` never exists, because the spec maps
        # src/clarity_agent -> clarity_agent at the bundle root.
        assert python_path_entry() == str(tmp_path)
        assert python_path_entry(Path("/somewhere/else")) == str(tmp_path)

    def test_frozen_entry_would_make_the_package_importable(self, frozen, tmp_path: Path):
        (tmp_path / "clarity_agent" / "protocol").mkdir(parents=True)
        frozen(tmp_path)
        entry = Path(python_path_entry())
        assert (entry / "clarity_agent" / "protocol").is_dir()


class TestRenderGuide:
    def test_development_leaves_guides_untouched(self):
        # sys.executable -m ... is what the placeholder means here; we still
        # substitute the absolute interpreter path, so only assert the shape.
        text = f"```bash\n{GUIDE_COMMAND} . --record summary.md\n```"
        assert "clarity_agent.protocol.packet_status" in render_guide(text)

    def test_frozen_rewrites_every_occurrence(self, frozen, tmp_path: Path):
        frozen(tmp_path)
        text = (
            f"{GUIDE_COMMAND} . --agent\n"
            f"and later\n"
            f"{GUIDE_COMMAND} . --record goal/problem.md\n"
        )
        rendered = render_guide(text)
        assert GUIDE_COMMAND not in rendered
        assert rendered.count("clarity-server status") == 2
        assert ". --record goal/problem.md" in rendered

    def test_unrelated_text_is_preserved(self, frozen, tmp_path: Path):
        frozen(tmp_path)
        text = "Read `.clarity-protocol/notes.md` first.\n"
        assert render_guide(text) == text


class TestGuidesUseTheCanonicalSpelling:
    """The rewrite is a literal substring replace, so the guides must match."""

    @pytest.mark.parametrize(
        "guide", sorted((REPO_ROOT / "processes").glob("*.md")), ids=lambda p: p.name
    )
    def test_no_unrewritable_packet_status_invocation(self, guide: Path):
        text = guide.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            if "packet_status" not in line or "python" not in line:
                continue
            assert GUIDE_COMMAND in line, (
                f"{guide.name}:{line_no} invokes packet_status in a spelling "
                f"render_guide() cannot rewrite: {line.strip()!r}"
            )


class TestClarityStatusSubcommand:
    """`clarity status` must behave exactly like the module entry point."""

    def _run(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        # encoding is explicit: the CLI emits UTF-8 (see
        # ``clarity_agent.console``), while ``text=True`` alone would
        # decode with the parent's locale — cp1252 on a Windows runner.
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "clarity.py"), *args],
            cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        )

    @pytest.fixture
    def project(self, tmp_path: Path) -> Path:
        proto = tmp_path / ".clarity-protocol"
        proto.mkdir()
        (proto / "config.json").write_text("{}")
        (proto / "summary.md").write_text("# Summary\n\nSomething real.\n")
        return tmp_path

    def test_matches_the_module_entry_point(self, project: Path):
        via_module = subprocess.run(
            [sys.executable, "-m", "clarity_agent.protocol.packet_status", ".", "--agent"],
            cwd=project, capture_output=True, text=True, encoding="utf-8",
        )
        via_subcommand = self._run(["status", ".", "--agent"], project)
        assert via_subcommand.stdout == via_module.stdout
        assert via_subcommand.returncode == via_module.returncode

    def test_record_persists_state(self, project: Path):
        result = self._run(["status", ".", "--record", "summary.md"], project)
        assert result.returncode == 0, result.stderr
        config = (project / ".clarity-protocol" / "config.json").read_text()
        assert "documentState" in config
        assert "summary.md" in config

    def test_does_not_fall_through_to_the_web_default(self, project: Path):
        # `status` must be in _SUBCOMMANDS, or argparse would insert "web"
        # and launch a server instead.
        result = self._run(["status", ".", "--json"], project)
        assert result.returncode in (0, 1)
        assert "documentState" in result.stdout or "summary" in result.stdout
