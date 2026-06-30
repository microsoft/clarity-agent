"""Clarity Agent MCP Server.

Exposes the clarity-agent process as MCP tools and resources using the
FastMCP framework. The tool surface is intentionally small: a coding
agent needs only a focused set of tools to integrate clarity into its
workflow. Internal helper functions (process guide access and mailbox
management) remain available as plain functions for the desktop/web/CLI
modes but are not exposed as MCP tools.

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
from datetime import UTC, datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DEFAULT_SSE_PORT = 8421

mcp = FastMCP(
    "clarity-agent",
    instructions=(
        "Clarity Agent provides structured thinking about what you're "
        "building, why, and what could go wrong. "
        "IMPORTANT: Before making architectural decisions (new services, "
        "auth/trust models, data schemas, external integrations, "
        "significant API contracts), call check_decision with a "
        "description of what you plan to do. "
        "Call run_clarity when starting work on a project or returning "
        "after a break. "
        "After completing significant implementation, call "
        "get_packet_status to check if protocol documents need updating. "
        "Call generate_packet when the user needs a shareable review packet."
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

    pkg_data = Path(__file__).resolve().parent.parent / "_data"
    if (pkg_data / "processes").is_dir():
        return pkg_data

    env = os.environ.get("CLARITY_AGENT_DIR")
    if env:
        return Path(env).resolve()

    return candidate


# ===================================================================
# MCP TOOLS (9 tools — the coding agent surface)
# ===================================================================


@mcp.tool()
def run_clarity(project_dir: str | None = None) -> str:
    """Assess project state and recommend what to work on next.

    This is the main entry point. Call this when starting work on a project,
    returning after a break, or when unsure what to do next. It checks whether
    a clarity protocol exists, evaluates document staleness, and returns a
    structured assessment with the recommended next process to follow.

    Auto-initializes the protocol if it doesn't exist yet.
    """
    proto_dir = _resolve_protocol_dir(project_dir)

    if not proto_dir.exists():
        agent_dir = _resolve_agent_dir()
        guide_path = agent_dir / "processes" / "clarity-agent.md"
        guide = guide_path.read_text(encoding="utf-8") if guide_path.exists() else ""
        return (
            "# New Project\n\n"
            "No clarity protocol found. This is a new project.\n\n"
            "Follow the clarity-agent process guide below to get started.\n\n"
            "---\n\n" + guide
        )

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

    status_text = format_for_agent(report)

    if dreport.get("triggers"):
        status_text += "\n\n## Triggered Decisions\n\n"
        for t in dreport["triggers"]:
            docs = ", ".join(t["changed_docs"])
            status_text += f"- **{t['decision']}**: grounding documents changed ({docs})\n"

    if phases:
        status_text += "\n\n## Process Availability\n\n"
        for p in phases:
            status_text += f"- **{p['process']}**: {p['status']}"
            if p.get("reason"):
                status_text += f" — {p['reason']}"
            status_text += "\n"

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
            agent_dir = _resolve_agent_dir()
            guide_path = agent_dir / "processes" / f"{action['process']}.md"
            if guide_path.exists():
                guide_content = guide_path.read_text(encoding="utf-8")
                status_text += (
                    f"\n\n---\n\n"
                    f"## Process Guide: {action['process']}\n\n"
                    f"{guide_content}"
                )
            else:
                status_text += (
                    f"\n\nProcess: {action['process']}"
                )

    return status_text


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
        return "No protocol directory found. No existing decisions to check against."

    sections: list[str] = []

    decisions_dir = proto_dir / "decisions"
    if decisions_dir.exists():
        decision_files = sorted(decisions_dir.glob("decision-*.md"))
        if decision_files:
            sections.append("## Existing Decisions\n")
            for df in decision_files:
                content = df.read_text(encoding="utf-8")
                sections.append(f"### {df.stem}\n\n{content}\n")

    req_path = proto_dir / "goal" / "requirements.md"
    if req_path.exists():
        from clarity_agent.protocol.packet_status import is_template
        if not is_template(req_path):
            content = req_path.read_text(encoding="utf-8")
            sections.append(f"## Current Requirements\n\n{content}\n")

    arch_path = proto_dir / "solution" / "architecture.md"
    if arch_path.exists():
        from clarity_agent.protocol.packet_status import is_template
        if not is_template(arch_path):
            content = arch_path.read_text(encoding="utf-8")
            sections.append(f"## Current Architecture\n\n{content}\n")

    if not sections:
        return (
            "No decisions, requirements, or architecture documents found. "
            "Proceed, but consider recording this as a decision with "
            "record_decision if it is significant."
        )

    header = (
        f"## Proposed Change\n\n{description}\n\n"
        "Review the following existing context for conflicts "
        "before proceeding.\n\n"
    )
    return header + "\n".join(sections)


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
def read_protocol_document(
    document_path: str,
    project_dir: str | None = None,
) -> str:
    """Read a document from the project's .clarity-protocol/ directory.

    Use forward slashes for nested paths (e.g., 'goal/problem.md').
    """
    proto_dir = _resolve_protocol_dir(project_dir)
    file_path = (proto_dir / document_path).resolve()

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
    """Write or update a document in the project's .clarity-protocol/ directory.

    Automatically records the content hash so the staleness tracker
    knows the document is current.
    """
    proto_dir = _resolve_protocol_dir(project_dir)
    file_path = (proto_dir / document_path).resolve()

    if not str(file_path).startswith(str(proto_dir.resolve())):
        return "Error: path traversal not allowed."

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    try:
        from clarity_agent.protocol.packet_status import record_hashes
        record_hashes(proto_dir, [document_path])
    except Exception:
        pass

    return f"Written: {document_path}"


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
    from clarity_agent.protocol.packet_status import (
        write_decision_file,
    )

    proto_dir = _resolve_protocol_dir(project_dir)

    content_parts: list[str] = [
        f"# Decision: {title}\n",
        "**Status:** decided\n",
        f"**Date:** {datetime.now(UTC).strftime('%Y-%m-%d')}\n",
        f"\n## Context\n\n{context}\n",
        f"\n## Decision\n\n{decision}\n",
        f"\n## Rationale\n\n{rationale}\n",
    ]
    if alternatives:
        content_parts.append(f"\n## Alternatives Considered\n\n{alternatives}\n")
    if consequences:
        content_parts.append(f"\n## Consequences\n\n{consequences}\n")

    content = "\n".join(content_parts)

    filename, _ = write_decision_file(proto_dir, title, content)

    # Extract the number prefix for config.json tracking.
    import re
    match = re.search(r"decision-(\d+)", filename)
    decision_id = match.group(1) if match else "01"

    try:
        _record_decision(
            proto_dir,
            decision_id=decision_id,
            status="decided",
        )
    except Exception as exc:
        return f"Recorded decision: {title} → decisions/{filename} (warning: status tracking failed: {exc})"

    return f"Recorded decision: {title} → decisions/{filename}"


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
def generate_packet(
    output_format: str = "markdown",
    view: str = "complete",
    project_dir: str | None = None,
) -> str:
    """Generate a review packet document from protocol content.

    Use this when the user wants a shareable packet from the current
    protocol. Markdown output is returned directly. Binary formats such
    as docx are generated to confirm availability, but MCP returns only
    a status message because text tools cannot return binary files.

    Args:
        output_format: Packet renderer to use, such as "markdown" or "docx".
        view: Packet view ID, such as "complete", "short", or "engineer".
        project_dir: Project directory (default: CLARITY_PROJECT_DIR or cwd).
    """
    from clarity_agent.packet import PacketError
    from clarity_agent.packet import generate_packet as _generate

    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return "No protocol directory found."

    selected_view = view.strip() or "complete"
    try:
        content: bytes = _generate(
            proto_dir,
            format=output_format,
            view=selected_view,
        )
    except PacketError as exc:
        return f"Error generating packet: {exc}"

    if output_format == "markdown":
        return content.decode("utf-8")
    return (
        f"Generated {output_format} packet ({len(content)} bytes). "
        "Use the web UI or CLI to download binary formats."
    )


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


# ===================================================================
# INTERNAL FUNCTIONS (not exposed as MCP tools)
#
# These remain importable for desktop/web/CLI modes and for tests,
# but coding agents don't need them as separate tools.
# ===================================================================


def init_protocol(project_dir: str | None = None) -> str:
    """Initialize a .clarity-protocol/ directory for a project."""
    from clarity_agent.protocol.initialize import init_protocol as _init

    proj = _resolve_project_dir(project_dir)
    created = _init(proj)
    if created:
        return f"Initialized clarity protocol at {_resolve_protocol_dir(project_dir)}"
    return f"Protocol directory already exists at {_resolve_protocol_dir(project_dir)}"


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


def record_packet_status(
    documents: list[str] | None = None,
    project_dir: str | None = None,
) -> str:
    """Record the current content hashes for protocol documents."""
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


def get_next_action(project_dir: str | None = None) -> str:
    """Determine what clarity process should be run next."""
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


def list_processes() -> str:
    """List all available clarity-agent processes."""
    from clarity_agent.process_registry import PROCESS_METADATA

    lines: list[str] = []
    for meta in PROCESS_METADATA.values():
        lines.append(
            f"- **{meta.display_name}** (`{meta.name}`): "
            f"{meta.one_liner} [{meta.category}]"
        )
    return "\n".join(lines)


def read_process_guide(process_name: str) -> str:
    """Read the full markdown guide for a specific clarity-agent process."""
    agent_dir = _resolve_agent_dir()
    guide_path = agent_dir / "processes" / f"{process_name}.md"
    if not guide_path.exists():
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


def list_thinkers() -> str:
    """List all available specialist thinkers for failure brainstorming."""
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


def read_thinker_guide(thinker_name: str) -> str:
    """Read the full methodology guide for a specialist thinker."""
    from clarity_agent.ai_actions.brainstorm import (
        read_thinker_guide as _read,
    )

    agent_dir = _resolve_agent_dir()
    return _read(agent_dir, thinker_name)


def read_behaviors(project_dir: str | None = None) -> str:
    """Read the cross-cutting behavioral guidelines from the project's
    ``AGENTS.md`` — specifically the Clarity-managed block between
    the ``<!-- clarity-begin -->`` / ``<!-- clarity-end -->`` markers.

    Same source the in-process Clarity LLM reads (see
    :meth:`ClaritySession.load_behaviors`).  Before reading, we run
    the shared :func:`~clarity_agent.setup.snippet.ensure_for_project`
    helper so a host agent that's only ever touched Clarity through
    MCP (never opened ``clarity-web``) still sees current content.
    The helper is idempotent — no write when nothing's drifted — so
    the cost is one file read + comparison in the common case.
    """
    from clarity_agent.setup.snippet import _extract_block, ensure_for_project

    resolved_project = _resolve_project_dir(project_dir)
    ensure_for_project(resolved_project, _resolve_agent_dir())

    agents_md = resolved_project / "AGENTS.md"
    if not agents_md.exists():
        return (
            "AGENTS.md not found in this project. Open the project in "
            "Clarity (or run `clarity install --embedded` for a git "
            "repo) to create it."
        )
    block = _extract_block(agents_md.read_text(encoding="utf-8"))
    if block is None:
        return (
            "AGENTS.md exists but has no Clarity block (no "
            "<!-- clarity-begin --> / <!-- clarity-end --> markers). "
            "Re-open the project in Clarity to refresh it."
        )
    return block


def get_mailbox_status(project_dir: str | None = None) -> str:
    """Check the status of async operation mailboxes."""
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


def check_failure_state(project_dir: str | None = None) -> str:
    """Check the current state of failure analysis."""
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


def snapshot_mailbox(
    name: str,
    project_dir: str | None = None,
) -> str:
    """Freeze a mailbox by moving all items into a timestamped archive snapshot."""
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


def list_mailbox_items(
    name: str,
    project_dir: str | None = None,
) -> str:
    """List all item filenames in a mailbox."""
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


def read_mailbox_item(
    name: str,
    filename: str,
    project_dir: str | None = None,
) -> str:
    """Read the content of a single mailbox item."""
    from clarity_agent.protocol.mailbox import Mailbox

    proto_dir = _resolve_protocol_dir(project_dir)
    if not proto_dir.exists():
        return "No protocol directory found. Run init_protocol first."

    mailbox = Mailbox(proto_dir, name)

    item_path = mailbox.mailbox_dir / filename
    if item_path.is_file():
        return item_path.read_text(encoding="utf-8")

    if mailbox.archive_dir.exists():
        for snapshot in sorted(mailbox.archive_dir.iterdir(), reverse=True):
            if snapshot.is_dir():
                candidate = snapshot / filename
                if candidate.is_file():
                    return candidate.read_text(encoding="utf-8")

    return f"Item '{filename}' not found in mailbox '{name}' or its archive."


def archive_mailbox_item(
    name: str,
    filename: str,
    project_dir: str | None = None,
) -> str:
    """Move a single item from the active mailbox to the archive."""
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


@mcp.resource("clarity://decisions")
def decisions_resource() -> str:
    """Read all project decision records concatenated into one document."""
    proto_dir = _resolve_protocol_dir()
    decisions_dir = proto_dir / "decisions"
    if not decisions_dir.exists():
        return "No decisions directory found."

    parts: list[str] = []
    for df in sorted(decisions_dir.glob("decision-*.md")):
        parts.append(df.read_text(encoding="utf-8"))

    if not parts:
        return "No decision records found."
    return "\n\n---\n\n".join(parts)


@mcp.resource("clarity://behaviors")
def behaviors_resource() -> str:
    """Read the cross-cutting behavioral guidelines.

    Thin wrapper around :func:`read_behaviors` — delegates to the
    project-AGENTS.md path so the resource URI returns the same
    content the host coding agent and Clarity's own LLM both see.
    Uses the default project resolution (``CLARITY_PROJECT_DIR`` env
    var or cwd); callers that need a specific project should invoke
    :func:`read_behaviors` directly with an explicit ``project_dir``.
    """
    return read_behaviors()


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


@mcp.resource("clarity://protocol/{path}")
def protocol_document_resource(path: str) -> str:
    """Read any protocol document by path.

    Use forward slashes for nested paths (e.g., 'goal/problem.md').
    """
    proto_dir = _resolve_protocol_dir()
    file_path = (proto_dir / path).resolve()
    if not str(file_path).startswith(str(proto_dir.resolve())):
        return "Error: path traversal not allowed."
    if not file_path.exists():
        return f"Document not found: {path}"
    return file_path.read_text(encoding="utf-8")
