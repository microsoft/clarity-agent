"""pytest fixtures and hooks for the eval framework.

Fixtures are consumed by test cases under ``evals/cases/**/test_*.py``.
The hooks below collect per-test outcomes and judge-call records.

``summary.md`` is rewritten incrementally — after each test starts,
each judge call, and each test outcome — so that an interrupted run
still has a report of everything completed and every judge call
made up to the interrupt.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from evals.framework import (
    AgentRefusedError,
    EvalConfig,
    Judge,
    SimulatedUser,
    SmokeCheckFailedError,
    TargetSession,
    describe_resolved_config,
    load_default,
    missing_credentials,
)
from evals.framework.judge import JudgeRecord
from evals.framework.report import write_summary


def _repo_root() -> Path:
    # conftest.py is at evals/conftest.py; repo root is one up.
    return Path(__file__).resolve().parent.parent


_REBUILD_CHOICES = ("conversation", "judgment", "all", "none")


# ---------------------------------------------------------------------------
# CLI options
# ---------------------------------------------------------------------------

def pytest_addoption(parser: pytest.Parser) -> None:
    """Register eval-specific command-line options."""
    group = parser.getgroup("evals")
    group.addoption(
        "--output-dir",
        action="store",
        default=None,
        metavar="DIR",
        help=(
            "Directory for eval run outputs.  Each test writes its "
            "protocol, transcripts, and metadata directly into "
            "<DIR>/<category>/<module>/ as the conversation runs — "
            "tail files there to watch progress during long runs.  "
            "A summary.md is written at the root at session end.  "
            "REQUIRED when running tests under evals/cases/ — pytest "
            "exits with an error at collection time if any eval test "
            "is collected without this flag.  No default."
        ),
    )
    group.addoption(
        "--rebuild",
        action="append",
        default=[],
        choices=_REBUILD_CHOICES,
        metavar="PHASE",
        help=(
            "Force re-computation of a cached phase.  Repeatable: "
            "--rebuild conversation --rebuild judgment.  Values:\n"
            "  conversation — rerun the user↔target loop, overwriting "
            "transcript.md, metadata.json, and .clarity-protocol/.  "
            "Invalidates cached judgments (their transcript is gone).\n"
            "  judgment — rerun the judges against the existing "
            "transcript.  Wipes judge_records.json.\n"
            "  all — rm -rf the module directory and start fresh.\n"
            "  none — accept all on-disk artifacts verbatim; do NOT "
            "rerun conversations, do NOT rerun judges, and do NOT "
            "validate the transcript fingerprint against cached "
            "judgments.  No LLM calls are made.  Used to regenerate "
            "summary.md from a shared eval-run produced by someone "
            "else's backend.  Fails noisily if any required artifact "
            "is missing or any assertion lacks a cached verdict.  "
            "Mutually exclusive with the other rebuild values.\n"
            "Default (no flag): resume — reuse every cached artifact "
            "that's consistent with the current inputs."
        ),
    )
    group.addoption(
        "--print-config",
        action="store_true",
        default=False,
        help=(
            "Resolve and print the eval framework's per-role config "
            "(provider, auth mode, endpoint, deployment / model, full "
            "URL for Azure) and exit without running any tests.  Use "
            "this to verify that what's in evals/config.yaml resolves "
            "to the URL you expect — most useful for catching Azure "
            "endpoint or deployment-name mistakes before paying for a run."
        ),
    )


# ---------------------------------------------------------------------------
# Session-level state for summary generation
#
# These dicts are populated by the pytest hooks below and consumed at
# session end to write summary.md.  They live at module scope because
# pytest hooks aren't fixtures and can't request fixture dependencies.
# ---------------------------------------------------------------------------

_test_outcomes: dict[str, dict[str, Any]] = {}
_judge_records: dict[str, list[JudgeRecord]] = {}
_current_test_id: str | None = None
_session_start: float | None = None


def pytest_configure(config: pytest.Config) -> None:
    """Announce the resolved per-role config at session start.

    Runs before collection so the banner appears ahead of any test
    output — useful for catching "wrong model / wrong endpoint"
    mistakes before a long run burns time and tokens.  Load failures
    are swallowed quietly in normal runs (the ``eval_config`` fixture
    will surface them later); ``--print-config`` treats the same
    failure as fatal because the flag's whole purpose is diagnostic.
    """
    # Register the ``advisory`` marker so pytest doesn't warn when
    # an eval imports it from ``evals.framework`` and applies it to
    # a test.  See ``evals.framework.advisory`` for the decorator
    # definition and the makereport hook below for the outcome
    # rewrite.
    config.addinivalue_line(
        "markers",
        "advisory: a test whose failure is informative but should "
        "not block the suite (no contribution to pytest exit code, "
        "rendered as 💡 advisory-failed in summary.md)",
    )
    # Module-level marker: in this test, agent refusal is an
    # acceptable / desired outcome.  Triggers the optional refusal
    # gate in make_conversation_fixture before substantivity, and
    # routes every test in the module to the ``refused`` outcome
    # (a success flavor) when the agent refused cleanly.
    config.addinivalue_line(
        "markers",
        "refusal_acceptable: refusal-by-the-agent is a valid "
        "success path for this test/module (rendered as ✅ refused "
        "in summary.md)",
    )

    print_and_exit = bool(config.getoption("--print-config"))
    try:
        eval_cfg = load_default()
    except Exception as exc:
        if print_and_exit:
            print(
                f"\n[eval] Failed to load evals/config.yaml: {exc}",
                file=sys.stderr,
            )
            pytest.exit("--print-config: load failed", returncode=2)
        return

    print("\n[eval] Resolved configuration:", file=sys.stderr)
    print(describe_resolved_config(eval_cfg), file=sys.stderr)
    print("", file=sys.stderr)

    # Banner for the accept-as-is mode.  Operators forget what flag
    # they passed three hours into a run; printing this once at
    # session start anchors the rest of the output, and an empty
    # summary later won't read as a bug.
    rebuild_raw = config.getoption("--rebuild") or []
    if "none" in rebuild_raw:
        print(
            "[eval] --rebuild=none: using cached artifacts only; "
            "no LLM calls will be made.  Missing cached verdicts "
            "will fail the affected test loudly.",
            file=sys.stderr,
        )
        print("", file=sys.stderr)

    if print_and_exit:
        pytest.exit("--print-config: done", returncode=0)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item],  # noqa: ARG001
) -> None:
    """Require ``--output-dir`` whenever an eval test is collected.

    Fails the session loudly at collection time — before any test
    runs — so the user gets a clear "you forgot the flag" message
    rather than discovering hours into a long run that nothing
    was being recorded.

    Mixed sessions (``pytest tests/ evals/cases/...``) without the
    flag also fail.  Pure unit-test sessions (``pytest tests/``)
    are unaffected because no item matches the eval-cases prefix.
    """
    has_eval_test = any(
        item.nodeid.startswith("evals/cases/") for item in items
    )
    if has_eval_test and not config.getoption("--output-dir"):
        pytest.exit(
            "Eval tests require --output-dir=DIR.\n\n"
            "  Example: pytest evals/cases --output-dir=./eval-runs/my-run\n\n"
            "Pass a path on the command line and re-run.  We don't "
            "default to ./eval-runs/<timestamp>/ anymore — too easy "
            "to miss the directory afterwards, and unit-test runs "
            "were leaving stray empties behind.",
            returncode=2,
        )


def pytest_sessionstart(session: pytest.Session) -> None:  # noqa: ARG001
    """Record session start so the summary can report total wall time."""
    global _session_start
    _session_start = time.monotonic()


def _snapshot_summary(pytest_config: pytest.Config) -> None:
    """Write ``summary.md`` based on the current in-memory state.

    Safe to call at any time — called after each test start, each
    judge check, each test outcome, and at session end.  Failures
    are swallowed so a disk-full or permissions issue can't abort
    a running eval.

    No-ops when ``--output-dir`` wasn't given.  This keeps unit-test
    runs (``pytest tests/``) from generating spurious summary
    artifacts: the conftest's runtest hooks fire for every test in
    the session, but without an output directory there's nowhere
    to write so we just return.
    """
    if not _test_outcomes and not _judge_records:
        return
    outputs_dir = _resolve_output_dir(pytest_config)
    if outputs_dir is None or not outputs_dir.exists():
        return
    try:
        eval_cfg = load_default()
    except Exception:
        eval_cfg = None
    total_seconds = (
        time.monotonic() - _session_start
        if _session_start is not None else None
    )
    try:
        write_summary(
            outputs_dir, _test_outcomes, _judge_records,
            config=eval_cfg,
            total_seconds=total_seconds,
        )
    except Exception as exc:
        print(
            f"  [eval] warning: failed to update summary.md: {exc}",
            file=sys.stderr,
            flush=True,
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _resolve_output_dir(config: pytest.Config) -> Path | None:
    """Compute the output directory, caching on *config* so the fixture
    and the session-finish hook see the same path.

    Returns ``None`` when ``--output-dir`` wasn't given.  Callers
    that need a path either short-circuit (the snapshot/sessionfinish
    hooks) or surface a clear error before they get here (the
    ``output_dir`` fixture and the collection guard, both of which
    fail loudly when an eval test asks for an output dir but none
    was configured).
    """
    cached = getattr(config, "_eval_output_dir", None)
    if cached is not None:
        return cached
    raw: str | None = config.getoption("--output-dir")
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    config._eval_output_dir = path  # type: ignore[attr-defined]
    return path


@pytest.fixture(scope="session")
def rebuild_targets(pytestconfig: pytest.Config) -> frozenset[str]:
    """Phases the user asked to forcibly rebuild.

    Populated from repeated ``--rebuild`` flags on the pytest command
    line.  Consumed by :func:`make_conversation_fixture` — the default
    (empty set) means "resume from disk where possible."  ``"all"``
    subsumes the others.

    ``"none"`` is a separate mode (accept-all-cached, no LLM calls)
    and is mutually exclusive with the other values; combining them
    is rejected at fixture resolution time with a clear error,
    because the intent is ambiguous (does the user want to rerun
    something or not?).
    """
    raw = pytestconfig.getoption("--rebuild") or []
    targets = frozenset(raw)
    if "none" in targets and len(targets) > 1:
        other = sorted(targets - {"none"})
        raise pytest.UsageError(
            f"--rebuild=none cannot be combined with other --rebuild "
            f"values (got: {', '.join(other)}).  --rebuild=none means "
            "'accept all on-disk artifacts verbatim, no LLM calls' "
            "and is mutually exclusive with any rebuild directive."
        )
    return targets


@pytest.fixture(scope="session")
def output_dir(pytestconfig: pytest.Config) -> Path:
    """Root output directory for this eval run.

    Each test's per-module subdirectory (``<category>/<module>/``)
    doubles as its Clarity project directory — protocol files and
    transcripts land there live as the conversation runs.  The
    ``summary.md`` is written at the root at session end.

    REQUIRED: pass ``--output-dir=DIR`` when running eval tests.
    The collection guard (``pytest_collection_modifyitems`` below)
    fails loudly before any test runs if eval tests were collected
    without the flag, so reaching this fixture without one means a
    test outside the normal collection path requested it — also
    a hard error.
    """
    path = _resolve_output_dir(pytestconfig)
    if path is None:
        pytest.exit(
            "Eval tests require --output-dir=DIR.  This fixture was "
            "requested without one — pass --output-dir on the pytest "
            "command line.",
            returncode=2,
        )
    return path


@pytest.fixture(scope="session")
def clarity_agent_dir() -> Path:
    """Path to the clarity-agent installation (this repo root)."""
    return _repo_root()


@pytest.fixture(scope="session")
def eval_config(pytestconfig: pytest.Config) -> EvalConfig:  # noqa: ARG001 — keep signature stable
    """Load ``evals/config.yaml`` once per pytest session.

    If required credentials are missing, stops the entire eval run
    immediately with a clear error message.  Silent skipping hides
    configuration problems; a loud failure makes them obvious.

    We check credentials for every configured role even when resume
    would normally avoid invoking some of them — predicting which
    backends will actually be called requires knowing which cached
    artifacts are valid, which isn't knowable until the fixtures run.
    """
    config = load_default()
    missing = missing_credentials(config)
    if missing:
        pytest.exit(
            "Missing credentials for eval roles:\n  "
            + "\n  ".join(missing)
            + "\n\nEither configure the providers (settings.json / keyring / env)\n"
            "or edit evals/config.yaml to use a provider you have configured.",
            returncode=2,
        )
    return config


@pytest.fixture
def target_session(
    tmp_path: Path,
    eval_config: EvalConfig,
    clarity_agent_dir: Path,
) -> Iterator[TargetSession]:
    """Fresh ClaritySession in a temp dir, using the target LLM backend.

    Yields a :class:`TargetSession`; closes it after the test.

    This function-scoped fixture is for tests that need an independent
    target per assertion.  Prefer the module-scoped
    :func:`make_conversation_fixture` for shared conversations.
    """
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    backend, llm_config = eval_config.create_backend(
        slot="target",
        project_dir=project_dir,
        clarity_agent_dir=clarity_agent_dir,
    )
    backend.connect()

    session = TargetSession(
        project_dir=project_dir,
        clarity_agent_dir=clarity_agent_dir,
        backend=backend,
        llm_config=llm_config,
    )
    try:
        yield session
    finally:
        session.close()
        backend.disconnect()


@pytest.fixture
def user_factory(
    eval_config: EvalConfig,
    clarity_agent_dir: Path,
    tmp_path: Path,
) -> Iterator[Callable[..., SimulatedUser]]:
    """Returns a function that constructs a :class:`SimulatedUser`.

    Usage::

        user = user_factory(goal="...", persona="...", situation="...")
        result = user.converse_with(target_session, max_turns=10)
    """
    created: list = []  # keep backends alive for disconnect

    def _make(
        *, goal: str, persona: str, situation: str = "",
    ) -> SimulatedUser:
        backend, _ = eval_config.create_backend(
            slot="user",
            project_dir=tmp_path,
            clarity_agent_dir=clarity_agent_dir,
        )
        backend.connect()
        created.append(backend)
        return SimulatedUser(
            goal=goal,
            persona=persona,
            backend=backend,
            situation=situation,
        )

    yield _make

    for backend in created:
        try:
            backend.disconnect()
        except Exception:
            pass


@pytest.fixture(scope="session")
def judge(
    eval_config: EvalConfig,
    clarity_agent_dir: Path,
    tmp_path_factory: pytest.TempPathFactory,
    pytestconfig: pytest.Config,
) -> Judge:
    """Shared judge instance for the pytest session.

    Stateless — each ``judge.check()`` call uses a fresh backend.
    Records every check into the session-level ``_judge_records`` dict,
    attributed to the currently-running test, so the run summary can
    reconstruct what was asked and how the judge replied.

    Each recorded check also triggers a ``summary.md`` rewrite so
    that an interrupt loses no judge output.
    """
    judge_project_dir = tmp_path_factory.mktemp("judge")

    def _record(record: JudgeRecord) -> None:
        test_id = _current_test_id or "<unknown>"
        _judge_records.setdefault(test_id, []).append(record)
        _snapshot_summary(pytestconfig)

    def _get_current_test_id() -> str | None:
        # Read the module-level global so the Judge can attribute
        # cached/recorded entries without each module-scoped fixture
        # threading the test nodeid through every check() call.
        return _current_test_id

    return Judge(
        eval_config,
        project_dir=judge_project_dir,
        clarity_agent_dir=clarity_agent_dir,
        recorder=_record,
        current_test_getter=_get_current_test_id,
    )


# ---------------------------------------------------------------------------
# Hooks: collect outcomes and write the run summary at session end
# ---------------------------------------------------------------------------

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):  # noqa: ARG001 — hook signature
    """Track the currently-running test so the judge can attribute records.

    Also snapshots the summary on test start so a test visible in
    ``summary.md`` as "in progress" — this way an interrupt mid-test
    leaves a summary that shows which test was running.

    Only applies to legacy cases under ``evals/cases/``.  Non-legacy
    paths (e.g. ``evals/cases_rampart/``) bypass the legacy summary
    machinery entirely.
    """
    global _current_test_id
    if item.nodeid.startswith("evals/cases/"):
        _current_test_id = item.nodeid
        _snapshot_summary(item.config)
    yield
    if item.nodeid.startswith("evals/cases/"):
        _current_test_id = None


def _classify_error(call) -> str:
    """Return the error category for a failed test.

    - ``"refused"`` — the framework's refusal gate fired for a
      ``@refusal_acceptable`` module.  This is a SUCCESS flavor
      (the agent refused cleanly, which is the desired outcome
      for these tests), routed to its own bucket.  Does NOT
      trigger session abort.
    - ``"smoke_failed"`` — the framework's smoke check rejected the
      module's conversation (drift, role failure, etc.).  Routed to a
      dedicated outcome bucket and does NOT trigger session abort, so
      one bad module doesn't take down every module after it.
    - ``"assertion"`` — an ``assert`` inside the test body.
    - ``"infra"`` — anything else (fixture setup error, backend crash,
      timeout, etc.).  Triggers session abort so a wedged backend
      isn't reported once per test in the module.
    """
    if call.excinfo is None:
        return "infra"
    if call.excinfo.errisinstance(AgentRefusedError):
        return "refused"
    if call.excinfo.errisinstance(SmokeCheckFailedError):
        return "smoke_failed"
    return "assertion" if call.excinfo.type is AssertionError else "infra"


def _extract_smoke_reasoning(call) -> str | None:
    """Pull the judge's reasoning off a SmokeCheckFailedError, if any.

    Stored on the exception by ``Judge.goal_pursued_check`` so the summary
    can render WHY the smoke check failed, not just that it did.
    """
    if call is None or call.excinfo is None:
        return None
    # Both SmokeCheckFailedError (a failure) and AgentRefusedError
    # (a success short-circuit) carry a ``reasoning`` attribute the
    # report renders.  Recognize either so the same downstream
    # field name works for both.
    if not call.excinfo.errisinstance(
        (SmokeCheckFailedError, AgentRefusedError),
    ):
        return None
    exc = call.excinfo.value
    return getattr(exc, "reasoning", None)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture pass/fail/skip outcome for each test's ``call`` phase.

    Distinguishes assertion failures (expected, part of normal test
    output) from infrastructure failures (fixture setup errors, backend
    crashes, etc).  For infra failures we:

    - Record the full traceback without truncation so the root cause is
      visible in ``summary.md``.
    - Fail fast: calling :func:`pytest.exit` stops the run.  Without
      this, a fixture that can't connect to its backend would produce
      the same error repeated once per test function in the module,
      burying the real problem in noise.

    Only applies to legacy cases under ``evals/cases/`` — the RAMPART
    path (``evals/cases_rampart/``) uses standard pytest reporting via
    its own conftest, and shouldn't be intercepted by this hook.
    """
    outcome = yield

    if not item.nodeid.startswith("evals/cases/"):
        # Pass through for non-legacy paths (e.g. evals/cases_rampart/).
        return

    report = outcome.get_result()

    if report.when == "call":
        error_type: str | None = None
        if report.outcome == "failed":
            error_type = _classify_error(call)

        # @advisory interception.  If a test marked ``@advisory``
        # failed an assertion, route it to the ``advisory_failed``
        # outcome bucket and rewrite pytest's report outcome to
        # ``"passed"`` so the suite's exit code stays 0.  Only
        # applies to assertion-style failures — infrastructure
        # errors and smoke failures are always blocking, even on an
        # advisory-marked test, because they signal something broken
        # about the run rather than a behavior the eval is probing.
        advisory_marker = item.get_closest_marker("advisory")
        outcome_label = report.outcome
        advisory_issue: str | None = None
        if (
            advisory_marker is not None
            and report.outcome == "failed"
            and error_type == "assertion"
        ):
            outcome_label = "advisory_failed"
            # Rewrite the pytest report so the test contributes to
            # neither pytest's exit code nor its terminal summary's
            # "failed" line.  Our own summary tracks the original
            # failure via ``outcome_label`` above.
            #
            # Do NOT set ``report.wasxfail`` here.  It looks like a
            # convenient way to make ``-v`` print "ADVISORY" next
            # to the test, but pytest's terminal reporter then
            # reclassifies the result as XPASSED — polluting the
            # session line ("12 xpassed") with our advisory tests.
            # A clean ``"passed"`` outcome is enough; the real
            # advisory accounting lives in summary.md.
            report.outcome = "passed"
            # Optional issue-tracker URL passed to the marker:
            # ``@advisory("https://...")`` (positional) or
            # ``@advisory(issue="https://...")`` (keyword).  Stored
            # as-is on _test_outcomes so the report can render it
            # next to the failure.  We only capture it on the
            # actual advisory_failed path — a passing advisory test
            # has no failure to point at, so the URL is noise.
            if advisory_marker.args:
                advisory_issue = str(advisory_marker.args[0])
            elif "issue" in advisory_marker.kwargs:
                advisory_issue = str(advisory_marker.kwargs["issue"])

        _test_outcomes[item.nodeid] = {
            "outcome": outcome_label,
            "duration": report.duration,
            "error": (
                report.longreprtext if outcome_label != "passed" else None
            ),
            "error_type": error_type,
            "advisory_issue": advisory_issue,
        }
        _snapshot_summary(item.config)

        if error_type == "infra":
            pytest.exit(
                f"Infrastructure failure in {item.nodeid} — see "
                f"summary.md in the run's output directory.",
                returncode=1,
            )
    elif report.when == "setup" and report.outcome in ("failed", "skipped"):
        # Setup-phase failures usually mean the fixture (backend,
        # conversation runner, etc.) couldn't get the test off the
        # ground.  Three paths matter:
        #
        # 1. AgentRefusedError from the refusal-acceptable gate:
        #    the agent declined cleanly, which is the desired
        #    outcome for these tests.  Reported as ``refused`` (a
        #    SUCCESS flavor), recorded for the whole module.  Like
        #    smoke_failed, does NOT abort the run, AND does NOT
        #    contribute to pytest's exit code — we rewrite the
        #    report outcome to "passed" so pytest sees a clean run.
        #
        # 2. SmokeCheckFailedError from any of the three framework
        #    gates (persona-adoption, substantivity, goal-pursued):
        #    the conversation ran but downstream assertions can't
        #    meaningfully run on it.  Reported as ``smoke_failed``
        #    (its own bucket), recorded for the whole module, does
        #    NOT abort the run — other modules' samples may be fine.
        #
        # 3. Any other setup failure: real infrastructure problem
        #    (fixture exception, backend crash).  Aborts the session
        #    via pytest.exit so a wedged backend doesn't repeat the
        #    same error once per test in the module.
        if report.outcome == "failed":
            error_type = _classify_error(call)
        else:
            error_type = None
        smoke_reasoning = _extract_smoke_reasoning(call)
        if error_type == "refused":
            outcome_label = "refused"
            # Pytest skip semantics: setup-skipped → call phase
            # doesn't run, test doesn't count toward failure / exit
            # code.  We can't use ``"passed"`` here (the @advisory
            # trick) because passed-setup makes pytest proceed to
            # the call phase, which then KeyErrors on the missing
            # ``result`` fixture argument (the fixture raised, so
            # never produced a value).  Skipped-setup is the right
            # signal — pytest skips the call cleanly and exits 0.
            report.outcome = "skipped"
            # Replace the AgentRefusedError traceback with a short
            # human-readable reason — pytest renders ``longrepr``
            # as the skip reason in its terminal output, and we
            # don't want a stack trace appearing for what is
            # semantically a success short-circuit.
            #
            # Format MUST be a 3-tuple ``(filename, lineno, reason)``
            # — that's what pytest's ``pytest.skip()`` produces and
            # what the terminal reporter expects.  A plain string
            # crashes ``_pytest.terminal._get_raw_skip_reason`` with
            # an AssertionError because that helper does
            # ``assert isinstance(report.longrepr, tuple)``.
            short_reason = smoke_reasoning or "agent refused"
            location = getattr(item, "location", None)
            if location and len(location) >= 2:
                filename, lineno = location[0], location[1] or 0
            else:
                filename, lineno = (
                    str(getattr(item, "fspath", "<refused>")), 0,
                )
            report.longrepr = (
                filename, lineno, f"refused: {short_reason}",
            )
        elif error_type == "smoke_failed":
            outcome_label = "smoke_failed"
            # Same skipped-setup trick as the refused branch above:
            # without rewriting the outcome, pytest renders these as
            # ERROR in the terminal (one line per test in the module)
            # which buries the rest of the run.  ``"skipped"`` plus
            # a short reason matches our own classification — the
            # test never ran (no signal), the suite isn't blocked,
            # and pytest's terminal stays readable.  summary.md
            # still surfaces these as ``smoke_failed`` in the
            # no-signal bucket.
            report.outcome = "skipped"
            short_reason = smoke_reasoning or "smoke check failed"
            location = getattr(item, "location", None)
            if location and len(location) >= 2:
                filename, lineno = location[0], location[1] or 0
            else:
                filename, lineno = (
                    str(getattr(item, "fspath", "<smoke-failed>")), 0,
                )
            report.longrepr = (
                filename, lineno, f"smoke-failed: {short_reason}",
            )
        else:
            outcome_label = report.outcome
        _test_outcomes.setdefault(item.nodeid, {
            "outcome": outcome_label,
            "duration": report.duration,
            "error": (
                report.longreprtext if report.outcome == "failed" else None
            ),
            "error_type": error_type,
            "smoke_reasoning": smoke_reasoning,
        })
        _snapshot_summary(item.config)

        if report.outcome == "failed" and error_type == "infra":
            pytest.exit(
                f"Infrastructure failure in {item.nodeid} — see "
                f"summary.md in the run's output directory.",
                returncode=1,
            )


def pytest_sessionfinish(
    session: pytest.Session, exitstatus: int,  # noqa: ARG001
) -> None:
    """Write the final ``summary.md`` and print its path."""
    if not _test_outcomes and not _judge_records:
        return
    outputs_dir = _resolve_output_dir(session.config)
    if outputs_dir is None or not outputs_dir.exists():
        return

    _snapshot_summary(session.config)
    summary_path = outputs_dir / "summary.md"
    print(
        f"\n  [eval] Run summary: {summary_path}",
        file=sys.stderr,
        flush=True,
    )
