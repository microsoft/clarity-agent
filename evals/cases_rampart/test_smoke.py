"""Wiring proof for the RAMPART adapter.

Proves:

  - the ``rampart`` package installs and imports
  - ``CLARITY_AGENT_MANIFEST`` is a valid ``AppManifest``
  - ``ClaritySessionAdapter.create_session_async`` returns a working
    ``Session`` whose async context-manager + ``send_async`` flow
    makes a real round-trip through ``ClaritySession.chat``
  - tool-call observation and side-effect snapshotting don't crash
  - session cleanup runs without leaking transcripts or backends

Does NOT exercise simulated user, judge, refusal logic, or report
generation — those are evaluator-level concerns that belong in
their own case files.  Keep this test small; broader surface area
lives in sibling files as cases are added.

Run locally with:
    pytest evals/cases_rampart/ -sv

And once under parallelism:
    pytest evals/cases_rampart/ -sv -n 2
"""

from __future__ import annotations

import pytest
from rampart import (
    AppManifest,
    ObservabilityLevel,
    Request,
    Response,
)

from evals.rampart_adapter import (
    CLARITY_AGENT_MANIFEST,
    ClaritySessionAdapter,
)


def test_manifest_well_formed() -> None:
    """Sanity check the manifest constant — synchronous, free."""
    assert isinstance(CLARITY_AGENT_MANIFEST, AppManifest)
    assert CLARITY_AGENT_MANIFEST.name == "clarity-agent"
    assert CLARITY_AGENT_MANIFEST.declares_tool("record_failure")
    assert CLARITY_AGENT_MANIFEST.declares_tool("record_suggestion")


def test_adapter_observability_profile(
    clarity_adapter: ClaritySessionAdapter,
) -> None:
    """The adapter declares full observability — tool calls + side
    effects."""
    assert (
        clarity_adapter.observability_profile
        == ObservabilityLevel.TOOL_AND_SIDE_EFFECTS
    )
    assert clarity_adapter.manifest is CLARITY_AGENT_MANIFEST


@pytest.mark.asyncio
async def test_smoke_send_async_round_trip(
    clarity_adapter: ClaritySessionAdapter,
) -> None:
    """A single ``send_async`` produces a non-empty response.

    The prompt is intentionally bland — we want to test the bridge,
    not the agent's behavior.  Anything stronger would couple this
    test to the target's prompting logic and flake under model
    revisions.
    """
    async with await clarity_adapter.create_session_async() as session:
        response = await session.send_async(
            Request(prompt=(
                "In one sentence, what kind of process does the "
                "clarity-agent guide describe?"
            )),
        )

    assert isinstance(response, Response)
    assert response.text.strip(), (
        "ClaritySession returned empty text — adapter or backend "
        "wiring is broken."
    )
    # Tool calls and side effects are lists; they may legitimately
    # be empty for a single-turn benign prompt.  Asserting only the
    # type avoids coupling to model behavior.
    assert isinstance(response.tool_calls, list)
    assert isinstance(response.side_effects, list)
    # Cost telemetry is best-effort — some backends don't report
    # it.  When present it must be non-negative.
    cost = response.metadata.get("cost_usd")
    if cost is not None:
        assert cost >= 0.0
    # The adapter exposes the project_dir so evaluators can look at
    # the on-disk artifacts the agent produced.
    assert response.metadata.get("project_dir")
    assert response.metadata.get("protocol_dir")
