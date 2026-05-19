"""Centralized settings management for Clarity.

Provides a ``Settings`` singleton that holds all user-configurable
settings and handles loading/saving to persistent storage.

Access the current settings via ``Settings.current()``.

Storage layout:
- **Secrets** (API keys): platform keychain via ``keyring``, with a
  ``.env``-based fallback on systems without a keychain service.
- **Preferences** (provider, model tiers, theme): ``settings.json``
  in the data directory.
- Environment variables override both.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import keyring

from clarity_agent.keyring_backend import SERVICE, ensure_backend

# Preferences: stored in settings.json, overridable via env vars.
_PREF_KEYS: dict[str, str] = {
    "provider": "CLARITY_LLM_PROVIDER",
    "auth_mode": "CLARITY_AUTH_MODE",
    "tenant_id": "CLARITY_TENANT_ID",
    "model_default": "CLARITY_MODEL_DEFAULT",
    "model_deep": "CLARITY_MODEL_DEEP",
    "model_fast": "CLARITY_MODEL_FAST",
    "theme": "CLARITY_THEME",
    "font_scale": "CLARITY_FONT_SCALE",
    "reduce_motion": "CLARITY_REDUCE_MOTION",
}

# Secrets: stored in keyring, overridable via env vars.
_SECRET_KEYS: dict[str, str] = {
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "openai_api_key": "OPENAI_API_KEY",
    "azure_api_key": "AZURE_AI_API_KEY",
    "azure_endpoint": "AZURE_AI_ENDPOINT",
    "github_token": "GITHUB_TOKEN",
    "gemini_api_key": "GEMINI_API_KEY",
}

# Combined lookup for get()/set().
_ALL_KEYS: dict[str, str] = {**_PREF_KEYS, **_SECRET_KEYS}
_ATTR_FOR_ENV = {v: k for k, v in _ALL_KEYS.items()}

# Module-level singleton.
_current: Settings | None = None


@dataclass
class Settings:
    """All user-configurable Clarity settings.

    Use :meth:`load` at startup to initialize the singleton, then
    :meth:`current` anywhere else to access it.
    """

    # -- Provider credentials --
    provider: str | None = None
    auth_mode: str | None = None
    tenant_id: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    azure_api_key: str | None = None
    azure_endpoint: str | None = None
    github_token: str | None = None
    gemini_api_key: str | None = None

    # -- Per-provider auth mode memory --
    # Remembers the last-used auth mode for each provider so that
    # switching back to a previously configured provider is one click.
    provider_auth_modes: dict[str, str] = field(default_factory=dict)

    # -- Model configuration --
    model_default: str | None = None
    model_deep: str | None = None
    model_fast: str | None = None
    process_model_overrides: dict[str, str] = field(default_factory=dict)

    # Per-model context-window override (in tokens).  Used when a
    # model isn't in any backend's built-in ``MODEL_CONTEXT_WINDOWS``
    # table — e.g., a custom Azure deployment or a model released
    # after this codebase's tier defaults were last updated.  The
    # compaction trigger looks here first.  Empty by default.
    context_window_overrides: dict[str, int] = field(default_factory=dict)

    # -- App preferences --
    theme: str = "sage"
    font_scale: int = 100
    reduce_motion: str = "system"

    # -- Storage paths (not user settings) --
    env_path: Path | None = None
    settings_path: Path | None = None

    @classmethod
    def load(cls, env_path: Path | None = None) -> Settings:
        """Load settings and install as the process-wide singleton.

        Load order (lowest to highest priority):
        1. ``settings.json`` (preferences)
        2. ``.env`` file (legacy secrets and preferences, for backward compat)
        3. Keyring (secrets)
        4. Environment variables
        """
        global _current

        if env_path is None:
            from clarity_agent.app_paths import clarity_env_path
            env_path = clarity_env_path()

        from clarity_agent.app_paths import clarity_data_dir
        settings_path = clarity_data_dir() / "settings.json"

        # Ensure a working keyring backend is available.
        ensure_backend()

        settings = cls(env_path=env_path, settings_path=settings_path)

        # 1. Read settings.json (preferences).
        if settings_path.exists():
            try:
                data = json.loads(settings_path.read_text())
                for attr in _PREF_KEYS:
                    if attr in data and data[attr] is not None:
                        setattr(settings, attr, data[attr])
                if "process_model_overrides" in data:
                    settings.process_model_overrides.update(data["process_model_overrides"])
                if "context_window_overrides" in data:
                    # Coerce to int — JSON numeric type is fine, but
                    # hand-edited entries might come through as
                    # strings; the conversion makes the contract
                    # explicit either way.
                    settings.context_window_overrides.update({
                        k: int(v) for k, v in data["context_window_overrides"].items()
                    })
                if "provider_auth_modes" in data:
                    settings.provider_auth_modes.update(data["provider_auth_modes"])
            except (json.JSONDecodeError, OSError):
                pass  # corrupt or unreadable — start fresh

        # 2. Load .env (legacy secrets + backward compat for preferences).
        if env_path.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path, override=False)
            except ImportError:
                pass

        # 3. Read secrets from keyring (overrides .env values).
        for attr, env_key in _SECRET_KEYS.items():
            value = keyring.get_password(SERVICE, env_key)
            if value:
                setattr(settings, attr, value)
                # Also inject into os.environ so LLM SDKs see them.
                os.environ.setdefault(env_key, value)

        # 4. Environment variables override everything.
        for attr, env_key in _ALL_KEYS.items():
            value = os.environ.get(env_key)
            if value:
                setattr(settings, attr, value)

        prefix = "CLARITY_PROCESS_MODEL_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                process_name = key[len(prefix):].lower().replace("_", "-")
                settings.process_model_overrides[process_name] = value

        # Migrate legacy "claude-sdk" provider → anthropic + claude_sdk auth.
        _migrated = False
        if settings.provider == "claude-sdk":
            settings.provider = "anthropic"
            settings.auth_mode = "claude_sdk"
            settings.provider_auth_modes["anthropic"] = "claude_sdk"
            _migrated = True
        if _migrated:
            settings.save()

        _current = settings
        return settings

    @classmethod
    def current(cls) -> Settings:
        """Return the process-wide Settings singleton.

        If :meth:`load` has not been called yet, loads from the default
        location.
        """
        if _current is None:
            cls.load()
        return _current  # type: ignore[return-value]

    @classmethod
    def _reset(cls) -> None:
        """Clear the singleton (for testing only)."""
        global _current
        _current = None

    @property
    def tier_overrides(self) -> dict[str, str]:
        """Model tier overrides as a ``{tier_name: model}`` dict."""
        tiers: dict[str, str] = {}
        if self.model_default:
            tiers["default"] = self.model_default
        if self.model_deep:
            tiers["deep"] = self.model_deep
        if self.model_fast:
            tiers["fast"] = self.model_fast
        return tiers

    def get(self, env_key: str) -> str | None:
        """Read a setting by its environment variable name."""
        attr = _ATTR_FOR_ENV.get(env_key)
        if attr:
            return getattr(self, attr)
        return None

    def set(self, env_key: str, value: str | None) -> None:
        """Set a setting by its environment variable name.

        Also updates ``os.environ`` so downstream code sees the change.
        """
        attr = _ATTR_FOR_ENV.get(env_key)
        if attr is None:
            raise KeyError(f"Unknown setting: {env_key}")
        setattr(self, attr, value)
        if value:
            os.environ[env_key] = value
        elif env_key in os.environ:
            del os.environ[env_key]

    def save(self) -> None:
        """Write preferences to ``settings.json`` and secrets to keyring."""
        # Preferences → settings.json
        if self.settings_path is not None:
            data: dict[str, object] = {}
            for attr in _PREF_KEYS:
                value = getattr(self, attr)
                if value is not None:
                    data[attr] = value
            if self.process_model_overrides:
                data["process_model_overrides"] = dict(self.process_model_overrides)
            if self.context_window_overrides:
                data["context_window_overrides"] = dict(self.context_window_overrides)
            if self.provider_auth_modes:
                data["provider_auth_modes"] = dict(self.provider_auth_modes)

            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(json.dumps(data, indent=2) + "\n")

        # Secrets → keyring
        for attr, env_key in _SECRET_KEYS.items():
            value = getattr(self, attr)
            if value is not None:
                keyring.set_password(SERVICE, env_key, value)
            else:
                # Remove from keyring if the value was cleared.
                try:
                    keyring.delete_password(SERVICE, env_key)
                except keyring.errors.PasswordDeleteError:  # type: ignore[attr-defined]
                    pass  # wasn't stored — nothing to delete

        # Remove secrets from .env — they now live in keyring (or
        # LocalKeyring's secrets.json). This cleans up legacy plaintext.
        if self.env_path is not None and self.env_path.exists():
            secret_env_keys = set(_SECRET_KEYS.values())
            lines = []
            for line in self.env_path.read_text().splitlines():
                stripped = line.strip()
                if "=" in stripped:
                    key, _, _ = stripped.partition("=")
                    if key.strip() in secret_env_keys:
                        continue  # skip — now in keyring
                lines.append(line)
            self.env_path.write_text("\n".join(lines) + "\n" if lines else "")
