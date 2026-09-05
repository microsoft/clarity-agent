"""Tests for the model catalog: construction, caching, and provider listings."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clarity_agent.llm import LLMConfig
from clarity_agent.llm.factory import (
    fetch_model_catalog,
    get_provider_model_catalog,
)
from clarity_agent.llm.model_catalog import (
    CACHE_TTL_SECONDS,
    assign_roles,
    build_catalog,
    cache_key,
    clear_cache,
    default_model_for,
    describe_fetch_error,
    humanize_model_id,
    load_cached,
    store_cached,
)
from clarity_agent.llm.types import ModelCatalog, ModelInfo


@pytest.fixture(autouse=True)
def _clear_catalog_cache() -> Iterator[None]:
    """Drop the process-lifetime cache between tests."""
    clear_cache()
    yield
    clear_cache()


class _AsyncIter:
    """Minimal async-iterable standing in for a provider's paginator."""

    def __init__(self, items: Iterable[Any]) -> None:
        self._items = list(items)

    def __aiter__(self) -> Any:
        async def gen() -> Any:
            for item in self._items:
                yield item
        return gen()


async def _anthropic_catalog(listing: list[Any] | BaseException) -> ModelCatalog:
    """Run a full Anthropic catalog fetch against a faked ``/v1/models``.

    Goes through :func:`fetch_model_catalog` rather than the client
    method directly, since that's where fallback and error handling
    live.  Pass an exception to simulate a listing failure.
    """
    from clarity_agent.llm.impl import anthropic as impl

    client = MagicMock()
    if isinstance(listing, BaseException):
        client.models.list.side_effect = listing
    else:
        client.models.list.return_value = _AsyncIter(listing)
    with patch.object(impl._anthropic_mod, "AsyncAnthropic", return_value=client):
        return await fetch_model_catalog(_config("anthropic", auth_mode="api_key"))


def _config(provider: str, **kwargs: Any) -> LLMConfig:
    kwargs.setdefault("api_key", "test-key")
    return LLMConfig(provider=provider, **kwargs)


# ---------------------------------------------------------------------------
# Display names
# ---------------------------------------------------------------------------

class TestHumanizeModelId:
    @pytest.mark.parametrize(("model_id", "expected"), [
        ("claude-opus-5", "Claude Opus 5"),
        ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
        ("claude-sonnet-4-5-20250929", "Claude Sonnet 4.5"),
        ("claude-sonnet-4.6", "Claude Sonnet 4.6"),
        ("gpt-5.4", "GPT 5.4"),
        ("gpt-5.4-mini", "GPT 5.4 Mini"),
        ("gemini-3.1-flash-lite-preview", "Gemini 3.1 Flash Lite Preview"),
    ])
    def test_known_shapes(self, model_id: str, expected: str) -> None:
        assert humanize_model_id(model_id) == expected

    def test_unrecognized_id_is_not_mangled(self) -> None:
        assert humanize_model_id("my-custom-deployment") == "My Custom Deployment"

    def test_empty_input_returned_as_is(self) -> None:
        assert humanize_model_id("") == ""
        assert humanize_model_id("   ") == "   "


# ---------------------------------------------------------------------------
# Catalog construction
# ---------------------------------------------------------------------------

class TestAssignRoles:
    def test_roles_applied_from_recommendations(self) -> None:
        models = [ModelInfo(id="a", display_name="A"), ModelInfo(id="b", display_name="B")]
        tagged = assign_roles(models, {"deep": "a", "fast": "b"})
        assert [m.role for m in tagged] == ["deep", "fast"]

    def test_model_filling_two_roles_keeps_deep(self) -> None:
        """Anthropic's ``default`` and ``deep`` are the same model."""
        models = [ModelInfo(id="opus", display_name="Opus"), ModelInfo(id="sonnet", display_name="Sonnet")]
        tagged = assign_roles(models, {"default": "opus", "deep": "opus", "fast": "sonnet"})
        assert [(m.id, m.role) for m in tagged] == [("opus", "deep"), ("sonnet", "fast")]

    def test_unlisted_recommendation_is_ignored(self) -> None:
        models = [ModelInfo(id="a", display_name="A")]
        tagged = assign_roles(models, {"deep": "not-listed"})
        assert tagged[0].role is None


class TestDefaultModelFor:
    def test_prefers_deep_over_default(self) -> None:
        """The deep model is what every process actually runs on today."""
        assert default_model_for({"default": "sonnet", "deep": "opus", "fast": "haiku"}) == "opus"

    def test_falls_back_through_role_order(self) -> None:
        assert default_model_for({"default": "sonnet", "fast": "haiku"}) == "sonnet"
        assert default_model_for({"fast": "haiku"}) == "haiku"

    def test_empty_recommendations(self) -> None:
        assert default_model_for({}) == ""


class TestBuildCatalog:
    def test_builtin_uses_recommendations_and_context_windows(self) -> None:
        catalog = build_catalog(
            recommended={"default": "a", "deep": "a", "fast": "b"},
            context_windows={"a": 100, "b": 50, "c": 25},
        )
        assert [m.id for m in catalog.models] == ["a", "b", "c"]
        assert catalog.default_model == "a"
        assert catalog.get("c") is not None
        assert catalog.get("c").context_window == 25  # type: ignore[union-attr]

    def test_highlighted_models_sort_first(self) -> None:
        catalog = build_catalog(
            recommended={"deep": "b", "fast": "c"},
            model_ids=["a", "b", "c", "d"],
        )
        assert [m.id for m in catalog.models] == ["b", "c", "a", "d"]
        assert [m.id for m in catalog.highlighted] == ["b", "c"]
        assert [m.id for m in catalog.rest] == ["a", "d"]

    def test_unhighlighted_models_keep_provider_order(self) -> None:
        catalog = build_catalog(recommended={}, model_ids=["z", "m", "a"])
        assert [m.id for m in catalog.models] == ["z", "m", "a"]

    def test_duplicate_ids_collapse(self) -> None:
        catalog = build_catalog(recommended={}, model_ids=["a", "b", "a"])
        assert [m.id for m in catalog.models] == ["a", "b"]

    def test_live_display_names_win_over_derived(self) -> None:
        catalog = build_catalog(
            recommended={},
            model_ids=["claude-opus-5"],
            display_names={"claude-opus-5": "Claude Opus 5 (Latest)"},
        )
        assert catalog.models[0].display_name == "Claude Opus 5 (Latest)"

    def test_derives_display_name_when_provider_gives_none(self) -> None:
        catalog = build_catalog(recommended={}, model_ids=["gpt-5.4-mini"])
        assert catalog.models[0].display_name == "GPT 5.4 Mini"

    def test_default_missing_from_listing_is_still_offered(self) -> None:
        """A recommendation the provider no longer lists stays selectable."""
        catalog = build_catalog(recommended={"deep": "retired"}, model_ids=["a", "b"])
        assert catalog.default_model == "retired"
        assert catalog.models[0].id == "retired"
        assert catalog.models[0].role == "deep"

    def test_default_falls_back_to_first_model(self) -> None:
        catalog = build_catalog(recommended={}, model_ids=["a", "b"])
        assert catalog.default_model == "a"

    def test_empty_listing_stays_empty(self) -> None:
        """An empty listing must not be papered over with the default.

        ``fetch_model_catalog`` keys its fallback off an empty
        ``models``; inventing a one-model catalog here would hide a
        provider anomaly behind a plausible-looking answer.
        """
        catalog = build_catalog(recommended={"deep": "opus"}, model_ids=[])
        assert catalog.models == []

    def test_empty_catalog(self) -> None:
        catalog = build_catalog(recommended={}, model_ids=[])
        assert catalog.models == []
        assert catalog.default_model == ""


class TestModelCatalogAccessors:
    def test_get_returns_none_for_unknown_id(self) -> None:
        catalog = build_catalog(recommended={}, model_ids=["a"])
        assert catalog.get("nope") is None

    def test_highlighted_ordering_is_deep_default_fast(self) -> None:
        catalog = ModelCatalog(models=[
            ModelInfo(id="c", display_name="C", role="fast"),
            ModelInfo(id="a", display_name="A", role="deep"),
            ModelInfo(id="b", display_name="B", role="default"),
        ])
        assert [m.id for m in catalog.highlighted] == ["a", "b", "c"]


class TestDescribeFetchError:
    def test_includes_type_name(self) -> None:
        assert describe_fetch_error(ValueError("bad key")) == "ValueError: bad key"

    def test_truncates_and_takes_first_line(self) -> None:
        message = describe_fetch_error(RuntimeError("first\nsecond"))
        assert message == "RuntimeError: first"
        assert len(describe_fetch_error(RuntimeError("x" * 500))) <= 200


# ---------------------------------------------------------------------------
# Built-in catalogs, per provider
# ---------------------------------------------------------------------------

class TestBuiltinCatalogs:
    @pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini", "azure", "github"])
    def test_every_provider_has_a_nonempty_builtin_catalog(self, provider: str) -> None:
        catalog = get_provider_model_catalog(provider)
        assert catalog.models
        assert catalog.default_model
        assert catalog.source == "builtin"

    @pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini", "azure", "github"])
    def test_default_matches_the_provider_deep_tier(self, provider: str) -> None:
        """The default model must stay the deep one.

        Every process in ``process_registry`` maps to the ``"deep"``
        tier, so the deep model is what Clarity actually runs on.
        Defaulting to the ``default`` tier instead would silently
        downgrade providers whose two entries differ — GitHub Copilot
        being the live example.
        """
        from clarity_agent.llm.factory import get_provider_tier_defaults

        tiers = get_provider_tier_defaults(provider)
        catalog = get_provider_model_catalog(provider)
        assert catalog.default_model == tiers["deep"]

    def test_github_default_is_opus_not_sonnet(self) -> None:
        """Regression guard for the migration trap, stated concretely."""
        catalog = get_provider_model_catalog("github")
        assert catalog.default_model == "claude-opus-4.6"

    def test_azure_is_free_form(self) -> None:
        """Azure deployments are user-named, so the picker takes typed input."""
        assert get_provider_model_catalog("azure").free_form is True

    def test_other_providers_are_not_free_form(self) -> None:
        for provider in ["anthropic", "openai", "gemini", "github"]:
            assert get_provider_model_catalog(provider).free_form is False

    def test_unknown_provider_yields_empty_catalog(self) -> None:
        catalog = get_provider_model_catalog("nonesuch")
        assert catalog.models == []

    def test_client_chat_backend_refuses_rather_than_lying(self) -> None:
        """The wrapper shadows ``TIER_DEFAULTS`` with an instance property.

        Inheriting the class-level implementation would read the
        property object instead of a model table, so the override
        fails loudly.
        """
        from clarity_agent.llm import ClientChatBackend

        with pytest.raises(NotImplementedError, match="wraps an arbitrary client"):
            ClientChatBackend.builtin_catalog()

    def test_anthropic_auth_modes_share_a_catalog(self) -> None:
        assert (
            get_provider_model_catalog("anthropic", "api_key").models
            == get_provider_model_catalog("anthropic", "claude_sdk").models
        )


# ---------------------------------------------------------------------------
# Live provider listings
# ---------------------------------------------------------------------------

class TestAnthropicFetchModels:
    def _listing(self) -> list[Any]:
        return [
            SimpleNamespace(id="claude-opus-5", display_name="Claude Opus 5"),
            SimpleNamespace(id="claude-brand-new", display_name="Claude Brand New"),
        ]

    def test_uses_provider_listing(self) -> None:
        catalog = asyncio.run(_anthropic_catalog(self._listing()))

        assert catalog.source == "provider"
        assert catalog.error is None
        assert {m.id for m in catalog.models} == {"claude-opus-5", "claude-brand-new"}
        assert catalog.get("claude-brand-new").display_name == "Claude Brand New"  # type: ignore[union-attr]

    def test_context_windows_come_from_the_builtin_table(self) -> None:
        """The listing reports no context window, so we fill it in."""
        catalog = asyncio.run(_anthropic_catalog(self._listing()))

        assert catalog.get("claude-opus-5").context_window == 1_000_000  # type: ignore[union-attr]
        assert catalog.get("claude-brand-new").context_window is None  # type: ignore[union-attr]

    def test_claude_sdk_mode_uses_builtin(self) -> None:
        """The SDK borrows Claude Code's credentials; we have no key to list with.

        ``create_client`` refuses that auth mode, so no listing is even
        attempted and the built-in catalog comes back clean — no error,
        because nothing failed.
        """
        from clarity_agent.llm.impl import anthropic as impl

        with patch.object(impl._anthropic_mod, "AsyncAnthropic") as ctor:
            catalog = asyncio.run(fetch_model_catalog(
                _config("anthropic", auth_mode="claude_sdk", api_key=None),
            ))
        ctor.assert_not_called()
        assert catalog.source == "builtin"
        assert catalog.error is None

    def test_failure_falls_back_with_an_error_message(self) -> None:
        """Providers raise; the factory converts that to a usable fallback."""
        catalog = asyncio.run(_anthropic_catalog(RuntimeError("network down")))

        assert catalog.source == "builtin"
        assert catalog.models, "fallback must stay usable"
        assert catalog.error == "RuntimeError: network down"

    def test_empty_listing_falls_back(self) -> None:
        catalog = asyncio.run(_anthropic_catalog([]))
        assert catalog.source == "builtin"
        assert catalog.models


class TestOpenAIFetchModels:
    @pytest.mark.parametrize("model_id", [
        "gpt-5.4", "gpt-5.4-mini", "chatgpt-4o-latest", "o1", "o3-mini",
    ])
    def test_chat_models_accepted(self, model_id: str) -> None:
        from clarity_agent.llm.impl.openai import _is_chat_model
        assert _is_chat_model(model_id)

    @pytest.mark.parametrize("model_id", [
        "text-embedding-3-large", "tts-1", "whisper-1", "dall-e-3",
        "omni-moderation-latest", "gpt-4o-realtime-preview",
        "gpt-4o-audio-preview", "gpt-3.5-turbo-instruct", "davinci-002",
    ])
    def test_non_chat_models_rejected(self, model_id: str) -> None:
        from clarity_agent.llm.impl.openai import _is_chat_model
        assert not _is_chat_model(model_id)

    def test_filters_and_sorts_newest_first(self) -> None:
        from clarity_agent.llm.impl import openai as impl

        listing = [
            SimpleNamespace(id="gpt-4o", created=100),
            SimpleNamespace(id="text-embedding-3-large", created=400),
            SimpleNamespace(id="gpt-5.4", created=300),
            SimpleNamespace(id="whisper-1", created=500),
        ]
        client = MagicMock()
        client.models.list = AsyncMock(return_value=_AsyncIter(listing))
        with patch.object(impl._openai_mod, "AsyncOpenAI", return_value=client):
            catalog = asyncio.run(fetch_model_catalog(_config("openai")))

        assert catalog.source == "provider"
        # The embedding and speech models are filtered out.  gpt-5.4 is
        # the deep recommendation so it sorts to the front; gpt-4o
        # follows.  gpt-5.4-mini is *not* here: it's the fast
        # recommendation, but a live listing is authoritative about
        # what exists (see the sibling test below).
        assert [m.id for m in catalog.models] == ["gpt-5.4", "gpt-4o"]

    def test_failure_falls_back(self) -> None:
        from clarity_agent.llm.impl import openai as impl

        client = MagicMock()
        client.models.list = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(impl._openai_mod, "AsyncOpenAI", return_value=client):
            catalog = asyncio.run(fetch_model_catalog(_config("openai")))
        assert catalog.source == "builtin"
        assert catalog.error == "RuntimeError: boom"


class TestGeminiFetchModels:
    def _listing(self) -> list[Any]:
        return [
            SimpleNamespace(
                name="models/gemini-3.1-pro-preview",
                display_name="Gemini 3.1 Pro",
                description="  A  long\n  description  ",
                input_token_limit=2_000_000,
                supported_actions=["generateContent", "countTokens"],
            ),
            SimpleNamespace(
                name="models/text-embedding-004",
                display_name="Embedding",
                description=None,
                input_token_limit=2048,
                supported_actions=["embedContent"],
            ),
        ]

    def _client(self) -> MagicMock:
        client = MagicMock()
        client.aio.models.list = AsyncMock(return_value=_AsyncIter(self._listing()))
        return client

    def test_keeps_only_generate_content_models(self) -> None:
        from clarity_agent.llm.impl import gemini as impl

        with patch.object(impl._genai_mod, "Client", return_value=self._client()):
            catalog = asyncio.run(fetch_model_catalog(_config("gemini")))

        assert [m.id for m in catalog.models] == ["gemini-3.1-pro-preview"]
        assert catalog.source == "provider"

    def test_strips_models_prefix_and_uses_live_context_window(self) -> None:
        """Gemini is the one provider that reports a real window."""
        from clarity_agent.llm.impl import gemini as impl

        with patch.object(impl._genai_mod, "Client", return_value=self._client()):
            catalog = asyncio.run(fetch_model_catalog(_config("gemini")))

        model = catalog.models[0]
        assert model.id == "gemini-3.1-pro-preview"
        assert model.context_window == 2_000_000
        assert model.description == "A long description"

    def test_long_descriptions_are_shortened(self) -> None:
        from clarity_agent.llm.impl.gemini import _MAX_DESCRIPTION_CHARS, _shorten

        assert _shorten("x" * 500).endswith("…")
        assert len(_shorten("x" * 500)) <= _MAX_DESCRIPTION_CHARS

    def test_failure_falls_back(self) -> None:
        from clarity_agent.llm.impl import gemini as impl

        client = MagicMock()
        client.aio.models.list = AsyncMock(side_effect=RuntimeError("nope"))
        with patch.object(impl._genai_mod, "Client", return_value=client):
            catalog = asyncio.run(fetch_model_catalog(_config("gemini")))
        assert catalog.source == "builtin"
        assert catalog.error == "RuntimeError: nope"


class TestNonEnumerableProviders:
    def test_azure_never_builds_a_client_to_ask(self) -> None:
        """Free-form providers short-circuit before client construction.

        Azure's interactive auth mode builds a browser credential in its
        constructor; filling a dropdown must not pay that cost.
        """
        from clarity_agent.llm import factory

        with patch.object(factory, "create_client") as ctor:
            catalog = asyncio.run(fetch_model_catalog(
                _config("azure", endpoint="https://x", auth_mode="interactive"),
            ))
        ctor.assert_not_called()
        assert catalog.free_form is True
        assert catalog.source == "builtin"

    def test_github_returns_builtin(self) -> None:
        """Copilot is chat-only, so ``create_client`` refuses and we fall back."""
        catalog = asyncio.run(fetch_model_catalog(_config("github")))
        assert catalog.source == "builtin"
        assert catalog.default_model == "claude-opus-4.6"
        assert catalog.error is None


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

class TestCatalogCache:
    def _catalog(self, source: str = "provider") -> ModelCatalog:
        return ModelCatalog(
            models=[ModelInfo(id="a", display_name="A", role="deep", context_window=42)],
            default_model="a",
            source=source,
        )

    def test_cache_key_includes_auth_mode(self) -> None:
        assert cache_key("anthropic", "claude_sdk") == "anthropic:claude_sdk"
        assert cache_key("anthropic", None) == "anthropic:default"

    def test_round_trip(self) -> None:
        store_cached("p:m", self._catalog())
        loaded = load_cached("p:m")
        assert loaded is not None
        assert loaded.default_model == "a"
        assert loaded.models[0].role == "deep"
        assert loaded.models[0].context_window == 42

    def test_survives_a_fresh_process(self, tmp_path: Path) -> None:
        """The disk half of the cache works without the in-memory half."""
        store_cached("p:m", self._catalog())
        clear_cache.__globals__["_MEMORY_CACHE"].clear()
        assert load_cached("p:m") is not None

    def test_miss_returns_none(self) -> None:
        assert load_cached("never:stored") is None

    def test_builtin_catalogs_are_not_cached(self) -> None:
        """Caching a fallback would paper over an outage for a full day."""
        store_cached("p:m", self._catalog(source="builtin"))
        assert load_cached("p:m") is None

    def test_expired_entry_is_a_miss(self) -> None:
        store_cached("p:m", self._catalog())
        stale = time.time() - CACHE_TTL_SECONDS - 1
        clear_cache.__globals__["_MEMORY_CACHE"]["p:m"] = (
            stale, self._catalog(),
        )
        path = Path(load_cached.__globals__["_cache_path"]())
        data = json.loads(path.read_text())
        data["p:m"]["fetched_at"] = stale
        path.write_text(json.dumps(data))
        assert load_cached("p:m") is None

    def test_corrupt_cache_file_is_a_miss(self) -> None:
        store_cached("p:m", self._catalog())
        path = Path(load_cached.__globals__["_cache_path"]())
        path.write_text("{not json")
        clear_cache.__globals__["_MEMORY_CACHE"].clear()
        assert load_cached("p:m") is None

    def test_clear_cache_removes_the_file(self) -> None:
        store_cached("p:m", self._catalog())
        clear_cache()
        assert load_cached("p:m") is None


class TestFetchModelCatalog:
    def test_second_call_is_served_from_cache(self) -> None:
        from clarity_agent.llm.impl import anthropic as impl

        client = MagicMock()
        client.models.list.side_effect = lambda **_: _AsyncIter([
            SimpleNamespace(id="claude-opus-5", display_name="Claude Opus 5"),
        ])
        config = _config("anthropic", auth_mode="api_key")

        with patch.object(impl._anthropic_mod, "AsyncAnthropic", return_value=client):
            first = asyncio.run(fetch_model_catalog(config))
            second = asyncio.run(fetch_model_catalog(config))

        assert first.models == second.models
        assert client.models.list.call_count == 1

    def test_refresh_bypasses_the_cache(self) -> None:
        from clarity_agent.llm.impl import anthropic as impl

        client = MagicMock()
        client.models.list.side_effect = lambda **_: _AsyncIter([
            SimpleNamespace(id="claude-opus-5", display_name="Claude Opus 5"),
        ])
        config = _config("anthropic", auth_mode="api_key")

        with patch.object(impl._anthropic_mod, "AsyncAnthropic", return_value=client):
            asyncio.run(fetch_model_catalog(config))
            asyncio.run(fetch_model_catalog(config, refresh=True))

        assert client.models.list.call_count == 2

    def test_failed_fetch_is_not_cached(self) -> None:
        """A transient outage must not pin the fallback for a day."""
        from clarity_agent.llm.impl import anthropic as impl

        client = MagicMock()
        client.models.list.side_effect = RuntimeError("down")
        config = _config("anthropic", auth_mode="api_key")

        with patch.object(impl._anthropic_mod, "AsyncAnthropic", return_value=client):
            asyncio.run(fetch_model_catalog(config))
        assert load_cached(cache_key("anthropic", "api_key")) is None

    def test_unknown_provider_yields_empty_catalog(self) -> None:
        catalog = asyncio.run(fetch_model_catalog(_config("nonesuch")))
        assert catalog.models == []
