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
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from evals.framework import (
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


_REBUILD_CHOICES = ("conversation", "judgment", "all")


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
            "Default: ./eval-runs/<timestamp>/."
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

    if print_and_exit:
        pytest.exit("--print-config: done", returncode=0)


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
    """
    if not _test_outcomes and not _judge_records:
        return
    outputs_dir = _resolve_output_dir(pytest_config)
    if not outputs_dir.exists():
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

def _resolve_output_dir(config: pytest.Config) -> Path:
    """Compute the output directory, caching on *config* so the fixture
    and the session-finish hook see the same path.
    """
    cached = getattr(config, "_eval_output_dir", None)
    if cached is not None:
        return cached
    raw: str | None = config.getoption("--output-dir")
    if not raw:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        raw = f"./eval-runs/{timestamp}"
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
    """
    raw = pytestconfig.getoption("--rebuild") or []
    return frozenset(raw)


@pytest.fixture(scope="session")
def output_dir(pytestconfig: pytest.Config) -> Path:
    """Root output directory for this eval run.

    Each test's per-module subdirectory (``<category>/<module>/``)
    doubles as its Clarity project directory — protocol files and
    transcripts land there live as the conversation runs.  The
    ``summary.md`` is written at the root at session end.

    Default: ``./eval-runs/<YYYYmmdd-HHMMSS>/``.  Override with
    ``--output-dir=DIR``.
    """
    return _resolve_output_dir(pytestconfig)


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
        "target",
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
            "user",
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
    """
    global _current_test_id
    _current_test_id = item.nodeid
    _snapshot_summary(item.config)
    yield
    _current_test_id = None


def _classify_error(call) -> str:
    """Return the error category for a failed test.

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
    if call.excinfo.errisinstance(SmokeCheckFailedError):
        return "smoke_failed"
    return "assertion" if call.excinfo.type is AssertionError else "infra"


def _extract_smoke_reasoning(call) -> str | None:
    """Pull the judge's reasoning off a SmokeCheckFailedError, if any.

    Stored on the exception by ``Judge.smoke_check`` so the summary
    can render WHY the smoke check failed, not just that it did.
    """
    if call is None or call.excinfo is None:
        return None
    if not call.excinfo.errisinstance(SmokeCheckFailedError):
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
    """
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        error_type: str | None = None
        if report.outcome == "failed":
            error_type = _classify_error(call)
        _test_outcomes[item.nodeid] = {
            "outcome": report.outcome,
            "duration": report.duration,
            "error": (
                report.longreprtext if report.outcome == "failed" else None
            ),
            "error_type": error_type,
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
        # ground.  Two paths now matter:
        #
        # 1. SmokeCheckFailedError from the framework smoke check:
        #    the conversation ran but didn't actually exercise the
        #    persona's goal.  Reported as ``smoke_failed`` (its own
        #    bucket), recorded for the whole module, does NOT abort
        #    the run — other modules' samples may be fine.
        #
        # 2. Any other setup failure: real infrastructure problem
        #    (fixture exception, backend crash).  Aborts the session
        #    via pytest.exit so a wedged backend doesn't repeat the
        #    same error once per test in the module.
        if report.outcome == "failed":
            error_type = _classify_error(call)
        else:
            error_type = None
        outcome_label = (
            "smoke_failed" if error_type == "smoke_failed"
            else report.outcome
        )
        smoke_reasoning = _extract_smoke_reasoning(call)
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
    if not outputs_dir.exists():
        return

    _snapshot_summary(session.config)
    summary_path = outputs_dir / "summary.md"
    print(
        f"\n  [eval] Run summary: {summary_path}",
        file=sys.stderr,
        flush=True,
    )
