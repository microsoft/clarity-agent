"""Tests for clarity_agent.settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from clarity_agent.settings import Settings


class TestSettingsLoad:
    def test_loads_from_env_vars(self) -> None:
        env = {
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "CLARITY_LLM_PROVIDER": "anthropic",
            "CLARITY_THEME": "midnight",
            "CLARITY_MODEL_DEEP": "claude-opus-4-6",
        }
        with patch.dict(os.environ, env, clear=False):
            s = Settings.load(env_path=Path("/nonexistent/.env"))
        assert s.anthropic_api_key == "sk-ant-test"
        assert s.provider == "anthropic"
        assert s.theme == "midnight"
        assert s.model_deep == "claude-opus-4-6"

    def test_loads_process_overrides(self) -> None:
        env = {
            "CLARITY_PROCESS_MODEL_PROBLEM_CLARIFICATION": "deep",
            "CLARITY_PROCESS_MODEL_ARCHITECTURE_DESIGN": "o1-preview",
        }
        with patch.dict(os.environ, env, clear=False):
            s = Settings.load(env_path=Path("/nonexistent/.env"))
        assert s.process_model_overrides["problem-clarification"] == "deep"
        assert s.process_model_overrides["architecture-design"] == "o1-preview"

    def test_default_theme(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            s = Settings.load(env_path=Path("/nonexistent/.env"))
        assert s.theme == "sage"

    def test_loads_secrets_from_env_file(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("ANTHROPIC_API_KEY=sk-from-file\n")

        clean_env = {k: v for k, v in os.environ.items()
                     if k != "ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, clean_env, clear=True):
            s = Settings.load(env_path=env_file)
        assert s.anthropic_api_key == "sk-from-file"

    def test_env_file_overrides_keyring_secrets(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("ANTHROPIC_API_KEY=old\n")

        import keyring as kr

        from clarity_agent.keyring_backend import SERVICE

        old_password = kr.get_password(SERVICE, "ANTHROPIC_API_KEY")
        kr.set_password(SERVICE, "ANTHROPIC_API_KEY", "new")
        try:
            clean_env = {k: v for k, v in os.environ.items()
                         if k != "ANTHROPIC_API_KEY"}
            with patch.dict(os.environ, clean_env, clear=True):
                s = Settings.load(env_path=env_file)
            assert s.anthropic_api_key == "old"
        finally:
            if old_password is None:
                kr.delete_password(SERVICE, "ANTHROPIC_API_KEY")
            else:
                kr.set_password(SERVICE, "ANTHROPIC_API_KEY", old_password)

    def test_loads_preferences_from_settings_json(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({
            "provider": "anthropic",
            "theme": "midnight",
            "model_deep": "claude-opus-4-6",
            "process_model_overrides": {"problem-clarification": "deep"},
        }))

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("CLARITY_LLM_PROVIDER", "CLARITY_THEME",
                                  "CLARITY_MODEL_DEEP")}
        with patch.dict(os.environ, clean_env, clear=True), \
             patch("clarity_agent.app_paths.clarity_data_dir", return_value=tmp_path):
            s = Settings.load(env_path=tmp_path / ".env")
        assert s.provider == "anthropic"
        assert s.theme == "midnight"
        assert s.model_deep == "claude-opus-4-6"
        assert s.process_model_overrides["problem-clarification"] == "deep"

    def test_env_vars_override_settings_json(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"theme": "from-json"}))

        with patch.dict(os.environ, {"CLARITY_THEME": "from-env"}, clear=False), \
             patch("clarity_agent.app_paths.clarity_data_dir", return_value=tmp_path):
            s = Settings.load(env_path=tmp_path / ".env")
        assert s.theme == "from-env"

    def test_env_file_backward_compat(self, tmp_path: Path) -> None:
        """Preferences in .env still work (backward compat)."""
        env_file = tmp_path / ".env"
        env_file.write_text("CLARITY_THEME=ocean\nCLARITY_LLM_PROVIDER=openai\n")

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("CLARITY_THEME", "CLARITY_LLM_PROVIDER")}
        with patch.dict(os.environ, clean_env, clear=True):
            s = Settings.load(env_path=env_file)
        assert s.theme == "ocean"
        assert s.provider == "openai"


class TestSettingsSave:
    def test_preferences_go_to_settings_json(self, tmp_path: Path) -> None:
        s = Settings(
            env_path=tmp_path / ".env",
            settings_path=tmp_path / "settings.json",
            provider="anthropic",
            theme="midnight",
            model_deep="claude-opus-4-6",
        )
        s.save()

        data = json.loads((tmp_path / "settings.json").read_text())
        assert data["provider"] == "anthropic"
        assert data["theme"] == "midnight"
        assert data["model_deep"] == "claude-opus-4-6"

    def test_secrets_go_to_keyring(self, tmp_path: Path) -> None:
        s = Settings(
            env_path=tmp_path / ".env",
            settings_path=tmp_path / "settings.json",
            anthropic_api_key="sk-test",
            openai_api_key="sk-oai",
        )
        s.save()

        import keyring as kr

        from clarity_agent.keyring_backend import SERVICE
        assert kr.get_password(SERVICE, "ANTHROPIC_API_KEY") == "sk-test"
        assert kr.get_password(SERVICE, "OPENAI_API_KEY") == "sk-oai"
        # Secrets should NOT be in settings.json
        data = json.loads((tmp_path / "settings.json").read_text())
        assert "anthropic_api_key" not in data

    def test_process_overrides_go_to_settings_json(self, tmp_path: Path) -> None:
        s = Settings(
            env_path=tmp_path / ".env",
            settings_path=tmp_path / "settings.json",
            process_model_overrides={"problem-clarification": "deep"},
        )
        s.save()

        data = json.loads((tmp_path / "settings.json").read_text())
        assert data["process_model_overrides"]["problem-clarification"] == "deep"

    def test_roundtrip(self, tmp_path: Path) -> None:
        """Save then load produces the same settings."""
        s = Settings(
            env_path=tmp_path / ".env",
            settings_path=tmp_path / "settings.json",
            provider="anthropic",
            anthropic_api_key="sk-test",
            theme="midnight",
            model_deep="claude-opus-4-6",
            process_model_overrides={"architecture-design": "deep"},
        )
        s.save()

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("CLARITY_LLM_PROVIDER", "CLARITY_THEME",
                                  "CLARITY_MODEL_DEEP", "ANTHROPIC_API_KEY")}
        with patch.dict(os.environ, clean_env, clear=True), \
             patch("clarity_agent.app_paths.clarity_data_dir", return_value=tmp_path):
            loaded = Settings.load(env_path=tmp_path / ".env")

        assert loaded.provider == "anthropic"
        assert loaded.anthropic_api_key == "sk-test"
        assert loaded.theme == "midnight"
        assert loaded.model_deep == "claude-opus-4-6"
        assert loaded.process_model_overrides["architecture-design"] == "deep"

    def test_skips_none_values(self, tmp_path: Path) -> None:
        s = Settings(
            env_path=tmp_path / ".env",
            settings_path=tmp_path / "settings.json",
            theme="sage",
        )
        s.save()

        import keyring as kr

        from clarity_agent.keyring_backend import SERVICE
        assert kr.get_password(SERVICE, "ANTHROPIC_API_KEY") is None

        data = json.loads((tmp_path / "settings.json").read_text())
        assert "anthropic_api_key" not in data

    def test_save_cleans_env_when_real_keychain(self, tmp_path: Path) -> None:
        """When a real keychain is active, secrets are removed from .env."""
        import keyring as kr
        from keyring.backend import KeyringBackend

        class InMemoryKeyring(KeyringBackend):
            """Minimal in-memory keyring for testing."""
            # ``priority`` on the base class is a ``classproperty[float]``
            # descriptor which pyright can't model; assigning an int
            # literal is the standard keyring-library pattern.
            priority = 10  # type: ignore[assignment]
            _store: dict[str, str] = {}
            def get_password(self, service: str, username: str) -> str | None:
                return self._store.get(f"{service}/{username}")
            def set_password(self, service: str, username: str, password: str) -> None:
                self._store[f"{service}/{username}"] = password
            def delete_password(self, service: str, username: str) -> None:
                self._store.pop(f"{service}/{username}", None)

        old_kr = kr.get_keyring()
        kr.set_keyring(InMemoryKeyring())

        try:
            env_file = tmp_path / ".env"
            env_file.write_text("ANTHROPIC_API_KEY=old-key\nCLARITY_THEME=sage\n")

            s = Settings(
                env_path=env_file,
                settings_path=tmp_path / "settings.json",
                anthropic_api_key="new-key",
                theme="sage",
            )
            s.save()

            # Secret should have been removed from .env
            env_text = env_file.read_text()
            assert "ANTHROPIC_API_KEY" not in env_text
            # Non-secret lines should be preserved
            assert "CLARITY_THEME" in env_text
        finally:
            kr.set_keyring(old_kr)


class TestSettingsAccessors:
    def test_tier_overrides(self) -> None:
        s = Settings(model_default="gpt-4", model_deep="gpt-4-turbo")
        tiers = s.tier_overrides
        assert tiers == {"default": "gpt-4", "deep": "gpt-4-turbo"}
        assert "fast" not in tiers

    def test_get_by_env_key(self) -> None:
        s = Settings(anthropic_api_key="sk-test", theme="midnight")
        assert s.get("ANTHROPIC_API_KEY") == "sk-test"
        assert s.get("CLARITY_THEME") == "midnight"
        assert s.get("OPENAI_API_KEY") is None
        assert s.get("BOGUS_KEY") is None

    def test_set_by_env_key(self) -> None:
        s = Settings()
        s.set("ANTHROPIC_API_KEY", "sk-new")
        assert s.anthropic_api_key == "sk-new"
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-new"
        # Clean up
        s.set("ANTHROPIC_API_KEY", None)

    def test_set_unknown_key_raises(self) -> None:
        s = Settings()
        with pytest.raises(KeyError, match="Unknown setting"):
            s.set("BOGUS_KEY", "value")

    def test_auth_mode_and_tenant_id(self) -> None:
        s = Settings(auth_mode="interactive", tenant_id="my-tenant")
        assert s.get("CLARITY_AUTH_MODE") == "interactive"
        assert s.get("CLARITY_TENANT_ID") == "my-tenant"

    def test_auth_mode_loads_from_env(self) -> None:
        env = {"CLARITY_AUTH_MODE": "interactive", "CLARITY_TENANT_ID": "t1"}
        with patch.dict(os.environ, env, clear=False):
            s = Settings.load(env_path=Path("/nonexistent/.env"))
        assert s.auth_mode == "interactive"
        assert s.tenant_id == "t1"

    def test_auth_mode_roundtrip_settings_json(self, tmp_path: Path) -> None:
        s = Settings(
            env_path=tmp_path / ".env",
            settings_path=tmp_path / "settings.json",
            auth_mode="device_code",
            tenant_id="t-123",
        )
        s.save()

        data = json.loads((tmp_path / "settings.json").read_text())
        assert data["auth_mode"] == "device_code"
        assert data["tenant_id"] == "t-123"

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("CLARITY_AUTH_MODE", "CLARITY_TENANT_ID")}
        with patch.dict(os.environ, clean_env, clear=True), \
             patch("clarity_agent.app_paths.clarity_data_dir", return_value=tmp_path):
            loaded = Settings.load(env_path=tmp_path / ".env")
        assert loaded.auth_mode == "device_code"
        assert loaded.tenant_id == "t-123"
