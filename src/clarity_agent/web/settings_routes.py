"""Settings API routes for the preferences panel.

Provides read/write access to user settings via the Settings singleton.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Shared app state (set by init() from create_app or launcher).
_app_state: dict[str, Any] | None = None
_kill_children_fn: Any | None = None  # callable to kill child processes (launcher mode)


def init(
    *,
    app_state: dict[str, Any] | None = None,
    kill_children: Any | None = None,
) -> None:
    """Configure module-level state. Called once from create_app() or launcher.

    - In single-project mode (app.py): pass ``app_state`` so the config
      can be rebuilt and the current session stopped.
    - In launcher mode (launcher.py): pass ``kill_children`` so child
      project subprocesses respawn with the new config.
    """
    global _app_state, _kill_children_fn
    _app_state = app_state
    _kill_children_fn = kill_children


@router.get("")
async def get_settings() -> dict[str, Any]:
    """Return all current settings."""
    from clarity_agent.settings import Settings

    s = Settings.current()
    return {
        "provider": s.provider,
        "auth_mode": s.auth_mode,
        "model_default": s.model_default,
        "model_deep": s.model_deep,
        "model_fast": s.model_fast,
        "process_model_overrides": dict(s.process_model_overrides),
        "provider_auth_modes": dict(s.provider_auth_modes),
        "theme": s.theme,
        "font_scale": s.font_scale,
        "reduce_motion": s.reduce_motion,
        # Credential presence (not values) — so the UI can show
        # "configured" vs "not configured" without exposing keys.
        "has_anthropic_key": s.anthropic_api_key is not None,
        "has_openai_key": s.openai_api_key is not None,
        "has_azure_key": s.azure_api_key is not None,
        "has_azure_endpoint": s.azure_endpoint is not None,
    }


@router.post("")
async def update_settings(body: dict[str, Any]) -> dict[str, Any]:
    """Update settings. Only provided fields are changed.

    Body: ``{provider: str, theme: str, model_default: str, ...}``
    """
    from clarity_agent.settings import _ALL_KEYS, Settings

    s = Settings.current()

    for key, value in body.items():
        if key == "process_model_overrides" and isinstance(value, dict):
            s.process_model_overrides = value
            continue
        if key == "provider_auth_modes" and isinstance(value, dict):
            s.provider_auth_modes = value
            continue
        if key == "font_scale" and isinstance(value, (int, float)):
            s.font_scale = int(value)
            continue
        if key == "reduce_motion" and isinstance(value, str):
            s.reduce_motion = value
            continue
        # Map JSON field names to env key names for set().
        env_key = _ALL_KEYS.get(key)
        if env_key:
            s.set(env_key, value if value else None)

    s.save()
    return {"ok": True}


@router.post("/activate")
async def activate_provider(body: dict[str, Any]) -> dict[str, Any]:
    """Switch the active provider without re-entering credentials.

    Body: ``{provider: str, auth_mode: str}``

    Uses stored credentials from previous configuration.  Also rebuilds
    the LLM config in the shared app state if running in single-project
    mode, so the next chat session uses the new provider.
    """
    from clarity_agent.settings import Settings

    provider: str = body.get("provider", "")
    auth_mode: str = body.get("auth_mode", "")

    if not provider:
        return {"ok": False, "message": "No provider specified"}

    s = Settings.current()
    s.set("CLARITY_LLM_PROVIDER", provider)
    s.set("CLARITY_AUTH_MODE", auth_mode)
    s.provider_auth_modes[provider] = auth_mode
    s.save()

    # Rebuild the LLM config so the next chat session uses the new provider.
    if _app_state is None:
        # Launcher mode: kill child processes so they respawn with the
        # new config when a project is next activated.
        if _kill_children_fn is not None:
            try:
                _kill_children_fn()
            except Exception:
                pass
    else:
        import argparse

        from clarity_agent.llm.config import LLMConfig, LLMConfigError
        try:
            ns = argparse.Namespace(
                provider=None, api_key=None, endpoint=None,
                model=None, model_deep=None, model_fast=None,
                auth_mode=None,
            )
            new_config = LLMConfig.create(ns)
            _app_state["llm_config"] = new_config
            old_session = _app_state.get("session")
            if old_session is not None:
                await old_session.stop()
                _app_state["session"] = None
        except (LLMConfigError, Exception) as exc:
            print(f"  [Settings] Config reload failed: {exc}", flush=True)

    return {"ok": True, "provider": provider, "auth_mode": auth_mode}
