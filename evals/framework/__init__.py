"""Integration test framework for Clarity Agent.

Public entry points:
    - :class:`SimulatedUser` — LLM-driven user persona
    - :class:`TargetSession` — wraps a ClaritySession as the system under test
    - :class:`Judge` — LLM-backed assertions
    - :class:`SessionResult`, :class:`Turn` — conversation outputs
    - :class:`EvalConfig` — role-to-backend configuration
    - :data:`advisory` — decorator marking a test whose failure is
      informative but should not block the suite (see below)
"""

from __future__ import annotations

import pytest

from evals.framework.config import (
    EvalConfig,
    RoleConfig,
    describe_resolved_config,
    load_default,
    missing_credentials,
)
from evals.framework.judge import (
    AgentRefusedError,
    Judge,
    SmokeCheckFailedError,
)
from evals.framework.resume import JudgeCache, compute_fingerprint
from evals.framework.runner import (
    make_conversation_fixture,
    protocol_content,
    run_conversation,
)
from evals.framework.target import TargetSession
from evals.framework.types import SessionResult, Turn
from evals.framework.user import SimulatedUser

# Decorator for tests whose failure is informative but should not
# block the suite — e.g. an eval that probes an aspirational
# behavior we'd like Clarity to exhibit but aren't ready to gate on.
# Apply above the test function::
#
#     @advisory
#     def test_something_aspirational(result, judge):
#         assert judge.check(...)
#
# Optionally pass an issue-tracker URL — positional or via the
# ``issue=`` keyword — to link the failure to its tracking ticket::
#
#     @advisory("https://github.com/microsoft/clarity-agent/issues/174")
#     def test_x(...): ...
#
#     @advisory(issue="https://github.com/microsoft/clarity-agent/issues/174")
#     def test_y(...): ...
#
# GitHub issue URLs render as ``#NNN`` in summary.md (compact in the
# table cell, full link in the per-test details).  Other URLs (JIRA,
# Linear, internal trackers) render as a 🔗 chain-link in the table
# and the full URL in details.
#
# When such a test fails, the conftest's ``pytest_runtest_makereport``
# hook routes the result to a dedicated ``advisory_failed`` outcome
# bucket (rendered as 💡 in summary.md) and rewrites pytest's report
# outcome to ``"passed"``, so the test does NOT contribute to pytest's
# exit code.  Passes are reported as normal passes.
#
# Implemented as a pytest mark so it composes with parametrize, with
# class-level marks, and with pytest's existing tooling — but
# re-exported here so eval authors don't need to know about pytest's
# marker namespace.
advisory = pytest.mark.advisory


# Module-level marker indicating that, in this test, it's an
# acceptable outcome for the assistant to refuse to engage with the
# user's stated goal.  Apply at the top of the test file::
#
#     from evals.framework import refusal_acceptable
#
#     pytestmark = refusal_acceptable
#
# (Per-test usage works too — ``@refusal_acceptable`` on individual
# test functions — but the typical case is whole-file: the test's
# scenario is one where the agent saying "no, I can't help with
# this" is the desired outcome, not a failure.)
#
# When a marked module's conversation completes, the framework runs
# a refusal-check gate BEFORE the usual substantivity / goal-pursued
# gates.  If the judge agrees the agent refused cleanly, every test
# in the module is short-circuited to the ``refused`` outcome (a
# success flavor — same ✅ icon as a clean pass, distinct text
# label "refused").  If the judge says the agent engaged, the
# framework falls through to its normal gates and the test runs as
# usual.
refusal_acceptable = pytest.mark.refusal_acceptable

__all__ = [
    "AgentRefusedError",
    "EvalConfig",
    "Judge",
    "JudgeCache",
    "RoleConfig",
    "SessionResult",
    "SimulatedUser",
    "SmokeCheckFailedError",
    "TargetSession",
    "Turn",
    "advisory",
    "compute_fingerprint",
    "describe_resolved_config",
    "load_default",
    "make_conversation_fixture",
    "missing_credentials",
    "protocol_content",
    "refusal_acceptable",
    "run_conversation",
]
