"""Clarity Agent MCP Server — Embed (lite) mode.

Exposes only the essential tools for embedded use where Clarity
runs alongside another agent. Keeps the tool list small so the
host LLM pays attention to each tool.

Tools: run_clarity, check_decision, dismiss_check, get_packet_status,
       record_decision, init_protocol, read_protocol_document,
       write_protocol_document, record_packet_status.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from clarity_agent.mcp.server import (
    SNIPPET_VERSION,
    _resolve_project_dir,
    _resolve_protocol_dir,
    check_decision as _check_decision,
    check_snippet_version as _check_snippet_version,
    dismiss_check as _dismiss_check,
    get_packet_status as _get_packet_status,
    init_protocol as _init_protocol,
    read_protocol_document as _read_protocol_document,
    record_decision as _record_decision,
    record_packet_status as _record_packet_status,
    run_clarity as _run_clarity,
    write_protocol_document as _write_protocol_document,
)

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


@mcp_embed.tool()
def run_clarity(project_dir: str | None = None) -> str:
    """Assess project state and recommend what to work on next.

    This is the main entry point. Call this when starting work on a project,
    returning after a break, or when unsure what to do next. It checks whether
    a clarity protocol exists, evaluates document staleness, and returns a
    structured assessment with the recommended next process to follow.
    """
    return _run_clarity(project_dir)


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
    return _check_decision(description, project_dir)


@mcp_embed.tool()
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
    return _dismiss_check(reason, project_dir)


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
    return _get_packet_status(project_dir, output_format)


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
    return _record_decision(title, context, decision, rationale, alternatives, consequences, project_dir)


@mcp_embed.tool()
def init_protocol(project_dir: str | None = None) -> str:
    """Initialize a .clarity-protocol/ directory for a project.

    Call this at the start of a new project before any protocol work.
    Creates directory structure, config.json, and template files.
    Safe to run on partially-initialized projects.
    """
    return _init_protocol(project_dir)


@mcp_embed.tool()
def read_protocol_document(
    document_path: str,
    project_dir: str | None = None,
) -> str:
    """Read a document from the project's .clarity-protocol/ directory.

    Use list_protocol_documents to see available files.
    """
    return _read_protocol_document(document_path, project_dir)


@mcp_embed.tool()
def write_protocol_document(
    document_path: str,
    content: str,
    project_dir: str | None = None,
) -> str:
    """Write or update a document in the project's .clarity-protocol/ directory."""
    return _write_protocol_document(document_path, content, project_dir)


@mcp_embed.tool()
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
    return _record_packet_status(documents, project_dir)


@mcp_embed.tool()
def check_snippet_version(project_dir: str | None = None) -> str:
    """Check if the Clarity snippet in the project's AGENTS.md is up to date.

    Compares the embedded snippet version against the current template version.
    Call this periodically to ensure the project has the latest intervention
    instructions.

    Args:
        project_dir: Project directory (default: CLARITY_PROJECT_DIR or cwd).
    """
    return _check_snippet_version(project_dir)


# Resources — keep only the essential ones
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