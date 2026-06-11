"""Persistent onboarding state for the first-five-minutes exploration.

Stores per-user state in ``~/.clarity/onboarding.json`` (or the
platform equivalent via :func:`~clarity_agent.app_paths.clarity_data_dir`).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from clarity_agent.app_paths import clarity_data_dir

_FILE = "onboarding.json"

ExplorationStatus = Literal["not_started", "completed", "dismissed"]


@dataclass
class OnboardingState:
    """User-level onboarding state."""

    first_exploration_status: ExplorationStatus = "not_started"
    first_exploration_completed_at: float | None = None
    last_exploration_scenario: str | None = None

    # -- persistence -------------------------------------------------------

    @classmethod
    def load(cls, path: Path | None = None) -> OnboardingState:
        """Load state from disk, returning defaults if absent."""
        p = path or (clarity_data_dir() / _FILE)
        if not p.exists():
            return cls()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return cls(
                first_exploration_status=data.get(
                    "first_exploration_status", "not_started",
                ),
                first_exploration_completed_at=data.get(
                    "first_exploration_completed_at",
                ),
                last_exploration_scenario=data.get(
                    "last_exploration_scenario",
                ),
            )
        except (json.JSONDecodeError, KeyError):
            return cls()

    def save(self, path: Path | None = None) -> None:
        """Persist to disk."""
        p = path or (clarity_data_dir() / _FILE)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(asdict(self), indent=2) + "\n",
            encoding="utf-8",
        )

    # -- mutations ---------------------------------------------------------

    def mark_completed(self, scenario: str | None = None) -> None:
        self.first_exploration_status = "completed"
        self.first_exploration_completed_at = time.time()
        if scenario:
            self.last_exploration_scenario = scenario

    def mark_dismissed(self) -> None:
        self.first_exploration_status = "dismissed"

    def reset(self) -> None:
        """Reset to not_started (for "run again" from Help)."""
        self.first_exploration_status = "not_started"
        self.first_exploration_completed_at = None
        self.last_exploration_scenario = None

    # -- queries -----------------------------------------------------------

    @property
    def eligible_for_auto_exploration(self) -> bool:
        """True when the automatic first-screen experience should show."""
        return self.first_exploration_status == "not_started"
