"""Tests for the clarity_agent.llm package."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clarity_agent.llm import (
    ChatBackend,
    ClientChatBackend,
    LLMAuthExpiredError,
    LLMClient,
    LLMConfig,
    LLMResponse,
    TextBlock,
    ToolUseBlock,
    create_chat_backend,
    create_client,
)
from clarity_agent.llm.config import LLMConfigError, get_auth_mode_info

# ---------------------------------------------------------------------------
# Streaming mock helpers (used by OpenAI and Azure tests)
# ---------------------------------------------------------------------------

def _make_stream_chunk(
    content: str | None = None,
    finish_reason: str | None = None,
    tool_calls: list[Any] | None = None,
    usage: Any = None,
) -> MagicMock:
    """Build a mock streaming chunk (OpenAI/Azure format)."""
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = tool_calls

    choice = MagicMock()
    choice.delta = delta
    choice.finish_reason = finish_reason

    chunk = MagicMock()
    chunk.choices = [choice] if content is not None or finish_reason or tool_calls else []
    chunk.usage = usage
    return chunk


async def _async_iter(items: list[Any]) -> Any:
    """Turn a list into an async iterator for mocking stream responses."""
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# LLMResponse
# ---------------------------------------------------------------------------

class TestLLMResponse:
    """LLMResponse normalizes content and exposes helpers."""

    def test_text_joins_text_blocks(self) -> None:
        resp = LLMResponse(content=[
            TextBlock(text="Hello"),
            TextBlock(text="world"),
        ])
        assert resp.text == "Hello\nworld"

    def test_text_skips_tool_blocks(self) -> None:
        resp = LLMResponse(content=[
            TextBlock(text="Before"),
            ToolUseBlock(id="t1", name="tool", input={}),
            TextBlock(text="After"),
        ])
        assert resp.text == "Before\nAfter"

    def test_text_empty_when_no_text_blocks(self) -> None:
        resp = LLMResponse(content=[
            ToolUseBlock(id="t1", name="tool", input={}),
        ])
        assert resp.text == ""

    def test_tool_calls_extracts_tool_blocks(self) -> None:
        t1 = ToolUseBlock(id="t1", name="search", input={"q": "hello"})
        t2 = ToolUseBlock(id="t2", name="fetch", input={"url": "x"})
        resp = LLMResponse(content=[TextBlock(text="hi"), t1, t2])
        assert resp.tool_calls == [t1, t2]

    def test_tool_calls_empty_when_none(self) -> None:
        resp = LLMResponse(content=[TextBlock(text="hi")])
        assert resp.tool_calls == []

    def test_content_as_dicts_round_trips(self) -> None:
        resp = LLMResponse(content=[
            TextBlock(text="Hello"),
            ToolUseBlock(id="t1", name="tool", input={"key": "val"}),
        ])
        dicts = resp.content_as_dicts
        assert dicts == [
            {"type": "text", "text": "Hello"},
            {"type": "tool_use", "id": "t1", "name": "tool", "input": {"key": "val"}},
        ]

    def test_defaults(self) -> None:
        resp = LLMResponse()
        assert resp.content == []
        assert resp.stop_reason == "end_turn"


# ---------------------------------------------------------------------------
# Provider metadata
# ---------------------------------------------------------------------------

class TestProviderMetadata:
    """Provider metadata drives first-run setup and preferences UI copy."""

    def test_github_auth_modes_distinguish_copilot_cli_from_gh_fallback(
        self,
    ) -> None:
        sdk_mode = get_auth_mode_info("github", "sdk_native")
        gh_mode = get_auth_mode_info("github", "gh_cli")

        assert sdk_mode is not None
        assert gh_mode is not None
        assert sdk_mode["display_name"] == "GitHub Copilot CLI (copilot, recommended)"
        assert "No separate GitHub CLI install required" in sdk_mode["description"]
        assert "copilot auth login" in sdk_mode["setup_help"]
        assert gh_mode["display_name"] == "GitHub CLI (gh)"
        assert "not 'copilot auth login'" in gh_mode["setup_help"]


# ---------------------------------------------------------------------------
# create_client factory
# ---------------------------------------------------------------------------

class TestCreateClient:
    """create_client builds the right LLMClient for each provider."""

    def test_anthropic_provider(self) -> None:
        config = LLMConfig(provider="anthropic", api_key="fake-key")
        with patch("clarity_agent.llm.impl.anthropic._anthropic_mod") as mock_mod:
            mock_mod.AsyncAnthropic.return_value = MagicMock()
            client = create_client(config)
        assert isinstance(client, LLMClient)

    def test_azure_provider(self) -> None:
        config = LLMConfig(
            provider="azure", api_key="fake-key",
            endpoint="https://example.models.ai.azure.com",
        )
        with \
             patch("clarity_agent.llm.impl.azure_inference._azure_aio_mod") as mock_aio, \
             patch("clarity_agent.llm.impl.azure_inference._AzureKeyCredential"):
            mock_aio.ChatCompletionsClient.return_value = MagicMock()
            client = create_client(config)
        assert isinstance(client, LLMClient)

    def test_openai_provider(self) -> None:
        config = LLMConfig(provider="openai", api_key="fake-key")
        with \
             patch("clarity_agent.llm.impl.openai._openai_mod") as mock_mod:
            mock_mod.AsyncOpenAI.return_value = MagicMock()
            client = create_client(config)
        assert isinstance(client, LLMClient)

    def test_unknown_provider_raises(self) -> None:
        config = LLMConfig(provider="unknown-provider", api_key=None)
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_client(config)


# ---------------------------------------------------------------------------
# create_chat_backend factory
# ---------------------------------------------------------------------------

class TestCreateChatBackend:
    """create_chat_backend builds the right ChatBackend for each provider."""

    def test_anthropic_provider(self, tmp_path: Any) -> None:
        config = LLMConfig(provider="anthropic", api_key="fake-key")
        with patch("clarity_agent.llm.impl.anthropic._anthropic_mod") as mock_mod:
            mock_mod.AsyncAnthropic.return_value = MagicMock()
            backend = create_chat_backend(
                config,
                project_dir=tmp_path,
                clarity_agent_dir=tmp_path,
            )
        assert isinstance(backend, ClientChatBackend)
        assert hasattr(backend, "chat")

    def test_azure_provider(self, tmp_path: Any) -> None:
        config = LLMConfig(
            provider="azure", api_key="fake-key",
            endpoint="https://example.models.ai.azure.com",
        )
        with \
             patch("clarity_agent.llm.impl.azure_inference._azure_aio_mod") as mock_aio, \
             patch("clarity_agent.llm.impl.azure_inference._AzureKeyCredential"):
            mock_aio.ChatCompletionsClient.return_value = MagicMock()
            backend = create_chat_backend(
                config,
                project_dir=tmp_path,
                clarity_agent_dir=tmp_path,
            )
        assert isinstance(backend, ClientChatBackend)

    def test_openai_provider(self, tmp_path: Any) -> None:
        config = LLMConfig(provider="openai", api_key="fake-key")
        with \
             patch("clarity_agent.llm.impl.openai._openai_mod") as mock_mod:
            mock_mod.AsyncOpenAI.return_value = MagicMock()
            backend = create_chat_backend(
                config,
                project_dir=tmp_path,
                clarity_agent_dir=tmp_path,
            )
        assert isinstance(backend, ClientChatBackend)

    def test_unknown_provider_raises(self, tmp_path: Any) -> None:
        config = LLMConfig(provider="unknown", api_key=None)
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_chat_backend(
                config,
                project_dir=tmp_path,
                clarity_agent_dir=tmp_path,
            )


# ---------------------------------------------------------------------------
# AnthropicClient
# ---------------------------------------------------------------------------

class TestAnthropicClient:
    """AnthropicClient translates Anthropic SDK responses to LLMResponse."""

    def _make_anthropic_response(
        self,
        content: list[MagicMock],
        stop_reason: str = "end_turn",
    ) -> MagicMock:
        resp = MagicMock()
        resp.content = content
        resp.stop_reason = stop_reason
        resp.usage = None
        return resp

    def _make_text_block(self, text: str) -> MagicMock:
        block = MagicMock()
        block.type = "text"
        block.text = text
        return block

    def _make_tool_block(
        self, tool_id: str, name: str, input: dict[str, Any],
    ) -> MagicMock:
        block = MagicMock()
        block.type = "tool_use"
        block.id = tool_id
        block.name = name
        block.input = input
        return block

    def _make_stream(
        self,
        text_chunks: list[str],
        final_response: MagicMock,
        tool_blocks: list[MagicMock] | None = None,
    ) -> MagicMock:
        """Build a mock for ``messages.stream()`` (async context manager).

        Returns an object that supports ``async with ... as stream``,
        where iterating the stream itself yields a sequence of event
        objects: a ``TextEvent``-shaped object per entry in
        *text_chunks* (``type="text"``, ``text=chunk``) followed by a
        ``ContentBlockStopEvent``-shaped object per entry in
        *tool_blocks* (``type="content_block_stop"``,
        ``content_block=block``).  ``get_final_message()`` returns
        *final_response*.

        The production code in :meth:`AnthropicClient._create_message`
        iterates the stream's event sequence (not ``text_stream``) so
        it can surface tool-use blocks live.  Tests that only care
        about text or final-message shape can omit *tool_blocks*.
        """
        stream = MagicMock()

        events: list[MagicMock] = []
        for chunk in text_chunks:
            ev = MagicMock()
            ev.type = "text"
            ev.text = chunk
            events.append(ev)
        for block in tool_blocks or []:
            ev = MagicMock()
            ev.type = "content_block_stop"
            ev.content_block = block
            events.append(ev)

        async def _iter():
            for ev in events:
                yield ev

        stream.__aiter__ = lambda self: _iter()
        stream.get_final_message = AsyncMock(return_value=final_response)

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=stream)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    def test_translates_text_response(self) -> None:
        sdk_resp = self._make_anthropic_response([
            self._make_text_block("Hello world"),
        ])
        mock_stream = self._make_stream(["Hello", " world"], sdk_resp)

        with patch("clarity_agent.llm.impl.anthropic._anthropic_mod") as mock_mod:
            mock_client = AsyncMock()
            mock_client.messages.stream = MagicMock(return_value=mock_stream)
            mock_mod.AsyncAnthropic.return_value = mock_client

            from clarity_agent.llm.impl.anthropic import AnthropicClient
            client = AnthropicClient(api_key="fake")

            result = asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model="test-model",
            ))

        assert isinstance(result, LLMResponse)
        assert result.text == "Hello world"
        assert result.stop_reason == "end_turn"

    def test_translates_tool_use_response(self) -> None:
        sdk_resp = self._make_anthropic_response(
            [
                self._make_tool_block("t1", "search", {"q": "test"}),
                self._make_text_block("Done"),
            ],
            stop_reason="tool_use",
        )
        mock_stream = self._make_stream(["Done"], sdk_resp)

        with patch("clarity_agent.llm.impl.anthropic._anthropic_mod") as mock_mod:
            mock_client = AsyncMock()
            mock_client.messages.stream = MagicMock(return_value=mock_stream)
            mock_mod.AsyncAnthropic.return_value = mock_client

            from clarity_agent.llm.impl.anthropic import AnthropicClient
            client = AnthropicClient(api_key="fake")

            result = asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model="test-model",
                tools=[{"name": "search", "description": "...", "input_schema": {}}],
            ))

        assert result.stop_reason == "tool_use"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "search"
        assert result.tool_calls[0].input == {"q": "test"}
        assert result.text == "Done"

    def test_fires_text_delta_callback(self) -> None:
        sdk_resp = self._make_anthropic_response([
            self._make_text_block("Hello world"),
        ])
        mock_stream = self._make_stream(["Hello", " ", "world"], sdk_resp)

        deltas: list[str] = []

        with patch("clarity_agent.llm.impl.anthropic._anthropic_mod") as mock_mod:
            mock_client = AsyncMock()
            mock_client.messages.stream = MagicMock(return_value=mock_stream)
            mock_mod.AsyncAnthropic.return_value = mock_client

            from clarity_agent.llm.impl.anthropic import AnthropicClient
            client = AnthropicClient(api_key="fake")
            client.on_text_delta = deltas.append

            asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model="test-model",
            ))

        assert deltas == ["Hello", " ", "world"]

    def test_fires_tool_callbacks_inline_during_stream(self) -> None:
        """Tool-use blocks fire ``on_tool_use`` / ``on_tool_call`` as
        soon as each block finishes streaming — before
        ``stream.get_final_message()`` returns.  This is what gives
        the UI live tool-call updates on tool-heavy turns; without
        the inline path the events all batch at end-of-response.

        Also asserts the inline-fired flag is set so the base
        :class:`LLMClient.create_message` post-call loop skips its
        re-fire (the same callbacks would otherwise be invoked
        twice per tool block).
        """
        tool_block_1 = self._make_tool_block("t1", "search", {"q": "alpha"})
        tool_block_2 = self._make_tool_block("t2", "fetch", {"url": "/x"})
        sdk_resp = self._make_anthropic_response(
            [
                self._make_text_block("Looking..."),
                tool_block_1,
                tool_block_2,
            ],
            stop_reason="tool_use",
        )
        mock_stream = self._make_stream(
            ["Looking..."], sdk_resp, tool_blocks=[tool_block_1, tool_block_2],
        )

        tool_use_events: list[tuple[str, str]] = []
        tool_call_events: list[ToolUseBlock] = []

        with patch("clarity_agent.llm.impl.anthropic._anthropic_mod") as mock_mod:
            mock_client = AsyncMock()
            mock_client.messages.stream = MagicMock(return_value=mock_stream)
            mock_mod.AsyncAnthropic.return_value = mock_client

            from clarity_agent.llm.impl.anthropic import AnthropicClient
            client = AnthropicClient(api_key="fake")
            client.on_tool_use = lambda name, detail: tool_use_events.append(
                (name, detail),
            )
            client.on_tool_call = tool_call_events.append

            asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model="test-model",
                tools=[{"name": "search", "description": "", "input_schema": {}}],
            ))

        # One event per tool block — fired exactly once (not duplicated
        # by the post-call loop in ``LLMClient.create_message``).
        assert [name for name, _ in tool_use_events] == ["search", "fetch"]
        assert [tc.id for tc in tool_call_events] == ["t1", "t2"]
        assert [tc.input for tc in tool_call_events] == [
            {"q": "alpha"},
            {"url": "/x"},
        ]
        assert client._callbacks_fired_inline is True

    def test_passes_system_and_tools(self) -> None:
        sdk_resp = self._make_anthropic_response([
            self._make_text_block("ok"),
        ])
        mock_stream = self._make_stream(["ok"], sdk_resp)

        with patch("clarity_agent.llm.impl.anthropic._anthropic_mod") as mock_mod:
            mock_client = AsyncMock()
            mock_client.messages.stream = MagicMock(return_value=mock_stream)
            mock_mod.AsyncAnthropic.return_value = mock_client

            from clarity_agent.llm.impl.anthropic import AnthropicClient
            client = AnthropicClient(api_key="fake")

            tools = [{"name": "t", "description": "d", "input_schema": {}}]
            asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model="m",
                system="sys prompt",
                tools=tools,
            ))

            call_kwargs = mock_client.messages.stream.call_args[1]
            assert call_kwargs["system"] == "sys prompt"
            assert call_kwargs["tools"] == tools

    def test_omits_system_when_none(self) -> None:
        sdk_resp = self._make_anthropic_response([
            self._make_text_block("ok"),
        ])
        mock_stream = self._make_stream(["ok"], sdk_resp)

        with patch("clarity_agent.llm.impl.anthropic._anthropic_mod") as mock_mod:
            mock_client = AsyncMock()
            mock_client.messages.stream = MagicMock(return_value=mock_stream)
            mock_mod.AsyncAnthropic.return_value = mock_client

            from clarity_agent.llm.impl.anthropic import AnthropicClient
            client = AnthropicClient(api_key="fake")

            asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model="m",
            ))

            call_kwargs = mock_client.messages.stream.call_args[1]
            assert "system" not in call_kwargs
            assert "tools" not in call_kwargs


# ---------------------------------------------------------------------------
# LLMConfig — class methods (add_arguments / create)
# ---------------------------------------------------------------------------

class TestLLMConfigCLI:
    """LLMConfig.add_arguments registers CLI flags and .create resolves config."""

    def test_adds_provider_model_apikey_flags(self) -> None:
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args([])
        assert args.provider is None  # auto-detect
        # Model default is None at parse time; resolved to provider default in create().
        assert args.model is None
        assert args.api_key is None

    def test_custom_provider_default(self) -> None:
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser, default_provider="anthropic")
        args = parser.parse_args([])
        assert args.provider == "anthropic"

    def test_cli_overrides(self) -> None:
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args([
            "--provider", "anthropic",
            "--model", "custom-model",
            "--api-key", "my-key",
        ])
        assert args.provider == "anthropic"
        assert args.model == "custom-model"
        assert args.api_key == "my-key"

    def test_create_with_cli_api_key(self) -> None:
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args(["--provider", "anthropic", "--api-key", "cli-key"])

        with patch("clarity_agent.llm.config._check_package"):
            config = LLMConfig.create(args)

        assert isinstance(config, LLMConfig)
        assert config.provider == "anthropic"
        assert config.api_key == "cli-key"

    def test_create_reads_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args([])

        with patch("clarity_agent.llm.config._check_package"):
            config = LLMConfig.create(args)

        assert config.provider == "anthropic"
        assert config.api_key == "env-key"

    def test_create_exits_when_no_provider_detected(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With no API keys and no CLAUDECODE, auto-detect fails."""
        for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_AI_API_KEY",
                     "AZURE_AI_ENDPOINT", "CLAUDECODE", "GITHUB_TOKEN",
                     "GH_TOKEN", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                     "CLARITY_LLM_PROVIDER"):
            monkeypatch.delenv(var, raising=False)
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args([])

        with patch(
            "clarity_agent.llm.impl.github_copilot.get_gh_cli_token",
            return_value=None,
        ), patch(
            "clarity_agent.llm.impl.github_copilot.probe_sdk_native_auth",
            return_value=False,
        ), pytest.raises(LLMConfigError):
            LLMConfig.create(args)

    def test_create_explicit_api_key_mode_raises_when_key_missing(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Explicit --auth-mode api_key still requires API key."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args(["--provider", "anthropic", "--auth-mode", "api_key"])

        with patch("clarity_agent.llm.config._check_package"):
            with pytest.raises(LLMConfigError):
                LLMConfig.create(args)

    def test_create_anthropic_claude_sdk_no_key_required(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Anthropic with claude_sdk auth mode doesn't require an API key."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args([
            "--provider", "anthropic", "--auth-mode", "claude_sdk",
        ])

        with patch("clarity_agent.llm.config._check_package"):
            config = LLMConfig.create(args)

        assert config.provider == "anthropic"
        assert config.auth_mode == "claude_sdk"
        assert config.api_key is None

    def test_create_azure_with_endpoint(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AZURE_AI_API_KEY", "az-key")
        monkeypatch.setenv("AZURE_AI_ENDPOINT", "https://my.endpoint.com")
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args(["--provider", "azure"])

        with patch("clarity_agent.llm.config._check_package"):
            config = LLMConfig.create(args)

        assert config.provider == "azure"
        assert config.api_key == "az-key"
        assert config.endpoint == "https://my.endpoint.com"

    def test_create_azure_cli_endpoint_overrides_env(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AZURE_AI_API_KEY", "az-key")
        monkeypatch.setenv("AZURE_AI_ENDPOINT", "https://env.endpoint.com")
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args([
            "--provider", "azure",
            "--endpoint", "https://cli.endpoint.com",
        ])

        with patch("clarity_agent.llm.config._check_package"):
            config = LLMConfig.create(args)

        assert config.endpoint == "https://cli.endpoint.com"

    def test_create_azure_raises_when_endpoint_missing(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AZURE_AI_API_KEY", "az-key")
        monkeypatch.delenv("AZURE_AI_ENDPOINT", raising=False)
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args(["--provider", "azure"])

        with patch("clarity_agent.llm.config._check_package"):
            with pytest.raises(LLMConfigError):
                LLMConfig.create(args)

    def test_create_openai_with_env_key(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args(["--provider", "openai"])

        with patch("clarity_agent.llm.config._check_package"):
            config = LLMConfig.create(args)

        assert config.provider == "openai"
        assert config.api_key == "oai-key"
        assert config.endpoint is None

    def test_create_openai_raises_when_key_missing(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args(["--provider", "openai"])

        with patch("clarity_agent.llm.config._check_package"):
            with pytest.raises(LLMConfigError):
                LLMConfig.create(args)

    def test_create_azure_infers_api_key_auth_mode(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When an API key is present, auth_mode defaults to 'api_key'."""
        monkeypatch.setenv("AZURE_AI_API_KEY", "az-key")
        monkeypatch.setenv("AZURE_AI_ENDPOINT", "https://x.com")
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args(["--provider", "azure"])

        with patch("clarity_agent.llm.config._check_package"):
            config = LLMConfig.create(args)

        assert config.auth_mode == "api_key"

    def test_create_azure_defaults_to_preferred_auth_mode(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without an API key, Azure defaults to preferred auth mode (interactive)."""
        monkeypatch.delenv("AZURE_AI_API_KEY", raising=False)
        monkeypatch.setenv("AZURE_AI_ENDPOINT", "https://x.com")
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args(["--provider", "azure"])

        with patch("clarity_agent.llm.config._check_package"):
            config = LLMConfig.create(args)

        assert config.auth_mode == "interactive"
        assert config.api_key is None

    def test_create_azure_cli_auth_mode_override(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--auth-mode overrides the inferred mode."""
        monkeypatch.delenv("AZURE_AI_API_KEY", raising=False)
        monkeypatch.setenv("AZURE_AI_ENDPOINT", "https://x.com")
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args([
            "--provider", "azure", "--auth-mode", "interactive",
        ])

        with patch("clarity_agent.llm.config._check_package"):
            config = LLMConfig.create(args)

        assert config.auth_mode == "interactive"

    def test_create_rejects_unsupported_auth_mode(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An auth mode not in the provider's auth_modes is rejected."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args([
            "--provider", "anthropic", "--auth-mode", "interactive",
        ])

        with patch("clarity_agent.llm.config._check_package"):
            with pytest.raises(LLMConfigError, match="not supported"):
                LLMConfig.create(args)


# ---------------------------------------------------------------------------
# LLMConfig — auto-detection
# ---------------------------------------------------------------------------

class TestAutoDetectProvider:
    """_auto_detect_provider probes the environment for usable providers."""

    def _clear_all_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY",
                     "AZURE_AI_API_KEY", "AZURE_AI_ENDPOINT", "CLAUDECODE",
                     "GITHUB_TOKEN", "GH_TOKEN", "GEMINI_API_KEY",
                     "GOOGLE_API_KEY", "CLARITY_LLM_PROVIDER"):
            monkeypatch.delenv(var, raising=False)

    def test_detects_anthropic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from clarity_agent.llm.config import _auto_detect_provider
        self._clear_all_keys(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        with patch("clarity_agent.llm.config._has_package", return_value=True):
            assert _auto_detect_provider() == ("anthropic", "api_key")

    def test_detects_openai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from clarity_agent.llm.config import _auto_detect_provider
        self._clear_all_keys(monkeypatch)
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        with patch("clarity_agent.llm.config._has_package", return_value=True):
            assert _auto_detect_provider() == ("openai", "api_key")

    def test_detects_azure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from clarity_agent.llm.config import _auto_detect_provider
        self._clear_all_keys(monkeypatch)
        monkeypatch.setenv("AZURE_AI_API_KEY", "k")
        monkeypatch.setenv("AZURE_AI_ENDPOINT", "https://x.com")
        with patch("clarity_agent.llm.config._has_package", return_value=True):
            assert _auto_detect_provider() == ("azure", "api_key")

    def test_detects_claude_sdk(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from clarity_agent.llm.config import _auto_detect_provider
        self._clear_all_keys(monkeypatch)
        monkeypatch.setenv("CLAUDECODE", "1")
        with patch("clarity_agent.llm.config._has_package", return_value=True):
            assert _auto_detect_provider() == ("anthropic", "claude_sdk")

    def test_returns_none_when_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from clarity_agent.llm.config import _auto_detect_provider
        self._clear_all_keys(monkeypatch)
        # Mock away BOTH Copilot probes — gh CLI and the bundled
        # SDK login — so the test environment doesn't accidentally
        # detect a real local setup.
        with patch(
            "clarity_agent.llm.impl.github_copilot.get_gh_cli_token",
            return_value=None,
        ), patch(
            "clarity_agent.llm.impl.github_copilot.probe_sdk_native_auth",
            return_value=False,
        ):
            assert _auto_detect_provider() is None

    def test_detects_github_sdk_native(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SDK-native auth (Copilot login) is picked when the probe succeeds."""
        from clarity_agent.llm.config import _auto_detect_provider
        self._clear_all_keys(monkeypatch)
        with patch("clarity_agent.llm.config._has_package", return_value=True), \
             patch(
                "clarity_agent.llm.impl.github_copilot.probe_sdk_native_auth",
                return_value=True,
             ), patch(
                "clarity_agent.llm.impl.github_copilot.get_gh_cli_token",
                return_value="should-not-be-used",
             ):
            assert _auto_detect_provider() == ("github", "sdk_native")

    def test_detects_github_gh_cli_fallback(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """gh CLI fires when the SDK-native probe says we aren't logged in."""
        from clarity_agent.llm.config import _auto_detect_provider
        self._clear_all_keys(monkeypatch)
        with patch("clarity_agent.llm.config._has_package", return_value=True), \
             patch(
                "clarity_agent.llm.impl.github_copilot.probe_sdk_native_auth",
                return_value=False,
             ), patch(
                "clarity_agent.llm.impl.github_copilot.get_gh_cli_token",
                return_value="gh-token",
             ):
            assert _auto_detect_provider() == ("github", "gh_cli")

    def test_github_token_beats_sdk_native(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Explicit GITHUB_TOKEN wins over the SDK-native probe."""
        from clarity_agent.llm.config import _auto_detect_provider
        self._clear_all_keys(monkeypatch)
        monkeypatch.setenv("GITHUB_TOKEN", "explicit")
        with patch("clarity_agent.llm.config._has_package", return_value=True), \
             patch(
                "clarity_agent.llm.impl.github_copilot.probe_sdk_native_auth",
                return_value=True,
             ):
            assert _auto_detect_provider() == ("github", "token")

    def test_anthropic_takes_priority_over_claudecode(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from clarity_agent.llm.config import _auto_detect_provider
        self._clear_all_keys(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        monkeypatch.setenv("CLAUDECODE", "1")
        with patch("clarity_agent.llm.config._has_package", return_value=True):
            assert _auto_detect_provider() == ("anthropic", "api_key")

    def test_create_auto_detects_claude_sdk(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """LLMConfig.create() with no --provider auto-detects claude_sdk."""
        self._clear_all_keys(monkeypatch)
        monkeypatch.setenv("CLAUDECODE", "1")
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args([])

        with patch("clarity_agent.llm.config._check_package"):
            config = LLMConfig.create(args)

        assert config.provider == "anthropic"
        assert config.auth_mode == "claude_sdk"
        assert config.api_key is None

    def test_create_auto_detects_anthropic(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """LLMConfig.create() with no --provider auto-detects anthropic."""
        self._clear_all_keys(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "auto-key")
        parser = argparse.ArgumentParser()
        LLMConfig.add_arguments(parser)
        args = parser.parse_args([])

        with patch("clarity_agent.llm.config._check_package"):
            config = LLMConfig.create(args)

        assert config.provider == "anthropic"
        assert config.auth_mode == "api_key"
        assert config.api_key == "auto-key"


# ---------------------------------------------------------------------------
# LLMConfig — instance methods (create_client / create_chat_backend)
# ---------------------------------------------------------------------------

class TestLLMConfigInstances:
    """LLMConfig creates clients and backends from resolved settings."""

    def test_create_client(self) -> None:
        config = LLMConfig(provider="anthropic", api_key="fake")
        with patch("clarity_agent.llm.impl.anthropic._anthropic_mod") as mock_mod:
            mock_mod.AsyncAnthropic.return_value = MagicMock()
            client = config.create_client()
        assert isinstance(client, LLMClient)

    def test_create_chat_backend(self, tmp_path: Any) -> None:
        config = LLMConfig(provider="anthropic", api_key="fake")
        with patch("clarity_agent.llm.impl.anthropic._anthropic_mod") as mock_mod:
            mock_mod.AsyncAnthropic.return_value = MagicMock()
            backend = config.create_chat_backend(
                project_dir=tmp_path,
                clarity_agent_dir=tmp_path,
            )
        assert isinstance(backend, ChatBackend)


# ---------------------------------------------------------------------------
# AzureInferenceClient
# ---------------------------------------------------------------------------

class TestAzureInferenceClient:
    """AzureInferenceClient translates streamed Azure responses to LLMResponse."""

    def _make_stream(self, chunks: list[MagicMock]) -> Any:
        """Return an async iterator of chunks for mocking ``complete(stream=True)``."""
        return _async_iter(chunks)

    def _make_tool_call_delta(
        self, tc_id: str, name: str, arguments: str, index: int = 0,
    ) -> MagicMock:
        tc = MagicMock()
        tc.index = index
        tc.id = tc_id
        tc.function.name = name
        tc.function.arguments = arguments
        return tc

    def test_translates_text_response(self) -> None:
        chunks = [
            _make_stream_chunk(content="Hello"),
            _make_stream_chunk(content=" world"),
            _make_stream_chunk(finish_reason="stop"),
        ]

        with \
             patch("clarity_agent.llm.impl.azure_inference._azure_aio_mod") as mock_aio, \
             patch("clarity_agent.llm.impl.azure_inference._AzureKeyCredential"), \
             patch("clarity_agent.llm.impl.azure_inference._azure_models"):
            mock_client = AsyncMock()
            mock_client.complete = AsyncMock(return_value=self._make_stream(chunks))
            mock_aio.ChatCompletionsClient.return_value = mock_client

            from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
            client = AzureInferenceClient(
                api_key="fake", endpoint="https://example.com",
            )

            result = asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model="test-model",
            ))

        assert isinstance(result, LLMResponse)
        assert result.text == "Hello world"
        assert result.stop_reason == "end_turn"

    def test_translates_tool_use_response(self) -> None:
        tc_delta = self._make_tool_call_delta("t1", "search", json.dumps({"q": "test"}))
        chunks = [
            _make_stream_chunk(content="Let me search."),
            _make_stream_chunk(tool_calls=[tc_delta]),
            _make_stream_chunk(finish_reason="tool_calls"),
        ]

        with \
             patch("clarity_agent.llm.impl.azure_inference._azure_aio_mod") as mock_aio, \
             patch("clarity_agent.llm.impl.azure_inference._AzureKeyCredential"), \
             patch("clarity_agent.llm.impl.azure_inference._azure_models"):
            mock_client = AsyncMock()
            mock_client.complete = AsyncMock(return_value=self._make_stream(chunks))
            mock_aio.ChatCompletionsClient.return_value = mock_client

            from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
            client = AzureInferenceClient(
                api_key="fake", endpoint="https://example.com",
            )

            result = asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model="test-model",
                tools=[{"name": "search", "description": "...", "input_schema": {}}],
            ))

        assert result.stop_reason == "tool_use"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "search"
        assert result.tool_calls[0].input == {"q": "test"}
        assert result.text == "Let me search."

    def test_maps_length_finish_reason(self) -> None:
        chunks = [
            _make_stream_chunk(content="truncated"),
            _make_stream_chunk(finish_reason="length"),
        ]

        with \
             patch("clarity_agent.llm.impl.azure_inference._azure_aio_mod") as mock_aio, \
             patch("clarity_agent.llm.impl.azure_inference._AzureKeyCredential"), \
             patch("clarity_agent.llm.impl.azure_inference._azure_models"):
            mock_client = AsyncMock()
            mock_client.complete = AsyncMock(return_value=self._make_stream(chunks))
            mock_aio.ChatCompletionsClient.return_value = mock_client

            from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
            client = AzureInferenceClient(
                api_key="fake", endpoint="https://example.com",
            )

            result = asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model="m",
            ))

        assert result.stop_reason == "max_tokens"

    def test_fires_text_delta_callback(self) -> None:
        chunks = [
            _make_stream_chunk(content="Hello"),
            _make_stream_chunk(content=" world"),
            _make_stream_chunk(finish_reason="stop"),
        ]
        deltas: list[str] = []

        with \
             patch("clarity_agent.llm.impl.azure_inference._azure_aio_mod") as mock_aio, \
             patch("clarity_agent.llm.impl.azure_inference._AzureKeyCredential"), \
             patch("clarity_agent.llm.impl.azure_inference._azure_models"):
            mock_client = AsyncMock()
            mock_client.complete = AsyncMock(return_value=self._make_stream(chunks))
            mock_aio.ChatCompletionsClient.return_value = mock_client

            from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
            client = AzureInferenceClient(
                api_key="fake", endpoint="https://example.com",
            )
            client.on_text_delta = deltas.append

            asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model="m",
            ))

        assert deltas == ["Hello", " world"]

    def _capture_azure_complete_kwargs(
        self, model: str, max_tokens: int,
    ) -> dict[str, Any]:
        # Same shape as the OpenAI helper above: drive a one-shot
        # create_message against a mock Azure client and return the
        # kwargs that landed on the inference SDK's ``complete()``.
        chunks = [_make_stream_chunk(content="hi"), _make_stream_chunk(finish_reason="stop")]
        with \
             patch("clarity_agent.llm.impl.azure_inference._azure_aio_mod") as mock_aio, \
             patch("clarity_agent.llm.impl.azure_inference._AzureKeyCredential"), \
             patch("clarity_agent.llm.impl.azure_inference._azure_models"):
            mock_client = AsyncMock()
            mock_client.complete = AsyncMock(return_value=self._make_stream(chunks))
            mock_aio.ChatCompletionsClient.return_value = mock_client

            from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
            client = AzureInferenceClient(
                api_key="fake", endpoint="https://example.com",
            )
            asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model=model,
                max_tokens=max_tokens,
            ))
        return mock_client.complete.await_args.kwargs

    def test_default_routes_through_model_extras(self) -> None:
        # Azure mirrors the OpenAI inversion (see test_default_picks_
        # max_completion_tokens above), but routes via ``model_extras``
        # because the inference SDK doesn't surface
        # ``max_completion_tokens`` as a first-class kwarg.  Unknown /
        # future model names must take this branch by default.
        for model in ("gpt-5.4", "o3-mini", "ft:gpt-7-future"):
            kw = self._capture_azure_complete_kwargs(model, 1234)
            assert kw.get("model_extras") == {"max_completion_tokens": 1234}, model
            assert "max_tokens" not in kw, model

    def test_legacy_models_use_max_tokens(self) -> None:
        # Pre-o1 deployments take the legacy first-class kwarg
        # rather than the ``model_extras`` route.
        for model in ("gpt-4", "gpt-4o", "gpt-3.5-turbo-1106"):
            kw = self._capture_azure_complete_kwargs(model, 2048)
            assert kw.get("max_tokens") == 2048, model
            assert "model_extras" not in kw, model


# ---------------------------------------------------------------------------
# AzureInferenceClient — auth modes
# ---------------------------------------------------------------------------

class TestAzureAuthModes:
    """AzureInferenceClient supports multiple authentication modes."""

    def test_api_key_mode(self) -> None:
        with \
             patch("clarity_agent.llm.impl.azure_inference._AzureKeyCredential") as mock_cred, \
             patch("clarity_agent.llm.impl.azure_inference._azure_aio_mod"):
            from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
            client = AzureInferenceClient(
                endpoint="https://x.com", api_key="k", auth_mode="api_key",
            )
        mock_cred.assert_called_once_with("k")
        assert not client._uses_token_credential

    def test_api_key_mode_requires_key(self) -> None:
        from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
        with pytest.raises(ValueError, match="requires an api_key"):
            AzureInferenceClient(
                endpoint="https://x.com", auth_mode="api_key",
            )

    def test_default_mode_with_key(self) -> None:
        """Default mode uses AzureKeyCredential when a key is provided."""
        with \
             patch("clarity_agent.llm.impl.azure_inference._AzureKeyCredential") as mock_cred, \
             patch("clarity_agent.llm.impl.azure_inference._azure_aio_mod"):
            from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
            client = AzureInferenceClient(
                endpoint="https://x.com", api_key="k", auth_mode="default",
            )
        mock_cred.assert_called_once_with("k")
        assert not client._uses_token_credential

    def test_default_mode_without_key(self) -> None:
        """Default mode uses DefaultAzureCredential when no key is provided."""
        with patch("clarity_agent.llm.impl.azure_inference._DefaultAzureCredential") as mock_cred, \
             patch("clarity_agent.llm.impl.azure_inference._azure_aio_mod"):
            from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
            client = AzureInferenceClient(
                endpoint="https://x.com", auth_mode="default",
            )
        mock_cred.assert_called_once()
        assert client._uses_token_credential

    def test_interactive_mode(self) -> None:
        with patch("clarity_agent.llm.impl.azure_inference._azure_aio_mod"), \
             patch("azure.identity.InteractiveBrowserCredential") as mock_cred, \
             patch("azure.identity.TokenCachePersistenceOptions"):
            from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
            client = AzureInferenceClient(
                endpoint="https://x.com", auth_mode="interactive",
                tenant_id="my-tenant",
            )
        mock_cred.assert_called_once()
        call_kwargs = mock_cred.call_args[1]
        assert call_kwargs["tenant_id"] == "my-tenant"
        assert "cache_persistence_options" in call_kwargs
        assert client._uses_token_credential

    def test_device_code_mode(self) -> None:
        with patch("clarity_agent.llm.impl.azure_inference._azure_aio_mod"), \
             patch("azure.identity.DeviceCodeCredential") as mock_cred:
            from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
            client = AzureInferenceClient(
                endpoint="https://x.com", auth_mode="device_code",
                tenant_id="t",
            )
        mock_cred.assert_called_once_with(tenant_id="t")
        assert client._uses_token_credential

    def test_auth_expired_error_on_token_failure(self) -> None:
        """Token credential auth failures raise LLMAuthExpiredError."""
        with patch("clarity_agent.llm.impl.azure_inference._DefaultAzureCredential"), \
             patch("clarity_agent.llm.impl.azure_inference._azure_aio_mod") as mock_aio, \
             patch("clarity_agent.llm.impl.azure_inference._azure_models"):
            mock_client = AsyncMock()
            mock_client.complete = AsyncMock(
                side_effect=Exception("ClientAuthenticationError: authentication failed"),
            )
            mock_aio.ChatCompletionsClient.return_value = mock_client

            from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
            client = AzureInferenceClient(
                endpoint="https://x.com", auth_mode="default",
            )

            with pytest.raises(LLMAuthExpiredError, match="expired"):
                asyncio.run(client.create_message(
                    messages=[{"role": "user", "content": "hi"}],
                    model="test",
                ))

    def test_non_auth_errors_propagate_unchanged(self) -> None:
        """Non-authentication errors are not wrapped."""
        with patch("clarity_agent.llm.impl.azure_inference._DefaultAzureCredential"), \
             patch("clarity_agent.llm.impl.azure_inference._azure_aio_mod") as mock_aio, \
             patch("clarity_agent.llm.impl.azure_inference._azure_models"):
            mock_client = AsyncMock()
            mock_client.complete = AsyncMock(
                side_effect=RuntimeError("network timeout"),
            )
            mock_aio.ChatCompletionsClient.return_value = mock_client

            from clarity_agent.llm.impl.azure_inference import AzureInferenceClient
            client = AzureInferenceClient(
                endpoint="https://x.com", auth_mode="default",
            )

            with pytest.raises(RuntimeError, match="network timeout"):
                asyncio.run(client.create_message(
                    messages=[{"role": "user", "content": "hi"}],
                    model="test",
                ))


# ---------------------------------------------------------------------------
# OpenAIClient
# ---------------------------------------------------------------------------

class TestOpenAIClient:
    """OpenAIClient translates streamed OpenAI responses to LLMResponse."""

    def _make_stream(self, chunks: list[MagicMock]) -> Any:
        return _async_iter(chunks)

    def _make_tool_call_delta(
        self, tc_id: str, name: str, arguments: str, index: int = 0,
    ) -> MagicMock:
        tc = MagicMock()
        tc.index = index
        tc.id = tc_id
        tc.function.name = name
        tc.function.arguments = arguments
        return tc

    def test_translates_text_response(self) -> None:
        chunks = [
            _make_stream_chunk(content="Hello"),
            _make_stream_chunk(content=" world"),
            _make_stream_chunk(finish_reason="stop"),
        ]

        with \
             patch("clarity_agent.llm.impl.openai._openai_mod") as mock_mod:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=self._make_stream(chunks))
            mock_mod.AsyncOpenAI.return_value = mock_client

            from clarity_agent.llm.impl.openai import OpenAIClient
            client = OpenAIClient(api_key="fake")

            result = asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model="test-model",
            ))

        assert isinstance(result, LLMResponse)
        assert result.text == "Hello world"
        assert result.stop_reason == "end_turn"

    def test_translates_tool_use_response(self) -> None:
        tc_delta = self._make_tool_call_delta("t1", "search", json.dumps({"q": "test"}))
        chunks = [
            _make_stream_chunk(content="Let me search."),
            _make_stream_chunk(tool_calls=[tc_delta]),
            _make_stream_chunk(finish_reason="tool_calls"),
        ]

        with \
             patch("clarity_agent.llm.impl.openai._openai_mod") as mock_mod:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=self._make_stream(chunks))
            mock_mod.AsyncOpenAI.return_value = mock_client

            from clarity_agent.llm.impl.openai import OpenAIClient
            client = OpenAIClient(api_key="fake")

            result = asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model="test-model",
                tools=[{"name": "search", "description": "...", "input_schema": {}}],
            ))

        assert result.stop_reason == "tool_use"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "search"
        assert result.tool_calls[0].input == {"q": "test"}
        assert result.text == "Let me search."

    def test_maps_length_finish_reason(self) -> None:
        chunks = [
            _make_stream_chunk(content="truncated"),
            _make_stream_chunk(finish_reason="length"),
        ]

        with \
             patch("clarity_agent.llm.impl.openai._openai_mod") as mock_mod:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=self._make_stream(chunks))
            mock_mod.AsyncOpenAI.return_value = mock_client

            from clarity_agent.llm.impl.openai import OpenAIClient
            client = OpenAIClient(api_key="fake")

            result = asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model="m",
            ))

        assert result.stop_reason == "max_tokens"

    def test_fires_text_delta_callback(self) -> None:
        chunks = [
            _make_stream_chunk(content="Hello"),
            _make_stream_chunk(content=" "),
            _make_stream_chunk(content="world"),
            _make_stream_chunk(finish_reason="stop"),
        ]
        deltas: list[str] = []

        with \
             patch("clarity_agent.llm.impl.openai._openai_mod") as mock_mod:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=self._make_stream(chunks))
            mock_mod.AsyncOpenAI.return_value = mock_client

            from clarity_agent.llm.impl.openai import OpenAIClient
            client = OpenAIClient(api_key="fake")
            client.on_text_delta = deltas.append

            asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model="m",
            ))

        assert deltas == ["Hello", " ", "world"]

    def _capture_create_kwargs(self, model: str, max_tokens: int) -> dict[str, Any]:
        # Run a one-shot create_message against a mock and return
        # the kwargs the OpenAI SDK was called with — the assertion
        # surface for the legacy / modern token-kwarg routing tests.
        chunks = [_make_stream_chunk(content="hi"), _make_stream_chunk(finish_reason="stop")]
        with patch("clarity_agent.llm.impl.openai._openai_mod") as mock_mod:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=self._make_stream(chunks),
            )
            mock_mod.AsyncOpenAI.return_value = mock_client

            from clarity_agent.llm.impl.openai import OpenAIClient
            client = OpenAIClient(api_key="fake")
            asyncio.run(client.create_message(
                messages=[{"role": "user", "content": "hi"}],
                model=model,
                max_tokens=max_tokens,
            ))
        return mock_client.chat.completions.create.await_args.kwargs

    def test_default_picks_max_completion_tokens(self) -> None:
        # Regression for issue #59 and forward-default guarantee:
        # any model not in the legacy prefix list (the dwindling
        # set of pre-o1 chat models) gets ``max_completion_tokens``.
        # This covers the named gpt-5 family models, reasoning
        # models (o3/o4), AND unknown future / fine-tuned model
        # names — the inversion's whole point is that new model
        # IDs work without a code change.
        for model in ("gpt-5.4", "o3-mini", "o4-mini", "ft:gpt-7-future"):
            kw = self._capture_create_kwargs(model, 1234)
            assert kw.get("max_completion_tokens") == 1234, model
            assert "max_tokens" not in kw, model

    def test_legacy_models_use_max_tokens(self) -> None:
        # The flip side: pre-o1 chat models still take the legacy
        # kwarg.  These date-stamped names exercise the prefix
        # match — bare ``gpt-4``, ``gpt-4o-2024-08-06``, and
        # ``gpt-3.5-turbo-1106`` must all be recognised as legacy
        # rather than getting the new kwarg.
        for model in ("gpt-4", "gpt-4o", "gpt-4o-2024-08-06", "gpt-3.5-turbo-1106"):
            kw = self._capture_create_kwargs(model, 2048)
            assert kw.get("max_tokens") == 2048, model
            assert "max_completion_tokens" not in kw, model


# ---------------------------------------------------------------------------
# ClientChatBackend
# ---------------------------------------------------------------------------

class TestClientChatBackend:
    """ClientChatBackend wraps any LLMClient for chat and tool loops."""

    def _make_mock_client(self, *responses: LLMResponse) -> AsyncMock:
        """Create a mock LLMClient returning the given responses in order."""
        client = AsyncMock()
        client.TIER_DEFAULTS = {"default": "test-model", "deep": "deep-model"}
        if len(responses) == 1:
            client.create_message = AsyncMock(return_value=responses[0])
        else:
            client.create_message = AsyncMock(side_effect=list(responses))
        client.on_tool_use = None
        return client

    def _make_backend(self, mock_client: AsyncMock, tmp_path: Any) -> ClientChatBackend:
        """Create a ClientChatBackend with connect() already called."""
        backend = ClientChatBackend(
            mock_client, project_dir=tmp_path, clarity_agent_dir=tmp_path,
        )
        backend.connect()
        return backend

    def test_chat_appends_to_history(self, tmp_path: Any) -> None:
        mock_client = self._make_mock_client(
            LLMResponse(content=[TextBlock(text="Hello!")])
        )
        backend = self._make_backend(mock_client, tmp_path)

        result = backend.chat("Hi")

        assert result == "Hello!"
        assert len(backend.conversation_history) == 2
        assert backend.conversation_history[0]["role"] == "user"
        assert backend.conversation_history[1]["role"] == "assistant"

    def test_chat_includes_system_prompt(self, tmp_path: Any) -> None:
        mock_client = self._make_mock_client(
            LLMResponse(content=[TextBlock(text="ok")])
        )
        backend = self._make_backend(mock_client, tmp_path)

        backend.chat("Hi", system_prompt="Be helpful")

        call_kwargs = mock_client.create_message.call_args[1]
        assert "Be helpful" in call_kwargs["system"]

    def test_tier_defaults_delegate_to_client(self, tmp_path: Any) -> None:
        mock_client = self._make_mock_client(
            LLMResponse(content=[TextBlock(text="ok")])
        )
        backend = self._make_backend(mock_client, tmp_path)

        assert backend.TIER_DEFAULTS == {"default": "test-model", "deep": "deep-model"}
        assert backend.resolve_model("deep") == "deep-model"

    def test_tier_overrides_win_over_client_defaults(self, tmp_path: Any) -> None:
        # User-configured tiers (from LLMConfig.tiers — i.e. --model /
        # settings / evals config) must override the provider's built-in
        # TIER_DEFAULTS. Otherwise resolve_model(None) silently ignores
        # a configured model and the backend calls the wrong deployment.
        mock_client = self._make_mock_client(
            LLMResponse(content=[TextBlock(text="ok")])
        )
        backend = ClientChatBackend(
            mock_client,
            project_dir=tmp_path,
            clarity_agent_dir=tmp_path,
            tiers={"default": "user-chosen-model"},
        )

        assert backend.resolve_model(None) == "user-chosen-model"
        assert backend.resolve_model("default") == "user-chosen-model"
        # Non-overridden tiers still fall through to the client defaults.
        assert backend.resolve_model("deep") == "deep-model"

    def test_factory_passes_config_tiers_to_backend(self, tmp_path: Any) -> None:
        # End-to-end guard: create_chat_backend must propagate
        # LLMConfig.tiers into the backend so an explicit --model /
        # config model actually reaches the API call.  Regression guard
        # for a bug where the factory dropped tiers on the floor and the
        # simulated-user backend silently used the provider default.
        import argparse

        from clarity_agent.llm.config import LLMConfig
        from clarity_agent.llm.factory import create_chat_backend

        ns = argparse.Namespace(
            provider="openai", api_key="sk-test", endpoint=None,
            model="explicit-model", model_deep=None, model_fast=None,
            auth_mode="api_key",
        )
        config = LLMConfig.create(ns)
        backend = create_chat_backend(
            config, project_dir=tmp_path, clarity_agent_dir=tmp_path,
        )
        assert backend.resolve_model(None) == "explicit-model"

    def test_on_tool_use_propagates_to_client(self, tmp_path: Any) -> None:
        mock_client = self._make_mock_client(
            LLMResponse(content=[TextBlock(text="ok")])
        )
        backend = self._make_backend(mock_client, tmp_path)

        callback = MagicMock()
        backend.on_tool_use = callback
        assert mock_client.on_tool_use is callback

    def test_disconnect_clears_history(self, tmp_path: Any) -> None:
        mock_client = self._make_mock_client(
            LLMResponse(content=[TextBlock(text="ok")])
        )
        backend = self._make_backend(mock_client, tmp_path)

        backend.chat("Hi")
        assert len(backend.conversation_history) == 2
        backend.disconnect()
        assert len(backend.conversation_history) == 0

    def test_arun_tool_loop_single_round(self, tmp_path: Any) -> None:
        """Tool loop with one tool call then end_turn."""
        resp1 = LLMResponse(
            content=[
                ToolUseBlock(id="t1", name="search", input={"q": "test"}),
            ],
            stop_reason="tool_use",
        )
        resp2 = LLMResponse(
            content=[TextBlock(text="Done.")],
            stop_reason="end_turn",
        )
        mock_client = self._make_mock_client(resp1, resp2)
        backend = self._make_backend(mock_client, tmp_path)

        handler_calls: list[str] = []

        def handler(tc: ToolUseBlock) -> str:
            handler_calls.append(tc.name)
            return "result"

        result = asyncio.run(backend.arun_tool_loop(
            user_message="search for test",
            tools=[{"name": "search", "description": "...", "input_schema": {}}],
            tool_handler=handler,
        ))

        assert result.text == "Done."
        assert handler_calls == ["search"]
        # Tool loop should NOT affect conversation_history.
        assert len(backend.conversation_history) == 0

    def test_arun_tool_loop_processes_final_response_tools(self, tmp_path: Any) -> None:
        """Tool calls in the final response (end_turn) are also processed."""
        resp = LLMResponse(
            content=[
                ToolUseBlock(id="t1", name="record", input={"title": "A"}),
                TextBlock(text="Done."),
            ],
            stop_reason="end_turn",
        )
        mock_client = self._make_mock_client(resp)
        backend = self._make_backend(mock_client, tmp_path)

        handler_calls: list[str] = []

        def handler(tc: ToolUseBlock) -> str:
            handler_calls.append(tc.input["title"])
            return "ok"

        result = asyncio.run(backend.arun_tool_loop(
            user_message="analyze",
            tool_handler=handler,
        ))

        assert result.text == "Done."
        assert handler_calls == ["A"]

    def test_arun_tool_loop_raises_without_client(self) -> None:
        """Base ChatBackend raises NotImplementedError."""

        class DummyBackend(ChatBackend):
            def chat(self, msg: str, system_prompt: str | None = None, *, model: str | None = None) -> str:
                return ""

        backend = DummyBackend()
        with pytest.raises(NotImplementedError):
            asyncio.run(backend.arun_tool_loop(user_message="test"))

    def test_run_tool_loop_sync_wrapper(self, tmp_path: Any) -> None:
        """run_tool_loop is a sync wrapper around arun_tool_loop."""
        resp = LLMResponse(
            content=[TextBlock(text="Done.")],
            stop_reason="end_turn",
        )
        mock_client = self._make_mock_client(resp)
        backend = self._make_backend(mock_client, tmp_path)

        result = backend.run_tool_loop(user_message="test")

        assert result.text == "Done."


class TestClientChatBackendCompaction:
    """ClientChatBackend owns its own threshold-based compaction.

    These tests exercise :meth:`ClientChatBackend.maybe_compact_after_chat`
    directly — the place where the decision logic and transcript
    mechanics live after the issue #35 refactor.  The adapter-level
    bridge (``WebSessionAdapter._on_compaction_*``) is covered
    separately in test_web_session_resume.py::TestCompactionBridge.
    """

    def _make_backend(self, tmp_path: Any, *, transcript=None) -> ClientChatBackend:
        """Build a ClientChatBackend wired to a transcript.  The mock
        client's ``create_message`` returns ``"summary text"`` so
        the summarizer call produces a deterministic result.
        """
        from clarity_agent.llm.types import TokenUsage
        client = AsyncMock()
        client.TIER_DEFAULTS = {"default": "test-model"}
        client.MODEL_CONTEXT_WINDOWS = {"test-model": 128_000}
        client.create_message = AsyncMock(
            return_value=LLMResponse(
                content=[TextBlock(text="summary text")],
                usage=TokenUsage(input_tokens=0, output_tokens=0),
            ),
        )
        client.on_tool_use = None
        client.on_usage = None
        backend = ClientChatBackend(
            client,
            project_dir=tmp_path,
            clarity_agent_dir=tmp_path,
            transcript=transcript,
        )
        backend.connect()
        return backend

    def test_no_fire_when_under_threshold(self, tmp_path: Any) -> None:
        # Small transcript, small input_tokens → no compaction.
        # The wrapped client should never be asked to summarize.
        from datetime import datetime

        from clarity_agent.transcript import Transcript, UserTurn

        transcript = Transcript(tmp_path)
        transcript.write(UserTurn(
            timestamp=datetime.now(UTC),
            content="tiny",
        ))
        backend = self._make_backend(tmp_path, transcript=transcript)
        backend._latest_input_tokens = 1_000

        backend.maybe_compact_after_chat()

        # Still on chapter 1 — no rollover.
        assert Transcript(tmp_path).current_chapter == 1
        # And the client wasn't called to produce a summary.
        backend._client.create_message.assert_not_called()

    def test_fires_when_input_tokens_over_threshold(self, tmp_path: Any) -> None:
        # input_tokens > 85% of 128K window (the test-model context).
        # Compaction writes a CompactionSummary into a new chapter,
        # produced by our stubbed create_message → "summary text".
        from datetime import datetime

        from clarity_agent.transcript import (
            CompactionSummary,
            Transcript,
            UserTurn,
        )

        transcript = Transcript(tmp_path)
        # Seed the chapter with enough turns that the 70/30 split
        # has something to summarize.
        for i in range(10):
            transcript.write(UserTurn(
                timestamp=datetime.now(UTC),
                content=f"turn {i}",
            ))
        backend = self._make_backend(tmp_path, transcript=transcript)
        backend._latest_input_tokens = 120_000  # > 85% of 128K

        backend.maybe_compact_after_chat()

        t = Transcript(tmp_path)
        assert t.current_chapter == 2
        new_events = list(t.chapter_events(2))
        assert isinstance(new_events[0], CompactionSummary)
        assert new_events[0].summary == "summary text"
        assert new_events[0].source_chapter == 1
        # Counter resets after rollover so a second pass through this
        # method sees a clean slate.
        assert backend._latest_input_tokens == 0

    def test_fires_when_transcript_size_over_threshold(
        self, tmp_path: Any,
    ) -> None:
        # Rebuild-safety trigger: transcript content exceeds the
        # threshold even though live input_tokens stays small.  At
        # 85% of 128K → 108,800 tokens → ~435,200 chars by the
        # estimator (4 chars per token).
        from datetime import datetime

        from clarity_agent.transcript import (
            CompactionSummary,
            Transcript,
            UserTurn,
        )

        transcript = Transcript(tmp_path)
        transcript.write(UserTurn(
            timestamp=datetime.now(UTC),
            content="x" * 450_000,
        ))
        backend = self._make_backend(tmp_path, transcript=transcript)
        backend._latest_input_tokens = 5_000  # provider kept it small

        backend.maybe_compact_after_chat()

        t = Transcript(tmp_path)
        assert t.current_chapter == 2
        new_events = list(t.chapter_events(2))
        assert isinstance(new_events[0], CompactionSummary)

    def test_fires_callbacks_around_compaction(self, tmp_path: Any) -> None:
        # on_compaction_started fires before the slow work,
        # on_compaction_complete fires after with the summary +
        # source turn count.  The adapter relies on this ordering
        # to drive its status / banner UI.
        from datetime import datetime

        from clarity_agent.llm.types import CompactionInfo
        from clarity_agent.transcript import Transcript, UserTurn

        transcript = Transcript(tmp_path)
        for i in range(5):
            transcript.write(UserTurn(
                timestamp=datetime.now(UTC),
                content=f"turn {i}",
            ))
        backend = self._make_backend(tmp_path, transcript=transcript)
        backend._latest_input_tokens = 120_000

        events: list[str] = []
        completion_info: list[CompactionInfo] = []
        backend.on_compaction_started = lambda: events.append("started")
        backend.on_compaction_complete = lambda info: (
            events.append("complete"), completion_info.append(info),
        )

        backend.maybe_compact_after_chat()

        assert events == ["started", "complete"]
        assert completion_info[0].summary == "summary text"
        assert completion_info[0].source_turn_count >= 1

    def test_noop_when_no_transcript_bound(self, tmp_path: Any) -> None:
        # No transcript → backend silently skips compaction.  The
        # eval harness uses ClientChatBackend without a transcript
        # and shouldn't crash even when input_tokens crosses the
        # nominal threshold.
        backend = self._make_backend(tmp_path, transcript=None)
        backend._latest_input_tokens = 120_000
        # Doesn't raise; doesn't do anything.
        backend.maybe_compact_after_chat()


# ---------------------------------------------------------------------------
# SdkChatBackend — text-based tool-call helpers
# ---------------------------------------------------------------------------

class TestSdkToolCallParsing:
    """Tests for SdkChatBackend's text-based tool-call encoding/parsing."""

    def _get_cls(self) -> type:
        from clarity_agent.llm.impl.claude_sdk import SdkChatBackend
        return SdkChatBackend

    def test_format_tools_for_prompt_basic(self) -> None:
        cls = self._get_cls()
        tools = [
            {
                "name": "record_failure",
                "description": "Record a failure mode.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Failure title"},
                        "severity": {"type": "integer", "description": "1-5 severity"},
                    },
                    "required": ["title"],
                },
            },
        ]
        result = cls._format_tools_for_prompt(tools)
        assert "record_failure" in result
        assert "Record a failure mode." in result
        assert "title (string (required))" in result
        assert "severity (integer)" in result
        assert "(required)" not in result.split("severity")[1].split("\n")[0]

    def test_format_tools_for_prompt_empty(self) -> None:
        cls = self._get_cls()
        assert cls._format_tools_for_prompt([]) == ""

    def test_parse_text_tool_calls_basic(self) -> None:
        cls = self._get_cls()
        text = (
            "Here are some failures:\n\n"
            "```tool_call\n"
            '{"name": "record_failure", "input": {"title": "SQL Injection"}}\n'
            "```\n\n"
            "And another:\n\n"
            "```tool_call\n"
            '{"name": "record_failure", "input": {"title": "XSS Attack"}}\n'
            "```\n"
        )
        calls = cls._parse_text_tool_calls(text)
        assert len(calls) == 2
        assert calls[0]["name"] == "record_failure"
        assert calls[0]["input"]["title"] == "SQL Injection"
        assert calls[1]["input"]["title"] == "XSS Attack"

    def test_parse_text_tool_calls_no_matches(self) -> None:
        cls = self._get_cls()
        assert cls._parse_text_tool_calls("No tool calls here.") == []

    def test_parse_text_tool_calls_ignores_bad_json(self) -> None:
        cls = self._get_cls()
        text = (
            "```tool_call\n"
            "not valid json\n"
            "```\n"
            "```tool_call\n"
            '{"name": "good", "input": {"x": 1}}\n'
            "```\n"
        )
        calls = cls._parse_text_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "good"

    def test_parse_text_tool_calls_ignores_missing_fields(self) -> None:
        cls = self._get_cls()
        text = (
            "```tool_call\n"
            '{"just": "data"}\n'
            "```\n"
            "```tool_call\n"
            '{"name": "valid", "input": {}}\n'
            "```\n"
        )
        calls = cls._parse_text_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "valid"

    def test_strip_tool_calls(self) -> None:
        cls = self._get_cls()
        text = (
            "Some text before.\n\n"
            "```tool_call\n"
            '{"name": "x", "input": {}}\n'
            "```\n\n"
            "Some text after."
        )
        stripped = cls._strip_tool_calls(text)
        assert "tool_call" not in stripped
        assert "Some text before." in stripped
        assert "Some text after." in stripped

    def test_has_api_key_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cls = self._get_cls()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        backend = MagicMock(spec=cls)
        assert cls._has_api_key(backend) is True

    def test_has_api_key_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cls = self._get_cls()
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        backend = MagicMock(spec=cls)
        assert cls._has_api_key(backend) is False


class TestSdkToolLoopRouting:
    """arun_tool_loop dispatches to API or SDK path based on API key."""

    def test_routes_to_api_when_key_present(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        from clarity_agent.llm.impl.claude_sdk import SdkChatBackend
        backend = SdkChatBackend(
            project_dir=tmp_path,
            clarity_agent_dir=tmp_path,
        )

        with patch.object(backend, "_arun_tool_loop_api") as mock_api:
            mock_api.return_value = LLMResponse(
                content=[TextBlock(text="done")],
            )
            result = asyncio.run(backend.arun_tool_loop(user_message="test"))

            mock_api.assert_called_once()
            assert result.text == "done"

    def test_routes_to_sdk_when_no_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        from clarity_agent.llm.impl.claude_sdk import SdkChatBackend
        backend = SdkChatBackend(
            project_dir=tmp_path,
            clarity_agent_dir=tmp_path,
        )

        with patch.object(backend, "_arun_tool_loop_sdk") as mock_sdk:
            mock_sdk.return_value = LLMResponse(
                content=[TextBlock(text="done via sdk")],
            )
            result = asyncio.run(backend.arun_tool_loop(user_message="test"))

            mock_sdk.assert_called_once()
            assert result.text == "done via sdk"
