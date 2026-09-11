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
from clarity_agent.llm.impl._openai_compat import uses_legacy_max_tokens
from clarity_agent.llm.model_catalog import build_catalog
from clarity_agent.llm.types import (
    LLMResponse,
    ModelCatalog,
    TextBlock,
    TokenUsage,
    ToolUseBlock,
)

_OPENAI_RECOMMENDED: dict[str, str] = {
    "default": "gpt-5.4",
    "deep": "gpt-5.4",
    "fast": "gpt-5.4-mini",
}

# Context-window size in tokens.  Co-located with the recommendations
# so this file declares everything about its known models in one
# place.  Unknown models fall back to ``ChatBackend.DEFAULT_CONTEXT_WINDOW``
# (or a user override in ``Settings.context_window_overrides``).
_OPENAI_MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    # GPT-5 family carries forward the 128K window from GPT-4o.
    "gpt-5.4": 128_000,
    "gpt-5.4-mini": 128_000,
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



# ---------------------------------------------------------------------------
# Model catalog
# ---------------------------------------------------------------------------

# ``GET /v1/models`` returns every model on the account — embeddings,
# speech, image, moderation — with nothing in the payload saying which
# ones do chat completions.  So we filter by name: a model must match a
# known chat prefix and contain none of the non-chat markers.  It's a
# heuristic, and it errs toward hiding an unfamiliar model rather than
# offering one that will 404 on the first turn; anything wrongly hidden
# is still reachable by typing its id.
_CHAT_MODEL_PREFIXES: tuple[str, ...] = ("gpt-", "chatgpt-", "o1", "o3", "o4")

_NON_CHAT_MARKERS: tuple[str, ...] = (
    "embedding", "tts", "whisper", "dall-e", "moderation", "audio",
    "realtime", "image", "transcribe", "search", "similarity", "edit",
    "instruct", "davinci", "babbage", "curie", "ada", "codex",
)


def _is_chat_model(model_id: str) -> bool:
    """True if *model_id* looks like a chat-completions model."""
    lowered = model_id.lower()
    if not lowered.startswith(_CHAT_MODEL_PREFIXES):
        return False
    return not any(marker in lowered for marker in _NON_CHAT_MARKERS)


class OpenAIClient(LLMClient):
    """Low-level async LLM client wrapping OpenAI's chat completions API.

    Translates OpenAI chat completion responses into provider-agnostic
    :class:`~clarity_agent.llm.types.LLMResponse` objects.
    """

    RECOMMENDED_MODELS = _OPENAI_RECOMMENDED
    MODEL_CONTEXT_WINDOWS = _OPENAI_MODEL_CONTEXT_WINDOWS

    def __init__(self, *, api_key: str) -> None:
        self._client = _openai_mod.AsyncOpenAI(api_key=api_key)

    async def fetch_models(self) -> ModelCatalog:
        """List chat-capable models on this key, via ``GET /v1/models``.

        OpenAI supplies no display names, so those are derived from the
        id, and the listing has no useful order, so results are sorted
        newest-first by ``created``.
        """
        listed = [m async for m in await self._client.models.list()]
        chat_models = [m for m in listed if _is_chat_model(m.id)]
        chat_models.sort(key=lambda m: m.created or 0, reverse=True)

        return build_catalog(
            recommended=self.RECOMMENDED_MODELS,
            context_windows=self.MODEL_CONTEXT_WINDOWS,
            model_ids=[m.id for m in chat_models],
            source="provider",
        )

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
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        # ``max_completion_tokens`` is the forward-compatible kwarg
        # (required by gpt-5 family + reasoning models, accepted by
        # everything since o1).  ``uses_legacy_max_tokens`` picks
        # out the dwindling set of pre-o1 chat models that still
        # need the legacy name.  See ``_openai_compat`` for the
        # rationale and the maintenance note on the prefix list.
        if uses_legacy_max_tokens(model):
            kwargs["max_tokens"] = max_tokens
        else:
            kwargs["max_completion_tokens"] = max_tokens
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


