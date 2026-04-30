"""Tests for tools/suggestion.py — cross-cutting document suggestion tool."""

from __future__ import annotations

from pathlib import Path

from clarity_agent.ai_actions.suggestion import (
    RECORD_SUGGESTION_TOOL,
    RawSuggestion,
    handle_record_suggestion,
    record_suggestion,
    render_suggestion_markdown,
)
from clarity_agent.llm.types import ToolUseBlock

# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

class TestRenderSuggestionMarkdown:
    """render_suggestion_markdown() produces expected markdown."""

    def test_basic_rendering(self) -> None:
        s = RawSuggestion(
            title="Add stalker to stakeholders",
            source="conversation",
            target_document="goal/stakeholders.md",
            suggestion="Add a stalker adversary persona.",
        )
        md = render_suggestion_markdown(s)
        assert "# Add stalker to stakeholders" in md
        assert "**Source:** conversation" in md
        assert "**Target:** goal/stakeholders.md" in md
        assert "Add a stalker adversary persona." in md

    def test_includes_rationale_when_provided(self) -> None:
        s = RawSuggestion(
            title="T",
            source="s",
            target_document="d",
            suggestion="x",
            rationale="Because we found adversarial use patterns.",
        )
        md = render_suggestion_markdown(s)
        assert "## Rationale" in md
        assert "adversarial use patterns" in md

    def test_omits_rationale_when_empty(self) -> None:
        s = RawSuggestion(
            title="T", source="s", target_document="d", suggestion="x",
        )
        md = render_suggestion_markdown(s)
        assert "Rationale" not in md


# ---------------------------------------------------------------------------
# record_suggestion (core function)
# ---------------------------------------------------------------------------

class TestRecordSuggestion:
    """record_suggestion() writes to the suggestion box."""

    def test_writes_to_suggestion_box(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        pd.mkdir()
        path, msg = record_suggestion(
            pd,
            title="Add adversary",
            target_document="goal/stakeholders.md",
            suggestion="Include stalker persona.",
        )
        assert path.exists()
        assert "adversary" in path.name.lower() or "add" in path.name.lower()
        assert "Recorded suggestion" in msg

    def test_file_contains_rendered_content(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        pd.mkdir()
        path, _ = record_suggestion(
            pd,
            title="Improve docs",
            target_document="solution/architecture.md",
            suggestion="Add diagram.",
            rationale="Architecture is unclear.",
        )
        content = path.read_text()
        assert "# Improve docs" in content
        assert "**Target:** solution/architecture.md" in content
        assert "Add diagram." in content
        assert "Architecture is unclear." in content

    def test_default_source_is_conversation(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        pd.mkdir()
        path, _ = record_suggestion(
            pd,
            title="T",
            target_document="d",
            suggestion="s",
        )
        assert "**Source:** conversation" in path.read_text()

    def test_custom_source(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        pd.mkdir()
        path, _ = record_suggestion(
            pd,
            title="T",
            target_document="d",
            suggestion="s",
            source="security-thinker",
        )
        assert "**Source:** security-thinker" in path.read_text()


# ---------------------------------------------------------------------------
# handle_record_suggestion (tool handler)
# ---------------------------------------------------------------------------

class TestHandleRecordSuggestion:
    """handle_record_suggestion() dispatches tool calls correctly."""

    def test_creates_file_from_tool_call(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        pd.mkdir()
        tc = ToolUseBlock(
            id="tc_1",
            name="record_suggestion",
            input={
                "title": "Add test coverage",
                "target_document": "solution/solution.md",
                "suggestion": "Include testing strategy section.",
            },
        )
        path, msg = handle_record_suggestion(tc, pd)
        assert path.exists()
        assert "Recorded suggestion" in msg
        assert "testing strategy" in path.read_text()


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

class TestRecordSuggestionTool:
    """RECORD_SUGGESTION_TOOL schema is well-formed."""

    def test_has_required_fields(self) -> None:
        assert RECORD_SUGGESTION_TOOL["name"] == "record_suggestion"
        assert "description" in RECORD_SUGGESTION_TOOL
        schema = RECORD_SUGGESTION_TOOL["input_schema"]
        assert "title" in schema["required"]
        assert "target_document" in schema["required"]
        assert "suggestion" in schema["required"]
