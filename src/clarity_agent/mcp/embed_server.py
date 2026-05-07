"""Clarity Agent MCP Server — Embed mode.

A consolidated MCP server with 8 tools that provides the full Clarity
experience with a minimal tool surface. Designed for use when Clarity
runs alongside another agent as an MCP server.

Tools:
    run_clarity             — Assess project state; auto-initializes protocol.
    check_decision          — Pre-change conflict check.
    record_decision         — Record architectural/design decisions.
    get_packet_status       — Check document staleness after implementation.
    read_protocol_document  — Read any protocol document.
    write_protocol_document — Write protocol documents (auto-records hash).
    record_failure          — Record failure modes during brainstorming.
    record_suggestion       — Record suggestions for document updates.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

SNIPPET_VERSION = 3
SLUG_MAX_LENGTH = 40

mcp_embed = FastMCP(
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
    """Resolve the clarity-agent installation directory."""
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
# Tool 1: run_clarity
# ===================================================================

@mcp_embed.tool()
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
        from clarity_agent.protocol.initialize import init_protocol as _init
        _init(_resolve_project_dir(project_dir))

        agent_dir = _resolve_agent_dir()
        guide_path = agent_dir / "processes" / "clarity-agent.md"
        guide = guide_path.read_text(encoding="utf-8") if guide_path.exists() else ""
        return (
            "# New Project — Protocol Initialized\n\n"
            "Created `.clarity-protocol/` directory.\n\n"
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
            status_text += f"\n\nProcess: {action['process']}"

    return status_text


# ===================================================================
# Tool 2: check_decision
# ===================================================================

@mcp_embed.tool()
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


# ===================================================================
# Tool 3: record_decision
# ===================================================================

@mcp_embed.tool()
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
# Tool 4: get_packet_status
# ===================================================================

@mcp_embed.tool()
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


# ===================================================================
# Tool 5: read_protocol_document
# ===================================================================

@mcp_embed.tool()
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


# ===================================================================
# Tool 6: write_protocol_document
# ===================================================================

@mcp_embed.tool()
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


# ===================================================================
# Tool 7: record_failure
# ===================================================================

@mcp_embed.tool()
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


# ===================================================================
# Tool 8: record_suggestion
# ===================================================================

@mcp_embed.tool()
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
# MCP RESOURCES
# ===================================================================

@mcp_embed.resource("clarity://summary")
def project_summary() -> str:
    """Read the project summary from .clarity-protocol/summary.md."""
    proto_dir = _resolve_protocol_dir()
    summary_path = proto_dir / "summary.md"
    if not summary_path.exists():
        return "No project summary found."
    return summary_path.read_text(encoding="utf-8")


@mcp_embed.resource("clarity://decisions")
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