"""Tests for :mod:`clarity_agent.setup.layout`.

Covers the detection state matrix from
:func:`~clarity_agent.setup.layout.detect_layout`'s docstring, plus
the path-form invariants on :class:`ProjectLayout` (relative paths
in EMBEDDED, absolute in USERSPACE) — the asymmetry the whole
two-mode abstraction exists to capture.
"""

from __future__ import annotations

from pathlib import Path

from clarity_agent.setup.layout import (
    EMBEDDED_AGENT_SUBDIR,
    PROTOCOL_DIR_DOT,
    PROTOCOL_DIR_VISIBLE,
    LayoutBroken,
    Mode,
    ProjectLayout,
    detect_layout,
    looks_like_clarity_agent_source,
    looks_like_code_directory,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_bundle(tmp_path: Path) -> Path:
    """A minimal bundled clarity-agent dir (just enough for layout
    construction; nothing inside it is read by detect_layout)."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "processes").mkdir()
    return bundle


# ---------------------------------------------------------------------------
# Detection — happy paths
# ---------------------------------------------------------------------------


class TestDetectLayoutHappyPaths:
    def test_embedded_when_clarity_agent_subdir_present(
        self, tmp_path: Path,
    ) -> None:
        project = tmp_path / "repo"
        project.mkdir()
        (project / EMBEDDED_AGENT_SUBDIR).mkdir()
        (project / PROTOCOL_DIR_DOT).mkdir()

        layout = detect_layout(
            project, bundled_clarity_agent_dir=_make_bundle(tmp_path),
        )
        assert isinstance(layout, ProjectLayout)
        assert layout.mode is Mode.EMBEDDED
        # clarity_agent_dir points at the in-repo install, not the
        # bundle — the embedded install marker is the source of truth.
        assert layout.clarity_agent_dir == (project / EMBEDDED_AGENT_SUBDIR).resolve()
        assert layout.protocol_dir == project / PROTOCOL_DIR_DOT

    def test_userspace_when_visible_protocol_dir_present(
        self, tmp_path: Path,
    ) -> None:
        project = tmp_path / "userspace"
        project.mkdir()
        (project / PROTOCOL_DIR_VISIBLE).mkdir()
        bundle = _make_bundle(tmp_path)

        layout = detect_layout(project, bundled_clarity_agent_dir=bundle)
        assert isinstance(layout, ProjectLayout)
        assert layout.mode is Mode.USERSPACE
        # USERSPACE means clarity-agent lives outside the project — in
        # the bundle the caller supplied.
        assert layout.clarity_agent_dir == bundle.resolve()
        assert layout.protocol_dir == project / PROTOCOL_DIR_VISIBLE

    def test_clean_embedded_requires_both_markers(
        self, tmp_path: Path,
    ) -> None:
        # Clean EMBEDDED needs ``.clarity-agent/`` AND ``.clarity-protocol/``
        # — both markers consistent.  This is the post-install
        # steady state.
        project = tmp_path / "repo"
        project.mkdir()
        (project / EMBEDDED_AGENT_SUBDIR).mkdir()
        (project / PROTOCOL_DIR_DOT).mkdir()

        layout = detect_layout(
            project, bundled_clarity_agent_dir=_make_bundle(tmp_path),
        )
        assert isinstance(layout, ProjectLayout)
        assert layout.mode is Mode.EMBEDDED
        assert layout.protocol_dir == project / PROTOCOL_DIR_DOT


class TestDetectLayoutClarityAgentSource:
    """The clarity-agent source repo is its own mode, detected
    structurally (``clarity.py`` at root + ``src/clarity_agent/``
    subdir).  Takes precedence over everything else — including the
    ``.clarity-protocol/`` it carries, which would otherwise look
    like a PARTIAL_EMBEDDED_INSTALL.
    """

    def _make_source_repo(self, tmp_path: Path) -> Path:
        repo = tmp_path / "clarity-agent"
        repo.mkdir()
        (repo / "clarity.py").write_text("# entry point\n")
        (repo / "src").mkdir()
        (repo / "src" / "clarity_agent").mkdir()
        return repo

    def test_detects_source_repo(self, tmp_path: Path) -> None:
        repo = self._make_source_repo(tmp_path)
        layout = detect_layout(
            repo, bundled_clarity_agent_dir=_make_bundle(tmp_path),
        )
        assert isinstance(layout, ProjectLayout)
        assert layout.mode is Mode.CLARITY_AGENT_SOURCE
        # The repo IS the clarity-agent — clarity_agent_dir points
        # at the project root, not at a bundled dir.
        assert layout.clarity_agent_dir == repo
        assert layout.protocol_dir == repo / PROTOCOL_DIR_DOT

    def test_source_repo_takes_precedence_over_dotted_protocol(
        self, tmp_path: Path,
    ) -> None:
        # The source repo has its own ``.clarity-protocol/`` (the
        # dev's protocol dir for working on Clarity itself).  Under
        # the strict state table, ``.clarity-protocol/`` without
        # ``.clarity-agent/`` is PARTIAL_EMBEDDED_INSTALL — but the
        # source-repo check runs first, so we don't trip that path.
        repo = self._make_source_repo(tmp_path)
        (repo / PROTOCOL_DIR_DOT).mkdir()

        layout = detect_layout(
            repo, bundled_clarity_agent_dir=_make_bundle(tmp_path),
        )
        assert isinstance(layout, ProjectLayout)
        assert layout.mode is Mode.CLARITY_AGENT_SOURCE

    def test_partial_source_markers_not_recognized(
        self, tmp_path: Path,
    ) -> None:
        # Both markers are required — just one (e.g. a stray
        # ``clarity.py`` in some unrelated repo) must not falsely
        # claim the source-repo mode.
        repo = tmp_path / "not-the-source"
        repo.mkdir()
        (repo / "clarity.py").write_text("# unrelated\n")
        # No src/clarity_agent/ — shouldn't match.
        assert not looks_like_clarity_agent_source(repo)
        assert detect_layout(
            repo, bundled_clarity_agent_dir=_make_bundle(tmp_path),
        ) is None


# ---------------------------------------------------------------------------
# Detection — None / LayoutBroken cases
# ---------------------------------------------------------------------------


class TestDetectLayoutBrokenAndNone:
    def test_returns_none_for_empty_project(self, tmp_path: Path) -> None:
        # No Clarity markers → caller decides what to do (flow 1
        # create new, or flow 3 prompt).
        project = tmp_path / "blank"
        project.mkdir()
        assert (
            detect_layout(
                project, bundled_clarity_agent_dir=_make_bundle(tmp_path),
            )
            is None
        )

    def test_ambiguous_both_protocol_dirs_returns_broken_variant(
        self, tmp_path: Path,
    ) -> None:
        # Both protocol directory names present is a broken state we
        # refuse to interpret — return the specific LayoutBroken
        # variant so the caller can word an actionable prompt
        # ("you have both `.clarity-protocol/` and `Clarity Protocol/`;
        # remove one").
        project = tmp_path / "ambiguous"
        project.mkdir()
        (project / PROTOCOL_DIR_DOT).mkdir()
        (project / PROTOCOL_DIR_VISIBLE).mkdir()

        assert (
            detect_layout(
                project, bundled_clarity_agent_dir=_make_bundle(tmp_path),
            )
            is LayoutBroken.AMBIGUOUS_PROTOCOL_DIRS
        )

    def test_partial_embedded_install_dotted_only(
        self, tmp_path: Path,
    ) -> None:
        # ``.clarity-protocol/`` without ``.clarity-agent/`` — looks
        # like someone ran ``protocol.initialize`` in a git repo
        # without running the full embedded install.  Used to be
        # silently treated as EMBEDDED; under the strict model it's
        # broken, and the launcher should surface a repair prompt.
        project = tmp_path / "partial"
        project.mkdir()
        (project / PROTOCOL_DIR_DOT).mkdir()

        assert (
            detect_layout(
                project, bundled_clarity_agent_dir=_make_bundle(tmp_path),
            )
            is LayoutBroken.PARTIAL_EMBEDDED_INSTALL
        )

    def test_partial_embedded_install_agent_only(
        self, tmp_path: Path,
    ) -> None:
        # The other half of the partial-install case: somehow
        # ``.clarity-agent/`` got laid down without a protocol dir.
        # Same remedy: complete the install.
        project = tmp_path / "partial-2"
        project.mkdir()
        (project / EMBEDDED_AGENT_SUBDIR).mkdir()

        assert (
            detect_layout(
                project, bundled_clarity_agent_dir=_make_bundle(tmp_path),
            )
            is LayoutBroken.PARTIAL_EMBEDDED_INSTALL
        )


# ---------------------------------------------------------------------------
# Structural predicates used at flow-3 prompt time
# ---------------------------------------------------------------------------


class TestLooksLikeCodeDirectory:
    def test_git_repo(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        assert looks_like_code_directory(tmp_path) is True

    def test_python_project(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        assert looks_like_code_directory(tmp_path) is True

    def test_node_project(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        assert looks_like_code_directory(tmp_path) is True

    def test_rust_project(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("[package]\n")
        assert looks_like_code_directory(tmp_path) is True

    def test_go_project(self, tmp_path: Path) -> None:
        (tmp_path / "go.mod").write_text("module x\n")
        assert looks_like_code_directory(tmp_path) is True

    def test_ruby_project(self, tmp_path: Path) -> None:
        (tmp_path / "Gemfile").write_text("# ruby\n")
        assert looks_like_code_directory(tmp_path) is True

    def test_plain_workspace_directory(self, tmp_path: Path) -> None:
        # Non-technical user's project folder — just markdown files
        # or similar.  Should NOT match (flow-3 prompt should then
        # only offer USERSPACE).
        (tmp_path / "notes.md").write_text("# my notes\n")
        (tmp_path / "research").mkdir()
        assert looks_like_code_directory(tmp_path) is False


# ---------------------------------------------------------------------------
# ProjectLayout — path-form invariants (the asymmetry that justifies modes)
# ---------------------------------------------------------------------------


class TestProjectLayoutPathForms:
    def test_userspace_renders_absolute_processes_dir(
        self, tmp_path: Path,
    ) -> None:
        bundle = _make_bundle(tmp_path)
        project = tmp_path / "p"
        project.mkdir()
        layout = ProjectLayout(
            mode=Mode.USERSPACE,
            project_dir=project,
            clarity_agent_dir=bundle,
            protocol_dir=project / PROTOCOL_DIR_VISIBLE,
        )
        rendered = layout.processes_dir_for_rendering()
        assert Path(rendered).is_absolute()
        assert rendered == (bundle / "processes").as_posix()

    def test_embedded_renders_relative_processes_dir(
        self, tmp_path: Path,
    ) -> None:
        project = tmp_path / "p"
        project.mkdir()
        layout = ProjectLayout(
            mode=Mode.EMBEDDED,
            project_dir=project,
            clarity_agent_dir=project / EMBEDDED_AGENT_SUBDIR,
            protocol_dir=project / PROTOCOL_DIR_DOT,
        )
        rendered = layout.processes_dir_for_rendering()
        # Repo-relative — no absolute path, no tmp_path leakage.
        assert not Path(rendered).is_absolute()
        assert rendered == f"{EMBEDDED_AGENT_SUBDIR}/processes"
        assert str(tmp_path) not in rendered

    def test_protocol_dir_name_strips_to_leaf(self, tmp_path: Path) -> None:
        # The substitution into the rendered body wants the bare
        # directory name (``.clarity-protocol`` or ``Clarity Protocol``)
        # — absolute paths would look wrong inline.
        project = tmp_path / "p"
        project.mkdir()
        embedded = ProjectLayout(
            mode=Mode.EMBEDDED,
            project_dir=project,
            clarity_agent_dir=project / EMBEDDED_AGENT_SUBDIR,
            protocol_dir=project / PROTOCOL_DIR_DOT,
        )
        assert embedded.protocol_dir_name() == PROTOCOL_DIR_DOT

        userspace = ProjectLayout(
            mode=Mode.USERSPACE,
            project_dir=project,
            clarity_agent_dir=_make_bundle(tmp_path),
            protocol_dir=project / PROTOCOL_DIR_VISIBLE,
        )
        assert userspace.protocol_dir_name() == PROTOCOL_DIR_VISIBLE

    def test_agents_md_always_at_project_root(self, tmp_path: Path) -> None:
        # AGENTS.md is the universal LLM-coding-agent convention; the
        # whole architecture rests on it living at the project root.
        project = tmp_path / "p"
        project.mkdir()
        layout = ProjectLayout(
            mode=Mode.USERSPACE,
            project_dir=project,
            clarity_agent_dir=_make_bundle(tmp_path),
            protocol_dir=project / PROTOCOL_DIR_VISIBLE,
        )
        assert layout.agents_md == project / "AGENTS.md"
