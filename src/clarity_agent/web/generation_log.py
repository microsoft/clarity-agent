"""Generic formatting helpers for web LLM generation logs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

APPROX_CHARS_PER_TOKEN = 4
PROVIDER_MANAGED_CONTEXT_PROVIDERS = frozenset({"anthropic", "github"})
PROVIDER_MANAGED_CONTEXT_BACKENDS = frozenset({"CopilotChatBackend", "SdkChatBackend"})


@dataclass(frozen=True)
class RequestLogContext:
    provider: str
    model: str
    tier: str
    process: str
    auth_mode: str
    credential: str
    endpoint: str
    tool_count: int
    user_message_chars: int
    system_prompt_chars: int


@dataclass(frozen=True)
class ContextSegment:
    name: str
    role: str
    chars: int | None
    source: str
    position: str | None = None


@dataclass(frozen=True)
class ContextManifest:
    context_window_tokens: int
    provider_managed_context: bool
    segments: list[ContextSegment]


def provider_manages_context(provider: str, backend_name: str) -> bool:
    """Return whether the provider may hold unseen context internally.

    Args:
        provider: Configured provider name.
        backend_name: Runtime chat backend class name.

    Returns:
        True when Clarity cannot inspect the final provider-side message history.
    """
    return (
        provider in PROVIDER_MANAGED_CONTEXT_PROVIDERS
        or backend_name in PROVIDER_MANAGED_CONTEXT_BACKENDS
    )


def serialized_char_count(value: Any) -> int:
    """Return a deterministic redacted character count.

    Args:
        value: Value to measure after JSON serialization.

    Returns:
        Number of serialized characters, or ``repr`` length for unserializable values.
    """
    try:
        return len(json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ))
    except (TypeError, ValueError):
        return len(repr(value))


def format_request_started(context: RequestLogContext) -> str:
    """Format the start of an LLM request.

    Args:
        context: Redacted request metadata.

    Returns:
        Human-readable generation log line.
    """
    return (
        "llm.request started. "
        f"Sending this turn to provider {context.provider} with model {context.model}. "
        f"Tier: {context.tier}. "
        f"Process: {context.process}. "
        f"Auth mode: {context.auth_mode}; credential {context.credential}; "
        f"endpoint {context.endpoint}. "
        f"Tools available: {context.tool_count}. "
        f"User message: {context.user_message_chars} chars. "
        f"Added system instructions: {context.system_prompt_chars} chars."
    )


def format_stream_started(provider: str, model: str) -> str:
    """Format the first streamed text event.

    Args:
        provider: Configured provider name.
        model: Active model name.

    Returns:
        Human-readable generation log line.
    """
    return (
        "llm.stream started. "
        f"First text arrived from {provider} using {model}."
    )


def format_response_failed(
    *,
    provider: str,
    model: str,
    duration_ms: int,
    error_type: str,
) -> str:
    """Format a failed LLM response.

    Args:
        provider: Configured provider name.
        model: Active model name.
        duration_ms: Elapsed request duration in milliseconds.
        error_type: Exception class name.

    Returns:
        Human-readable generation log line.
    """
    return (
        f"llm.response failed after {duration_ms} ms. "
        f"Provider: {provider}. "
        f"Model: {model}. "
        f"Error type: {error_type}."
    )


def format_response_complete(
    *,
    provider: str,
    model: str,
    duration_ms: int,
    response_chars: int,
    stream_chunks: int,
    stream_chars: int,
) -> str:
    """Format a completed LLM response.

    Args:
        provider: Configured provider name.
        model: Active model name.
        duration_ms: Elapsed request duration in milliseconds.
        response_chars: Final response size in characters.
        stream_chunks: Number of streamed chunks observed.
        stream_chars: Number of streamed characters observed.

    Returns:
        Human-readable generation log line.
    """
    return (
        f"llm.response complete in {duration_ms} ms. "
        f"Provider: {provider}. "
        f"Model: {model}. "
        f"Response: {response_chars} chars. "
        f"Streamed chunks: {stream_chunks}; "
        f"streamed chars: {stream_chars}."
    )


def format_context_manifest(manifest: ContextManifest) -> list[str]:
    """Format a redacted prompt map for an LLM request.

    Args:
        manifest: Redacted context-window measurements.

    Returns:
        One manifest line followed by one line per context segment.
    """
    segment_lines, known_tokens = _format_segments(manifest)
    provider_visibility = (
        "not visible to Clarity after handoff"
        if manifest.provider_managed_context
        else "visible to Clarity in local backend history"
    )
    summary = (
        "llm.context_manifest Prompt map: "
        f"known context is about {known_tokens:,} tokens "
        f"({_window_fraction_label(known_tokens, manifest.context_window_tokens)} "
        f"of the {manifest.context_window_tokens:,}-token model window). "
        "Raw prompt text is omitted. "
        f"Provider-managed context is {provider_visibility}."
    )
    return [summary, *segment_lines]


def _format_segments(manifest: ContextManifest) -> tuple[list[str], int]:
    lines: list[str] = []
    cursor = 0
    known_tokens = 0
    total = len(manifest.segments)
    for index, segment in enumerate(manifest.segments, start=1):
        if segment.chars is None:
            lines.append(_format_unknown_segment(index, total, segment))
            continue

        tokens = _estimate_tokens(segment.chars)
        known_tokens += tokens
        if segment.position is None:
            position = _position_label(
                cursor,
                cursor + tokens,
                manifest.context_window_tokens,
            )
            cursor += tokens
        else:
            position = segment.position
        lines.append(_format_known_segment(index, total, segment, tokens, position))
    return lines, known_tokens


def _format_known_segment(
    index: int,
    total: int,
    segment: ContextSegment,
    tokens: int,
    position: str,
) -> str:
    return (
        f"llm.context_segment {index}/{total}: {segment.name}. "
        f"Role: {segment.role}. "
        f"Size: about {tokens:,} tokens from {segment.chars:,} chars. "
        f"Position: {_position_explanation(position)}. "
        f"Source: {segment.source}. "
        "Content: omitted."
    )


def _format_unknown_segment(index: int, total: int, segment: ContextSegment) -> str:
    return (
        f"llm.context_segment {index}/{total}: {segment.name}. "
        f"Role: {segment.role}. "
        "Size: unknown. "
        f"Position: {_position_explanation(segment.position)}. "
        f"Source: {segment.source}. "
        "Content: not visible to Clarity."
    )


def _estimate_tokens(chars: int) -> int:
    if chars <= 0:
        return 0
    return max(1, (chars + APPROX_CHARS_PER_TOKEN - 1) // APPROX_CHARS_PER_TOKEN)


def _position_label(start_tokens: int, end_tokens: int, context_window: int) -> str:
    if context_window <= 0:
        return "unknown"
    return f"{start_tokens / context_window:.1%}-{end_tokens / context_window:.1%}"


def _window_fraction_label(tokens: int, context_window: int) -> str:
    if context_window <= 0:
        return "unknown"
    return f"{tokens / context_window:.1%}"


def _position_explanation(position: str | None) -> str:
    if position == "provider_managed":
        return "provider-managed, exact position not visible to Clarity"
    if position == "provider_specific":
        return "provider-specific placement"
    if position is None or position == "unknown":
        return "unknown"
    return f"about {position} of the known context window"
