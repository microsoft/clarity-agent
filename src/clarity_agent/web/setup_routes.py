"""Setup wizard API routes.

Provides endpoints for the first-launch setup wizard that replaces
manual ``.env`` editing. Reuses diagnostic logic from doctor.py.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from clarity_agent.app_paths import clarity_env_path

router = APIRouter(prefix="/api/setup", tags=["setup"])

# Set during app startup via init().
_env_path: Path = clarity_env_path()
_clarity_agent_dir: Path = Path(".")
_project_dir: Path | None = None
_app_state: dict[str, Any] | None = None
_kill_children_fn: Any | None = None  # callable to kill child processes (launcher mode)


def init(
    env_path: Path,
    clarity_agent_dir: Path,
    project_dir: Path | None = None,
    app_state: dict[str, Any] | None = None,
    kill_children: Any | None = None,
) -> None:
    """Configure module-level paths. Called once from create_app()."""
    global _env_path, _clarity_agent_dir, _project_dir, _app_state, _kill_children_fn
    _env_path = env_path
    _clarity_agent_dir = clarity_agent_dir
    _project_dir = project_dir
    _app_state = app_state
    _kill_children_fn = kill_children


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect() -> str | None:
    """Detect the currently configured provider (if any).

    Checks stored settings first (user already configured a provider),
    then falls back to environment-variable auto-detection.
    """
    from clarity_agent.settings import Settings
    s = Settings.current()
    if s.provider:
        return s.provider

    from clarity_agent.llm.config import _auto_detect_provider
    result = _auto_detect_provider()
    return result[0] if result else None


def _provider_info() -> list[dict[str, Any]]:
    """Return display metadata for each supported provider.

    Reads directly from ``_PROVIDERS`` — the registry is the single
    source of truth for display info, auth modes, and fields.
    """
    from clarity_agent.llm.config import _PROVIDERS, _has_package

    result = []
    for name, info in _PROVIDERS.items():
        # Build auth mode list with availability checks.
        auth_modes = []
        for mode in info["auth_modes"]:
            mode_entry: dict[str, Any] = {
                "name": mode["name"],
                "display_name": mode["display_name"],
                "description": mode["description"],
                "fields": mode.get("fields", []),
                "available": (
                    _has_package(mode["package"])
                    if mode.get("package") else True
                ),
            }
            if mode.get("setup_help"):
                mode_entry["setup_help"] = mode["setup_help"]
            if mode.get("setup_url"):
                mode_entry["setup_url"] = mode["setup_url"]
            auth_modes.append(mode_entry)

        entry: dict[str, Any] = {
            "name": name,
            "display_name": info["display_name"],
            "description": info["description"],
            "auth_modes": auth_modes,
        }
        if info.get("common_fields"):
            entry["common_fields"] = info["common_fields"]
        if info.get("setup_url"):
            entry["setup_url"] = info["setup_url"]
        result.append(entry)
    return result


def _write_env(
    provider: str,
    auth_mode: str,
    credentials: dict[str, str],
) -> None:
    """Write provider selection and credentials to storage."""
    from clarity_agent.settings import Settings

    s = Settings.current()
    s.set("CLARITY_LLM_PROVIDER", provider)
    s.set("CLARITY_AUTH_MODE", auth_mode)
    # Remember this auth mode for the provider so switching back is instant.
    s.provider_auth_modes[provider] = auth_mode
    for key, value in credentials.items():
        if value:
            s.set(key, value)
    s.save()


def _test_connection(provider: str, auth_mode: str) -> dict[str, Any]:
    """Probe the provider and return {ok, message, hint?}."""
    from clarity_agent.setup.doctor import _classify_error, _probe_api, _probe_sdk

    try:
        if provider == "anthropic" and auth_mode == "claude_sdk":
            result = _probe_sdk(_project_dir or _clarity_agent_dir)
        elif provider == "github":
            from clarity_agent.setup.doctor import _probe_copilot
            result = _probe_copilot(_clarity_agent_dir)
        else:
            result = _probe_api(_clarity_agent_dir, provider)
        return {"ok": result.status.value == "pass", "message": result.message}
    except Exception as e:
        hint = _classify_error(e, provider)
        return {"ok": False, "message": str(e), "hint": hint}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status")
async def setup_status() -> dict[str, Any]:
    """Check whether the system is configured."""
    provider = await asyncio.to_thread(_detect)
    return {
        "configured": provider is not None,
        "provider": provider,
        "has_env_file": _env_path.exists(),
    }


@router.get("/providers")
async def setup_providers() -> dict[str, Any]:
    """Return the list of supported providers with display metadata."""
    return {"providers": _provider_info()}


@router.post("/configure")
async def setup_configure(body: dict[str, Any]) -> dict[str, Any]:
    """Write provider configuration and test the connection.

    Body: ``{provider: str, auth_mode: str, credentials: {KEY: value, ...}}``
    """
    provider: str = body.get("provider", "")
    auth_mode: str = body.get("auth_mode", "api_key")
    credentials: dict[str, str] = body.get("credentials", {})

    if not provider:
        return {"ok": False, "message": "No provider specified"}

    # Write settings
    await asyncio.to_thread(_write_env, provider, auth_mode, credentials)

    # Test
    result = await asyncio.to_thread(_test_connection, provider, auth_mode)

    # On success, rebuild the LLM config and update the shared app state
    # so the WebSocket handler can create sessions with the new config.
    if result.get("ok"):
        if _app_state is not None:
            # Single-project mode (app.py): update in-place.
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
                print(f"  [Setup] Config reloaded: provider={new_config.provider}", flush=True)
                old_session = _app_state.get("session")
                if old_session is not None:
                    await old_session.stop()
                    _app_state["session"] = None
            except (LLMConfigError, Exception) as exc:
                print(f"  [Setup] Config reload failed: {exc}", flush=True)
        else:
            # Launcher mode: kill child processes so they respawn with
            # the new config when a project is next activated.
            if _kill_children_fn is not None:
                try:
                    _kill_children_fn()
                    print("  [Setup] Killed child processes for config reload", flush=True)
                except Exception:
                    pass

    return result


@router.post("/test-connection")
async def test_connection(body: dict[str, Any]) -> dict[str, Any]:
    """Test connection without writing settings.

    Temporarily sets env vars for the probe, then restores originals.
    """
    provider: str = body.get("provider", "")
    auth_mode: str = body.get("auth_mode", "api_key")
    credentials: dict[str, str] = body.get("credentials", {})

    # Temporarily set env vars
    originals: dict[str, str | None] = {}
    for key, value in credentials.items():
        if value:
            originals[key] = os.environ.get(key)
            os.environ[key] = value
    if provider:
        originals["CLARITY_LLM_PROVIDER"] = os.environ.get("CLARITY_LLM_PROVIDER")
        os.environ["CLARITY_LLM_PROVIDER"] = provider

    try:
        result = await asyncio.to_thread(_test_connection, provider, auth_mode)
    finally:
        # Restore
        for key, original in originals.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original

    return result
