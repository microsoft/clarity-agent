"""LLM backend abstraction layer.

Provides two abstraction levels:

- **Low-level** (:class:`LLMClient`): async message creation with tool
  support.  Optional interface for provider implementations.
- **High-level** (:class:`ChatBackend`): conversational interface with
  connection management and tool-use loops.  Used by ``ClaritySession``
  and the web session adapter.

:class:`ClientChatBackend` wraps any :class:`LLMClient` and provides both
conversational :meth:`~ClientChatBackend.chat` and
:meth:`~ClientChatBackend.arun_tool_loop` support.

Factory functions:

- :func:`create_client` — build an :class:`LLMClient` for a provider.
- :func:`create_chat_backend` — build a :class:`ChatBackend` for a provider.

CLI integration:

- :class:`LLMConfig` — add standard LLM flags to a parser via
  :meth:`~LLMConfig.add_arguments`, resolve via :meth:`~LLMConfig.create`,
  then use :meth:`~LLMConfig.create_client` / :meth:`~LLMConfig.create_chat_backend`.
"""

from __future__ import annotations

from clarity_agent.llm.chat import ChatBackend, ClientChatBackend
from clarity_agent.llm.client import LLMClient
from clarity_agent.llm.config import LLMConfig
from clarity_agent.llm.factory import create_chat_backend, create_client
from clarity_agent.llm.types import (
    LLMAuthExpiredError,
    LLMResponse,
    TextBlock,
    TokenUsage,
    ToolCallback,
    ToolHandler,
    ToolUseBlock,
)

__all__ = [
    "ChatBackend",
    "ClientChatBackend",
    "LLMAuthExpiredError",
    "LLMClient",
    "LLMConfig",
    "LLMResponse",
    "TextBlock",
    "TokenUsage",
    "ToolCallback",
    "ToolHandler",
    "ToolUseBlock",
    "create_chat_backend",
    "create_client",
]
