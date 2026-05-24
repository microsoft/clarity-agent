"""Tests for :func:`clarity_agent.setup.project.setup_userspace_project`.

The lightweight counterpart to ``run_project_embed`` — creates
``Clarity Protocol/`` + its template structure + writes AGENTS.md.
Used by the launcher's ``create_project`` endpoint when the user
picks "Set up as userspace project" in flow 1 (Create new) or in
flow 3 (Open ambiguous → user confirmed userspace).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from clarity_agent.setup.layout import Mode, PROTOCOL_DIR_VISIBLE
from clarity_agent.setup.project import setup_userspace_project
from clarity_agent.setup.snippet import (
    BEGIN_DELIMITER,
    END_DELIMITER,
    snippet_path,
)


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    """A bundle dir with ``processes/`` and a copy of the snippet
    template at its expected path — enough for ``init_protocol`` /
    ``render_snippet`` / ``ensure_agents_md`` to function."""
    b = tmp_path / "bundle"
    setup_dir = b / "src" / "clarity_agent" / "setup"
    setup_dir.mkdir(parents=True)
    shutil.copy2(snippet_path(), setup_dir / "snippet.md")
    (b / "processes").mkdir()
    return b


class TestSetupUserspaceProject:
    def test_creates_protocol_dir_and_template_structure(
        self, tmp_path: Path, bundle: Path,
    ) -> None:
        project = tmp_path / "newproj"
        # Project dir doesn't exist yet; setup must create it.

        layout = setup_userspace_project(project, bundle)

        assert layout.mode is Mode.USERSPACE
        assert project.is_dir()
        protocol = project / PROTOCOL_DIR_VISIBLE
        assert protocol.is_dir()
        # init_protocol lays down the template subdir structure.
        for sub in ("goal", "solution", "failures", "decisions"):
            assert (protocol / sub).is_dir(), f"missing template subdir: {sub}"
        # And the build-database config.
        assert (protocol / "config.json").exists()

    def test_writes_agents_md_with_clarity_block(
        self, tmp_path: Path, bundle: Path,
    ) -> None:
        # End-to-end: setup must produce a fully-rendered AGENTS.md
        # so the next session-start sees a valid project without
        # any further setup machinery firing.
        project = tmp_path / "newproj"
        layout = setup_userspace_project(project, bundle)

        agents = layout.agents_md
        assert agents.exists()
        content = agents.read_text(encoding="utf-8")
        assert BEGIN_DELIMITER in content
        assert END_DELIMITER in content
        # USERSPACE mode → visible protocol-dir name appears in body.
        assert PROTOCOL_DIR_VISIBLE in content

    def test_idempotent_on_existing_userspace_project(
        self, tmp_path: Path, bundle: Path,
    ) -> None:
        # Calling on a project that's already set up must be safe —
        # the user might reopen via flow 3 and re-confirm userspace,
        # which re-runs this code path.  Verify nothing crashes and
        # the second run still returns the same layout shape.
        project = tmp_path / "existing"
        setup_userspace_project(project, bundle)
        agents_before = (project / "AGENTS.md").read_text()

        layout = setup_userspace_project(project, bundle)
        assert layout.mode is Mode.USERSPACE
        # AGENTS.md content stable across re-runs (ensure_agents_md's
        # UNCHANGED contract).
        assert (project / "AGENTS.md").read_text() == agents_before
