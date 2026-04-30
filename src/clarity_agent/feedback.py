"""User feedback mechanism.

Provides functions to gather context, format feedback as markdown,
and submit it to the feedback endpoint (an Azure Function that
validates and stores the content server-side).

If the endpoint is not configured or the upload fails, feedback is
saved to a local file so the user's input is never lost.
"""

from __future__ import annotations

import os
import tempfile
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — replace with the real endpoint URL when ready.
# ---------------------------------------------------------------------------

# The URL of the feedback submission endpoint (Azure Function).
# The function key is included in the URL as a query parameter.
# The storage credential lives server-side and never reaches the client.
# Example:
#   FEEDBACK_URL = "https://clarity-feedback.azurewebsites.net/api/feedback?code=<function-key>"
FEEDBACK_URL: str = ""


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
    protocol_content: str | None = None


@dataclass
class FeedbackDeliveryResult:
    """Outcome of attempting to deliver feedback."""

    submitted: bool
    """True if feedback was uploaded successfully."""
    file_path: Path | None = None
    """Local file path (set when upload fails or is not configured)."""


# ---------------------------------------------------------------------------
# Context gathering
# ---------------------------------------------------------------------------

def gather_llm_info(
    provider: str | None = None,
    model: str | None = None,
    active_model: str | None = None,
    active_tier: str | None = None,
) -> dict[str, str]:
    """Gather LLM backend/model information into a display dict."""
    info: dict[str, str] = {}
    if provider:
        info["Provider"] = provider
    if model:
        info["Configured model"] = model
    if active_model:
        info["Active model"] = active_model
    if active_tier:
        info["Active tier"] = active_tier
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

    if report.protocol_content:
        parts.append(
            f"## Clarity Protocol\n\n{report.protocol_content}\n"
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Delivery: POST to feedback endpoint
# ---------------------------------------------------------------------------

def _upload_feedback(feedback_md: str) -> bool:
    """POST feedback to the submission endpoint.

    Returns ``True`` on success (HTTP 201), ``False`` on failure or
    if the endpoint is not configured.
    """
    if not FEEDBACK_URL:
        return False

    data = feedback_md.encode("utf-8")
    req = urllib.request.Request(
        FEEDBACK_URL,
        data=data,
        method="POST",
        headers={"Content-Type": "text/markdown; charset=utf-8"},
    )
    try:
        response = urllib.request.urlopen(req, timeout=15)
        return response.status == 201
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Delivery: local save (when upload is unavailable)
# ---------------------------------------------------------------------------

def _save_feedback_file(feedback_md: str) -> Path:
    """Save formatted feedback to a temporary ``.md`` file.

    The file is placed in the system temp directory with a timestamped
    name and is **not** auto-deleted, so the user's input is never lost.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    fd, path_str = tempfile.mkstemp(
        prefix=f"clarity-feedback-{timestamp}-",
        suffix=".md",
    )
    path = Path(path_str)
    path.write_text(feedback_md, encoding="utf-8")
    os.close(fd)
    return path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def prepare_feedback(report: FeedbackReport) -> FeedbackDeliveryResult:
    """Format and deliver feedback.

    Tries the remote endpoint first.  If it is not configured or the
    upload fails, saves to a local file so the user's input is preserved.
    """
    feedback_md = format_feedback_md(report)

    if _upload_feedback(feedback_md):
        return FeedbackDeliveryResult(submitted=True)

    file_path = _save_feedback_file(feedback_md)
    return FeedbackDeliveryResult(submitted=False, file_path=file_path)
