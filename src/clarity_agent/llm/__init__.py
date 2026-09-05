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

Model discovery:

- :func:`fetch_model_catalog` — list a provider's models, live where the
  provider supports it, cached, falling back to built-in tables.
- :func:`get_provider_model_catalog` — the built-in list alone, no network.

CLI integration:

- :class:`LLMConfig` — add standard LLM flags to a parser via
  :meth:`~LLMConfig.add_arguments`, resolve via :meth:`~LLMConfig.create`,
  then use :meth:`~LLMConfig.create_client` / :meth:`~LLMConfig.create_chat_backend`.
"""

from __future__ import annotations

from clarity_agent.llm.chat import ChatBackend, ClientChatBackend
from clarity_agent.llm.client import LLMClient
from clarity_agent.llm.config import LLMConfig
from clarity_agent.llm.factory import (
    create_chat_backend,
    create_client,
    fetch_model_catalog,
    get_provider_model_catalog,
)
from clarity_agent.llm.types import (
    LLMAuthExpiredError,
    LLMResponse,
    ModelCatalog,
    ModelInfo,
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
    "ModelCatalog",
    "ModelInfo",
    "TextBlock",
    "TokenUsage",
    "ToolCallback",
    "ToolHandler",
    "ToolUseBlock",
    "create_chat_backend",
    "create_client",
    "fetch_model_catalog",
    "get_provider_model_catalog",
]
