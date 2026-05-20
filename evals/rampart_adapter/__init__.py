"""RAMPART adapter for clarity-agent.

A bridge layer that exposes ``ClaritySession`` as a RAMPART
``AgentAdapter``.  Lets new eval cases written against RAMPART's
public API drive the same target as the legacy framework, so we can
migrate cases off ``evals/framework/`` piecewise.

Phase 1 scope: just the adapter, manifest, and config glue.  See
``NOTES.md`` for the running migration log.
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
