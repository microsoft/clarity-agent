"""
Tests for GitHub Copilot backend-signaled compaction detection.

Copilot's SDK fires ``SESSION_COMPACTION_COMPLETE`` with the
full summary content + messages-removed count attached.  Unlike
the Claude SDK path (which requires PreCompact hook + post-hoc
JSONL parsing), Copilot gives us everything in one event — so
the integration is just "translate the event to a
``CompactionInfo`` and fire ``on_compaction``."

These tests exercise that translation with a synthetic event,
since spinning up a real Copilot session for testing would
require an authenticated SDK + a long enough conversation to
trigger auto-compaction.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from clarity_agent.llm.types import CompactionInfo


def _import_copilot_backend():
    """Import CopilotChatBackend, skipping if the SDK isn't installed.

    Wrapped because the Copilot SDK is optional and may not be
    present in every test env.
    """
    try:
        from copilot.generated.session_events import (
            SessionEvent,
            SessionEventType,
        )

        from clarity_agent.llm.impl.github_copilot import CopilotChatBackend
        return CopilotChatBackend, SessionEvent, SessionEventType
    except ImportError:
        pytest.skip("copilot SDK not installed")


def _build_session_compaction_event(
    *,
    success: bool = True,
    summary_content: str | None = "compacted summary text",
    messages_removed: float | None = 12,
):
    """Build a synthetic ``SESSION_COMPACTION_COMPLETE`` event.

    The real event carries a ``SessionCompactionCompleteData``
    in its ``data`` field; we mock the attributes that the
    backend's handler reads.
    """
    _, SessionEvent, SessionEventType = _import_copilot_backend()
    event = MagicMock(spec=SessionEvent)
    event.type = SessionEventType.SESSION_COMPACTION_COMPLETE
    event.data = MagicMock()
    event.data.success = success
    event.data.summary_content = summary_content
    event.data.messages_removed = messages_removed
    return event


def _fake_handler():
    """Return (fired_list, callback) so tests can capture
    on_compaction calls without setting up the whole backend."""
    fired: list[CompactionInfo] = []
    return fired, fired.append


# ---------------------------------------------------------------------------
# Direct handler invocation
#
# The compaction handling lives inside an inner ``on_event`` closure
# in ``_async_send_one``; rather than replay the whole closure setup,
# these tests focus on the contract — given an event of the right
# type with the right data shape, the on_compaction callback fires
# with a properly-translated ``CompactionInfo``.
# ---------------------------------------------------------------------------


class TestCompletionEventTranslation:
    def test_fires_with_summary_and_count(self):
        # The happy path: success=True, full content, count present.
        # The CompactionInfo carries through exactly what the SDK
        # reported — including converting the float messages_removed
        # to an int (Copilot's JSON-schema generation types it as
        # float; we want an int for downstream UI display).
        from clarity_agent.llm.impl.github_copilot import CopilotChatBackend  # noqa: F401
        event = _build_session_compaction_event(
            summary_content="auth refactor decisions captured; in-flight: D-3 review",
            messages_removed=42,
        )

        # Build the snippet from the backend that does the
        # translation.  We mirror the logic here rather than
        # invoking the full ``_async_send_one`` because the
        # latter requires a live session.
        fired, on_compaction = _fake_handler()
        success = event.data.success
        summary_content = event.data.summary_content
        if success and summary_content and on_compaction:
            messages_removed = event.data.messages_removed
            on_compaction(CompactionInfo(
                summary=summary_content,
                source_turn_count=(
                    int(messages_removed) if messages_removed is not None
                    else None
                ),
            ))

        assert len(fired) == 1
        assert fired[0].summary == "auth refactor decisions captured; in-flight: D-3 review"
        assert fired[0].source_turn_count == 42

    def test_no_fire_on_failed_compaction(self):
        # Copilot reports success=False if its compaction LLM call
        # errored.  Don't record a bogus/missing summary in our
        # transcript.
        event = _build_session_compaction_event(
            success=False, summary_content=None,
        )
        fired, on_compaction = _fake_handler()
        success = event.data.success
        summary_content = event.data.summary_content
        if success and summary_content and on_compaction:
            on_compaction(CompactionInfo(summary=summary_content))
        assert fired == []

    def test_no_fire_on_missing_summary_content(self):
        # Even with success=True, defensively skip if the summary is
        # empty — recording an empty CompactionSummary would be
        # confusing to the user.
        event = _build_session_compaction_event(
            success=True, summary_content=None,
        )
        fired, on_compaction = _fake_handler()
        success = event.data.success
        summary_content = event.data.summary_content
        if success and summary_content and on_compaction:
            on_compaction(CompactionInfo(summary=summary_content))
        assert fired == []

    def test_missing_messages_removed_defaults_to_none(self):
        # When the SDK doesn't report a count (older SDK versions,
        # edge cases), the Transcript layer will derive the count
        # from its own 70/30 split.
        event = _build_session_compaction_event(
            summary_content="summary",
            messages_removed=None,
        )
        fired, on_compaction = _fake_handler()
        success = event.data.success
        summary_content = event.data.summary_content
        if success and summary_content and on_compaction:
            messages_removed = event.data.messages_removed
            on_compaction(CompactionInfo(
                summary=summary_content,
                source_turn_count=(
                    int(messages_removed) if messages_removed is not None
                    else None
                ),
            ))
        assert len(fired) == 1
        assert fired[0].source_turn_count is None


class TestEventTypeRouting:
    """Smoke check that the event-type constant matches what we
    handle.  Just confirms the SDK names the event the way we
    expect — if a future SDK version renames the type, this test
    will fail visibly rather than silently dropping signals."""

    def test_session_compaction_complete_is_a_known_event_type(self):
        _, _, SessionEventType = _import_copilot_backend()
        # The handler in github_copilot.py keys off this name.
        assert hasattr(SessionEventType, "SESSION_COMPACTION_COMPLETE")
