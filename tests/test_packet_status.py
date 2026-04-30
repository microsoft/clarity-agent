"""Tests for the packet status system.

Covers the full lifecycle: template detection, status checking,
hash recording, next-action recommendations, and output formatting.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clarity_agent.protocol.mailbox import Mailbox
from clarity_agent.protocol.packet_status import (
    DEFAULT_DEPENDENCIES,
    TEMPLATE_MARKERS,
    WALK_ORDER,
    check_mailbox_status,
    check_packet_status,
    check_process_availability,
    compute_hash,
    format_for_agent,
    format_report,
    is_template,
    next_action,
    record_hashes,
)

# -----------------------------------------------------------------------
# is_template
# -----------------------------------------------------------------------

class TestIsTemplate:
    """Template detection identifies placeholder files correctly."""

    def test_nonexistent_file_is_template(self, tmp_path: Path) -> None:
        assert is_template(tmp_path / "nope.md") is True

    def test_empty_file_is_template(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.md"
        f.write_text("")
        assert is_template(f) is True

    def test_whitespace_only_is_template(self, tmp_path: Path) -> None:
        f = tmp_path / "blank.md"
        f.write_text("   \n\n  \n")
        assert is_template(f) is True

    def test_real_content_is_not_template(self, tmp_path: Path) -> None:
        f = tmp_path / "real.md"
        f.write_text("# Problem\n\nWe need faster coffee.\n")
        assert is_template(f) is False

    @pytest.mark.parametrize("marker", TEMPLATE_MARKERS)
    def test_each_marker_detected(self, tmp_path: Path, marker: str) -> None:
        f = tmp_path / "marked.md"
        f.write_text(f"# Heading\n\n{marker}\n")
        assert is_template(f) is True


# -----------------------------------------------------------------------
# compute_hash
# -----------------------------------------------------------------------

class TestComputeHash:

    def test_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text("hello world\n")
        assert compute_hash(f) == compute_hash(f)

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("content A\n")
        b.write_text("content B\n")
        assert compute_hash(a) != compute_hash(b)

    def test_returns_hex_string(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text("test\n")
        h = compute_hash(f)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest


# -----------------------------------------------------------------------
# check_packet_status — full lifecycle
# -----------------------------------------------------------------------

class TestCheckPacketStatus:
    """Packet status detection through the full lifecycle."""

    def test_fresh_init_all_empty(self, tmp_path: Path) -> None:
        """After init_protocol (no real content), all docs are 'empty'."""
        from clarity_agent.protocol.initialize import init_protocol

        (tmp_path / ".git").mkdir()
        init_protocol(tmp_path)
        pd = tmp_path / ".clarity-protocol"

        report = check_packet_status(pd)
        for doc in DEFAULT_DEPENDENCIES:
            assert report["documents"][doc]["status"] == "empty"

    def test_real_content_becomes_untracked(self, protocol_dir: Path) -> None:
        """Documents with real content but no recorded baseline are 'untracked'."""
        # protocol_dir fixture writes real content but doesn't record hashes
        report = check_packet_status(protocol_dir)
        for doc in DEFAULT_DEPENDENCIES:
            assert report["documents"][doc]["status"] == "untracked"

    def test_after_record_all_current(self, protocol_dir: Path) -> None:
        """Recording hashes makes all documents 'current'."""
        record_hashes(protocol_dir)
        report = check_packet_status(protocol_dir)
        for doc in DEFAULT_DEPENDENCIES:
            assert report["documents"][doc]["status"] == "current"

    def test_modifying_dependency_causes_stale_status(self, protocol_dir: Path) -> None:
        """When an upstream doc changes, downstream docs become 'stale'."""
        record_hashes(protocol_dir)

        # Modify problem.md — this is upstream of stakeholders, requirements, solution
        (protocol_dir / "goal/problem.md").write_text(
            "# Problem\n\nActually, we need faster tea.\n"
        )

        report = check_packet_status(protocol_dir)

        # problem.md itself should still be current (it has no deps)
        assert report["documents"]["goal/problem.md"]["status"] == "current"

        # Direct dependents of problem.md should be stale
        assert report["documents"]["goal/stakeholders.md"]["status"] == "stale"
        assert report["documents"]["goal/requirements.md"]["status"] == "stale"
        assert report["documents"]["solution/solution.md"]["status"] == "stale"

    def test_stale_because_identifies_changed_dep(self, protocol_dir: Path) -> None:
        """stale_because lists the specific dependency that changed."""
        record_hashes(protocol_dir)

        (protocol_dir / "goal/problem.md").write_text(
            "# Problem\n\nChanged.\n"
        )

        report = check_packet_status(protocol_dir)
        stakeholders = report["documents"]["goal/stakeholders.md"]
        changed_docs = [d["doc"] for d in stakeholders["stale_because"]]
        assert "goal/problem.md" in changed_docs

    def test_modifying_leaf_does_not_affect_upstream(self, protocol_dir: Path) -> None:
        """Changing a leaf document shouldn't make its dependencies stale."""
        record_hashes(protocol_dir)

        # requirements.md depends on problem + stakeholders, but nothing depends on requirements
        # except solution/solution.md
        (protocol_dir / "goal/requirements.md").write_text(
            "# Requirements\n\nUpdated requirements.\n"
        )

        report = check_packet_status(protocol_dir)

        # Upstream docs should still be current
        assert report["documents"]["goal/problem.md"]["status"] == "current"
        assert report["documents"]["goal/stakeholders.md"]["status"] == "current"

        # solution.md depends on requirements, so it should be stale
        assert report["documents"]["solution/solution.md"]["status"] == "stale"

    def test_missing_file(self, protocol_dir: Path) -> None:
        """A deleted file is reported as 'missing'."""
        (protocol_dir / "goal/stakeholders.md").unlink()

        report = check_packet_status(protocol_dir)
        assert report["documents"]["goal/stakeholders.md"]["status"] == "missing"

    def test_summary_counts(self, protocol_dir: Path) -> None:
        """Summary lists aggregate correctly."""
        record_hashes(protocol_dir)

        # Make one doc stale by changing its dependency
        (protocol_dir / "goal/problem.md").write_text("# Changed\n\nNew content.\n")
        # Delete one
        (protocol_dir / "failures/failures.md").unlink()

        report = check_packet_status(protocol_dir)

        assert "goal/problem.md" in report["summary"]["current"]
        assert "failures/failures.md" in report["summary"]["missing"]
        assert len(report["summary"]["stale"]) > 0


# -----------------------------------------------------------------------
# record_hashes
# -----------------------------------------------------------------------

class TestRecordHashes:
    """Hash recording baseline behavior."""

    def test_records_all_non_template_docs(self, protocol_dir: Path) -> None:
        recorded = record_hashes(protocol_dir)
        # All docs in protocol_dir fixture have real content
        for doc in DEFAULT_DEPENDENCIES:
            assert doc in recorded

    def test_skips_template_files(self, tmp_path: Path) -> None:
        """Template files should not be recorded."""
        from clarity_agent.protocol.initialize import init_protocol

        (tmp_path / ".git").mkdir()
        init_protocol(tmp_path)
        pd = tmp_path / ".clarity-protocol"

        recorded = record_hashes(pd)
        assert len(recorded) == 0

    def test_selective_recording(self, protocol_dir: Path) -> None:
        """Can record specific documents only."""
        recorded = record_hashes(protocol_dir, ["goal/problem.md"])
        assert recorded == ["goal/problem.md"]

        # Other docs should still be untracked
        report = check_packet_status(protocol_dir)
        assert report["documents"]["goal/problem.md"]["status"] == "current"
        assert report["documents"]["goal/stakeholders.md"]["status"] == "untracked"

    def test_unknown_doc_ignored(self, protocol_dir: Path) -> None:
        """Recording an unknown document path is silently ignored."""
        recorded = record_hashes(protocol_dir, ["nonexistent/doc.md"])
        assert recorded == []


# -----------------------------------------------------------------------
# next_action — dependency graph walk
# -----------------------------------------------------------------------

class TestNextAction:
    """next_action walks the dependency graph in order and returns
    the first document needing attention."""

    def test_returns_none_when_all_current(self, protocol_dir: Path) -> None:
        record_hashes(protocol_dir)
        report = check_packet_status(protocol_dir)
        assert next_action(report) is None

    def test_returns_first_empty_in_walk_order(self, tmp_path: Path) -> None:
        """With all templates, should recommend the first doc in walk order."""
        from clarity_agent.protocol.initialize import init_protocol

        (tmp_path / ".git").mkdir()
        init_protocol(tmp_path)
        pd = tmp_path / ".clarity-protocol"

        report = check_packet_status(pd)
        action = next_action(report)

        assert action is not None
        assert action["document"] == WALK_ORDER[0]  # goal/problem.md
        assert action["status"] == "empty"

    def test_recommends_upstream_before_downstream(self, protocol_dir: Path) -> None:
        """When multiple docs need attention, upstream comes first."""
        record_hashes(protocol_dir)

        # Make problem.md (root) stale-causing: revert to template
        (protocol_dir / "goal/problem.md").write_text(
            "[To be determined. Run problem clarification to develop this.]"
        )

        report = check_packet_status(protocol_dir)
        action = next_action(report)

        assert action is not None
        assert action["document"] == "goal/problem.md"

    def test_action_includes_process(self, protocol_dir: Path) -> None:
        """The recommended action should include which process to run."""
        # Make requirements untracked by clearing hashes
        report = check_packet_status(protocol_dir)
        action = next_action(report)

        assert action is not None
        assert action["process"] is not None

    def test_skips_current_docs(self, protocol_dir: Path) -> None:
        """If early docs are current, next_action skips to the first non-current."""
        # Record only problem and stakeholders
        record_hashes(protocol_dir, ["goal/problem.md", "goal/stakeholders.md"])

        report = check_packet_status(protocol_dir)
        action = next_action(report)

        assert action is not None
        # problem and stakeholders are current; requirements is next and untracked
        assert action["document"] == "goal/requirements.md"

    def test_failures_recommends_brainstorming_when_no_pool(
        self, protocol_dir: Path,
    ) -> None:
        """When failures.md needs attention and no brainstorm pool exists,
        recommend failure-brainstorming (not the static failure-analysis)."""
        # Make all docs current, then revert failures.md to template
        record_hashes(protocol_dir)
        (protocol_dir / "failures/failures.md").write_text(
            "# Failures\n\nNo failure modes have been analyzed yet.\n"
        )

        report = check_packet_status(protocol_dir)
        action = next_action(report)

        assert action is not None
        assert action["document"] == "failures/failures.md"
        assert action["process"] == "failure-brainstorming"

    def test_failures_recommends_analysis_when_pool_has_items(
        self, protocol_dir: Path,
    ) -> None:
        """When failures.md needs attention and brainstorm pool has items,
        recommend failure-analysis."""
        record_hashes(protocol_dir)
        (protocol_dir / "failures/failures.md").write_text(
            "# Failures\n\nNo failure modes have been analyzed yet.\n"
        )

        # Add items to brainstorm mailbox
        Mailbox.create(protocol_dir, "failure-brainstorm", {
            "display_name": "failure brainstorming",
            "collector": "failure-analysis",
            "collector_type": "batch",
            "status": "ready for analysis",
        })
        Mailbox(protocol_dir, "failure-brainstorm").write(
            "raw-failure", "# A raw failure\n",
        )

        report = check_packet_status(protocol_dir)
        action = next_action(report)

        assert action is not None
        assert action["document"] == "failures/failures.md"
        assert action["process"] == "failure-analysis"


# -----------------------------------------------------------------------
# check_process_availability
# -----------------------------------------------------------------------

class TestProcessAvailability:
    """Process availability map reflects project state."""

    def test_fresh_project_only_problem_clarification_recommended(
        self, tmp_path: Path,
    ) -> None:
        """Fresh project: problem-clarification recommended, most others unavailable."""
        from clarity_agent.protocol.initialize import init_protocol

        (tmp_path / ".git").mkdir()
        init_protocol(tmp_path)
        pd = tmp_path / ".clarity-protocol"

        report = check_packet_status(pd)
        phases = check_process_availability(report)
        by_process = {p["process"]: p for p in phases}

        assert by_process["problem-clarification"]["status"] == "recommended"
        assert by_process["solution-brainstorming"]["status"] == "unavailable"
        assert by_process["failure-brainstorming"]["status"] == "unavailable"
        assert by_process["failure-analysis"]["status"] == "unavailable"
        assert by_process["failure-management"]["status"] == "unavailable"
        assert by_process["architecture-design"]["status"] == "unavailable"
        assert by_process["decision-guidance"]["status"] == "available"

    def test_with_problem_content_unlocks_processes(
        self, protocol_dir: Path,
    ) -> None:
        """When problem.md has content, solution and failure brainstorming become available."""
        report = check_packet_status(protocol_dir)
        phases = check_process_availability(report)
        by_process = {p["process"]: p for p in phases}

        # problem.md has content (untracked), so these should be available or recommended
        assert by_process["solution-brainstorming"]["status"] in ("recommended", "available")
        assert by_process["failure-brainstorming"]["status"] in ("recommended", "available")

    def test_failure_analysis_recommended_when_pool_has_items(
        self, protocol_dir: Path,
    ) -> None:
        """When brainstorm pool has items, failure-analysis is recommended."""
        Mailbox.create(protocol_dir, "failure-brainstorm", {
            "display_name": "failure brainstorming",
            "collector": "failure-analysis",
            "collector_type": "batch",
            "status": "ready for analysis",
        })
        Mailbox(protocol_dir, "failure-brainstorm").write("f1", "# Failure 1\n")

        report = check_packet_status(protocol_dir)
        phases = check_process_availability(report)
        by_process = {p["process"]: p for p in phases}

        assert by_process["failure-analysis"]["status"] == "recommended"
        assert "1 raw failure" in by_process["failure-analysis"]["reason"]

    def test_architecture_requires_solution(self, tmp_path: Path) -> None:
        """architecture-design is unavailable when solution.md has no content."""
        from clarity_agent.protocol.initialize import init_protocol

        (tmp_path / ".git").mkdir()
        init_protocol(tmp_path)
        pd = tmp_path / ".clarity-protocol"
        # Write problem.md but leave solution.md as template
        (pd / "goal/problem.md").write_text("# Problem\n\nReal problem.\n")

        report = check_packet_status(pd)
        phases = check_process_availability(report)
        by_process = {p["process"]: p for p in phases}

        assert by_process["architecture-design"]["status"] == "unavailable"
        assert "solution" in by_process["architecture-design"]["reason"].lower()

    def test_architecture_available_when_solution_has_content(
        self, protocol_dir: Path,
    ) -> None:
        """architecture-design is available or recommended when solution.md has content."""
        report = check_packet_status(protocol_dir)
        phases = check_process_availability(report)
        by_process = {p["process"]: p for p in phases}

        # protocol_dir fixture has solution.md with real content
        assert by_process["architecture-design"]["status"] in ("recommended", "available")

    def test_all_current_still_shows_availability(
        self, protocol_dir: Path,
    ) -> None:
        """Even when all docs are current, process availability is populated."""
        record_hashes(protocol_dir)

        report = check_packet_status(protocol_dir)
        phases = check_process_availability(report)

        assert len(phases) > 0
        by_process = {p["process"]: p for p in phases}
        # problem-clarification is always at least available
        assert by_process["problem-clarification"]["status"] in ("recommended", "available")
        # decision-guidance is always available
        assert by_process["decision-guidance"]["status"] == "available"

    def test_discovery_available_when_open_questions_has_content(
        self, protocol_dir: Path,
    ) -> None:
        """Discovery processes available when open-questions.md has content."""
        report = check_packet_status(protocol_dir)
        phases = check_process_availability(report)
        by_process = {p["process"]: p for p in phases}

        # protocol_dir fixture has open-questions.md with real content
        assert by_process["discovery-prototype"]["status"] == "available"
        assert by_process["discovery-research"]["status"] == "available"

    def test_discovery_unavailable_when_no_open_questions(
        self, tmp_path: Path,
    ) -> None:
        """Discovery processes unavailable when open-questions.md is empty."""
        from clarity_agent.protocol.initialize import init_protocol

        (tmp_path / ".git").mkdir()
        init_protocol(tmp_path)
        pd = tmp_path / ".clarity-protocol"

        report = check_packet_status(pd)
        phases = check_process_availability(report)
        by_process = {p["process"]: p for p in phases}

        assert by_process["discovery-prototype"]["status"] == "unavailable"
        assert by_process["discovery-research"]["status"] == "unavailable"

    def test_failure_brainstorming_unavailable_during_brainstorm(
        self, protocol_dir: Path,
    ) -> None:
        """failure-brainstorming is unavailable when async thinkers are running."""
        from datetime import datetime, timedelta, timezone

        Mailbox.create(protocol_dir, "failure-brainstorm", {
            "display_name": "failure brainstorming",
            "collector": "failure-analysis",
            "collector_type": "batch",
            "status": "collecting",
        })
        mb = Mailbox(protocol_dir, "failure-brainstorm")
        # Create a lock to simulate an in-progress brainstorm
        expires = datetime.now(timezone.utc) + timedelta(minutes=30)
        mb.create_lock("test-thinker", expires)

        report = check_packet_status(protocol_dir)
        phases = check_process_availability(report)
        by_process = {p["process"]: p for p in phases}

        assert by_process["failure-brainstorming"]["status"] == "unavailable"
        assert "in progress" in by_process["failure-brainstorming"]["reason"].lower()


# -----------------------------------------------------------------------
# format_report (human-readable)
# -----------------------------------------------------------------------

class TestFormatReport:

    def test_contains_header(self, protocol_dir: Path) -> None:
        report = check_packet_status(protocol_dir)
        output = format_report(report)
        assert "Packet Status" in output

    def test_shows_status_icons(self, protocol_dir: Path) -> None:
        record_hashes(protocol_dir)
        report = check_packet_status(protocol_dir)
        output = format_report(report)
        # All current — should have check marks
        assert "✓" in output

    def test_verbose_shows_changed_deps(self, protocol_dir: Path) -> None:
        record_hashes(protocol_dir)
        (protocol_dir / "goal/problem.md").write_text("# Changed\n")

        report = check_packet_status(protocol_dir)
        output = format_report(report, verbose=True)

        assert "content changed" in output

    def test_all_current_message(self, protocol_dir: Path) -> None:
        record_hashes(protocol_dir)
        report = check_packet_status(protocol_dir)
        output = format_report(report)
        assert "current" in output.lower()

    def test_includes_process_availability(self, protocol_dir: Path) -> None:
        report = check_packet_status(protocol_dir)
        output = format_report(report)
        assert "Process Availability" in output
        # Should show at least some processes
        assert "problem-clarification" in output

    def test_verbose_shows_process_reasons(self, protocol_dir: Path) -> None:
        report = check_packet_status(protocol_dir)
        output = format_report(report, verbose=True)
        # Verbose mode shows reasons under each process
        assert "└─" in output

    def test_process_availability_icons(self, protocol_dir: Path) -> None:
        """Process availability uses distinct icons for each status."""
        report = check_packet_status(protocol_dir)
        output = format_report(report)
        # protocol_dir has all real content, so some processes should be
        # recommended (●) or available (·)
        assert "●" in output or "·" in output

    def test_failure_brainstorm_filtered_from_async_ops(
        self, protocol_dir: Path,
    ) -> None:
        """failure-brainstorm mailbox doesn't appear in Active Async Operations."""
        Mailbox.create(protocol_dir, "failure-brainstorm", {
            "display_name": "failure brainstorming",
            "collector": "failure-analysis",
            "collector_type": "batch",
            "status": "collecting",
        })
        Mailbox(protocol_dir, "failure-brainstorm").write("f1", "# F1\n")

        report = check_packet_status(protocol_dir)
        output = format_report(report)

        # Should NOT appear in async ops section
        assert "Active Async Operations" not in output

    def test_non_brainstorm_mailbox_still_in_async_ops(
        self, protocol_dir: Path,
    ) -> None:
        """Non-failure-brainstorm mailboxes still appear in Active Async Operations."""
        Mailbox.create(protocol_dir, "review-round-1", {
            "display_name": "design review",
            "collector": "review-synthesis",
            "collector_type": "batch",
            "status": "collecting",
        })
        Mailbox(protocol_dir, "review-round-1").write("r1", "# R1\n")

        report = check_packet_status(protocol_dir)
        output = format_report(report)

        assert "Active Async Operations" in output
        assert "design review" in output


# -----------------------------------------------------------------------
# format_for_agent (agent-friendly markdown)
# -----------------------------------------------------------------------

class TestFormatForAgent:

    def test_contains_packet_status_header(self, protocol_dir: Path) -> None:
        report = check_packet_status(protocol_dir)
        output = format_for_agent(report)
        assert "## Packet Status Report" in output

    def test_includes_next_step_when_not_current(self, protocol_dir: Path) -> None:
        report = check_packet_status(protocol_dir)
        output = format_for_agent(report)
        assert "Recommended Next Step" in output

    def test_all_current_shows_quality_check(self, protocol_dir: Path) -> None:
        record_hashes(protocol_dir)
        report = check_packet_status(protocol_dir)
        output = format_for_agent(report)
        assert "All Documents Mechanically Current" in output
        assert "assess quality" in output.lower()

    def test_stale_docs_listed(self, protocol_dir: Path) -> None:
        record_hashes(protocol_dir)
        (protocol_dir / "goal/problem.md").write_text("# Changed\n")

        report = check_packet_status(protocol_dir)
        output = format_for_agent(report)

        assert "Stale Documents" in output
        assert "goal/stakeholders.md" in output

    def test_empty_docs_listed(self, tmp_path: Path) -> None:
        from clarity_agent.protocol.initialize import init_protocol

        (tmp_path / ".git").mkdir()
        init_protocol(tmp_path)
        pd = tmp_path / ".clarity-protocol"

        report = check_packet_status(pd)
        output = format_for_agent(report)

        assert "Empty Documents" in output

    def test_process_availability_shown_with_brainstorm_items(
        self, protocol_dir: Path,
    ) -> None:
        """When brainstorm mailbox has items, process availability shows failure-analysis."""
        Mailbox.create(protocol_dir, "failure-brainstorm", {
            "display_name": "failure brainstorming",
            "collector": "failure-analysis",
            "collector_type": "batch",
            "status": "ready for analysis",
        })
        mb = Mailbox(protocol_dir, "failure-brainstorm")
        mb.write("test-failure", "# Test failure\n")

        report = check_packet_status(protocol_dir)
        output = format_for_agent(report)

        assert "Process Availability" in output
        assert "failure-analysis" in output

    def test_process_availability_shows_pending_count(
        self, protocol_dir: Path,
    ) -> None:
        """When brainstorm mailbox has items, process availability shows pending count."""
        Mailbox.create(protocol_dir, "failure-brainstorm", {
            "display_name": "failure brainstorming",
            "collector": "failure-analysis",
            "collector_type": "batch",
            "status": "collecting",
        })
        mb = Mailbox(protocol_dir, "failure-brainstorm")
        mb.write("test-failure", "# Test failure\n")

        report = check_packet_status(protocol_dir)
        output = format_for_agent(report)

        assert "Process Availability" in output
        assert "pending" in output.lower()

    def test_mailbox_status_hidden_when_empty(self, protocol_dir: Path) -> None:
        """When there are no nonempty mailboxes, don't show the section."""
        report = check_packet_status(protocol_dir)
        output = format_for_agent(report)

        assert "Active Async Operations" not in output

    def test_check_packet_status_includes_mailboxes(self, protocol_dir: Path) -> None:
        """check_packet_status always populates the mailboxes field."""
        report = check_packet_status(protocol_dir)
        assert "mailboxes" in report
        assert report["mailboxes"] == []

    def test_multiple_mailboxes_shown(self, protocol_dir: Path) -> None:
        """Non-brainstorm mailboxes appear in Active Async Operations."""
        Mailbox.create(protocol_dir, "failure-brainstorm", {
            "display_name": "failure brainstorming",
            "collector": "failure-analysis",
            "collector_type": "batch",
            "status": "ready for analysis",
        })
        Mailbox.create(protocol_dir, "review-round-1", {
            "display_name": "design review",
            "collector": "review-synthesis",
            "collector_type": "batch",
            "status": "collecting",
        })
        Mailbox(protocol_dir, "failure-brainstorm").write("f1", "# F1\n")
        Mailbox(protocol_dir, "review-round-1").write("r1", "# R1\n")

        report = check_packet_status(protocol_dir)
        output = format_for_agent(report)

        # Brainstorm mailbox handled by process availability section.
        assert "Process Availability" in output
        # Other mailboxes still in Active Async Operations.
        assert "design review" in output

    def test_process_availability_includes_failure_analysis_when_pending(
        self, protocol_dir: Path,
    ) -> None:
        """When items are in the brainstorm mailbox, failure-analysis is recommended."""
        Mailbox.create(protocol_dir, "failure-brainstorm", {
            "display_name": "failure brainstorming",
            "collector": "failure-analysis",
            "collector_type": "batch",
            "status": "ready for analysis",
        })
        Mailbox(protocol_dir, "failure-brainstorm").write(
            "raw-failure", "# Failure\n",
        )

        report = check_packet_status(protocol_dir)
        output = format_for_agent(report)

        assert "Process Availability" in output
        assert "failure-analysis" in output

    def test_process_availability_always_present(
        self, protocol_dir: Path,
    ) -> None:
        """Process availability section is always shown."""
        report = check_packet_status(protocol_dir)
        output = format_for_agent(report)
        assert "Process Availability" in output
        # The old Failure Management State section no longer appears.
        assert "Failure Management State" not in output

    def test_brainstorm_mailbox_filtered_from_async_ops(
        self, protocol_dir: Path,
    ) -> None:
        """failure-brainstorm is always filtered from Active Async Operations
        (covered by Process Availability instead)."""
        Mailbox.create(protocol_dir, "failure-brainstorm", {
            "display_name": "failure brainstorming",
            "collector": "failure-analysis",
            "collector_type": "batch",
            "status": "ready for analysis",
        })
        Mailbox(protocol_dir, "failure-brainstorm").write(
            "raw-failure", "# Failure\n",
        )

        report = check_packet_status(protocol_dir)
        output = format_for_agent(report)

        # Should NOT appear in the generic Active Async Operations section.
        # The process availability section covers failure brainstorming status.
        lines = output.split("\n")
        async_section_idx = None
        for i, line in enumerate(lines):
            if "Active Async Operations" in line:
                async_section_idx = i
                break
        if async_section_idx is not None:
            async_section = "\n".join(lines[async_section_idx:])
            assert "failure brainstorming" not in async_section


# -----------------------------------------------------------------------
# check_mailbox_status
# -----------------------------------------------------------------------

class TestCheckMailboxStatus:
    """Mailbox status checking for active async operations."""

    def test_no_mailboxes_dir(self, tmp_path: Path) -> None:
        """If mailboxes/ doesn't exist, returns empty list."""
        result = check_mailbox_status(tmp_path)
        assert result == []

    def test_empty_mailboxes_excluded(self, protocol_dir: Path) -> None:
        """Mailboxes with no items (only _config.json) are excluded."""
        # suggestion box exists from init but has no items
        result = check_mailbox_status(protocol_dir)
        assert result == []

    def test_nonempty_mailbox_found(self, protocol_dir: Path) -> None:
        """A mailbox with items is returned."""
        Mailbox.create(protocol_dir, "test-op", {
            "display_name": "test operation",
            "collector": "test-collector",
            "collector_type": "batch",
        })
        Mailbox(protocol_dir, "test-op").write("item1", "# Item 1\n")

        result = check_mailbox_status(protocol_dir)
        assert len(result) == 1
        assert result[0]["name"] == "test-op"
        assert result[0]["item_count"] == 1
        assert result[0]["config"]["display_name"] == "test operation"

    def test_multiple_mailboxes(self, protocol_dir: Path) -> None:
        """Multiple nonempty mailboxes are all returned."""
        Mailbox.create(protocol_dir, "op-a", {
            "display_name": "operation A",
            "collector": "collector-a",
            "collector_type": "batch",
        })
        Mailbox.create(protocol_dir, "op-b", {
            "display_name": "operation B",
            "collector": "collector-b",
            "collector_type": "single-response",
        })
        Mailbox(protocol_dir, "op-a").write("a1", "# A1\n")
        Mailbox(protocol_dir, "op-b").write("b1", "# B1\n")
        Mailbox(protocol_dir, "op-b").write("b2", "# B2\n")

        result = check_mailbox_status(protocol_dir)
        names = {r["name"] for r in result}
        assert names == {"op-a", "op-b"}

        op_b = next(r for r in result if r["name"] == "op-b")
        assert op_b["item_count"] == 2

    def test_sorted_by_name(self, protocol_dir: Path) -> None:
        """Results are sorted by mailbox name."""
        for name in ["zz-last", "aa-first", "mm-middle"]:
            Mailbox.create(protocol_dir, name, {
                "display_name": name,
                "collector": "test",
                "collector_type": "batch",
            })
            Mailbox(protocol_dir, name).write("item", "# Item\n")

        result = check_mailbox_status(protocol_dir)
        names = [r["name"] for r in result]
        assert names == sorted(names)


