"""Tests for standalone Responsible AI assessment support."""

from pathlib import Path

import pytest

from clarity_agent.ai_actions.rai_assessment import (
    create_rai_assessment_handler,
    load_rai_guidance,
    read_project_plan,
    write_rai_assessment,
)
from clarity_agent.llm.types import ToolUseBlock

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_given_project_plan_when_read_then_returns_markdown(tmp_path: Path) -> None:
    # Arrange
    plan = tmp_path / "docs" / "project-plan.md"
    plan.parent.mkdir()
    plan.write_text("# Project plan\n", encoding="utf-8")

    # Act
    path, content = read_project_plan(tmp_path, "docs/project-plan.md")

    # Assert
    assert (path, content) == (plan, "# Project plan\n")


def test_given_external_path_when_read_then_rejects_traversal(tmp_path: Path) -> None:
    # Arrange
    outside = tmp_path.parent / "outside.md"
    outside.write_text("secret", encoding="utf-8")

    # Act and assert
    with pytest.raises(ValueError, match="within the assessed project"):
        read_project_plan(tmp_path, "../outside.md")


def test_given_assessment_when_write_then_persists_markdown(tmp_path: Path) -> None:
    # Act
    path = write_rai_assessment(tmp_path, "# Responsible AI Assessment")

    # Assert
    assert path.read_text(encoding="utf-8") == "# Responsible AI Assessment\n"


def test_given_external_path_when_write_then_rejects_traversal(tmp_path: Path) -> None:
    # Act and assert
    with pytest.raises(ValueError, match="within the assessed project"):
        write_rai_assessment(tmp_path, "content", "../assessment.md")


def test_given_agent_bundle_when_loading_guidance_then_includes_required_sources(
    tmp_path: Path,
) -> None:
    # Arrange
    sources = {
        "rai-context/rai-background.md": "RAI background",
        "rai-context/sensitive-use-cases.md": "Sensitive uses",
        "thinkers/responsible-ai-thinker.md": "Thinker method",
    }
    for relative_path, content in sources.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    # Act
    guidance = load_rai_guidance(tmp_path)

    # Assert
    assert all(content in guidance for content in sources.values())


def test_given_tool_calls_when_handled_then_reads_plan_and_writes_assessment(
    tmp_path: Path,
) -> None:
    # Arrange
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    handler = create_rai_assessment_handler(tmp_path)

    # Act
    plan_result = handler(ToolUseBlock("1", "read_project_plan", {"path": "plan.md"}))
    write_result = handler(
        ToolUseBlock("2", "write_rai_assessment", {"content": "# Assessment"}),
    )

    # Assert
    assert plan_result == "# Plan\n"
    assert "Assessment written" in write_result
    assert (tmp_path / "rai-assessment.md").is_file()


def test_given_wheel_manifest_when_checked_then_includes_rai_context() -> None:
    # Arrange
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    # Act
    mapping = '"rai-context" = "clarity_agent/_data/rai-context"'

    # Assert
    assert mapping in pyproject


def test_given_pyinstaller_manifest_when_checked_then_includes_rai_context() -> None:
    # Arrange
    spec = (REPO_ROOT / "clarity-server.spec").read_text(encoding="utf-8")

    # Act
    data_entry = '("rai-context", "rai-context")'

    # Assert
    assert data_entry in spec


def test_given_repository_bundle_when_loading_guidance_then_has_no_missing_sources() -> None:
    # Act
    guidance = load_rai_guidance(REPO_ROOT)

    # Assert
    assert "Required source unavailable" not in guidance
