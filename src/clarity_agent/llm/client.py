"""Abstract base class for low-level LLM clients.

An ``LLMClient`` wraps a single provider's message-creation API and returns
normalized :class:`~clarity_agent.llm.types.LLMResponse` objects. This is a
low-level interface used with raw LLM chat completion API's; the rest of the
clarity-agent consumes this via the higher-level ChatBackend interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, ClassVar

from clarity_agent.llm.types import LLMResponse, TextDeltaCallback, ToolCallback, UsageCallback

# ---------------------------------------------------------------------------
# Tool-detail extraction (shared by LLMClient callbacks and ChatBackend)
# ---------------------------------------------------------------------------

def truncate(val: str, limit: int = 80) -> str:
    return val[:limit] + "..." if len(val) > limit else val

# Tier 1: tool-specific formatters for the most useful summary per tool.
_TOOL_DETAIL_EXTRACTORS: dict[str, Callable[[dict], str]] = {
    "Bash": lambda inp: f"{inp.get('description', '')}: {inp.get('command', '')}",
    "Edit": lambda inp: inp.get("file_path", ""),
    "Read": lambda inp: inp.get("file_path", ""),
    "Task": lambda inp: inp.get("description", ""),
    "WebFetch": lambda inp: inp.get("url", ""),
    "WebSearch": lambda inp: inp.get("query", ""),
}

# Tier 2: ordered list of well-known input keys.  The first match wins.
_DETAIL_KEYS: list[str] = [
    "file_path", "command", "pattern", "query",
    "url", "path", "title", "description", "prompt",
]


def extract_tool_detail(name: str, tool_input: dict[str, Any]) -> str:
    """Return a short human-readable summary of a tool invocation.

    Used by :class:`LLMClient` and :class:`ChatBackend` callbacks to
    produce a compact description of what a tool call does.

    Resolution order:

    1. **Tool-specific** — a custom formatter for well-known tools
       (``Bash``, ``Edit``, ``Read``, …).
    2. **Well-known keys** — the first matching key from a priority list
       (``file_path``, ``command``, ``title``, …).
    3. **Generic** — parameter names only (avoids leaking values).
    """
    # Tier 1 – tool-specific
    if name in _TOOL_DETAIL_EXTRACTORS:
        return _TOOL_DETAIL_EXTRACTORS[name](tool_input)

    # Tier 2 – well-known keys
    for key in _DETAIL_KEYS:
        if key in tool_input:
            return str(tool_input[key])

    # Tier 3 – generic: show parameter names (avoids leaking values)
    if tool_input:
        return f"({', '.join(tool_input.keys())})"
    return ""


class LLMClient(ABC):
    """Async client for creating LLM messages.

    Implementations translate between the canonical request/response
    format and a specific provider's API (Anthropic, OpenAI, Azure, …).

    Tool definitions use the Anthropic-style canonical format::

        {
            "name": "tool_name",
            "description": "What the tool does",
            "input_schema": { … JSON Schema … },
        }

    Non-Anthropic backends translate this in their ``_create_message``
    implementation.

    Subclasses should declare :attr:`TIER_DEFAULTS` mapping all standard
    tiers (``"default"``, ``"deep"``, ``"fast"``) to concrete model strings
    for their provider.

    **Callbacks**

    Every tool-use block in a response is automatically printed to
    stdout (``[Tool] name -> detail``).  Set :attr:`on_tool_use` for
    additional handling (e.g. forwarding events to a web client).
    """

    TIER_DEFAULTS: ClassVar[dict[str, str]] = {}
    """Provider-specific mapping from tier names to model strings.

    Subclasses override this to declare which concrete models correspond
    to the ``"default"``, ``"deep"``, and ``"fast"`` tiers.  Callers can
    use :meth:`resolve_model` to translate a tier name before passing it
    to :meth:`create_message`.
    """

    on_tool_use: ToolCallback | None = None
    """Optional callback fired for each tool-use block in a response.

    This is *in addition to* the default ``[Tool]`` print.  Use it
    for things like forwarding events to a web UI or recording a
    transcript.
    """

    on_text_delta: TextDeltaCallback | None = None
    """Optional callback fired for each text chunk during streaming."""

    on_usage: UsageCallback | None = None
    """Optional callback fired when a response includes token usage data."""

    _suppress_tool_output: bool = False
    """When True, :meth:`create_message` skips the ``[Tool]`` print and
    ``on_tool_use`` callback.  Set by :class:`ChatBackend` tool loops
    that provide a handler which does its own output."""

    def resolve_model(self, model_or_tier: str) -> str:
        """Resolve a tier name or model string to a concrete model.

        - A known tier name (e.g. ``"deep"``) → the tier's model from
          :attr:`TIER_DEFAULTS`
        - Anything else → returned as-is (treated as a literal model string)
        """
        return self.TIER_DEFAULTS.get(model_or_tier, model_or_tier)

    async def create_message(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Create a single LLM response and fire any registered callbacks.

        This is the public entry point.  Subclasses implement the
        provider-specific logic in :meth:`_create_message`.

        Args:
            messages: Conversation history in Anthropic message format
                (``[{"role": "user"|"assistant", "content": …}, …]``).
            model: Model identifier (e.g. ``"claude-sonnet-4-5-20250929"``).
            max_tokens: Maximum tokens in the response.
            system: Optional system prompt.
            tools: Optional list of tool definitions in canonical format.

        Returns:
            A normalized :class:`LLMResponse`.
        """
        response = await self._create_message(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
        )
        if not self._suppress_tool_output:
            for tc in response.tool_calls:
                detail = extract_tool_detail(tc.name, tc.input)
                print(f"  [Tool] {tc.name} -> {truncate(detail)}")
                if self.on_tool_use:
                    self.on_tool_use(tc.name, detail)
        if response.usage and self.on_usage:
            self.on_usage(response.usage)
        return response

    @abstractmethod
    async def _create_message(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Provider-specific message creation (override in subclasses).

        Same parameters as :meth:`create_message`.  Subclasses should
        return a normalized :class:`LLMResponse`; callback dispatch is
        handled by the public method.
        """
        ...
