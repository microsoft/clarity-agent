"""Tests for clarity_agent.setup.project."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from clarity_agent.setup.installer import CLARITY_DIR, Outcome
from clarity_agent.setup.layout import (
    PROTOCOL_DIR_DOT,
    LayoutBroken,
    Mode,
    ProjectLayout,
    detect_layout,
)
from clarity_agent.setup.project import (
    AgentDirStyle,
    create_project_wrapper,
    create_protocol_dir,
    provide_agent_dir,
    run_project_embed,
)


def _layout(target: Path, agent: Path | None = None) -> ProjectLayout:
    """EMBEDDED-mode layout for *target* — matches what
    ``run_project_embed`` builds at the top of its orchestrator."""
    return ProjectLayout(
        mode=Mode.EMBEDDED,
        project_dir=target,
        clarity_agent_dir=agent if agent is not None else target / CLARITY_DIR,
        protocol_dir=target / PROTOCOL_DIR_DOT,
    )

# ---------------------------------------------------------------------------
# create_protocol_dir
# ---------------------------------------------------------------------------

class TestCreateProtocolDir:
    def test_creates_directory(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        r = create_protocol_dir(_layout(tmp_path))
        assert r.outcome == Outcome.OK
        assert (tmp_path / ".clarity-protocol").is_dir()

    def test_idempotent(self, tmp_path: Path) -> None:
        (tmp_path / ".clarity-protocol").mkdir()
        r = create_protocol_dir(_layout(tmp_path))
        assert r.outcome == Outcome.OK
        assert "already" in r.message


# ---------------------------------------------------------------------------
# create_project_wrapper
# ---------------------------------------------------------------------------

class TestCreateProjectWrapper:
    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-only")
    def test_unix_wrapper_is_executable(self, tmp_path: Path) -> None:
        r = create_project_wrapper(_layout(tmp_path, tmp_path))
        assert r.outcome == Outcome.OK
        wrapper = tmp_path / "clarity"
        assert wrapper.exists()
        assert wrapper.stat().st_mode & 0o111
        content = wrapper.read_text()
        assert "command -v clarity" in content
        assert "not installed" in content

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_windows_wrappers_created(self, tmp_path: Path) -> None:
        r = create_project_wrapper(_layout(tmp_path, tmp_path))
        assert r.outcome == Outcome.OK
        assert (tmp_path / "clarity.ps1").exists()
        assert (tmp_path / "clarity.bat").exists()


# ---------------------------------------------------------------------------
# provide_agent_dir
# ---------------------------------------------------------------------------

def _fake_install(root: Path) -> Path:
    """A stand-in for a machine-wide Clarity install: the protocol
    content a project reads, plus the bulky dev artifacts (venv, git
    checkout, Rust build cache) a copy must not drag along."""
    agent = root / "install"
    (agent / "processes").mkdir(parents=True)
    (agent / "processes" / "guide.md").write_text("guidance")
    (agent / "thinkers").mkdir()
    (agent / "thinkers" / "skeptic.md").write_text("be skeptical")
    (agent / ".git").mkdir()
    (agent / ".git" / "HEAD").write_text("ref: refs/heads/main")
    (agent / ".venv" / "bin").mkdir(parents=True)
    (agent / "src-tauri" / "target").mkdir(parents=True)
    (agent / "src-tauri" / "target" / "huge.bin").write_text("x" * 1024)
    return agent


class TestProvideAgentDir:
    """The step that makes an embedded project a *clean* EMBEDDED
    layout rather than a PARTIAL_EMBEDDED_INSTALL."""

    def test_link_exposes_install_content(self, tmp_path: Path) -> None:
        project = tmp_path / "repo"
        project.mkdir()
        agent = _fake_install(tmp_path)

        r = provide_agent_dir(_layout(project, agent))

        assert r.outcome == Outcome.OK
        dest = project / CLARITY_DIR
        assert dest.is_dir()
        assert dest.resolve() == agent.resolve()
        assert (dest / "processes" / "guide.md").read_text() == "guidance"

    def test_link_tracks_the_install(self, tmp_path: Path) -> None:
        """A link, not a copy: later changes to the install show up."""
        project = tmp_path / "repo"
        project.mkdir()
        agent = _fake_install(tmp_path)
        provide_agent_dir(_layout(project, agent))

        (agent / "processes" / "new.md").write_text("added later")

        assert (project / CLARITY_DIR / "processes" / "new.md").exists()

    def test_link_idempotent(self, tmp_path: Path) -> None:
        project = tmp_path / "repo"
        project.mkdir()
        agent = _fake_install(tmp_path)
        provide_agent_dir(_layout(project, agent))

        r = provide_agent_dir(_layout(project, agent))

        assert r.outcome == Outcome.OK
        assert "already links" in r.message

    def test_link_repoints_when_install_moves(self, tmp_path: Path) -> None:
        project = tmp_path / "repo"
        project.mkdir()
        agent = _fake_install(tmp_path)
        provide_agent_dir(_layout(project, agent))

        moved = tmp_path / "moved"
        agent.rename(moved)
        r = provide_agent_dir(_layout(project, moved))

        assert r.outcome == Outcome.OK
        assert (project / CLARITY_DIR).resolve() == moved.resolve()

    def test_copy_snapshots_content_without_dev_artifacts(
        self, tmp_path: Path,
    ) -> None:
        project = tmp_path / "repo"
        project.mkdir()
        agent = _fake_install(tmp_path)

        r = provide_agent_dir(_layout(project, agent), AgentDirStyle.COPY)

        assert r.outcome == Outcome.OK
        dest = project / CLARITY_DIR
        assert not dest.is_symlink()
        assert dest.resolve() == dest  # a real directory, not a link
        assert (dest / "processes" / "guide.md").read_text() == "guidance"
        assert (dest / "thinkers" / "skeptic.md").read_text() == "be skeptical"
        # Allowlist, not denylist: everything else stays behind, however
        # it's named.  (src-tauri/target alone is gigabytes in practice.)
        assert sorted(p.name for p in dest.iterdir()) == ["processes", "thinkers"]

    def test_copy_drops_content_removed_upstream(self, tmp_path: Path) -> None:
        project = tmp_path / "repo"
        project.mkdir()
        agent = _fake_install(tmp_path)
        provide_agent_dir(_layout(project, agent), AgentDirStyle.COPY)

        (agent / "processes" / "guide.md").unlink()
        provide_agent_dir(_layout(project, agent), AgentDirStyle.COPY)

        assert not (project / CLARITY_DIR / "processes" / "guide.md").exists()

    def test_copy_fails_when_install_has_no_content(self, tmp_path: Path) -> None:
        project = tmp_path / "repo"
        project.mkdir()
        empty = tmp_path / "not-an-install"
        empty.mkdir()

        r = provide_agent_dir(_layout(project, empty), AgentDirStyle.COPY)

        assert r.outcome == Outcome.FAIL

    def test_copy_replaces_a_link(self, tmp_path: Path) -> None:
        project = tmp_path / "repo"
        project.mkdir()
        agent = _fake_install(tmp_path)
        provide_agent_dir(_layout(project, agent))

        r = provide_agent_dir(_layout(project, agent), AgentDirStyle.COPY)

        assert r.outcome == Outcome.OK
        dest = project / CLARITY_DIR
        assert not dest.is_symlink()
        # The link's target is left intact.
        assert (agent / "processes" / "guide.md").exists()

    def test_copy_refreshes_in_place(self, tmp_path: Path) -> None:
        project = tmp_path / "repo"
        project.mkdir()
        agent = _fake_install(tmp_path)
        provide_agent_dir(_layout(project, agent), AgentDirStyle.COPY)

        (agent / "processes" / "new.md").write_text("added later")
        r = provide_agent_dir(_layout(project, agent), AgentDirStyle.COPY)

        assert r.outcome == Outcome.OK
        assert (project / CLARITY_DIR / "processes" / "new.md").exists()

    def test_link_leaves_a_real_directory_alone(self, tmp_path: Path) -> None:
        """A full clone (or an earlier --copy) is content we didn't
        create; warn rather than delete it."""
        project = tmp_path / "repo"
        project.mkdir()
        agent = _fake_install(tmp_path)
        existing = project / CLARITY_DIR
        existing.mkdir()
        (existing / "local.md").write_text("do not delete me")

        r = provide_agent_dir(_layout(project, agent))

        assert r.outcome == Outcome.WARN
        assert (existing / "local.md").read_text() == "do not delete me"

    def test_fails_on_non_directory_in_the_way(self, tmp_path: Path) -> None:
        project = tmp_path / "repo"
        project.mkdir()
        agent = _fake_install(tmp_path)
        (project / CLARITY_DIR).write_text("not a directory")

        r = provide_agent_dir(_layout(project, agent))

        assert r.outcome == Outcome.FAIL

    def test_skips_when_install_lives_inside_the_project(
        self, tmp_path: Path,
    ) -> None:
        """The clarity-agent source repo dogfooding itself — detection
        recognizes it structurally, so no marker is needed."""
        r = provide_agent_dir(_layout(tmp_path, tmp_path))

        assert r.outcome == Outcome.SKIP
        assert not (tmp_path / CLARITY_DIR).exists()


# ---------------------------------------------------------------------------
# run_project_embed
# ---------------------------------------------------------------------------

class TestRunProjectEmbed:
    def test_happy_path(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        agent = tmp_path  # snippet template lives here

        results = run_project_embed(tmp_path, agent)

        assert not any(r.outcome == Outcome.FAIL for r in results)
        assert (tmp_path / ".clarity-protocol").is_dir()

    def test_result_is_a_clean_embedded_layout(self, tmp_path: Path) -> None:
        """The whole point: what embed leaves on disk must be something
        ``detect_layout`` accepts, or the app refuses to open it."""
        project = tmp_path / "repo"
        project.mkdir()
        (project / ".git").mkdir()
        agent = _fake_install(tmp_path)

        results = run_project_embed(project, agent)
        assert not any(r.outcome == Outcome.FAIL for r in results)

        layout = detect_layout(project, bundled_clarity_agent_dir=agent)
        assert not isinstance(layout, LayoutBroken)
        assert isinstance(layout, ProjectLayout)
        assert layout.mode is Mode.EMBEDDED
        assert layout.clarity_agent_dir == agent.resolve()

    def test_copy_style_is_also_a_clean_layout(self, tmp_path: Path) -> None:
        project = tmp_path / "repo"
        project.mkdir()
        (project / ".git").mkdir()
        agent = _fake_install(tmp_path)

        results = run_project_embed(project, agent, style=AgentDirStyle.COPY)
        assert not any(r.outcome == Outcome.FAIL for r in results)

        layout = detect_layout(project, bundled_clarity_agent_dir=agent)
        assert isinstance(layout, ProjectLayout)
        assert layout.mode is Mode.EMBEDDED
        assert layout.clarity_agent_dir == (project / CLARITY_DIR).resolve()
        # A copy is committable, so it isn't gitignored.
        assert CLARITY_DIR not in (project / ".gitignore").read_text()

    def test_link_style_is_gitignored(self, tmp_path: Path) -> None:
        project = tmp_path / "repo"
        project.mkdir()
        (project / ".git").mkdir()
        agent = _fake_install(tmp_path)

        run_project_embed(project, agent)

        assert f"/{CLARITY_DIR}" in (project / ".gitignore").read_text()

    def test_fails_when_dir_missing(self, tmp_path: Path) -> None:
        results = run_project_embed(tmp_path / "nope", tmp_path)
        assert results[0].outcome == Outcome.FAIL
        assert "not found" in results[0].message

    def test_fails_when_not_a_git_repo(self, tmp_path: Path) -> None:
        results = run_project_embed(tmp_path, tmp_path)
        assert results[0].outcome == Outcome.FAIL
        assert "Not a git repository" in results[0].message

    def test_on_step_callback(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        called = []
        run_project_embed(tmp_path, tmp_path, on_step=called.append)
        assert len(called) > 0

    def test_idempotent(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        run_project_embed(tmp_path, tmp_path)
        results = run_project_embed(tmp_path, tmp_path)
        assert not any(r.outcome == Outcome.FAIL for r in results)
