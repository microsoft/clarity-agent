"""Registry for discovering, validating, and selecting thinkers.

Thinker files are Markdown documents with optional YAML frontmatter that
describe a perspective from which to examine a system for potential failures.
This module discovers those files, parses their metadata, checks whether
the project has the prerequisite documents each thinker needs, and selects
the appropriate thinkers for a brainstorming run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from clarity_agent.protocol.packet_status import ClarityConfig, is_template, load_config

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Prerequisites:
    """Documents a thinker needs before it can run."""

    required: list[str] = field(default_factory=list)
    recommended: list[str] = field(default_factory=list)


@dataclass
class PrereqResult:
    """Result of checking a thinker's prerequisites against a project."""

    satisfied: bool
    missing_required: list[str] = field(default_factory=list)
    missing_recommended: list[str] = field(default_factory=list)


@dataclass
class ThinkerInfo:
    """Parsed metadata and content for a single thinker."""

    name: str
    display_name: str
    type: str                       # "ai" | "human"
    modes: list[str]                # e.g. ["quick", "deep"]
    prerequisites: Prerequisites
    tags: list[str]
    guide_path: Path
    guide_content: str              # markdown body after frontmatter
    execution: str = "sync"         # "sync" | "async"
    description: str = ""           # short description of what this thinker is good at


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

# Matches a YAML frontmatter block delimited by --- on its own line.
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?\n)---[ \t]*\n", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from a Markdown document.

    Returns ``(metadata_dict, body)`` where *body* is the text after
    the closing ``---`` delimiter.  If no frontmatter is found, returns
    ``({}, text)`` unchanged.

    Raises ``ImportError`` if PyYAML is not installed and frontmatter is
    present.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    try:
        import yaml
    except ImportError as exc:
        raise ImportError(
            "Parsing thinker frontmatter requires PyYAML. "
            "Install with: pip install 'clarity-agent[brainstorm]'"
        ) from exc

    raw: Any = yaml.safe_load(match.group(1))
    metadata: dict[str, Any] = raw if isinstance(raw, dict) else {}
    body: str = text[match.end():]
    return metadata, body


# ---------------------------------------------------------------------------
# Loading individual thinkers
# ---------------------------------------------------------------------------

def load_thinker(path: Path) -> ThinkerInfo:
    """Load a single thinker from a ``.md`` file.

    If the file has YAML frontmatter, fields are read from it.  Otherwise,
    sensible defaults are inferred from the filename.
    """
    text: str = path.read_text()
    meta, body = parse_frontmatter(text)

    prereqs_raw: dict[str, list[str]] = meta.get("prerequisites", {})
    prereqs = Prerequisites(
        required=prereqs_raw.get("required", []),
        recommended=prereqs_raw.get("recommended", []),
    )

    # Derive a display name from the filename if not specified.
    stem: str = path.stem  # e.g. "security-thinker"
    default_display: str = stem.replace("-", " ").title()

    return ThinkerInfo(
        name=meta.get("name", stem),
        display_name=meta.get("display_name", default_display),
        type=meta.get("type", "ai"),
        execution=meta.get("execution", "sync"),
        modes=meta.get("modes", ["quick", "deep"]),
        prerequisites=prereqs,
        tags=meta.get("tags", []),
        guide_path=path,
        guide_content=body.strip(),
        description=meta.get("description", ""),
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_thinkers(
    agent_dir: Path,
    custom_dir: Path | None = None,
) -> list[ThinkerInfo]:
    """Discover all thinkers from the agent's ``thinkers/`` directory.

    Optionally also discovers thinkers from *custom_dir* (typically
    ``.clarity-protocol/extensions/thinkers/`` inside a project).

    Returns thinkers sorted by name.
    """
    thinkers: list[ThinkerInfo] = []

    thinker_dir: Path = agent_dir / "thinkers"
    if thinker_dir.is_dir():
        for path in sorted(thinker_dir.glob("*.md")):
            thinkers.append(load_thinker(path))

    if custom_dir is not None and custom_dir.is_dir():
        for path in sorted(custom_dir.glob("*.md")):
            thinkers.append(load_thinker(path))

    return thinkers


# ---------------------------------------------------------------------------
# Prerequisite checking
# ---------------------------------------------------------------------------

def check_prerequisites(
    thinker: ThinkerInfo,
    protocol_dir: Path,
) -> PrereqResult:
    """Check whether a thinker's prerequisite documents are ready.

    A document is considered "not ready" if it does not exist or still
    contains template placeholder content (detected via
    :func:`packet_status.is_template`).
    """
    missing_required: list[str] = []
    missing_recommended: list[str] = []

    for doc_path in thinker.prerequisites.required:
        if is_template(protocol_dir / doc_path):
            missing_required.append(doc_path)

    for doc_path in thinker.prerequisites.recommended:
        if is_template(protocol_dir / doc_path):
            missing_recommended.append(doc_path)

    return PrereqResult(
        satisfied=len(missing_required) == 0,
        missing_required=missing_required,
        missing_recommended=missing_recommended,
    )


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def select_thinkers(
    agent_dir: Path,
    protocol_dir: Path,
    config: ClarityConfig | None = None,
    mode: str = "deep",
    custom_dir: Path | None = None,
) -> list[ThinkerInfo]:
    """Select thinkers eligible for a brainstorming run.

    Applies the following filters in order:

    1. **Discovery** — all ``.md`` files in ``agent_dir/thinkers/`` and
       optional *custom_dir*.
    2. **Config blacklist** — thinkers whose name appears in
       ``config["thinkers"]["disabled"]`` are removed.
    3. **Mode** — the thinker must list the requested *mode* in its
       ``modes`` field.
    4. **Prerequisites** — all ``required`` documents must exist and
       contain real (non-template) content.

    If *config* is ``None``, it is loaded from ``protocol_dir/config.json``.
    """
    if config is None:
        config = load_config(protocol_dir)

    thinker_config = config.get("thinkers") or {}
    disabled: list[str] = thinker_config.get("disabled", [])

    all_thinkers: list[ThinkerInfo] = discover_thinkers(agent_dir, custom_dir)
    selected: list[ThinkerInfo] = []

    for thinker in all_thinkers:
        # Config blacklist.
        if thinker.name in disabled:
            continue

        # Mode filter.
        if mode not in thinker.modes:
            continue

        # Prerequisite filter.
        prereq: PrereqResult = check_prerequisites(thinker, protocol_dir)
        if not prereq.satisfied:
            continue

        selected.append(thinker)

    return selected
