"""Tests for failure_state.py — deterministic failure-phase routing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from clarity_agent.protocol.failure_state import (
    _has_management_plan,
    check_failure_state,
)
from clarity_agent.protocol.mailbox import Mailbox

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_protocol(tmp_path: Path) -> Path:
    """Create a minimal .clarity-protocol directory."""
    pd = tmp_path / ".clarity-protocol"
    pd.mkdir()
    (pd / "mailboxes").mkdir()
    (pd / "archive").mkdir()
    return pd


def _make_failure_file(
    protocol_dir: Path,
    name: str,
    *,
    managed: bool = False,
) -> Path:
    """Write a failure file with or without a management plan."""
    failures_dir = protocol_dir / "failures"
    failures_dir.mkdir(exist_ok=True)
    content = f"# Failure: {name}\n\n## Summary\n\nSomething bad.\n\n## Failure Chain\n\n1. Step one.\n"
    if managed:
        content += "\n## Management Plan\n\nWe will do X to handle this.\n"
    else:
        content += "\n## Management Plan\n\n[Not yet developed. Run failure management to develop a plan.]\n"
    path = failures_dir / name
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# _has_management_plan
# ---------------------------------------------------------------------------

class TestHasManagementPlan:
    """_has_management_plan checks for real management content."""

    def test_with_real_plan(self, tmp_path: Path) -> None:
        path = tmp_path / "failure-01-test.md"
        path.write_text("# Failure\n\n## Management Plan\n\nReal plan content.\n")
        assert _has_management_plan(path) is True

    def test_with_placeholder(self, tmp_path: Path) -> None:
        path = tmp_path / "failure-01-test.md"
        path.write_text(
            "# Failure\n\n## Management Plan\n\n"
            "[Not yet developed. Run failure management to develop a plan.]\n"
        )
        assert _has_management_plan(path) is False

    def test_without_section(self, tmp_path: Path) -> None:
        path = tmp_path / "failure-01-test.md"
        path.write_text("# Failure\n\n## Summary\n\nJust a summary.\n")
        assert _has_management_plan(path) is False

    def test_empty_section(self, tmp_path: Path) -> None:
        path = tmp_path / "failure-01-test.md"
        path.write_text("# Failure\n\n## Management Plan\n\n")
        assert _has_management_plan(path) is False


# ---------------------------------------------------------------------------
# check_failure_state — empty project
# ---------------------------------------------------------------------------

class TestCheckFailureStateEmpty:
    """Empty project: no failures, no mailbox."""

    def test_brainstorming_recommended(self, tmp_path: Path) -> None:
        pd = _make_protocol(tmp_path)
        state = check_failure_state(pd)
        assert state.recommended_phase == "failure-brainstorming"

    def test_no_pending_items(self, tmp_path: Path) -> None:
        pd = _make_protocol(tmp_path)
        state = check_failure_state(pd)
        assert state.pending_analysis_count == 0
        assert state.unmitigated_failures == []
        assert state.brainstorm_in_progress is False


# ---------------------------------------------------------------------------
# check_failure_state — items in brainstorm mailbox
# ---------------------------------------------------------------------------

class TestCheckFailureStatePendingAnalysis:
    """Items in brainstorm mailbox: analysis recommended."""

    def test_analysis_recommended(self, tmp_path: Path) -> None:
        pd = _make_protocol(tmp_path)
        mb = Mailbox.create(pd, "failure-brainstorm", {
            "display_name": "failure brainstorming",
            "collector": "failure-analysis",
            "collector_type": "batch",
            "status": "ready for analysis",
        })
        mb.write("raw-failure-1", "# Failure 1\n")
        mb.write("raw-failure-2", "# Failure 2\n")

        state = check_failure_state(pd)
        assert state.recommended_phase == "failure-analysis"
        assert state.pending_analysis_count == 2

    def test_brainstorming_available_but_not_recommended(self, tmp_path: Path) -> None:
        pd = _make_protocol(tmp_path)
        mb = Mailbox.create(pd, "failure-brainstorm", {
            "display_name": "failure brainstorming",
            "collector": "failure-analysis",
            "collector_type": "batch",
            "status": "ready for analysis",
        })
        mb.write("raw-failure", "# Failure\n")

        state = check_failure_state(pd)
        brainstorm_opts = [o for o in state.options if o.phase == "failure-brainstorming"]
        assert len(brainstorm_opts) == 1
        assert brainstorm_opts[0].recommended is False


# ---------------------------------------------------------------------------
# check_failure_state — failure files without management plans
# ---------------------------------------------------------------------------

class TestCheckFailureStateUnmitigated:
    """Failure files exist but lack management plans."""

    def test_management_recommended(self, tmp_path: Path) -> None:
        pd = _make_protocol(tmp_path)
        _make_failure_file(pd, "failure-01-auth-bypass.md", managed=False)
        _make_failure_file(pd, "failure-02-xss.md", managed=False)

        state = check_failure_state(pd)
        assert state.recommended_phase == "failure-management"
        assert len(state.unmitigated_failures) == 2

    def test_managed_failures_excluded(self, tmp_path: Path) -> None:
        pd = _make_protocol(tmp_path)
        _make_failure_file(pd, "failure-01-auth-bypass.md", managed=True)

        state = check_failure_state(pd)
        assert state.unmitigated_failures == []
        assert state.mitigated_failures == ["failure-01-auth-bypass.md"]
        # Management not offered because no unmitigated failures.
        mgmt_opts = [o for o in state.options if o.phase == "failure-management"]
        assert mgmt_opts == []


# ---------------------------------------------------------------------------
# check_failure_state — active lockfiles
# ---------------------------------------------------------------------------

class TestCheckFailureStateLocks:
    """Active lockfiles: brainstorming in progress."""

    def test_brainstorming_unavailable(self, tmp_path: Path) -> None:
        pd = _make_protocol(tmp_path)
        mb = Mailbox.create(pd, "failure-brainstorm", {
            "display_name": "failure brainstorming",
            "collector": "failure-analysis",
            "collector_type": "batch",
            "status": "collecting",
        })
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        mb.create_lock("sec-thinker", future)

        state = check_failure_state(pd)
        assert state.brainstorm_in_progress is True
        brainstorm_opts = [o for o in state.options if o.phase == "failure-brainstorming"]
        assert brainstorm_opts == []


# ---------------------------------------------------------------------------
# check_failure_state — mixed state
# ---------------------------------------------------------------------------

class TestCheckFailureStateMixed:
    """Both pending items and unmanaged failures: analysis recommended first."""

    def test_analysis_takes_priority(self, tmp_path: Path) -> None:
        pd = _make_protocol(tmp_path)
        mb = Mailbox.create(pd, "failure-brainstorm", {
            "display_name": "failure brainstorming",
            "collector": "failure-analysis",
            "collector_type": "batch",
            "status": "ready for analysis",
        })
        mb.write("raw-failure", "# Failure\n")
        _make_failure_file(pd, "failure-01-auth-bypass.md", managed=False)

        state = check_failure_state(pd)
        assert state.recommended_phase == "failure-analysis"
        # Management is available but not recommended.
        mgmt_opts = [o for o in state.options if o.phase == "failure-management"]
        assert len(mgmt_opts) == 1
        assert mgmt_opts[0].recommended is False
