"""Clarity Agent MCP Server.

Exposes the complete clarity-agent process as MCP tools and resources
using the FastMCP framework.  Tools are thin wrappers around existing
Python infrastructure in ``clarity_agent.protocol``, ``clarity_agent.packet``,
and ``clarity_agent.ai_actions``.

Run via::

    python -m clarity_agent.mcp [--project-dir DIR]

Or configure in an MCP client's ``.mcp.json``::

    {
      "mcpServers": {
        "clarity-agent": {
          "command": "python",
          "args": ["-m", "clarity_agent.mcp"],
          "env": {"CLARITY_PROJECT_DIR": "/path/to/project"}
        }
      }
    }
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

SLUG_MAX_LENGTH = 40
DEFAULT_SSE_PORT = 8421

SNIPPET_VERSION = 3

mcp = FastMCP(
    "clarity-agent",
    instructions=(
        "Clarity Agent provides structured thinking about what you're building, "
        "why, and what could go wrong. "
        "IMPORTANT: Before making architectural decisions (new services, auth/trust "
        "models, data schemas, external integrations, significant API contracts), "
        "call check_decision with a description of what you plan to do. "
        "Call run_clarity when starting work on a project or returning after a break. "
        "After completing significant implementation, call get_packet_status to check "
        "if protocol documents need updating."
    ),
)

# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------


def _resolve_project_dir(project_dir: str | None = None) -> Path:
    """Resolve the project directory from argument, env var, or cwd."""
    if project_dir:
        return Path(project_dir).resolve()
    env = os.environ.get("CLARITY_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    return Path.cwd()


def _resolve_protocol_dir(project_dir: str | None = None) -> Path:
    """Resolve the protocol directory for a project."""
    from clarity_agent.app_paths import protocol_dir
    return protocol_dir(_resolve_project_dir(project_dir))


def _resolve_agent_dir() -> Path:
    """Resolve the clarity-agent installation directory.

    Works in both development (repo checkout) and installed (pip/uv)
    contexts by checking for the ``processes/`` marker directory.
    Falls back to the package location if the repo root doesn't
    contain the expected directories.
    """
    from clarity_agent.app_paths import get_bundle_dir
    candidate = get_bundle_dir()
    if (candidate / "processes").is_dir():
        return candidate

    # Installed via pip: processes/ and thinkers/ are bundled as
    # package data under clarity_agent/_data/
    pkg_data = Path(__file__).resolve().parent.parent / "_data"
    if (pkg_data / "processes").is_dir():
        return pkg_data

    # Last resort: check if CLARITY_AGENT_DIR env var is set
    env = os.environ.get("CLARITY_AGENT_DIR")
    if env:
        return Path(env).resolve()

    return candidate


# ===================================================================
# TOP-LEVEL SKILL
# ===================================================================


@mcp.tool()
def run_clarity(project_dir: str | None = None) -> str:
    """Assess project state and recommend what to work on next.

    This is the main entry point. Call this when starting work on a project,
    returning after a break, or when unsure what to do next. It checks whether
    a clarity protocol exists, evaluates document staleness, and returns a
    structured assessment with the recommended next process to follow.
    """
    proto_dir = _resolve_protocol_dir(project_dir)

    if not proto_dir.exists():
        # New project — return the clarity-agent guide
        agent_dir = _resolve_agent_dir()
        guide_path = agent_dir / "processes" / "clarity-agent.md"
        guide = guide_path.read_text(encoding="utf-8") if guide_path.exists() else ""
        return (
            "# New Project\n\n"
            "No clarity protocol found.  This is a new project.\n\n"
            "Follow the clarity-agent process guide below to get started.\n\n"
            "---\n\n" + guide
        )

    # Existing project — run packet status
    from clarity_agent.protocol.packet_status import (
        check_decision_triggers,
        check_packet_status,
        check_process_availability,
        format_for_agent,
        next_action,
    )

    report = check_packet_status(proto_dir)
    action = next_action(report)
    phases = check_process_availability(report)
    dreport = check_decision_triggers(proto_dir)

    # Format the status report
    status_text = format_for_agent(report)

    # Add decision info if there are triggers
    if dreport.get("triggers"):
        status_text += "\n\n## Triggered Decisions\n\n"
        for t in dreport["triggers"]:
            docs = ", ".join(t["changed_docs"])
            status_text += f"- **{t['decision']}**: grounding documents changed ({docs})\n"

    # Add process availability
    if phases:
        status_text += "\n\n## Process Availability\n\n"
        for p in phases:
            status_text += f"- **{p['process']}**: {p['status']}"
            if p.get("reason"):
                status_text += f" — {p['reason']}"
            status_text += "\n"

    # Read notes.md if it exists
    notes_path = proto_dir / "notes.md"
    if notes_path.exists():
        notes_content = notes_path.read_text(encoding="utf-8").strip()
        if notes_content:
            status_text += f"\n\n## Notes\n\n{notes_content}"

    if action:
        status_text += (
            f"\n\n## Recommended Next Step\n\n"
            f"**{action.get('document', 'unknown')}**"
        )
        if action.get("reason"):
            status_text += f": {action['reason']}"
        if action.get("process"):
            status_text += (
                f"\n\nUse `read_process_guide` with process_name="
                f'"{action["process"]}" to get the full process guide.'
            )

    return status_text


# ===================================================================
# SUPPORT TOOLS — Protocol I/O
# ===================================================================


@mcp.tool()
def init_protocol(project_dir: str | None = None) -> str:
    """Initialize a .clarity-protocol/ directory for a project.

    Call this at the start of a new project before any protocol work.
    Creates directory structure, config.json, and template files.
    Safe to run on partially-initialized projects.
    """
    from clarity_agent.protocol.initialize import init_protocol as _init

    proj = _resolve_project_dir(project_dir)
    created = _init(proj)
    if created:
        return f"Initialized clarity protocol at {_resolve_protocol_dir(project_dir)}"
    return f"Protocol directory already exists at {_resolve_protocol_dir(project_dir)}"


@mcp.tool()
def list_protocol_documents(project_dir: str | None = None) -> str:
    """List all files in the project's .clarity-protocol/ directory tree."""
    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return "No protocol directory found."

    files: list[str] = []
    for root, dirs, filenames in os.walk(proto_dir):
        dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]
        rel_root = Path(root).relative_to(proto_dir)
        for f in sorted(filenames):
            if f.startswith("."):
                continue
            rel_path = str(rel_root / f) if str(rel_root) != "." else f
            files.append(rel_path)

    if not files:
        return "Protocol directory exists but is empty."
    return "\n".join(files)


@mcp.tool()
def read_protocol_document(
    document_path: str,
    project_dir: str | None = None,
) -> str:
    """Read a document from the project's .clarity-protocol/ directory.

    Use list_protocol_documents to see available files.
    """
    proto_dir = _resolve_protocol_dir(project_dir)
    file_path = (proto_dir / document_path).resolve()

    # Path traversal protection
    if not str(file_path).startswith(str(proto_dir.resolve())):
        return "Error: path traversal not allowed."
    if not file_path.exists():
        return f"Error: document not found: {document_path}"

    return file_path.read_text(encoding="utf-8")


@mcp.tool()
def write_protocol_document(
    document_path: str,
    content: str,
    project_dir: str | None = None,
) -> str:
    """Write or update a document in the project's .clarity-protocol/ directory."""
    proto_dir = _resolve_protocol_dir(project_dir)
    file_path = (proto_dir / document_path).resolve()

    if not str(file_path).startswith(str(proto_dir.resolve())):
        return "Error: path traversal not allowed."

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return f"Written: {document_path}"


# ===================================================================
# SUPPORT TOOLS — Status & Navigation
# ===================================================================


@mcp.tool()
def get_packet_status(
    project_dir: str | None = None,
    output_format: str = "agent",
) -> str:
    """Check the status of all protocol documents: staleness, dependencies,
    what needs updating.

    Call this after completing significant implementation work (new features,
    architectural changes) to see if protocol documents need updating.
    Returns a structured report showing which documents are current,
    stale, empty, or untracked.
    """
    from clarity_agent.protocol.packet_status import (
        check_packet_status as _check,
    )
    from clarity_agent.protocol.packet_status import (
        format_for_agent,
        format_report,
    )

    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return "No protocol directory found."

    report = _check(proto_dir)
    if output_format == "human":
        return format_report(report, verbose=True)
    elif output_format == "json":
        return json.dumps(report, indent=2, default=str)
    else:
        return format_for_agent(report)


@mcp.tool()
def record_packet_status(
    documents: list[str] | None = None,
    project_dir: str | None = None,
) -> str:
    """Record the current content hashes for protocol documents.

    Call this after writing or updating protocol documents so the
    staleness tracker knows they are current. If no documents are
    specified, records all tracked documents that have real content.

    Args:
        documents: List of document paths relative to .clarity-protocol/
                   (e.g. ["goal/problem.md", "goal/stakeholders.md"]).
                   If omitted, records all documents with content.
        project_dir: Project directory (default: CLARITY_PROJECT_DIR or cwd).
    """
    from clarity_agent.protocol.packet_status import record_hashes

    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return "No protocol directory found. Run init_protocol first."

    try:
        recorded = record_hashes(proto_dir, documents)
    except (json.JSONDecodeError, OSError) as exc:
        return f"Error recording packet status: {exc}"

    if not recorded:
        return "No documents to record (all empty or untracked)."
    _MAX_LISTED = 5
    if len(recorded) <= _MAX_LISTED:
        names = ", ".join(recorded)
    else:
        names = ", ".join(recorded[:_MAX_LISTED]) + f" + {len(recorded) - _MAX_LISTED} more"
    return f"Recorded baselines for {len(recorded)} document(s): {names}"


@mcp.tool()
def get_next_action(project_dir: str | None = None) -> str:
    """Determine what clarity process should be run next based on the
    current state of the protocol documents.

    Returns the recommended next step with rationale.
    """
    from clarity_agent.protocol.packet_status import (
        check_packet_status as _check,
    )
    from clarity_agent.protocol.packet_status import (
        next_action as _next,
    )

    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return "No protocol directory found. Run init_protocol first."

    report = _check(proto_dir)
    action = _next(report)
    if action is None:
        return "All documents are current. No immediate action needed."

    result = f"**{action.get('document', 'unknown')}**"
    if action.get("reason"):
        result += f"\n\n{action['reason']}"
    if action.get("process"):
        result += f"\n\nProcess: {action['process']}"
    return result


# ===================================================================
# SUPPORT TOOLS — Recording
# ===================================================================


@mcp.tool()
def record_failure(
    title: str,
    description: str,
    additional_context: str = "",
    pre_existing: bool | None = None,
    project_dir: str | None = None,
) -> str:
    """Record a potential failure mode during brainstorming.

    Call this during failure brainstorming sessions when you identify
    a way the system could fail. Writes to the failure-brainstorm
    mailbox in the protocol directory.
    """
    from clarity_agent.ai_actions.brainstorm import record_failure as _record

    proto_dir = _resolve_protocol_dir(project_dir)
    _, msg = _record(
        proto_dir,
        title=title,
        description=description,
        source="mcp",
        additional_context=additional_context,
        pre_existing=pre_existing,
    )
    return msg


@mcp.tool()
def record_suggestion(
    title: str,
    target_document: str,
    suggestion: str,
    rationale: str = "",
    project_dir: str | None = None,
) -> str:
    """Record a suggestion to update a project document.

    Writes to the suggestions mailbox so the suggestion can be
    reviewed and applied later.
    """
    from clarity_agent.ai_actions.suggestion import (
        record_suggestion as _record,
    )

    proto_dir = _resolve_protocol_dir(project_dir)
    _, msg = _record(
        proto_dir,
        title=title,
        target_document=target_document,
        suggestion=suggestion,
        source="mcp",
        rationale=rationale,
    )
    return msg


@mcp.tool()
def record_decision(
    title: str,
    context: str,
    decision: str,
    rationale: str,
    alternatives: str = "",
    consequences: str = "",
    project_dir: str | None = None,
) -> str:
    """Record a project decision with structured analysis.

    Call this after making a significant architectural or design choice
    to create a permanent record. Creates a decision document in the
    protocol's decisions/ directory.
    """
    from clarity_agent.protocol.packet_status import (
        record_decision as _record_decision,
    )

    proto_dir = _resolve_protocol_dir(project_dir)

    content_parts: list[str] = [
        f"# Decision: {title}\n",
        "**Status:** decided\n",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n",
        f"\n## Context\n\n{context}\n",
        f"\n## Decision\n\n{decision}\n",
        f"\n## Rationale\n\n{rationale}\n",
    ]
    if alternatives:
        content_parts.append(f"\n## Alternatives Considered\n\n{alternatives}\n")
    if consequences:
        content_parts.append(f"\n## Consequences\n\n{consequences}\n")

    content = "\n".join(content_parts)

    decisions_dir = proto_dir / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(decisions_dir.glob("decision-*.md"))
    next_num = 1
    if existing:
        match = re.search(r"decision-(\d+)", existing[-1].name)
        if match:
            next_num = int(match.group(1)) + 1

    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:SLUG_MAX_LENGTH]
    filename = f"decision-{next_num:02d}-{slug}.md"
    file_path = decisions_dir / filename
    file_path.write_text(content, encoding="utf-8")

    try:
        _record_decision(
            proto_dir,
            decision_id=f"{next_num:02d}",
            status="decided",
        )
    except Exception as exc:
        return f"Recorded decision: {title} → decisions/{filename} (warning: status tracking failed: {exc})"

    return f"Recorded decision: {title} → decisions/{filename}"


# ===================================================================
# SUPPORT TOOLS — Process & Thinker Access
# ===================================================================


@mcp.tool()
def list_processes() -> str:
    """List all available clarity-agent processes with their descriptions,
    tiers, and categories.
    """
    from clarity_agent.process_registry import PROCESS_METADATA

    lines: list[str] = []
    for meta in PROCESS_METADATA.values():
        lines.append(
            f"- **{meta.display_name}** (`{meta.name}`): "
            f"{meta.one_liner} [{meta.category}]"
        )
    return "\n".join(lines)


@mcp.tool()
def read_process_guide(process_name: str) -> str:
    """Read the full markdown guide for a specific clarity-agent process.

    This contains the step-by-step instructions the AI follows when
    running the process.
    """
    agent_dir = _resolve_agent_dir()
    guide_path = agent_dir / "processes" / f"{process_name}.md"
    if not guide_path.exists():
        # Check without .md extension
        if not process_name.endswith(".md"):
            guide_path = agent_dir / "processes" / process_name
        if not guide_path.exists():
            available = [
                p.stem for p in (agent_dir / "processes").glob("*.md")
                if p.stem != "README"
            ]
            return (
                f"Error: process guide not found: {process_name}\n"
                f"Available: {', '.join(sorted(available))}"
            )
    return guide_path.read_text(encoding="utf-8")


@mcp.tool()
def list_thinkers() -> str:
    """List all available specialist thinkers for failure brainstorming.

    Each thinker brings a specific analytical perspective (security,
    human factors, adversarial, etc.).
    """
    from clarity_agent.protocol.thinker_registry import discover_thinkers

    agent_dir = _resolve_agent_dir()
    thinkers_dir = agent_dir / "thinkers"
    if not thinkers_dir.exists():
        return "No thinkers directory found."

    thinkers = discover_thinkers(agent_dir)
    lines: list[str] = []
    for t in thinkers:
        lines.append(f"- **{t.display_name}** (`{t.name}`): {t.description}")
    return "\n".join(lines) if lines else "No thinkers found."


@mcp.tool()
def read_thinker_guide(thinker_name: str) -> str:
    """Read the full methodology guide for a specialist thinker.

    Use this to apply their analytical framework when brainstorming
    failures.
    """
    from clarity_agent.ai_actions.brainstorm import (
        read_thinker_guide as _read,
    )

    agent_dir = _resolve_agent_dir()
    return _read(agent_dir, thinker_name)


@mcp.tool()
def read_behaviors() -> str:
    """Read the cross-cutting behavioral guidelines from AGENTS.md.

    These apply to all clarity processes.
    """
    agent_dir = _resolve_agent_dir()
    agents_path = agent_dir / "AGENTS.md"
    if not agents_path.exists():
        return "AGENTS.md not found."
    return agents_path.read_text(encoding="utf-8")


# ===================================================================
# SUPPORT TOOLS — Output
# ===================================================================


@mcp.tool()
def generate_packet(
    output_format: str = "markdown",
    sections: str | None = None,
    view: str | None = None,
    project_dir: str | None = None,
) -> str:
    """Generate a review packet document from protocol content.

    Assembles problem statement, solution, failures, decisions, etc.
    into a readable document for human reviewers.
    """
    from clarity_agent.packet import generate_packet as _generate

    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return "No protocol directory found."

    include = sections.split(",") if sections else None
    try:
        content: bytes = _generate(
            proto_dir,
            include=include,
            format=output_format,
            view=view,
        )
        if output_format == "markdown":
            return content.decode("utf-8")
        else:
            return f"Generated {output_format} packet ({len(content)} bytes). Use the web UI or CLI to download binary formats."
    except Exception as e:
        return f"Error generating packet: {e}"


@mcp.tool()
def get_mailbox_status(project_dir: str | None = None) -> str:
    """Check the status of async operation mailboxes (failure brainstorming
    results, suggestions, etc.).
    """
    from clarity_agent.protocol.packet_status import check_mailbox_status

    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return "No protocol directory found."

    mailboxes = check_mailbox_status(proto_dir)
    if not mailboxes:
        return "No active mailboxes."

    lines: list[str] = []
    for mb in mailboxes:
        name = mb.get("name", "unknown")
        count = mb.get("item_count", 0)
        status = mb.get("status", "unknown")
        lines.append(f"- **{name}**: {count} items, status: {status}")
    return "\n".join(lines)


@mcp.tool()
def check_failure_state(project_dir: str | None = None) -> str:
    """Check the current state of failure analysis: what phase the project
    is in (brainstorming, analysis, management) and what the next
    failure-related step should be.
    """
    from clarity_agent.protocol.failure_state import (
        check_failure_state as _check,
    )

    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return "No protocol directory found."

    state = _check(proto_dir)
    lines: list[str] = [
        f"**Recommended phase:** {state.recommended_phase or 'none'}",
        f"**Brainstorm in progress:** {state.brainstorm_in_progress}",
        f"**Pending analysis:** {state.pending_analysis_count} item(s)",
        f"**Unmitigated failures:** {len(state.unmitigated_failures)}",
        f"**Mitigated failures:** {len(state.mitigated_failures)}",
    ]
    if state.options:
        lines.append("\n**Available actions:**")
        for opt in state.options:
            rec = " (recommended)" if opt.recommended else ""
            lines.append(f"- `{opt.phase}`{rec}: {opt.reason}")
    return "\n".join(lines)


# ===================================================================
# SUPPORT TOOLS — Mailbox Operations
# ===================================================================


@mcp.tool()
def snapshot_mailbox(
    name: str,
    project_dir: str | None = None,
) -> str:
    """Freeze a mailbox by moving all items into a timestamped archive snapshot.

    Used at the start of failure-analysis to lock in brainstorming results.

    Args:
        name: Mailbox name (e.g. "failure-brainstorm").
        project_dir: Project directory (default: CLARITY_PROJECT_DIR or cwd).
    """
    from clarity_agent.protocol.mailbox import Mailbox, MailboxError

    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return "No protocol directory found. Run init_protocol first."

    mailbox = Mailbox(proto_dir, name)
    if not mailbox.exists:
        return f"Mailbox '{name}' does not exist."

    try:
        snapshot_path = mailbox.snapshot()
    except MailboxError as exc:
        return f"Error creating snapshot: {exc}"

    return f"Snapshot created: {snapshot_path.name}"


@mcp.tool()
def list_mailbox_items(
    name: str,
    project_dir: str | None = None,
) -> str:
    """List all item filenames in a mailbox.

    Returns one filename per line, suitable for passing to read_mailbox_item.

    Args:
        name: Mailbox name (e.g. "failure-brainstorm").
        project_dir: Project directory (default: CLARITY_PROJECT_DIR or cwd).
    """
    from clarity_agent.protocol.mailbox import Mailbox, MailboxError

    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return "No protocol directory found. Run init_protocol first."

    mailbox = Mailbox(proto_dir, name)
    if not mailbox.exists:
        return f"Mailbox '{name}' does not exist."

    try:
        items = mailbox.list_items()
    except MailboxError as exc:
        return f"Error listing items: {exc}"

    if not items:
        return f"Mailbox '{name}' is empty."
    return "\n".join(item.name for item in items)


@mcp.tool()
def read_mailbox_item(
    name: str,
    filename: str,
    project_dir: str | None = None,
) -> str:
    """Read the content of a single mailbox item.

    Also checks the archive snapshot directories if the item is not
    in the active mailbox.

    Args:
        name: Mailbox name (e.g. "failure-brainstorm").
        filename: Item filename (from list_mailbox_items).
        project_dir: Project directory (default: CLARITY_PROJECT_DIR or cwd).
    """
    from clarity_agent.protocol.mailbox import Mailbox

    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return "No protocol directory found. Run init_protocol first."

    mailbox = Mailbox(proto_dir, name)

    # Check active mailbox
    item_path = mailbox.mailbox_dir / filename
    if item_path.is_file():
        return item_path.read_text(encoding="utf-8")

    # Check archive snapshots
    if mailbox.archive_dir.exists():
        for snapshot in sorted(mailbox.archive_dir.iterdir(), reverse=True):
            if snapshot.is_dir():
                candidate = snapshot / filename
                if candidate.is_file():
                    return candidate.read_text(encoding="utf-8")

    return f"Item '{filename}' not found in mailbox '{name}' or its archive."


@mcp.tool()
def archive_mailbox_item(
    name: str,
    filename: str,
    project_dir: str | None = None,
) -> str:
    """Move a single item from the active mailbox to the archive.

    Marks the item as processed so it no longer appears in list_mailbox_items.

    Args:
        name: Mailbox name (e.g. "failure-brainstorm").
        filename: Item filename to archive.
        project_dir: Project directory (default: CLARITY_PROJECT_DIR or cwd).
    """
    from clarity_agent.protocol.mailbox import Mailbox, MailboxError

    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return "No protocol directory found. Run init_protocol first."

    mailbox = Mailbox(proto_dir, name)
    if not mailbox.exists:
        return f"Mailbox '{name}' does not exist."

    try:
        new_path = mailbox.archive_item(filename)
    except MailboxError as exc:
        return f"Error archiving item: {exc}"

    return f"Archived: {filename} → {new_path.name}"


# ===================================================================
# SUPPORT TOOLS — Decision Checking
# ===================================================================


@mcp.tool()
def check_decision(
    description: str,
    project_dir: str | None = None,
) -> str:
    """Check whether a proposed change conflicts with existing decisions or requirements.

    Call this BEFORE making choices that would be expensive to reverse:
    new services, auth/trust models, data schemas, external integrations,
    significant API contracts. Returns any relevant existing decisions and
    requirements so you can check for conflicts before proceeding.

    Args:
        description: What you plan to do or change.
        project_dir: Project directory (default: CLARITY_PROJECT_DIR or cwd).
    """
    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return json.dumps({"should_pause": False, "reason": "No protocol exists yet."})

    relevant: list[dict[str, str]] = []

    decisions_dir = proto_dir / "decisions"
    if decisions_dir.exists():
        for dec_file in sorted(decisions_dir.glob("decision-*.md")):
            content = dec_file.read_text(encoding="utf-8")
            relevant.append({
                "type": "decision",
                "file": dec_file.name,
                "preview": content[:500],
            })

    req_path = proto_dir / "goal" / "requirements.md"
    if req_path.exists():
        content = req_path.read_text(encoding="utf-8").strip()
        if content:
            relevant.append({
                "type": "requirements",
                "file": "goal/requirements.md",
                "preview": content[:500],
            })

    arch_path = proto_dir / "solution" / "architecture.md"
    if arch_path.exists():
        content = arch_path.read_text(encoding="utf-8").strip()
        if content:
            relevant.append({
                "type": "architecture",
                "file": "solution/architecture.md",
                "preview": content[:500],
            })

    return json.dumps({
        "should_pause": len(relevant) > 0,
        "reason": (
            f"Found {len(relevant)} existing document(s) to review before proceeding."
            if relevant
            else "No existing decisions, requirements, or architecture to conflict with."
        ),
        "proposed_change": description,
        "relevant_documents": relevant,
    }, indent=2)


@mcp.tool()
def dismiss_check(
    reason: str,
    project_dir: str | None = None,
) -> str:
    """Record that a decision check was reviewed and dismissed.

    Call this when check_decision surfaced documents but the user decided
    to proceed without changes. Logs the dismissal to notes.md to avoid
    re-triggering on the same topic.

    Args:
        reason: Why the check was dismissed (e.g., "no conflict found").
        project_dir: Project directory (default: CLARITY_PROJECT_DIR or cwd).
    """
    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return "No protocol directory found."

    notes_path = proto_dir / "notes.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entry = f"\n- [{timestamp}] Decision check dismissed: {reason}\n"

    existing = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
    notes_path.write_text(existing + entry, encoding="utf-8")
    return f"Recorded dismissal in notes.md: {reason}"


@mcp.tool()
def check_snippet_version(project_dir: str | None = None) -> str:
    """Check if the Clarity snippet in the project's AGENTS.md is up to date.

    Compares the embedded snippet version against the current template version.
    Call this periodically to ensure the project has the latest intervention
    instructions.

    Args:
        project_dir: Project directory (default: CLARITY_PROJECT_DIR or cwd).
    """
    proj_dir = _resolve_project_dir(project_dir)

    embedded_version = None
    for candidate_name in ("AGENTS.md", "CLAUDE.md"):
        candidate = proj_dir / candidate_name
        if candidate.exists():
            content = candidate.read_text(encoding="utf-8")
            match = re.search(r"<!--\s*clarity-version:\s*(\d+)\s*-->", content)
            if match:
                embedded_version = int(match.group(1))
                break
            if "<!-- clarity-begin -->" in content:
                embedded_version = 1
                break

    if embedded_version is None:
        return json.dumps({
            "up_to_date": False,
            "reason": "No Clarity snippet found in AGENTS.md or CLAUDE.md.",
            "current_version": SNIPPET_VERSION,
            "embedded_version": None,
        }, indent=2)

    return json.dumps({
        "up_to_date": embedded_version >= SNIPPET_VERSION,
        "current_version": SNIPPET_VERSION,
        "embedded_version": embedded_version,
        "reason": (
            "Snippet is current."
            if embedded_version >= SNIPPET_VERSION
            else f"Snippet is version {embedded_version}, current is {SNIPPET_VERSION}. "
                 "Re-run 'clarity embed' to update."
        ),
    }, indent=2)


# ===================================================================
# MCP RESOURCES
# ===================================================================


@mcp.resource("clarity://summary")
def project_summary() -> str:
    """Read the project summary from .clarity-protocol/summary.md."""
    proto_dir = _resolve_protocol_dir()
    summary_path = proto_dir / "summary.md"
    if not summary_path.exists():
        return "No project summary found."
    return summary_path.read_text(encoding="utf-8")


@mcp.resource("clarity://behaviors")
def behaviors_resource() -> str:
    """Read the cross-cutting behavioral guidelines."""
    agent_dir = _resolve_agent_dir()
    agents_path = agent_dir / "AGENTS.md"
    if not agents_path.exists():
        return "AGENTS.md not found."
    return agents_path.read_text(encoding="utf-8")


@mcp.resource("clarity://processes/{name}")
def process_guide_resource(name: str) -> str:
    """Read a process guide by name."""
    agent_dir = _resolve_agent_dir()
    guide_path = agent_dir / "processes" / f"{name}.md"
    if not guide_path.exists():
        return f"Process guide not found: {name}"
    return guide_path.read_text(encoding="utf-8")


@mcp.resource("clarity://thinkers/{name}")
def thinker_guide_resource(name: str) -> str:
    """Read a thinker guide by name."""
    agent_dir = _resolve_agent_dir()
    guide_path = agent_dir / "thinkers" / f"{name}.md"
    if not guide_path.exists():
        return f"Thinker guide not found: {name}"
    return guide_path.read_text(encoding="utf-8")


@mcp.resource("clarity://decisions")
def decisions_resource() -> str:
    """Read all project decision records concatenated into one document."""
    proto_dir = _resolve_protocol_dir()
    decisions_dir = proto_dir / "decisions"
    if not decisions_dir.exists():
        return "No decisions directory found."
    parts: list[str] = []
    for dec_file in sorted(decisions_dir.glob("decision-*.md")):
        parts.append(dec_file.read_text(encoding="utf-8"))
    if not parts:
        return "No decision records found."
    return "\n\n---\n\n".join(parts)


@mcp.resource("clarity://protocol/{path}")
def protocol_document_resource(path: str) -> str:
    """Read any protocol document by path.

    Use forward slashes for nested paths (e.g., 'goal/problem.md').
    """
    proto_dir = _resolve_protocol_dir()
    file_path = (proto_dir / path).resolve()
    # Path traversal protection
    if not str(file_path).startswith(str(proto_dir.resolve())):
        return "Error: path traversal not allowed."
    if not file_path.exists():
        return f"Document not found: {path}"
    return file_path.read_text(encoding="utf-8")
