"""Tests for :func:`clarity_agent.web.app.create_app`'s AGENTS.md
ensure hook.

The ensure runs at app-construction time — i.e. exactly once per
sidecar startup, which is exactly once per "open this directory"
event in the desktop / launcher model — so AGENTS.md is current
before *any* endpoint (WS or REST) runs against it.  This module
verifies the placement: no WebSocket is opened in any test here,
yet AGENTS.md must already exist with the rendered block after
``create_app`` returns.

The complementary ``WebSessionAdapter._ensure_agents_md_best_effort``
hook is covered in
:class:`tests.test_web_session_resume.TestEnsureAgentsMdHook` (the
defense-in-depth path used by direct adapter construction).
"""

from __future__ import annotations

from pathlib import Path

from clarity_agent.llm import LLMConfig
from clarity_agent.setup.layout import PROTOCOL_DIR_VISIBLE
from clarity_agent.setup.snippet import BEGIN_DELIMITER
from clarity_agent.web import app as app_module


def _make_userspace_project(tmp_path: Path) -> tuple[Path, Path]:
    """Build a USERSPACE project + a separate bundle dir.

    USERSPACE means the visible-name protocol dir is present; the
    bundle is distinct from the project so the dogfooding skip in
    ``ensure_for_project`` doesn't fire.
    """
    project = tmp_path / "project"
    bundle = tmp_path / "bundle"
    project.mkdir()
    bundle.mkdir()
    (bundle / "processes").mkdir()
    (project / PROTOCOL_DIR_VISIBLE).mkdir()
    return project, bundle


def _cfg() -> LLMConfig:
    # Tiers must be populated because ``WebSessionAdapter.__init__``
    # reads ``tiers["default"]`` — even though the tests here never
    # exercise the LLM path.
    return LLMConfig(
        provider="anthropic",
        api_key="fake-key",
        tiers={"default": "fake-model"},
    )


class TestCreateAppEnsureHook:
    def test_creates_agents_md_at_app_construction_time(
        self, tmp_path: Path,
    ) -> None:
        # No WebSocket, no REST call, no session — just create_app.
        # AGENTS.md must exist immediately after, with the rendered
        # Clarity block.  This is the central guarantee the placement
        # exists to provide: opening a directory is enough.
        project, bundle = _make_userspace_project(tmp_path)
        assert not (project / "AGENTS.md").exists()

        app_module.create_app(
            project_dir=project,
            clarity_agent_dir=bundle,
            llm_config=_cfg(),
        )

        agents_md = project / "AGENTS.md"
        assert agents_md.exists()
        assert BEGIN_DELIMITER in agents_md.read_text(encoding="utf-8")

    def test_idempotent_across_app_reconstructions(
        self, tmp_path: Path,
    ) -> None:
        # Sidecars can restart (crash, deploy, etc.).  Re-running
        # create_app on the same project must not thrash the file
        # — important for filesystem watchers in host coding agents
        # that re-read on every change.
        project, bundle = _make_userspace_project(tmp_path)
        app_module.create_app(
            project_dir=project, clarity_agent_dir=bundle, llm_config=_cfg(),
        )
        first = (project / "AGENTS.md").read_text(encoding="utf-8")
        mtime_before = (project / "AGENTS.md").stat().st_mtime_ns

        app_module.create_app(
            project_dir=project, clarity_agent_dir=bundle, llm_config=_cfg(),
        )
        second = (project / "AGENTS.md").read_text(encoding="utf-8")

        assert second == first
        # No rewrite — UNCHANGED path was taken.  The mtime
        # invariant is what filesystem watchers depend on.
        assert (project / "AGENTS.md").stat().st_mtime_ns == mtime_before

    def test_skips_when_no_layout_detectable(self, tmp_path: Path) -> None:
        # Bare project — no protocol dir, no .clarity-agent.  The
        # ensure helper short-circuits to None; create_app must
        # succeed without writing AGENTS.md (we don't implicitly
        # create directories from this hook; mode selection belongs
        # in the explicit setup entry points).
        project = tmp_path / "bare"
        bundle = tmp_path / "bundle"
        project.mkdir()
        bundle.mkdir()
        (bundle / "processes").mkdir()

        app_module.create_app(
            project_dir=project, clarity_agent_dir=bundle, llm_config=_cfg(),
        )
        assert not (project / "AGENTS.md").exists()

    def test_skips_when_project_is_clarity_agent_source(
        self, tmp_path: Path,
    ) -> None:
        # Dogfooding: project_dir == clarity_agent_dir.  The hand-
        # curated block at the source repo's AGENTS.md must never be
        # auto-rewritten with the generic embedded-relative form.
        same = tmp_path / "clarity-agent-source"
        same.mkdir()
        (same / "processes").mkdir()
        (same / ".clarity-protocol").mkdir()  # would otherwise → EMBEDDED layout

        app_module.create_app(
            project_dir=same, clarity_agent_dir=same, llm_config=_cfg(),
        )
        # No AGENTS.md written by us (the source repo manages its own).
        assert not (same / "AGENTS.md").exists()
