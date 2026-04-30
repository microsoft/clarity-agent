"""OpenAI API backend implementation.

Provides :class:`OpenAIClient`, a low-level async client wrapping
OpenAI's chat completions API.  High-level chat is handled by
:class:`~clarity_agent.llm.chat.ClientChatBackend`.
"""

from __future__ import annotations

import json
from typing import Any

import openai as _openai_mod

from clarity_agent.llm.client import LLMClient
from clarity_agent.llm.types import (
    LLMResponse,
    TextBlock,
    TokenUsage,
    ToolUseBlock,
)

_OPENAI_TIER_DEFAULTS: dict[str, str] = {
    "default": "gpt-5.4",
    "deep": "gpt-5.4",
    "fast": "gpt-5.4-mini",
}

# Map OpenAI finish reasons to canonical stop reasons.
_FINISH_REASON_MAP: dict[str, str] = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "length": "max_tokens",
    "content_filter": "end_turn",
}



def _translate_tools(
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Translate canonical tool definitions to OpenAI format.

    Canonical (Anthropic-style)::

        {"name": "search", "description": "...", "input_schema": {...}}

    OpenAI::

        {"type": "function", "function": {"name": "search", "description": "...", "parameters": {...}}}
    """
    result: list[dict[str, Any]] = []
    for tool in tools:
        result.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            },
        })
    return result


def _translate_messages(
    messages: list[dict[str, Any]],
    system: str | None,
) -> list[dict[str, Any]]:
    """Translate canonical messages to OpenAI message dicts.

    OpenAI expects system messages in the messages array rather than as
    a separate parameter.
    """
    result: list[dict[str, Any]] = []

    if system is not None:
        result.append({"role": "system", "content": system})

    for msg in messages:
        role: str = msg["role"]
        content: Any = msg["content"]
        if role == "user":
            result.append({"role": "user", "content": content})
        elif role == "assistant":
            result.append({"role": "assistant", "content": content})
        elif role == "tool":
            result.append({
                "role": "tool",
                "content": content,
                "tool_call_id": msg.get("tool_use_id", ""),
            })

    return result


class OpenAIClient(LLMClient):
    """Low-level async LLM client wrapping OpenAI's chat completions API.

    Translates OpenAI chat completion responses into provider-agnostic
    :class:`~clarity_agent.llm.types.LLMResponse` objects.
    """

    TIER_DEFAULTS = _OPENAI_TIER_DEFAULTS

    def __init__(self, *, api_key: str) -> None:
        self._client = _openai_mod.AsyncOpenAI(api_key=api_key)

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
            "messages": _translate_messages(messages, system),
            "model": model,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = _translate_tools(tools)

        # Accumulate the streamed response.
        text_parts: list[str] = []
        tool_calls_by_index: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage = None

        stream = await self._client.chat.completions.create(**kwargs)
        async for chunk in stream:
            if not chunk.choices and hasattr(chunk, "usage") and chunk.usage:
                # Final chunk with usage stats (no choices).
                usage = TokenUsage(
                    input_tokens=chunk.usage.prompt_tokens,
                    output_tokens=chunk.usage.completion_tokens,
                )
                continue

            for choice in chunk.choices:
                delta = choice.delta
                if choice.finish_reason:
                    finish_reason = choice.finish_reason

                # Text delta.
                if delta.content:
                    text_parts.append(delta.content)
                    if self.on_text_delta:
                        self.on_text_delta(delta.content)

                # Tool call deltas — accumulate by index.
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_by_index:
                            tool_calls_by_index[idx] = {
                                "id": tc_delta.id or "",
                                "name": "",
                                "arguments": "",
                            }
                        entry = tool_calls_by_index[idx]
                        if tc_delta.id:
                            entry["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                entry["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                entry["arguments"] += tc_delta.function.arguments

        # Build content blocks.
        content: list[TextBlock | ToolUseBlock] = []
        full_text = "".join(text_parts)
        if full_text:
            content.append(TextBlock(text=full_text))
        for idx in sorted(tool_calls_by_index):
            tc = tool_calls_by_index[idx]
            content.append(ToolUseBlock(
                id=tc["id"],
                name=tc["name"],
                input=json.loads(tc["arguments"]) if tc["arguments"] else {},
            ))

        stop_reason: str = _FINISH_REASON_MAP.get(
            finish_reason or "stop", "end_turn",
        )

        return LLMResponse(content=content, stop_reason=stop_reason, usage=usage)


