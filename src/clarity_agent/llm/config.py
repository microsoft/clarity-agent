"""CLI configuration helpers for LLM backends.

Provides :class:`LLMConfig` to register standard flags on an
:class:`argparse.ArgumentParser`, resolve settings from the parsed
arguments and environment, and create clients or backends.

Typical usage in a CLI entry point::

    LLMConfig.add_arguments(parser)
    args = parser.parse_args()
    config = LLMConfig.create(args)
    client = config.create_client()
"""

from __future__ import annotations

import argparse
import copy
import importlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class LLMConfigError(Exception):
    """Raised when LLM configuration cannot be resolved.

    Replaces the old ``sys.exit(1)`` pattern so callers can handle
    the error gracefully (e.g. the web server can start the setup
    wizard instead of dying).
    """


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

# Maps provider name to metadata used during resolution.
# Model defaults live on the implementation classes (TIER_DEFAULTS);
# this registry has connectivity, package metadata, and per-provider
# auth mode definitions (ordered by preference — first = recommended).
_PROVIDERS: dict[str, dict[str, Any]] = {
    "anthropic": {
        "display_name": "Anthropic (Claude)",
        "description": "Claude AI models from Anthropic",
        "endpoint_env_var": None,
        "auth_modes": [
            {
                "name": "claude_sdk",
                "display_name": "Claude Code",
                "description": (
                    "Sign in through Claude Code — no API key needed. "
                    "Best for personal use and development."
                ),
                "package": "claude_agent_sdk",
                "env_var": None,
                "setup_help": (
                    "This option uses the Claude Code CLI's authentication. "
                    "You must have run 'claude login' in your terminal first."
                ),
                "setup_url": "https://claude.ai/download",
                "fields": [],
            },
            {
                "name": "api_key",
                "display_name": "API Key",
                "description": (
                    "Use an API key from console.anthropic.com. "
                    "Best for teams and automated setups."
                ),
                "package": "anthropic",
                "env_var": "ANTHROPIC_API_KEY",
                "setup_help": (
                    "You'll need an API key from your Anthropic account. "
                    "Go to console.anthropic.com, sign in, then navigate to "
                    "API Keys to create one."
                ),
                "setup_url": "https://console.anthropic.com/settings/keys",
                "fields": [
                    {"key": "ANTHROPIC_API_KEY", "label": "API Key",
                     "secret": True,
                     "help": "Starts with sk-ant-. Found under API Keys "
                             "in the Anthropic Console."},
                ],
            },
        ],
    },
    "openai": {
        "display_name": "OpenAI (GPT)",
        "description": "GPT models from OpenAI",
        "endpoint_env_var": None,
        "auth_modes": [
            {
                "name": "api_key",
                "display_name": "API Key",
                "description": "Use an API key from platform.openai.com.",
                "package": "openai",
                "env_var": "OPENAI_API_KEY",
                "setup_help": (
                    "You'll need an API key from your OpenAI account. "
                    "Go to platform.openai.com, sign in, then navigate to "
                    "API Keys to create one."
                ),
                "setup_url": "https://platform.openai.com/api-keys",
                "fields": [
                    {"key": "OPENAI_API_KEY", "label": "API Key",
                     "secret": True,
                     "help": "Starts with sk-. Found under API Keys "
                             "in the OpenAI dashboard."},
                ],
            },
        ],
    },
    "azure": {
        "display_name": "Azure AI",
        "description": "Azure-hosted models (requires Azure subscription)",
        "endpoint_env_var": "AZURE_AI_ENDPOINT",
        "setup_url": "https://ai.azure.com/",
        # Fields needed regardless of auth mode.
        "common_fields": [
            {"key": "AZURE_AI_ENDPOINT", "label": "Endpoint URL",
             "secret": False,
             "placeholder": "https://your-resource.openai.azure.com",
             "help": "From your Azure AI resource's Keys and Endpoint page."},
            {"key": "CLARITY_MODEL_DEFAULT", "label": "Deployment Name",
             "secret": False,
             "placeholder": "gpt-4o",
             "help": "The name of your model deployment in Azure. Found under Deployments in the Azure AI portal."},
        ],
        "auth_modes": [
            {
                "name": "interactive",
                "display_name": "Sign in with Microsoft",
                "description": "Opens your browser to sign in to Azure.",
                "package": "azure.identity",
                "env_var": None,
                "setup_help": (
                    "Sign in with your Microsoft account. You need an Azure "
                    "subscription with an AI deployment."
                ),
                "setup_url": "https://ai.azure.com/",
                "fields": [
                    {"key": "CLARITY_TENANT_ID", "label": "Tenant ID",
                     "secret": False, "optional": True,
                     "help": "Your Azure AD tenant ID. Leave blank for multi-tenant."},
                ],
            },
            {
                "name": "default",
                "display_name": "Azure CLI / Managed Identity",
                "description": (
                    "Uses your existing az login session or managed identity. "
                    "No extra credentials needed."
                ),
                "package": "azure.identity",
                "env_var": None,
                "fields": [],
            },
            {
                "name": "api_key",
                "display_name": "API Key",
                "description": "Paste a key from your Azure resource.",
                "package": "azure.ai.inference",
                "env_var": "AZURE_AI_API_KEY",
                "setup_help": (
                    "You need an API key. Find it on the Keys and Endpoint "
                    "page of your Azure resource."
                ),
                "setup_url": "https://ai.azure.com/",
                "fields": [
                    {"key": "AZURE_AI_API_KEY", "label": "API Key",
                     "secret": True},
                ],
            },
            {
                "name": "device_code",
                "display_name": "Device Code",
                "description": (
                    "For servers and headless environments — displays a "
                    "code to enter at a URL."
                ),
                "package": "azure.identity",
                "env_var": None,
                "fields": [],
            },
        ],
    },
    "github": {
        "display_name": "GitHub Copilot",
        "description": "AI models via GitHub Copilot (uses your GitHub account)",
        "endpoint_env_var": None,
        "auth_modes": [
            {
                "name": "gh_cli",
                "display_name": "GitHub CLI",
                "description": (
                    "Zero-config via the gh CLI — uses your existing "
                    "GitHub login. No token needed."
                ),
                "package": "copilot",
                "env_var": None,
                "setup_help": (
                    "This option uses the GitHub CLI's authentication. "
                    "You must have run 'gh auth login' first."
                ),
                "setup_url": "https://cli.github.com/",
                "fields": [],
            },
            {
                "name": "token",
                "display_name": "Personal Access Token",
                "description": (
                    "Use a GitHub personal access token. "
                    "Best for CI and automated setups."
                ),
                "package": "copilot",
                "env_var": "GITHUB_TOKEN",
                "setup_help": (
                    "Create a personal access token at github.com/settings/tokens. "
                    "No special scopes are required for GitHub Copilot."
                ),
                "setup_url": "https://github.com/settings/tokens",
                "fields": [
                    {"key": "GITHUB_TOKEN", "label": "GitHub Token",
                     "secret": True,
                     "help": "A GitHub personal access token (classic or fine-grained)."},
                ],
            },
        ],
    },
    "gemini": {
        "display_name": "Google Gemini",
        "description": "Gemini models from Google (gemini-2.5-pro, gemini-2.5-flash)",
        "endpoint_env_var": None,
        "auth_modes": [
            {
                "name": "api_key",
                "display_name": "API Key",
                "description": "Use an API key from Google AI Studio.",
                "package": "google.genai",
                "env_var": "GEMINI_API_KEY",
                "setup_help": (
                    "You'll need an API key from Google AI Studio. "
                    "Sign in and create one under API Keys."
                ),
                "setup_url": "https://aistudio.google.com/apikey",
                "fields": [
                    {"key": "GEMINI_API_KEY", "label": "API Key",
                     "secret": True,
                     "help": "From Google AI Studio (aistudio.google.com/apikey)."},
                ],
            },
        ],
    },
}


def get_auth_mode_info(provider: str, auth_mode_name: str) -> dict[str, Any] | None:
    """Look up auth mode metadata by provider and mode name."""
    info = _PROVIDERS.get(provider)
    if info is None:
        return None
    for mode in info["auth_modes"]:
        if mode["name"] == auth_mode_name:
            return mode
    return None


def get_auth_mode_names(provider: str) -> list[str]:
    """Return the ordered list of auth mode names for a provider."""
    info = _PROVIDERS.get(provider)
    if info is None:
        return []
    return [m["name"] for m in info["auth_modes"]]


def get_default_auth_mode(provider: str) -> str | None:
    """Return the first (preferred) auth mode name for a provider."""
    names = get_auth_mode_names(provider)
    return names[0] if names else None


# ---------------------------------------------------------------------------
# Default process-to-tier mapping (derived from process_registry)
# ---------------------------------------------------------------------------

from clarity_agent.process_registry import (  # noqa: E402 — late import avoids circular dependency
    get_default_process_tiers,
)

_DEFAULT_PROCESS_TIERS: dict[str, str] = get_default_process_tiers()



def _check_package(package: str, provider: str) -> None:
    """Verify that a provider's required package is importable."""
    try:
        importlib.import_module(package)
    except ImportError as exc:
        raise LLMConfigError(
            f"Provider {provider!r} requires the '{package}' package, "
            f"but it is not installed."
        ) from exc


def _has_package(package: str) -> bool:
    """Return True if *package* can be imported."""
    try:
        importlib.import_module(package)
        return True
    except ImportError:
        return False


def _auto_detect_provider() -> tuple[str, str] | None:
    """Probe the environment and return the best available (provider, auth_mode).

    Detection order (first match wins):

    1. ``ANTHROPIC_API_KEY`` present → ``("anthropic", "api_key")``
    2. ``OPENAI_API_KEY`` present → ``("openai", "api_key")``
    3. ``AZURE_AI_ENDPOINT`` present → ``("azure", <best available mode>)``
    4. ``CLAUDECODE`` present → ``("anthropic", "claude_sdk")``
    5. Nothing found → ``None``

    Each candidate is only returned if its required package is also
    installed, so a stray env var without the SDK won't cause a
    confusing error.
    """
    # Explicit selection — always takes priority.  The env var may be
    # a legacy "claude-sdk" value, so migrate it.
    explicit = os.environ.get("CLARITY_LLM_PROVIDER")
    if explicit:
        if explicit == "claude-sdk":
            return ("anthropic", "claude_sdk")
        return (explicit, os.environ.get("CLARITY_AUTH_MODE", "api_key"))

    # Direct API providers — fastest, preferred when credentials exist.
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ("anthropic", "api_key")
    if os.environ.get("OPENAI_API_KEY"):
        return ("openai", "api_key")
    if os.environ.get("AZURE_AI_ENDPOINT"):
        if os.environ.get("AZURE_AI_API_KEY"):
            return ("azure", "api_key")
        return ("azure", "default")
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return ("gemini", "api_key")

    # GitHub Copilot — explicit GITHUB_TOKEN takes priority.
    if os.environ.get("GITHUB_TOKEN"):
        return ("github", "token")

    # Claude Code environment — SDK manages its own auth.
    # claude_agent_sdk is in the [cli] extra, not a base dependency.
    if os.environ.get("CLAUDECODE") and _has_package("claude_agent_sdk"):
        return ("anthropic", "claude_sdk")

    # GitHub Copilot via gh CLI — most ambient fallback (almost any
    # developer has `gh` installed), so check last.
    from clarity_agent.llm.impl.github_copilot import get_gh_cli_token
    if get_gh_cli_token():
        return ("github", "gh_cli")

    return None


# ---------------------------------------------------------------------------
# LLMConfig
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    """Resolved LLM configuration ready for client creation.

    Typically produced by :meth:`LLMConfig.create` from parsed CLI
    arguments, but direct construction is fine for programmatic use.

    Class methods provide the full CLI workflow:

    1. :meth:`add_arguments` — register ``--provider``, ``--api-key``,
       ``--model`` on an :class:`argparse.ArgumentParser`.
    2. :meth:`create` — resolve a config from parsed arguments, loading
       ``.env`` files, checking package health, and resolving API keys.

    Instance methods create the LLM objects:

    - :meth:`create_client` — low-level :class:`~clarity_agent.llm.LLMClient`
    - :meth:`create_chat_backend` — high-level :class:`~clarity_agent.llm.ChatBackend`

    Model tier support:

    - :attr:`tiers` — tier-to-model mapping.  ``tiers["default"]`` is
      always set and determines the model used when no tier override is
      active.  ``--model`` sets ``tiers["default"]``, just as
      ``--model-deep`` sets ``tiers["deep"]``.
    - :attr:`process_overrides` — per-process tier/model overrides.
    - :meth:`resolve` — resolve a process name to a tier name or model string.
    - :meth:`resolve_tier` — resolve a process name to its tier name.
    """

    provider: str
    api_key: str | None
    endpoint: str | None = None
    auth_mode: str | None = None
    tenant_id: str | None = None
    tiers: dict[str, str] = field(default_factory=dict)
    process_overrides: dict[str, str] = field(default_factory=dict)

    # -------------------------------------------------------------------
    # Process-to-tier resolution
    # -------------------------------------------------------------------

    def resolve(self, process_name: str) -> str:
        """Return a tier name or model string for *process_name*.

        Resolution order:

        1. ``process_overrides[process_name]`` (tier name or model string)
        2. Built-in ``_DEFAULT_PROCESS_TIERS[process_name]``
        3. ``"default"``

        If the resolved value is a tier name that has a user override in
        :attr:`tiers`, the override is returned.  Otherwise the raw tier
        name (or model string) is returned for the backend to resolve.
        """
        raw = self.process_overrides.get(process_name)
        if raw is None:
            raw = _DEFAULT_PROCESS_TIERS.get(process_name, "default")
        return self.tiers.get(raw, raw)

    def resolve_tier(self, process_name: str) -> str:
        """Return the tier name (not model) for *process_name*.

        Returns ``"default"``, ``"deep"``, ``"fast"``, or a custom
        tier/model string if a per-process override is set.
        """
        raw = self.process_overrides.get(process_name)
        if raw is None:
            raw = _DEFAULT_PROCESS_TIERS.get(process_name, "default")
        return raw

    # -------------------------------------------------------------------
    # Class methods — CLI registration and resolution
    # -------------------------------------------------------------------

    @classmethod
    def add_arguments(
        cls,
        parser: argparse.ArgumentParser,
        *,
        default_provider: str | None = None,
    ) -> None:
        """Add ``--provider``, ``--api-key``, and ``--model`` to *parser*.

        The flags are placed in an "LLM backend" argument group so they
        appear together in ``--help`` output.

        Args:
            parser: The argument parser to extend.
            default_provider: Provider used when ``--provider`` is not given.
                When ``None`` (the default), :meth:`create` auto-detects
                the best provider from the environment.
        """
        group = parser.add_argument_group("LLM backend")
        group.add_argument(
            "--provider",
            default=default_provider,
            choices=sorted(_PROVIDERS),
            help="LLM provider (default: auto-detect from environment)",
        )
        group.add_argument(
            "--api-key",
            help="API key (or set via environment variable, e.g. ANTHROPIC_API_KEY)",
        )
        group.add_argument(
            "--model",
            default=None,
            help="Model to use (default: provider-specific)",
        )
        group.add_argument(
            "--endpoint",
            help="Provider endpoint URL (or set via environment variable, e.g. AZURE_AI_ENDPOINT)",
        )
        group.add_argument(
            "--auth-mode",
            default=None,
            help="Authentication mode (e.g. api_key, default, interactive, device_code)",
        )
        group.add_argument(
            "--model-deep",
            default=None,
            help="Model for deep-thinking processes (problem clarification, architecture, decisions)",
        )
        group.add_argument(
            "--model-fast",
            default=None,
            help="Model for fast/cheap tasks (thinker runs, routing)",
        )

    @classmethod
    def create(
        cls,
        args: argparse.Namespace,
    ) -> LLMConfig:
        """Resolve an :class:`LLMConfig` from parsed arguments.

        Reads credentials and preferences from :meth:`Settings.current()`.
        CLI arguments override settings where applicable.
        """
        from clarity_agent.settings import Settings

        s = Settings.current()

        provider: str | None = getattr(args, "provider", None)
        api_key: str | None = getattr(args, "api_key", None)
        endpoint: str | None = getattr(args, "endpoint", None)
        detected_auth_mode: str | None = None

        # Migrate legacy "claude-sdk" CLI arg.
        if provider == "claude-sdk":
            provider = "anthropic"
            detected_auth_mode = "claude_sdk"

        # Auto-detect provider when not explicitly specified.
        # (Settings.load() already migrates stored "claude-sdk" values.)
        if provider is None and s.provider is not None:
            provider = s.provider
        if provider is None:
            detected = _auto_detect_provider()
            if detected is None:
                raise LLMConfigError(
                    "No LLM provider detected. Either:\n"
                    "  - Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or "
                    "AZURE_AI_API_KEY + AZURE_AI_ENDPOINT\n"
                    "  - Run inside Claude Code (sets CLAUDECODE automatically)\n"
                    "  - Pass --provider explicitly"
                )
            provider, detected_auth_mode = detected

        info = _PROVIDERS.get(provider)
        if info is None:
            raise ValueError(f"Unknown provider: {provider!r}")

        supported_mode_names = get_auth_mode_names(provider)

        # Resolve auth mode: CLI arg > settings > auto-detected > inferred.
        auth_mode: str | None = getattr(args, "auth_mode", None)
        if not auth_mode:
            stored_mode = s.auth_mode
            # Validate stored mode is still valid for this provider.
            if stored_mode and stored_mode in supported_mode_names:
                auth_mode = stored_mode
        if not auth_mode:
            auth_mode = detected_auth_mode

        # Resolve the API key: CLI arg > settings > env var from auth mode.
        if not api_key:
            # Try env vars from all auth modes for this provider (the active
            # mode's env var and any others — a key set in the environment
            # should be picked up regardless of which mode is selected).
            for mode_info in info["auth_modes"]:
                ev = mode_info.get("env_var")
                if ev:
                    api_key = s.get(ev)
                    if api_key:
                        break

        # Gemini also accepts GOOGLE_API_KEY as a standard alternative.
        if not api_key and provider == "gemini":
            api_key = os.environ.get("GOOGLE_API_KEY")

        # If no auth mode yet, infer from credentials.
        if not auth_mode:
            if api_key:
                # Find the auth mode that uses the env var we resolved from.
                for candidate in info["auth_modes"]:
                    if candidate.get("env_var") and s.get(candidate["env_var"]):
                        auth_mode = candidate["name"]
                        break
                if not auth_mode and "api_key" in supported_mode_names:
                    auth_mode = "api_key"
            if not auth_mode:
                auth_mode = get_default_auth_mode(provider)

        # Validate auth mode against provider capabilities.
        if auth_mode and supported_mode_names and auth_mode not in supported_mode_names:
            raise LLMConfigError(
                f"Auth mode {auth_mode!r} is not supported by provider "
                f"{provider!r}. Supported modes: {', '.join(supported_mode_names)}"
            )

        # Check that the auth mode's required package is installed.
        mode_info = get_auth_mode_info(provider, auth_mode) if auth_mode else None
        if mode_info and mode_info.get("package"):
            _check_package(mode_info["package"], provider)

        # API key / token is required for credential-based auth modes.
        if auth_mode in ("api_key", "token") and not api_key:
            env_var: str = (mode_info or {}).get("env_var", "")
            raise LLMConfigError(
                f"No API key for {provider}. "
                f"Set {env_var} or use --api-key."
            )

        # Resolve tenant ID (used by Azure and potentially other providers).
        tenant_id: str | None = s.tenant_id

        # Resolve the endpoint: CLI arg > settings.
        endpoint_env_var: str | None = info.get("endpoint_env_var")
        if endpoint_env_var and not endpoint:
            endpoint = s.get(endpoint_env_var)
            if not endpoint:
                raise LLMConfigError(
                    f"No endpoint URL for {provider}. "
                    f"Set {endpoint_env_var} or use --endpoint."
                )

        # Resolve tier overrides: CLI flag > settings > provider default.
        from clarity_agent.llm.factory import get_provider_tier_defaults
        provider_defaults = get_provider_tier_defaults(provider, auth_mode)

        tiers: dict[str, str] = {}
        model: str | None = getattr(args, "model", None)
        model_deep: str | None = getattr(args, "model_deep", None)
        model_fast: str | None = getattr(args, "model_fast", None)

        settings_tiers = s.tier_overrides
        for tier_name, cli_value in [("default", model), ("deep", model_deep), ("fast", model_fast)]:
            if cli_value:
                tiers[tier_name] = cli_value
            elif tier_name in settings_tiers:
                tiers[tier_name] = settings_tiers[tier_name]

        # Ensure "default" is always populated.
        if "default" not in tiers:
            tiers["default"] = provider_defaults.get("default", "unknown")

        # Per-process overrides from settings.
        process_overrides: dict[str, str] = dict(s.process_model_overrides)

        # Persist the resolved provider + auth mode back to settings so
        # the UI and future loads see the same values without re-detecting.
        if s.provider != provider or s.auth_mode != auth_mode:
            s.provider = provider
            s.auth_mode = auth_mode
            if auth_mode:
                s.provider_auth_modes[provider] = auth_mode
            s.save()

        return cls(
            provider=provider, api_key=api_key,
            endpoint=endpoint, auth_mode=auth_mode,
            tenant_id=tenant_id, tiers=tiers,
            process_overrides=process_overrides,
        )

    # -------------------------------------------------------------------
    # Instance methods — client / backend creation
    # -------------------------------------------------------------------

    def with_model(self, model: str) -> LLMConfig:
        """Return a shallow copy with a different default model.

        Useful when creating separate clients (e.g. for brainstorm
        thinker runs) that need a different model but the same
        provider and credentials.
        """
        clone = copy.copy(self)
        clone.tiers = {**self.tiers, "default": model}
        return clone

    def create_client(self) -> Any:
        """Create a low-level :class:`~clarity_agent.llm.LLMClient`.

        The return type is ``LLMClient``; typed as ``Any`` here to
        avoid a circular import at module level.
        """
        from clarity_agent.llm.factory import create_client
        return create_client(self)

    def create_chat_backend(
        self,
        *,
        project_dir: Path,
        clarity_agent_dir: Path,
    ) -> Any:
        """Create a high-level :class:`~clarity_agent.llm.ChatBackend`.

        The return type is ``ChatBackend``; typed as ``Any`` here to
        avoid a circular import at module level.
        """
        from clarity_agent.llm.factory import create_chat_backend
        return create_chat_backend(
            self,
            project_dir=project_dir,
            clarity_agent_dir=clarity_agent_dir,
        )
