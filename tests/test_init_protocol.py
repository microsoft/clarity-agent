"""Tests for init_protocol.py — the .clarity-protocol/ directory initializer."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from clarity_agent.protocol.initialize import DEFAULT_CONFIG, TEMPLATES, init_protocol


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    """A temporary directory that looks like a git repo (has .git/)."""
    (tmp_path / ".git").mkdir()
    return tmp_path


class TestDirectoryStructure:
    """init_protocol creates the expected directory layout."""

    def test_creates_protocol_dir(self, project_path: Path) -> None:
        result = init_protocol(project_path)
        assert result == project_path / ".clarity-protocol"
        assert result.is_dir()

    def test_creates_subdirectories(self, project_path: Path) -> None:
        init_protocol(project_path)
        pd = project_path / ".clarity-protocol"
        assert (pd / "goal").is_dir()
        assert (pd / "solution").is_dir()
        assert (pd / "failures").is_dir()
        assert (pd / "decisions").is_dir()
        assert (pd / "mailboxes").is_dir()
        assert (pd / "archive").is_dir()

    def test_creates_suggestion_box(self, project_path: Path) -> None:
        init_protocol(project_path)
        pd = project_path / ".clarity-protocol"
        assert (pd / "mailboxes" / "suggestions" / "_config.json").exists()
        assert (pd / "archive" / "suggestions" / "_config.json").exists()
        config = json.loads(
            (pd / "mailboxes" / "suggestions" / "_config.json").read_text()
        )
        assert config["display_name"] == "suggestion box"
        assert config["collector"] == "suggestion-review"
        assert config["collector_type"] == "single-response"
        assert config["permanent"] is True

    def test_suggestion_box_idempotent(self, project_path: Path) -> None:
        init_protocol(project_path)
        pd = project_path / ".clarity-protocol"
        # Write a suggestion
        (pd / "mailboxes" / "suggestions" / "idea.md").write_text("# Idea\n")
        # Re-init
        init_protocol(project_path)
        # Suggestion survives
        assert (pd / "mailboxes" / "suggestions" / "idea.md").exists()

    def test_creates_all_template_files(self, project_path: Path) -> None:
        init_protocol(project_path)
        pd = project_path / ".clarity-protocol"
        for rel_path in TEMPLATES:
            assert (pd / rel_path).exists(), f"Missing template: {rel_path}"


class TestConfigJson:
    """config.json is written with the correct default content."""

    def test_config_created(self, project_path: Path) -> None:
        init_protocol(project_path)
        config_path = project_path / ".clarity-protocol" / "config.json"
        assert config_path.exists()

    def test_config_matches_defaults(self, project_path: Path) -> None:
        init_protocol(project_path)
        config_path = project_path / ".clarity-protocol" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        assert config == DEFAULT_CONFIG

    def test_config_is_valid_json(self, project_path: Path) -> None:
        init_protocol(project_path)
        config_path = project_path / ".clarity-protocol" / "config.json"
        # Should not raise
        json.loads(config_path.read_text())

    def test_config_has_trailing_newline(self, project_path: Path) -> None:
        """Trailing newline keeps the file POSIX-compliant."""
        init_protocol(project_path)
        config_path = project_path / ".clarity-protocol" / "config.json"
        assert config_path.read_text().endswith("\n")


class TestTemplateContent:
    """Template files contain the expected placeholder markers."""

    def test_templates_contain_markers(self, project_path: Path) -> None:
        init_protocol(project_path)
        pd = project_path / ".clarity-protocol"
        for rel_path, expected_content in TEMPLATES.items():
            actual = (pd / rel_path).read_text(encoding="utf-8")
            assert actual == expected_content, f"Content mismatch: {rel_path}"

    def test_all_goal_templates_have_tbd_markers(self, project_path: Path) -> None:
        """Goal templates should be detectable as templates by the packet status checker."""
        init_protocol(project_path)
        pd = project_path / ".clarity-protocol"
        for name in ("problem.md", "stakeholders.md", "requirements.md"):
            content = (pd / "goal" / name).read_text()
            assert "[To be determined" in content or "[TBD]" in content


class TestIdempotence:
    """Running init_protocol twice is safe — existing files are not overwritten."""

    def test_does_not_overwrite_config(self, project_path: Path) -> None:
        init_protocol(project_path)
        config_path = project_path / ".clarity-protocol" / "config.json"

        # Modify config
        with open(config_path) as f:
            config = json.load(f)
        config["custom_field"] = "user data"
        with open(config_path, "w") as f:
            json.dump(config, f)

        # Run again
        init_protocol(project_path)

        # User's modification should survive
        with open(config_path) as f:
            config_after = json.load(f)
        assert config_after["custom_field"] == "user data"

    def test_does_not_overwrite_template_files(self, project_path: Path) -> None:
        init_protocol(project_path)
        problem_path = project_path / ".clarity-protocol" / "goal" / "problem.md"

        # User writes real content
        problem_path.write_text("# Problem\n\nWe need faster coffee.\n")

        # Run again
        init_protocol(project_path)

        # User's content should survive
        assert "faster coffee" in problem_path.read_text()

    def test_return_value_consistent(self, project_path: Path) -> None:
        result1 = init_protocol(project_path)
        result2 = init_protocol(project_path)
        assert result1 == result2


class TestSnippetInsertion:
    """Clarity snippet is inserted into agent config when clarity_agent_dir is provided."""

    def _make_agent_dir(self, tmp_path: Path) -> Path:
        """Create a fake clarity-agent directory with the real snippet template."""
        from clarity_agent.setup.snippet import snippet_path

        agent_dir = tmp_path / "fake-clarity-agent"
        setup_dir = agent_dir / "src" / "clarity_agent" / "setup"
        setup_dir.mkdir(parents=True)
        # Copy the real snippet template so render_snippet works.
        import shutil
        shutil.copy2(snippet_path(), setup_dir / "snippet.md")
        return agent_dir

    def test_inserts_snippet_into_new_file(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()

        init_protocol(project, clarity_agent_dir=Path(__file__).resolve().parent.parent)

        # Should create AGENTS.md (default target) with delimiters.
        from clarity_agent.setup.snippet import BEGIN_DELIMITER, END_DELIMITER
        target = project / "AGENTS.md"
        assert target.exists()
        content = target.read_text()
        assert BEGIN_DELIMITER in content
        assert END_DELIMITER in content

    def test_appends_to_existing_agents_md(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / "AGENTS.md").write_text("# Custom agents config\n")

        init_protocol(project, clarity_agent_dir=Path(__file__).resolve().parent.parent)

        from clarity_agent.setup.snippet import BEGIN_DELIMITER
        content = (project / "AGENTS.md").read_text()
        assert "# Custom agents config" in content
        assert BEGIN_DELIMITER in content

    def test_snippet_references_mcp_tools(self, tmp_path: Path) -> None:
        """The snippet should reference MCP tool names, not CLI commands."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".clarity-agent").mkdir()

        init_protocol(project, clarity_agent_dir=Path(__file__).resolve().parent.parent)

        from clarity_agent.setup.snippet import find_target
        content = find_target(project).read_text()
        assert "run_clarity" in content
        assert "check_decision" in content
        assert "{{PROCESSES_DIR}}" not in content

    def test_no_snippet_without_clarity_agent_dir(self, tmp_path: Path) -> None:
        init_protocol(tmp_path)
        assert not (tmp_path / "CLAUDE.md").exists()
        assert not (tmp_path / "AGENTS.md").exists()

    def test_missing_snippet_template_is_fine(self, tmp_path: Path) -> None:
        """If the snippet template doesn't exist, no error."""
        fake_path = tmp_path / "nonexistent" / "snippet.md"
        with patch("clarity_agent.setup.snippet.snippet_path", return_value=fake_path):
            init_protocol(tmp_path, clarity_agent_dir=tmp_path / "empty-agent")
        assert not (tmp_path / "CLAUDE.md").exists()

    def test_idempotent(self, tmp_path: Path) -> None:
        """Running init_protocol twice doesn't duplicate the snippet."""
        project = tmp_path / "project"
        project.mkdir()
        agent_dir = Path(__file__).resolve().parent.parent

        init_protocol(project, clarity_agent_dir=agent_dir)
        first = (project / "AGENTS.md").read_text()

        init_protocol(project, clarity_agent_dir=agent_dir)
        second = (project / "AGENTS.md").read_text()

        assert first == second
