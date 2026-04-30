#!/usr/bin/env python3
"""
Clarity Protocol Packet Status

Tracks which documents in a .clarity-protocol/ directory need attention,
relative to their dependencies. Uses content hashes (not mtimes) and a
dependency graph to determine what needs updating.

Content hashes are stored in config.json under "documentState". Each document
records its own content hash and the hashes of its dependencies at the time it
was last accepted. A document is stale when any dependency's current hash
differs from the recorded hash — meaning the dependency's content changed since
this document was last reviewed.

Use --record to capture the current baseline (like a build system recording
input hashes after a successful build).

Can be used standalone (CLI) or imported as a module by the clarity CLI (``clarity.py``).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, TypedDict

# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------

# Default dependency graph for clarity protocol documents.
# Keys are document paths relative to .clarity-protocol/.
# Values are lists of documents this document depends on.
#
# The graph has an intentional cycle between failures and architecture:
# failures should be re-analyzed when architecture changes, and architecture
# should be reviewed when failures change. The checker handles this gracefully
# by reporting status based on content hashes without trying to resolve
# the cycle. The clarity agent's priority ordering (failure analysis before
# architecture design) naturally breaks the cycle during bootstrap.
DEFAULT_DEPENDENCIES: dict[str, list[str]] = {
    "goal/problem.md": [],
    "goal/stakeholders.md": ["goal/problem.md"],
    "goal/requirements.md": ["goal/problem.md", "goal/stakeholders.md"],
    "goal/open-questions.md": ["goal/problem.md"],
    "solution/solution.md": ["goal/problem.md", "goal/requirements.md", "goal/open-questions.md"],
    "failures/failures.md": ["solution/solution.md", "solution/architecture.md"],
    "solution/architecture.md": ["solution/solution.md", "failures/failures.md"],
    # The solution summary captures "what's the plan?" in ≤2 pages.
    # It depends on the solution and architecture — updated when either changes.
    "solution/solution-summary.md": ["solution/solution.md", "solution/architecture.md"],
    # The summary is the general-audience narrative ("what is this and why
    # should you care?"). It depends on the problem, stakeholders, and
    # solution — the three things that shape the story.
    "summary.md": ["goal/problem.md", "goal/stakeholders.md", "solution/solution.md"],
    # Decisions are cross-cutting — tracked separately via decisionState,
    # not as part of the document dependency graph.
}

# Topological walk order of the dependency graph. This defines the order in
# which clarity-agent examines documents: earlier documents are more foundational,
# so problems upstream should be addressed before anything downstream.
#
# The cycle between failures and architecture is broken by convention:
# failures come first (discover what could go wrong before locking in design).
WALK_ORDER: list[str] = [
    "goal/problem.md",
    "goal/stakeholders.md",
    "goal/requirements.md",
    "goal/open-questions.md",
    "solution/solution.md",
    "failures/failures.md",
    "solution/architecture.md",
    "solution/solution-summary.md",
    "summary.md",
]

# Maps each document to the process responsible for creating/updating it.
# Used by next_action() to recommend which process to run.
DOCUMENT_PROCESS: dict[str, str | None] = {
    "goal/problem.md": "problem-clarification",
    "goal/stakeholders.md": "problem-clarification",
    "goal/requirements.md": "problem-clarification",
    "goal/open-questions.md": "problem-clarification",
    "solution/solution.md": "solution-brainstorming",
    "failures/failures.md": "failure-analysis",
    "solution/architecture.md": "architecture-design",
    "solution/solution-summary.md": None,  # Updated as a side-effect of solution-brainstorming and architecture-design
    "summary.md": "message-clarification",
}

# Markers that indicate a file is still a template (not yet written with
# real content). If any marker appears anywhere in the file, it's a template.
TEMPLATE_MARKERS: list[str] = [
    "[To be determined",
    "[TBD]",
    "[Write this like you're telling a friend",
    "[Project Title]",
    "No failure modes have been analyzed yet",
    "No decisions have been recorded yet",
    "No open questions have been identified yet",
    "No observations have been recorded yet",
    "No questions have been resolved yet",
]


# ---------------------------------------------------------------------------
# Type definitions
# ---------------------------------------------------------------------------

class DocumentState(TypedDict):
    """Stored in config.json for each tracked document."""
    contentHash: str
    dependencyHashes: dict[str, str]


class StaleDependency(TypedDict):
    """Info about a single dependency that has changed."""
    doc: str
    current_hash: str
    recorded_hash: str | None


class DocumentStatus(TypedDict):
    """Status of a single document in the packet status report."""
    status: str  # "current" | "stale" | "empty" | "missing" | "untracked"
    content_hash: str | None
    dependencies: list[str]
    stale_because: list[StaleDependency]


class ReportSummary(TypedDict):
    """Aggregated counts by status."""
    current: list[str]
    stale: list[str]
    empty: list[str]
    missing: list[str]
    untracked: list[str]


class PacketStatusReport(TypedDict):
    """Complete packet status report for a clarity protocol."""
    protocol_dir: str
    documents: dict[str, DocumentStatus]
    summary: ReportSummary
    mailboxes: list[dict[str, Any]]  # Active async operations (from mailbox system)


class DecisionInfo(TypedDict, total=False):
    """State of a single decision, stored in config.json under decisionState."""
    status: str  # "gathering" | "needed" | "decided" | "reconsideration-needed"
    relatedDocs: dict[str, str]  # doc path -> content hash at decision time
    decidedDate: str | None
    reviewBy: str | None  # ISO date, for future time-based triggers


class DecisionTrigger(TypedDict):
    """A decided decision whose related documents have changed."""
    decision: str
    changed_docs: list[str]


class DecisionReport(TypedDict):
    """Report on decision states and preliminary triggers."""
    decisions: dict[str, DecisionInfo]
    triggers: list[DecisionTrigger]  # decided decisions with changed context
    pending: list[str]  # decisions in gathering or needed state
    reconsideration: list[str]  # decisions already flagged for reconsideration


class ClarityConfig(TypedDict, total=False):
    """Shape of config.json. All fields optional (total=False)."""
    clarityAgent: dict[str, str]
    thinkers: dict[str, list[str]]
    processes: dict[str, list[str]]
    dependencies: dict[str, list[str]]
    documentState: dict[str, DocumentState]
    decisionState: dict[str, DecisionInfo]
    brainstormState: dict[str, Any]



class NextAction(TypedDict):
    """Recommendation from walking the dependency graph."""
    document: str
    status: str  # "empty" | "missing" | "stale" | "untracked"
    process: str | None
    reason: str


class ProcessPhase(TypedDict):
    """Availability status of a single process."""
    process: str       # e.g. "failure-brainstorming"
    status: str        # "recommended" | "available" | "unavailable"
    reason: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_template(file_path: Path) -> bool:
    """Check if a file contains only template/placeholder content."""
    if not file_path.exists():
        return True
    try:
        content: str = file_path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        content = file_path.read_text().strip()
    if not content:
        return True
    for marker in TEMPLATE_MARKERS:
        if marker in content:
            return True
    return False


def compute_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of file contents."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def load_config(protocol_dir: Path) -> ClarityConfig:
    """Load config.json from the protocol directory."""
    config_path: Path = protocol_dir / "config.json"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        result: ClarityConfig = json.load(f)
        return result


def save_config(protocol_dir: Path, config: ClarityConfig) -> None:
    """Write config.json to the protocol directory, preserving formatting."""
    config_path: Path = protocol_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def get_dependencies(config: ClarityConfig) -> dict[str, list[str]]:
    """Get the dependency graph, merging defaults with optional config overrides.

    If config.json contains a "dependencies" key, those entries override
    the defaults for the specified documents only. Documents not mentioned
    in the override keep their default dependencies.
    """
    deps: dict[str, list[str]] = dict(DEFAULT_DEPENDENCIES)
    overrides: dict[str, list[str]] | None = config.get("dependencies")
    if overrides is not None:
        deps.update(overrides)
    return deps


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def check_packet_status(protocol_dir: Path) -> PacketStatusReport:
    """Check packet status of all tracked documents in a clarity protocol.

    Statuses:
      - "current": content tracked, all dependency hashes match
      - "stale": content tracked, but at least one dependency's hash changed
      - "empty": file exists but contains only template placeholders
      - "missing": file does not exist
      - "untracked": file has real content but no recorded baseline
    """
    config: ClarityConfig = load_config(protocol_dir)
    dependencies: dict[str, list[str]] = get_dependencies(config)
    state: dict[str, DocumentState] = config.get("documentState", {})

    documents: dict[str, DocumentStatus] = {}
    summary: ReportSummary = {
        "current": [], "stale": [], "empty": [],
        "missing": [], "untracked": [],
    }

    for doc_path, deps in dependencies.items():
        full_path: Path = protocol_dir / doc_path
        content_hash: str | None = None
        stale_because: list[StaleDependency] = []
        status: str

        if not full_path.exists():
            status = "missing"
        elif is_template(full_path):
            status = "empty"
        elif doc_path not in state:
            # File has real content but we have no recorded baseline.
            status = "untracked"
            content_hash = compute_hash(full_path)
        else:
            content_hash = compute_hash(full_path)
            recorded: DocumentState = state[doc_path]

            for dep in deps:
                dep_full: Path = protocol_dir / dep
                if not dep_full.exists() or is_template(dep_full):
                    # Empty/template dependencies don't trigger a stale status —
                    # there's nothing new to incorporate.
                    continue
                current_dep_hash: str = compute_hash(dep_full)
                recorded_dep_hash: str | None = recorded["dependencyHashes"].get(dep)
                if current_dep_hash != recorded_dep_hash:
                    stale_because.append({
                        "doc": dep,
                        "current_hash": current_dep_hash,
                        "recorded_hash": recorded_dep_hash,
                    })

            status = "stale" if stale_because else "current"

        documents[doc_path] = {
            "status": status,
            "content_hash": content_hash,
            "dependencies": deps,
            "stale_because": stale_because,
        }
        summary[status].append(doc_path)  # type: ignore[literal-required]

    mailboxes: list[dict[str, Any]] = check_mailbox_status(protocol_dir)

    return {
        "protocol_dir": str(protocol_dir),
        "documents": documents,
        "summary": summary,
        "mailboxes": mailboxes,
    }


def record_hashes(
    protocol_dir: Path,
    doc_paths: list[str] | None = None,
) -> list[str]:
    """Record current content hashes for documents and their dependencies.

    If doc_paths is None, records all tracked documents that have real content.
    Returns the list of documents that were recorded.
    """
    config: ClarityConfig = load_config(protocol_dir)
    dependencies: dict[str, list[str]] = get_dependencies(config)
    state: dict[str, DocumentState] = config.get("documentState", {})

    targets: list[str] = doc_paths if doc_paths else list(dependencies.keys())
    recorded: list[str] = []

    for doc_path in targets:
        if doc_path not in dependencies:
            continue  # skip unknown documents
        full_path: Path = protocol_dir / doc_path
        if not full_path.exists() or is_template(full_path):
            continue

        content_hash: str = compute_hash(full_path)
        dep_hashes: dict[str, str] = {}
        for dep in dependencies.get(doc_path, []):
            dep_full: Path = protocol_dir / dep
            if dep_full.exists() and not is_template(dep_full):
                dep_hashes[dep] = compute_hash(dep_full)

        state[doc_path] = {
            "contentHash": content_hash,
            "dependencyHashes": dep_hashes,
        }
        recorded.append(doc_path)

    config["documentState"] = state
    save_config(protocol_dir, config)
    return recorded


def check_decision_triggers(protocol_dir: Path) -> DecisionReport:
    """Check preliminary triggers for all tracked decisions.

    For each decision in "decided" state, compares the current content hashes
    of its related documents to the hashes recorded at decision time. If any
    have changed, the decision is reported as having fired triggers.

    This is Phase 1 only — a fired trigger means "the question is worth asking,"
    not "the decision needs to change." Phase 2 (AI-driven analysis of whether
    the change actually affects the decision) happens in the clarity-agent process.
    """
    config: ClarityConfig = load_config(protocol_dir)
    decision_state: dict[str, DecisionInfo] = config.get("decisionState", {})

    triggers: list[DecisionTrigger] = []
    pending: list[str] = []
    reconsideration: list[str] = []

    for decision_id, info in decision_state.items():
        status: str = info.get("status", "")

        if status in ("gathering", "needed"):
            pending.append(decision_id)
            continue

        if status == "reconsideration-needed":
            reconsideration.append(decision_id)
            continue

        if status != "decided":
            continue

        # Check if any related documents have changed since decision time.
        changed: list[str] = []
        for doc_path, recorded_hash in info.get("relatedDocs", {}).items():
            full_path: Path = protocol_dir / doc_path
            if full_path.exists() and not is_template(full_path):
                current_hash: str = compute_hash(full_path)
                if current_hash != recorded_hash:
                    changed.append(doc_path)

        if changed:
            triggers.append({
                "decision": decision_id,
                "changed_docs": changed,
            })

    return {
        "decisions": decision_state,
        "triggers": triggers,
        "pending": pending,
        "reconsideration": reconsideration,
    }


def check_mailbox_status(protocol_dir: Path) -> list[dict[str, Any]]:
    """Check for active async operations with pending items.

    Returns info about all nonempty mailboxes. Each entry has:
    ``name``, ``config`` (dict), and ``item_count`` (int).
    """
    from clarity_agent.protocol.mailbox import list_nonempty_mailboxes
    return list_nonempty_mailboxes(protocol_dir)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Content lints
# ---------------------------------------------------------------------------

def check_resolved_in_open_questions(protocol_dir: Path) -> list[str]:
    """Check for questions marked 'resolved' that are still in open-questions.md.

    Returns a list of warning strings (empty if clean).
    """
    oq_path: Path = protocol_dir / "goal" / "open-questions.md"
    if not oq_path.exists():
        return []

    import re

    warnings: list[str] = []
    current_question: str | None = None

    for line in oq_path.read_text().splitlines():
        heading_match = re.match(r"^##\s+(Q\d+:.+)", line)
        if heading_match:
            current_question = heading_match.group(1).strip()
        elif current_question and re.match(
            r"\*\*Status:\*\*\s*resolved", line, re.IGNORECASE
        ):
            warnings.append(
                f"`goal/open-questions.md` contains resolved question "
                f'"{current_question}" — move it to `goal/resolved-questions.md`'
            )
            current_question = None

    return warnings


# ---------------------------------------------------------------------------
# Process availability
# ---------------------------------------------------------------------------

def _has_content(report: PacketStatusReport, doc_path: str) -> bool:
    """Check if a document has real (non-template) content in the report."""
    if doc_path not in report["documents"]:
        return False
    return report["documents"][doc_path]["status"] not in ("empty", "missing")


def _is_non_current(report: PacketStatusReport, doc_path: str) -> bool:
    """Check if a document needs attention (status is not 'current')."""
    if doc_path not in report["documents"]:
        return True
    return report["documents"][doc_path]["status"] != "current"


def _resolve_process(doc_path: str, protocol_dir: Path) -> str | None:
    """Resolve which process to recommend for a document.

    For most documents, returns the static DOCUMENT_PROCESS mapping.
    For ``failures/failures.md``, inspects the failure state to determine
    the right phase dynamically.
    """
    if doc_path == "failures/failures.md":
        from clarity_agent.protocol.failure_state import check_failure_state
        state = check_failure_state(protocol_dir)
        return state.recommended_phase or "failure-brainstorming"
    return DOCUMENT_PROCESS.get(doc_path)


def check_process_availability(report: PacketStatusReport) -> list[ProcessPhase]:
    """Determine availability of all processes based on project state.

    Returns a list of :class:`ProcessPhase` entries — one per process —
    each with status ``"recommended"``, ``"available"``, or ``"unavailable"``
    and a reason explaining why.
    """
    from clarity_agent.protocol.failure_state import check_failure_state

    protocol_dir = Path(report["protocol_dir"])
    phases: list[ProcessPhase] = []

    # -- problem-clarification (always available; recommended if goal docs need work) --
    goal_docs = [d for d in WALK_ORDER if d.startswith("goal/")]
    goal_non_current = [d for d in goal_docs if _is_non_current(report, d)]
    if goal_non_current:
        first = goal_non_current[0]
        doc_status = report["documents"][first]["status"]
        phases.append({
            "process": "problem-clarification",
            "status": "recommended",
            "reason": f"{first} is {doc_status}",
        })
    else:
        phases.append({
            "process": "problem-clarification",
            "status": "available",
            "reason": "Refine the problem statement and goals",
        })

    # -- solution-brainstorming (requires problem.md content) --
    if _has_content(report, "goal/problem.md"):
        if _is_non_current(report, "solution/solution.md"):
            doc_status = report["documents"]["solution/solution.md"]["status"]
            phases.append({
                "process": "solution-brainstorming",
                "status": "recommended",
                "reason": f"solution/solution.md is {doc_status}",
            })
        else:
            phases.append({
                "process": "solution-brainstorming",
                "status": "available",
                "reason": "Problem defined — solution can be explored",
            })
    else:
        phases.append({
            "process": "solution-brainstorming",
            "status": "unavailable",
            "reason": "Requires goal/problem.md to have content",
        })

    # -- failure phases (from failure_state) --
    has_problem = _has_content(report, "goal/problem.md")
    failure_state = check_failure_state(protocol_dir)

    # failure-brainstorming
    if not has_problem:
        phases.append({
            "process": "failure-brainstorming",
            "status": "unavailable",
            "reason": "Requires goal/problem.md to have content",
        })
    elif failure_state.brainstorm_in_progress:
        phases.append({
            "process": "failure-brainstorming",
            "status": "unavailable",
            "reason": (
                f"Brainstorming in progress "
                f"({len(failure_state.active_locks)} async thinker(s) running)"
            ),
        })
    else:
        never_started = (
            failure_state.pending_analysis_count == 0
            and not failure_state.unmitigated_failures
            and not failure_state.mitigated_failures
        )
        phases.append({
            "process": "failure-brainstorming",
            "status": "recommended" if never_started else "available",
            "reason": (
                "No failure work in progress — brainstorming is the starting point"
                if never_started
                else "Run additional thinkers"
            ),
        })

    # failure-analysis
    if failure_state.pending_analysis_count > 0:
        phases.append({
            "process": "failure-analysis",
            "status": "recommended",
            "reason": (
                f"{failure_state.pending_analysis_count} raw failure mode(s) "
                f"pending analysis"
            ),
        })
    else:
        phases.append({
            "process": "failure-analysis",
            "status": "unavailable",
            "reason": "No items in brainstorming pool",
        })

    # failure-management
    if failure_state.unmitigated_failures:
        is_recommended = failure_state.pending_analysis_count == 0
        phases.append({
            "process": "failure-management",
            "status": "recommended" if is_recommended else "available",
            "reason": (
                f"{len(failure_state.unmitigated_failures)} failure(s) "
                f"without management plans"
            ),
        })
    else:
        phases.append({
            "process": "failure-management",
            "status": "unavailable",
            "reason": "No analyzed failure files without management plans",
        })

    # -- architecture-design (requires solution.md content) --
    if _has_content(report, "solution/solution.md"):
        if _is_non_current(report, "solution/architecture.md"):
            doc_status = report["documents"]["solution/architecture.md"]["status"]
            phases.append({
                "process": "architecture-design",
                "status": "recommended",
                "reason": f"solution/architecture.md is {doc_status}",
            })
        else:
            phases.append({
                "process": "architecture-design",
                "status": "available",
                "reason": "Solution defined — architecture can be designed",
            })
    else:
        phases.append({
            "process": "architecture-design",
            "status": "unavailable",
            "reason": "Requires solution/solution.md to have content",
        })

    # -- discovery-prototype / discovery-research (require open-questions) --
    if _has_content(report, "goal/open-questions.md"):
        phases.append({
            "process": "discovery-prototype",
            "status": "available",
            "reason": "Open questions exist — check for prototyping-strategy questions",
        })
        phases.append({
            "process": "discovery-research",
            "status": "available",
            "reason": "Open questions exist — check for research-strategy questions",
        })
    else:
        phases.append({
            "process": "discovery-prototype",
            "status": "unavailable",
            "reason": "No open questions identified",
        })
        phases.append({
            "process": "discovery-research",
            "status": "unavailable",
            "reason": "No open questions identified",
        })

    # -- decision-guidance (always available, cross-cutting) --
    phases.append({
        "process": "decision-guidance",
        "status": "available",
        "reason": "Always available — cross-cutting process for important choices",
    })

    return phases


def record_decision(
    protocol_dir: Path,
    decision_id: str,
    status: str,
    related_docs: list[str] | None = None,
) -> None:
    """Record or update the state of a decision in config.json.

    Computes current content hashes for the related documents so that
    future runs can detect when context has changed (preliminary triggers).
    """
    from datetime import date

    valid_statuses: set[str] = {"gathering", "needed", "decided", "reconsideration-needed"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {valid_statuses}")

    config: ClarityConfig = load_config(protocol_dir)
    decision_state: dict[str, DecisionInfo] = config.get("decisionState", {})

    existing: DecisionInfo = decision_state.get(decision_id, {})  # type: ignore[assignment]

    # Compute hashes for related docs.
    doc_hashes: dict[str, str] = {}
    if related_docs:
        for doc_path in related_docs:
            full_path: Path = protocol_dir / doc_path
            if full_path.exists() and not is_template(full_path):
                doc_hashes[doc_path] = compute_hash(full_path)
    elif "relatedDocs" in existing:
        # No new related docs specified — preserve existing ones but
        # re-snapshot their current hashes (useful when confirming a
        # decision still holds after review).
        for doc_path in existing["relatedDocs"]:
            full_path = protocol_dir / doc_path
            if full_path.exists() and not is_template(full_path):
                doc_hashes[doc_path] = compute_hash(full_path)

    # Set decidedDate on first transition to "decided".
    decided_date: str | None = existing.get("decidedDate")
    if status == "decided" and not decided_date:
        decided_date = date.today().isoformat()

    decision_state[decision_id] = {
        "status": status,
        "relatedDocs": doc_hashes,
        "decidedDate": decided_date,
        "reviewBy": existing.get("reviewBy"),
    }

    config["decisionState"] = decision_state
    save_config(protocol_dir, config)


def next_action(report: PacketStatusReport) -> NextAction | None:
    """Walk the dependency graph and return the first document needing attention.

    Walks in WALK_ORDER (topological sort of the dependency graph). Returns
    the first document that isn't "current" — i.e., the first one that is
    empty, missing, stale, or untracked.

    Returns None when all documents are current, meaning the AI should
    read documents in walk order and judge quality ("rough" vs "solid").
    """
    for doc_path in WALK_ORDER:
        if doc_path not in report["documents"]:
            continue
        info: DocumentStatus = report["documents"][doc_path]
        status: str = info["status"]
        if status == "current":
            continue

        protocol_dir = Path(report["protocol_dir"])
        process: str | None = _resolve_process(doc_path, protocol_dir)
        reason: str = _build_reason(doc_path, status, info)
        return {
            "document": doc_path,
            "status": status,
            "process": process,
            "reason": reason,
        }
    return None


def _build_reason(
    doc_path: str,
    status: str,
    info: DocumentStatus,
) -> str:
    """Build a human-readable reason for why this document needs attention."""
    if status == "empty":
        return f"{doc_path} is empty (template placeholder)"
    elif status == "missing":
        return f"{doc_path} does not exist"
    elif status == "stale":
        deps: str = ", ".join(d["doc"] for d in info["stale_because"])
        return f"{doc_path} is stale — these dependencies changed: {deps}"
    elif status == "untracked":
        return f"{doc_path} has content but no recorded baseline"
    return f"{doc_path} has status: {status}"


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_report(report: PacketStatusReport, verbose: bool = False) -> str:
    """Format a packet status report for human reading."""
    lines: list[str] = []
    lines.append("Clarity Protocol Packet Status")
    lines.append("=" * 40)
    lines.append("")

    status_icons: dict[str, str] = {
        "current": "✓",
        "stale": "⚠",
        "empty": "○",
        "missing": "✗",
        "untracked": "?",
    }

    for doc_path, info in report["documents"].items():
        icon: str = status_icons.get(info["status"], "?")
        status_label: str = (
            info["status"].upper()
            if info["status"] in ("stale", "missing", "untracked")
            else info["status"]
        )
        lines.append(f"  {icon} {doc_path:<35} {status_label}")

        if info["stale_because"] and verbose:
            for dep in info["stale_because"]:
                if dep["recorded_hash"] is None:
                    lines.append(f"    └─ {dep['doc']} (new — not previously recorded)")
                else:
                    lines.append(f"    └─ {dep['doc']} (content changed)")

    lines.append("")

    # Summary
    s: ReportSummary = report["summary"]
    if s["stale"]:
        lines.append(f"⚠ {len(s['stale'])} document(s) are stale and should be reviewed.")
    if s["untracked"]:
        lines.append(f"? {len(s['untracked'])} document(s) are untracked. Run --record to establish baseline.")
    if s["empty"]:
        lines.append(f"○ {len(s['empty'])} document(s) are empty (not yet written).")
    if s["missing"]:
        lines.append(f"✗ {len(s['missing'])} document(s) are missing.")
    if (
        s["current"]
        and not s["stale"]
        and not s["missing"]
        and not s["untracked"]
    ):
        if not s["empty"]:
            lines.append("✓ All documents are current.")
        else:
            lines.append(f"✓ {len(s['current'])} written document(s) are current.")

    # Content lints
    protocol_dir = Path(report["protocol_dir"])
    lint_warnings_hr: list[str] = check_resolved_in_open_questions(protocol_dir)
    if lint_warnings_hr:
        lines.append("")
        for warning in lint_warnings_hr:
            lines.append(f"⚠ {warning}")

    # Process availability
    phases: list[ProcessPhase] = check_process_availability(report)
    status_icons_proc: dict[str, str] = {
        "recommended": "●",
        "available": "·",
        "unavailable": "✗",
    }

    lines.append("")
    lines.append("Process Availability")
    lines.append("-" * 40)

    for p in phases:
        icon = status_icons_proc.get(p["status"], "?")
        label: str = p["status"].upper() if p["status"] == "recommended" else p["status"]
        lines.append(f"  {icon} {p['process']:<30} {label}")
        if verbose:
            lines.append(f"    └─ {p['reason']}")

    # Active async operations (failure-brainstorm is covered by process availability).
    mailboxes: list[dict[str, Any]] = report.get("mailboxes", [])
    mailboxes = [mb for mb in mailboxes if mb["name"] != "failure-brainstorm"]
    if mailboxes:
        lines.append("")
        lines.append("Active Async Operations")
        lines.append("-" * 40)
        for mb in mailboxes:
            display: str = mb["config"].get("display_name", mb["name"])
            status: str = mb["config"].get("status", "active")
            lines.append(
                f"  {mb['name']}: {mb['item_count']} item(s) ({status}) — {display}"
            )

    return "\n".join(lines)



def format_for_agent(report: PacketStatusReport) -> str:
    """Format a packet status report for inclusion in an AI agent's system prompt.

    Includes a next-action recommendation (from walking the dependency graph)
    followed by the full document status for context. Active async operations
    (nonempty mailboxes) are always included from the report.
    """
    lines: list[str] = []
    lines.append("## Packet Status Report")
    lines.append("")

    # Next action recommendation
    action: NextAction | None = next_action(report)
    if action is not None:
        lines.append("### Recommended Next Step")
        lines.append("")
        lines.append(f"**{action['document']}** — {action['reason']}")
        if action["process"]:
            lines.append(f"Run process: `{action['process']}`")
        lines.append("")
    else:
        lines.append("### All Documents Mechanically Current")
        lines.append("")
        lines.append(
            "No issues detected. Walk documents in dependency order "
            "and assess quality (look for vague, incomplete, or rough content):"
        )
        lines.append("")
        for doc in WALK_ORDER:
            lines.append(f"- {doc}")
        lines.append("")

    # Full status for context
    s: ReportSummary = report["summary"]

    if s["stale"]:
        lines.append("### Stale Documents (need updating)")
        lines.append("")
        for doc_path in s["stale"]:
            info: DocumentStatus = report["documents"][doc_path]
            deps: str = ", ".join(d["doc"] for d in info["stale_because"])
            lines.append(
                f"- **{doc_path}** — stale because these dependencies changed: {deps}"
            )
        lines.append("")

    if s["untracked"]:
        lines.append("### Untracked Documents (no baseline recorded)")
        lines.append("")
        for doc_path in s["untracked"]:
            lines.append(f"- **{doc_path}**")
        lines.append("")

    if s["empty"]:
        lines.append("### Empty Documents (not yet written)")
        lines.append("")
        for doc_path in s["empty"]:
            lines.append(f"- **{doc_path}**")
        lines.append("")

    if s["current"]:
        lines.append("### Current Documents (up to date)")
        lines.append("")
        for doc_path in s["current"]:
            lines.append(f"- **{doc_path}**")
        lines.append("")

    # Content lints
    protocol_dir = Path(report["protocol_dir"])
    lint_warnings: list[str] = check_resolved_in_open_questions(protocol_dir)
    if lint_warnings:
        lines.append("### Warnings")
        lines.append("")
        for warning in lint_warnings:
            lines.append(f"- {warning}")
        lines.append("")

    # Process availability
    phases: list[ProcessPhase] = check_process_availability(report)
    recommended = [p for p in phases if p["status"] == "recommended"]
    available = [p for p in phases if p["status"] == "available"]
    unavailable = [p for p in phases if p["status"] == "unavailable"]

    lines.append("### Process Availability")
    lines.append("")
    lines.append(
        "Each process name below corresponds to a process guide in `processes/`. "
        "To run a recommended process, load and follow that guide — "
        "do not attempt the task directly."
    )
    lines.append("")
    if recommended:
        lines.append("**Recommended:**")
        for p in recommended:
            lines.append(f"- `{p['process']}` — {p['reason']}")
        lines.append("")
    if available:
        lines.append("**Available:**")
        for p in available:
            lines.append(f"- `{p['process']}` — {p['reason']}")
        lines.append("")
    if unavailable:
        lines.append("**Unavailable:**")
        for p in unavailable:
            lines.append(f"- `{p['process']}` — {p['reason']}")
        lines.append("")

    # Active async operations (failure-brainstorm is always covered by the
    # process availability section, so filter it from the generic list).
    mailboxes: list[dict[str, Any]] = report.get("mailboxes", [])
    mailboxes = [mb for mb in mailboxes if mb["name"] != "failure-brainstorm"]
    if mailboxes:
        lines.append("### Active Async Operations")
        lines.append("")
        for mb in mailboxes:
            display: str = mb["config"].get("display_name", mb["name"])
            count: int = mb["item_count"]
            status: str = mb["config"].get("status", "active")
            collector: str = mb["config"].get("collector", "unknown")
            if status == "ready for analysis":
                lines.append(
                    f"**{display}:** {count} item(s) ready. "
                    f"Run process: `{collector}`"
                )
            else:
                lines.append(f"**{display}:** {count} item(s) ({status}).")
        lines.append("")

    return "\n".join(lines)


def format_decision_report(dreport: DecisionReport, verbose: bool = False) -> str:
    """Format a decision report for human reading."""
    lines: list[str] = []

    if not dreport["decisions"]:
        return ""  # No decisions tracked — nothing to report.

    lines.append("")
    lines.append("Decisions")
    lines.append("-" * 40)
    lines.append("")

    status_icons: dict[str, str] = {
        "decided": "✓",
        "gathering": "…",
        "needed": "●",
        "reconsideration-needed": "⚠",
    }

    for decision_id, info in dreport["decisions"].items():
        icon: str = status_icons.get(info.get("status", ""), "?")
        status_label: str = info.get("status", "unknown")
        lines.append(f"  {icon} {decision_id:<45} {status_label}")

    if dreport["triggers"]:
        lines.append("")
        lines.append(
            f"⚠ {len(dreport['triggers'])} decision(s) have preliminary "
            f"triggers — related documents changed since the decision was made."
        )
        if verbose:
            for trigger in dreport["triggers"]:
                docs: str = ", ".join(trigger["changed_docs"])
                lines.append(f"  └─ {trigger['decision']}: {docs}")

    if dreport["reconsideration"]:
        lines.append(
            f"● {len(dreport['reconsideration'])} decision(s) flagged "
            f"for reconsideration."
        )

    if dreport["pending"]:
        lines.append(
            f"… {len(dreport['pending'])} decision(s) pending "
            f"(gathering info or awaiting decision)."
        )

    return "\n".join(lines)


def format_decisions_for_agent(dreport: DecisionReport) -> str:
    """Format a decision report for inclusion in an AI agent's system prompt.

    Three-stage model:
      - Stage 3 (reconsideration-needed): Surface at normal priority,
        alongside stale documents. These need user attention.
      - Stage 1 (preliminary triggers): Note that they exist, but don't
        analyze during normal assessment. Analyze when idle.
      - Pending decisions: Informational.
    """
    if not dreport["decisions"]:
        return ""

    lines: list[str] = []
    lines.append("## Decision Status")
    lines.append("")

    # Stage 3: confirmed reconsideration — surface prominently.
    if dreport["reconsideration"]:
        lines.append("### Decisions Needing Reconsideration")
        lines.append("")
        lines.append(
            "These decisions have been reviewed and confirmed as needing "
            "reconsideration. Surface to the user at the same priority as "
            "stale documents."
        )
        lines.append("")
        for decision_id in dreport["reconsideration"]:
            lines.append(f"- **{decision_id}** — run `decision-guidance`")
        lines.append("")

    # Stage 1: preliminary triggers — don't analyze now, just note.
    if dreport["triggers"]:
        lines.append("### Preliminary Triggers (analyze when idle)")
        lines.append("")
        lines.append(
            "Related documents changed since these decisions were made. "
            "Don't analyze during normal assessment. When nothing else "
            "needs attention, review whether the changes are material — "
            "if yes, mark `reconsideration-needed`; if no, re-record "
            "the decision to clear the trigger."
        )
        lines.append("")
        for trigger in dreport["triggers"]:
            docs: str = ", ".join(trigger["changed_docs"])
            lines.append(f"- **{trigger['decision']}** — changed: {docs}")
        lines.append("")

    if dreport["pending"]:
        lines.append("### Pending Decisions")
        lines.append("")
        for decision_id in dreport["pending"]:
            info: DecisionInfo = dreport["decisions"][decision_id]
            lines.append(f"- **{decision_id}** ({info.get('status', 'unknown')})")
        lines.append("")

    # If everything is clean, say so briefly.
    if (
        not dreport["triggers"]
        and not dreport["reconsideration"]
        and not dreport["pending"]
    ):
        lines.append("All tracked decisions are current — no triggers fired.")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Check packet status of clarity protocol documents",
    )
    parser.add_argument(
        "project_dir",
        nargs="?",
        default=".",
        help="Project directory containing .clarity-protocol/ (default: .)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of human-readable report",
    )
    parser.add_argument(
        "--agent",
        action="store_true",
        help="Output in agent-friendly markdown format",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed status reasons",
    )
    parser.add_argument(
        "--record",
        nargs="*",
        metavar="DOC",
        help="Record current hashes (all documents if none specified, or list specific ones)",
    )
    parser.add_argument(
        "--next",
        action="store_true",
        help="Show only the recommended next action (graph walk)",
    )
    parser.add_argument(
        "--record-decision",
        metavar="ID",
        help="Record a decision state (e.g. decision-01-implementation-approach)",
    )
    parser.add_argument(
        "--status",
        choices=["gathering", "needed", "decided", "reconsideration-needed"],
        help="Decision status (used with --record-decision)",
    )
    parser.add_argument(
        "--related-docs",
        nargs="*",
        metavar="DOC",
        help="Documents this decision is grounded in (used with --record-decision)",
    )

    args: argparse.Namespace = parser.parse_args()

    from clarity_agent.app_paths import protocol_dir as _protocol_dir
    protocol_dir: Path = _protocol_dir(Path(args.project_dir))
    if not protocol_dir.exists():
        parser.error(f"No protocol directory found in {args.project_dir}")

    # Record decision mode
    if args.record_decision is not None:
        if not args.status:
            parser.error("--status is required with --record-decision")
        record_decision(
            protocol_dir,
            args.record_decision,
            args.status,
            args.related_docs,
        )
        print(f"Recorded decision: {args.record_decision} ({args.status})")
        if args.related_docs:
            for doc in args.related_docs:
                print(f"  ↳ {doc}")
        return

    # Record mode
    if args.record is not None:
        doc_paths: list[str] | None = args.record if args.record else None
        recorded: list[str] = record_hashes(protocol_dir, doc_paths)
        if recorded:
            print(f"Recorded hashes for {len(recorded)} document(s):")
            for doc in recorded:
                print(f"  ✓ {doc}")
        else:
            print("No documents to record (all empty or missing).")
        return

    # Check mode
    report: PacketStatusReport = check_packet_status(protocol_dir)
    dreport: DecisionReport = check_decision_triggers(protocol_dir)

    # Next-action mode: show only the recommendation
    if args.next:
        action: NextAction | None = next_action(report)
        if args.json:
            print(json.dumps(action, indent=2))
        elif args.agent:
            if action is not None:
                print(f"**{action['document']}** — {action['reason']}")
                if action["process"]:
                    print(f"Run process: `{action['process']}`")
            else:
                print("All documents are current. Assess quality in dependency order:")
                for doc in WALK_ORDER:
                    print(f"- {doc}")
        else:
            if action is not None:
                print(f"Next: {action['document']} ({action['status']})")
                if action["process"]:
                    print(f"Process: {action['process']}")
                print(f"Reason: {action['reason']}")
            else:
                print("All documents are current.")
                print("Assess quality in dependency order:")
                for doc in WALK_ORDER:
                    print(f"  {doc}")
        return

    if args.json:
        phases: list[ProcessPhase] = check_process_availability(report)
        combined: dict[str, object] = {
            **report, "decisions": dreport,
            "processAvailability": phases,
        }
        print(json.dumps(combined, indent=2))
    elif args.agent:
        output: str = format_for_agent(report)
        decision_output: str = format_decisions_for_agent(dreport)
        if decision_output:
            output += "\n" + decision_output
        print(output)
    else:
        output = format_report(report, verbose=args.verbose)
        decision_output = format_decision_report(dreport, verbose=args.verbose)
        if decision_output:
            output += "\n" + decision_output
        print(output)

    if report["summary"]["stale"] or dreport["reconsideration"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
