"""Pytest fixtures for RAMPART-driven eval cases.

Currently provides ``eval_config`` (loads ``evals/config.yaml`` with
hard-fail on missing config or credentials) and ``clarity_adapter``
(a ready-to-use ``ClaritySessionAdapter`` against the configured
target).  ``advisory`` / ``refusal_acceptable`` / smoke-gate /
fingerprint-cache equivalents are not yet ported.

The parent ``evals/conftest.py`` is loaded automatically and supplies
its own session-level hooks.  Those hooks only react to ``evals/cases/``
node IDs (legacy path), so they pass through harmlessly here.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from evals.framework.config import EvalConfig, missing_credentials
from evals.rampart_adapter import (
    ClaritySessionAdapter,
    build_target_backend,
    load_eval_config,
)


def _repo_root() -> Path:
    # ``conftest.py`` is at evals/cases_rampart/conftest.py;
    # repo root is two directories up.
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="session")
def eval_config() -> EvalConfig:
    """Load ``evals/config.yaml``.

    Hard-fails (not skip) if the file is missing or malformed —
    operators must explicitly opt in by providing a config.  Same
    fail-fast contract as the legacy ``--output-dir`` collection
    guard.
    """
    try:
        cfg = load_eval_config()
    except FileNotFoundError as exc:
        pytest.fail(
            f"evals/config.yaml not found ({exc}).  Copy "
            f"evals/config.sample.yaml to evals/config.yaml and "
            f"configure your providers before running RAMPART evals.",
            pytrace=False,
        )
    except Exception as exc:
        pytest.fail(
            f"Failed to load evals/config.yaml: {exc}",
            pytrace=False,
        )

    missing = missing_credentials(cfg)
    if missing:
        pytest.fail(
            "Missing credentials for the following eval roles:\n  - "
            + "\n  - ".join(missing)
            + "\n\nSet the relevant env vars (ANTHROPIC_API_KEY, "
            "OPENAI_API_KEY, etc.) and re-run.  RAMPART evals require "
            "all configured providers to be reachable.",
            pytrace=False,
        )
    return cfg


@pytest.fixture
def clarity_adapter(
    eval_config: EvalConfig,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[ClaritySessionAdapter]:
    """A ``ClaritySessionAdapter`` configured against ``_target``.

    Each test gets its own tempdir factory so per-session project
    dirs don't collide.  Pytest cleans the tempdirs up at the end of
    the test run.
    """
    repo_root = _repo_root()
    factory, llm_config = build_target_backend(
        config=eval_config,
        clarity_agent_dir=repo_root,
    )

    def project_dir_factory() -> Path:
        return tmp_path_factory.mktemp("clarity-rampart-")

    adapter = ClaritySessionAdapter(
        clarity_agent_dir=repo_root,
        backend_factory=factory,
        llm_config=llm_config,
        project_dir_factory=project_dir_factory,
    )
    yield adapter
