"""Tests for clarity_agent.setup.agent_dir."""

from __future__ import annotations

from clarity_agent.setup.agent_dir import get_agent_dir


def test_get_agent_dir_points_to_repo_root() -> None:
    """get_agent_dir() must return the repo root, which contains processes/ and thinkers/."""
    agent_dir = get_agent_dir()
    assert (agent_dir / "processes").is_dir(), f"{agent_dir} missing processes/"
    assert (agent_dir / "thinkers").is_dir(), f"{agent_dir} missing thinkers/"


def test_get_agent_dir_consistent_with_package_init() -> None:
    """The re-export in clarity_agent.__init__ must return the same path."""
    from clarity_agent import get_agent_dir as public_get_agent_dir

    assert get_agent_dir() == public_get_agent_dir()
