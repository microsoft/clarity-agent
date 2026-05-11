"""Helpers for running end-to-end eval conversations.

The house style: one shared conversation per test module, evaluated
by several test functions.  :func:`make_conversation_fixture` is the
high-level helper — it returns a pytest module-scoped fixture that
handles project-directory setup and conversation running.

Each test writes directly into its per-test output directory under
the run's root (e.g. ``eval-runs/<ts>/safety/test_terminal_suicide/``).
That directory doubles as Clarity's project dir, so protocol files
and transcripts land there live as the conversation runs — useful
for watching progress with ``tail -f`` during long runs.

In ``--judge-only`` mode (set on the pytest command line), the
fixture loads the previously-preserved transcript / protocol from
the chosen output directory rather than running a new conversation.
Tests whose data is missing skip; tests whose data is present have
only their judge calls re-run.  This is useful for re-evaluating an
existing run with a new judge prompt or a different judge model
without paying for the target/user calls again.

:func:`run_conversation` is the lower-level context manager that the
fixture uses internally; expose it so test authors can build custom
fixtures if needed.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from evals.framework.config import EvalConfig
from evals.framework.judge import (
    _SUBSTANTIVITY_CACHE_KEY,
    AgentRefusedError,
    SmokeCheckFailedError,
    _make_substantivity_record,
)
from evals.framework.resume import JudgeCache, compute_fingerprint
from evals.framework.target import TargetSession
from evals.framework.types import SessionResult, Turn
from evals.framework.user import SimulatedUser


def _phase(message: str) -> None:
    """Print a phase marker.  Stderr so pytest's stdout capture doesn't hide it."""
    print(f"\n  [eval] {message}", file=sys.stderr, flush=True)


def _module_has_marker(request: pytest.FixtureRequest, name: str) -> bool:
    """Return True if any test in *request*'s module has the given marker.

    Catches both module-level (``pytestmark = refusal_acceptable``)
    and per-test (``@refusal_acceptable``) usage.  We look at all
    tests' markers because the conversation fixture is module-scoped
    — if any test in the module declares the marker, we want the
    marker's behavior to apply to the shared conversation.

    Returns False if the request doesn't have a session-level
    iterator we can walk — e.g. some non-standard fixture call
    paths.  Defensive: never raise from here.
    """
    try:
        for item in request.session.items:
            # ``item.module`` is defined on pytest.Function (the
            # subclass for test functions) but not on the abstract
            # Item base class — getattr with a default so pyright
            # doesn't complain on the static type AND so non-Function
            # items (rare hookable subclasses) don't blow up.
            item_module = getattr(item, "module", None)
            if item_module is request.module:
                if item.get_closest_marker(name) is not None:
                    return True
        return False
    except (AttributeError, TypeError):
        return False


@contextmanager
def run_conversation(
    config: EvalConfig,
    *,
    goal: str,
    persona: str,
    clarity_agent_dir: Path,
    project_dir: Path,
    situation: str = "",
    max_turns: int = 15,
    timeout_seconds: float | None = None,
    opening_validator: Callable[[str], tuple[bool, str]] | None = None,
    target_role: str | None = None,
    user_role: str | None = None,
) -> Iterator[SessionResult]:
    """Run one simulated conversation end-to-end and yield the result.

    Handles backend lifecycle for both target and user.  *project_dir*
    is used directly as Clarity's project directory — protocol files
    and transcripts land there live.  ``timeout_seconds`` is a soft,
    between-turns wall-clock budget; ``None`` disables it.  Use inside
    a module-scoped pytest fixture to share a single conversation
    across multiple test assertions:

    .. code-block:: python

        @pytest.fixture(scope="module")
        def result(eval_config, clarity_agent_dir, output_dir):
            project_dir = output_dir / "functionality" / "my_scenario"
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / ".git").mkdir(exist_ok=True)
            with run_conversation(
                eval_config,
                goal=GOAL,
                persona=PERSONA,
                clarity_agent_dir=clarity_agent_dir,
                project_dir=project_dir,
            ) as r:
                yield r
    """
    # Run the entire conversation in an opaque tmp working directory
    # so the Clarity target can't see project_dir's name or
    # surroundings.  Anything the target can observe about its
    # working dir ("eval-runs/..../test_murder_brother_in_law") leaks
    # the test's intent and tips the LLM off that it's being
    # evaluated — both of which have been observed to corrupt evals.
    # We move the artifacts into project_dir at the very end, after
    # the target is done reading.
    working_dir = Path(tempfile.mkdtemp(prefix="clarity-conversation-"))
    (working_dir / ".git").mkdir()
    _phase(f"Conversation working dir (hidden from target): {working_dir}")

    target_backend, llm_config = config.create_backend(
        slot="target",
        role=target_role,
        project_dir=working_dir,
        clarity_agent_dir=clarity_agent_dir,
    )
    target_backend.connect()
    try:
        target = TargetSession(
            project_dir=working_dir,
            clarity_agent_dir=clarity_agent_dir,
            backend=target_backend,
            llm_config=llm_config,
        )
        try:
            user_backend, _ = config.create_backend(
                slot="user",
                role=user_role,
                project_dir=working_dir,
                clarity_agent_dir=clarity_agent_dir,
            )
            user_backend.connect()
            try:
                # Spool the streaming user-LLM dialogue to /tmp, NOT
                # to working_dir (same leak concern as above — the
                # target reads files in its working dir) and NOT to
                # project_dir (that's the final resting place, set up
                # only after the conversation completes).  The spool
                # path is independent of both.
                tmp_dialogue_log = _make_spool_path(project_dir)
                _phase(
                    f"User-LLM dialogue (live): {tmp_dialogue_log} "
                    "— `tail -f` this to watch the user role in real time"
                )
                user = SimulatedUser(
                    goal=goal,
                    persona=persona,
                    backend=user_backend,
                    situation=situation,
                    dialogue_log_path=tmp_dialogue_log,
                )
                try:
                    result = user.converse_with(
                        target,
                        max_turns=max_turns,
                        timeout_seconds=timeout_seconds,
                        opening_validator=opening_validator,
                    )
                except BaseException:
                    # Preserve whatever partial state is on disk —
                    # the dialogue spool plus any .clarity-protocol/
                    # files the target managed to write — before
                    # re-raising.  Gives a failed run something to
                    # debug.
                    _move_spool_into_project(tmp_dialogue_log, project_dir)
                    _move_conversation_artifacts_to_final(
                        working_dir, project_dir, None,
                    )
                    raise
                # Success path: move the spool, write the summary
                # artifacts into working_dir, then move everything
                # into project_dir as the final step.
                _move_spool_into_project(tmp_dialogue_log, project_dir)
                _write_test_artifacts(
                    result, working_dir,
                    persona=persona, situation=situation, goal=goal,
                )
                _move_conversation_artifacts_to_final(
                    working_dir, project_dir, result,
                )
                yield result
            finally:
                user_backend.disconnect()
        finally:
            target.close()
    finally:
        target_backend.disconnect()
        # Drop the working_dir last — after the target session is
        # torn down, so the transcript file handle (which tracks an
        # inode, not a path, on Unix) has already been closed.
        shutil.rmtree(working_dir, ignore_errors=True)


def protocol_content(result: SessionResult) -> str:
    """Concatenate all non-empty markdown files in the protocol dir.

    Useful for judge assertions that need to evaluate both the
    conversation transcript AND what the target wrote into the
    protocol directory.
    """
    if result.protocol_dir is None or not result.protocol_dir.exists():
        return ""
    parts: list[str] = []
    for path in sorted(result.protocol_dir.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if text.strip():
            rel = path.relative_to(result.protocol_dir)
            parts.append(f"## {rel}\n\n{text}")
    return "\n\n".join(parts)


def _write_test_artifacts(
    result: SessionResult,
    project_dir: Path,
    *,
    persona: str,
    situation: str,
    goal: str,
) -> None:
    """Write summary artifacts alongside the live Clarity output.

    *project_dir* is Clarity's own project directory, so its
    ``.clarity-protocol/`` tree (including transcripts) is already on
    disk.  We only need to add the eval-specific files:

      - ``transcript.md``     — the full user/target conversation
      - ``metadata.json``     — turn count, cost, scenario inputs, etc.

    The persona/situation/goal are recorded so ``summary.md`` can be
    a self-contained review artifact — a reader can see what the
    simulated user was told to do without opening the test file.
    """
    (project_dir / "transcript.md").write_text(
        result.transcript, encoding="utf-8",
    )

    metadata = {
        "turn_count": result.turn_count,
        "cost_usd": result.cost_usd,
        "stopped_early": result.stopped_early,
        "timed_out": result.timed_out,
        "duration_seconds": result.duration_seconds,
        # Captured from the turn-1 persona-adoption gate (run inside
        # converse_with via opening_validator).  Persisted so resume
        # can preserve the original gate-failure classification —
        # without this, a resume of a persona-failed conversation
        # gets reclassified as a substantivity failure (or whatever
        # other gate happens to fire on the cached transcript), and
        # the summary's "which gate failed" label is wrong.  Stored
        # as ``None`` for conversations where the persona gate
        # passed; ``_load_session_result`` reads it back.
        "persona_check_failed": result.persona_check_failed,
        "persona": persona.strip(),
        "situation": situation.strip(),
        "goal": goal.strip(),
    }
    (project_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8",
    )


def _project_dir_path_for(root: Path, module_file: Path) -> Path:
    """Compute ``<root>/<category>/<module-stem>/`` as a path; no I/O.

    ``module_file`` is expected to live under
    ``evals/cases/<category>/test_*.py``.  Falls back to
    ``<root>/<module-stem>/`` if ``cases/`` isn't in the path.
    """
    parts = module_file.parts
    try:
        cases_idx = parts.index("cases")
        tail = Path(*parts[cases_idx + 1:])
        return root / tail.with_suffix("")
    except ValueError:
        return root / module_file.stem


def _project_dir_for(root: Path, module_file: Path) -> Path:
    """Compute the project dir AND clean+create it for a fresh run.

    If the directory already exists (from a previous run reusing the
    same output root), its contents are cleared so the new run starts
    from a clean state.
    """
    dest = _project_dir_path_for(root, module_file)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    return dest


# The conversation-level artifacts that get produced in the working
# tmpdir and moved into the final project_dir after the target is
# done.  The ``user_llm_dialogue.md`` spool is handled separately
# (it never lives in working_dir — it's in /tmp from the start).
_CONVERSATION_ARTIFACT_NAMES = (
    ".clarity-protocol",
    "transcript.md",
    "metadata.json",
)


def _move_conversation_artifacts_to_final(
    working_dir: Path,
    project_dir: Path,
    result: SessionResult | None,
) -> None:
    """Move conversation artifacts from a tmp working dir into project_dir.

    The conversation runs in an opaque tmp directory so the Clarity
    target can't learn anything from ``project_dir``'s name or
    surroundings (seeing ``eval-runs/.../test_murder_brother_in_law``
    in its own working directory tips it off that it's being
    evaluated, leaks the persona's intent, etc.).  This helper does
    the final migration once the target is finished.

    Replaces any same-named destinations (e.g., a half-wiped prior
    run) so the final state is exactly the fresh artifacts.  Updates
    *result*'s path attributes to point at the final location;
    tolerates ``result=None`` for the conversation-failed path where
    we want to preserve partial state for debugging without a
    SessionResult to update.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    for name in _CONVERSATION_ARTIFACT_NAMES:
        src = working_dir / name
        dst = project_dir / name
        if not src.exists():
            continue
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        # On Windows, shutil.move (os.rename) can fail with
        # PermissionError when the Copilot SDK or another backend
        # hasn't fully released file handles yet.  Fall back to
        # copytree which copies to the destination without needing
        # exclusive access to the source, then best-effort clean up.
        try:
            shutil.move(str(src), str(dst))
        except (PermissionError, OSError):
            if src.is_dir():
                shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
                shutil.rmtree(str(src), ignore_errors=True)
            else:
                shutil.copy2(str(src), str(dst))
                try:
                    src.unlink()
                except OSError:
                    pass

    if result is None:
        return
    result.project_dir = project_dir
    pd = project_dir / ".clarity-protocol"
    result.protocol_dir = pd if pd.exists() else None
    # ClaritySession opens its transcript under working_dir; once we
    # move the containing .clarity-protocol/ tree, re-anchor the
    # stored path so downstream consumers can read it.
    if result.transcript_file is not None:
        try:
            rel = result.transcript_file.relative_to(working_dir)
            result.transcript_file = project_dir / rel
        except ValueError:
            # transcript_file isn't under working_dir (shouldn't
            # happen in practice) — leave as-is.
            pass


def _make_spool_path(project_dir: Path) -> Path:
    """Build a unique tmp path for the streaming user-LLM dialogue.

    Includes the module slug in the filename so a developer with
    multiple eval runs in flight can identify which spool belongs
    to which test from the path alone (the operator typically reads
    the path off the ``[eval]`` log and `tail -f`s it).

    Lives in :func:`tempfile.gettempdir` so the Clarity target —
    which reads files in ``project_dir`` — can't see the live log
    and accidentally learn the user's persona / goal / "this is a
    test" framing during the conversation.
    """
    parts = project_dir.parts
    try:
        idx = parts.index("eval-runs")
        slug = "-".join(parts[idx + 1:])  # e.g. "20260424-120300-safety-test_x"
    except ValueError:
        slug = project_dir.name
    safe_slug = re.sub(r"[^A-Za-z0-9_.-]", "-", slug)[:120] or "module"
    fd, path_str = tempfile.mkstemp(
        prefix=f"clarity-eval-user-dialogue-{safe_slug}-",
        suffix=".md",
    )
    # Close the descriptor — SimulatedUser will reopen via Path.
    import os as _os
    _os.close(fd)
    return Path(path_str)


def _move_spool_into_project(spool_path: Path, project_dir: Path) -> None:
    """Move the dialogue spool from tmp into project_dir as the final artifact.

    Runs in a finally block so it fires even when ``converse_with``
    raised — the partial dialogue is the most useful debug data
    available in that case.  Errors are swallowed: a missing or
    unmovable spool is a diagnostic-quality issue, not a reason to
    obscure the underlying conversation failure.
    """
    if not spool_path.exists():
        return
    try:
        target = project_dir / "user_llm_dialogue.md"
        project_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(spool_path), str(target))
    except OSError as exc:
        _phase(
            f"warning: failed to move dialogue spool {spool_path} "
            f"into {project_dir}: {exc} (the spool remains at the "
            "tmp path above)"
        )


def _wipe_conversation_artifacts(project_dir: Path) -> None:
    """Remove conversation outputs so a fresh run can be written in place.

    Keeps the ``.git`` marker and any unrelated files, but clears
    ``.clarity-protocol/`` plus ``transcript.md`` and ``metadata.json``.
    Also deletes ``judge_records.json`` because cached judgments refer
    to a transcript that no longer exists — leaving them would silently
    serve stale verdicts against the new conversation.
    """
    for name in (
        ".clarity-protocol",
        "transcript.md",
        "metadata.json",
        "judge_records.json",
    ):
        target = project_dir / name
        if target.is_file() or target.is_symlink():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)


@contextmanager
def _yield_existing(result: SessionResult) -> Iterator[SessionResult]:
    """Trivial context manager for the resume path.

    Lets the fixture use a single ``with ... as r`` form regardless of
    whether the conversation was run fresh or loaded from disk.
    """
    yield result


# --- Judge-only mode: loading preserved artifacts ---

_TURN_HEADER_RE = re.compile(r"^## Turn \d+\s*$", re.MULTILINE)
_TURN_PARTS_RE = re.compile(
    r"\*\*User:\*\*\n(?P<user>.*?)\n\*\*Assistant:\*\*\n(?P<target>.*)\Z",
    re.DOTALL,
)


def _parse_transcript_md(text: str) -> list[Turn]:
    """Parse ``transcript.md`` back into :class:`Turn` objects.

    Inverse of :attr:`SessionResult.transcript`.  A round-trip test
    in ``tests/test_eval_runner.py`` guards the coupling.
    """
    chunks = _TURN_HEADER_RE.split(text)
    turns: list[Turn] = []
    for chunk in chunks[1:]:  # chunks[0] is anything before the first header
        m = _TURN_PARTS_RE.search(chunk.strip())
        if m:
            turns.append(Turn(
                user=m.group("user").strip(),
                target=m.group("target").strip(),
            ))
    return turns


def _load_session_result(project_dir: Path) -> SessionResult | None:
    """Reconstruct a :class:`SessionResult` from preserved on-disk artifacts.

    Returns ``None`` if ``transcript.md`` is missing — in that case
    judge-only mode skips the test entirely.
    """
    transcript_path = project_dir / "transcript.md"
    if not transcript_path.exists():
        return None
    transcript_text = transcript_path.read_text(encoding="utf-8")
    turns = _parse_transcript_md(transcript_text)

    metadata: dict[str, Any] = {}
    metadata_path = project_dir / "metadata.json"
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    protocol_dir = project_dir / ".clarity-protocol"
    return SessionResult(
        turns=turns,
        project_dir=project_dir,
        protocol_dir=protocol_dir if protocol_dir.exists() else None,
        transcript_file=None,
        cost_usd=metadata.get("cost_usd", 0.0),
        stopped_early=metadata.get("stopped_early", False),
        timed_out=metadata.get("timed_out", False),
        duration_seconds=metadata.get("duration_seconds", 0.0),
        # Restore the original turn-1 persona-adoption verdict so
        # the resume path classifies the smoke-failure the same way
        # the original run did.  Older metadata files predating
        # this field default to None (persona gate passed), which
        # is the same behavior as before this fix — so existing
        # resumed runs that DIDN'T fail persona-adoption are
        # unaffected.
        persona_check_failed=metadata.get("persona_check_failed"),
    )


def make_conversation_fixture(
    *,
    goal: str,
    persona: str,
    situation: str = "",
    meta_goal: str | None = None,
    max_turns: int | None = None,
    timeout_seconds: float | None = None,
    slug: str | None = None,
    target: str | None = None,
    user: str | None = None,
    judge: str | None = None,
) -> Callable:
    """Build a module-scoped pytest fixture for a shared conversation.

    This is the recommended way to write an eval case.  Use like::

        PERSONA = "..."
        SITUATION = "..."
        GOAL = "..."

        result = make_conversation_fixture(
            goal=GOAL, persona=PERSONA, situation=SITUATION,
        )

        def test_criterion_one(result, judge):
            assert judge.check(result.transcript, "...")

    ``meta_goal`` (optional) overrides what the goal-coverage smoke
    check evaluates against.  Use it when the eval is designed
    around the agent challenging the user's stated framing — false-
    premise repair, redirect-to-real-need patterns.  Without it,
    such tests fail goal-coverage even when the agent did the right
    thing, because the user's surface goal went unmet by design.
    The persona's GOAL is unchanged either way — the user-LLM still
    pursues what the persona believes they want.  ``meta_goal`` is
    purely a framework-level evaluation lens, never seen by the
    user-LLM or the target.

    ``max_turns`` and ``timeout_seconds`` default to the values in
    ``evals/config.yaml`` (``defaults.max_turns`` /
    ``defaults.timeout_seconds``) when left as ``None``.  Pass an
    explicit value to override the global default for a single test
    — useful for short scenarios that should end quickly or for
    long-running ones that need extra room.  ``timeout_seconds`` is
    a soft, between-turns budget; an in-flight LLM call always runs
    to completion.

    The per-test directory under the run's ``output_dir`` (e.g.
    ``eval-runs/<ts>/<category>/<module>/``) doubles as Clarity's
    project directory — protocol files, transcripts, and the
    eval-level ``transcript.md`` / ``metadata.json`` all land there
    live, so you can watch progress with ``tail`` during long runs.

    ``slug`` overrides the per-test subdirectory name; defaults to
    ``<category>/<module-stem>`` derived from the test's file path.

    ``target``, ``user``, and ``judge`` (optional) override which model
    profile to use for that role on this specific eval.  Each must
    name a profile defined in ``evals/config.yaml`` (i.e., a key under
    ``models:``).  ``None`` falls back to the reserved default
    (``_target`` / ``_user`` / ``_judge``).  Use these to route a
    safety-test eval to a less-safety-tuned user-LLM
    (``user="unsafe_user"``), point an adversarial test at a stronger
    judge, etc., without affecting the default profile that other
    evals continue to use.
    """
    # Capture overrides in locally-renamed names so the inner fixture
    # can reference them without shadowing its pytest-injected
    # ``judge`` fixture parameter (which is the Judge *instance*, not
    # the role-name override).
    _target_role_override = target
    _user_role_override = user
    _judge_role_override = judge

    @pytest.fixture(scope="module")
    def _fixture(
        eval_config,
        clarity_agent_dir,
        output_dir,
        rebuild_targets,
        judge,
        request,
    ) -> Iterator[SessionResult]:
        # Compute the per-test project dir (path only — no I/O yet).
        if slug is not None:
            project_dir = output_dir / slug
        else:
            project_dir = _project_dir_path_for(
                output_dir, Path(request.fspath),
            )
        display_slug = slug or project_dir.relative_to(output_dir).as_posix()

        # Apply rebuild directives, worst→narrowest.  "all" subsumes
        # "conversation", which in turn forces judgments to rebuild
        # (the transcript they judged against is gone).
        rebuild_all = "all" in rebuild_targets
        rebuild_conversation = rebuild_all or "conversation" in rebuild_targets
        rebuild_judgment = rebuild_conversation or "judgment" in rebuild_targets

        if rebuild_all and project_dir.exists():
            shutil.rmtree(project_dir)

        # Ensure the module dir + git marker exist.  Use exist_ok=True
        # so resume paths (which keep an existing dir) don't fail.
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / ".git").mkdir(exist_ok=True)

        # Try to resume the conversation from existing artifacts.
        # ``rebuild_conversation`` forces us to run fresh regardless of
        # what's on disk.
        loaded: SessionResult | None = None
        if not rebuild_conversation:
            loaded = _load_session_result(project_dir)

        if loaded is not None:
            _phase(
                f"Resumed conversation: {display_slug} "
                f"({loaded.turn_count} turns)"
            )
            conversation_ctx = _yield_existing(loaded)
        else:
            # Fresh run.  ALWAYS wipe conversation artifacts first,
            # even when there's no explicit --rebuild flag: if an
            # earlier run was interrupted mid-conversation it may have
            # left .clarity-protocol/ on disk without a transcript.md.
            # Restarting without the wipe would make the Clarity
            # target see the stale protocol and behave as if it were
            # continuing the previous conversation, while the
            # simulated user starts over from turn 1 — a subtle
            # desync that silently corrupts the run.  Idempotent
            # when the dir is already clean.
            _wipe_conversation_artifacts(project_dir)

            effective_max_turns = (
                max_turns if max_turns is not None
                else eval_config.max_turns
            )
            effective_timeout = (
                timeout_seconds if timeout_seconds is not None
                else eval_config.timeout_seconds
            )
            timeout_label = (
                f", timeout {effective_timeout:.0f}s"
                if effective_timeout is not None else ""
            )
            _phase(
                f"Running conversation: {display_slug} "
                f"(max {effective_max_turns} turns{timeout_label})"
            )
            _phase(f"Output directory: {project_dir}")

            # Turn-1 persona-adoption gate, run inside converse_with.
            # The closure routes the live opening message through the
            # judge so we can abort the run before turn 2 if the
            # simulated user substituted a sanitized persona.  See
            # persona-robustness-analysis.md for the failure modes
            # this catches (and which it doesn't).  The judge's cache
            # is set up after the conversation completes (see below)
            # — the live persona check therefore always issues a
            # fresh judgment, which is the right behavior because the
            # check only fires on fresh runs (resumes skip
            # converse_with entirely).
            def _persona_validator(opening_message: str) -> tuple[bool, str]:
                return judge.persona_adoption_check(
                    opening_message,
                    persona=persona, situation=situation, goal=goal,
                )

            conversation_ctx = run_conversation(
                eval_config,
                goal=goal,
                persona=persona,
                situation=situation,
                clarity_agent_dir=clarity_agent_dir,
                project_dir=project_dir,
                max_turns=effective_max_turns,
                timeout_seconds=effective_timeout,
                opening_validator=_persona_validator,
                target_role=_target_role_override,
                user_role=_user_role_override,
            )

        with conversation_ctx as r:
            if loaded is None:
                note = " (timed out)" if r.timed_out else ""
                _phase(
                    f"Conversation complete: {r.turn_count} turns, "
                    f"${r.cost_usd:.4f}{note} — evaluating criteria"
                )

            # Set up the judgment cache for this module.  The
            # fingerprint covers the exact transcript the judge will
            # see, so any edit — manual or by rerun — invalidates
            # cached verdicts automatically.
            cache_path = project_dir / "judge_records.json"
            if rebuild_judgment:
                cache_path.unlink(missing_ok=True)
            cache = JudgeCache(
                path=cache_path,
                fingerprint=compute_fingerprint(r.transcript),
            )
            judge.set_cache(cache)
            judge.set_role(_judge_role_override)
            try:
                # Turn-1 persona-adoption result, if a fresh
                # converse_with run flagged it.  Surfaces with the
                # same smoke_failed semantics as the post-conversation
                # smoke check, but with a more specific reason ("user
                # never adopted the persona" vs. "conversation didn't
                # explore the goal").  Resumed conversations carry
                # ``persona_check_failed=None`` because converse_with
                # didn't run — the resume path trusts whatever
                # smoke/persona verdicts were cached previously.
                if r.persona_check_failed is not None:
                    reason = r.persona_check_failed
                    _phase(
                        f"Persona-adoption check FAILED for {display_slug} — "
                        "marking module as smoke_failed"
                    )
                    raise SmokeCheckFailedError(
                        f"Persona-adoption check failed for "
                        f"{display_slug}: {reason}",
                        reasoning=reason,
                    )

                # Optional refusal gate, only for modules marked
                # ``@refusal_acceptable``.  Runs BEFORE substantivity
                # because a clean turn-1 "go away" is a valid pass
                # for these tests — substantivity's >= 2 turns
                # threshold would otherwise smoke-fail it.  If the
                # judge agrees the agent refused cleanly, every
                # test in the module is short-circuited to the
                # ``refused`` outcome (a success flavor).  If the
                # judge says the agent engaged, we fall through to
                # the normal gates.
                if _module_has_marker(request, "refusal_acceptable"):
                    _phase(f"Running refusal check for {display_slug}")
                    is_refused, refusal_reasoning = judge.refusal_check(
                        r.transcript, goal=goal,
                    )
                    if is_refused:
                        _phase(
                            f"Refusal check PASSED for {display_slug} — "
                            "agent refused cleanly; marking module as refused "
                            "(success short-circuit)"
                        )
                        raise AgentRefusedError(
                            f"Agent refused for {display_slug}: "
                            f"{refusal_reasoning}",
                            reasoning=refusal_reasoning,
                        )
                    _phase(
                        f"Refusal check ENGAGED for {display_slug} — "
                        "agent engaged with the request; continuing to "
                        "substantivity / goal-pursued gates"
                    )

                # Substantivity gate.  Pure code, no LLM call —
                # checks ``turn_count >= 2``.  Below that, the
                # conversation didn't have enough exchange for any
                # downstream criterion to differentiate behavior, so
                # goal_pursued_check would just produce a meaningless verdict
                # too.  Promoted from the old per-test
                # ``test_conversation_was_substantive`` assertion to
                # a framework gate so the whole module aborts cleanly.
                # Synthetic record stored in the cache so the report
                # renders this gate alongside the other smoke gates.
                substantivity_rec = _make_substantivity_record(r.turn_count)
                cache.store(
                    _SUBSTANTIVITY_CACHE_KEY, substantivity_rec,
                )
                if substantivity_rec.verdict != "YES":
                    _phase(
                        f"Substantivity check FAILED for {display_slug} — "
                        "marking module as smoke_failed"
                    )
                    raise SmokeCheckFailedError(
                        f"Substantivity check failed for "
                        f"{display_slug}: {substantivity_rec.reasoning}",
                        reasoning=substantivity_rec.reasoning,
                    )

                # User-pursuit gate: did the simulated user-LLM stay
                # in character and earnestly pursue its goal?  Subject
                # is the user's MESSAGES, not the agent's responses
                # or the conversation outcome.  Catches the failure
                # modes downstream of the persona-reminder defenses:
                # role inversion, persona dissolution, drift, echo,
                # repetition.  Run BEFORE goal-coverage so that when
                # the user-LLM has degraded we surface that as the
                # reason (the more fundamental issue) rather than
                # whatever incidental coverage failure also happened.
                _phase(f"Running user-pursuit check for {display_slug}")
                user_passed, user_reasoning = judge.user_pursued_check(
                    r.transcript, goal=goal,
                )
                if not user_passed:
                    _phase(
                        f"User-pursuit check FAILED for {display_slug} — "
                        "marking module as smoke_failed"
                    )
                    raise SmokeCheckFailedError(
                        f"User-pursuit check failed for {display_slug}: "
                        f"{user_reasoning}",
                        reasoning=user_reasoning,
                    )

                # Goal-coverage gate: did the WHOLE conversation cover
                # the right ground?  Default lens evaluates against
                # the user's stated goal; with ``meta_goal`` set, the
                # judge evaluates against the deeper question the
                # eval is designed to measure (false-premise repair,
                # redirect-to-real-need patterns).  Failure here means
                # the conversation was on-character but didn't engage
                # with what the test cares about.
                _phase(f"Running goal-coverage check for {display_slug}")
                smoke_passed, smoke_reasoning = judge.goal_pursued_check(
                    r.transcript, goal=goal, meta_goal=meta_goal,
                )
                if not smoke_passed:
                    _phase(
                        f"Goal-coverage check FAILED for {display_slug} — "
                        "marking module as smoke_failed"
                    )
                    raise SmokeCheckFailedError(
                        f"Goal-coverage check failed for {display_slug}: "
                        f"{smoke_reasoning}",
                        reasoning=smoke_reasoning,
                    )
                yield r
            finally:
                # Drop on-disk cache entries from earlier runs that
                # weren't touched this session — typically records
                # left behind when a smoke-gate or judge claim was
                # rewritten between runs.  See JudgeCache.prune_unseen
                # for the full rationale.  Runs after all per-test
                # judge calls have completed (per pytest's
                # yield-then-teardown ordering).
                cache.prune_unseen()
                judge.set_cache(None)
                judge.set_role(None)

    return _fixture


__all__ = [
    "make_conversation_fixture",
    "protocol_content",
    "run_conversation",
]
