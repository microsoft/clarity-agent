"""
Internal: produce a compacted summary of an event stream.

The summarization call itself is injected as a ``summarize_fn`` —
production wiring (in :class:`WebSessionAdapter`) supplies a closure
that calls the backend's chat path with a summarization prompt; tests
supply a fake.  Keeping the LLM call behind an injection point means
the rendering logic + prompt are unit-testable without spinning up a
real model.

The function returns the summary string ready to be stored on a
:class:`CompactionSummary` event.  Caller is responsible for the
``start_compacted_chapter`` rollover that consumes it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from clarity_agent.transcript._render import render_event
from clarity_agent.transcript.events import Event

# Instructions prepended to the rendered conversation when asking
# the model to summarize.  Optimized for downstream use as
# rebuild-from-summary context: the summary needs to contain enough
# decision-state and current-work information that a fresh model
# session can pick up coherently.
_SUMMARIZATION_PROMPT = (
    "Below is a portion of a long conversation between a user and "
    "the Clarity Agent (which helps the user think through projects "
    "structured around decisions and protocol documents).  The "
    "conversation is being compacted to fit within the model's "
    "context window.\n\n"
    "Produce a concise summary (3-6 paragraphs) capturing:\n"
    "- The user's project and what they're working through\n"
    "- Key decisions made (with the names/labels used in the protocol)\n"
    "- Current state of work and any in-flight tasks\n"
    "- Important context the next turn will need to continue coherently\n"
    "\n"
    "Write in a neutral, factual tone — this summary will be shown "
    "to the model (not the user) when continuing the conversation, "
    "so optimize for accuracy and reconstructability rather than "
    "narrative.\n"
    "\n"
    "Do NOT preface the summary with phrases like 'Here is the "
    "summary' — go directly into the content.\n"
    "\n"
    "CONVERSATION TO SUMMARIZE:\n\n"
)


def summarize_chapter(
    events: Iterable[Event],
    *,
    summarize_fn: Callable[[str], str],
) -> str:
    """Render events as a prompt, call ``summarize_fn``, return the summary.

    The function does no I/O of its own — all the LLM-side work is
    delegated to ``summarize_fn``, which receives the assembled
    prompt and is expected to return the summary text.

    Returns the summary string, suitable for storing on a
    :class:`CompactionSummary` event.
    """
    rendered_events = "".join(render_event(e) for e in events)
    prompt = _SUMMARIZATION_PROMPT + rendered_events
    summary = summarize_fn(prompt).strip()
    return summary
