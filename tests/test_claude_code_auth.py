"""Tests for borrowing Claude Code's OAuth token to enumerate models.

Every failure mode must come back as ``None`` rather than raising or
reporting a reason: the caller can't act on a reason, and any message
risks leaking part of the credential.

The placeholder values here are deliberately not shaped like real
Anthropic credentials.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterable, Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from clarity_agent.llm import LLMConfig
from clarity_agent.llm.claude_code_auth import find_oauth_token
from clarity_agent.llm.factory import _listing_client, fetch_model_catalog
from clarity_agent.llm.model_catalog import clear_cache

FAKE_TOKEN = "test-oauth-token-value"


@pytest.fixture(autouse=True)
def _clear_catalog_cache() -> Iterator[None]:
    clear_cache()
    yield
    clear_cache()


@pytest.fixture(autouse=True)
def _no_ambient_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a developer's real environment out of these tests."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)


class _AsyncIter:
    def __init__(self, items: Iterable[Any]) -> None:
        self._items = list(items)

    def __aiter__(self) -> Any:
        async def gen() -> Any:
            for item in self._items:
                yield item
        return gen()


def _config(**kwargs: Any) -> LLMConfig:
    kwargs.setdefault("provider", "anthropic")
    kwargs.setdefault("auth_mode", "claude_sdk")
    kwargs.setdefault("api_key", None)
    return LLMConfig(**kwargs)


def _blob(**overrides: Any) -> str:
    """A credential blob shaped the way Claude Code stores one."""
    oauth = {
        "accessToken": FAKE_TOKEN,
        "refreshToken": "test-refresh-token-value",
        "expiresAt": int((time.time() + 3600) * 1000),
        "scopes": ["user:inference", "user:profile"],
        **overrides,
    }
    return json.dumps({"claudeAiOauth": oauth})


def _find(*, keychain: str | None = None, file: str | None = None) -> str | None:
    from clarity_agent.llm import claude_code_auth as auth

    with (
        patch.object(auth, "_read_from_keychain", return_value=keychain),
        patch.object(auth, "_read_from_file", return_value=file),
    ):
        return find_oauth_token()


# ---------------------------------------------------------------------------
# Locating the token
# ---------------------------------------------------------------------------

class TestFindOAuthToken:
    def test_reads_a_valid_token_from_the_keychain(self) -> None:
        assert _find(keychain=_blob()) == FAKE_TOKEN

    def test_falls_back_to_the_credentials_file(self) -> None:
        """Linux and Windows keep the same blob on disk instead."""
        assert _find(file=_blob()) == FAKE_TOKEN

    def test_env_var_wins_and_needs_no_keychain(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The sanctioned headless path shouldn't touch the keychain.

        Reading the keychain from a process other than Claude Code can
        prompt the user, so an explicitly supplied token must
        short-circuit before we get there.
        """
        from clarity_agent.llm import claude_code_auth as auth

        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "token-from-environment")
        with patch.object(auth, "_read_from_keychain") as reader:
            assert auth.find_oauth_token() == "token-from-environment"
        reader.assert_not_called()

    def test_blank_env_var_is_ignored(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "   ")
        assert _find(keychain=_blob()) == FAKE_TOKEN

    def test_no_credential_anywhere(self) -> None:
        assert _find() is None


class TestTokenExpiry:
    def test_expired_token_is_refused(self) -> None:
        """Refreshing is Claude Code's job — racing it could invalidate
        the user's live session."""
        stale = int((time.time() - 3600) * 1000)
        assert _find(keychain=_blob(expiresAt=stale)) is None

    def test_token_expiring_within_the_margin_is_refused(self) -> None:
        """Don't start a request with a credential that dies mid-flight."""
        soon = int((time.time() + 5) * 1000)
        assert _find(keychain=_blob(expiresAt=soon)) is None

    def test_missing_expiry_is_treated_as_expired(self) -> None:
        payload = json.dumps({"claudeAiOauth": {"accessToken": FAKE_TOKEN}})
        assert _find(keychain=payload) is None

    @pytest.mark.parametrize("value", ["soon", None, True, [1]])
    def test_unparseable_expiry_is_treated_as_expired(self, value: Any) -> None:
        assert _find(keychain=_blob(expiresAt=value)) is None


class TestUnrecognizedLayouts:
    """The store is undocumented and may change shape without notice."""

    @pytest.mark.parametrize("blob", [
        "not json at all",
        "",
        "[]",
        "null",
        "{}",
        '{"claudeAiOauth": "not a dict"}',
        '{"claudeAiOauth": {}}',
        '{"claudeAiOauth": {"accessToken": ""}}',
        '{"claudeAiOauth": {"accessToken": "   "}}',
        '{"claudeAiOauth": {"accessToken": 12345}}',
        '{"someOtherKey": {"accessToken": "x"}}',
    ])
    def test_yield_none_rather_than_raising(self, blob: str) -> None:
        assert _find(keychain=blob) is None

    def test_malformed_keychain_still_lets_the_file_win(self) -> None:
        assert _find(keychain="{garbage", file=_blob()) == FAKE_TOKEN


class TestStorageErrors:
    def test_keychain_errors_are_swallowed(self) -> None:
        """A locked, denied, or absent keychain is a miss, not a crash."""
        from clarity_agent.llm import claude_code_auth as auth

        with patch("keyring.get_password", side_effect=OSError("access denied")):
            assert auth._read_from_keychain() is None

    def test_unreadable_credentials_file_is_swallowed(self) -> None:
        from clarity_agent.llm import claude_code_auth as auth

        with (
            patch.object(type(auth._CREDENTIALS_FILE), "exists", return_value=True),
            patch.object(
                type(auth._CREDENTIALS_FILE), "read_text",
                side_effect=PermissionError("nope"),
            ),
        ):
            assert auth._read_from_file() is None


# ---------------------------------------------------------------------------
# Using it to list models
# ---------------------------------------------------------------------------

class TestClaudeSdkOAuthListing:
    def test_oauth_token_is_used_when_there_is_no_api_key(self) -> None:
        """The gap this closes: claude_sdk with no API key anywhere."""
        from clarity_agent.llm.impl import anthropic as impl

        client = MagicMock()
        client.models.list.return_value = _AsyncIter([
            SimpleNamespace(id="claude-opus-5", display_name="Claude Opus 5"),
        ])
        with (
            patch("clarity_agent.llm.claude_code_auth.find_oauth_token",
                  return_value=FAKE_TOKEN),
            patch.object(
                impl._anthropic_mod, "AsyncAnthropic", return_value=client,
            ) as ctor,
        ):
            catalog = asyncio.run(fetch_model_catalog(_config()))

        assert catalog.source == "provider"

        # Bearer auth plus the OAuth beta header — never x-api-key.
        kwargs = ctor.call_args.kwargs
        assert kwargs["auth_token"] == FAKE_TOKEN
        assert kwargs["default_headers"]["anthropic-beta"] == "oauth-2025-04-20"
        assert "api_key" not in kwargs

    def test_api_key_is_preferred_over_the_oauth_token(self) -> None:
        """A real key is the supported path; only reach past it if absent."""
        from clarity_agent.llm.impl import anthropic as impl

        with (
            patch("clarity_agent.llm.claude_code_auth.find_oauth_token") as finder,
            patch.object(impl._anthropic_mod, "AsyncAnthropic"),
        ):
            _listing_client(_config(api_key="test-api-key"))
        finder.assert_not_called()

    def test_no_token_means_no_listing_client(self) -> None:
        with patch("clarity_agent.llm.claude_code_auth.find_oauth_token",
                   return_value=None):
            assert _listing_client(_config()) is None

    def test_falls_back_to_builtin_when_the_token_is_rejected(self) -> None:
        """An OAuth token the API won't take must degrade, not break."""
        from clarity_agent.llm.impl import anthropic as impl

        client = MagicMock()
        client.models.list.side_effect = RuntimeError("401 unauthorized")
        with (
            patch("clarity_agent.llm.claude_code_auth.find_oauth_token",
                  return_value=FAKE_TOKEN),
            patch.object(impl._anthropic_mod, "AsyncAnthropic", return_value=client),
        ):
            catalog = asyncio.run(fetch_model_catalog(_config()))

        assert catalog.source == "builtin"
        assert catalog.models, "fallback must stay usable"
        assert "RuntimeError" in (catalog.error or "")


class TestAnthropicClientAuthArgs:
    def test_requires_exactly_one_credential(self) -> None:
        from clarity_agent.llm.impl.anthropic import AnthropicClient

        with pytest.raises(ValueError, match="exactly one"):
            AnthropicClient()
        with pytest.raises(ValueError, match="exactly one"):
            AnthropicClient(api_key="k", auth_token="t")

    def test_api_key_path_sends_no_oauth_header(self) -> None:
        from clarity_agent.llm.impl import anthropic as impl

        with patch.object(impl._anthropic_mod, "AsyncAnthropic") as ctor:
            impl.AnthropicClient(api_key="test-api-key")
        assert ctor.call_args.kwargs == {"api_key": "test-api-key"}
