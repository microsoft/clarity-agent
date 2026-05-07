"""Load and apply eval framework configuration.

The config file (``evals/config.yaml``) defines named **roles** —
each role is one provider+auth+model combination the framework
can dispatch a backend call to.  Three reserved role names map
to the framework's three role slots (target, user, judge):

  ``_target`` — default role for the system under test (a
            ClaritySession).  Runs the normal Clarity tier
            routing, so the model choice per process is governed
            by the target provider's tier defaults — the
            ``model`` field is NOT used for this role.
  ``_user``  — default role for the simulated user, a
            single-call LLM.  ``model`` picks the exact model.
  ``_judge`` — default role for the evaluator, a single-call
            LLM.  ``model`` picks the exact model; a strong model
            here makes verdicts reliable.

Additional non-underscore names can be defined alongside these
defaults as **alternative roles**.  Tests can override the default
for a given role slot by passing the alternative role's name to
:func:`make_conversation_fixture` (e.g., ``user='unsafe_user'`` to
use a less-safety-tuned model on a specific safety test).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from clarity_agent.llm.chat import ChatBackend
from clarity_agent.llm.config import LLMConfig

# Reserved role names — defaults for the framework's three role
# slots.  A config file MUST define each of these.  Additional
# roles (for per-test overrides) use any other name; the
# underscore prefix is reserved so user-defined roles can't
# collide.
_RESERVED_TARGET = "_target"
_RESERVED_USER = "_user"
_RESERVED_JUDGE = "_judge"
_RESERVED_ROLES = (_RESERVED_TARGET, _RESERVED_USER, _RESERVED_JUDGE)
_SLOT_TO_RESERVED: dict[str, str] = {
    "target": _RESERVED_TARGET,
    "user": _RESERVED_USER,
    "judge": _RESERVED_JUDGE,
}


@dataclass
class RoleConfig:
    """One LLM backend configuration — provider, model, auth.

    Roles are named (the dict key in :class:`EvalConfig.roles`).
    The framework's three role slots each have a reserved default
    role (``_target`` / ``_user`` / ``_judge``); additional roles
    can be defined for per-test overrides.
    """

    provider: str
    model: str | None = None
    auth_mode: str | None = None


@dataclass
class EvalConfig:
    """Top-level configuration for the eval framework."""

    roles: dict[str, RoleConfig] = field(default_factory=dict)
    """All configured roles, keyed by name.  Must include the three
    reserved defaults: ``_target``, ``_user``, ``_judge``.  May
    include any number of additional named roles for per-test
    overrides."""

    max_turns: int = 15
    """Default turn cap for conversations.  Per-test overrides via
    :func:`make_conversation_fixture`'s ``max_turns`` kwarg."""

    timeout_seconds: float | None = None
    """Default soft wall-clock budget for the user↔target conversation,
    in seconds.  ``None`` disables the timeout.  Per-test overrides via
    :func:`make_conversation_fixture`'s ``timeout_seconds`` kwarg."""

    @classmethod
    def load(cls, path: Path) -> EvalConfig:
        """Load config from a YAML file.

        The YAML must define a ``roles:`` block with all three
        reserved-default roles (``_target`` / ``_user`` /
        ``_judge``).  Missing reserveds raise ``ValueError`` at
        load time — fail-fast on misconfiguration rather than at
        first use.
        """
        data = yaml.safe_load(path.read_text())
        roles_data = data.get("roles")
        if not isinstance(roles_data, dict):
            raise ValueError(
                f"{path}: missing or invalid top-level 'roles:' block.  "
                "Expected a mapping of role-name → "
                "{provider, model, auth_mode}."
            )
        roles = {
            name: RoleConfig(**spec)
            for name, spec in roles_data.items()
        }
        missing = [name for name in _RESERVED_ROLES if name not in roles]
        if missing:
            raise ValueError(
                f"{path}: missing required reserved role(s): "
                f"{', '.join(missing)}.  All three of "
                f"{', '.join(_RESERVED_ROLES)} must be defined "
                "as the defaults for the target / user / judge slots."
            )
        defaults = data.get("defaults") or {}
        # ``timeout_seconds: null`` in YAML disables the timeout;
        # an absent key falls back to the dataclass default.
        timeout_raw: float | None = defaults.get("timeout_seconds", None)
        return cls(
            roles=roles,
            max_turns=defaults.get("max_turns", 15),
            timeout_seconds=timeout_raw,
        )

    def resolve_role(
        self, slot: str, override: str | None = None,
    ) -> str:
        """Return the role name to use for *slot*, honoring an override.

        ``slot`` is one of ``"target"``, ``"user"``, ``"judge"``.
        ``override``, if given, names a role defined in
        ``self.roles`` — used for per-test selection of an
        alternative role.  ``None`` falls back to the reserved
        default (``_target`` / ``_user`` / ``_judge``).

        Raises ``KeyError`` if the override names a role that
        isn't defined.
        """
        if override is not None:
            if override not in self.roles:
                raise KeyError(
                    f"Role {override!r} is not defined. "
                    f"Available: {sorted(self.roles.keys())}"
                )
            return override
        try:
            return _SLOT_TO_RESERVED[slot]
        except KeyError as exc:
            raise KeyError(
                f"Unknown slot {slot!r}.  Expected one of "
                f"{list(_SLOT_TO_RESERVED.keys())}."
            ) from exc

    def create_backend(
        self,
        *,
        slot: str,
        role: str | None = None,
        project_dir: Path,
        clarity_agent_dir: Path,
    ) -> tuple[ChatBackend, LLMConfig]:
        """Instantiate a ChatBackend + LLMConfig for *slot*.

        ``slot`` is one of ``"target"``, ``"user"``, ``"judge"``.
        Selects which role's configuration to dispatch against
        (default is the reserved ``_target``/``_user``/``_judge``)
        AND determines the backend's behavior — specifically, the
        target slot uses Clarity's tier-based per-process model
        routing, while the user and judge slots dispatch to the
        role's specific model.

        ``role``, if given, overrides which named role to use.
        That role must exist in :attr:`roles`; ``None`` falls back
        to the reserved default for the slot.  The slot + tier
        routing decision is independent of which role is selected
        — an alternative role used for the target slot still gets
        tier routing, an alternative role used for the user slot
        still gets exact-model dispatch.

        Credentials are resolved by ``LLMConfig.create()`` from the
        environment, keyring, or settings — same as the main app.
        """
        resolved_role = self.resolve_role(slot, role)
        role_cfg = self.roles[resolved_role]

        # The target slot uses tier-based routing — Clarity decides
        # which model to call per-tier (default/deep/fast) based on
        # the provider's tier defaults — so the role's ``model``
        # field is ignored regardless of which role is selected.
        # User and judge slots dispatch to the exact configured
        # model.
        is_target_slot = slot == "target"
        model = None if is_target_slot else role_cfg.model

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
    aren't present (e.g., in forked-PR CI where secrets aren't
    injected).

    Checks the same sources as the main app — env vars, keyring,
    and ``.env`` — via :class:`Settings`.  Each defined role is
    checked independently; a missing-cred error is reported
    against the role name (which makes it actionable for the
    operator).
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
    """Return a human-readable summary of the configured roles.

    Used by the ``--print-config`` pytest option to verify endpoint /
    deployment / auth before paying for a real run.  Reads
    :class:`Settings` for endpoint values but does **not** instantiate
    backends — there are no network calls or auth probes here, so this
    works even when credentials would later fail.

    The three reserved-default roles (``_target`` / ``_user`` /
    ``_judge``) are listed first with slot labels; alternative roles
    follow.
    """
    from clarity_agent.settings import Settings

    s = Settings.current()
    lines: list[str] = []

    def _role_block(name: str, slot_label: str | None = None) -> None:
        role_cfg = config.roles.get(name)
        if role_cfg is None:
            return
        lines.append("")
        if slot_label:
            lines.append(f"  {name}  (default for {slot_label} slot):")
        else:
            lines.append(f"  {name}:")
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

        if name == _RESERVED_TARGET:
            # Target-slot role uses per-process tier routing; the
            # model field is ignored (provider tier defaults apply).
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

    # Reserved defaults first, in slot order.
    _role_block(_RESERVED_TARGET, "target")
    _role_block(_RESERVED_USER, "user")
    _role_block(_RESERVED_JUDGE, "judge")

    # Alternative roles (non-underscore-prefixed names) follow.
    for name in config.roles:
        if name not in _RESERVED_ROLES:
            _role_block(name)

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
