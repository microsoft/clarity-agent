"""Tests for thinker_registry.py — thinker discovery, parsing, and selection."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from clarity_agent.protocol.packet_status import ClarityConfig
from clarity_agent.protocol.thinker_registry import (
    Prerequisites,
    ThinkerInfo,
    check_prerequisites,
    discover_thinkers,
    load_thinker,
    parse_frontmatter,
    select_thinkers,
)


def _config(disabled: list[str] | None = None) -> ClarityConfig:
    """Build a minimal ClarityConfig for select_thinkers calls.

    The TypedDict structure is strict, so tests cast a literal dict
    to ClarityConfig rather than constructing one inline (more
    readable than wrapping every call site).
    """
    return cast(
        ClarityConfig,
        {"thinkers": {"disabled": list(disabled or [])}},
    )

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_FRONTMATTER = """\
---
name: test-thinker
display_name: Test
type: ai
modes: [quick, deep]
prerequisites:
  required: [goal/problem.md, goal/stakeholders.md]
  recommended: [solution/solution.md]
tags: [testing, example]
---
# Test Thinker

This is the guide body.
"""

SAMPLE_NO_FRONTMATTER = """\
# Plain Thinker

No frontmatter here. Just markdown.
"""


def _write_thinker(
    thinker_dir: Path,
    name: str,
    content: str,
) -> Path:
    """Write a thinker file and return its path."""
    thinker_dir.mkdir(parents=True, exist_ok=True)
    path = thinker_dir / f"{name}.md"
    path.write_text(content)
    return path


def _make_protocol_with_docs(
    tmp_path: Path,
    docs: dict[str, str] | None = None,
) -> Path:
    """Create a .clarity-protocol/ with the given docs (real content)."""
    from clarity_agent.protocol.initialize import init_protocol

    init_protocol(tmp_path)
    pd = tmp_path / ".clarity-protocol"

    if docs:
        for rel_path, content in docs.items():
            (pd / rel_path).parent.mkdir(parents=True, exist_ok=True)
            (pd / rel_path).write_text(content)

    return pd


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    """parse_frontmatter splits YAML metadata from the markdown body."""

    def test_with_valid_frontmatter(self) -> None:
        meta, body = parse_frontmatter(SAMPLE_FRONTMATTER)
        assert meta["name"] == "test-thinker"
        assert meta["display_name"] == "Test"
        assert meta["type"] == "ai"
        assert meta["modes"] == ["quick", "deep"]
        assert meta["tags"] == ["testing", "example"]
        assert "# Test Thinker" in body

    def test_prerequisites_parsed(self) -> None:
        meta, _ = parse_frontmatter(SAMPLE_FRONTMATTER)
        prereqs = meta["prerequisites"]
        assert prereqs["required"] == ["goal/problem.md", "goal/stakeholders.md"]
        assert prereqs["recommended"] == ["solution/solution.md"]

    def test_without_frontmatter(self) -> None:
        meta, body = parse_frontmatter(SAMPLE_NO_FRONTMATTER)
        assert meta == {}
        assert body == SAMPLE_NO_FRONTMATTER

    def test_empty_frontmatter(self) -> None:
        text = "---\n---\n# Body\n"
        meta, body = parse_frontmatter(text)
        assert meta == {}
        assert "# Body" in body

    def test_frontmatter_not_at_start(self) -> None:
        """Frontmatter must be at the very start of the file."""
        text = "\n---\nname: oops\n---\n# Body\n"
        meta, body = parse_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_body_excludes_frontmatter(self) -> None:
        _, body = parse_frontmatter(SAMPLE_FRONTMATTER)
        assert "---" not in body.split("\n")[0]
        assert "name:" not in body


# ---------------------------------------------------------------------------
# load_thinker
# ---------------------------------------------------------------------------

class TestLoadThinker:
    """load_thinker reads a .md file and constructs ThinkerInfo."""

    def test_load_with_frontmatter(self, tmp_path: Path) -> None:
        path = _write_thinker(tmp_path / "thinkers", "test-thinker", SAMPLE_FRONTMATTER)
        info = load_thinker(path)
        assert info.name == "test-thinker"
        assert info.display_name == "Test"
        assert info.type == "ai"
        assert info.modes == ["quick", "deep"]
        assert info.tags == ["testing", "example"]
        assert info.prerequisites.required == ["goal/problem.md", "goal/stakeholders.md"]
        assert info.prerequisites.recommended == ["solution/solution.md"]
        assert "# Test Thinker" in info.guide_content
        assert info.guide_path == path

    def test_load_without_frontmatter(self, tmp_path: Path) -> None:
        path = _write_thinker(tmp_path / "thinkers", "plain-thinker", SAMPLE_NO_FRONTMATTER)
        info = load_thinker(path)
        assert info.name == "plain-thinker"
        assert info.display_name == "Plain Thinker"
        assert info.type == "ai"
        assert info.modes == ["quick", "deep"]
        assert info.tags == []
        assert info.prerequisites.required == []
        assert "# Plain Thinker" in info.guide_content

    def test_guide_content_excludes_frontmatter(self, tmp_path: Path) -> None:
        path = _write_thinker(tmp_path / "thinkers", "t", SAMPLE_FRONTMATTER)
        info = load_thinker(path)
        assert "name: test-thinker" not in info.guide_content
        assert "---" not in info.guide_content.split("\n")[0]

    def test_execution_field_parsed(self, tmp_path: Path) -> None:
        content = """\
---
name: async-thinker
type: ai
execution: async
modes: [deep]
---
# Async Thinker
"""
        path = _write_thinker(tmp_path / "thinkers", "async-thinker", content)
        info = load_thinker(path)
        assert info.execution == "async"

    def test_execution_defaults_to_sync(self, tmp_path: Path) -> None:
        path = _write_thinker(tmp_path / "thinkers", "plain", SAMPLE_NO_FRONTMATTER)
        info = load_thinker(path)
        assert info.execution == "sync"


# ---------------------------------------------------------------------------
# discover_thinkers
# ---------------------------------------------------------------------------

class TestDiscoverThinkers:
    """discover_thinkers finds all .md files in the thinkers directory."""

    def test_discovers_from_agent_dir(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        _write_thinker(agent_dir / "thinkers", "alpha", SAMPLE_NO_FRONTMATTER)
        _write_thinker(agent_dir / "thinkers", "beta", SAMPLE_NO_FRONTMATTER)
        result = discover_thinkers(agent_dir)
        names = [t.name for t in result]
        assert names == ["alpha", "beta"]

    def test_discovers_with_custom_dir(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        custom_dir = tmp_path / "custom"
        _write_thinker(agent_dir / "thinkers", "builtin", SAMPLE_NO_FRONTMATTER)
        _write_thinker(custom_dir, "custom-one", SAMPLE_NO_FRONTMATTER)
        result = discover_thinkers(agent_dir, custom_dir)
        names = [t.name for t in result]
        assert "builtin" in names
        assert "custom-one" in names

    def test_empty_dir(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        result = discover_thinkers(agent_dir)
        assert result == []

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        result = discover_thinkers(tmp_path / "nonexistent")
        assert result == []

    def test_ignores_non_md_files(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        thinker_dir = agent_dir / "thinkers"
        thinker_dir.mkdir(parents=True)
        _write_thinker(thinker_dir, "real", SAMPLE_NO_FRONTMATTER)
        (thinker_dir / "notes.txt").write_text("not a thinker")
        (thinker_dir / "data.json").write_text("{}")
        result = discover_thinkers(agent_dir)
        assert len(result) == 1
        assert result[0].name == "real"

    def test_sorted_by_name(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        _write_thinker(agent_dir / "thinkers", "zebra", SAMPLE_NO_FRONTMATTER)
        _write_thinker(agent_dir / "thinkers", "alpha", SAMPLE_NO_FRONTMATTER)
        result = discover_thinkers(agent_dir)
        assert [t.name for t in result] == ["alpha", "zebra"]


# ---------------------------------------------------------------------------
# check_prerequisites
# ---------------------------------------------------------------------------

class TestCheckPrerequisites:
    """check_prerequisites validates that required documents are written."""

    def test_all_satisfied(self, tmp_path: Path) -> None:
        pd = _make_protocol_with_docs(tmp_path, {
            "goal/problem.md": "# Problem\n\nReal content.\n",
            "goal/stakeholders.md": "# Stakeholders\n\nReal content.\n",
        })
        thinker = ThinkerInfo(
            name="t", display_name="T", type="ai", modes=["deep"],
            prerequisites=Prerequisites(
                required=["goal/problem.md", "goal/stakeholders.md"],
            ),
            tags=[], guide_path=Path("x"), guide_content="",
        )
        result = check_prerequisites(thinker, pd)
        assert result.satisfied is True
        assert result.missing_required == []

    def test_missing_required(self, tmp_path: Path) -> None:
        pd = _make_protocol_with_docs(tmp_path, {
            "goal/problem.md": "# Problem\n\nReal content.\n",
            # stakeholders.md left as template
        })
        thinker = ThinkerInfo(
            name="t", display_name="T", type="ai", modes=["deep"],
            prerequisites=Prerequisites(
                required=["goal/problem.md", "goal/stakeholders.md"],
            ),
            tags=[], guide_path=Path("x"), guide_content="",
        )
        result = check_prerequisites(thinker, pd)
        assert result.satisfied is False
        assert "goal/stakeholders.md" in result.missing_required

    def test_missing_recommended_still_satisfied(self, tmp_path: Path) -> None:
        pd = _make_protocol_with_docs(tmp_path, {
            "goal/problem.md": "# Problem\n\nReal content.\n",
        })
        thinker = ThinkerInfo(
            name="t", display_name="T", type="ai", modes=["deep"],
            prerequisites=Prerequisites(
                required=["goal/problem.md"],
                recommended=["solution/solution.md"],
            ),
            tags=[], guide_path=Path("x"), guide_content="",
        )
        result = check_prerequisites(thinker, pd)
        assert result.satisfied is True
        assert "solution/solution.md" in result.missing_recommended

    def test_template_counts_as_missing(self, tmp_path: Path) -> None:
        """A document with template markers is not considered ready."""
        pd = _make_protocol_with_docs(tmp_path)
        # goal/problem.md is still the init_protocol template with [TBD] markers
        thinker = ThinkerInfo(
            name="t", display_name="T", type="ai", modes=["deep"],
            prerequisites=Prerequisites(required=["goal/problem.md"]),
            tags=[], guide_path=Path("x"), guide_content="",
        )
        result = check_prerequisites(thinker, pd)
        assert result.satisfied is False
        assert "goal/problem.md" in result.missing_required

    def test_nonexistent_file_counts_as_missing(self, tmp_path: Path) -> None:
        pd = _make_protocol_with_docs(tmp_path)
        thinker = ThinkerInfo(
            name="t", display_name="T", type="ai", modes=["deep"],
            prerequisites=Prerequisites(required=["nonexistent.md"]),
            tags=[], guide_path=Path("x"), guide_content="",
        )
        result = check_prerequisites(thinker, pd)
        assert result.satisfied is False

    def test_no_prerequisites_always_satisfied(self, tmp_path: Path) -> None:
        pd = _make_protocol_with_docs(tmp_path)
        thinker = ThinkerInfo(
            name="t", display_name="T", type="ai", modes=["deep"],
            prerequisites=Prerequisites(),
            tags=[], guide_path=Path("x"), guide_content="",
        )
        result = check_prerequisites(thinker, pd)
        assert result.satisfied is True


# ---------------------------------------------------------------------------
# select_thinkers
# ---------------------------------------------------------------------------

class TestSelectThinkers:
    """select_thinkers filters thinkers by config, mode, and prerequisites."""

    def _setup(
        self,
        tmp_path: Path,
        *,
        thinker_names: list[str] | None = None,
        docs: dict[str, str] | None = None,
    ) -> tuple[Path, Path]:
        """Create an agent dir with thinkers and a protocol dir with docs."""
        agent_dir = tmp_path / "agent"
        if thinker_names is None:
            thinker_names = ["alpha-thinker", "beta-thinker"]
        for name in thinker_names:
            content = f"""\
---
name: {name}
type: ai
modes: [quick, deep]
prerequisites:
  required: [goal/problem.md]
tags: []
---
# {name}

Guide content.
"""
            _write_thinker(agent_dir / "thinkers", name, content)

        default_docs: dict[str, str] = {
            "goal/problem.md": "# Problem\n\nReal content.\n",
        }
        pd = _make_protocol_with_docs(
            tmp_path / "project",
            default_docs if docs is None else docs,
        )
        return agent_dir, pd

    def test_all_eligible_thinkers_selected(self, tmp_path: Path) -> None:
        agent_dir, pd = self._setup(tmp_path)
        result = select_thinkers(agent_dir, pd, config=_config())
        assert len(result) == 2

    def test_filter_by_disabled_list(self, tmp_path: Path) -> None:
        agent_dir, pd = self._setup(tmp_path)
        result = select_thinkers(
            agent_dir, pd, config=_config(disabled=["beta-thinker"]),
        )
        names = [t.name for t in result]
        assert "alpha-thinker" in names
        assert "beta-thinker" not in names

    def test_filter_by_mode(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        # deep-only thinker
        _write_thinker(agent_dir / "thinkers", "deep-only", """\
---
name: deep-only
type: ai
modes: [deep]
prerequisites:
  required: [goal/problem.md]
---
# Deep Only
""")
        pd = _make_protocol_with_docs(tmp_path / "project", {
            "goal/problem.md": "# Problem\n\nReal.\n",
        })
        deep_result = select_thinkers(agent_dir, pd, config=_config(), mode="deep")
        quick_result = select_thinkers(agent_dir, pd, config=_config(), mode="quick")
        assert len(deep_result) == 1
        assert len(quick_result) == 0

    def test_filter_by_prerequisites(self, tmp_path: Path) -> None:
        """Thinkers with unmet required prerequisites are excluded."""
        agent_dir, pd = self._setup(
            tmp_path,
            docs={},  # No real content — all docs are templates
        )
        result = select_thinkers(agent_dir, pd, config=_config())
        assert result == []

    def test_custom_dir_thinkers_included(self, tmp_path: Path) -> None:
        """Custom-dir thinkers are discovered and included."""
        agent_dir, pd = self._setup(tmp_path, thinker_names=["builtin"])
        custom_dir = tmp_path / "custom"
        _write_thinker(custom_dir, "my-custom", """\
---
name: my-custom
type: ai
modes: [deep]
prerequisites:
  required: [goal/problem.md]
---
# Custom
""")
        result = select_thinkers(
            agent_dir, pd, config=_config(), custom_dir=custom_dir,
        )
        names = [t.name for t in result]
        assert "builtin" in names
        assert "my-custom" in names

    def test_loads_config_from_protocol_dir(self, tmp_path: Path) -> None:
        """When config=None, loads from protocol_dir/config.json."""
        agent_dir, pd = self._setup(tmp_path, thinker_names=["security-thinker"])
        result = select_thinkers(agent_dir, pd, config=None)
        assert len(result) == 1
        assert result[0].name == "security-thinker"
