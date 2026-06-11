"""Onboarding API routes for the first-five-minutes exploration.

Endpoints for checking onboarding status, listing scenarios,
starting/completing/dismissing the exploration, and managing the
exploration workspace.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

# Module-level state, set via init().
_clarity_agent_dir: Path = Path(".")
_project_dir: Path | None = None
_app_state: dict[str, Any] | None = None


def init(
    clarity_agent_dir: Path,
    app_state: dict[str, Any] | None = None,
    project_dir: Path | None = None,
) -> None:
    """Configure module-level paths.  Called once from create_app()."""
    global _clarity_agent_dir, _app_state, _project_dir
    _clarity_agent_dir = clarity_agent_dir
    _app_state = app_state
    _project_dir = project_dir


# ------------------------------------------------------------------
# GET /api/onboarding/status
# ------------------------------------------------------------------

@router.get("/status")
def get_onboarding_status() -> dict[str, Any]:
    """Return the current onboarding state.

    Includes ``project_is_fresh`` — True when the current project's
    protocol documents are all templates (no substantive work done).
    This is the project-level half of the first-screen eligibility
    check.
    """
    from clarity_agent.onboarding.state import OnboardingState

    state = OnboardingState.load()
    return {
        "first_exploration_status": state.first_exploration_status,
        "eligible_for_auto_exploration": state.eligible_for_auto_exploration,
        "last_exploration_scenario": state.last_exploration_scenario,
        "project_is_fresh": _check_project_is_fresh(),
    }


def _check_project_is_fresh() -> bool:
    """True when the project has no substantive Clarity content.

    Checks whether all tracked protocol documents are still templates.
    Returns True if there's no protocol dir at all.
    """
    if _project_dir is None:
        return True
    from clarity_agent.app_paths import protocol_dir as _protocol_dir
    from clarity_agent.protocol.packet_status import (
        DEFAULT_DEPENDENCIES,
        is_template,
    )

    pd = _protocol_dir(_project_dir)
    if not pd.is_dir():
        return True
    return all(is_template(pd / doc) for doc in DEFAULT_DEPENDENCIES)


# ------------------------------------------------------------------
# GET /api/onboarding/scenarios
# ------------------------------------------------------------------

@router.get("/scenarios")
def get_scenarios() -> dict[str, Any]:
    """Return the list of available exploration scenarios."""
    from clarity_agent.onboarding.scenarios import list_scenarios

    scenarios = list_scenarios(_clarity_agent_dir)
    return {"scenarios": [s.to_dict() for s in scenarios]}


# ------------------------------------------------------------------
# POST /api/onboarding/start
# ------------------------------------------------------------------

@router.post("/start")
def start_exploration(body: dict[str, Any]) -> dict[str, Any]:
    """Create the exploration workspace and return its path.

    Body: ``{"scenario_id": "autonomous-email-assistant"}``
    """
    scenario_id: str = body.get("scenario_id", "")
    if not scenario_id:
        raise HTTPException(status_code=400, detail="scenario_id is required")

    # Validate scenario exists.
    from clarity_agent.onboarding.scenarios import load_scenario_content

    try:
        load_scenario_content(_clarity_agent_dir, scenario_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {scenario_id}") from exc

    from clarity_agent.onboarding.workspace import ensure_exploration_workspace

    workspace_path = ensure_exploration_workspace(_clarity_agent_dir)

    return {
        "workspace_path": str(workspace_path),
        "scenario_id": scenario_id,
    }


# ------------------------------------------------------------------
# POST /api/onboarding/complete
# ------------------------------------------------------------------

@router.post("/complete")
def complete_exploration(body: dict[str, Any] | None = None) -> dict[str, str]:
    """Mark the exploration as completed."""
    from clarity_agent.onboarding.state import OnboardingState

    scenario = (body or {}).get("scenario_id")
    state = OnboardingState.load()
    state.mark_completed(scenario)
    state.save()
    return {"status": "completed"}


# ------------------------------------------------------------------
# POST /api/onboarding/dismiss
# ------------------------------------------------------------------

@router.post("/dismiss")
def dismiss_exploration() -> dict[str, str]:
    """Mark the exploration as dismissed (skipped)."""
    from clarity_agent.onboarding.state import OnboardingState

    state = OnboardingState.load()
    state.mark_dismissed()
    state.save()
    return {"status": "dismissed"}


# ------------------------------------------------------------------
# POST /api/onboarding/reset
# ------------------------------------------------------------------

@router.post("/reset")
def reset_exploration() -> dict[str, str]:
    """Reset onboarding state to not_started (for "run again")."""
    from clarity_agent.onboarding.state import OnboardingState

    state = OnboardingState.load()
    state.reset()
    state.save()
    return {"status": "not_started"}


# ------------------------------------------------------------------
# POST /api/onboarding/reset-workspace
# ------------------------------------------------------------------

@router.post("/reset-workspace")
def reset_workspace() -> dict[str, str]:
    """Delete and recreate the exploration workspace (for retrying)."""
    from clarity_agent.onboarding.workspace import reset_exploration_workspace

    ws = reset_exploration_workspace(_clarity_agent_dir)
    return {"workspace_path": str(ws)}


# ------------------------------------------------------------------
# POST /api/onboarding/reset-all
# ------------------------------------------------------------------

@router.post("/reset-all")
def reset_all() -> dict[str, str]:
    """Reset both onboarding state and workspace in one call.

    Convenience for iterative testing: resets state to not_started,
    deletes and recreates the exploration workspace, so the next
    page load shows the first screen again.
    """
    from clarity_agent.onboarding.state import OnboardingState
    from clarity_agent.onboarding.workspace import reset_exploration_workspace

    state = OnboardingState.load()
    state.reset()
    state.save()

    ws = reset_exploration_workspace(_clarity_agent_dir)
    return {"status": "not_started", "workspace_path": str(ws)}
