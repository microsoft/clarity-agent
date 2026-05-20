"""RAMPART adapter for clarity-agent.

Exposes ``ClaritySession`` as a RAMPART ``AgentAdapter`` so eval
cases written against RAMPART's public API can drive the same
target as the legacy ``evals/framework/`` harness.  Exports the
adapter classes, the application manifest, and a thin wrapper
around ``evals.framework.config`` for loading ``evals/config.yaml``.
"""

from __future__ import annotations

from evals.rampart_adapter.adapter import (
    ClaritySessionAdapter,
    ClaritySessionSession,
)
from evals.rampart_adapter.config import (
    build_target_backend,
    load_eval_config,
)
from evals.rampart_adapter.manifest import CLARITY_AGENT_MANIFEST

__all__ = [
    "CLARITY_AGENT_MANIFEST",
    "ClaritySessionAdapter",
    "ClaritySessionSession",
    "build_target_backend",
    "load_eval_config",
]
