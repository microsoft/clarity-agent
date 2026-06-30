"""Tests for the Clarity Agent MCP server.

Verifies that all tools and resources are registered and that the
core tools produce sensible output when pointed at test fixtures.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from mcp import types

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
    """All expected MCP tools should be registered."""
    from clarity_agent.mcp.server import mcp

    tool_names = {t.name for t in mcp._tool_manager.list_tools()}
    expected = {
        "run_clarity",
        "check_decision",
        "get_packet_status",
        "read_protocol_document",
        "write_protocol_document",
        "record_decision",
        "record_failure",
        "generate_packet",
        "record_suggestion",
    }
    assert expected == tool_names, (
        f"Missing tools: {expected - tool_names}\n"
        f"Extra tools: {tool_names - expected}"
    )


def test_no_internal_tools_exposed() -> None:
    """Internal functions should NOT be registered as MCP tools."""
    from clarity_agent.mcp.server import mcp

    tool_names = {t.name for t in mcp._tool_manager.list_tools()}
    internal = {
        "init_protocol",
        "list_protocol_documents",
        "record_packet_status",
        "get_next_action",
        "list_processes",
        "read_process_guide",
        "list_thinkers",
        "read_thinker_guide",
        "read_behaviors",
        "get_mailbox_status",
        "check_failure_state",
        "snapshot_mailbox",
        "list_mailbox_items",
        "read_mailbox_item",
        "archive_mailbox_item",
    }
    leaked = internal & tool_names
    assert not leaked, f"Internal functions leaked as MCP tools: {leaked}"


def test_resources_registered() -> None:
    """Direct resources and templates should be registered."""
    from clarity_agent.mcp.server import mcp

    resource_names = {r.name for r in mcp._resource_manager.list_resources()}
    assert "project_summary" in resource_names
    assert "decisions_resource" in resource_names
    assert "behaviors_resource" in resource_names

    template_names = {t.name for t in mcp._resource_manager.list_templates()}
    assert "process_guide_resource" in template_names
    assert "thinker_guide_resource" in template_names
    assert "protocol_document_resource" in template_names


# ---------------------------------------------------------------------------
# MCP Tool function tests
# ---------------------------------------------------------------------------

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
        assert "New Project" not in result

    def test_inlines_process_guide(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When a next action has a process, the guide content is inlined."""
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import run_clarity
        result = run_clarity()
        if "Process Guide:" in result:
            assert "##" in result


class TestCheckDecision:
    def test_no_protocol(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import check_decision
        result = check_decision("Add a new database")
        assert "No protocol" in result

    def test_returns_context(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import check_decision, write_protocol_document
        write_protocol_document("goal/requirements.md", "# Requirements\n\nMust be fast.")
        result = check_decision("Switch to a slow database")
        assert "Requirements" in result
        assert "Proposed Change" in result

    def test_with_decisions(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import check_decision, record_decision
        record_decision(
            title="Use PostgreSQL",
            context="Need a database.",
            decision="Use PostgreSQL.",
            rationale="Battle-tested.",
        )
        result = check_decision("Switch to MongoDB")
        assert "Existing Decisions" in result

    def test_empty_protocol(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import check_decision
        result = check_decision("Add a cache layer")
        assert "No decisions" in result or "Proceed" in result


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

    def test_write_auto_records_hashes(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Writing a protocol document should auto-record its content hash."""
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import write_protocol_document
        write_protocol_document("goal/problem.md", "# Real Problem\n\nA real problem statement.")
        from clarity_agent.app_paths import protocol_dir
        from clarity_agent.protocol.packet_status import load_config
        config = load_config(protocol_dir(initialized_project))
        state = config.get("documentState", {})
        assert "goal/problem.md" in state


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


# ---------------------------------------------------------------------------
# Internal function tests (not MCP tools, but still callable)
# ---------------------------------------------------------------------------

class TestInitProtocol:
    def test_creates_protocol_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(tmp_path))
        from clarity_agent.mcp.server import init_protocol
        result = init_protocol()
        assert "Initialized" in result or "already exists" in result
        from clarity_agent.app_paths import protocol_dir
        assert protocol_dir(tmp_path).exists()

    def test_idempotent(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import init_protocol
        result = init_protocol()
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
        from clarity_agent.mcp.server import list_thinkers
        result = list_thinkers()
        assert (
            "general" in result.lower()
            or "security" in result.lower()
            or "No thinkers" in result
        )


class TestReadBehaviors:
    def test_returns_project_agents_md_clarity_block(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Set up a userspace project with a freshly-rendered Clarity
        # block, then verify read_behaviors returns it.
        from clarity_agent.mcp.server import read_behaviors
        from clarity_agent.setup.layout import Mode, ProjectLayout
        from clarity_agent.setup.snippet import ensure_agents_md

        project = tmp_path / "project"
        bundle = tmp_path / "bundle"
        project.mkdir()
        bundle.mkdir()
        (bundle / "processes").mkdir()
        layout = ProjectLayout(
            mode=Mode.USERSPACE,
            project_dir=project,
            clarity_agent_dir=bundle,
            protocol_dir=project / "Clarity Protocol",
        )
        ensure_agents_md(layout)
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(project))

        result = read_behaviors()
        assert "Behaviors" in result
        assert "<!-- clarity-begin -->" in result
        assert "<!-- clarity-end -->" in result

    def test_missing_agents_md_returns_actionable_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # No AGENTS.md in the project — the reader should return a
        # message that tells the user how to fix it, not silently
        # empty.
        from clarity_agent.mcp.server import read_behaviors

        project = tmp_path / "empty"
        project.mkdir()
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(project))

        result = read_behaviors()
        assert "AGENTS.md not found" in result
        assert "Clarity" in result


class TestGeneratePacket:
    def test_no_protocol(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import generate_packet
        result = generate_packet()
        assert "No protocol" in result

    def test_generates_markdown(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import generate_packet, write_protocol_document
        write_protocol_document("goal/problem.md", "# Test Problem\n\nA real problem.")
        result = generate_packet()
        assert isinstance(result, str)
        assert "Test Problem" in result

    def test_generates_docx_embedded_resource(
        self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import (
            PACKET_DOCX_MIME_TYPE,
            generate_packet,
            write_protocol_document,
        )

        write_protocol_document("goal/problem.md", "# Test Problem\n\nA real problem.")

        result = generate_packet(output_format="docx")

        assert isinstance(result, types.EmbeddedResource)
        resource = result.resource
        assert isinstance(resource, types.BlobResourceContents)
        assert str(resource.uri) == "clarity-packet://generated/packet-complete.docx"
        assert resource.mimeType == PACKET_DOCX_MIME_TYPE
        assert base64.b64decode(resource.blob)[:2] == b"PK"

    def test_accepts_packet_view(
        self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import generate_packet, write_protocol_document

        write_protocol_document("goal/problem.md", "# Test Problem\n\nA real problem.")
        write_protocol_document("solution/solution.md", "# Test Solution\n\nA real solution.")

        result = generate_packet(view="engineer")
        assert "Test Problem" in result
        assert "Test Solution" in result

    def test_returns_unknown_view_errors(
        self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import generate_packet

        result = generate_packet(view="unknown")
        assert result.startswith("Error generating packet:")
        assert "Unknown view" in result

    def test_rejects_unsupported_output_format(
        self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import generate_packet

        result = generate_packet(output_format="html")

        assert isinstance(result, str)
        assert result.startswith("Error generating packet:")
        assert "Unsupported MCP packet output format" in result


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
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import snapshot_mailbox
        result = snapshot_mailbox("failure-brainstorm")
        assert "No protocol" in result

    def test_nonexistent_mailbox(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import snapshot_mailbox
        result = snapshot_mailbox("nonexistent")
        assert "does not exist" in result

    def test_snapshots_mailbox(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import record_failure, snapshot_mailbox
        record_failure(title="Test fail", description="desc")
        result = snapshot_mailbox("failure-brainstorm")
        assert "Snapshot created" in result


class TestListMailboxItems:
    def test_no_protocol(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import list_mailbox_items
        result = list_mailbox_items("failure-brainstorm")
        assert "No protocol" in result

    def test_empty_mailbox(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.app_paths import protocol_dir
        from clarity_agent.protocol.mailbox import Mailbox
        proto = protocol_dir(initialized_project)
        Mailbox.create(proto, "test-box", {"display_name": "test", "collector": "x", "collector_type": "batch"})
        from clarity_agent.mcp.server import list_mailbox_items
        result = list_mailbox_items("test-box")
        assert "empty" in result.lower()

    def test_lists_items(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import list_mailbox_items, record_failure
        record_failure(title="Fail one", description="desc")
        result = list_mailbox_items("failure-brainstorm")
        assert ".md" in result


class TestReadMailboxItem:
    def test_no_protocol(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import read_mailbox_item
        result = read_mailbox_item("failure-brainstorm", "nonexistent.md")
        assert "No protocol" in result

    def test_reads_item(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import list_mailbox_items, read_mailbox_item, record_failure
        record_failure(title="Read test", description="readable content")
        items = list_mailbox_items("failure-brainstorm")
        filename = items.strip().splitlines()[0]
        content = read_mailbox_item("failure-brainstorm", filename)
        assert "readable content" in content

    def test_reads_from_archive(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(initialized_project))
        from clarity_agent.mcp.server import read_mailbox_item, record_failure
        record_failure(title="x", description="y")
        result = read_mailbox_item("failure-brainstorm", "nonexistent.md")
        assert "not found" in result.lower()


class TestArchiveMailboxItem:
    def test_no_protocol(self, empty_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLARITY_PROJECT_DIR", str(empty_project))
        from clarity_agent.mcp.server import archive_mailbox_item
        result = archive_mailbox_item("failure-brainstorm", "x.md")
        assert "No protocol" in result

    def test_archives_item(self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
