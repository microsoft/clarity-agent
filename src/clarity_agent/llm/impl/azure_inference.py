"""Azure AI Inference backend implementation.

Provides :class:`AzureInferenceClient`, a low-level async client wrapping
the Azure AI Inference chat completions API.  High-level chat is handled by
:class:`~clarity_agent.llm.chat.ClientChatBackend`.
"""

from __future__ import annotations

import json
from typing import Any

import azure.ai.inference.aio as _azure_aio_mod
import azure.ai.inference.models as _azure_models
from azure.core.credentials import AzureKeyCredential as _AzureKeyCredential
from azure.identity import DefaultAzureCredential as _DefaultAzureCredential

from clarity_agent.llm.client import LLMClient
from clarity_agent.llm.impl._openai_compat import uses_legacy_max_tokens
from clarity_agent.llm.types import (
    LLMAuthExpiredError,
    LLMResponse,
    TextBlock,
    TokenUsage,
    ToolUseBlock,
)

_AZURE_TIER_DEFAULTS: dict[str, str] = {
    "default": "gpt-5.4",
    "deep": "gpt-5.4",
    "fast": "gpt-5.4-mini",
}

# Context-window size in tokens.  Azure deployments are typically
# named to match the OpenAI model family they serve, so the sizes
# follow the OpenAI map.  Custom deployment names not listed here
# fall back to ``ChatBackend.DEFAULT_CONTEXT_WINDOW`` or to a user
# override in ``Settings.context_window_overrides``.
_AZURE_MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-5.4": 128_000,
    "gpt-5.4-mini": 128_000,
}

# Map Azure finish reasons to canonical stop reasons.
_FINISH_REASON_MAP: dict[str, str] = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "length": "max_tokens",
    "content_filter": "end_turn",
}




def _translate_tools(
    tools: list[dict[str, Any]],
) -> list[Any]:
    """Translate canonical tool definitions to Azure format.

    Canonical (Anthropic-style)::

        {"name": "search", "description": "...", "input_schema": {...}}

    Azure (OpenAI-style)::

        ChatCompletionsToolDefinition(
            function=FunctionDefinition(name="search", description="...", parameters={...})
        )
    """
    result: list[Any] = []
    for tool in tools:
        result.append(_azure_models.ChatCompletionsToolDefinition(
            function=_azure_models.FunctionDefinition(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=tool.get("input_schema", {}),
            ),
        ))
    return result


def _translate_messages(
    messages: list[dict[str, Any]],
    system: str | None,
) -> list[Any]:
    """Translate canonical messages to Azure message objects.

    Azure expects system messages in the messages array rather than as
    a separate parameter.
    """
    result: list[Any] = []

    if system is not None:
        result.append(_azure_models.SystemMessage(content=system))

    for msg in messages:
        role: str = msg["role"]
        content: Any = msg["content"]
        if role == "user":
            result.append(_azure_models.UserMessage(content=content))
        elif role == "assistant":
            result.append(_azure_models.AssistantMessage(content=content))
        elif role == "tool":
            result.append(_azure_models.ToolMessage(
                content=content,
                tool_call_id=msg.get("tool_use_id", ""),
            ))

    return result


class AzureInferenceClient(LLMClient):
    """Low-level async LLM client wrapping Azure AI Inference.

    Translates Azure chat completion responses into provider-agnostic
    :class:`~clarity_agent.llm.types.LLMResponse` objects.

    Supports four authentication modes via ``auth_mode``:

    - **api_key**: pass ``api_key`` to use ``AzureKeyCredential``.
    - **default**: use ``DefaultAzureCredential`` from ``azure-identity``.
      Picks up tokens from ``az login``, managed identity, VS Code,
      environment variables, etc.
    - **interactive**: use ``InteractiveBrowserCredential`` — opens a
      browser for the user to sign in.  Best for desktop apps.
    - **device_code**: use ``DeviceCodeCredential`` — shows a code + URL
      for the user to authenticate.  Works in headless / SSH sessions.

    For Azure OpenAI endpoints, the deployment name is derived from the
    model parameter at call time.  The client constructs the
    deployment-specific endpoint URL automatically.
    """

    TIER_DEFAULTS = _AZURE_TIER_DEFAULTS
    MODEL_CONTEXT_WINDOWS = _AZURE_MODEL_CONTEXT_WINDOWS

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str | None = None,
        auth_mode: str = "default",
        tenant_id: str | None = None,
    ) -> None:

        self._uses_token_credential = False

        if auth_mode == "api_key":
            if api_key is None:
                raise ValueError("auth_mode='api_key' requires an api_key")
            self._credential = _AzureKeyCredential(api_key)

        elif auth_mode == "interactive":

            from azure.identity import InteractiveBrowserCredential
            kwargs: dict[str, Any] = {}
            if tenant_id:
                kwargs["tenant_id"] = tenant_id
            try:
                from azure.identity import TokenCachePersistenceOptions
                kwargs["cache_persistence_options"] = TokenCachePersistenceOptions(
                    name="clarity-agent",
                )
            except ImportError:
                pass  # older azure-identity without persistence support
            self._credential = InteractiveBrowserCredential(**kwargs)
            self._uses_token_credential = True

        elif auth_mode == "device_code":

            from azure.identity import DeviceCodeCredential
            dc_kwargs: dict[str, Any] = {}
            if tenant_id:
                dc_kwargs["tenant_id"] = tenant_id
            self._credential = DeviceCodeCredential(**dc_kwargs)
            self._uses_token_credential = True

        else:  # "default" — backward-compatible behavior
            if api_key is not None:
                self._credential = _AzureKeyCredential(api_key)
            else:

                self._credential = _DefaultAzureCredential()
                self._uses_token_credential = True

        self._base_endpoint = endpoint.rstrip("/")
        self._is_azure_openai = (
            ".openai.azure.com" in endpoint
            or ".cognitiveservices.azure.com" in endpoint
            or ".services.ai.azure.com" in endpoint
        )
        self._clients: dict[str, Any] = {}

    def _get_client(self, model: str) -> Any:
        """Return a ChatCompletionsClient for the given model/deployment.

        Azure OpenAI requires a per-deployment endpoint.  Clients are
        cached by model name.
        """
        if model not in self._clients:
            if self._is_azure_openai:
                endpoint = f"{self._base_endpoint}/openai/deployments/{model}"
            else:
                endpoint = self._base_endpoint

            kwargs: dict[str, Any] = {
                "endpoint": endpoint,
                "credential": self._credential,
            }
            # Azure AD credentials need the correct scope for Cognitive Services.
            if self._uses_token_credential:
                kwargs["credential_scopes"] = [
                    "https://cognitiveservices.azure.com/.default"
                ]
            if self._is_azure_openai:
                kwargs["api_version"] = "2025-01-01-preview"

            self._clients[model] = _azure_aio_mod.ChatCompletionsClient(**kwargs)
        return self._clients[model]

    async def _create_message(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        client = self._get_client(model)

        kwargs: dict[str, Any] = {
            "messages": _translate_messages(messages, system),
            "model": model,
        }

        # ``max_completion_tokens`` is the forward-compatible kwarg
        # name — only pre-o1 chat models still take ``max_tokens``.
        # See ``_openai_compat`` for the prefix list and rationale.
        # The Azure inference SDK doesn't accept ``max_completion_tokens``
        # as a first-class argument, so we route it through
        # ``model_extras`` (which forwards to the underlying HTTP body).
        if uses_legacy_max_tokens(model):
            kwargs["max_tokens"] = max_tokens
        else:
            kwargs["model_extras"] = {"max_completion_tokens": max_tokens}

        if tools:
            kwargs["tools"] = _translate_tools(tools)

        kwargs["stream"] = True

        try:
            stream = await client.complete(**kwargs)
        except Exception as exc:
            if self._uses_token_credential and "authentication" in str(exc).lower():
                raise LLMAuthExpiredError(
                    "Azure authentication has expired. Please re-authenticate."
                ) from exc
            raise

        # Accumulate the streamed response.
        text_parts: list[str] = []
        tool_calls_by_index: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage = None

        async for chunk in stream:
            for choice in chunk.choices:
                delta = choice.delta
                if choice.finish_reason:
                    finish_reason = choice.finish_reason

                if delta.content:
                    text_parts.append(delta.content)
                    if self.on_text_delta:
                        self.on_text_delta(delta.content)

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index if hasattr(tc_delta, "index") else 0
                        if idx not in tool_calls_by_index:
                            tool_calls_by_index[idx] = {
                                "id": getattr(tc_delta, "id", "") or "",
                                "name": "",
                                "arguments": "",
                            }
                        entry = tool_calls_by_index[idx]
                        if getattr(tc_delta, "id", None):
                            entry["id"] = tc_delta.id
                        func = getattr(tc_delta, "function", None)
                        if func:
                            if getattr(func, "name", None):
                                entry["name"] = func.name
                            if getattr(func, "arguments", None):
                                entry["arguments"] += func.arguments

            # Usage may appear on the final chunk.
            if hasattr(chunk, "usage") and chunk.usage:
                usage = TokenUsage(
                    input_tokens=getattr(chunk.usage, "prompt_tokens", 0),
                    output_tokens=getattr(chunk.usage, "completion_tokens", 0),
                )

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


