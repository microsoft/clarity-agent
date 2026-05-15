"""High-level chat backend abstract base class and generic implementation.
This is how the rest of the clarity-agent interacts with LLMs.

A ``ChatBackend`` provides a conversation-oriented interface for LLM
interaction.  This formalizes the interface shared by all LLM backends,
and is directly provided by AI backends like the Claude Agent SDK.

``ClientChatBackend`` wraps any :class:`~clarity_agent.llm.client.LLMClient`
and provides both conversational chat and tool-use loop support. This
is used when you are using a raw LLM API, such as the Azure, OpenAI, or
Anthropic ones.

ChatBackend is a context manager: use it in a ``with`` block to ensure
proper cleanup::

    with config.create_chat_backend(...) as backend:
        response = backend.chat("Hello")
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType
from typing import Any, ClassVar

from clarity_agent.llm.types import (
    CostCallback,
    LLMResponse,
    StatusCallback,
    TextDeltaCallback,
    StructuredToolCallback,
    ToolCallback,
    ToolHandler,
    ToolUseBlock,
    UsageCallback,
    WarnCallback,
)


class ChatBackend(ABC):
    """Abstract base class for high-level chat backends.

    Implementations manage their own conversation state, system prompt
    construction, and provider-specific details.  Callers (like
    ``ClaritySession``) interact only through this interface.

    Subclasses must implement :meth:`chat` and set :attr:`supports_tools`.
    Override :meth:`connect` and :meth:`disconnect` if the backend needs
    setup or teardown.

    Subclasses should declare :attr:`TIER_DEFAULTS` mapping all standard
    tiers (``"default"``, ``"deep"``, ``"fast"``) to concrete model strings
    for their provider.
    """

    on_tool_use: ToolCallback | None = None
    # Structured tool-call callback, fired alongside ``on_tool_use``.
    # See :data:`StructuredToolCallback` — receives the original
    # :class:`ToolUseBlock` so consumers can record the structured
    # input dict and provider-assigned id (used by the transcript
    # event log).
    on_tool_call: StructuredToolCallback | None = None
    on_text_delta: TextDeltaCallback | None = None
    on_cost: CostCallback | None = None
    on_usage: UsageCallback | None = None
    on_warning: WarnCallback | None = None
    on_status: StatusCallback | None = None
    supports_tools: bool = False

    TIER_DEFAULTS: ClassVar[dict[str, str]] = {}
    """Provider-specific mapping from tier names to model strings.

    Subclasses override this to declare which concrete models correspond
    to the ``"default"``, ``"deep"``, and ``"fast"`` tiers.
    """

    @property
    def llm_session_id(self) -> str | None:
        """Return the backend's session ID, if any.

        Only meaningful for backends with intrinsic session persistence
        (e.g. Claude Agent SDK).  Other backends return ``None``.
        """
        return None

    @llm_session_id.setter
    def llm_session_id(self, value: str | None) -> None:
        """Set the backend's session ID for session restoration.

        Backends that don't support session IDs silently ignore this.
        """

    def resolve_model(self, model_or_tier: str | None) -> str:
        """Resolve a tier name or model string to a concrete model.

        - ``None`` → ``TIER_DEFAULTS["default"]``
        - A known tier name (e.g. ``"deep"``) → the tier's model from
          :attr:`TIER_DEFAULTS`
        - Anything else → returned as-is (treated as a literal model string)
        """
        if model_or_tier is None:
            model_or_tier = "default"
        return self.TIER_DEFAULTS.get(model_or_tier, model_or_tier)

    def connect(self) -> None:
        """Establish the backend connection (if needed)."""

    def disconnect(self) -> None:
        """Tear down the backend connection and reset state."""

    @abstractmethod
    def chat(
        self,
        user_message: str,
        system_prompt: str | None = None,
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_handler: ToolHandler | None = None,
    ) -> str:
        """Send a user message and return the assistant's text response.

        Args:
            user_message: The message from the user.
            system_prompt: Optional system prompt override for this turn.
            model: Optional model override for this turn.  When ``None``,
                the backend's default model (``TIER_DEFAULTS["default"]``)
                is used.  The conversation history is preserved regardless
                of model changes.
            tools: Optional list of tool schemas to provide to the model.
                When provided, the model may respond with tool calls which
                are dispatched to *tool_handler*.
            tool_handler: Callable that receives a :class:`ToolUseBlock`
                and returns a result string.  Required when *tools* is
                provided and the backend uses native tool-use (API
                backends).  SDK backends may ignore this and deliver
                tools via CLI instructions instead.

        Returns:
            The assistant's text response.
        """

    async def arun_tool_loop(
        self,
        *,
        user_message: str,
        system_prompt: str | None = None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_handler: ToolHandler | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Run an async tool-use loop.

        Sends *user_message* to the model with *tools* defined. When the
        model responds with ``stop_reason == "tool_use"``, each tool call
        is passed to *tool_handler* and the results are fed back. The loop
        continues until the model stops requesting tools.

        Subclasses that wrap an :class:`LLMClient` should override this.
        The default raises :class:`NotImplementedError`.

        Returns the final :class:`LLMResponse` (the one that ended the loop).
        """
        raise NotImplementedError("This backend does not support tool-use loops")

    def run_tool_loop(
        self,
        *,
        user_message: str,
        system_prompt: str | None = None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_handler: ToolHandler | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Synchronous wrapper around :meth:`arun_tool_loop`."""
        return asyncio.run(self.arun_tool_loop(
            user_message=user_message,
            system_prompt=system_prompt,
            model=model,
            tools=tools,
            tool_handler=tool_handler,
            max_tokens=max_tokens,
        ))

    def __enter__(self) -> ChatBackend:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.disconnect()


class ClientChatBackend(ChatBackend):
    """Generic chat backend wrapping any :class:`LLMClient`.

    Provides both conversational :meth:`chat` and :meth:`arun_tool_loop`
    support.  Replaces the provider-specific ``AnthropicChatBackend``,
    ``OpenAIChatBackend``, and ``AzureInferenceChatBackend`` classes which
    were all identical.
    """

    def __init__(
        self,
        client: Any,  # LLMClient (typed Any to avoid circular import at module level)
        *,
        project_dir: Path,
        clarity_agent_dir: Path,
        tiers: dict[str, str] | None = None,
    ) -> None:
        self._client = client
        self.project_dir: Path = project_dir
        self.clarity_agent_dir: Path = clarity_agent_dir
        self.conversation_history: list[dict[str, Any]] = []
        # User-configured tier overrides (e.g. from LLMConfig.tiers, which
        # comes from --model / settings / evals/config.yaml).  Layered
        # over the client's provider defaults in the TIER_DEFAULTS
        # property so resolve_model(None) honors the user's choice.
        self._tier_overrides: dict[str, str] = dict(tiers) if tiers else {}
        # Persistent event loop for async LLM calls.  asyncio.run()
        # closes its loop after each call, which breaks clients that
        # cache connections (e.g. aiohttp in Azure AI Inference).
        # Created in connect(), closed in disconnect().
        self._loop: asyncio.AbstractEventLoop | None = None

    def connect(self) -> None:
        """Create a persistent event loop for async LLM calls.

        ``asyncio.run()`` closes its loop after each call, which breaks
        clients that cache connections (e.g. aiohttp in Azure AI Inference).
        """
        self._loop = asyncio.new_event_loop()

    @property  # type: ignore[override]
    def TIER_DEFAULTS(self) -> dict[str, str]:  # type: ignore[override]
        """Client's provider defaults with user tier overrides layered on top.

        Overrides come from :class:`LLMConfig` (``--model``, settings,
        ``evals/config.yaml``) and must win over the provider's built-in
        defaults, otherwise a configured model is silently ignored when
        :meth:`resolve_model` is called with ``None``.
        """
        return {**self._client.TIER_DEFAULTS, **self._tier_overrides}

    @property  # type: ignore[override]
    def on_tool_use(self) -> ToolCallback | None:  # type: ignore[override]
        """Read the tool-use callback."""
        return self._on_tool_use

    @on_tool_use.setter
    def on_tool_use(self, value: ToolCallback | None) -> None:
        """Set the tool-use callback on both backend and wrapped client."""
        self._on_tool_use = value
        self._client.on_tool_use = value

    @property  # type: ignore[override]
    def on_tool_call(self) -> StructuredToolCallback | None:  # type: ignore[override]
        """Read the structured tool-call callback."""
        return getattr(self, "_on_tool_call", None)

    @on_tool_call.setter
    def on_tool_call(self, value: StructuredToolCallback | None) -> None:
        """Set the structured tool-call callback on backend and wrapped client.

        Mirrors :attr:`on_tool_use` — kept in sync so the same call
        pattern works regardless of which layer (backend's own tool
        loop, or the wrapped client's internal path) emits the event.
        """
        self._on_tool_call = value
        # The wrapped client may not have this attribute on older
        # versions; guard so we don't break existing clients during
        # the rollout.
        if hasattr(self._client, "on_tool_call"):
            self._client.on_tool_call = value

    @property  # type: ignore[override]
    def on_text_delta(self) -> TextDeltaCallback | None:  # type: ignore[override]
        """Read the text delta callback."""
        return self._on_text_delta

    @on_text_delta.setter
    def on_text_delta(self, value: TextDeltaCallback | None) -> None:
        """Set the text delta callback on both backend and wrapped client."""
        self._on_text_delta = value
        self._client.on_text_delta = value

    @property  # type: ignore[override]
    def on_usage(self) -> UsageCallback | None:  # type: ignore[override]
        """Read the usage callback."""
        return self._on_usage

    @on_usage.setter
    def on_usage(self, value: UsageCallback | None) -> None:
        """Set the usage callback on both backend and wrapped client."""
        self._on_usage = value
        self._client.on_usage = value

    def _build_system_prompt(self, system_prompt: str | None = None) -> str:
        """Build the full system prompt with base context."""
        from clarity_agent.app_paths import protocol_dir as _protocol_dir
        pd = _protocol_dir(self.project_dir)
        base: str = (
            "You are running the Clarity Agent framework.  Clarity "
            "helps users think through any kind of project that "
            "involves consequential decisions — a product launch, a "
            "research direction, a hiring plan, a career pivot, a "
            "policy question, a software system, or anything else "
            "where the thinking IS the work.  Do NOT assume the user "
            "is building software or writing code unless they tell "
            "you they are; let them describe the project in their own "
            "terms.\n\n"
            f"The project directory is: {self.project_dir}\n"
            f"The protocol directory is: {pd}\n\n"
            f"The clarity-agent installation directory is: {self.clarity_agent_dir}\n"
            f"Process guides are at: {self.clarity_agent_dir / 'processes'}/\n"
            f"Thinker guides are at: {self.clarity_agent_dir / 'thinkers'}/\n\n"
            "Follow the process guides exactly as written."
        )
        if system_prompt:
            base += f"\n\n{system_prompt}"
        return base

    def chat(
        self,
        user_message: str,
        system_prompt: str | None = None,
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_handler: ToolHandler | None = None,
    ) -> str:
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
        })

        full_system: str = self._build_system_prompt(system_prompt)
        resolved_model: str = self.resolve_model(model)

        # Suppress duplicate tool output when a handler is provided.
        if tool_handler is not None:
            self._client._suppress_tool_output = True

        try:
            while True:
                kwargs: dict[str, Any] = {
                    "model": resolved_model,
                    "max_tokens": 16384,
                    "system": full_system,
                    "messages": self.conversation_history,
                }
                if tools:
                    kwargs["tools"] = tools

                if self._loop is None:
                    raise RuntimeError("ClientChatBackend.connect() was not called")
                response: LLMResponse = self._loop.run_until_complete(
                    self._client.create_message(**kwargs)
                )

                # Process tool calls if any.
                tool_calls: list[ToolUseBlock] = response.tool_calls
                tool_results: list[dict[str, Any]] = []
                for tc in tool_calls:
                    # Fire the structured callback first — transcript
                    # consumers want every tool call recorded, not
                    # just the ones without a handler.  Independent
                    # of the legacy ``on_tool_use`` stringified path
                    # below.
                    if self.on_tool_call:
                        self.on_tool_call(tc)
                    result_text: str = "OK"
                    if tool_handler is not None:
                        result_text = tool_handler(tc)
                    elif self.on_tool_use:
                        from clarity_agent.llm.client import extract_tool_detail
                        detail = extract_tool_detail(tc.name, tc.input)
                        self.on_tool_use(tc.name, detail)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": result_text,
                    })

                # If the model is done requesting tools, extract text and return.
                if response.stop_reason != "tool_use":
                    assistant_message: str = response.text
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": assistant_message,
                    })
                    return assistant_message

                # Mid-loop: preserve tool exchanges in conversation history.
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content_as_dicts,
                })
                self.conversation_history.append({
                    "role": "user",
                    "content": tool_results,
                })
        finally:
            if tool_handler is not None:
                self._client._suppress_tool_output = False

    async def arun_tool_loop(
        self,
        *,
        user_message: str,
        system_prompt: str | None = None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_handler: ToolHandler | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Run a tool-use loop via the wrapped :class:`LLMClient`.

        The loop sends *user_message*, then repeatedly processes tool calls
        via *tool_handler* until the model stops requesting tools.  Each
        tool call result is fed back as a ``tool_result`` message.

        This is a stateless loop — it does NOT append to
        :attr:`conversation_history`.  Use :meth:`chat` for conversational
        interactions.
        """
        resolved_model: str = self.resolve_model(model)
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_message},
        ]

        # When a tool_handler is provided, it handles its own output and
        # callbacks.  Suppress the client's generic [Tool] print to avoid
        # duplicate output.
        if tool_handler is not None:
            self._client._suppress_tool_output = True

        try:
            while True:
                response: LLMResponse = await self._client.create_message(
                    model=resolved_model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=messages,
                    tools=tools,
                )

                # Always process tool calls via handler, even in the final
                # response.
                tool_calls: list[ToolUseBlock] = response.tool_calls
                tool_results: list[dict[str, Any]] = []
                for tc in tool_calls:
                    result_text: str = "OK"
                    if tool_handler is not None:
                        result_text = tool_handler(tc)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": result_text,
                    })

                # Stop if the model is done requesting tools.
                if response.stop_reason != "tool_use":
                    return response

                # Feed assistant response and tool results back.
                messages.append({
                    "role": "assistant",
                    "content": response.content_as_dicts,
                })
                messages.append({"role": "user", "content": tool_results})
        finally:
            self._client._suppress_tool_output = False

    def disconnect(self) -> None:
        """Clear conversation history and close the event loop."""
        self.conversation_history.clear()
        if self._loop is not None and not self._loop.is_closed():
            self._loop.close()
