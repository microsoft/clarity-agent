"""Configuration glue for RAMPART-driven eval cases.

The legacy framework's ``evals.framework.config`` already knows how
to parse ``evals/config.yaml`` into a structured :class:`EvalConfig`
and how to turn a role spec into a ``ChatBackend`` + ``LLMConfig``.
We reuse it here rather than reimplementing the same machinery on
the RAMPART side — the YAML is data, not behavior, and re-parsing
it twice would be a bug factory once people start editing roles.

When ``evals/framework/`` is finally deleted in Phase 5, this module
either inlines whatever bits it still needs or moves to a
RAMPART-side equivalent.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from clarity_agent.llm.chat import ChatBackend
from clarity_agent.llm.config import LLMConfig
from evals.framework.config import EvalConfig, load_default


def load_eval_config() -> EvalConfig:
    """Load the project's eval config (``evals/config.yaml``).

    Hard-fails with a clear error if the file is missing — the
    operator must explicitly opt in to running RAMPART evals by
    providing a config, same as the legacy path.
    """
    return load_default()


def build_target_backend(
    *,
    config: EvalConfig,
    clarity_agent_dir: Path,
    role: str | None = None,
) -> tuple[Callable[[Path], ChatBackend], LLMConfig]:
    """Return a (backend factory, llm_config) pair for the target slot.

    Each call to the returned factory produces a fresh ``ChatBackend``
    bound to the given project dir.  RAMPART's adapter contract wants
    a new session per ``create_session_async``, and a session owns its
    backend, so we hand back a factory rather than a shared instance.
    """
    # Resolve once so misconfiguration fails fast (before any session
    # creation), but recreate the backend each time the factory is
    # called — backends hold conversation state.
    config.resolve_role("target", role)

    def factory(project_dir: Path) -> ChatBackend:
        backend, _ = config.create_backend(
            slot="target",
            role=role,
            project_dir=project_dir,
            clarity_agent_dir=clarity_agent_dir,
        )
        return backend

    # The LLMConfig itself doesn't depend on project_dir — call
    # create_backend once with a placeholder to extract it.  This is
    # wasteful (it builds a backend we throw away) but the cost is a
    # cheap object construction; LLM clients lazily connect.
    _, llm_config = config.create_backend(
        slot="target",
        role=role,
        project_dir=Path("."),
        clarity_agent_dir=clarity_agent_dir,
    )
    return factory, llm_config
