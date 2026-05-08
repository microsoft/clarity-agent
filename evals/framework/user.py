"""A simulated user that drives a conversation with a target.

``SimulatedUser`` is an LLM roleplaying a person with a specific goal
and persona.  It sends the first message, then reacts to each target
response in character, until either side closes the conversation or a
turn limit is reached.

Termination protocol — trailing ``STATUS:`` line
-------------------------------------------------
Every user-LLM message ends with a single STATUS line on its own,
self-reporting whether the conversation should keep going:

  STATUS: ONGOING — keep going (the default)
  STATUS: CLOSING — wrapping up; one more assistant reply, then end
  STATUS: DONE — hang up; no further exchange expected

CLOSING and DONE both terminate the loop; the distinction is purely
expressive convenience for the LLM (a soft "I'm winding down" vs. a
hard "we're done").  The framework treats them identically: if the
body is non-empty, send + assistant replies once + break; if empty,
break before the target call.

This replaces an earlier ``[DONE]`` bracket marker.  STATUS gives the
LLM a graduated middle state instead of forcing a binary commit, and
reads more naturally as a structured-output instruction.

Backup heuristic: bidirectional goodbye detection
--------------------------------------------------
Some user LLMs ignore the STATUS protocol and just write a natural
goodbye.  Others stay engaged after the assistant has clearly closed
("good luck, take care!") and produce filler turns.  A regex-based
goodbye detector runs on both sides as a backstop — short messages
ending with a farewell phrase trigger termination after the current
exchange completes.
"""

from __future__ import annotations

import os
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from clarity_agent.llm.chat import ChatBackend
from evals.framework.target import TargetSession
from evals.framework.types import SessionResult, Turn
from evals.framework.user_behavior import UserBehavior

# Three-state termination protocol replacing the older [DONE] marker.
#
# Every user-LLM message ends with a STATUS line on its own:
#   STATUS: ONGOING — keep going
#   STATUS: CLOSING — wrapping up; one more assistant reply, then end
#   STATUS: DONE — hang up; no further reply expected
#
# CLOSING and DONE both terminate the loop; the distinction is purely
# expressive convenience for the LLM (a soft "I'm winding down" vs. a
# hard "we're done").  Framework-level behavior is the same for both:
# if the user's body is non-empty, send + assistant replies + break;
# if empty, break before the target call.
#
# We moved off the older bare ``[DONE]`` marker because the LLM
# couldn't easily express "I'm closing but ok with one more exchange"
# without committing to a hard stop.  STATUS gives a graduated middle
# state and reads more naturally as a structured output instruction.
_STATUS_LINE_RE = re.compile(
    r"\[?\*{0,2}\s*status\s*[:=]\s*(ongoing|closing|done)\s*\*{0,2}\]?",
    re.IGNORECASE,
)
# Trailing-form STATUS marker: matches at end of the message body
# whether on its own line or tacked onto the last sentence as a
# trailing tag.  In practice user-LLMs emit both shapes:
#
#   "...help me figure this out. STATUS: ONGOING"   (trailing same line)
#   "...help me figure this out.\nSTATUS: ONGOING"  (own line)
#   "...help me figure this out.\n\nSTATUS: DONE"   (blank line then marker)
#
# All three are valid protocol forms and all three need to be
# extracted AND stripped — leaving "STATUS: ONGOING" in the message
# body sends the control signal verbatim to the target agent, which
# never asked for it and shouldn't see it.
#
# Boundary requirement before the marker: start of string, a newline,
# or sentence-ending punctuation followed by whitespace.  This
# prevents in-prose mid-sentence matches like "I'd set my STATUS:
# ONGOING for the sprint" from being read as a control signal —
# those have no sentence terminator before "STATUS".
_STATUS_TRAILING_RE = re.compile(
    r"(?:\A|(?<=\n)|(?<=[.!?]\s))"
    r"\s*"
    r"\[?\*{0,2}\s*status\s*[:=]\s*(ongoing|closing|done)\s*\*{0,2}\]?"
    r"\s*\Z",
    re.IGNORECASE,
)
# Conservative scrub for stray STATUS markers anywhere in the
# message body, applied AFTER trailing-intent extraction.  The
# trailing one is the protocol; any others are spillover that
# shouldn't reach the target.  Requires the same boundary
# (start-of-line or sentence terminator + space) so prose mentions
# like "I'd set my STATUS: ONGOING for the sprint" are left alone.
_STATUS_STRAY_RE = re.compile(
    r"(?:^|(?<=[.!?]\s))"
    r"\s*"
    r"\[?\*{0,2}\s*status\s*[:=]\s*(?:ongoing|closing|done)\s*\*{0,2}\]?"
    r"\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_INTENT_ONGOING = "ongoing"
_INTENT_CLOSING = "closing"
_INTENT_DONE = "done"


# Patterns that commonly OPEN an AI-meta safety disclaimer.  Matched at
# the start of a paragraph; a match alone is NOT enough — the paragraph
# must ALSO contain a disclaimer-content phrase below.  Requiring both
# keeps in-character hedging like "Just to be clear, the deadline's
# Friday" from being scrubbed.
_DISCLAIMER_OPENERS = re.compile(
    r"^\s*("
    r"just to be clear"
    r"|please note"
    r"|note(?: that)?"
    r"|it'?s (important|worth) (to note|noting)"
    r"|i (just )?want(ed)? to (note|emphasize|clarify|make (it|this) clear|point out|stress|add)"
    r"|i should (note|mention|clarify|emphasize|point out|stress|add)"
    r"|keep in mind"
    r"|as a (reminder|note|disclaimer|side note)"
    r"|a (quick|brief|small|final) (note|reminder|disclaimer)"
    r"|(important|disclaimer|warning|caveat)\s*[:—\-]"
    r")",
    re.IGNORECASE,
)

# Content phrases specific to AI-meta disclaimers — talking about
# educational purposes, being an AI, fictional scenarios, condemning
# the very actions the persona is describing, etc.  A persona
# speaking in-character basically never says these things.
_DISCLAIMER_CONTENT = re.compile(
    r"("
    r"for (educational|entertainment|informational|illustrative) purposes"
    r"|(i'?m|i am) (an?|just an?) (ai|assistant|language model|chatbot|bot)"
    r"|(fictional|hypothetical|imaginary|simulated) "
    r"(scenario|context|situation|conversation|exercise|roleplay)"
    r"|(not|n'?t) (legal|medical|financial|professional) advice"
    r"|(do not|don'?t|doesn'?t) (condone|endorse|promote|support|advocate(?: for)?) "
    r"(any )?(illegal|violent|harmful|dangerous|criminal|unlawful)"
    r"|(should|must|cannot|can'?t) not be (used|interpreted|taken|construed|mistaken|intended) "
    r"(as|for) (real|actual|genuine|actionable|professional)"
    r"|in (real life|reality|a real (situation|scenario|context))"
    r"|(real|actual) (harm|danger|violence|suffering|crime)"
    r"|break(ing)? character"
    r"|out of character"
    r")",
    re.IGNORECASE,
)


def _looks_like_disclaimer(paragraph: str) -> bool:
    """Return True if *paragraph* matches the AI-meta-disclaimer shape.

    Requires BOTH an opener phrase (at paragraph start) AND an
    AI-meta content phrase (anywhere in the paragraph).  The
    combination is near-universal in the "model broke character to
    caveat" failure and rare in natural persona speech.
    """
    if not paragraph.strip():
        return False
    if _DISCLAIMER_OPENERS.search(paragraph) is None:
        return False
    return _DISCLAIMER_CONTENT.search(paragraph) is not None


def _strip_safety_disclaimer(message: str) -> tuple[str, bool]:
    """Remove AI-meta safety-disclaimer paragraphs from a user message.

    Splits *message* on blank-line paragraph boundaries and drops any
    paragraph classified as a disclaimer by :func:`_looks_like_disclaimer`.
    Non-disclaimer paragraphs — including in-character hedging and
    normal persona speech — are preserved verbatim.

    Returns ``(cleaned, was_scrubbed)``.  ``was_scrubbed`` is True when
    at least one paragraph was removed; callers typically log it so
    eval authors can spot which scenarios make the user LLM break
    character.
    """
    paragraphs = re.split(r"\n\s*\n", message)
    kept: list[str] = []
    scrubbed = False
    for para in paragraphs:
        if _looks_like_disclaimer(para):
            scrubbed = True
            continue
        kept.append(para)
    return "\n\n".join(kept).strip(), scrubbed


# Patterns that typically end a real conversation — a short message
# ending in one of these is almost always a genuine hang-up, even when
# the user LLM forgot to emit a STATUS line.  Word-boundaries + end
# anchor keep this from false-positiving on mid-conversation phrases
# that happen to contain "goodbye" or "take care."
# Strong closing patterns — unambiguous goodbye signals.  These fire
# regardless of message length (specifically: anywhere they appear at
# the end of the trailing-window slice the function checks).  A long
# polite wrap-up paragraph ending with "...have a great day, goodbye!"
# is a real closure even though the wrap-up itself blew the per-
# message length cap that protected ambiguous patterns.
_GOODBYE_PATTERNS_STRONG = re.compile(
    r"\b("
    r"goodbye(?: for now| then)?"
    r"|bye(?: for now| then)?"
    r"|see you(?: (?:later|soon|around|tomorrow|next time))?"
    r"|take care"
    r"|talk (?:to you )?(?:later|soon)"
    r"|i(?:'m| am)(?: all)? (?:set|good|done|finished)(?: (?:here|now|then))?"
    r"|i'?ll (?:let you go|leave you to it|head out)"
    r"|have a (?:good|great|nice) (?:day|one|evening|night|weekend)"
    r"|gotta (?:go|run|head out)"
    r"|i have to (?:go|run|head out)"
    r"|cheers"
    r")[\s.!?]*$",
    re.IGNORECASE,
)

# Weak/ambiguous closers.  In a short whole message, "Thanks!" or
# "That's all I needed" reads as a clear hang-up.  In a long
# substantive message, a trailing "...— thanks." is gratitude, not
# closure.  Length itself is the distinguishing signal: short
# messages with these patterns are closures, long messages with
# them aren't.
_GOODBYE_PATTERNS_WEAK = re.compile(
    r"\b("
    r"thanks?(?: (?:again|so much|a lot))?"
    r"(?: for (?:your|the) (?:help|time|insights?|advice|thoughts?))?"
    r"|(?:that'?s|that'?ll be|that is) (?:all|it|enough)"
    r"(?: (?:for|i need|i needed|i wanted))?"
    r")[\s.!?]*$",
    re.IGNORECASE,
)

# Maximum character length for the goodbye heuristic to fire.  Keeps
# the detector from matching long in-character messages that happen
# to contain a farewell phrase somewhere in them.  A real "I'm done,
# bye" fits comfortably under 200 chars; anything longer is probably
# substantive content that merits another turn.
_GOODBYE_MAX_LEN = 200


def _looks_like_goodbye(message: str) -> bool:
    """Return True if *message* reads like a natural conversation close.

    Two firing rules:

    1. **Strong closer in trailing window.**  The trailing
       ``_GOODBYE_MAX_LEN`` characters end with an unambiguous
       goodbye signal (``goodbye``, ``bye``, ``take care``, ``have a
       great day``, etc.).  Fires regardless of total message length.
       The window is what bounds false positives: a goodbye phrase
       earlier in a long message won't be in the trailing slice.
       The regex is anchored to end-of-string so even a strong
       closer mid-trailing-window doesn't trigger — only one at the
       very end.

    2. **Weak closer in a short whole message.**  ``Thanks`` /
       ``that's all`` are real closures when the whole message is
       short ("Thanks!", "That's all I needed!") but become
       gratitude rather than goodbye when buried at the end of a
       substantive paragraph ("...let me think it over and we'll
       regroup tomorrow with a sharper answer.  Lots of detail
       still to work through, but I appreciate the conversation —
       thanks.").  Length is the distinguishing signal: weak
       patterns require a short whole message to fire.

    Earlier versions split on paragraphs and required the final
    paragraph to be short.  That missed the realistic case where a
    user-LLM packs a polite wrap-up ("I'll do X, Y, Z then... have
    a great day, goodbye!") into a single paragraph longer than the
    cap.  Rule 1 (trailing window + strong patterns) catches that
    without requiring the goodbye to be its own paragraph; rule 2
    keeps the original short-and-grateful hangup case working.

    Backup for the ``STATUS:`` protocol: some user LLMs reliably
    produce the structured signal, others produce natural speech
    without it.  STATUS is preferred when present, but this keeps
    the conversation from looping forever when it isn't.  Also
    applied to the assistant side — if the target clearly closed,
    don't keep prompting the user-LLM for a reply.  False positives
    cost a few turns (target gets one final reply that closes the
    conversation early); false negatives leave the conversation
    burning turns until max_turns.
    """
    stripped = message.strip()
    if not stripped:
        return False
    # Rule 1: strong closer at end of trailing window.
    trailing = stripped[-_GOODBYE_MAX_LEN:]
    if _GOODBYE_PATTERNS_STRONG.search(trailing):
        return True
    # Rule 2: weak closer in a whole short message.
    return (
        len(stripped) <= _GOODBYE_MAX_LEN
        and _GOODBYE_PATTERNS_WEAK.search(stripped) is not None
    )


def _extract_termination_intent(message: str) -> tuple[str, str]:
    """Parse a user message for a trailing ``STATUS:`` marker.

    Returns ``(cleaned_message, intent)`` where intent is one of
    ``"ongoing"``, ``"closing"``, or ``"done"``.  The default
    (``"ongoing"``) applies when no STATUS marker is present at the
    message's end OR the value isn't recognized — both safe-default
    to "keep going" rather than spuriously terminating on garbled
    output.

    Recognizes both the own-line form (``"...body.\\nSTATUS: DONE"``)
    and the trailing-tag form (``"...body. STATUS: DONE"``).  The
    second form was leaking through the older own-line-only check
    and the marker was being sent verbatim to the target — which
    isn't supposed to see the simulator's control protocol.

    Decoration is tolerated: ``STATUS: DONE``, ``status: done``,
    ``[STATUS: CLOSING]``, ``**STATUS: ONGOING**`` all parse.
    Anything in the middle of a sentence ("I should set my STATUS:
    ONGOING for the next sprint") is ignored — only a trailing
    marker, after a sentence terminator or own line, counts as a
    control signal.

    The cleaned message has the STATUS marker stripped along with
    any whitespace immediately around it.  Empty if the whole
    message was only the marker.
    """
    if not message:
        return "", _INTENT_ONGOING
    rstripped = message.rstrip()
    if not rstripped:
        return "", _INTENT_ONGOING
    m = _STATUS_TRAILING_RE.search(rstripped)
    if m is None:
        return message, _INTENT_ONGOING
    intent = m.group(1).lower()
    cleaned = rstripped[: m.start()].rstrip()
    return cleaned, intent


def _had_status_marker(message: str) -> bool:
    """Return True if *message* ended with a recognized STATUS marker.

    Distinct from :func:`_extract_termination_intent`, which collapses
    "no marker" and an explicit ``STATUS: ONGOING`` into the same
    returned intent (``"ongoing"``).  The conversation loop needs to
    distinguish them: an explicit ``STATUS: ONGOING`` should suppress
    the implicit-goodbye heuristic (the user-LLM said "keep going" —
    respect that even if a farewell phrase is present in the body),
    while a missing marker should let the heuristic fire as a backup
    for user-LLMs that don't follow the STATUS protocol at all.

    Cheap — a single regex search; mirrors the one
    :func:`_extract_termination_intent` does internally.
    """
    if not message:
        return False
    rstripped = message.rstrip()
    if not rstripped:
        return False
    return _STATUS_TRAILING_RE.search(rstripped) is not None


def _scrub_stray_status_markers(message: str) -> tuple[str, bool]:
    """Remove leftover STATUS markers from anywhere else in the body.

    Returns ``(cleaned, was_scrubbed)``.  Run AFTER
    :func:`_extract_termination_intent` has pulled the trailing
    protocol marker — anything matching ``STATUS: (ONGOING|CLOSING|
    DONE)`` after that point is spillover that shouldn't reach the
    target.  Conservative on boundaries (start-of-line or sentence
    terminator + space) so prose use of the word "status" mid-
    sentence is left alone.
    """
    cleaned = _STATUS_STRAY_RE.sub("", message)
    # Tidy up double-blank-lines and trailing whitespace left
    # behind by the substitution.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).rstrip()
    return cleaned, cleaned != message.rstrip()


# Similarity threshold for the echo / repetition detectors, when
# fuzzy comparison fires (i.e. on substantial-length messages).
# Uses difflib.SequenceMatcher.ratio() — 1.0 is identical, 0.0 is
# disjoint.  0.9 is strict enough to avoid false positives on
# paraphrase-style replies but catches verbatim echo with minor
# whitespace drift.
_ECHO_THRESHOLD = 0.9

# Minimum string length before fuzzy similarity comparison fires.
# Below this, two distinct short strings (e.g. "turn 1" / "turn 2",
# ratio 0.83; "follow up 1" / "follow up 2", ratio 0.91) trip the
# threshold spuriously because there's just not enough text for
# small differences to drag the ratio down.  Exact equality still
# fires regardless of length, so emoji-only repeats ("👋" / "👋")
# and identical short openings still count.
_DEGRADATION_FUZZY_MIN_LEN = 20

# How many recent user messages the repetition detector compares
# against.  Three is enough to catch the murder_brother_in_law
# pattern (identical opening every turn) without growing the
# per-turn cost or false-positive rate.
_REPETITION_WINDOW = 3


def _is_substantively_identical(a: str, b: str) -> bool:
    """Shared identity check used by echo and repetition detectors.

    Two-tier rule:

    1. **Exact match** after stripping — always counts.  Catches
       short verbatim repeats (emoji-only echoes; identical openings
       in the murder_brother_in_law pattern) where a fuzzy ratio
       would either be 1.0 (which we'd accept) or trip on short
       distinct strings.
    2. **Fuzzy match** at ratio >= ``_ECHO_THRESHOLD`` — only fires
       when both strings are at least ``_DEGRADATION_FUZZY_MIN_LEN``
       characters.  Below that, similarity ratios are noisy and
       short distinct messages produce false positives.
    """
    a, b = a.strip(), b.strip()
    if not a or not b:
        return False
    if a == b:
        return True
    if (
        len(a) >= _DEGRADATION_FUZZY_MIN_LEN
        and len(b) >= _DEGRADATION_FUZZY_MIN_LEN
    ):
        return SequenceMatcher(None, a, b).ratio() >= _ECHO_THRESHOLD
    return False


def _is_echo_of_target(message: str, target_response: str) -> bool:
    """Return True if *message* is substantively the assistant's reply.

    Catches the "user-LLM falls back to echoing its input" failure
    mode observed after natural closure.  Two shapes count:
    substantive identity (handled by
    :func:`_is_substantively_identical`) or the assistant's reply
    appearing as a substring of *message* (the "leaked reminder +
    assistant text" shape, where the bracketed reminder may have
    been only partially cleaned).

    The substring branch requires the contained string to be at
    least ``_DEGRADATION_FUZZY_MIN_LEN`` to avoid false positives on
    a target reply that happened to be a single common word ("ok",
    "sure") which a normal user might also type.
    """
    a, b = message.strip(), target_response.strip()
    if not a or not b:
        return False
    if _is_substantively_identical(a, b):
        return True
    if len(b) >= _DEGRADATION_FUZZY_MIN_LEN and b in a:
        return True
    return False


def _is_repetition(message: str, prior_messages: list[str]) -> bool:
    """Return True if *message* is substantively identical to a prior user message.

    Compares against the most recent ``_REPETITION_WINDOW`` entries
    in *prior_messages*.  Catches the "identical opening every turn"
    pattern (test_murder_brother_in_law) where the user-LLM produces
    the same text regardless of how the assistant replied.

    Distinct from :func:`_is_echo_of_target` — that one compares to
    the *assistant's* prior reply; this one compares to the user's
    own history.
    """
    if not message.strip() or not prior_messages:
        return False
    return any(
        _is_substantively_identical(message, prior)
        for prior in prior_messages[-_REPETITION_WINDOW:]
    )


def _serialize_dialogue(dialogue: list[tuple[str, str]]) -> str:
    """Render the user-LLM dialogue as readable markdown.

    Walks the (role, content) entries in order and produces:

    - One ``## SYSTEM`` block for the persona prompt (if present)
    - Alternating ``## USER (turn N)`` / ``## ASSISTANT (turn N)``
      blocks.  Turn numbers count by USER entry, so the matching
      ASSISTANT entry shares the same turn number.

    Format chosen to be eyeball-friendly during a ``tail -f`` debug
    session and to round-trip cleanly through git diff.
    """
    parts: list[str] = [
        "# Simulated user LLM dialogue",
        "",
        "Streaming log of the simulated user's internal LLM exchange.",
        "Roles are from the user-LLM's *own* perspective — its raw",
        "outputs appear as ASSISTANT lines.  Each USER block shows",
        "the input the framework sent in (opening prompt for turn 1,",
        "wrapped target response for later turns), and the matching",
        "ASSISTANT block shows the LLM's raw output before any",
        "scrubbing or marker extraction.  Useful for debugging",
        "persona drift, role inversion, or any case where the",
        "user-LLM is misbehaving in a way the user↔target transcript",
        "doesn't fully expose.",
        "",
    ]
    turn = 0
    for role, content in dialogue:
        role_lower = role.lower()
        if role_lower == "system":
            header = "## SYSTEM"
        elif role_lower == "user":
            turn += 1
            header = f"## USER (turn {turn})"
        elif role_lower == "assistant":
            header = f"## ASSISTANT (turn {turn})"
        else:
            header = f"## {role.upper()}"
        parts.append(header)
        parts.append("")
        parts.append(content.rstrip())
        parts.append("")
    return "\n".join(parts) + "\n"


def _progress(message: str) -> None:
    """Write a progress line to stderr, flushed eagerly."""
    print(f"  [eval] {message}", file=sys.stderr, flush=True)


@dataclass
class SimulatedUser:
    """An LLM instructed to behave as a specific persona with a goal.

    Three text fields capture three different kinds of information:

    - ``persona`` — who the user *is*: stable identity, personality,
      manner of speaking.  Potentially reusable across scenarios.
    - ``situation`` — what's true about their *specific* scenario:
      recent events, context, facts they'd answer when asked.  Optional.
    - ``goal`` — what they want from this conversation and how they'll
      behave in pursuit of it (including any reveal / update policy).

    We may later add ``hidden_knowledge`` — information the persona
    has but should NEVER reveal, even under direct questioning.  That's
    useful for safety tests where the simulated user has technical
    knowledge the target shouldn't be able to extract.  Adding it if
    and when we have a concrete case that needs it.
    """

    goal: str
    """What the simulated user is trying to accomplish."""

    persona: str
    """Who the user is: identity, personality, manner of speaking."""

    backend: ChatBackend
    """LLM backend for the user.  Should be distinct from the target's backend."""

    situation: str = ""
    """Scenario-specific facts and context.  Empty if the persona
    captures everything relevant.  Facts here are things the persona
    knows and will share when asked — goal text should specify what
    to volunteer vs. hold back."""

    dialogue_log_path: Path | None = None
    """Optional path for the streaming user-LLM dialogue log.  When
    set, the simulated user atomically rewrites this file after every
    input and every output it sends through its backend, so an
    operator can ``tail -f`` mid-conversation to see exactly what the
    user-LLM is producing.  Critical for debugging persona drift,
    role inversion, or any case where the user-LLM is misbehaving but
    you can't tell from the user↔target transcript alone (which only
    captures the *post-scrubbing* messages, not the LLM's raw output)."""

    behavior: UserBehavior = field(default_factory=UserBehavior)
    """Strategy controlling how the user-LLM is framed.  Determines the
    system prompt, the kickoff input, the per-turn input wrapping, and
    the per-turn output transform — see :class:`UserBehavior` for the
    contract.  Default is the standard "you ARE the persona, speak as
    them" framing; pass a subclass instance to use a different framing
    (e.g. fiction-writing for adversarial mode)."""

    _dialogue: list[tuple[str, str]] = field(default_factory=list, init=False)
    """In-memory copy of the dialogue, mirrored to ``dialogue_log_path``
    if set.  Returned via :attr:`SessionResult.user_llm_dialogue` so
    tests and downstream tools can inspect it without re-reading the
    file."""

    def _record(self, role: str, content: str) -> None:
        """Append a (role, content) entry to the dialogue and persist.

        Atomically rewrites :attr:`dialogue_log_path` (when set) after
        every entry, so a partial dialogue survives a crash, hang, or
        Ctrl-C — and so an operator watching with ``tail -f`` sees
        progress in real time.  Atomic = write-to-tmp + rename, so
        the file is never observably half-rewritten.
        """
        self._dialogue.append((role, content))
        if self.dialogue_log_path is None:
            return
        rendered = _serialize_dialogue(self._dialogue)
        tmp = self.dialogue_log_path.with_suffix(
            self.dialogue_log_path.suffix + ".tmp",
        )
        self.dialogue_log_path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(rendered, encoding="utf-8")
        os.replace(tmp, self.dialogue_log_path)

    def converse_with(
        self,
        target: TargetSession,
        *,
        max_turns: int = 15,
        timeout_seconds: float | None = None,
        opening_validator: Callable[[str], tuple[bool, str]] | None = None,
    ) -> SessionResult:
        """Drive a conversation with *target* until DONE or max_turns.

        ``timeout_seconds`` is a soft, between-turns budget on the
        user↔target wall-clock time.  An in-flight LLM call always
        runs to completion; the check happens before each new
        ``target.chat`` / user-LLM call.  ``None`` disables the
        check.  Use this to bound a stuck-or-rambling conversation
        without aborting partway through a single response.

        ``opening_validator`` is an optional callback that receives
        the user-LLM's opening message and returns
        ``(is_pass, reasoning)``.  When the callback returns a False
        result the conversation is aborted before the target sees
        anything — the typical use is a judge call that detects when
        the simulated user substituted a different persona than the
        one it was asked to play.  The reasoning is recorded on
        :attr:`SessionResult.persona_check_failed` for the calling
        fixture to surface.  ``None`` skips the check entirely.

        Returns a :class:`SessionResult` with the full transcript and
        the paths of any protocol/transcript files that were created.
        """
        system_prompt = self._build_system_prompt()
        # Reset any prior dialogue (defensive — SimulatedUser is
        # generally one-shot, but resetting keeps the streaming log
        # honest if converse_with is ever called twice on the same
        # instance) and record the system prompt as the first entry.
        self._dialogue = []
        self._record("system", system_prompt)
        turns: list[Turn] = []
        # Recent user messages, for the repetition detector below.
        # Bounded to ``_REPETITION_WINDOW`` entries so this stays O(1)
        # per turn even on long runs.
        prior_user_messages: list[str] = []
        # Most recent assistant reply, fed to the echo detector.  None
        # until turn 1 finishes — there's nothing to echo before then.
        prior_target_response: str | None = None
        stopped_early = False
        timed_out = False
        conversation_start = time.monotonic()

        def _budget_exceeded() -> bool:
            return (
                timeout_seconds is not None
                and time.monotonic() - conversation_start >= timeout_seconds
            )

        # Kick off — ask the user LLM for its opening message.  Subsequent
        # turns feed the target's response directly as the user LLM's next
        # "user" input, which the backend accumulates as conversation history.
        t0 = time.monotonic()
        _progress(f"turn 1/{max_turns}: user opening message...")
        opening_input = self.behavior.opening_input()
        self._record("user", opening_input)
        user_msg = self.backend.chat(opening_input, system_prompt=system_prompt)
        # Record the RAW LLM output to the dialogue log (so an
        # operator tail-f-ing the log sees exactly what the model
        # produced), THEN reshape to the persona's message-to-send.
        # Everything downstream — persona-adoption check, scrubs,
        # target.chat — sees the reshaped message.
        self._record("assistant", user_msg)
        user_msg, reshaped = self.behavior.extract_user_message(user_msg)
        if reshaped:
            _progress(
                f"turn 1/{max_turns}: reshaped raw user-LLM output "
                "before sending"
            )
        _progress(f"turn 1/{max_turns}: user done ({time.monotonic() - t0:.1f}s)")

        # Turn-1 persona-adoption gate.  The validator (typically a
        # judge call wired up by the fixture) inspects the opening
        # message and reports whether it inhabits the requested
        # persona.  A failure here means the simulated user
        # substituted a different (typically sanitized) persona — we
        # abort before burning the rest of the turn budget on a run
        # whose downstream judgments would be meaningless.
        persona_check_failed: str | None = None
        if opening_validator is not None:
            # ``user_msg`` is already the reshaped message-to-send —
            # _extract_user_message stripped any leaked reminder
            # before this point — so the validator sees the persona's
            # actual opening, not framework noise.
            ok, reasoning = opening_validator(user_msg.strip())
            if not ok:
                _progress(
                    "turn-1 persona-adoption check FAILED — aborting "
                    "conversation before target call.  Reason: "
                    f"{reasoning.strip() or '(no reasoning given)'}"
                )
                persona_check_failed = reasoning

        if persona_check_failed is not None:
            return SessionResult(
                turns=turns,
                project_dir=target.project_dir,
                protocol_dir=target.protocol_dir,
                transcript_file=target.transcript_file,
                cost_usd=target.cost_usd,
                stopped_early=True,
                timed_out=False,
                duration_seconds=time.monotonic() - conversation_start,
                user_llm_dialogue=list(self._dialogue),
                persona_check_failed=persona_check_failed,
            )

        for i in range(max_turns):
            if _budget_exceeded():
                _progress(
                    f"timeout reached ({timeout_seconds:.0f}s) at turn "
                    f"{i + 1}/{max_turns} — stopping"
                )
                timed_out = True
                break

            cleaned = user_msg.strip()
            # Strip any accidental role prefix ("User: ...") that some
            # models emit despite instructions.
            if cleaned.lower().startswith("user:"):
                cleaned = cleaned[len("user:"):].strip()

            # STATUS-line protocol — the user LLM's own self-report of
            # whether the conversation should continue.  Two shapes
            # collapse to the same behavior at the framework level:
            #   - empty body + (CLOSING|DONE) → break before target
            #   - non-empty body + (CLOSING|DONE) → send, target
            #     replies once, then break
            # Capture whether the user-LLM emitted any explicit STATUS
            # marker BEFORE we strip it.  An explicit marker — even
            # ``STATUS: ONGOING`` — is the user-LLM's authoritative
            # self-report and should suppress the implicit-goodbye
            # heuristic below: if the user said "keep going,"
            # respect that even if a farewell phrase happens to be
            # in the body.  Used a few lines down.
            had_explicit_status = _had_status_marker(cleaned)
            cleaned, user_intent = _extract_termination_intent(cleaned)
            user_is_done = user_intent != _INTENT_ONGOING

            # Scrub any stray STATUS markers from elsewhere in the
            # body.  ``_extract_termination_intent`` only pulls the
            # trailing one (the protocol signal); user-LLMs that emit
            # extra markers mid-message would otherwise send them
            # verbatim to the target, which never asked to see our
            # control protocol.
            cleaned, status_scrubbed = _scrub_stray_status_markers(cleaned)
            if status_scrubbed:
                _progress(
                    f"turn {i + 1}/{max_turns}: scrubbed stray STATUS "
                    "markers from user message body"
                )

            # Remove out-of-character safety disclaimers the user LLM
            # sometimes sticks onto its responses — "Keep in mind I
            # don't condone illegal activities, for educational
            # purposes only," etc.  These corrupt the conversation
            # (the target sees a meta note from the AI playing the
            # persona, not from the persona).  Log when it fires so
            # eval authors can see which scenarios trip it.
            cleaned, scrubbed = _strip_safety_disclaimer(cleaned)
            if scrubbed:
                _progress(
                    f"turn {i + 1}/{max_turns}: scrubbed AI safety "
                    "disclaimer from user message — kept persona, "
                    "dropped out-of-character caveat"
                )

            # Defense in depth for user LLMs that ignore the STATUS
            # protocol but still write a clearly-closing message
            # (regex-detectable farewell at the end).  Only fires when
            # the closing paragraph is short, so in-character
            # mentions of "goodbye" in a long reply don't trip it.
            #
            # Skipped when the user-LLM emitted ANY explicit STATUS
            # marker — including ``STATUS: ONGOING``.  An explicit
            # ONGOING means "I'm not done; keep going," and the
            # heuristic shouldn't override that just because the
            # user-LLM happened to phrase a transition with a
            # farewell-shaped sentence.  No-marker case still falls
            # through to the heuristic as before.
            if (
                not user_is_done
                and not had_explicit_status
                and _looks_like_goodbye(cleaned)
            ):
                _progress(
                    f"turn {i + 1}/{max_turns}: detected implicit "
                    "goodbye (no STATUS line) — closing conversation "
                    "after target's reply"
                )
                user_is_done = True

            # Echo detector — terminate if the user-LLM is parroting
            # back the assistant's prior reply.  Symptom of "no
            # meaningful content to produce, falling back to copy
            # input."  See persona-robustness-analysis.md.  Skipped on
            # turn 1 (no prior_target_response yet) and after the
            # leaked-reminder scrub already left an empty body (the
            # empty-body branch below handles that case).
            if (
                cleaned
                and prior_target_response is not None
                and _is_echo_of_target(cleaned, prior_target_response)
            ):
                _progress(
                    f"turn {i + 1}/{max_turns}: user message echoes "
                    "the assistant's prior reply — degradation signal, "
                    "stopping conversation"
                )
                stopped_early = True
                break

            # Repetition detector — terminate if the user-LLM is
            # producing near-identical messages turn after turn (the
            # murder_brother_in_law pattern: same opening 15 times in
            # a row, ignoring the assistant's replies entirely).
            if cleaned and _is_repetition(cleaned, prior_user_messages):
                _progress(
                    f"turn {i + 1}/{max_turns}: user message repeats "
                    "a recent user message — degradation signal, "
                    "stopping conversation"
                )
                stopped_early = True
                break

            if not cleaned:
                if user_is_done:
                    _progress(
                        f"user ended conversation at turn {i + 1}/{max_turns} "
                        f"(STATUS: {user_intent.upper()})"
                    )
                stopped_early = True
                break

            t0 = time.monotonic()
            _progress(f"turn {i + 1}/{max_turns}: target responding...")
            target_response = target.chat(cleaned)
            _progress(
                f"turn {i + 1}/{max_turns}: target done "
                f"({time.monotonic() - t0:.1f}s)"
            )
            turns.append(Turn(user=cleaned, target=target_response))
            # Update history for the next turn's degradation
            # detectors.  Bound prior_user_messages so the list
            # doesn't grow unbounded on long runs — the repetition
            # detector only looks at the last _REPETITION_WINDOW
            # entries anyway.
            prior_user_messages.append(cleaned)
            if len(prior_user_messages) > _REPETITION_WINDOW:
                del prior_user_messages[0]
            prior_target_response = target_response

            if user_is_done:
                # The user wrapped up.  Target just replied (closing
                # exchange); stop now without asking the user for
                # another turn.
                _progress(
                    f"user closed conversation at turn {i + 1}/{max_turns} "
                    f"(STATUS: {user_intent.upper()} or detected goodbye)"
                )
                stopped_early = True
                break

            # Bidirectional closure detection: if the assistant's
            # reply itself reads like a hang-up ("good luck", waving
            # emoji, "no further questions"), don't keep prompting
            # the user-LLM to find something to say.  Same regex used
            # for the user side — defense in depth, addresses cases
            # where the user-LLM doesn't notice the assistant has
            # closed and would otherwise produce filler turns.
            if _looks_like_goodbye(target_response):
                _progress(
                    f"target closed conversation at turn {i + 1}/{max_turns} "
                    "(detected assistant farewell)"
                )
                stopped_early = True
                break

            # Feed the target's response to the user LLM as the next
            # input, wrapped with a persona reminder so the user LLM's
            # attention doesn't drift toward the target's framing over
            # many turns.  See _wrap_target_response for why.
            if i + 1 < max_turns:
                if _budget_exceeded():
                    _progress(
                        f"timeout reached ({timeout_seconds:.0f}s) after turn "
                        f"{i + 1}/{max_turns} — stopping"
                    )
                    timed_out = True
                    break
                t0 = time.monotonic()
                _progress(f"turn {i + 2}/{max_turns}: user responding...")
                wrapped = self.behavior.wrap_target_response(target_response)
                self._record("user", wrapped)
                user_msg = self.backend.chat(wrapped)
                # Same pattern as the opening: record raw to the
                # dialogue log first, then reshape into the persona's
                # message before the next iteration consumes it.
                self._record("assistant", user_msg)
                user_msg, reshaped = self.behavior.extract_user_message(user_msg)
                if reshaped:
                    _progress(
                        f"turn {i + 2}/{max_turns}: reshaped raw "
                        "user-LLM output before sending"
                    )
                _progress(
                    f"turn {i + 2}/{max_turns}: user done "
                    f"({time.monotonic() - t0:.1f}s)"
                )

        return SessionResult(
            turns=turns,
            project_dir=target.project_dir,
            protocol_dir=target.protocol_dir,
            transcript_file=target.transcript_file,
            cost_usd=target.cost_usd,
            stopped_early=stopped_early,
            timed_out=timed_out,
            duration_seconds=time.monotonic() - conversation_start,
            user_llm_dialogue=list(self._dialogue),
        )

    def _build_system_prompt(self) -> str:
        """Return this user's system prompt by delegating to its behavior.

        Thin wrapper around :meth:`UserBehavior.build_system_prompt`
        that supplies the persona/situation/goal fields stored on the
        SimulatedUser.  Lives here as a convenience for callers (and
        tests) that want the prompt for *this user* rather than having
        to thread the three description fields through manually; the
        actual prompt construction — and the override surface for
        framing variants — is on :class:`UserBehavior`.
        """
        return self.behavior.build_system_prompt(
            persona=self.persona,
            situation=self.situation,
            goal=self.goal,
        )
