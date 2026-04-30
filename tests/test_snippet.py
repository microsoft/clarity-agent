"""Tests for clarity_agent.setup.snippet."""

from __future__ import annotations

from pathlib import Path

from clarity_agent.setup.snippet import (
    BEGIN_DELIMITER,
    END_DELIMITER,
    find_target,
    has_snippet,
    insert_snippet,
    render_snippet,
    snippet_path,
)


class TestSnippetPath:
    def test_returns_existing_file(self) -> None:
        path = snippet_path()
        assert path.exists()
        assert path.name == "snippet.md"


class TestRenderSnippet:
    def test_substitutes_processes_dir(self) -> None:
        result = render_snippet(".clarity-agent/processes")
        assert ".clarity-agent/processes/clarity-agent.md" in result
        assert "{{PROCESSES_DIR}}" not in result

    def test_preserves_delimiters(self) -> None:
        result = render_snippet("some/path")
        assert BEGIN_DELIMITER in result
        assert END_DELIMITER in result


class TestFindTarget:
    def test_prefers_claude_md(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("# Claude\n")
        (tmp_path / "AGENTS.md").write_text("# Agents\n")
        assert find_target(tmp_path) == tmp_path / "CLAUDE.md"

    def test_falls_back_to_agents_md(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("# Agents\n")
        assert find_target(tmp_path) == tmp_path / "AGENTS.md"

    def test_defaults_to_agents_md(self, tmp_path: Path) -> None:
        target = find_target(tmp_path)
        assert target == tmp_path / "AGENTS.md"
        # File is not created — just returns the path.
        assert not target.exists()


class TestHasSnippet:
    def test_true_when_delimiters_present(self, tmp_path: Path) -> None:
        f = tmp_path / "CLAUDE.md"
        f.write_text(f"# Stuff\n{BEGIN_DELIMITER}\ncontent\n{END_DELIMITER}\n")
        assert has_snippet(f) is True

    def test_false_when_no_delimiters(self, tmp_path: Path) -> None:
        f = tmp_path / "CLAUDE.md"
        f.write_text("# Stuff\nno clarity here\n")
        assert has_snippet(f) is False

    def test_false_when_file_missing(self, tmp_path: Path) -> None:
        assert has_snippet(tmp_path / "nope.md") is False


class TestInsertSnippet:
    SNIPPET = f"{BEGIN_DELIMITER}\nclarity stuff\n{END_DELIMITER}\n"

    def test_creates_new_file(self, tmp_path: Path) -> None:
        target = tmp_path / "CLAUDE.md"
        result = insert_snippet(target, self.SNIPPET)
        assert result == "created"
        assert target.exists()
        assert BEGIN_DELIMITER in target.read_text()

    def test_appends_to_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "AGENTS.md"
        target.write_text("# Existing content\n")
        result = insert_snippet(target, self.SNIPPET)
        assert result == "appended"
        content = target.read_text()
        assert "# Existing content" in content
        assert BEGIN_DELIMITER in content

    def test_updates_in_place(self, tmp_path: Path) -> None:
        target = tmp_path / "CLAUDE.md"
        target.write_text(
            f"# Header\n\n{BEGIN_DELIMITER}\nold stuff\n{END_DELIMITER}\n\n# Footer\n"
        )
        new_snippet = f"{BEGIN_DELIMITER}\nnew stuff\n{END_DELIMITER}\n"
        result = insert_snippet(target, new_snippet)
        assert result == "updated"
        content = target.read_text()
        assert "new stuff" in content
        assert "old stuff" not in content
        assert "# Header" in content
        assert "# Footer" in content

    def test_idempotent(self, tmp_path: Path) -> None:
        """Inserting the same snippet twice produces the same result."""
        target = tmp_path / "CLAUDE.md"
        insert_snippet(target, self.SNIPPET)
        first = target.read_text()
        insert_snippet(target, self.SNIPPET)
        second = target.read_text()
        assert first == second

    def test_preserves_trailing_content(self, tmp_path: Path) -> None:
        target = tmp_path / "CLAUDE.md"
        target.write_text("# Before\n")
        insert_snippet(target, self.SNIPPET)
        content = target.read_text()
        # Existing content appears before the snippet.
        assert content.index("# Before") < content.index(BEGIN_DELIMITER)

    def test_separator_when_no_trailing_newlines(self, tmp_path: Path) -> None:
        target = tmp_path / "CLAUDE.md"
        target.write_text("no trailing newline")
        insert_snippet(target, self.SNIPPET)
        content = target.read_text()
        # Should have separation between existing content and snippet.
        assert "\n\n" in content or "\n" in content.split(BEGIN_DELIMITER)[0]
