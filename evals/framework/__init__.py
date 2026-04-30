"""Integration test framework for Clarity Agent.

Public entry points:
    - :class:`SimulatedUser` — LLM-driven user persona
    - :class:`TargetSession` — wraps a ClaritySession as the system under test
    - :class:`Judge` — LLM-backed assertions
    - :class:`SessionResult`, :class:`Turn` — conversation outputs
    - :class:`EvalConfig` — role-to-backend configuration
"""

from __future__ import annotations

from evals.framework.config import (
    EvalConfig,
    RoleConfig,
    describe_resolved_config,
    load_default,
    missing_credentials,
)
from evals.framework.judge import Judge, SmokeCheckFailedError
from evals.framework.resume import JudgeCache, compute_fingerprint
from evals.framework.runner import (
    make_conversation_fixture,
    protocol_content,
    run_conversation,
)
from evals.framework.target import TargetSession
from evals.framework.types import SessionResult, Turn
from evals.framework.user import SimulatedUser

__all__ = [
    "EvalConfig",
    "Judge",
    "JudgeCache",
    "RoleConfig",
    "SessionResult",
    "SimulatedUser",
    "SmokeCheckFailedError",
    "TargetSession",
    "Turn",
    "compute_fingerprint",
    "describe_resolved_config",
    "load_default",
    "make_conversation_fixture",
    "missing_credentials",
    "protocol_content",
    "run_conversation",
]
