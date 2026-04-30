"""Structured metadata for all clarity-agent processes.

This is the single source of truth for process display names, descriptions,
tiers, and categories. Used by:

- ``llm/config.py`` for default process-to-tier mapping
- ``GET /api/processes`` for the web UI
- Process explainers (system messages before each process)
- Guided first session (entry points)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessMeta:
    """Metadata for a single clarity-agent process."""

    name: str
    display_name: str
    one_liner: str
    tier: str
    category: str  # explore, design, validate, communicate


PROCESS_METADATA: dict[str, ProcessMeta] = {
    "clarity-agent": ProcessMeta(
        name="clarity-agent",
        display_name="Clarity Agent",
        one_liner="Guides your project through the right thinking steps.",
        tier="deep",
        category="explore",
    ),
    "problem-clarification": ProcessMeta(
        name="problem-clarification",
        display_name="Problem Clarification",
        one_liner="Turns vague ideas into clear problem statements with stakeholders and requirements.",
        tier="deep",
        category="explore",
    ),
    "discovery-prototype": ProcessMeta(
        name="discovery-prototype",
        display_name="Discovery Prototype",
        one_liner="Tests a specific hypothesis through minimal, focused implementation.",
        tier="deep",
        category="explore",
    ),
    "discovery-research": ProcessMeta(
        name="discovery-research",
        display_name="Discovery Research",
        one_liner="Designs and executes a research program to answer open questions.",
        tier="deep",
        category="explore",
    ),
    "solution-brainstorming": ProcessMeta(
        name="solution-brainstorming",
        display_name="Solution Brainstorming",
        one_liner="Develops a plan for how to solve the problem.",
        tier="deep",
        category="design",
    ),
    "architecture-design": ProcessMeta(
        name="architecture-design",
        display_name="Architecture Design",
        one_liner="Turns a solution into a concrete implementation architecture.",
        tier="deep",
        category="design",
    ),
    "failure-brainstorming": ProcessMeta(
        name="failure-brainstorming",
        display_name="Failure Brainstorming",
        one_liner="Identifies what might go wrong using multiple specialist perspectives.",
        tier="deep",
        category="validate",
    ),
    "failure-analysis": ProcessMeta(
        name="failure-analysis",
        display_name="Failure Analysis",
        one_liner="Groups and analyzes raw failure ideas into structured failure modes.",
        tier="deep",
        category="validate",
    ),
    "failure-management": ProcessMeta(
        name="failure-management",
        display_name="Failure Management",
        one_liner="Develops mitigation strategies for identified failure modes.",
        tier="deep",
        category="validate",
    ),
    "decision-guidance": ProcessMeta(
        name="decision-guidance",
        display_name="Decision Guidance",
        one_liner="Helps think through a nontrivial decision with structured analysis.",
        tier="deep",
        category="design",
    ),
    "message-clarification": ProcessMeta(
        name="message-clarification",
        display_name="Message Clarification",
        one_liner="Builds the project summary and audience-specific messaging.",
        tier="deep",
        category="communicate",
    ),
}


def get_default_process_tiers() -> dict[str, str]:
    """Return a process-name → tier mapping derived from the registry.

    This replaces the old ``_DEFAULT_PROCESS_TIERS`` dict in config.py,
    keeping the registry as the single source of truth.
    """
    return {name: meta.tier for name, meta in PROCESS_METADATA.items()}
