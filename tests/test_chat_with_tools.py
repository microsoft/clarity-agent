"""Tests for ChatBackend.chat() with tool-use support.

Verifies that ClientChatBackend correctly handles tools in chat(),
preserving conversation history and dispatching to the tool_handler.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from clarity_agent.llm import ClientChatBackend, LLMResponse, TextBlock, ToolUseBlock


def _make_backend(
    mock_client: MagicMock, tmp_path: Path,
) -> ClientChatBackend:
    """Create a ClientChatBackend with a mock client."""
    backend = ClientChatBackend(
        mock_client,
        project_dir=tmp_path,
        clarity_agent_dir=tmp_path / "agent",
    )
    backend.connect()
    return backend


def _mock_client(responses: list[LLMResponse]) -> MagicMock:
    """Create a mock LLMClient that returns the given responses in sequence."""
    client = MagicMock()
    client.TIER_DEFAULTS = {"default": "test-model", "deep": "test-deep", "fast": "test-fast"}
    client.on_tool_use = None
    client._suppress_tool_output = False

    call_count = 0

    async def create_message(**kwargs: Any) -> LLMResponse:
        nonlocal call_count
        resp = responses[call_count]
        call_count += 1
        return resp

    client.create_message = create_message
    return client


# ---------------------------------------------------------------------------
# Basic chat without tools (backward compat)
# ---------------------------------------------------------------------------

class TestChatWithoutTools:
    """chat() works without tools (backward compatibility)."""

    def test_basic_chat(self, tmp_path: Path) -> None:
        resp = LLMResponse(
            content=[TextBlock(text="Hello!")],
            stop_reason="end_turn",
        )
        client = _mock_client([resp])
        backend = _make_backend(client, tmp_path)

        result = backend.chat("Hi there")
        assert result == "Hello!"
        assert len(backend.conversation_history) == 2  # user + assistant

    def test_preserves_conversation_history(self, tmp_path: Path) -> None:
        r1 = LLMResponse(content=[TextBlock(text="First")], stop_reason="end_turn")
        r2 = LLMResponse(content=[TextBlock(text="Second")], stop_reason="end_turn")
        client = _mock_client([r1, r2])
        backend = _make_backend(client, tmp_path)

        backend.chat("Message 1")
        backend.chat("Message 2")
        assert len(backend.conversation_history) == 4  # 2 user + 2 assistant


# ---------------------------------------------------------------------------
# Chat with tools
# ---------------------------------------------------------------------------

class TestChatWithTools:
    """chat() with tools dispatches to handler and preserves history."""

    def _sample_tools(self) -> list[dict[str, Any]]:
        return [{
            "name": "lookup",
            "description": "Look something up.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query"},
                },
                "required": ["query"],
            },
        }]

    def test_tool_call_then_final_response(self, tmp_path: Path) -> None:
        """Model calls a tool, then responds with text."""
        tool_resp = LLMResponse(
            content=[
                TextBlock(text="Let me look that up."),
                ToolUseBlock(id="t1", name="lookup", input={"query": "test"}),
            ],
            stop_reason="tool_use",
        )
        final_resp = LLMResponse(
            content=[TextBlock(text="Found it!")],
            stop_reason="end_turn",
        )
        client = _mock_client([tool_resp, final_resp])
        backend = _make_backend(client, tmp_path)

        handler_calls: list[ToolUseBlock] = []

        def handler(tc: ToolUseBlock) -> str:
            handler_calls.append(tc)
            return "result: success"

        result = backend.chat(
            "Find X",
            tools=self._sample_tools(),
            tool_handler=handler,
        )
        assert result == "Found it!"
        assert len(handler_calls) == 1
        assert handler_calls[0].name == "lookup"
        assert handler_calls[0].input == {"query": "test"}

    def test_tool_results_in_conversation_history(self, tmp_path: Path) -> None:
        """Tool exchanges are preserved in conversation_history."""
        tool_resp = LLMResponse(
            content=[
                ToolUseBlock(id="t1", name="lookup", input={"query": "x"}),
            ],
            stop_reason="tool_use",
        )
        final_resp = LLMResponse(
            content=[TextBlock(text="Done.")],
            stop_reason="end_turn",
        )
        client = _mock_client([tool_resp, final_resp])
        backend = _make_backend(client, tmp_path)

        backend.chat(
            "Test",
            tools=self._sample_tools(),
            tool_handler=lambda tc: "ok",
        )

        # History should contain:
        # 1. user message
        # 2. assistant (tool_use)
        # 3. user (tool_result)
        # 4. assistant (final text)
        assert len(backend.conversation_history) == 4
        assert backend.conversation_history[0]["role"] == "user"
        assert backend.conversation_history[1]["role"] == "assistant"
        assert backend.conversation_history[2]["role"] == "user"
        assert backend.conversation_history[3]["role"] == "assistant"

        # The tool result should be in history
        tool_result_msg = backend.conversation_history[2]["content"]
        assert any(
            item.get("type") == "tool_result" for item in tool_result_msg
        )

    def test_on_tool_use_callback_without_handler(self, tmp_path: Path) -> None:
        """Without a handler, on_tool_use callback fires."""
        tool_resp = LLMResponse(
            content=[
                ToolUseBlock(id="t1", name="lookup", input={"query": "x"}),
            ],
            stop_reason="tool_use",
        )
        final_resp = LLMResponse(
            content=[TextBlock(text="Done.")],
            stop_reason="end_turn",
        )
        client = _mock_client([tool_resp, final_resp])
        backend = _make_backend(client, tmp_path)

        callback_calls: list[tuple[str, str]] = []
        backend.on_tool_use = lambda name, detail: callback_calls.append((name, detail))

        backend.chat("Test", tools=self._sample_tools())
        assert len(callback_calls) == 1
        assert callback_calls[0][0] == "lookup"

    def test_suppress_tool_output_restored_on_error(self, tmp_path: Path) -> None:
        """_suppress_tool_output is reset even if an exception occurs."""
        client = MagicMock()
        client.TIER_DEFAULTS = {"default": "m", "deep": "d", "fast": "f"}
        client.on_tool_use = None
        client._suppress_tool_output = False

        async def failing_create(**kwargs: Any) -> LLMResponse:
            raise RuntimeError("boom")

        client.create_message = failing_create
        backend = _make_backend(client, tmp_path)

        with pytest.raises(RuntimeError, match="boom"):
            backend.chat(
                "Test",
                tools=self._sample_tools(),
                tool_handler=lambda tc: "ok",
            )

        assert client._suppress_tool_output is False

    def test_chat_without_tools_still_works(self, tmp_path: Path) -> None:
        """Passing tools=None (default) works normally."""
        resp = LLMResponse(
            content=[TextBlock(text="No tools needed.")],
            stop_reason="end_turn",
        )
        client = _mock_client([resp])
        backend = _make_backend(client, tmp_path)

        result = backend.chat("Hi")
        assert result == "No tools needed."

    def test_multiple_tool_calls_in_single_response(self, tmp_path: Path) -> None:
        """Model returns multiple tool calls in one response."""
        tool_resp = LLMResponse(
            content=[
                ToolUseBlock(id="t1", name="lookup", input={"query": "a"}),
                ToolUseBlock(id="t2", name="lookup", input={"query": "b"}),
            ],
            stop_reason="tool_use",
        )
        final_resp = LLMResponse(
            content=[TextBlock(text="Both found.")],
            stop_reason="end_turn",
        )
        client = _mock_client([tool_resp, final_resp])
        backend = _make_backend(client, tmp_path)

        calls: list[str] = []
        result = backend.chat(
            "Find both",
            tools=self._sample_tools(),
            tool_handler=lambda tc: (calls.append(tc.input["query"]), "ok")[1],
        )
        assert result == "Both found."
        assert calls == ["a", "b"]
