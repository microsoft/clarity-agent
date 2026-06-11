"""Discover and describe available first-exploration scenarios.

Scenarios are markdown files in ``processes/first-exploration/`` whose
name is not the base guide (``exploration-process-guide.md``).  Each
scenario file has a ``# Scenario: <title>`` heading and a ``## Seed
situation`` section whose first paragraph becomes the one-sentence
description shown on the scenario card.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# The base guide lives alongside scenarios but is not one.
_BASE_GUIDE = "exploration-process-guide.md"


@dataclass(frozen=True)
class Scenario:
    """Metadata for a single exploration scenario."""

    id: str  # stem of the filename, e.g. "autonomous-email-assistant"
    title: str  # extracted from ``# Scenario: <title>``
    description: str  # first paragraph under ``## Seed situation``

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "title": self.title, "description": self.description}


def _extract_title(text: str) -> str:
    """Pull the title from ``# Scenario: <title>``."""
    m = re.search(r"^#\s+Scenario:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else "Untitled Scenario"


def _extract_seed_description(text: str) -> str:
    """Pull the first paragraph after ``## Seed situation``."""
    m = re.search(
        r"^##\s+Seed situation\s*\n+(.+?)(?:\n\n|\n#|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not m:
        return ""
    # Collapse internal newlines to a single space.
    return re.sub(r"\s+", " ", m.group(1)).strip()


def list_scenarios(clarity_agent_dir: Path) -> list[Scenario]:
    """Return all available scenarios, sorted by id."""
    scenario_dir = clarity_agent_dir / "processes" / "first-exploration"
    if not scenario_dir.is_dir():
        return []

    scenarios: list[Scenario] = []
    for md in sorted(scenario_dir.glob("*.md")):
        if md.name == _BASE_GUIDE:
            continue
        text = md.read_text(encoding="utf-8")
        scenarios.append(Scenario(
            id=md.stem,
            title=_extract_title(text),
            description=_extract_seed_description(text),
        ))
    return scenarios


def load_scenario_content(clarity_agent_dir: Path, scenario_id: str) -> str:
    """Load the full markdown content of a scenario by id.

    Raises ``FileNotFoundError`` if the scenario doesn't exist.
    """
    path = (
        clarity_agent_dir / "processes" / "first-exploration" / f"{scenario_id}.md"
    )
    if not path.exists():
        raise FileNotFoundError(f"Scenario not found: {scenario_id}")
    return path.read_text(encoding="utf-8")
