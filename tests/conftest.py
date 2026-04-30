"""Shared fixtures for clarity-agent tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import keyring
import pytest

from clarity_agent.keyring_backend import LocalKeyring
from clarity_agent.protocol.initialize import init_protocol
from clarity_agent.settings import Settings


@pytest.fixture(autouse=True)
def _reset_settings(tmp_path: Path) -> Iterator[None]:
    """Reset Settings and keyring between tests.

    Points CLARITY_DATA_DIR at a temp dir so Settings.load() never
    picks up the developer's real credentials. Installs a LocalKeyring
    backed by a temp file so tests don't touch the real keychain.
    """
    _old_data_dir = os.environ.get("CLARITY_DATA_DIR")
    _old_keyring = keyring.get_keyring()

    os.environ["CLARITY_DATA_DIR"] = str(tmp_path)
    keyring.set_keyring(LocalKeyring(path=tmp_path / "secrets.json"))
    Settings._reset()

    yield

    Settings._reset()
    keyring.set_keyring(_old_keyring)
    if _old_data_dir is None:
        os.environ.pop("CLARITY_DATA_DIR", None)
    else:
        os.environ["CLARITY_DATA_DIR"] = _old_data_dir


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    """Return a temporary git project directory (has a .git folder)."""
    (tmp_path / ".git").mkdir()
    return tmp_path


@pytest.fixture
def protocol_dir(project_path: Path) -> Path:
    """Create a .clarity-protocol/ directory with real (non-template) content.

    Returns the path to the .clarity-protocol/ directory.
    """
    init_protocol(project_path)
    pd = project_path / ".clarity-protocol"

    # Write non-template content into the standard documents so that
    # hashing, staleness, and trigger logic have something to work with.
    docs = {
        "summary.md": "# CoffeeFast\n\nA faster coffee brewing system for engineers who can't wait.\n",
        "goal/problem.md": "# Problem\n\nWe need to make coffee faster.\n",
        "goal/stakeholders.md": "# Stakeholders\n\n- Engineers who drink coffee\n",
        "goal/requirements.md": "# Requirements\n\n1. Brew in under 2 minutes\n",
        "goal/open-questions.md": "# Open Questions\n\nNo fundamental unknowns identified.\n",
        "goal/resolved-questions.md": "# Resolved Questions\n\n## Q1: Can we brew under 2 minutes?\n\n**Status:** resolved\n**Resolution:** Yes, with the modular system.\n",
        "solution/solution.md": "# Solution\n\nUse a better coffee machine.\n",
        "solution/architecture.md": "# Architecture\n\nPlug-in modular brewing system.\n",
        "solution/solution-summary.md": "# Solution Summary\n\nA modular brewing system that makes coffee in under 2 minutes.\n",
        "failures/failures.md": "# Failures\n\n- Could run out of beans.\n",
        "decisions/decisions.md": "# Decisions\n\n- Chose pour-over method.\n",
        "notes.md": "# Notes\n\n- Use modular components for maintainability.\n",
        "observations.md": "# Observations\n\nCoverage: Security thinker examined auth and injection surfaces.\n",
    }
    for rel_path, content in docs.items():
        (pd / rel_path).write_text(content)

    return pd
