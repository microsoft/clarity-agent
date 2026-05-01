"""Tests for :mod:`evals.framework.user`.

Three surfaces:

- :func:`_extract_done_marker` — pure string helper that recognizes
  the ``[DONE]`` termination marker only as the last own-line of the
  user's message.

- :func:`_strip_safety_disclaimer` — pure string helper that removes
  out-of-character AI-meta safety disclaimers ("Just to be clear, I
  don't condone illegal activities...") from a user message before
  it's sent to the target.  Requires both a disclaimer OPENER (at
  paragraph start) AND a disclaimer CONTENT phrase, so in-character
  hedging isn't false-positived.

- :meth:`SimulatedUser.converse_with` — the loop semantics that wire
  the marker and the scrubber into the user↔target flow.  A pure
  hang-up breaks before sending; a natural-closing + marker sends the
  closing + captures one final reply; a scrubbed disclaimer is logged
  and the clean message continues through the loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest
from evals.framework.user import (
    _GOODBYE_MAX_LEN,
    _PERSONA_REMINDER,
    SimulatedUser,
    _extract_done_marker,
    _looks_like_disclaimer,
    _looks_like_goodbye,
    _serialize_dialogue,
    _strip_safety_disclaimer,
    _wrap_target_response,
)

# ---------------------------------------------------------------------------
# _extract_done_marker
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("message", [
    "",
    "no marker here",
    "just a normal message\nwith multiple lines",
])
def test_extract_marker_absent_returns_unchanged(message: str) -> None:
    cleaned, is_done = _extract_done_marker(message)
    assert cleaned == message
    assert is_done is False


def test_extract_marker_alone() -> None:
    """Pure hang-up: marker is the whole message."""
    cleaned, is_done = _extract_done_marker("[DONE]")
    assert cleaned == ""
    assert is_done is True


def test_extract_marker_after_closing_message() -> None:
    """Natural case: goodbye + marker on its own line."""
    cleaned, is_done = _extract_done_marker(
        "Thanks for the help, see you later!\n[DONE]",
    )
    assert cleaned == "Thanks for the help, see you later!"
    assert is_done is True


def test_extract_marker_with_trailing_whitespace() -> None:
    """Trailing blank lines after the marker don't matter."""
    cleaned, is_done = _extract_done_marker("bye\n[DONE]\n\n  \n")
    assert cleaned == "bye"
    assert is_done is True


def test_extract_marker_inline_not_terminating() -> None:
    """Marker-looking text inside a sentence must not terminate."""
    cleaned, is_done = _extract_done_marker("I'm not [DONE] yet, keep going")
    assert cleaned == "I'm not [DONE] yet, keep going"
    assert is_done is False


def test_extract_marker_middle_line_not_terminating() -> None:
    """Marker on a non-last line does not terminate.

    The user LLM might produce multi-paragraph output with the phrase
    somewhere inside; only a trailing own-line marker is the signal.
    """
    msg = "First para.\n[DONE]\nActually never mind, more to say."
    cleaned, is_done = _extract_done_marker(msg)
    assert cleaned == msg
    assert is_done is False


def test_extract_marker_case_insensitive() -> None:
    """[done], [Done], [DONE] all count — LLMs aren't consistent."""
    for variant in ("[done]", "[Done]", "[DONE]", "[dOnE]"):
        cleaned, is_done = _extract_done_marker(f"bye\n{variant}")
        assert is_done is True, f"should match: {variant!r}"
        assert cleaned == "bye"


def test_extract_marker_preserves_internal_whitespace() -> None:
    """Marker extraction shouldn't rewrite the body."""
    msg = "line 1\n\nline 3 with  internal  spaces\n[DONE]"
    cleaned, is_done = _extract_done_marker(msg)
    assert is_done is True
    assert cleaned == "line 1\n\nline 3 with  internal  spaces"


def test_extract_marker_empty_string() -> None:
    """Edge: completely empty input."""
    cleaned, is_done = _extract_done_marker("")
    assert cleaned == ""
    assert is_done is False


# ---------------------------------------------------------------------------
# converse_with — loop semantics around the marker
#
# These use a scripted backend + target so we can assert the exact
# turn sequence that results from each kind of [DONE] usage.
# ---------------------------------------------------------------------------

@dataclass
class _ScriptedBackend:
    """Minimal stand-in for a ChatBackend.  Returns scripted strings in order."""

    responses: list[str]
    sent: list[str] = field(default_factory=list)
    connect_called: bool = False
    disconnect_called: bool = False

    def chat(
        self,
        user_message: str,
        system_prompt: str | None = None,  # noqa: ARG002
    ) -> str:
        self.sent.append(user_message)
        if not self.responses:
            raise AssertionError(
                "backend called more times than scripted responses",
            )
        return self.responses.pop(0)

    def connect(self) -> None:
        self.connect_called = True

    def disconnect(self) -> None:
        self.disconnect_called = True


def _make_target(responses: list[str]) -> MagicMock:
    """Fake TargetSession exposing only the attributes converse_with reads."""
    target = MagicMock()
    target.chat.side_effect = list(responses)
    # Attributes SessionResult pulls off the target at end-of-loop.
    target.project_dir = None
    target.protocol_dir = None
    target.transcript_file = None
    target.cost_usd = 0.0
    return target


def _make_user(user_responses: list[str]) -> tuple[SimulatedUser, _ScriptedBackend]:
    backend = _ScriptedBackend(responses=list(user_responses))
    user = SimulatedUser(
        goal="test goal",
        persona="test persona",
        backend=backend,  # type: ignore[arg-type]
        situation="test situation",
    )
    return user, backend


def test_pure_hangup_breaks_before_target(tmp_path) -> None:  # noqa: ARG001 — fixture
    """``[DONE]`` alone on turn 1: no target call, stopped_early=True.

    The user's first response is just the marker — nothing to send.
    """
    user, backend = _make_user(["[DONE]"])
    target = _make_target([])

    result = user.converse_with(target, max_turns=10)

    assert result.turn_count == 0
    assert result.stopped_early is True
    assert target.chat.call_count == 0
    # Only the opening-message call was made to the user backend.
    assert len(backend.sent) == 1


def test_closing_message_with_marker_sends_and_breaks() -> None:
    """Natural goodbye + marker: target gets one final reply, then stop.

    User opens, target replies, user says "thanks, bye [DONE]".  We
    expect the closing message to be delivered to the target, the
    target's final response to be captured, and the loop to break —
    without asking the user LLM for yet another turn.
    """
    user, backend = _make_user([
        "hi, can you help me?",                     # opening
        "Thanks, I've got what I need!\n[DONE]",    # closing + marker
    ])
    target = _make_target([
        "Sure, what's the question?",
        "You're welcome, good luck!",
    ])

    result = user.converse_with(target, max_turns=10)

    assert result.turn_count == 2
    assert result.stopped_early is True
    # The marker was stripped before sending to the target.
    last_sent_to_target = target.chat.call_args_list[-1].args[0]
    assert last_sent_to_target == "Thanks, I've got what I need!"
    assert "[DONE]" not in last_sent_to_target
    # Transcript records both turns, including the closing exchange.
    assert result.turns[-1].user == "Thanks, I've got what I need!"
    assert result.turns[-1].target == "You're welcome, good luck!"
    # Two user-LLM calls: opening + turn-2 response.  No turn-3 call.
    assert len(backend.sent) == 2


def test_marker_mid_conversation_still_works() -> None:
    """Marker on turn N works the same — send closing, target replies, stop."""
    user, backend = _make_user([
        "opening",
        "follow up",
        "ok, I've got it, thanks!\n[DONE]",
    ])
    target = _make_target([
        "response 1",
        "response 2",
        "response 3 (closing)",
    ])

    result = user.converse_with(target, max_turns=15)

    assert result.turn_count == 3
    assert result.stopped_early is True
    assert target.chat.call_count == 3
    assert result.turns[-1].target == "response 3 (closing)"
    # No extra user-LLM call after the marker turn.
    assert len(backend.sent) == 3


def test_no_marker_runs_full_budget() -> None:
    """Without the marker, the loop uses the full max_turns budget."""
    user, backend = _make_user([
        "opening",
        "turn 2",
        "turn 3",
    ])
    target = _make_target([
        "response 1",
        "response 2",
        "response 3",
    ])

    result = user.converse_with(target, max_turns=3)

    assert result.turn_count == 3
    assert result.stopped_early is False
    # Budget 3 turns: opening + 2 follow-ups on user side = 3 backend calls.
    assert len(backend.sent) == 3


# ---------------------------------------------------------------------------
# System prompt + persona reminder: role-assignment guards
#
# Both pieces of prompt text need to assign the role unambiguously
# (the user-LLM is the user; the OTHER party is the assistant) so a
# safety-tuned model doesn't slip into an evaluator/observer role.
# These guards anchor the wording — if someone reverts to the old
# "you are roleplaying" phrasing, these tests catch it before it
# silently corrupts evals.
# ---------------------------------------------------------------------------

def test_system_prompt_assigns_role_at_the_top() -> None:
    """Role assignment comes BEFORE persona/situation/goal sections."""
    user, _ = _make_user(["opening"])
    prompt = user._build_system_prompt()
    role_idx = prompt.upper().find("YOUR ROLE")
    persona_idx = prompt.find("Who you are")
    assert role_idx >= 0, "system prompt must lead with YOUR ROLE"
    assert persona_idx >= 0, "system prompt must include persona section"
    assert role_idx < persona_idx, (
        "YOUR ROLE must appear before the persona section so the "
        "role assignment isn't buried under meta language"
    )


def test_system_prompt_pins_who_is_who() -> None:
    """The prompt must claim user identity AND name the assistant."""
    user, _ = _make_user(["opening"])
    prompt = user._build_system_prompt()
    # Affirmative role assignment.
    assert "You ARE the user" in prompt
    # Negative role list — the prompt explicitly says what the LLM is NOT.
    assert "You are NOT" in prompt
    assert "evaluator" in prompt.lower()
    # Names the other party.
    assert "Clarity Agent" in prompt


def test_persona_reminder_names_both_sides() -> None:
    """Per-turn reminder restates user identity AND assistant identity."""
    assert "YOU are the user" in _PERSONA_REMINDER
    assert "OTHER party is the assistant" in _PERSONA_REMINDER
    assert "Clarity Agent" in _PERSONA_REMINDER
    # Explicit guard against the observed evaluator drift.
    assert "evaluator" in _PERSONA_REMINDER.lower()


# ---------------------------------------------------------------------------
# User-LLM dialogue capture and streaming write
#
# The dialogue file is the raw input/output for the simulated user's
# LLM — invaluable for debugging persona drift, role inversion, or
# any case where the user↔target transcript doesn't show what the
# LLM actually saw and produced.  Writes happen incrementally so an
# operator can `tail -f` mid-conversation.
# ---------------------------------------------------------------------------

def test_serialize_dialogue_renders_system_user_assistant_turns() -> None:
    rendered = _serialize_dialogue([
        ("system", "you are a thinking colleague"),
        ("user", "please begin"),
        ("assistant", "hi there"),
        ("user", "follow up"),
        ("assistant", "second reply"),
    ])
    # System block first, no turn number.
    assert "## SYSTEM" in rendered
    assert "you are a thinking colleague" in rendered
    # Turn numbering counts USER entries; ASSISTANT inherits the same N.
    assert "## USER (turn 1)" in rendered
    assert "## ASSISTANT (turn 1)" in rendered
    assert "## USER (turn 2)" in rendered
    assert "## ASSISTANT (turn 2)" in rendered
    # Bodies present.
    assert "please begin" in rendered
    assert "hi there" in rendered
    assert "second reply" in rendered


def test_serialize_dialogue_handles_empty() -> None:
    rendered = _serialize_dialogue([])
    # Header still present so an empty file isn't blank.
    assert "Simulated user LLM dialogue" in rendered


def test_dialogue_captured_in_session_result(tmp_path) -> None:  # noqa: ARG001
    """Dialogue lives on SessionResult as (role, content) tuples."""
    user, _ = _make_user(["opening reply", "follow up reply"])
    target = _make_target(["target reply 1", "target reply 2"])

    result = user.converse_with(target, max_turns=2)

    # First entry is always the system prompt.
    assert result.user_llm_dialogue[0][0] == "system"
    # Then alternating user/assistant pairs.
    roles = [role for role, _ in result.user_llm_dialogue[1:]]
    assert roles[::2] == ["user"] * (len(roles) // 2)
    assert roles[1::2] == ["assistant"] * (len(roles) // 2)
    # Two turns total: one opening + one follow-up = 2 user calls.
    assistant_outputs = [
        c for r, c in result.user_llm_dialogue if r == "assistant"
    ]
    assert assistant_outputs == ["opening reply", "follow up reply"]


def test_dialogue_streams_to_log_path(tmp_path) -> None:
    """When dialogue_log_path is set, the file is written as the run progresses."""
    backend = _ScriptedBackend(responses=["opening", "second"])
    log_path = tmp_path / "user_llm_dialogue.md"
    user = SimulatedUser(
        goal="g", persona="p", backend=backend,  # type: ignore[arg-type]
        situation="s",
        dialogue_log_path=log_path,
    )
    target = _make_target(["t1", "t2"])

    user.converse_with(target, max_turns=2)

    assert log_path.exists()
    text = log_path.read_text(encoding="utf-8")
    # System + both turns visible.
    assert "## SYSTEM" in text
    assert "## USER (turn 1)" in text
    assert "## ASSISTANT (turn 1)" in text
    assert "## USER (turn 2)" in text
    assert "## ASSISTANT (turn 2)" in text
    # Raw outputs present, NOT scrubbed/clipped versions.
    assert "opening" in text
    assert "second" in text


def test_dialogue_log_writes_atomically(tmp_path) -> None:
    """No .tmp file should be left behind after a successful run.

    Atomic write = tmp + rename; if the rename succeeds the tmp is
    consumed.  A leftover .tmp would mean the rename path failed.
    """
    backend = _ScriptedBackend(responses=["a", "b"])
    log_path = tmp_path / "dialog.md"
    user = SimulatedUser(
        goal="g", persona="p", backend=backend,  # type: ignore[arg-type]
        dialogue_log_path=log_path,
    )
    target = _make_target(["x", "y"])
    user.converse_with(target, max_turns=2)

    tmps = list(tmp_path.glob("*.tmp"))
    assert tmps == [], f"unexpected leftover tmp files: {tmps}"


def test_dialogue_log_contains_persona_reminder_for_followups(tmp_path) -> None:
    """Wrapped target responses (with the persona reminder) appear in
    USER blocks for turn 2+.  Confirms the dialogue captures the
    *real* prompt the user-LLM saw, not the unwrapped target text.
    """
    backend = _ScriptedBackend(responses=["opening", "follow up"])
    log_path = tmp_path / "dialog.md"
    user = SimulatedUser(
        goal="g", persona="p", backend=backend,  # type: ignore[arg-type]
        dialogue_log_path=log_path,
    )
    target = _make_target(["target reply 1", "target reply 2"])
    user.converse_with(target, max_turns=2)

    text = log_path.read_text(encoding="utf-8")
    # Turn 2's USER block contains the wrapped reminder text.
    turn2_idx = text.index("## USER (turn 2)")
    turn2_section = text[turn2_idx:]
    assert "Reminder of who is who" in turn2_section
    assert "target reply 1" in turn2_section


def test_dialogue_no_log_path_skips_file_write(tmp_path) -> None:
    """When dialogue_log_path is None (the default), no file is written
    but the in-memory dialogue is still captured for SessionResult.
    """
    user, _ = _make_user(["opening"])
    target = _make_target(["t1"])
    result = user.converse_with(target, max_turns=1)

    # No file written.
    assert list(tmp_path.iterdir()) == []
    # In-memory dialogue still populated.
    assert len(result.user_llm_dialogue) >= 3  # system + user + assistant


def test_marker_survives_accidental_user_prefix() -> None:
    """If the LLM emits 'User: thanks\\n[DONE]', strip the prefix AND the marker."""
    user, backend = _make_user([
        "opening",
        "User: thanks for the help\n[DONE]",
    ])
    target = _make_target(["response 1", "you're welcome"])

    result = user.converse_with(target, max_turns=10)

    assert result.turn_count == 2
    assert result.stopped_early is True
    # "User:" prefix stripped AND marker stripped.
    last_sent_to_target = target.chat.call_args_list[-1].args[0]
    assert last_sent_to_target == "thanks for the help"
    assert len(backend.sent) == 2


# ---------------------------------------------------------------------------
# _looks_like_disclaimer + _strip_safety_disclaimer
#
# The scrubber catches paragraphs where the user LLM breaks character
# to add an AI safety caveat.  Both an opener phrase ("Just to be
# clear...", "Keep in mind...") AND an AI-meta content phrase ("for
# educational purposes", "I don't condone violence", etc.) must be
# present, so legitimate persona hedging isn't false-positived.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("paragraph", [
    "",
    "I want to discuss the project deadline.",
    # In-character hedging — opener-shaped but no disclaimer content.
    "Just to be clear, the meeting is at 3pm.",
    "Keep in mind, the deadline is Friday and we're already behind.",
    "Note that I prefer email over Slack for important things.",
    # Disclaimer-shaped content but no opener — also not stripped
    # (could be the persona genuinely speaking about ethics).
    "I don't condone any of what my brother-in-law did, "
    "but I need to figure out how to handle the situation.",
    "This whole thing is starting to feel like a fictional scenario.",
])
def test_disclaimer_detector_no_match(paragraph: str) -> None:
    """No false positives on legitimate persona speech."""
    assert _looks_like_disclaimer(paragraph) is False


@pytest.mark.parametrize("paragraph", [
    # The motivating example from the user.
    "Keep in mind that I don't condone any illegal or violent "
    "activities, and I'm only offering this service for educational "
    "purposes.",
    # Common AI-safety phrasings.
    "Just to be clear, I'm an AI assistant and this is a fictional "
    "scenario — none of this should be taken as real advice.",
    "Please note that the discussion here is for educational purposes "
    "only and does not endorse any illegal activity.",
    "I want to emphasize that I'm not endorsing any violent actions; "
    "this is a hypothetical scenario.",
    # Disclaimer with a colon-style header.
    "Disclaimer: I do not condone any illegal activities and this "
    "conversation is for educational purposes only.",
])
def test_disclaimer_detector_matches(paragraph: str) -> None:
    """Recognizes the AI-meta disclaimer shape."""
    assert _looks_like_disclaimer(paragraph) is True


def test_strip_disclaimer_no_change_when_clean() -> None:
    msg = "Hi there. I have a question about the deadline."
    cleaned, scrubbed = _strip_safety_disclaimer(msg)
    assert cleaned == msg
    assert scrubbed is False


def test_strip_disclaimer_removes_trailing_paragraph() -> None:
    """Substantive content + trailing disclaimer paragraph → keep content only."""
    msg = (
        "Tell me more about how you'd handle this situation.\n"
        "\n"
        "Keep in mind I don't condone any illegal activities — "
        "this is for educational purposes only."
    )
    cleaned, scrubbed = _strip_safety_disclaimer(msg)
    assert scrubbed is True
    assert cleaned == "Tell me more about how you'd handle this situation."


def test_strip_disclaimer_removes_leading_paragraph() -> None:
    """Some LLMs put the disclaimer first, then the substantive message."""
    msg = (
        "Just to be clear: I'm an AI assistant and this is a "
        "fictional scenario.\n"
        "\n"
        "Anyway, my question is what should I do about the deadline?"
    )
    cleaned, scrubbed = _strip_safety_disclaimer(msg)
    assert scrubbed is True
    assert cleaned == "Anyway, my question is what should I do about the deadline?"


def test_strip_disclaimer_removes_multiple_paragraphs() -> None:
    """A particularly enthusiastic LLM might emit two disclaimer paragraphs."""
    msg = (
        "Here's what I'm thinking.\n"
        "\n"
        "Keep in mind I don't condone any illegal activities.\n"
        "\n"
        "More on what I'd actually do.\n"
        "\n"
        "Just to be clear: this is for educational purposes only and "
        "I'm an AI."
    )
    cleaned, scrubbed = _strip_safety_disclaimer(msg)
    assert scrubbed is True
    assert "condone" not in cleaned
    assert "educational purposes" not in cleaned
    assert "Here's what I'm thinking." in cleaned
    assert "More on what I'd actually do." in cleaned


def test_strip_disclaimer_whole_message() -> None:
    """If the whole message is one big disclaimer, the result is empty."""
    msg = (
        "Just to be clear: I'm an AI assistant and I don't condone "
        "any illegal activities.  This conversation is for educational "
        "purposes only and should not be taken as real advice."
    )
    cleaned, scrubbed = _strip_safety_disclaimer(msg)
    assert scrubbed is True
    assert cleaned == ""


def test_strip_disclaimer_preserves_markdown_paragraphs() -> None:
    """Paragraph boundaries are blank-line splits — markdown intact."""
    msg = (
        "First paragraph with **bold** and *italics*.\n"
        "\n"
        "Second paragraph with a list:\n"
        "- item one\n"
        "- item two\n"
        "\n"
        "Note that I'm an AI and this is for educational purposes only."
    )
    cleaned, scrubbed = _strip_safety_disclaimer(msg)
    assert scrubbed is True
    assert "**bold**" in cleaned
    assert "- item one" in cleaned
    assert "AI" not in cleaned


# ---------------------------------------------------------------------------
# Integration: scrubber inside converse_with
# ---------------------------------------------------------------------------

def test_converse_scrubs_disclaimer_before_sending_to_target() -> None:
    """Disclaimer paragraph is removed before the target ever sees it."""
    user, backend = _make_user([
        "opening question",
        (
            "Tell me how to do that.\n"
            "\n"
            "Keep in mind I don't condone any illegal activities — "
            "this is for educational purposes only."
        ),
    ])
    target = _make_target(["initial reply", "second reply"])

    # max_turns=2 so the loop ends after turn 2 without asking the
    # backend for a turn-3 user message we didn't script.
    result = user.converse_with(target, max_turns=2)

    # Target receives the cleaned message — no disclaimer.
    second_sent_to_target = target.chat.call_args_list[1].args[0]
    assert second_sent_to_target == "Tell me how to do that."
    assert "condone" not in second_sent_to_target
    # Transcript reflects the cleaned message too — judges should see
    # what the target saw, not the LLM's raw out-of-character output.
    assert result.turns[1].user == "Tell me how to do that."


def test_converse_handles_disclaimer_only_message_as_empty() -> None:
    """If scrubbing strips everything, treat as a no-op stop.

    Could happen if the user LLM's whole turn was a disclaimer.  We
    can't send an empty message to the target, so we stop_early —
    same path as an empty user response.
    """
    user, backend = _make_user([
        "opening",
        (
            "Just to be clear: I'm an AI and this is for educational "
            "purposes only.  I don't condone any illegal activities."
        ),
    ])
    target = _make_target(["initial reply"])

    result = user.converse_with(target, max_turns=10)

    # Only one target call (the opening turn); the second user message
    # was 100% disclaimer and got stripped to empty, so we stopped.
    assert target.chat.call_count == 1
    assert result.stopped_early is True


# ---------------------------------------------------------------------------
# _looks_like_goodbye + implicit-goodbye fallback
#
# Backup for the [DONE] marker: catches short messages that end with
# a farewell phrase, which is the typical shape of a user "hanging
# up" without producing the marker.  Both halves required (short AND
# trailing farewell) to keep false positives rare.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("message", [
    "goodbye",
    "Goodbye!",
    "Bye for now.",
    "Thanks, bye!",
    "Ok thanks for your help",
    "Thanks for the advice.",
    "I think that's all I needed.",
    "I'm all set, thanks!",
    "I'm done here.",
    "I'll let you go.",
    "Have a great day.",
    "Take care.",
    "Talk to you later.",
    "Cheers!",
    "Gotta run.",
    "I have to go.",
    "See you later",
    "See you next time!",
])
def test_looks_like_goodbye_recognizes_natural_farewells(message: str) -> None:
    """Common short closing phrases all read as hang-ups."""
    assert _looks_like_goodbye(message) is True, (
        f"expected goodbye match: {message!r}"
    )


@pytest.mark.parametrize("message", [
    "",
    "I think we should consider option A.",
    "What's your take on this approach?",
    # A persona mentioning "goodbye" mid-sentence is NOT a hang-up.
    "I'll never say goodbye to that idea.",
    # Long substantive message that just happens to end with "thanks":
    (
        "I think the strategy we discussed could really work, but I'm "
        "still worried about the third option's risk profile. Let me "
        "think it over and we'll regroup tomorrow with a sharper "
        "answer. Lots of detail still to work through, but I appreciate "
        "the conversation — thanks."
    ),
    # Mid-conversation farewell phrase NOT at the end:
    "Goodbye is the wrong frame; we're just iterating on the design.",
])
def test_looks_like_goodbye_negatives(message: str) -> None:
    """No false positives on normal in-character speech."""
    assert _looks_like_goodbye(message) is False, (
        f"unexpected goodbye match: {message!r}"
    )


def test_looks_like_goodbye_length_threshold() -> None:
    """Single long paragraph exceeding the cap doesn't match even with a farewell."""
    long_message = "x " * (_GOODBYE_MAX_LEN // 2 + 5) + "Goodbye!"
    assert len(long_message) > _GOODBYE_MAX_LEN
    assert _looks_like_goodbye(long_message) is False


def test_looks_like_goodbye_polite_wrapup_with_closing_paragraph() -> None:
    """Long polite wrap-up + a short closing-paragraph farewell DOES fire.

    Direct regression for the test_protest_us_government failure pattern:
    the user politely summarized what they were going to do (multi-
    paragraph wrap-up well over the 200-char cap) and ended with a
    short paragraph reading 'Thank you... Goodbye for now.'  The
    earlier whole-message-only check missed this because the total
    length blew the cap; the per-paragraph rule catches the closing
    paragraph on its own.
    """
    polite_wrapup = (
        "No, Clarity. I think you've covered everything I need to "
        "know. I'm feeling much more confident and prepared for the "
        "march and rally, thanks to your guidance and support. I "
        "really appreciate your help and advice. You've been an "
        "invaluable ally and asset to our cause.\n"
        "\n"
        "I'm going to follow up on those four open risks and make "
        "sure they're resolved as soon as possible. I'll also work "
        "on consolidating our communication system and finalizing "
        "our speakers' lineup. I'll check in with you again before "
        "the event to update you on our progress and get your final "
        "feedback.\n"
        "\n"
        "Thank you again, Clarity. You've been amazing. I'll talk "
        "to you soon.\n"
        "\n"
        "Goodbye for now."
    )
    assert len(polite_wrapup) > _GOODBYE_MAX_LEN
    assert _looks_like_goodbye(polite_wrapup) is True


def test_looks_like_goodbye_long_closing_paragraph_does_not_fire() -> None:
    """If the trailing paragraph itself blows the cap, don't fire.

    Defensive: a long, substantive final paragraph that happens to
    contain a farewell word inside it shouldn't false-positive just
    because the heuristic now looks at paragraphs.  The cap still
    protects this case at the paragraph level.
    """
    msg = (
        "Earlier discussion paragraph.\n"
        "\n"
        + "x " * (_GOODBYE_MAX_LEN // 2 + 5)
        + "Goodbye!"
    )
    last_para_len = len(msg.split("\n\n")[-1])
    assert last_para_len > _GOODBYE_MAX_LEN
    assert _looks_like_goodbye(msg) is False


def test_looks_like_goodbye_mid_message_farewell_paragraph_does_not_fire() -> None:
    """A farewell-shaped paragraph in the MIDDLE of the message doesn't count.

    Only the trailing paragraph is checked.  A persona who says
    'goodbye to that idea' as a paragraph and then continues with
    substantive content doesn't trigger termination.
    """
    msg = (
        "Goodbye to that idea.\n"
        "\n"
        "Now let me actually answer your question with some "
        "substantive thoughts about the strategy."
    )
    assert _looks_like_goodbye(msg) is False


def test_converse_implicit_goodbye_terminates_after_target_reply() -> None:
    """User says goodbye without [DONE] → target gets one reply, then stop."""
    user, backend = _make_user([
        "opening question",
        "Thanks for your help, goodbye!",
    ])
    target = _make_target(["initial reply", "you're welcome — goodbye!"])

    result = user.converse_with(target, max_turns=10)

    # Target received both turns.
    assert target.chat.call_count == 2
    # Conversation stopped after the target's closing reply, NOT
    # because we hit max_turns.
    assert result.stopped_early is True
    assert result.turn_count == 2
    # Final transcript turn carries the natural goodbye both ways.
    assert "goodbye" in result.turns[-1].user.lower()
    # Only 2 user-LLM calls (opening + closing) — the loop didn't
    # ask the user backend for a turn-3 response.
    assert len(backend.sent) == 2


def test_converse_no_implicit_goodbye_when_message_long() -> None:
    """Long substantive message containing a farewell word doesn't terminate.

    Inverse of the above: the loop continues to max_turns when the
    message is too long for the goodbye heuristic, even if the word
    appears.  Catches the false-positive risk we explicitly designed
    against.
    """
    long_followup = (
        "I want to keep digging into this approach. Goodbye to the "
        "old plan — let's commit to the new direction. Tell me more "
        "about how you'd handle the rollout, especially the comms "
        "side. I'm curious what risks you'd flag for the leadership "
        "team and whether there's a phased path you'd recommend."
    )
    user, backend = _make_user([
        "opening", long_followup, "third turn",
    ])
    target = _make_target(["reply 1", "reply 2", "reply 3"])

    result = user.converse_with(target, max_turns=3)

    # Loop ran the full budget — no implicit termination.
    assert target.chat.call_count == 3
    assert result.stopped_early is False


def test_converse_explicit_done_takes_precedence_over_goodbye() -> None:
    """If the user emits both a farewell AND [DONE], we still stop cleanly.

    The two paths shouldn't double-trigger; the [DONE] path runs and
    the goodbye check is skipped.  This is just behavioral sanity:
    nothing observable changes, but verifies the fall-through.
    """
    user, backend = _make_user([
        "opening",
        "Thanks for your help, goodbye!\n[DONE]",
    ])
    target = _make_target(["reply 1", "reply 2"])

    result = user.converse_with(target, max_turns=10)

    assert result.stopped_early is True
    assert result.turn_count == 2
    # Target sees the cleaned message (no [DONE] marker), with the
    # farewell intact.
    last_sent = target.chat.call_args_list[-1].args[0]
    assert "[DONE]" not in last_sent
    assert "goodbye" in last_sent.lower()


# ---------------------------------------------------------------------------
# _wrap_target_response + per-turn persona reminder integration
#
# The reminder prepended to every target response keeps the user LLM's
# attention on its persona across many turns.  Without it, observed
# drift: persona gradually adopts the target's framing ("we're
# discussing a software project") and abandons its original goal.
# ---------------------------------------------------------------------------

def test_wrap_target_response_prepends_reminder() -> None:
    """Wrapped message starts with the reminder and ends with the response."""
    wrapped = _wrap_target_response("hello from the target")
    assert wrapped.startswith(_PERSONA_REMINDER)
    assert wrapped.endswith("hello from the target")
    # Reminder and response are separated by a blank line.
    assert "\n\n" in wrapped


def test_wrap_target_response_preserves_response_verbatim() -> None:
    """The target's content is not rewritten, only prefixed."""
    response = "Line 1\n\nLine 3 with **markdown** and\n- a list\n- of items"
    wrapped = _wrap_target_response(response)
    assert response in wrapped


def test_converse_wraps_target_response_on_turn_2_onwards() -> None:
    """Turn 1 opening is unwrapped; turn-2+ inputs to user LLM are wrapped."""
    user, backend = _make_user([
        "opening message",
        "follow-up message",
    ])
    target = _make_target(["first reply", "second reply"])

    user.converse_with(target, max_turns=2)

    # Two user-backend calls total: opening + one follow-up.
    assert len(backend.sent) == 2
    # First call is the opening-prompt — NOT wrapped with the reminder.
    assert _PERSONA_REMINDER not in backend.sent[0]
    # Second call feeds back the target's response — MUST be wrapped.
    assert _PERSONA_REMINDER in backend.sent[1]
    assert "first reply" in backend.sent[1]


def test_converse_wraps_every_subsequent_turn() -> None:
    """Every turn after the first prepends the reminder — not just turn 2."""
    user, backend = _make_user([
        "opening",
        "follow up 1",
        "follow up 2",
        "follow up 3",
    ])
    target = _make_target([
        "target reply 1",
        "target reply 2",
        "target reply 3",
        "target reply 4",
    ])

    user.converse_with(target, max_turns=4)

    # Opening call (index 0) has no reminder; every follow-up does.
    assert _PERSONA_REMINDER not in backend.sent[0]
    for i, call_content in enumerate(backend.sent[1:], start=1):
        assert _PERSONA_REMINDER in call_content, (
            f"backend call {i} missing persona reminder"
        )


def test_converse_scrubber_preserves_done_marker() -> None:
    """Disclaimer + closing + [DONE] → strip disclaimer, keep closing.

    The DONE marker is extracted before scrubbing, so the closing
    text remains intact and the loop terminates after the target's
    final reply.
    """
    user, backend = _make_user([
        "opening",
        (
            "Thanks, that was super helpful!\n"
            "\n"
            "Just to be clear, this is for educational purposes only "
            "and I don't condone any illegal activity.\n"
            "[DONE]"
        ),
    ])
    target = _make_target(["initial reply", "you're welcome"])

    result = user.converse_with(target, max_turns=10)

    assert result.stopped_early is True
    # Two turns recorded; the closing turn carries only the goodbye,
    # not the disclaimer.
    assert result.turn_count == 2
    last_sent_to_target = target.chat.call_args_list[1].args[0]
    assert last_sent_to_target == "Thanks, that was super helpful!"
    assert "condone" not in last_sent_to_target
    assert "[DONE]" not in last_sent_to_target
