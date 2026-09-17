"""User feedback mechanism.

Provides functions to gather context, format feedback as markdown,
and prepare a user-reviewed GitHub issue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

GITHUB_NEW_ISSUE_URL = "https://github.com/microsoft/clarity-agent/issues/new"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class FeedbackReport:
    """Assembled feedback ready to format and send."""

    message: str
    contact_ok: bool = False
    contact_email: str = ""
    llm_info: dict[str, str] = field(default_factory=dict)
    transcript_excerpt: str | None = None
    context: str | None = None
    protocol_content: str | None = None


@dataclass
class FeedbackDeliveryResult:
    """A GitHub issue draft ready for the user to review and submit."""

    issue_url: str


# ---------------------------------------------------------------------------
# Context gathering
# ---------------------------------------------------------------------------

def gather_llm_info(
    provider: str | None = None,
    model: str | None = None,
    active_model: str | None = None,
) -> dict[str, str]:
    """Gather LLM backend/model information into a display dict."""
    info: dict[str, str] = {}
    if provider:
        info["Provider"] = provider
    if model:
        info["Configured model"] = model
    if active_model:
        info["Active model"] = active_model
    return info


def gather_transcript(project_dir: Path, n_turns: int) -> str | None:
    """Read the last *n_turns* turns from the most recent transcript.

    Returns ``None`` if no transcripts exist.
    """
    from clarity_agent.app_paths import protocol_dir

    transcript_dir = protocol_dir(project_dir) / "transcripts"
    if not transcript_dir.exists():
        return None

    files = sorted(transcript_dir.glob("*.md"), reverse=True)
    if not files:
        return None

    try:
        content = files[0].read_text(encoding="utf-8")
    except OSError:
        return None

    # Split on turn boundaries (--- separators).
    turns = content.split("\n---\n")
    if n_turns and len(turns) > n_turns:
        turns = turns[-n_turns:]

    return "\n---\n".join(turns)


def gather_protocol(project_dir: Path) -> str | None:
    """Generate a complete markdown packet from the clarity protocol.

    Uses the packet builder so the output is well-structured and
    includes all protocol sections.  Returns ``None`` if the protocol
    directory does not exist.
    """
    from clarity_agent.app_paths import protocol_dir

    proto = protocol_dir(project_dir)
    if not proto.exists():
        return None

    try:
        from clarity_agent.packet import generate_packet
        packet_bytes: bytes = generate_packet(proto, format="markdown")
        return packet_bytes.decode("utf-8")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_feedback_md(report: FeedbackReport) -> str:
    """Format a :class:`FeedbackReport` as a markdown document."""
    parts: list[str] = ["# Clarity Agent Feedback\n"]

    parts.append(f"## Message\n\n{report.message}\n")

    if report.contact_ok and report.contact_email:
        parts.append(
            f"## Contact\n\n"
            f"OK to follow up: **Yes**\n"
            f"Email: {report.contact_email}\n"
        )
    elif report.contact_ok:
        parts.append(
            "## Contact\n\n"
            "OK to follow up: **Yes** (no email provided)\n"
        )
    else:
        parts.append("## Contact\n\nOK to follow up: **No**\n")

    if report.llm_info:
        info_lines = [f"- **{k}:** {v}" for k, v in report.llm_info.items()]
        parts.append(
            "## LLM Configuration\n\n" + "\n".join(info_lines) + "\n"
        )

    if report.transcript_excerpt:
        parts.append(
            f"## Transcript Excerpt\n\n{report.transcript_excerpt}\n"
        )

    if report.context:
        parts.append(f"## Additional Context\n\n{report.context}\n")

    if report.protocol_content:
        parts.append(
            f"## Clarity Protocol\n\n{report.protocol_content}\n"
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# GitHub issue draft
# ---------------------------------------------------------------------------

def build_feedback_issue_url(report: FeedbackReport) -> str:
    """Build a prefilled GitHub issue URL for the user to review."""
    query = urlencode({
        "title": "Product feedback",
        "body": format_feedback_md(report),
    })
    return f"{GITHUB_NEW_ISSUE_URL}?{query}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def prepare_feedback(report: FeedbackReport) -> FeedbackDeliveryResult:
    """Prepare a GitHub issue draft without submitting on the user's behalf."""
    return FeedbackDeliveryResult(issue_url=build_feedback_issue_url(report))
