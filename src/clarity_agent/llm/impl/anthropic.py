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

from clarity_agent.llm.client import LLMClient, extract_tool_detail, truncate
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

# Context-window size (in tokens) per model.  Co-located with the
# tier defaults so a single backend file declares everything about
# its known models.  The compaction trigger compares the last turn's
# ``input_tokens`` (from the provider's response) against this;
# users on a model not listed here can add an override via
# ``Settings.context_window_overrides``.
#
# Note: some providers (e.g. the Claude Agent SDK) apply their own
# context management server-side.  Because we measure the real
# ``input_tokens`` the provider reports, those providers' internal
# compaction naturally keeps our trigger cold — we only fire as the
# safety net when the provider isn't handling things itself.
_ANTHROPIC_MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "claude-opus-4-7": 200_000,
    "claude-sonnet-4-6": 200_000,
    "claude-haiku-4-5": 200_000,
}


class AnthropicClient(LLMClient):
    """Low-level async LLM client wrapping :class:`anthropic.AsyncAnthropic`.

    Translates Anthropic API responses into provider-agnostic
    :class:`~clarity_agent.llm.types.LLMResponse` objects.
    """

    TIER_DEFAULTS = _ANTHROPIC_TIER_DEFAULTS
    MODEL_CONTEXT_WINDOWS = _ANTHROPIC_MODEL_CONTEXT_WINDOWS

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

        # Iterate the full stream event sequence (not just
        # ``text_stream``) so we can surface tool-use blocks as
        # they complete — without this, tool calls inside an
        # assistant response don't reach the UI until the whole
        # response is finalized below, which produces the
        # "everything dumped at end-of-turn" experience users
        # see on tool-heavy turns.  Text deltas still flow via
        # ``TextEvent``; tool blocks fire on ``ContentBlockStopEvent``
        # the moment the provider finishes streaming each block.
        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "text":
                    if self.on_text_delta:
                        self.on_text_delta(event.text)
                elif event.type == "content_block_stop":
                    block = event.content_block
                    if block.type == "tool_use":
                        self._emit_tool_block(block)
            # Mark inline-fired before unwrapping the final message
            # so :meth:`LLMClient.create_message`'s post-call loop
            # doesn't re-fire the same callbacks.  Set unconditionally
            # — even a response with zero tool blocks went through
            # the inline path and should opt out of the duplicate-
            # firing safety loop.
            self._callbacks_fired_inline = True
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

    def _emit_tool_block(self, block: Any) -> None:
        """Surface a completed tool-use block via the configured callbacks.

        Called from inside the streaming loop in :meth:`_create_message`
        the moment the provider finishes emitting a ``tool_use`` block,
        rather than waiting for ``stream.get_final_message()``.  Without
        this mid-stream surfacing, tool-heavy turns appear silent to the
        UI: text-only sections stream live but the tool calls that
        usually follow batch up at end-of-turn.

        Fires the same ``[Tool]`` stdout echo, ``on_tool_use`` (flattened
        display string), and ``on_tool_call`` (structured block) that the
        base :meth:`LLMClient.create_message` would fire post-stream —
        the inline-fired flag set by the caller keeps that path from
        re-firing them.  Respects :attr:`_suppress_tool_output` for the
        stdout-only side, matching the base path's semantics.
        """
        detail = extract_tool_detail(block.name, block.input)
        if not self._suppress_tool_output:
            print(f"  [Tool] {block.name} -> {truncate(detail)}")
        if self.on_tool_use:
            self.on_tool_use(block.name, detail)
        if self.on_tool_call:
            self.on_tool_call(ToolUseBlock(
                id=block.id,
                name=block.name,
                input=block.input,
            ))


