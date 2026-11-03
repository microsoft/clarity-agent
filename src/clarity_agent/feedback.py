"""User feedback mechanism.

Provides functions to gather context, format feedback as markdown,
and prepare a user-reviewed GitHub issue.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from urllib.parse import urlencode

GITHUB_NEW_ISSUE_URL = "https://github.com/microsoft/clarity-agent/issues/new"
# Stay below the commonly supported 8 KB request-target limit used by browsers
# and proxies, leaving room for redirects or other URL additions.
_MAX_ISSUE_URL_LENGTH = 7000
_TRUNCATION_NOTICE = "\n\n[Content truncated to fit this GitHub issue draft.]"


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

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# GitHub issue draft
# ---------------------------------------------------------------------------

def build_feedback_issue_url(report: FeedbackReport) -> str:
    """Build a prefilled GitHub issue URL for the user to review."""
    def issue_url(candidate: FeedbackReport) -> str:
        query = urlencode({
            "title": "Product feedback",
            "body": format_feedback_md(candidate),
        })
        return f"{GITHUB_NEW_ISSUE_URL}?{query}"

    url = issue_url(report)
    if len(url) <= _MAX_ISSUE_URL_LENGTH:
        return url

    candidate = report
    for field_name in ("context", "transcript_excerpt", "message"):
        value = getattr(candidate, field_name)
        if not value:
            continue

        low, high = 0, len(value)
        best: FeedbackReport | None = None
        while low <= high:
            midpoint = (low + high) // 2
            shortened = replace(
                candidate,
                **{field_name: value[:midpoint] + _TRUNCATION_NOTICE},
            )
            if len(issue_url(shortened)) <= _MAX_ISSUE_URL_LENGTH:
                best = shortened
                low = midpoint + 1
            else:
                high = midpoint - 1
        if best is not None:
            return issue_url(best)
        empty_value = "" if field_name == "message" else None
        candidate = replace(candidate, **{field_name: empty_value})

    fallback = issue_url(FeedbackReport(message=_TRUNCATION_NOTICE.strip()))
    if len(fallback) > _MAX_ISSUE_URL_LENGTH:
        raise ValueError("GitHub issue URL limit is too small for the issue template")
    return fallback


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def prepare_feedback(report: FeedbackReport) -> FeedbackDeliveryResult:
    """Prepare a GitHub issue draft without submitting on the user's behalf."""
    return FeedbackDeliveryResult(issue_url=build_feedback_issue_url(report))
