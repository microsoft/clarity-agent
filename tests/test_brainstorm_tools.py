"""Tests for tools/brainstorm.py — brainstorm-specific tools and handler."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from clarity_agent.ai_actions.brainstorm import (
    READ_THINKER_GUIDE_TOOL,
    RECOMMEND_DEEPER_ANALYSIS_TOOL,
    RECORD_FAILURE_TOOL,
    ChainAnnotation,
    ChainStep,
    RawFailure,
    create_brainstorm_handler,
    create_brainstorm_tools,
    format_available_thinkers,
    read_thinker_guide,
    record_failure,
    render_chain_markdown,
    render_failure_markdown,
)
from clarity_agent.llm.types import ToolUseBlock
from clarity_agent.protocol.thinker_registry import Prerequisites, ThinkerInfo


def _make_thinker_info(
    name: str = "test-thinker",
    display_name: str = "Test Thinker",
    description: str = "For testing.",
) -> ThinkerInfo:
    """Create a minimal ThinkerInfo for tests."""
    return ThinkerInfo(
        name=name,
        display_name=display_name,
        type="ai",
        modes=["deep"],
        prerequisites=Prerequisites(),
        tags=[],
        guide_path=Path("/fake"),
        guide_content="# Test guide",
        description=description,
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

class TestRenderChainMarkdown:
    """render_chain_markdown() produces expected output."""

    def test_basic_chain(self) -> None:
        chain = [
            ChainStep(step_number=1, description="User submits form"),
            ChainStep(step_number=2, description="Server crashes"),
        ]
        md = render_chain_markdown(chain)
        assert "1. User submits form" in md
        assert "2. Server crashes" in md

    def test_harm_markers(self) -> None:
        chain = [
            ChainStep(step_number=1, description="Data exposed", harm_begins=True),
            ChainStep(step_number=2, description="Attacker downloads", harm_ends=True),
        ]
        md = render_chain_markdown(chain)
        assert "**harm begins**" in md
        assert "**harm ends**" in md

    def test_annotations(self) -> None:
        chain = [
            ChainStep(
                step_number=1,
                description="Request arrives",
                annotations=[
                    ChainAnnotation(type="intervention_point", content="Rate limit here"),
                    ChainAnnotation(type="observation", content="No auth check"),
                ],
            ),
        ]
        md = render_chain_markdown(chain)
        assert "*Intervention point:* Rate limit here" in md
        assert "*Observation:* No auth check" in md


class TestRenderFailureMarkdown:
    """render_failure_markdown() produces expected output."""

    def test_basic_failure(self) -> None:
        f = RawFailure(
            title="SQL Injection",
            source="security-thinker",
            description="Unsanitized input leads to data breach.",
        )
        md = render_failure_markdown(f)
        assert "# SQL Injection" in md
        assert "**Source:** security-thinker" in md
        assert "Unsanitized input" in md

    def test_pre_existing_flag(self) -> None:
        f = RawFailure(
            title="T", source="s", description="d", pre_existing=True,
        )
        md = render_failure_markdown(f)
        assert "**Pre-existing:** Yes" in md

    def test_pre_existing_false(self) -> None:
        f = RawFailure(
            title="T", source="s", description="d", pre_existing=False,
        )
        md = render_failure_markdown(f)
        assert "**Pre-existing:** No" in md

    def test_omits_pre_existing_when_none(self) -> None:
        f = RawFailure(title="T", source="s", description="d")
        md = render_failure_markdown(f)
        assert "Pre-existing" not in md

    def test_includes_chain_when_provided(self) -> None:
        f = RawFailure(
            title="T",
            source="s",
            description="d",
            failure_chain=[
                ChainStep(step_number=1, description="Step one"),
            ],
        )
        md = render_failure_markdown(f)
        assert "## Failure Chain" in md
        assert "1. Step one" in md

    def test_includes_additional_context(self) -> None:
        f = RawFailure(
            title="T", source="s", description="d",
            additional_context="Severity is high.",
        )
        md = render_failure_markdown(f)
        assert "## Additional Context" in md
        assert "Severity is high." in md


# ---------------------------------------------------------------------------
# record_failure (core function)
# ---------------------------------------------------------------------------

class TestRecordFailure:
    """record_failure() writes to the failure-brainstorm mailbox."""

    def test_writes_failure_to_mailbox(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        pd.mkdir()
        path, msg = record_failure(
            pd,
            title="Data Loss on Crash",
            description="Server crash causes data loss.",
        )
        assert path.exists()
        assert "Recorded failure" in msg

    def test_file_contains_rendered_content(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        pd.mkdir()
        path, _ = record_failure(
            pd,
            title="Auth Bypass",
            description="Missing auth check allows unauthorized access.",
            source="security-analysis",
            additional_context="Critical severity.",
        )
        content = path.read_text()
        assert "# Auth Bypass" in content
        assert "**Source:** security-analysis" in content
        assert "Missing auth check" in content
        assert "Critical severity." in content

    def test_pre_existing_marker_in_message(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        pd.mkdir()
        _, msg = record_failure(
            pd,
            title="T",
            description="d",
            pre_existing=True,
        )
        assert "(pre-existing)" in msg

    def test_failure_chain_parsing(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        pd.mkdir()
        raw_chain: list[dict[str, Any]] = [
            {"step_number": 1, "description": "User clicks button"},
            {
                "step_number": 2,
                "description": "Service fails",
                "harm_begins": True,
                "annotations": [
                    {"type": "intervention_point", "content": "Add retry"},
                ],
            },
        ]
        path, _ = record_failure(
            pd,
            title="Cascading Failure",
            description="Click triggers cascade.",
            failure_chain=raw_chain,
        )
        content = path.read_text()
        assert "## Failure Chain" in content
        assert "User clicks button" in content
        assert "**harm begins**" in content
        assert "*Intervention point:*" in content

    def test_multiple_failures_create_separate_files(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        pd.mkdir()
        p1, _ = record_failure(pd, title="Failure One", description="d1")
        p2, _ = record_failure(pd, title="Failure Two", description="d2")
        assert p1 != p2
        assert p1.exists()
        assert p2.exists()


# ---------------------------------------------------------------------------
# read_thinker_guide
# ---------------------------------------------------------------------------

class TestReadThinkerGuide:
    """read_thinker_guide() reads guide files."""

    def test_reads_existing_guide(self, tmp_path: Path) -> None:
        thinkers_dir = tmp_path / "thinkers"
        thinkers_dir.mkdir()
        (thinkers_dir / "test-thinker.md").write_text("# Test Guide\nContent.")
        result = read_thinker_guide(tmp_path, "test-thinker")
        assert "# Test Guide" in result
        assert "Content." in result

    def test_returns_error_for_missing_guide(self, tmp_path: Path) -> None:
        result = read_thinker_guide(tmp_path, "nonexistent")
        assert "Error" in result
        assert "not found" in result


# ---------------------------------------------------------------------------
# create_brainstorm_handler
# ---------------------------------------------------------------------------

class TestCreateBrainstormHandler:
    """create_brainstorm_handler() returns a working dispatch function."""

    def _make_handler(self, tmp_path: Path) -> Callable[[ToolUseBlock], str]:
        pd = tmp_path / ".clarity-protocol"
        pd.mkdir()
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "thinkers").mkdir()
        (agent_dir / "thinkers" / "test-thinker.md").write_text("# Guide")
        return create_brainstorm_handler(pd, agent_dir)

    def test_handles_record_failure(self, tmp_path: Path) -> None:
        handle = self._make_handler(tmp_path)
        tc = ToolUseBlock(
            id="tc_1",
            name="record_failure",
            input={"title": "Test Failure", "description": "Something breaks."},
        )
        result = handle(tc)
        assert "Recorded failure" in result

    def test_handles_record_suggestion(self, tmp_path: Path) -> None:
        handle = self._make_handler(tmp_path)
        tc = ToolUseBlock(
            id="tc_2",
            name="record_suggestion",
            input={
                "title": "Add adversary",
                "target_document": "goal/stakeholders.md",
                "suggestion": "Include stalker.",
            },
        )
        result = handle(tc)
        assert "Recorded suggestion" in result

    def test_handles_recommend_deeper(self, tmp_path: Path) -> None:
        handle = self._make_handler(tmp_path)
        tc = ToolUseBlock(
            id="tc_3",
            name="recommend_deeper_analysis",
            input={
                "thinker_name": "security-thinker",
                "rationale": "Has API endpoints.",
            },
        )
        result = handle(tc)
        assert "security-thinker" in result

    def test_handles_read_thinker_guide(self, tmp_path: Path) -> None:
        handle = self._make_handler(tmp_path)
        tc = ToolUseBlock(
            id="tc_4",
            name="read_thinker_guide",
            input={"thinker_name": "test-thinker"},
        )
        result = handle(tc)
        assert "# Guide" in result

    def test_unknown_tool_returns_error(self, tmp_path: Path) -> None:
        handle = self._make_handler(tmp_path)
        tc = ToolUseBlock(id="tc_5", name="unknown_tool", input={})
        result = handle(tc)
        assert "Unknown tool" in result

    def test_fires_on_tool_use_callback(self, tmp_path: Path) -> None:
        calls: list[tuple[str, str]] = []
        pd = tmp_path / ".clarity-protocol"
        pd.mkdir()
        handle = create_brainstorm_handler(
            pd, tmp_path,
            on_tool_use=lambda name, detail: calls.append((name, detail)),
        )
        tc = ToolUseBlock(
            id="tc_6",
            name="record_failure",
            input={"title": "CB Test", "description": "Test callback."},
        )
        handle(tc)
        assert len(calls) == 1
        assert calls[0][0] == "record_failure"


# ---------------------------------------------------------------------------
# create_brainstorm_tools
# ---------------------------------------------------------------------------

class TestCreateBrainstormTools:
    """create_brainstorm_tools() returns appropriate schemas."""

    def test_basic_tools_without_thinkers(self) -> None:
        tools = create_brainstorm_tools()
        names = {t["name"] for t in tools}
        assert "record_failure" in names
        assert "record_suggestion" in names
        assert "recommend_deeper_analysis" not in names
        assert "read_thinker_guide" not in names

    def test_includes_specialist_tools_with_thinkers(self) -> None:
        thinkers = [_make_thinker_info("test-thinker", "Test Thinker")]
        tools = create_brainstorm_tools(thinkers)
        names = {t["name"] for t in tools}
        assert "recommend_deeper_analysis" in names
        assert "read_thinker_guide" in names


# ---------------------------------------------------------------------------
# format_available_thinkers
# ---------------------------------------------------------------------------

class TestFormatAvailableThinkers:
    """format_available_thinkers() renders thinker info for prompts."""

    def test_formats_thinkers(self) -> None:
        thinkers = [_make_thinker_info("security-thinker", "Security Thinker", "Analyzes security.")]
        text = format_available_thinkers(thinkers)
        assert "Security Thinker" in text
        assert "`security-thinker`" in text
        assert "Analyzes security." in text


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

class TestToolSchemas:
    """Tool schemas are well-formed."""

    @pytest.mark.parametrize("tool", [
        RECORD_FAILURE_TOOL,
        RECOMMEND_DEEPER_ANALYSIS_TOOL,
        READ_THINKER_GUIDE_TOOL,
    ])
    def test_has_name_and_schema(self, tool: dict[str, Any]) -> None:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert "required" in tool["input_schema"]
