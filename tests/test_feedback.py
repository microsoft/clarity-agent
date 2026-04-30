"""Tests for clarity_agent.feedback."""

from __future__ import annotations

import http.server
import threading
from unittest.mock import patch

from clarity_agent.feedback import (
    FeedbackReport,
    _upload_feedback,
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

    def test_protocol_included(self) -> None:
        report = FeedbackReport(
            message="Test",
            protocol_content="# Problem\n\nSomething is broken.",
        )
        md = format_feedback_md(report)
        assert "## Clarity Protocol" in md
        assert "Something is broken" in md


# -----------------------------------------------------------------------
# Upload
# -----------------------------------------------------------------------

class _StubHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler that records the request and returns 201."""

    # Class-level state shared across requests.
    last_body: bytes = b""
    last_content_type: str = ""
    response_code: int = 201

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        _StubHandler.last_body = self.rfile.read(length)
        _StubHandler.last_content_type = self.headers.get("Content-Type", "")
        self.send_response(_StubHandler.response_code)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass  # Suppress request logging in test output.


class TestUploadFeedback:
    """Test the client-side upload path against a local stub server."""

    def _start_server(self) -> tuple[http.server.HTTPServer, str]:
        server = http.server.HTTPServer(("127.0.0.1", 0), _StubHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        return server, f"http://127.0.0.1:{port}/api/feedback"

    def test_posts_markdown_to_endpoint(self) -> None:
        server, url = self._start_server()
        try:
            with patch("clarity_agent.feedback.FEEDBACK_URL", url):
                result = _upload_feedback("# Test feedback")
            assert result is True
            assert b"# Test feedback" in _StubHandler.last_body
            assert "text/markdown" in _StubHandler.last_content_type
        finally:
            server.server_close()

    def test_returns_false_on_non_201(self) -> None:
        _StubHandler.response_code = 400
        server, url = self._start_server()
        try:
            with patch("clarity_agent.feedback.FEEDBACK_URL", url):
                result = _upload_feedback("bad")
            assert result is False
        finally:
            _StubHandler.response_code = 201  # Reset for other tests.
            server.server_close()

    def test_returns_false_when_not_configured(self) -> None:
        assert _upload_feedback("anything") is False

    def test_returns_false_on_network_error(self) -> None:
        with patch("clarity_agent.feedback.FEEDBACK_URL", "http://127.0.0.1:1/nope"):
            result = _upload_feedback("anything")
        assert result is False


# -----------------------------------------------------------------------
# Delivery (prepare_feedback)
# -----------------------------------------------------------------------

class TestPrepareFeedback:
    def test_falls_back_to_local_when_not_configured(self) -> None:
        """With no endpoint configured, feedback is saved locally."""
        report = FeedbackReport(message="test feedback")
        result = prepare_feedback(report)

        assert not result.submitted
        assert result.file_path is not None
        assert result.file_path.exists()

        saved = result.file_path.read_text(encoding="utf-8")
        assert "test feedback" in saved

        result.file_path.unlink(missing_ok=True)

    def test_submitted_when_endpoint_accepts(self) -> None:
        """When the endpoint returns 201, result.submitted is True."""
        server = http.server.HTTPServer(("127.0.0.1", 0), _StubHandler)
        port = server.server_address[1]
        url = f"http://127.0.0.1:{port}/api/feedback"
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()

        try:
            with patch("clarity_agent.feedback.FEEDBACK_URL", url):
                report = FeedbackReport(message="uploaded feedback")
                result = prepare_feedback(report)

            assert result.submitted
            assert result.file_path is None
            assert b"uploaded feedback" in _StubHandler.last_body
        finally:
            server.server_close()
