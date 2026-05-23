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
    Mode,
    ProjectLayout,
    detect_layout,
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
        assert layout is not None
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
        assert layout is not None
        assert layout.mode is Mode.USERSPACE
        # USERSPACE means clarity-agent lives outside the project — in
        # the bundle the caller supplied.
        assert layout.clarity_agent_dir == bundle.resolve()
        assert layout.protocol_dir == project / PROTOCOL_DIR_VISIBLE

    def test_embedded_via_dotted_protocol_dir_alone(
        self, tmp_path: Path,
    ) -> None:
        # No ``.clarity-agent/`` install marker but ``.clarity-protocol/``
        # exists — someone ran ``protocol.initialize`` in a git repo
        # without a full embedded install.  We still treat it as
        # EMBEDDED so the rendered paths are relative.
        project = tmp_path / "repo"
        project.mkdir()
        (project / PROTOCOL_DIR_DOT).mkdir()

        layout = detect_layout(
            project, bundled_clarity_agent_dir=_make_bundle(tmp_path),
        )
        assert layout is not None
        assert layout.mode is Mode.EMBEDDED
        assert layout.protocol_dir == project / PROTOCOL_DIR_DOT


# ---------------------------------------------------------------------------
# Detection — None cases (no implicit creation, no ambiguous guessing)
# ---------------------------------------------------------------------------


class TestDetectLayoutNoneCases:
    def test_returns_none_for_empty_project(self, tmp_path: Path) -> None:
        project = tmp_path / "blank"
        project.mkdir()
        assert (
            detect_layout(
                project, bundled_clarity_agent_dir=_make_bundle(tmp_path),
            )
            is None
        )

    def test_returns_none_for_ambiguous_both_protocol_dirs_present(
        self, tmp_path: Path,
    ) -> None:
        # Both protocol directory names present is a state we
        # deliberately refuse to interpret — the caller should
        # surface the conflict rather than us picking one silently.
        project = tmp_path / "ambiguous"
        project.mkdir()
        (project / PROTOCOL_DIR_DOT).mkdir()
        (project / PROTOCOL_DIR_VISIBLE).mkdir()

        # Note: ``.clarity-agent/`` is NOT present, so the EMBEDDED
        # short-circuit (which takes precedence) doesn't fire.
        assert (
            detect_layout(
                project, bundled_clarity_agent_dir=_make_bundle(tmp_path),
            )
            is None
        )

    def test_clarity_agent_subdir_takes_precedence_over_ambiguous_protocol_dirs(
        self, tmp_path: Path,
    ) -> None:
        # When ``.clarity-agent/`` is present, the EMBEDDED short-
        # circuit fires before the ambiguity check — the install
        # marker is unambiguous regardless of whatever stray protocol
        # directories happen to be lying around.  Documents the
        # precedence in the docstring.
        project = tmp_path / "embedded-with-stray"
        project.mkdir()
        (project / EMBEDDED_AGENT_SUBDIR).mkdir()
        (project / PROTOCOL_DIR_DOT).mkdir()
        (project / PROTOCOL_DIR_VISIBLE).mkdir()

        layout = detect_layout(
            project, bundled_clarity_agent_dir=_make_bundle(tmp_path),
        )
        assert layout is not None
        assert layout.mode is Mode.EMBEDDED


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
