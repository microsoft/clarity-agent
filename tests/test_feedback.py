"""Tests for clarity_agent.feedback."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from clarity_agent.feedback import (
    GITHUB_NEW_ISSUE_URL,
    FeedbackReport,
    build_feedback_issue_url,
    format_feedback_md,
    prepare_feedback,
)

# -----------------------------------------------------------------------
# Formatting
# -----------------------------------------------------------------------

class TestFormatFeedbackMd:
    def test_basic_message(self) -> None:
        report = FeedbackReport(message="Great tool!")
        md = format_feedback_md(report)
        assert "# Clarity Agent Feedback" in md
        assert "Great tool!" in md
        assert "OK to follow up: **No**" in md

    def test_contact_with_email(self) -> None:
        report = FeedbackReport(
            message="Bug report",
            contact_ok=True,
            contact_email="user@example.com",
        )
        md = format_feedback_md(report)
        assert "OK to follow up: **Yes**" in md
        assert "user@example.com" in md

    def test_contact_without_email(self) -> None:
        report = FeedbackReport(message="Hi", contact_ok=True)
        md = format_feedback_md(report)
        assert "no email provided" in md

    def test_llm_info_included(self) -> None:
        report = FeedbackReport(
            message="Test",
            llm_info={"Provider": "anthropic", "Active model": "claude-sonnet"},
        )
        md = format_feedback_md(report)
        assert "## LLM Configuration" in md
        assert "anthropic" in md
        assert "claude-sonnet" in md

    def test_transcript_included(self) -> None:
        report = FeedbackReport(
            message="Test",
            transcript_excerpt="User: hello\nAssistant: hi",
        )
        md = format_feedback_md(report)
        assert "## Transcript Excerpt" in md
        assert "User: hello" in md

# -----------------------------------------------------------------------
# GitHub issue draft
# -----------------------------------------------------------------------

class TestFeedbackIssueUrl:
    def test_prefills_github_issue(self) -> None:
        report = FeedbackReport(
            message="The app hangs",
            contact_ok=True,
            contact_email="user@example.com",
            context="It happened during failure brainstorming.",
        )

        url = build_feedback_issue_url(report)

        assert url.startswith(GITHUB_NEW_ISSUE_URL)
        assert "The+app+hangs" in url
        assert "user%40example.com" in url
        assert "failure+brainstorming" in url

    def test_truncates_oversized_issue_body(self) -> None:
        report = FeedbackReport(message="Feedback", context="🔥" * 10_000)

        url = build_feedback_issue_url(report)
        body = parse_qs(urlparse(url).query)["body"][0]

        assert len(url) <= 7000
        assert "## Additional Context" in body
        assert body.endswith("[Content truncated to fit this GitHub issue draft.]\n")


# -----------------------------------------------------------------------
# Preparation
# -----------------------------------------------------------------------

class TestPrepareFeedback:
    def test_returns_github_issue_draft(self) -> None:
        report = FeedbackReport(message="test feedback")
        result = prepare_feedback(report)

        assert result.issue_url.startswith(GITHUB_NEW_ISSUE_URL)
        assert "test+feedback" in result.issue_url
