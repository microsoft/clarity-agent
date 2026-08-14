"""Tests for CLI output surviving a non-UTF-8 stdout.

The failure this covers is Windows-only in the wild — a redirected
stdout falls back to the locale encoding (cp1252 on a Western Windows
box), and the first ``✓`` we print raises ``UnicodeEncodeError``, so a
command that did its work exits 1 with a traceback.  It reproduces
anywhere by forcing the child's ``PYTHONIOENCODING``, which is how
these tests run on every platform.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

from clarity_agent.console import configure_stdio

REPO_ROOT = Path(__file__).resolve().parent.parent

# A glyph from every family the CLIs print: status marks, arrows, rules.
GLYPHS = "✓✗⚠→↳━—"


def _cp1252_env() -> dict[str, str]:
    """Child environment whose stdout can't encode our glyphs."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"
    return env


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proto = tmp_path / ".clarity-protocol"
    proto.mkdir()
    (proto / "config.json").write_text("{}", encoding="utf-8")
    (proto / "summary.md").write_text(
        "# Summary\n\nSomething real.\n", encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# configure_stdio
# ---------------------------------------------------------------------------

class TestConfigureStdio:
    def test_switches_a_stream_that_cannot_carry_our_glyphs(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        monkeypatch.setattr(sys, "stdout", stream)

        configure_stdio()

        assert stream.encoding.lower().replace("-", "") == "utf8"
        stream.write(GLYPHS)  # would have raised before

    def test_leaves_a_working_stream_alone(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An explicit, capable encoding is the user's choice to keep."""
        stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-16")
        monkeypatch.setattr(sys, "stdout", stream)

        configure_stdio()

        assert stream.encoding == "utf-16"

    def test_tolerates_streams_it_cannot_reconfigure(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """pytest capture objects, host-installed streams, ``None``."""
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        monkeypatch.setattr(sys, "stderr", None)

        configure_stdio()  # must not raise


# ---------------------------------------------------------------------------
# End-to-end: the CLIs themselves
# ---------------------------------------------------------------------------

class TestCliOutputUnderCp1252:
    """Each of these crashed with UnicodeEncodeError before the fix."""

    def _run(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args, cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", env=_cp1252_env(),
        )

    def test_clarity_status_record(self, project: Path) -> None:
        r = self._run(
            [sys.executable, str(REPO_ROOT / "clarity.py"),
             "status", ".", "--record", "summary.md"],
            project,
        )
        assert r.returncode == 0, r.stderr
        assert "✓" in r.stdout

    def test_packet_status_module_entry_point(self, project: Path) -> None:
        r = self._run(
            [sys.executable, "-m", "clarity_agent.protocol.packet_status", "."],
            project,
        )
        assert r.returncode == 0, r.stderr
        assert "UnicodeEncodeError" not in r.stderr

    def test_embed(self, tmp_path: Path) -> None:
        # Redirected, embed reports in plain ASCII, so this is a guard
        # against the non-ASCII that leaks in elsewhere — em dashes in
        # step messages, a project path with non-Latin-1 characters.
        repo = tmp_path / "répo—ünicode"
        repo.mkdir()
        (repo / ".git").mkdir()
        r = self._run(
            [sys.executable, str(REPO_ROOT / "clarity.py"), "embed", str(repo)],
            tmp_path,
        )
        assert r.returncode == 0, r.stderr
        assert "UnicodeEncodeError" not in r.stderr
