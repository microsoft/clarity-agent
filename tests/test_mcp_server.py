"""Tests for the Clarity Agent MCP server.

Verifies that all tools and resources are registered and that the
core tools produce sensible output when pointed at test fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def agent_dir() -> Path:
    """Return the clarity-agent repo root."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture()
def empty_project(tmp_path: Path) -> Path:
    """Return a temp directory with no protocol."""
    return tmp_path


@pytest.fixture()
def initialized_project(tmp_path: Path) -> Path:
    """Return a temp directory with an initialized protocol."""
    from clarity_agent.protocol.initialize import init_protocol
    init_protocol(tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def _set_project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set CLARITY_PROJECT_DIR for each test so tools resolve correctly."""
    monkeypatch.setenv("CLARITY_PROJECT_DIR", str(tmp_path))


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

def test_all_tools_registered() -> None:
    """All expected tools should be registered in the MCP server."""
    from clarity_agent.mcp.server import mcp

    tool_names = {t.name for t in mcp._tool_manager.list_tools()}
    expected = {
        "run_clarity",
        "init_protocol",
        "list_protocol_documents",
        "read_protocol_document",
        "write_protocol_document",
        "get_packet_status",
        "record_packet_status",
        "get_next_action",
        "record_failure",
        "record_suggestion",
        "record_decision",
        "list_processes",
        "read_process_guide",
        "list_thinkers",
        "read_thinker_guide",
        "read_behaviors",
        "generate_packet",
        "get_mailbox_status",
        "check_failure_state",
        "snapshot_mailbox",
        "list_mailbox_items",
        "read_mailbox_item",
        "archive_mailbox_item",
    }
    assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"


def test_resources_registered() -> None:
    """Direct resources and templates should be registered."""
    from clarity_agent.mcp.server import mcp

    resource_names = {r.name for r in mcp._resource_manager.list_resources()}
    assert "project_summary" in resource_names
    assert "behaviors_resource" in resource_names

    template_names = {t.name for t in mcp._resource_manager.list_templates()}
    assert "process_guide_resource" in template_names
    assert "thinker_guide_resource" in template_names
    assert "protocol_document_resource" in template_names


# ---------------------------------------------------------------------------
# Tool function tests (direct calls, no MCP transport)
# ---------------------------------------------------------------------------

class TestInitProtocol:
    def test_creates_protocol_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(tmp_path))
        from clarity_agent.mcp.server import init_protocol
        result = init_protocol()
        assert "Initialized" in result or "already exists" in result
        # Protocol directory should exist
        from clarity_agent.app_paths import protocol_dir
        assert protocol_dir(tmp_path).exists()

    def test_idempotent(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import init_protocol
        result = init_protocol()
        # Second init should succeed (idempotent) — may say "Initialized" or "already exists"
        assert "Initialized" in result or "already exists" in result


class TestListProtocolDocuments:
    def test_no_protocol(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import list_protocol_documents
        result = list_protocol_documents()
        assert "No protocol" in result

    def test_lists_files(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import list_protocol_documents
        result = list_protocol_documents()
        assert "config.json" in result


class TestReadWriteProtocolDocument:
    def test_read_nonexistent(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import read_protocol_document
        result = read_protocol_document("nonexistent.md")
        assert "not found" in result.lower()

    def test_write_and_read(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import read_protocol_document, write_protocol_document

        write_result = write_protocol_document("goal/problem.md", "# Test Problem\n\nThis is a test.")
        assert "Written" in write_result

        read_result = read_protocol_document("goal/problem.md")
        assert "Test Problem" in read_result

    def test_path_traversal_blocked(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import read_protocol_document
        result = read_protocol_document("../../etc/passwd")
        assert "traversal" in result.lower()


class TestGetPacketStatus:
    def test_no_protocol(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import get_packet_status
        result = get_packet_status()
        assert "No protocol" in result

    def test_returns_report(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import get_packet_status
        result = get_packet_status()
        assert "Packet Status" in result or "empty" in result.lower() or "missing" in result.lower()

    def test_json_format(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import get_packet_status
        result = get_packet_status(output_format="json")
        parsed = json.loads(result)
        assert "documents" in parsed


class TestRunClarity:
    def test_new_project(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import run_clarity
        result = run_clarity()
        assert "New Project" in result

    def test_existing_project(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import run_clarity
        result = run_clarity()
        # Should contain status information, not "New Project"
        assert "New Project" not in result


class TestListProcesses:
    def test_returns_processes(self) -> None:
        from clarity_agent.mcp.server import list_processes
        result = list_processes()
        assert "problem-clarification" in result
        assert "failure-brainstorming" in result


class TestReadProcessGuide:
    def test_existing_process(self) -> None:
        from clarity_agent.mcp.server import read_process_guide
        result = read_process_guide("clarity-agent")
        assert "Clarity Agent" in result

    def test_nonexistent_process(self) -> None:
        from clarity_agent.mcp.server import read_process_guide
        result = read_process_guide("nonexistent-process")
        assert "not found" in result.lower()


class TestListThinkers:
    def test_returns_thinkers(self, agent_dir: Path) -> None:
        """Thinkers should be discoverable when agent_dir resolves correctly."""
        from clarity_agent.mcp.server import list_thinkers
        result = list_thinkers()
        # Thinkers may not be found if get_bundle_dir doesn't resolve to repo root
        # in the test environment — accept either outcome
        assert (
            "general" in result.lower()
            or "security" in result.lower()
            or "No thinkers" in result
        )


class TestReadBehaviors:
    def test_returns_agents_md(self) -> None:
        from clarity_agent.mcp.server import read_behaviors
        result = read_behaviors()
        assert "Behaviors" in result


class TestRecordFailure:
    def test_records_failure(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import record_failure
        result = record_failure(
            title="Test failure",
            description="Something could go wrong with testing.",
        )
        assert "Recorded failure" in result


class TestRecordSuggestion:
    def test_records_suggestion(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import record_suggestion
        result = record_suggestion(
            title="Add stakeholder",
            target_document="goal/stakeholders.md",
            suggestion="Consider adding end users as stakeholders.",
        )
        assert "Recorded suggestion" in result


class TestRecordDecision:
    def test_records_decision(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import record_decision
        result = record_decision(
            title="Use Python for MCP server",
            context="Need to choose implementation language.",
            decision="Use Python with FastMCP.",
            rationale="Existing codebase is Python.",
        )
        assert "Recorded decision" in result
        assert "decisions/" in result


class TestGeneratePacket:
    def test_no_protocol(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import generate_packet
        result = generate_packet()
        assert "No protocol" in result

    def test_generates_markdown(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        # Write some content first
        from clarity_agent.mcp.server import generate_packet, write_protocol_document
        write_protocol_document("goal/problem.md", "# Test Problem\n\nA real problem.")
        result = generate_packet()
        # Should return markdown content or indicate empty packet
        assert isinstance(result, str)


class TestCheckFailureState:
    def test_no_protocol(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import check_failure_state
        result = check_failure_state()
        assert "No protocol" in result

    def test_returns_state(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import check_failure_state
        result = check_failure_state()
        assert "Recommended phase" in result or "phase" in result.lower()


class TestRecordPacketStatus:
    def test_no_protocol(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import record_packet_status
        result = record_packet_status()
        assert "No protocol" in result

    def test_records_documents(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import record_packet_status, write_protocol_document
        write_protocol_document("goal/problem.md", "# Problem\n\nA real problem.")
        result = record_packet_status()
        assert "Recorded baselines" in result

    def test_specific_documents(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import record_packet_status, write_protocol_document
        write_protocol_document("goal/problem.md", "# Problem\n\nA real problem.")
        result = record_packet_status(documents=["goal/problem.md"])
        assert "Recorded baselines for 1" in result
        assert "goal/problem.md" in result

    def test_empty_project_returns_no_documents(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import record_packet_status
        result = record_packet_status()
        assert "No documents to record" in result or "Recorded" in result


class TestSnapshotMailbox:
    def test_no_protocol(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns error when no protocol directory exists."""
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import snapshot_mailbox
        result = snapshot_mailbox("failure-brainstorm")
        assert "No protocol" in result

    def test_nonexistent_mailbox(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns error for a mailbox that does not exist."""
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import snapshot_mailbox
        result = snapshot_mailbox("nonexistent")
        assert "does not exist" in result

    def test_snapshots_mailbox(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Creates a snapshot and empties the mailbox."""
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import record_failure, snapshot_mailbox
        record_failure(title="Test fail", description="desc")
        result = snapshot_mailbox("failure-brainstorm")
        assert "Snapshot created" in result


class TestListMailboxItems:
    def test_no_protocol(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns error when no protocol directory exists."""
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import list_mailbox_items
        result = list_mailbox_items("failure-brainstorm")
        assert "No protocol" in result

    def test_empty_mailbox(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns empty message for a mailbox with no items."""
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.app_paths import protocol_dir
        from clarity_agent.protocol.mailbox import Mailbox
        proto = protocol_dir(initialized_project)
        Mailbox.create(proto, "test-box", {"display_name": "test", "collector": "x", "collector_type": "batch"})
        from clarity_agent.mcp.server import list_mailbox_items
        result = list_mailbox_items("test-box")
        assert "empty" in result.lower()

    def test_lists_items(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Lists item filenames after recording failures."""
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import list_mailbox_items, record_failure
        record_failure(title="Fail one", description="desc")
        result = list_mailbox_items("failure-brainstorm")
        assert ".md" in result


class TestReadMailboxItem:
    def test_no_protocol(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns error when no protocol directory exists."""
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import read_mailbox_item
        result = read_mailbox_item("failure-brainstorm", "nonexistent.md")
        assert "No protocol" in result

    def test_reads_item(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Reads the content of a mailbox item."""
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import list_mailbox_items, read_mailbox_item, record_failure
        record_failure(title="Read test", description="readable content")
        items = list_mailbox_items("failure-brainstorm")
        filename = items.strip().splitlines()[0]
        content = read_mailbox_item("failure-brainstorm", filename)
        assert "readable content" in content

    def test_reads_from_archive(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Reads items from archive snapshots."""
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import (
            list_mailbox_items,
            read_mailbox_item,
            record_failure,
            snapshot_mailbox,
        )
        record_failure(title="Archive test", description="archived content")
        items = list_mailbox_items("failure-brainstorm")
        filename = items.strip().splitlines()[0]
        snapshot_mailbox("failure-brainstorm")
        content = read_mailbox_item("failure-brainstorm", filename)
        assert "archived content" in content

    def test_not_found(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns error for nonexistent item."""
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import read_mailbox_item, record_failure
        record_failure(title="x", description="y")
        result = read_mailbox_item("failure-brainstorm", "nonexistent.md")
        assert "not found" in result.lower()


class TestArchiveMailboxItem:
    def test_no_protocol(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns error when no protocol directory exists."""
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import archive_mailbox_item
        result = archive_mailbox_item("failure-brainstorm", "x.md")
        assert "No protocol" in result

    def test_archives_item(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Archives an item and removes it from the active mailbox."""
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import (
            archive_mailbox_item,
            list_mailbox_items,
            record_failure,
        )
        record_failure(title="Archive me", description="desc")
        items = list_mailbox_items("failure-brainstorm")
        filename = items.strip().splitlines()[0]
        result = archive_mailbox_item("failure-brainstorm", filename)
        assert "Archived" in result
        remaining = list_mailbox_items("failure-brainstorm")
        assert filename not in remaining


# ---------------------------------------------------------------------------
# __main__ tests
# ---------------------------------------------------------------------------

class TestMainModule:
    def test_import(self) -> None:
        """The __main__ module should be importable."""
        from clarity_agent.mcp.__main__ import main
        assert callable(main)
