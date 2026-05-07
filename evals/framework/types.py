"""Shared data types for the eval framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Turn:
    """A single user → target exchange."""
    user: str
    target: str


@dataclass
class SessionResult:
    """The outcome of a simulated conversation between user and target."""

    turns: list[Turn] = field(default_factory=list)
    """Ordered list of (user_message, target_response) pairs."""

    project_dir: Path | None = None
    """The temp project directory used for this session."""

    protocol_dir: Path | None = None
    """The ``.clarity-protocol/`` directory created during the session."""

    transcript_file: Path | None = None
    """Path to the transcript .md file written by ClaritySession."""

    cost_usd: float = 0.0
    """Total cost accumulated across all target turns (when reported)."""

    stopped_early: bool = False
    """True if the user ended the conversation before hitting max_turns."""

    timed_out: bool = False
    """True if the conversation was cut short by ``timeout_seconds``."""

    duration_seconds: float = 0.0
    """Wall-clock seconds the user↔target conversation took."""

    user_llm_dialogue: list[tuple[str, str]] = field(default_factory=list)
    """Raw input/output exchange between the framework and the
    simulated user's backend.  Each entry is ``(role, content)`` from
    the user-LLM's *internal* perspective: a single ``("system", ...)``
    entry first (the persona prompt), followed by alternating
    ``("user", ...)`` (what the framework sent in) and
    ``("assistant", ...)`` (what the LLM produced).

    Useful for debugging persona drift or role-confusion failures —
    the user-LLM's own transcript shows exactly what input it saw at
    each turn and what it returned (before scrubbing or marker
    extraction).  Empty for resumed conversations: the LLM didn't
    actually run, so there's nothing to record."""

    persona_check_failed: str | None = None
    """If the turn-1 persona-adoption validator rejected the opening
    message, the judge's reasoning.  ``None`` means either the check
    passed or no validator was configured.  The fixture treats a
    non-None value as a smoke failure — the simulated user
    substituted a different persona than requested, so the rest of
    the conversation isn't worth running."""

    @property
    def transcript(self) -> str:
        """The full conversation as a single markdown string, for judging."""
        parts: list[str] = []
        for i, turn in enumerate(self.turns, 1):
            parts.append(f"## Turn {i}\n")
            parts.append(f"**User:**\n{turn.user}\n")
            parts.append(f"**Assistant:**\n{turn.target}\n")
        return "\n".join(parts)

    @property
    def turn_count(self) -> int:
        return len(self.turns)
