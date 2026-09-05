"""Factory functions for creating LLM clients and chat backends."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from clarity_agent.llm.chat import ChatBackend
from clarity_agent.llm.client import LLMClient
from clarity_agent.llm.config import LLMConfig
from clarity_agent.llm.types import ModelCatalog

# Deferred behind ``TYPE_CHECKING`` to avoid the circular import
# documented in ``clarity_agent.llm.chat`` — same reason applies here
# since this module sits in the same package.
if TYPE_CHECKING:
    from clarity_agent.transcript import Transcript


def get_provider_tier_defaults(
    provider: str,
    auth_mode: str | None = None,
) -> dict[str, str]:
    """Return TIER_DEFAULTS for a provider without instantiating a backend.

    Uses lazy imports so implementation modules (and their optional
    dependencies) are only loaded on demand.

    For providers with auth modes that use a different backend (e.g.
    Anthropic's ``claude_sdk`` mode uses :class:`SdkChatBackend` which
    has its own tier defaults), pass *auth_mode* to get the right set.
    """
    if provider == "anthropic":
        from clarity_agent.llm.impl.anthropic import _ANTHROPIC_TIER_DEFAULTS
        return _ANTHROPIC_TIER_DEFAULTS
    if provider == "azure":
        from clarity_agent.llm.impl.azure_inference import _AZURE_TIER_DEFAULTS
        return _AZURE_TIER_DEFAULTS
    if provider == "openai":
        from clarity_agent.llm.impl.openai import _OPENAI_TIER_DEFAULTS
        return _OPENAI_TIER_DEFAULTS
    if provider == "github":
        from clarity_agent.llm.impl.github_copilot import _GITHUB_TIER_DEFAULTS
        return _GITHUB_TIER_DEFAULTS
    if provider == "gemini":
        from clarity_agent.llm.impl.gemini import _GEMINI_TIER_DEFAULTS
        return _GEMINI_TIER_DEFAULTS
    return {}


def _catalog_source_class(
    provider: str,
    auth_mode: str | None = None,
) -> type[LLMClient] | type[ChatBackend] | None:
    """Return the class that owns *provider*'s model tables.

    Usually the :class:`LLMClient` subclass.  Two providers have no
    low-level client — GitHub Copilot, and Anthropic under the
    ``claude_sdk`` auth mode — so their :class:`ChatBackend` subclass
    carries the tables instead.  Both bases implement
    :meth:`builtin_catalog`, so callers don't have to care which they
    got.

    Anthropic returns ``AnthropicClient`` for either auth mode: the two
    modes reach the same models and share one table, and only the
    *listing* differs (``claude_sdk`` can't enumerate, which
    :func:`fetch_model_catalog` handles by never building a client).

    Lazy imports keep optional provider SDKs off the import path until
    the provider is actually used, matching
    :func:`get_provider_tier_defaults`.
    """
    if provider == "anthropic":
        from clarity_agent.llm.impl.anthropic import AnthropicClient
        return AnthropicClient
    if provider == "azure":
        from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
        return AzureInferenceClient
    if provider == "openai":
        from clarity_agent.llm.impl.openai import OpenAIClient
        return OpenAIClient
    if provider == "github":
        from clarity_agent.llm.impl.github_copilot import CopilotChatBackend
        return CopilotChatBackend
    if provider == "gemini":
        from clarity_agent.llm.impl.gemini import GeminiClient
        return GeminiClient
    return None


def get_provider_model_catalog(
    provider: str,
    auth_mode: str | None = None,
) -> ModelCatalog:
    """Return a provider's built-in :class:`ModelCatalog`, without network.

    The offline counterpart to :func:`fetch_model_catalog`: usable
    before credentials are resolved, and the fallback whenever a live
    listing fails.  Unknown providers yield an empty catalog rather
    than raising, so a stale settings file can't break the picker.
    """
    source = _catalog_source_class(provider, auth_mode)
    if source is None:
        return ModelCatalog()
    return source.builtin_catalog()


def _listing_client(config: LLMConfig) -> LLMClient | None:
    """Return a client able to enumerate models, or ``None``.

    Listing models is a weaker requirement than holding a conversation:
    it's one credentialed GET, with no runtime, session, or tool
    plumbing behind it.  So this is deliberately more permissive than
    :func:`create_client`.

    The case that matters is Anthropic's ``claude_sdk`` auth mode.
    ``create_client`` refuses it because *chat* has to go through the
    agent runtime, but that says nothing about ``/v1/models``.  Two
    credentials can serve that listing, in order of preference:

    1. An ``ANTHROPIC_API_KEY``, which :meth:`LLMConfig.create` picks
       up from the environment whatever auth mode is selected.
    2. Failing that, the OAuth token ``claude login`` stored — see
       :mod:`clarity_agent.llm.claude_code_auth` for why that's a
       best-effort last resort.

    With neither, there's nothing to enumerate with and the caller
    falls back to the built-in catalog.
    """
    if config.provider == "anthropic" and config.auth_mode == "claude_sdk":
        from clarity_agent.llm.impl.anthropic import AnthropicClient

        if config.api_key:
            return AnthropicClient(api_key=config.api_key)

        from clarity_agent.llm.claude_code_auth import find_oauth_token

        token = find_oauth_token()
        return AnthropicClient(auth_token=token) if token else None

    try:
        return create_client(config)
    except Exception:  # noqa: BLE001 — chat-only provider or partial credentials
        return None


async def fetch_model_catalog(
    config: LLMConfig,
    *,
    refresh: bool = False,
) -> ModelCatalog:
    """Return the models available for *config*, fetching live when possible.

    Results are cached per provider + auth mode for
    :data:`~clarity_agent.llm.model_catalog.CACHE_TTL_SECONDS`, so
    opening the model picker is normally free.  Pass ``refresh=True``
    to bypass the cache — that's what the picker's refresh control does.

    Never raises.  Every failure path returns the provider's built-in
    catalog, with :attr:`ModelCatalog.error` set when a live attempt
    actually failed, so the picker shows a usable list plus a note
    rather than an empty menu.  Because providers therefore don't need
    their own fallback logic, ``fetch_models`` implementations are free
    to just do the listing and raise.
    """
    from clarity_agent.llm.model_catalog import (
        cache_key,
        describe_fetch_error,
        load_cached,
        store_cached,
    )

    key = cache_key(config.provider, config.auth_mode)
    if not refresh:
        cached = load_cached(key)
        if cached is not None:
            return cached

    builtin = get_provider_model_catalog(config.provider, config.auth_mode)

    # Free-form providers have nothing to enumerate, and building a
    # client for them can be expensive (Azure's interactive auth mode
    # constructs a browser credential).  Don't bother.
    if builtin.free_form:
        return builtin

    client = _listing_client(config)
    if client is None:
        # Nothing that can enumerate for this config.  Not an error
        # worth surfacing — the built-in catalog is the right answer,
        # and a genuinely broken credential will announce itself on
        # the first chat turn.
        return builtin

    try:
        catalog = await client.fetch_models()
    except Exception as exc:  # noqa: BLE001 — any listing failure falls back
        return replace(builtin, error=describe_fetch_error(exc))

    if not catalog.models:
        return builtin

    store_cached(key, catalog)  # no-ops unless the catalog is live
    return catalog


def create_client(config: LLMConfig) -> LLMClient:
    """Create a low-level LLM client for the given configuration.

    Args:
        config: Resolved :class:`LLMConfig` specifying the provider and
            credentials.

    Returns:
        An :class:`LLMClient` instance.

    Raises:
        ValueError: If the provider is not recognized or the auth mode
            does not support a low-level client (e.g. ``claude_sdk``).
    """
    if config.provider == "anthropic":
        if config.auth_mode == "claude_sdk":
            raise ValueError(
                "The claude_sdk auth mode does not use a low-level LLMClient. "
                "Use create_chat_backend() instead."
            )
        assert config.api_key is not None, "Anthropic provider requires an API key"
        from clarity_agent.llm.impl.anthropic import AnthropicClient
        return AnthropicClient(api_key=config.api_key)
    if config.provider == "azure":
        from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
        assert config.endpoint is not None, "Azure provider requires an endpoint"
        return AzureInferenceClient(
            endpoint=config.endpoint,
            api_key=config.api_key,
            auth_mode=config.auth_mode or "default",
            tenant_id=config.tenant_id,
        )
    if config.provider == "openai":
        from clarity_agent.llm.impl.openai import OpenAIClient
        assert config.api_key is not None, "OpenAI provider requires an API key"
        return OpenAIClient(api_key=config.api_key)
    if config.provider == "gemini":
        from clarity_agent.llm.impl.gemini import GeminiClient
        assert config.api_key is not None, "Gemini provider requires an API key"
        return GeminiClient(api_key=config.api_key)
    if config.provider == "github":
        raise ValueError(
            "The github provider uses the Copilot SDK backend, not a "
            "low-level LLMClient. Use create_chat_backend() instead."
        )
    raise ValueError(
        f"Unknown LLM provider: {config.provider!r}. "
        f"Supported providers: 'anthropic', 'azure', 'gemini', 'github', 'openai'"
    )


def create_chat_backend(
    config: LLMConfig,
    *,
    project_dir: Path,
    clarity_agent_dir: Path,
    transcript: Transcript | None = None,
) -> ChatBackend:
    """Create a high-level chat backend for the given configuration.

    For API-backed providers (anthropic, openai, azure), creates a
    :class:`ClientChatBackend` wrapping the appropriate :class:`LLMClient`.
    For Anthropic with ``claude_sdk`` auth mode, creates a
    :class:`SdkChatBackend` that wraps the Claude Code agent runtime.

    Args:
        config: Resolved :class:`LLMConfig` specifying the provider,
            model, and credentials.
        project_dir: Path to the project being analyzed.
        clarity_agent_dir: Path to the clarity agent installation.
        transcript: Optional :class:`Transcript` to bind for
            compaction recording.  Without one, the backend's
            compaction machinery is silently disabled.

    Returns:
        A :class:`ChatBackend` instance.

    Raises:
        ValueError: If the provider is not recognized.
    """
    # Both Anthropic auth modes route through SdkChatBackend (the
    # Claude Agent SDK runtime).  The difference is just *how* the
    # SDK authenticates:
    #
    #   - ``api_key``    → explicit ``ANTHROPIC_API_KEY`` passed in.
    #                      Recommended; works anywhere with no extra
    #                      setup.
    #   - ``claude_sdk`` → SDK uses ``claude login`` credentials.
    #                      Convenient for existing Claude Code users
    #                      but officially off-label and may be
    #                      removed by Anthropic in the future.
    #
    # The low-level :class:`AnthropicClient` is no longer used as a
    # chat backend — keeping every Anthropic conversation on the SDK
    # runtime means tool calls, compaction, and session resume all
    # use the same code path regardless of how the user authed.
    if config.provider == "anthropic":
        from clarity_agent.llm.impl.claude_sdk import SdkChatBackend
        return SdkChatBackend(
            project_dir=project_dir,
            clarity_agent_dir=clarity_agent_dir,
            api_key=config.api_key,
            transcript=transcript,
        )

    # The github provider uses the Copilot SDK agent runtime.
    # Auth-mode dispatch:
    #   - "token"      → explicit GITHUB_TOKEN, passed as-is
    #   - "sdk_native" → ``token=None`` → SDK uses its own logged-in
    #                    user (``use_logged_in_user=True``)
    #   - "gh_cli"     → pull a token from ``gh auth token`` and pass
    #                    it to the SDK like an explicit token
    if config.provider == "github":
        from clarity_agent.llm.impl.github_copilot import (
            CopilotChatBackend,
            get_gh_cli_token,
        )
        token = config.api_key
        if not token and config.auth_mode == "gh_cli":
            token = get_gh_cli_token(raise_on_failure=True)
        return CopilotChatBackend(
            project_dir=project_dir,
            clarity_agent_dir=clarity_agent_dir,
            token=token,
            transcript=transcript,
        )

    # All other provider+auth combinations use ClientChatBackend.
    from clarity_agent.llm.chat import ClientChatBackend
    client = create_client(config)
    return ClientChatBackend(
        client,
        project_dir=project_dir,
        clarity_agent_dir=clarity_agent_dir,
        tiers=config.tiers,
        transcript=transcript,
    )
