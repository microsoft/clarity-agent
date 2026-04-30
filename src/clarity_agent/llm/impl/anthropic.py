"""Anthropic LLM backend implementation.

Provides :class:`AnthropicClient`, a low-level async client wrapping
:class:`anthropic.AsyncAnthropic`.  High-level chat is handled by
:class:`~clarity_agent.llm.chat.ClientChatBackend`.

NB: This is the interface you use if you're accessing the Anthropic API
directly, using an API key. If you're using the Claude SDK, you use the
higher-level claude_sdk.SdkChatBackend instead.
"""

from __future__ import annotations

from typing import Any

import anthropic as _anthropic_mod

from clarity_agent.llm.client import LLMClient
from clarity_agent.llm.types import (
    LLMResponse,
    TextBlock,
    TokenUsage,
    ToolUseBlock,
)

_ANTHROPIC_TIER_DEFAULTS: dict[str, str] = {
    "default": "claude-sonnet-4-6",
    "deep": "claude-opus-4-7",
    "fast": "claude-haiku-4-5",
}


class AnthropicClient(LLMClient):
    """Low-level async LLM client wrapping :class:`anthropic.AsyncAnthropic`.

    Translates Anthropic API responses into provider-agnostic
    :class:`~clarity_agent.llm.types.LLMResponse` objects.
    """

    TIER_DEFAULTS = _ANTHROPIC_TIER_DEFAULTS

    def __init__(self, *, api_key: str) -> None:
        self._client = _anthropic_mod.AsyncAnthropic(api_key=api_key)

    async def _create_message(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system is not None:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        # Use streaming to get text deltas in real time.
        async with self._client.messages.stream(**kwargs) as stream:
            # Fire text deltas as they arrive.
            async for text in stream.text_stream:
                if self.on_text_delta:
                    self.on_text_delta(text)

            # Get the final accumulated message.
            response = await stream.get_final_message()

        # Translate Anthropic content blocks to our types.
        content: list[TextBlock | ToolUseBlock] = []
        for block in response.content:
            if block.type == "text":
                content.append(TextBlock(text=block.text))
            elif block.type == "tool_use":
                content.append(ToolUseBlock(
                    id=block.id,
                    name=block.name,
                    input=block.input,
                ))

        usage = None
        if hasattr(response, "usage") and response.usage:
            usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        return LLMResponse(
            content=content,
            stop_reason=response.stop_reason or "end_turn",
            usage=usage,
        )


