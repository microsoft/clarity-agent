"""Deterministic failure-phase routing.

Inspects the brainstorm mailbox, lockfiles, and failure documents to
determine which failure-management phase is appropriate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from clarity_agent.protocol.mailbox import LockInfo, Mailbox

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class PhaseOption:
    """A failure-management phase that could be run next."""

    phase: str          # "failure-brainstorming" | "failure-analysis" | "failure-management"
    recommended: bool
    reason: str


@dataclass
class FailureState:
    """Snapshot of the current failure-management state."""

    brainstorm_in_progress: bool = False
    active_locks: list[LockInfo] = field(default_factory=list)
    pending_analysis_count: int = 0
    unmitigated_failures: list[str] = field(default_factory=list)
    mitigated_failures: list[str] = field(default_factory=list)
    options: list[PhaseOption] = field(default_factory=list)
    recommended_phase: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAILURE_FILE_RE = re.compile(r"^failure-\d+-.*\.md$")

# Matches the ## Management Plan header.
_MGMT_HEADER_RE = re.compile(r"^##\s+Management\s+Plan", re.MULTILINE)

# Placeholder markers that indicate the management plan hasn't been written.
_PLACEHOLDER_PATTERNS = [
    "Not yet developed",
    "[Not yet developed",
    "Run failure management",
]


def _has_management_plan(file_path: Path) -> bool:
    """Check whether a failure file has a real management plan section."""
    text = file_path.read_text()
    match = _MGMT_HEADER_RE.search(text)
    if not match:
        return False
    # Everything after the header line.
    after_header = text[match.end():]
    # Strip whitespace and check for placeholder content.
    content = after_header.strip()
    if not content:
        return False
    for pattern in _PLACEHOLDER_PATTERNS:
        if pattern in content[:200]:
            return False
    return True


def _scan_failure_files(protocol_dir: Path) -> tuple[list[str], list[str]]:
    """Scan failure-NN-*.md files and classify as mitigated/unmitigated.

    Returns ``(unmitigated, mitigated)`` where each is a list of filenames.
    """
    failures_dir = protocol_dir / "failures"
    if not failures_dir.is_dir():
        return [], []

    unmitigated: list[str] = []
    mitigated: list[str] = []

    for path in sorted(failures_dir.iterdir()):
        if _FAILURE_FILE_RE.match(path.name):
            if _has_management_plan(path):
                mitigated.append(path.name)
            else:
                unmitigated.append(path.name)

    return unmitigated, mitigated


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def check_failure_state(protocol_dir: Path) -> FailureState:
    """Determine which failure-management phase is appropriate.

    Inspects:
    - The ``failure-brainstorm`` mailbox for active locks and pending items
    - The ``failures/`` directory for analyzed failure files

    Returns a :class:`FailureState` with available options and a recommendation.
    """
    state = FailureState()

    # 1. Check brainstorm mailbox.
    mailbox = Mailbox(protocol_dir, "failure-brainstorm")
    state.active_locks = mailbox.active_locks()
    state.brainstorm_in_progress = len(state.active_locks) > 0

    if mailbox.exists:
        state.pending_analysis_count = len(mailbox.list_items())

    # 2. Scan failure files.
    state.unmitigated_failures, state.mitigated_failures = _scan_failure_files(
        protocol_dir,
    )

    # 3. Determine phase options.
    options: list[PhaseOption] = []

    # Analysis is recommended when there are pending items.
    if state.pending_analysis_count > 0:
        options.append(PhaseOption(
            phase="failure-analysis",
            recommended=True,
            reason=f"{state.pending_analysis_count} raw failure mode(s) pending analysis",
        ))

    # Management is recommended when there are unmitigated failures.
    if state.unmitigated_failures:
        options.append(PhaseOption(
            phase="failure-management",
            recommended=state.pending_analysis_count == 0,
            reason=f"{len(state.unmitigated_failures)} failure(s) analyzed but without management plans",
        ))

    # Brainstorming availability depends on whether it's already in progress.
    if state.brainstorm_in_progress:
        # Can't start new brainstorming while async thinkers are running.
        pass
    else:
        never_started = (
            state.pending_analysis_count == 0
            and not state.unmitigated_failures
            and not state.mitigated_failures
        )
        options.append(PhaseOption(
            phase="failure-brainstorming",
            recommended=never_started,
            reason=(
                "No failure work in progress — brainstorming is the starting point"
                if never_started
                else "Run additional thinkers"
            ),
        ))

    state.options = options
    state.recommended_phase = next(
        (o.phase for o in options if o.recommended), None,
    )

    return state
