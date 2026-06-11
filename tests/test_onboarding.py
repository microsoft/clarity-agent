"""Tests for the first-five-minutes onboarding subsystem."""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# OnboardingState
# ---------------------------------------------------------------------------

class TestOnboardingState:
    """OnboardingState persistence and mutations."""

    def test_defaults(self) -> None:
        from clarity_agent.onboarding.state import OnboardingState

        state = OnboardingState()
        assert state.first_exploration_status == "not_started"
        assert state.first_exploration_completed_at is None
        assert state.last_exploration_scenario is None
        assert state.eligible_for_auto_exploration is True

    def test_load_missing_file(self, tmp_path: Path) -> None:
        from clarity_agent.onboarding.state import OnboardingState

        state = OnboardingState.load(tmp_path / "does-not-exist.json")
        assert state.first_exploration_status == "not_started"

    def test_roundtrip(self, tmp_path: Path) -> None:
        from clarity_agent.onboarding.state import OnboardingState

        path = tmp_path / "onboarding.json"

        state = OnboardingState()
        state.mark_completed("weekend-question")
        state.save(path)

        loaded = OnboardingState.load(path)
        assert loaded.first_exploration_status == "completed"
        assert loaded.first_exploration_completed_at is not None
        assert loaded.last_exploration_scenario == "weekend-question"
        assert loaded.eligible_for_auto_exploration is False

    def test_dismiss(self, tmp_path: Path) -> None:
        from clarity_agent.onboarding.state import OnboardingState

        path = tmp_path / "onboarding.json"
        state = OnboardingState()
        state.mark_dismissed()
        state.save(path)

        loaded = OnboardingState.load(path)
        assert loaded.first_exploration_status == "dismissed"
        assert loaded.eligible_for_auto_exploration is False

    def test_reset(self, tmp_path: Path) -> None:
        from clarity_agent.onboarding.state import OnboardingState

        path = tmp_path / "onboarding.json"
        state = OnboardingState()
        state.mark_completed("test")
        state.save(path)

        loaded = OnboardingState.load(path)
        loaded.reset()
        loaded.save(path)

        final = OnboardingState.load(path)
        assert final.first_exploration_status == "not_started"
        assert final.eligible_for_auto_exploration is True

    def test_load_corrupt_json(self, tmp_path: Path) -> None:
        from clarity_agent.onboarding.state import OnboardingState

        path = tmp_path / "onboarding.json"
        path.write_text("not valid json", encoding="utf-8")
        state = OnboardingState.load(path)
        assert state.first_exploration_status == "not_started"


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

class TestScenarios:
    """Scenario enumeration and loading."""

    def test_list_scenarios(self) -> None:
        """Should find the three shipped scenarios."""
        from clarity_agent.app_paths import get_bundle_dir
        from clarity_agent.onboarding.scenarios import list_scenarios

        scenarios = list_scenarios(get_bundle_dir())
        ids = {s.id for s in scenarios}
        assert "autonomous-email-assistant" in ids
        assert "renovate-or-move" in ids
        assert "weekend-question" in ids

    def test_scenario_has_title_and_description(self) -> None:
        from clarity_agent.app_paths import get_bundle_dir
        from clarity_agent.onboarding.scenarios import list_scenarios

        for scenario in list_scenarios(get_bundle_dir()):
            assert scenario.title, f"{scenario.id} missing title"
            assert scenario.description, f"{scenario.id} missing description"
            assert scenario.title != "Untitled Scenario"

    def test_load_scenario_content(self) -> None:
        from clarity_agent.app_paths import get_bundle_dir
        from clarity_agent.onboarding.scenarios import load_scenario_content

        content = load_scenario_content(get_bundle_dir(), "autonomous-email-assistant")
        assert "## Seed situation" in content

    def test_load_missing_scenario(self) -> None:
        from clarity_agent.app_paths import get_bundle_dir
        from clarity_agent.onboarding.scenarios import load_scenario_content

        with pytest.raises(FileNotFoundError):
            load_scenario_content(get_bundle_dir(), "does-not-exist")

    def test_base_guide_excluded(self) -> None:
        """The base process guide should not appear as a scenario."""
        from clarity_agent.app_paths import get_bundle_dir
        from clarity_agent.onboarding.scenarios import list_scenarios

        ids = {s.id for s in list_scenarios(get_bundle_dir())}
        assert "exploration-process-guide" not in ids


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

class TestWorkspace:
    """Exploration workspace creation."""

    def test_ensure_creates_protocol(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from clarity_agent.app_paths import get_bundle_dir
        from clarity_agent.onboarding.workspace import ensure_exploration_workspace

        # Redirect projects dir to tmp so we don't touch the real filesystem.
        monkeypatch.setattr(
            "clarity_agent.onboarding.workspace.clarity_projects_dir",
            lambda: tmp_path,
        )

        ws = ensure_exploration_workspace(get_bundle_dir())
        assert ws.is_dir()
        # Should have a Clarity Protocol directory (userspace mode).
        assert (ws / "Clarity Protocol").is_dir()
        # Should have config.json inside it.
        assert (ws / "Clarity Protocol" / "config.json").exists()

    def test_reset_cleans_and_recreates(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from clarity_agent.app_paths import get_bundle_dir
        from clarity_agent.onboarding.workspace import (
            ensure_exploration_workspace,
            reset_exploration_workspace,
        )

        monkeypatch.setattr(
            "clarity_agent.onboarding.workspace.clarity_projects_dir",
            lambda: tmp_path,
        )

        ws = ensure_exploration_workspace(get_bundle_dir())
        # Write a marker file.
        marker = ws / "Clarity Protocol" / "goal" / "problem.md"
        marker.write_text("custom content", encoding="utf-8")

        ws2 = reset_exploration_workspace(get_bundle_dir())
        assert ws2 == ws
        # The marker should be gone — replaced by template.
        content = marker.read_text(encoding="utf-8")
        assert "custom content" not in content
