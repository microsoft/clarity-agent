"""Integration tests for the decision tracking system.

These tests exercise the full decision lifecycle through the filesystem:
recording decisions, detecting triggers, formatting output, and the
interaction between decision state and the packet status checker.

Mirrors the manual test plan from PR #18.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from clarity_agent.protocol.packet_status import (
    DEFAULT_DEPENDENCIES,
    DOCUMENT_PROCESS,
    WALK_ORDER,
    check_decision_triggers,
    check_packet_status,
    format_decisions_for_agent,
    load_config,
    record_decision,
    record_hashes,
)

# -----------------------------------------------------------------------
# 1. Decisions are not in the document dependency graph
# -----------------------------------------------------------------------

class TestDecisionsNotInDependencyGraph:
    """Decisions are cross-cutting — they should not appear in the
    linear dependency graph or walk order."""

    def test_not_in_default_dependencies(self) -> None:
        assert "decisions/decisions.md" not in DEFAULT_DEPENDENCIES

    def test_not_in_walk_order(self) -> None:
        assert "decisions/decisions.md" not in WALK_ORDER

    def test_not_in_document_process(self) -> None:
        assert "decisions/decisions.md" not in DOCUMENT_PROCESS

    def test_packet_status_report_excludes_decisions(self, protocol_dir: Path) -> None:
        """The packet status report should not mention decisions/decisions.md."""
        record_hashes(protocol_dir)
        report = check_packet_status(protocol_dir)
        assert "decisions/decisions.md" not in report["documents"]


# -----------------------------------------------------------------------
# 2. Recording decisions
# -----------------------------------------------------------------------

class TestRecordDecision:
    """Recording a decision persists state to config.json with correct fields."""

    def test_record_decided_with_related_docs(self, protocol_dir: Path) -> None:
        record_decision(
            protocol_dir,
            "decision-01-test",
            "decided",
            ["solution/solution.md", "goal/requirements.md"],
        )

        # ClarityConfig + DecisionInfo are total=False TypedDicts; the
        # tests know the fields are populated post-record but pyright
        # treats them as optional.  Cast for direct indexing.
        config = cast(dict[str, Any], load_config(protocol_dir))
        state = config["decisionState"]["decision-01-test"]

        assert state["status"] == "decided"
        assert "solution/solution.md" in state["relatedDocs"]
        assert "goal/requirements.md" in state["relatedDocs"]
        assert state["decidedDate"] is not None  # should be today's date

    def test_record_gathering_status(self, protocol_dir: Path) -> None:
        record_decision(protocol_dir, "decision-02-test", "gathering")

        config = cast(dict[str, Any], load_config(protocol_dir))
        state = config["decisionState"]["decision-02-test"]
        assert state["status"] == "gathering"
        assert state["decidedDate"] is None  # not decided yet

    def test_record_preserves_existing_config(self, protocol_dir: Path) -> None:
        """Recording a decision should not clobber other config fields."""
        config_before = cast(dict[str, Any], load_config(protocol_dir))
        assert "clarityAgent" in config_before

        record_decision(protocol_dir, "decision-03-test", "decided")

        config_after = cast(dict[str, Any], load_config(protocol_dir))
        assert config_after["clarityAgent"] == config_before["clarityAgent"]
        assert config_after["thinkers"] == config_before["thinkers"]

    def test_invalid_status_raises(self, protocol_dir: Path) -> None:
        with pytest.raises(ValueError, match="Invalid status"):
            record_decision(protocol_dir, "bad", "invalid-status")

    def test_decided_date_set_only_once(self, protocol_dir: Path) -> None:
        """decidedDate should be set on first transition to decided
        and not overwritten on subsequent updates."""
        record_decision(protocol_dir, "decision-04-test", "decided")
        config1 = cast(dict[str, Any], load_config(protocol_dir))
        first_date = config1["decisionState"]["decision-04-test"]["decidedDate"]

        # Re-record with same status — date should not change.
        record_decision(protocol_dir, "decision-04-test", "decided")
        config2 = cast(dict[str, Any], load_config(protocol_dir))
        assert (
            config2["decisionState"]["decision-04-test"]["decidedDate"]
            == first_date
        )


# -----------------------------------------------------------------------
# 3. Agent format includes decision status
# -----------------------------------------------------------------------

class TestAgentFormatIncludesDecisions:
    """The agent-friendly output should include a Decision Status section."""

    def test_decided_produces_decision_status_section(self, protocol_dir: Path) -> None:
        record_decision(
            protocol_dir,
            "decision-01-test",
            "decided",
            ["solution/solution.md"],
        )

        dreport = check_decision_triggers(protocol_dir)
        output = format_decisions_for_agent(dreport)

        assert "## Decision Status" in output

    def test_no_decisions_produces_empty_output(self, protocol_dir: Path) -> None:
        dreport = check_decision_triggers(protocol_dir)
        output = format_decisions_for_agent(dreport)
        assert output == ""

    def test_all_current_says_no_triggers(self, protocol_dir: Path) -> None:
        record_decision(
            protocol_dir,
            "decision-01-test",
            "decided",
            ["solution/solution.md"],
        )

        dreport = check_decision_triggers(protocol_dir)
        output = format_decisions_for_agent(dreport)

        assert "no triggers fired" in output.lower()


# -----------------------------------------------------------------------
# 4. Trigger detection when related docs change
# -----------------------------------------------------------------------

class TestTriggerDetection:
    """When a related document's content changes after a decision is recorded,
    the packet status checker should report a preliminary trigger."""

    def test_trigger_fires_on_doc_change(self, protocol_dir: Path) -> None:
        record_decision(
            protocol_dir,
            "decision-01-test",
            "decided",
            ["goal/requirements.md"],
        )

        # Mutate the related document.
        req_path = protocol_dir / "goal/requirements.md"
        req_path.write_text(req_path.read_text() + "\n2. Must support decaf\n")

        dreport = check_decision_triggers(protocol_dir)

        assert len(dreport["triggers"]) == 1
        assert dreport["triggers"][0]["decision"] == "decision-01-test"
        assert "goal/requirements.md" in dreport["triggers"][0]["changed_docs"]

    def test_no_trigger_when_doc_unchanged(self, protocol_dir: Path) -> None:
        record_decision(
            protocol_dir,
            "decision-01-test",
            "decided",
            ["goal/requirements.md"],
        )

        dreport = check_decision_triggers(protocol_dir)
        assert len(dreport["triggers"]) == 0

    def test_trigger_in_agent_format(self, protocol_dir: Path) -> None:
        record_decision(
            protocol_dir,
            "decision-01-test",
            "decided",
            ["solution/solution.md"],
        )

        (protocol_dir / "solution/solution.md").write_text(
            "# Solution\n\nActually, use a French press.\n"
        )

        dreport = check_decision_triggers(protocol_dir)
        output = format_decisions_for_agent(dreport)

        assert "Preliminary Triggers" in output
        assert "decision-01-test" in output
        assert "solution/solution.md" in output

    def test_resnap_clears_trigger(self, protocol_dir: Path) -> None:
        """Re-recording a decision without new related-docs re-snapshots
        hashes, clearing the trigger."""
        record_decision(
            protocol_dir,
            "decision-01-test",
            "decided",
            ["goal/requirements.md"],
        )

        # Mutate the doc to fire a trigger.
        req_path = protocol_dir / "goal/requirements.md"
        req_path.write_text(req_path.read_text() + "\n2. Must support decaf\n")

        # Confirm trigger fires.
        dreport = check_decision_triggers(protocol_dir)
        assert len(dreport["triggers"]) == 1

        # Re-record without specifying related-docs → re-snapshots.
        record_decision(protocol_dir, "decision-01-test", "decided")

        dreport = check_decision_triggers(protocol_dir)
        assert len(dreport["triggers"]) == 0


# -----------------------------------------------------------------------
# 5. Reconsideration-needed surfaces prominently
# -----------------------------------------------------------------------

class TestReconsiderationNeeded:
    """Decisions marked reconsideration-needed should appear in the
    prominent section of the agent output."""

    def test_reconsideration_in_report(self, protocol_dir: Path) -> None:
        record_decision(protocol_dir, "decision-01-test", "reconsideration-needed")

        dreport = check_decision_triggers(protocol_dir)
        assert "decision-01-test" in dreport["reconsideration"]

    def test_reconsideration_in_agent_output(self, protocol_dir: Path) -> None:
        record_decision(protocol_dir, "decision-01-test", "reconsideration-needed")

        dreport = check_decision_triggers(protocol_dir)
        output = format_decisions_for_agent(dreport)

        assert "Decisions Needing Reconsideration" in output
        assert "decision-01-test" in output
        assert "decision-guidance" in output

    def test_pending_in_report(self, protocol_dir: Path) -> None:
        record_decision(protocol_dir, "decision-01-test", "gathering")
        record_decision(protocol_dir, "decision-02-test", "needed")

        dreport = check_decision_triggers(protocol_dir)
        assert "decision-01-test" in dreport["pending"]
        assert "decision-02-test" in dreport["pending"]


# -----------------------------------------------------------------------
# 6. Process guide structural checks
# -----------------------------------------------------------------------

class TestProcessGuideStructure:
    """decision-guidance.md exists and is referenced by clarity-agent.md."""

    REPO_ROOT = Path(__file__).resolve().parent.parent

    def test_decision_guidance_exists(self) -> None:
        assert (self.REPO_ROOT / "processes" / "decision-guidance.md").exists()

    def test_referenced_in_clarity_agent(self) -> None:
        text = (self.REPO_ROOT / "processes" / "clarity-agent.md").read_text()
        assert "decision-guidance" in text

    def test_three_stages_in_clarity_agent(self) -> None:
        """The three-stage reconsideration model should be present."""
        text = (self.REPO_ROOT / "processes" / "clarity-agent.md").read_text()
        assert "Preliminary triggers" in text
        assert "Trigger analysis" in text
        assert "Reconsideration" in text
