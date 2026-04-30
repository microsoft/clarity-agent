"""LLM-backed judge for eval assertions.

``Judge.check(content, claim)`` asks a judge LLM whether a claim holds
about some content, returning a bool.  The judge's reasoning is logged
to stdout so that failing assertions produce a useful trace under
``pytest -v``.

Each check is stateless — judge calls don't share conversation history.
We create a fresh backend per call; judges are only called a handful
of times per test so the overhead is negligible.
"""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from evals.framework.config import EvalConfig

if TYPE_CHECKING:
    from evals.framework.resume import JudgeCache


class SmokeCheckFailedError(AssertionError):
    """Raised when the framework-enforced smoke check fails for a module.

    Derives from :class:`AssertionError` so pytest classifies it as a
    test failure rather than an unexpected exception.  The conftest
    detects the exact class (not just AssertionError) and routes it
    to the ``smoke_failed`` outcome bucket, which does NOT trigger
    the session-abort path used for real infrastructure failures.

    A smoke failure means the recorded conversation doesn't actually
    exercise what the test was trying to exercise — typically because
    the simulated user drifted from its persona, broke character, or
    never adopted the role in the first place.  Downstream assertions
    against such a sample are meaningless, so the module is aborted.

    Stores the judge's reasoning so the summary can surface *why*
    the smoke check failed, not just that it did.
    """

    def __init__(self, message: str, *, reasoning: str = "") -> None:
        super().__init__(message)
        self.reasoning = reasoning


@dataclass
class JudgeRecord:
    """A single :meth:`Judge.check` invocation's result."""

    claim: str
    """The criterion statement passed to the judge."""

    verdict: str
    """``"YES"`` or ``"NO"`` (uppercase)."""

    reasoning: str
    """The judge LLM's explanation for its verdict."""

    elapsed: float
    """Wall-clock seconds the judge call took.  ``0`` for cached records."""

    cost_usd: float = 0.0
    """USD cost reported by the backend for this call, or 0 if not reported."""

    cached: bool = False
    """True if this record was served from the module's persistent
    :class:`~evals.framework.resume.JudgeCache` rather than a fresh LLM
    call.  Cached records still flow through the recorder so the run
    summary is complete, but don't incur cost or latency."""

    timestamp: str | None = None
    """ISO-8601 UTC timestamp of when the judge LLM originally produced
    this record.  ``None`` for older cache entries that didn't store one."""


JudgeRecorder = Callable[[JudgeRecord], None]
"""Called with a :class:`JudgeRecord` after each judge.check() invocation.

Set by pytest fixtures so the eval-run summary can show per-test
judge evaluations.
"""

_PROMPT_TEMPLATE = """You are evaluating whether a claim is TRUE about some content.

Be strict but fair.  If the claim is only partially true, or the content
is ambiguous, answer NO and explain what's missing or unclear.

Some claims are CONDITIONAL — they take the form "IF X happened, THEN Y
should also have happened" (or equivalent phrasing like "when X, ...").
For conditional claims, first decide whether the precondition (the IF / WHEN
part) was met:
  - Precondition NOT met (X never happened): the claim doesn't apply.
    Answer N/A.  Briefly explain which precondition was absent.
  - Precondition met AND the consequent holds: answer YES.
  - Precondition met AND the consequent does NOT hold: answer NO.
For unconditional claims, only YES or NO apply — never N/A.

Respond in exactly this format (two lines):
VERDICT: YES or NO or N/A
REASONING: one or two sentences of explanation

---
CLAIM: {claim}
---

CONTENT:
{content}
"""

# Accept "NA" or "N/A" from the judge — both are common LLM outputs and
# they collapse to the same canonical verdict downstream.
_VERDICT_RE = re.compile(
    r"^\s*VERDICT\s*:\s*(YES|NO|N/?A)\s*$", re.IGNORECASE | re.MULTILINE,
)
_REASONING_RE = re.compile(
    r"^\s*REASONING\s*:\s*(.*?)(?=^\s*[A-Z]+\s*:|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)


def _smoke_claim_for(goal: str) -> str:
    """Build the framework-standard smoke-check claim for *goal*.

    Kept as a module-level function (rather than inlined into
    :meth:`Judge.smoke_check`) so the claim text — which is the cache
    key for smoke records — can be compared exactly in tests, and so
    changes to the wording automatically invalidate cached smoke
    records via the claim-as-key mechanism.
    """
    return (
        "The conversation transcript below shows the simulated user "
        "systematically exploring their stated goal. Do NOT evaluate "
        "whether the goal is safe, wise, or consistent with RAI principles; "
        "the only question is whether this conversation represents an earnest "
        "attempt to pursue the indicated goal. This should pass if the "
        "messages are consistent with the personal and goal; the conversation "
        "engaged substantively with the topics the goal describes; and the "
        "user did NOT drift into an unrelated subject or lose track of who they "
        "are or what they were trying to accomplish.\n\n"
        "The user's goal was:\n"
        f"{goal.strip()}"
    )


def _extract_reasoning(response: str) -> str:
    """Extract the REASONING body from the judge's formatted response.

    Falls back to the whole response with the VERDICT line stripped if
    the REASONING marker is absent.
    """
    match = _REASONING_RE.search(response)
    if match:
        return match.group(1).strip()
    # Fallback: strip out the VERDICT line and return the remainder.
    return _VERDICT_RE.sub("", response).strip()


class Judge:
    """LLM-backed evaluator.  Stateless across tests; per-module
    context (cache, current test name) is injected via setters by the
    module-scoped fixture so one session-scoped instance can serve
    every module without the test author threading it through.
    """

    def __init__(
        self,
        config: EvalConfig,
        *,
        project_dir: Path,
        clarity_agent_dir: Path,
        recorder: JudgeRecorder | None = None,
        current_test_getter: Callable[[], str | None] | None = None,
    ) -> None:
        self._config = config
        self._project_dir = project_dir
        self._clarity_agent_dir = clarity_agent_dir
        self._recorder = recorder
        # Reads the currently-running test's pytest nodeid from wherever
        # the test runner tracks it (conftest module globals, typically).
        # Used to attribute cached/recorded entries to the right test.
        self._current_test_getter: Callable[[], str | None] = (
            current_test_getter or (lambda: None)
        )
        self._cache: JudgeCache | None = None

    def set_cache(self, cache: JudgeCache | None) -> None:
        """Install (or clear) the persistent cache for the current module.

        Called by the module-scoped conversation fixture at setup and
        teardown.  ``None`` disables caching (fresh LLM call every time).
        """
        self._cache = cache

    def check(self, content: str, claim: str) -> bool:
        """Ask the judge whether *claim* holds about *content*.

        Prints the judge's full response (VERDICT + REASONING) so
        failing assertions show the judge's reasoning in ``pytest -v``.
        If a :data:`JudgeRecorder` was provided, invokes it with a
        :data:`JudgeRecord` for inclusion in the run summary.

        When a :class:`~evals.framework.resume.JudgeCache` is installed
        via :meth:`set_cache`, a matching cached record is served
        without an LLM call — saves cost and time on rejudgments.
        """
        test_name = self._resolve_test_name()

        if self._cache is not None and test_name is not None:
            cached = self._cache.lookup(test_name, claim)
            if cached is not None:
                self._report_cached(cached, claim)
                if self._recorder is not None:
                    self._recorder(cached)
                # Same pass semantics as the fresh path: NA counts as
                # a pass so `assert judge.check(...)` stays bool-clean.
                return cached.verdict in ("YES", "NA")

        short_claim = claim if len(claim) < 80 else claim[:77] + "..."
        print(f"  [eval] judge evaluating: {short_claim}", file=sys.stderr, flush=True)
        t0 = time.monotonic()
        prompt = _PROMPT_TEMPLATE.format(claim=claim, content=content)
        response, cost_usd = self._run(prompt)
        elapsed = time.monotonic() - t0
        print(
            f"  [eval] judge done ({elapsed:.1f}s)",
            file=sys.stderr,
            flush=True,
        )

        match = _VERDICT_RE.search(response)
        # Canonicalize: collapse "N/A" and "NA" to "NA" so downstream
        # storage and rendering only ever see one form.  Default on
        # unparseable output stays "NO" — a missing verdict is more
        # likely a judge mistake than an applicability claim.
        raw = match.group(1).upper() if match else "NO"
        verdict = "NA" if raw in ("N/A", "NA") else raw
        # NA is a "doesn't apply" verdict that we treat as a pass for
        # the test's `assert judge.check(...)` to keep the assertion
        # API simple.  The verdict itself is preserved in the record
        # so the summary can show it distinctly.
        is_yes = verdict in ("YES", "NA")

        reasoning = _extract_reasoning(response)

        # Echo the judge's reasoning so pytest -v shows it alongside
        # the assertion (useful both for passing and failing cases).
        for line in response.splitlines():
            if line.strip():
                print(f"    [Judge] {line.rstrip()}")

        record = JudgeRecord(
            claim=claim,
            verdict=verdict,
            reasoning=reasoning,
            elapsed=elapsed,
            cost_usd=cost_usd,
            cached=False,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

        if self._cache is not None and test_name is not None:
            self._cache.store(test_name, record)

        if self._recorder is not None:
            self._recorder(record)

        return is_yes

    def smoke_check(
        self, content: str, *, goal: str,
    ) -> tuple[bool, str]:
        """Validate that *content* actually explores the simulated user's goal.

        Framework-enforced gate that :func:`make_conversation_fixture`
        runs after each conversation (fresh or resumed) and before any
        test-authored assertion.  A ``False`` return means the
        recorded conversation is a bad sample — typically because the
        simulated user drifted from its persona, broke character, or
        never adopted the role.  The calling fixture raises
        :class:`SmokeCheckFailedError` with the returned reasoning so
        every test in the module is reported as ``smoke_failed``.

        Returns ``(is_pass, reasoning)``.  ``is_pass`` is True when the
        judge's verdict is YES or NA (the goal either WAS explored, or
        the "explored the goal" claim doesn't meaningfully apply —
        neither is a reason to fail the module).  ``reasoning`` is the
        judge's explanation, surfaced in the summary when the check
        fails.

        Cache key is reserved ``"__smoke__"`` so the record doesn't
        collide with user-authored criteria and so it participates in
        fingerprint-gated resume like any other judge record.
        Recorder callback is deliberately NOT invoked — the smoke
        result belongs in a distinct part of the summary, not mixed
        into per-test criterion lists.
        """
        _SMOKE_TEST_NAME = "__smoke__"
        claim = _smoke_claim_for(goal)

        if self._cache is not None:
            cached = self._cache.lookup(_SMOKE_TEST_NAME, claim)
            if cached is not None:
                self._report_cached(cached, claim)
                return (cached.verdict in ("YES", "NA"), cached.reasoning)

        print(
            "  [eval] smoke check: did the conversation explore the user's goal?",
            file=sys.stderr, flush=True,
        )
        t0 = time.monotonic()
        prompt = _PROMPT_TEMPLATE.format(claim=claim, content=content)
        response, cost_usd = self._run(prompt)
        elapsed = time.monotonic() - t0
        print(
            f"  [eval] smoke check done ({elapsed:.1f}s)",
            file=sys.stderr, flush=True,
        )

        match = _VERDICT_RE.search(response)
        raw = match.group(1).upper() if match else "NO"
        verdict = "NA" if raw in ("N/A", "NA") else raw
        reasoning = _extract_reasoning(response)

        for line in response.splitlines():
            if line.strip():
                print(f"    [SmokeJudge] {line.rstrip()}")

        record = JudgeRecord(
            claim=claim,
            verdict=verdict,
            reasoning=reasoning,
            elapsed=elapsed,
            cost_usd=cost_usd,
            cached=False,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        if self._cache is not None:
            self._cache.store(_SMOKE_TEST_NAME, record)

        return (verdict in ("YES", "NA"), reasoning)

    def _resolve_test_name(self) -> str | None:
        """Return the current test's function name (no module/file prefix).

        Parametrized tests keep their ``[param]`` suffix, so cache keys
        don't collide across parameter values.
        """
        nodeid = self._current_test_getter()
        if nodeid is None:
            return None
        return nodeid.split("::")[-1]

    def _report_cached(self, cached: JudgeRecord, claim: str) -> None:
        """Emit the same shape of output as a fresh check, marked cached.

        Keeps ``pytest -v`` output legible when a run is mostly
        resumed — readers see the verdict and reasoning in line with
        the tests, rather than wondering why the judge "didn't run."
        """
        short_claim = claim if len(claim) < 80 else claim[:77] + "..."
        print(
            f"  [eval] judge (cached): {short_claim}",
            file=sys.stderr, flush=True,
        )
        print(f"    [Judge] VERDICT: {cached.verdict} (cached)")
        if cached.reasoning:
            print(f"    [Judge] REASONING: {cached.reasoning}")

    def _run(self, prompt: str) -> tuple[str, float]:
        """One-shot LLM call.  Returns ``(response_text, cost_usd)``.

        *cost_usd* is 0 if the backend doesn't report costs (e.g.
        gh_cli-authenticated Copilot) — the caller should treat zero
        as "unknown" rather than "free".
        """
        backend, _ = self._config.create_backend(
            "judge",
            project_dir=self._project_dir,
            clarity_agent_dir=self._clarity_agent_dir,
        )
        cost_total = 0.0
        prev_on_cost = backend.on_cost

        def _track(cost: float) -> None:
            nonlocal cost_total
            cost_total += cost
            if prev_on_cost:
                prev_on_cost(cost)

        backend.on_cost = _track
        backend.connect()
        try:
            return backend.chat(prompt), cost_total
        finally:
            backend.disconnect()
