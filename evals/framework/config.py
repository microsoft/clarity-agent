"""Load and apply eval framework configuration.

The config file (``evals/config.yaml``) specifies which LLM backend to
use for each role: the target (system under test), the simulated user,
and the judge.  Each role resolves credentials from environment
variables using the same mechanism as the main app.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from clarity_agent.llm.chat import ChatBackend
from clarity_agent.llm.config import LLMConfig


@dataclass
class RoleConfig:
    """LLM backend configuration for a single eval role."""

    provider: str
    model: str | None = None
    auth_mode: str | None = None


@dataclass
class EvalConfig:
    """Top-level configuration for the eval framework."""

    roles: dict[str, RoleConfig] = field(default_factory=dict)
    """Keyed by role name: ``target``, ``user``, ``judge``."""

    max_turns: int = 15
    """Default turn cap for conversations.  Per-test overrides via
    :func:`make_conversation_fixture`'s ``max_turns`` kwarg."""

    timeout_seconds: float | None = None
    """Default soft wall-clock budget for the user↔target conversation,
    in seconds.  ``None`` disables the timeout.  Per-test overrides via
    :func:`make_conversation_fixture`'s ``timeout_seconds`` kwarg."""

    @classmethod
    def load(cls, path: Path) -> EvalConfig:
        """Load config from a YAML file."""
        data = yaml.safe_load(path.read_text())
        roles = {
            name: RoleConfig(**spec)
            for name, spec in (data.get("roles") or {}).items()
        }
        defaults = data.get("defaults") or {}
        # ``timeout_seconds: null`` in YAML disables the timeout;
        # an absent key falls back to the dataclass default.
        timeout_raw: float | None = defaults.get("timeout_seconds", None)
        return cls(
            roles=roles,
            max_turns=defaults.get("max_turns", 15),
            timeout_seconds=timeout_raw,
        )

    def create_backend(
        self,
        role: str,
        *,
        project_dir: Path,
        clarity_agent_dir: Path,
    ) -> tuple[ChatBackend, LLMConfig]:
        """Instantiate a ChatBackend + LLMConfig for *role*.

        Credentials are resolved by ``LLMConfig.create()`` from the
        environment, keyring, or settings — same as the main app.

        Note: for the ``target`` role the ``model`` field is ignored —
        the target runs the normal Clarity tier routing (default/deep/fast)
        so the per-process model is chosen by the target provider's tier
        defaults, not by a single fixed model.
        """
        role_cfg = self.roles.get(role)
        if role_cfg is None:
            raise KeyError(
                f"Role {role!r} not configured. "
                f"Available roles: {list(self.roles.keys())}"
            )

        # The target uses tier-based routing; ignore any explicit model.
        model = None if role == "target" else role_cfg.model

        ns = argparse.Namespace(
            provider=role_cfg.provider,
            api_key=None,
            endpoint=None,
            model=model,
            model_deep=None,
            model_fast=None,
            auth_mode=role_cfg.auth_mode,
        )
        llm_config = LLMConfig.create(ns)
        backend = llm_config.create_chat_backend(
            project_dir=project_dir,
            clarity_agent_dir=clarity_agent_dir,
        )
        return backend, llm_config


def _default_config_path() -> Path:
    """Return the path to the default ``evals/config.yaml``."""
    # This file is evals/framework/config.py; config.yaml is at evals/config.yaml.
    return Path(__file__).resolve().parent.parent / "config.yaml"


def load_default() -> EvalConfig:
    """Load the project's default eval config."""
    return EvalConfig.load(_default_config_path())


def missing_credentials(config: EvalConfig) -> list[str]:
    """Return a list of role names whose credentials are missing.

    Used by pytest fixtures to skip eval tests cleanly when creds
    aren't present (e.g., in forked-PR CI where secrets aren't injected).

    Checks the same sources as the main app — env vars, keyring, and
    ``.env`` — via :class:`Settings`.
    """
    import os

    from clarity_agent.settings import Settings

    # Map providers to their credential sources.  Each entry is a list
    # of ways to satisfy the credential requirement; a role is only
    # flagged as missing if ALL sources come up empty.
    provider_sources: dict[str, list[str]] = {
        # Settings attribute names (which also read from env/keyring).
        "anthropic": ["anthropic_api_key"],
        "openai": ["openai_api_key"],
        "azure": ["azure_endpoint"],
        "gemini": ["gemini_api_key"],
        "github": ["github_token"],
    }
    # Fallback env vars that Settings doesn't track directly.
    extra_env: dict[str, list[str]] = {
        "gemini": ["GOOGLE_API_KEY"],
    }

    # Load settings once — it picks up env, keyring, and .env.
    settings = Settings.current()

    missing: list[str] = []
    for role_name, role_cfg in config.roles.items():
        if role_cfg.auth_mode in ("gh_cli", "claude_sdk", "default", "interactive"):
            continue
        attrs: list[str] = provider_sources.get(role_cfg.provider, [])
        env_fallbacks: list[str] = extra_env.get(role_cfg.provider, [])
        has_cred = any(getattr(settings, a, None) for a in attrs) or any(
            os.environ.get(v) for v in env_fallbacks
        )
        if attrs and not has_cred:
            missing.append(
                f"{role_name} (provider={role_cfg.provider})"
            )
    return missing


def describe_resolved_config(config: EvalConfig) -> str:
    """Return a human-readable summary of how each role will be wired up.

    Used by the ``--print-config`` pytest option to verify endpoint /
    deployment / auth before paying for a real run.  Reads
    :class:`Settings` for endpoint values but does **not** instantiate
    backends — there are no network calls or auth probes here, so this
    works even when credentials would later fail.
    """
    from clarity_agent.settings import Settings

    s = Settings.current()
    lines: list[str] = []

    for role_name in ("target", "user", "judge"):
        role_cfg = config.roles.get(role_name)
        if role_cfg is None:
            continue
        lines.append("")
        lines.append(f"  {role_name}:")
        lines.append(f"    provider:    {role_cfg.provider}")
        if role_cfg.auth_mode:
            lines.append(f"    auth_mode:   {role_cfg.auth_mode}")

        # Azure: surface the endpoint and the full URL Azure will be
        # hit at, since DeploymentNotFound is the most common failure.
        endpoint: str | None = None
        if role_cfg.provider == "azure":
            endpoint = s.azure_endpoint
            lines.append(
                f"    endpoint:    "
                f"{endpoint or '(unset — set AZURE_AI_ENDPOINT)'}"
            )

        if role_name == "target":
            # Target uses per-process tier routing; the model field is
            # ignored (provider tier defaults apply).
            lines.append("    model:       per-process tier routing")
        elif role_cfg.model:
            lines.append(f"    model:       {role_cfg.model}")
            if role_cfg.provider == "azure" and endpoint:
                base = endpoint.rstrip("/")
                lines.append(
                    f"    chat URL:    {base}/openai/deployments/"
                    f"{role_cfg.model}/chat/completions"
                    f"?api-version=2025-01-01-preview"
                )
        else:
            lines.append("    model:       (unset)")

    # Other configured roles (forward-compat with future role names).
    extra_roles = [r for r in config.roles if r not in ("target", "user", "judge")]
    for role_name in extra_roles:
        role_cfg = config.roles[role_name]
        lines.append("")
        lines.append(f"  {role_name}:")
        lines.append(f"    provider:    {role_cfg.provider}")
        if role_cfg.auth_mode:
            lines.append(f"    auth_mode:   {role_cfg.auth_mode}")
        if role_cfg.model:
            lines.append(f"    model:       {role_cfg.model}")

    lines.append("")
    lines.append("  defaults:")
    lines.append(f"    max_turns:        {config.max_turns}")
    timeout_text = (
        f"{config.timeout_seconds} (seconds)"
        if config.timeout_seconds is not None else "(disabled)"
    )
    lines.append(f"    timeout_seconds:  {timeout_text}")

    return "\n".join(lines)


__all__ = [
    "EvalConfig",
    "RoleConfig",
    "describe_resolved_config",
    "load_default",
    "missing_credentials",
]


# Type-only — keep imports for static checkers without forcing them at runtime.
_ = (Any,)
