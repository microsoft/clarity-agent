"""Google Gemini API backend implementation.

Provides :class:`GeminiClient`, a low-level async client wrapping
Google's Gemini API via the ``google-genai`` SDK.  High-level chat
is handled by :class:`~clarity_agent.llm.chat.ClientChatBackend`.
"""

from __future__ import annotations

from typing import Any

from google import genai as _genai_mod
from google.genai import types as _genai_types

from clarity_agent.llm.client import LLMClient
from clarity_agent.llm.types import (
    LLMResponse,
    TextBlock,
    TokenUsage,
    ToolUseBlock,
)

_GEMINI_TIER_DEFAULTS: dict[str, str] = {
    "default": "gemini-3.1-pro-preview",
    "deep": "gemini-3.1-pro-preview",
    "fast": "gemini-3.1-flash-lite-preview",
}

# Map Gemini finish reasons to canonical stop reasons.
_FINISH_REASON_MAP: dict[str, str] = {
    "STOP": "end_turn",
    "MAX_TOKENS": "max_tokens",
    "SAFETY": "end_turn",
    "RECITATION": "end_turn",
}


# ---------------------------------------------------------------------------
# Format translation
# ---------------------------------------------------------------------------

def _translate_tools(
    tools: list[dict[str, Any]],
) -> Any:
    """Translate canonical tool definitions to Gemini format.

    Canonical (Anthropic-style)::

        {"name": "search", "description": "...", "input_schema": {...}}

    Gemini::

        Tool(function_declarations=[{"name": "search", "description": "...", "parameters": {...}}])
    """
    declarations = []
    for tool in tools:
        params = tool.get("input_schema")
        declarations.append(_genai_types.FunctionDeclaration(
            name=tool["name"],
            description=tool.get("description", ""),
            parameters=params if params else None,
        ))
    return _genai_types.Tool(function_declarations=declarations)


def _translate_messages(
    messages: list[dict[str, Any]],
) -> list[Any]:
    """Translate canonical messages to Gemini Content objects.

    Handles text messages, assistant tool-use blocks, and user
    tool-result blocks.
    """
    result: list[Any] = []

    for msg in messages:
        role: str = msg["role"]
        content: Any = msg["content"]

        if role == "user":
            if isinstance(content, str):
                result.append(_genai_types.Content(
                    role="user",
                    parts=[_genai_types.Part(text=content)],
                ))
            elif isinstance(content, list):
                # Tool results from the tool-use loop.
                parts: list[Any] = []
                for block in content:
                    if block.get("type") == "tool_result":
                        parts.append(_genai_types.Part.from_function_response(
                            name=block.get("tool_name", ""),
                            response={"result": block.get("content", "")},
                        ))
                    elif block.get("type") == "text":
                        parts.append(_genai_types.Part(text=block.get("text", "")))
                if parts:
                    result.append(_genai_types.Content(role="user", parts=parts))

        elif role == "assistant":
            if isinstance(content, str):
                result.append(_genai_types.Content(
                    role="model",
                    parts=[_genai_types.Part(text=content)],
                ))
            elif isinstance(content, list):
                parts = []
                for block in content:
                    if block.get("type") == "text":
                        parts.append(_genai_types.Part(text=block.get("text", "")))
                    elif block.get("type") == "tool_use":
                        parts.append(_genai_types.Part(
                            function_call=_genai_types.FunctionCall(
                                name=block["name"],
                                args=block.get("input", {}),
                                id=block.get("id", ""),
                            ),
                        ))
                if parts:
                    result.append(_genai_types.Content(role="model", parts=parts))

    return result


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class GeminiClient(LLMClient):
    """Low-level async LLM client wrapping Google's Gemini API.

    Translates Gemini responses into provider-agnostic
    :class:`~clarity_agent.llm.types.LLMResponse` objects.
    """

    TIER_DEFAULTS = _GEMINI_TIER_DEFAULTS

    def __init__(self, *, api_key: str) -> None:
        self._client = _genai_mod.Client(api_key=api_key)

    async def _create_message(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        config: dict[str, Any] = {
            "max_output_tokens": max_tokens,
        }
        if system:
            config["system_instruction"] = system
        if tools:
            config["tools"] = [_translate_tools(tools)]

        contents = _translate_messages(messages)

        # Stream the response.
        text_parts: list[str] = []
        function_calls: list[dict[str, Any]] = []
        finish_reason: str | None = None
        usage = None

        stream = await self._client.aio.models.generate_content_stream(
            model=model,
            contents=contents,
            config=_genai_types.GenerateContentConfig(**config),
        )
        async for chunk in stream:
            # Extract text deltas.
            if chunk.text:
                text_parts.append(chunk.text)
                if self.on_text_delta:
                    self.on_text_delta(chunk.text)

            # Extract function calls from candidates.
            if chunk.candidates:
                for candidate in chunk.candidates:
                    if candidate.finish_reason:
                        finish_reason = candidate.finish_reason.name
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, "function_call") and part.function_call:
                                fc = part.function_call
                                function_calls.append({
                                    "id": getattr(fc, "id", "") or "",
                                    "name": fc.name,
                                    "args": dict(fc.args) if fc.args else {},
                                })

            # Extract usage metadata.
            if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                um = chunk.usage_metadata
                usage = TokenUsage(
                    input_tokens=getattr(um, "prompt_token_count", 0) or 0,
                    output_tokens=getattr(um, "candidates_token_count", 0) or 0,
                )

        # Build content blocks.
        content_blocks: list[TextBlock | ToolUseBlock] = []
        full_text = "".join(text_parts)
        if full_text:
            content_blocks.append(TextBlock(text=full_text))
        for fc in function_calls:
            content_blocks.append(ToolUseBlock(
                id=fc["id"],
                name=fc["name"],
                input=fc["args"],
            ))

        stop_reason: str = _FINISH_REASON_MAP.get(
            finish_reason or "STOP", "end_turn",
        )
        if function_calls and stop_reason == "end_turn":
            stop_reason = "tool_use"

        return LLMResponse(
            content=content_blocks,
            stop_reason=stop_reason,
            usage=usage,
        )
