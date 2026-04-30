"""Tests for the clarity_agent.web.launcher module."""

from __future__ import annotations

import subprocess
import time
from typing import cast
from unittest.mock import MagicMock

from clarity_agent.web.launcher import ProcessEntry, ProcessTable, _find_free_port

# ---------------------------------------------------------------------------
# ProcessTable tests
# ---------------------------------------------------------------------------

def _make_entry(name: str, alive: bool = True) -> ProcessEntry:
    """Create a ProcessEntry with a mocked subprocess."""
    proc = MagicMock(spec=subprocess.Popen)
    proc.poll.return_value = None if alive else 1
    proc.pid = 12345
    return ProcessEntry(
        project_name=name,
        pid=proc.pid,
        port=9000,
        process=proc,
    )


class TestProcessTable:
    def test_add_and_get(self) -> None:
        table = ProcessTable()
        entry = _make_entry("proj")
        table.add(entry)
        assert table.get("proj") is entry

    def test_get_returns_none_for_missing(self) -> None:
        table = ProcessTable()
        assert table.get("nope") is None

    def test_get_prunes_dead(self) -> None:
        table = ProcessTable()
        entry = _make_entry("dead", alive=False)
        table.add(entry)
        assert table.get("dead") is None

    def test_remove(self) -> None:
        table = ProcessTable()
        entry = _make_entry("proj")
        table.add(entry)
        removed = table.remove("proj")
        assert removed is entry
        assert table.get("proj") is None

    def test_remove_missing(self) -> None:
        table = ProcessTable()
        assert table.remove("ghost") is None

    def test_all_prunes_dead(self) -> None:
        table = ProcessTable()
        table.add(_make_entry("alive", alive=True))
        table.add(_make_entry("dead", alive=False))
        entries = table.all()
        assert len(entries) == 1
        assert entries[0].project_name == "alive"

    def test_kill_all(self) -> None:
        table = ProcessTable()
        e1 = _make_entry("a")
        e2 = _make_entry("b")
        table.add(e1)
        table.add(e2)
        table.kill_all()
        # process is a MagicMock at runtime (set up by _make_entry)
        # but typed as subprocess.Popen in ProcessEntry — cast back
        # so pyright sees the mock-assertion methods.
        cast(MagicMock, e1.process).terminate.assert_called_once()
        cast(MagicMock, e2.process).terminate.assert_called_once()
        assert table.all() == []

    def test_touch(self) -> None:
        table = ProcessTable()
        entry = _make_entry("proj")
        entry.last_activity = 100.0
        table.add(entry)
        table.touch("proj")
        assert entry.last_activity > 100.0

    def test_idle_entries(self) -> None:
        table = ProcessTable()
        old = _make_entry("old")
        old.last_activity = time.time() - 3600
        new = _make_entry("new")
        new.last_activity = time.time()
        table.add(old)
        table.add(new)
        idle = table.idle_entries(1800)
        assert len(idle) == 1
        assert idle[0].project_name == "old"


# ---------------------------------------------------------------------------
# Utility tests
# ---------------------------------------------------------------------------

class TestFindFreePort:
    def test_returns_int(self) -> None:
        port = _find_free_port()
        assert isinstance(port, int)
        assert port > 0

    def test_returns_different_ports(self) -> None:
        ports = {_find_free_port() for _ in range(5)}
        # At least some should differ (extremely unlikely all same)
        assert len(ports) >= 2
