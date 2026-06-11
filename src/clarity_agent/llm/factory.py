"""Factory functions for creating LLM clients and chat backends."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from clarity_agent.llm.chat import ChatBackend
from clarity_agent.llm.client import LLMClient
from clarity_agent.llm.config import LLMConfig

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
