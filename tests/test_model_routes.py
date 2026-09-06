"""Tests for the model picker's API surface.

``GET /api/models`` lists what a provider offers; ``PUT /api/model``
switches to one.  The switch has to land in three places — the live
backend, the session's config, and saved settings — because the picker
is a remembered preference, not a per-session toggle (issue #172).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from clarity_agent.llm import LLMConfig
from clarity_agent.llm.model_catalog import clear_cache
from clarity_agent.llm.types import ModelCatalog, ModelInfo
from clarity_agent.settings import Settings
from clarity_agent.web.session_manager import WebSessionAdapter


@pytest.fixture(autouse=True)
def _clear_catalog_cache() -> Any:
    clear_cache()
    yield
    clear_cache()


def _config(**kwargs: Any) -> LLMConfig:
    kwargs.setdefault("provider", "anthropic")
    kwargs.setdefault("api_key", "test-key")
    kwargs.setdefault("auth_mode", "api_key")
    return LLMConfig(**kwargs)


def _catalog() -> ModelCatalog:
    return ModelCatalog(
        models=[
            ModelInfo(id="claude-opus-5", display_name="Claude Opus 5",
                      role="default", context_window=1_000_000),
            ModelInfo(id="claude-fable-5-1", display_name="Claude Fable 5.1",
                      role="deep"),
            ModelInfo(id="claude-opus-4-7", display_name="Claude Opus 4.7"),
        ],
        default_model="claude-opus-5",
        source="provider",
    )


class TestSetModel:
    """``WebSessionAdapter.set_model`` — the part that has to stick."""

    def _adapter(self, tmp_path: Path, **cfg: Any) -> WebSessionAdapter:
        return WebSessionAdapter(tmp_path, tmp_path, _config(**cfg))

    def test_applies_to_the_live_backend(self, tmp_path: Path) -> None:
        """The next turn has to use it, not the one after."""
        adapter = self._adapter(tmp_path)
        backend = MagicMock()
        backend.resolve_model.side_effect = lambda m: m or "claude-opus-4-7"
        adapter._backend = backend

        adapter.set_model("claude-opus-4-7")

        assert backend._model == "claude-opus-4-7"

    def test_applies_to_the_session_config(self, tmp_path: Path) -> None:
        """A backend rebuilt later — new chapter, reconnect — must agree."""
        adapter = self._adapter(tmp_path)
        adapter.set_model("claude-fable-5-1")
        assert adapter.llm_config.model == "claude-fable-5-1"

    def test_persists_to_settings(self, tmp_path: Path) -> None:
        """The issue asks for the choice to be remembered across sessions."""
        adapter = self._adapter(tmp_path)
        adapter.set_model("claude-fable-5-1")

        assert Settings.current().model == "claude-fable-5-1"
        reloaded = Settings.load()
        assert reloaded.model == "claude-fable-5-1"

    def test_returns_the_active_model_for_echoing_back(self, tmp_path: Path) -> None:
        adapter = self._adapter(tmp_path)
        backend = MagicMock()
        backend.resolve_model.side_effect = lambda m: m or "claude-opus-4-7"
        adapter._backend = backend

        assert adapter.set_model("claude-opus-4-7") == "claude-opus-4-7"

    def test_works_before_a_backend_exists(self, tmp_path: Path) -> None:
        """Selecting a model during startup shouldn't need a live session."""
        adapter = self._adapter(tmp_path)
        assert adapter._backend is None
        assert adapter.set_model("claude-fable-5-1") == "claude-fable-5-1"


class TestProcessesDoNotOverrideTheModel:
    def test_resolve_model_never_returns_a_per_process_choice(
        self, tmp_path: Path,
    ) -> None:
        """Processes stopped picking models when the tiers went away.

        ``None`` means "use the backend's configured model", which is
        what ``set_model`` keeps current.
        """
        adapter = WebSessionAdapter(tmp_path, tmp_path, _config())
        assert adapter._resolve_model("architecture-design") is None
        assert adapter._resolve_model(None) is None


class TestModelsEndpointShape:
    """What ``GET /api/models`` hands the picker."""

    def _payload(self, catalog: ModelCatalog, current: str) -> dict[str, Any]:
        # Mirrors the endpoint's serialization; kept here so a change to
        # the wire shape has to be made deliberately in both places.
        return {
            "models": [
                {
                    "id": m.id,
                    "display_name": m.display_name,
                    "role": m.role,
                    "description": m.description,
                    "context_window": m.context_window,
                }
                for m in catalog.models
            ],
            "current": current,
            "default_model": catalog.default_model,
            "source": catalog.source,
            "free_form": catalog.free_form,
            "error": catalog.error,
        }

    def test_carries_everything_the_picker_groups_by(self) -> None:
        payload = self._payload(_catalog(), "claude-opus-5")

        assert payload["current"] == "claude-opus-5"
        roles = [m["role"] for m in payload["models"]]
        assert roles == ["default", "deep", None]
        assert payload["models"][0]["context_window"] == 1_000_000

    def test_error_and_source_survive_a_failed_fetch(self) -> None:
        payload = self._payload(
            ModelCatalog(
                models=[ModelInfo(id="a", display_name="A")],
                default_model="a", source="builtin", error="boom",
            ),
            "a",
        )
        assert payload["source"] == "builtin"
        assert payload["error"] == "boom"

    def test_free_form_is_reported_so_the_picker_takes_typed_input(self) -> None:
        from clarity_agent.llm.factory import get_provider_model_catalog

        payload = self._payload(get_provider_model_catalog("azure"), "gpt-5.4")
        assert payload["free_form"] is True


class TestSetModelRequest:
    def test_rejects_a_missing_model(self) -> None:
        import pydantic

        from clarity_agent.web.models import SetModelRequest

        with pytest.raises(pydantic.ValidationError):
            SetModelRequest()  # type: ignore[call-arg]

    def test_accepts_any_identifier(self) -> None:
        """Free-form providers take deployment names we can't validate."""
        from clarity_agent.web.models import SetModelRequest

        assert SetModelRequest(model="my-azure-deployment").model == "my-azure-deployment"


class TestCatalogFetchIsNeverFatal:
    def test_endpoint_path_survives_a_provider_outage(self) -> None:
        """The picker must show something rather than an empty menu."""
        import asyncio

        from clarity_agent.llm.factory import fetch_model_catalog
        from clarity_agent.llm.impl import anthropic as impl

        client = MagicMock()
        client.models.list.side_effect = RuntimeError("provider down")
        with patch.object(impl._anthropic_mod, "AsyncAnthropic", return_value=client):
            catalog = asyncio.run(fetch_model_catalog(_config()))

        assert catalog.models, "must still offer the built-in list"
        assert catalog.error
