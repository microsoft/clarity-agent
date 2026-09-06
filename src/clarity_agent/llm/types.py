"""Provider-agnostic types for LLM responses.

These types normalize the response formats from different LLM providers
(Anthropic, OpenAI, Azure, etc.) into a common representation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class LLMAuthExpiredError(Exception):
    """Raised when an OAuth/token credential has expired and needs re-auth.

    Backends raise this when a token-based credential fails in a way
    that indicates the user must re-authenticate (e.g. refresh token
    expired or revoked).  The web UI can catch this to trigger a
    re-authentication flow.
    """


# Callback type for streaming text deltas: (text_chunk,) -> None
TextDeltaCallback = Callable[[str], None]

# Callback type for tool-use events: (tool_name, detail) -> None
#
# ``detail`` is a short flattened string suitable for human-readable
# display (UI badges, log lines).  Use :data:`StructuredToolCallback`
# when you need the structured ``ToolUseBlock`` (id, input dict) — for
# example, when writing to the transcript event log where fidelity
# matters.  The two callbacks fire in parallel.
ToolCallback = Callable[[str, str], None]

# Callback type for structured tool-use events: (tool_use_block,) -> None
#
# Receives the full :class:`ToolUseBlock` with its provider-assigned
# ``id`` and structured ``input`` dict.  Used by the transcript layer
# to record :class:`clarity_agent.transcript.ToolUse` events with
# round-trippable fidelity; UI surfaces that only need a display
# string should keep using :data:`ToolCallback`.
StructuredToolCallback = Callable[["ToolUseBlock"], None]

# Callback type for cost events: (cost_usd,) -> None
CostCallback = Callable[[float], None]

# Callback type for non-fatal warning events: (message,) -> None
WarnCallback = Callable[[str], None]

# Callback type for ephemeral status updates: (phase,) -> None
# Phases are coalesced state transitions (e.g. "reasoning", "tool:read_file")
# not a stream of every SDK event.  The frontend should display the
# latest status transiently, overwriting the previous one.
StatusCallback = Callable[[str], None]

# Callback type for tool-use loop handlers: (tool_call) -> result_string
ToolHandler = Callable[["ToolUseBlock"], str]


@dataclass(frozen=True)
class ModelInfo:
    """One model a provider will accept as a ``model=`` argument.

    Produced either by a live provider listing (``/v1/models`` and
    friends) or from a backend's built-in tables.  Purely descriptive:
    nothing here changes how a request is made, it just tells the
    picker what to show.
    """

    id: str
    """The identifier passed to the provider as ``model=``."""

    display_name: str
    """Human-readable name for the picker (``"Claude Opus 5"``)."""

    role: str | None = None
    """Optional highlight role — one of ``"default"``, ``"deep"``, or
    ``"fast"``, mirroring the keys of a backend's ``RECOMMENDED_MODELS``.

    Roles exist so the picker can surface a provider's few notable
    models above the long tail: the one we use by default, a heavier
    option, and a lighter one.  A model may fill several roles at once
    (a provider whose heaviest model is also its default);
    :func:`clarity_agent.llm.model_catalog.assign_roles` keeps the
    first match in ``default`` → ``deep`` → ``fast`` order, so each
    model appears exactly once and the model marked "default" is the
    one :attr:`ModelCatalog.default_model` selects."""

    description: str | None = None
    """Optional one-line description, when the provider supplies one."""

    context_window: int | None = None
    """Context window in tokens, when known.  Most provider listings
    don't report it, so this is usually filled from the backend's
    ``MODEL_CONTEXT_WINDOWS`` table; Gemini is the exception and
    reports a live value."""


@dataclass(frozen=True)
class ModelCatalog:
    """The set of models available for one provider + auth mode."""

    models: list[ModelInfo] = field(default_factory=list)
    """Available models.  Ordered with highlighted (role-bearing)
    models first, then the rest in provider order."""

    default_model: str = ""
    """Model to use when the user has never picked one — the provider's
    ``default`` role, not its ``deep`` one."""

    source: str = "builtin"
    """``"provider"`` when fetched live, ``"builtin"`` when it came
    from the backend's own tables."""

    free_form: bool = False
    """True when the provider can't be enumerated and the user must
    type an identifier — Azure, whose deployments are user-named.
    The picker renders a text field instead of a list."""

    error: str | None = None
    """Set when a live fetch was attempted and failed.  ``models``
    then holds the built-in fallback, so the picker stays usable;
    the message is for an inline note, not an empty menu."""

    @property
    def highlighted(self) -> list[ModelInfo]:
        """Models carrying a role, in ``default``/``deep``/``fast`` order."""
        order = {"default": 0, "deep": 1, "fast": 2}
        return sorted(
            (m for m in self.models if m.role is not None),
            key=lambda m: order.get(m.role or "", 99),
        )

    @property
    def rest(self) -> list[ModelInfo]:
        """Models without a role, in catalog order."""
        return [m for m in self.models if m.role is None]

    def get(self, model_id: str) -> ModelInfo | None:
        """Return the entry for *model_id*, or ``None`` if unlisted."""
        return next((m for m in self.models if m.id == model_id), None)


@dataclass
class TokenUsage:
    """Token usage from an LLM API call."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


# Callback type for usage events: (usage,) -> None
UsageCallback = Callable[[TokenUsage], None]


@dataclass
class CompactionInfo:
    """Backend-provided signal that an internal compaction occurred.

    Fired by a :class:`ChatBackend` when the provider has performed
    its own context-management compaction (e.g., Claude Agent SDK's
    auto-compact).  Carries the provider's summary so the orchestrator
    can record it directly rather than producing its own summary —
    the provider already paid for the summarization LLM call, and
    their summary reflects exactly what the model is now operating on.

    Phase 2 v1: the type + callback are wired into the orchestrator,
    but no backend currently produces these signals.  Phase 2.5 will
    add SDK-specific detection (PreCompact hook + JSONL transcript
    inspection for ``isCompactSummary`` entries).
    """

    summary: str
    """The provider's summary of the compacted-away portion of the
    conversation, ready to be stored in a
    :class:`~clarity_agent.transcript.CompactionSummary` event."""

    source_turn_count: int | None = None
    """Number of turns the summary represents.  ``None`` when the
    backend can't easily report a count (e.g., the SDK's JSONL
    doesn't make this cheap to extract); in that case the
    transcript layer derives the count from its own 70/30 split."""


# Callback type for backend-signaled compaction events.
CompactionCallback = Callable[[CompactionInfo], None]


@dataclass
class TextBlock:
    """A text content block in an LLM response."""

    text: str


@dataclass
class ToolUseBlock:
    """A tool-use content block in an LLM response."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMResponse:
    """Normalized response from an LLM provider.

    Attributes:
        content: List of text and/or tool-use blocks.
        stop_reason: Why the model stopped generating.  Canonical values:
            ``"end_turn"`` (model finished), ``"tool_use"`` (model wants
            to call tools), ``"max_tokens"`` (hit the token limit).
    """

    content: list[TextBlock | ToolUseBlock] = field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: TokenUsage | None = None

    @property
    def text(self) -> str:
        """Concatenate all text blocks into a single string."""
        return "\n".join(
            block.text for block in self.content if isinstance(block, TextBlock)
        )

    @property
    def tool_calls(self) -> list[ToolUseBlock]:
        """All tool-use blocks in the response."""
        return [
            block for block in self.content if isinstance(block, ToolUseBlock)
        ]

    @property
    def content_as_dicts(self) -> list[dict[str, Any]]:
        """Serialize content blocks to the canonical dict format.

        Useful for feeding assistant responses back into message history
        during multi-turn tool-use loops.
        """
        result: list[dict[str, Any]] = []
        for block in self.content:
            if isinstance(block, TextBlock):
                result.append({"type": "text", "text": block.text})
            elif isinstance(block, ToolUseBlock):
                result.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        return result
