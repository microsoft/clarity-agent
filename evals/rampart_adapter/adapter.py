"""``ClaritySessionAdapter`` — RAMPART AgentAdapter wrapping ClaritySession.

Bridges RAMPART's async ``Session`` protocol to clarity-agent's sync
``ClaritySession.chat()`` via ``asyncio.to_thread``.  Owns the
priming step (system prompt with behaviors + process guide +
packet-status report) so cases don't have to know about Clarity's
internals.

Two callbacks observe the target during each turn:
  * ``backend.on_tool_call`` → captured into ``Response.tool_calls``
  * ``.clarity-protocol/`` path+mtime diff → ``Response.side_effects``

Cost is tracked by chaining ``backend.on_cost`` and exposed via
``Session.metadata['cost_usd']`` on each turn's ``Response`` and
cumulatively on the session.
"""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Self

from rampart import (
    AppManifest,
    ObservabilityLevel,
    Request,
    Response,
    SideEffect,
    ToolCall,
)

from clarity_agent.app_paths import protocol_dir as _protocol_dir
from clarity_agent.llm.chat import ChatBackend
from clarity_agent.llm.config import LLMConfig
from clarity_agent.llm.types import ToolUseBlock
from clarity_agent.protocol.initialize import init_protocol
from clarity_agent.session import ClaritySession
from clarity_agent.transcript import Transcript
from evals.rampart_adapter.manifest import CLARITY_AGENT_MANIFEST

if TYPE_CHECKING:
    pass


@dataclass
class _FsSnapshot:
    """A flat (path → mtime) snapshot of ``.clarity-protocol/``.

    Computed before/after each turn.  The diff against the previous
    snapshot becomes the turn's ``side_effects`` list.
    """

    entries: dict[str, float] = field(default_factory=dict)

    @classmethod
    def take(cls, root: Path) -> _FsSnapshot:
        if not root.exists():
            return cls()
        out: dict[str, float] = {}
        for p in root.rglob("*"):
            if p.is_file():
                try:
                    out[str(p.relative_to(root))] = p.stat().st_mtime
                except OSError:
                    # File vanished mid-walk; skip silently.
                    continue
        return cls(entries=out)

    def diff(self, newer: _FsSnapshot) -> list[SideEffect]:
        effects: list[SideEffect] = []
        for path, mtime in newer.entries.items():
            old = self.entries.get(path)
            if old is None:
                effects.append(SideEffect(
                    kind="file_write",
                    details={"path": path, "change": "created"},
                ))
            elif old != mtime:
                effects.append(SideEffect(
                    kind="file_write",
                    details={"path": path, "change": "modified"},
                ))
        for path in self.entries:
            if path not in newer.entries:
                effects.append(SideEffect(
                    kind="file_write",
                    details={"path": path, "change": "deleted"},
                ))
        return effects


class ClaritySessionSession:
    """RAMPART :class:`Session` wrapping a single ``ClaritySession``.

    Async context manager.  ``send_async`` blocks the calling task on a
    worker thread for the duration of the underlying sync chat call —
    safe because RAMPART's execution loop is willing to await us, but
    means a single Session can only handle one in-flight turn.
    """

    def __init__(
        self,
        *,
        project_dir: Path,
        clarity_agent_dir: Path,
        backend: ChatBackend,
        llm_config: LLMConfig,
        process_name: str,
    ) -> None:
        self._project_dir = project_dir
        self._clarity_agent_dir = clarity_agent_dir
        self._backend = backend
        self._llm_config = llm_config
        self._process_name = process_name
        self._primed = False
        self._inner: ClaritySession | None = None
        self._transcript: Transcript | None = None

        self._pending_tool_calls: list[ToolCall] = []
        self._cost_usd: float = 0.0
        self._fs_baseline: _FsSnapshot = _FsSnapshot()

    # --- async context management -----------------------------------

    async def __aenter__(self) -> Self:
        # Build the underlying session synchronously — it's cheap
        # (no LLM calls).  Priming, which DOES make an LLM call,
        # happens on first ``send_async``.
        init_protocol(self._project_dir)
        self._transcript = Transcript(self._project_dir)
        self._inner = ClaritySession(
            self._project_dir,
            self._clarity_agent_dir,
            self._backend,
            self._llm_config,
            transcript=self._transcript,
        )
        self._inner.__enter__()
        self._install_observers()
        self._fs_baseline = _FsSnapshot.take(_protocol_dir(self._project_dir))
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._inner is not None:
            self._inner.__exit__(exc_type, exc_val, exc_tb)
        if self._transcript is not None:
            self._transcript.close()

    # --- RAMPART Session protocol ----------------------------------

    async def send_async(self, request: Request) -> Response:
        if self._inner is None:
            raise RuntimeError(
                "ClaritySessionSession used outside its async-context.  "
                "Wrap the call in `async with adapter.create_session_async() "
                "as session: ...`."
            )
        if request.prompt is None:
            raise ValueError(
                "ClaritySessionSession requires Request.prompt.  Inline "
                "attachments aren't wired into the adapter yet — Phase 1 "
                "scope is text-only conversation."
            )

        # Snapshot fs + reset per-turn buffers BEFORE prompting.
        protocol_root = _protocol_dir(self._project_dir)
        fs_before = _FsSnapshot.take(protocol_root)
        self._pending_tool_calls = []
        cost_before = self._cost_usd

        text = await asyncio.to_thread(self._chat, request.prompt)

        fs_after = _FsSnapshot.take(protocol_root)
        side_effects = fs_before.diff(fs_after)
        tool_calls = list(self._pending_tool_calls)
        turn_cost = self._cost_usd - cost_before

        return Response(
            text=text,
            tool_calls=tool_calls,
            side_effects=side_effects,
            metadata={
                "project_dir": str(self._project_dir),
                "protocol_dir": str(protocol_root),
                "cost_usd": turn_cost,
                "cumulative_cost_usd": self._cost_usd,
            },
        )

    # --- internals --------------------------------------------------

    def _chat(self, prompt: str) -> str:
        """Run on the worker thread.  Primes lazily on first call."""
        assert self._inner is not None
        if not self._primed:
            self._primed = True
            system_prompt = self._build_system_prompt()
            kickoff = f"Let's run the {self._process_name} process."
            # Send the priming kickoff so the target has process
            # context, then the user's actual prompt.  Mirrors
            # ``TargetSession.chat``'s priming behavior.
            self._inner.chat(kickoff, system_prompt=system_prompt)
        return self._inner.chat(prompt)

    def _build_system_prompt(self) -> str:
        """Construct the system prompt the target sees on turn 1.

        Matches ``ClaritySession.run_custom_process`` /
        ``TargetSession._build_system_prompt`` so a RAMPART-driven
        case puts the target in the same starting state as a legacy
        ``TargetSession``.  Diverging here would mean cases written
        in the new path see different agent behavior than ones in
        the old path — and we don't want to chase that ghost during
        the migration.
        """
        assert self._inner is not None
        process_content = self._inner.load_process(self._process_name)
        behaviors = self._inner.load_behaviors()
        behaviors_block = f"{behaviors}\n\n" if behaviors else ""
        prompt: str = (
            f"{behaviors_block}"
            f"You are running the {self._process_name} process. "
            f"Here is the process guide:\n\n{process_content}\n\n"
            f"Follow this process step by step.\n\n"
            f"The clarity-agent directory (containing process guides "
            f"and thinker definitions) is: {self._clarity_agent_dir}\n"
            f"Process guides: {self._clarity_agent_dir / 'processes'}/\n"
            f"Thinker guides: {self._clarity_agent_dir / 'thinkers'}/"
        )
        status_report = self._inner.get_packet_status_report()
        if status_report:
            prompt += f"\n\nPacket status analysis:\n\n{status_report}"
        return prompt

    def _install_observers(self) -> None:
        """Hook backend callbacks for tool-call + cost observation."""
        prev_tool_call = self._backend.on_tool_call
        prev_cost = self._backend.on_cost

        def _record_tool_call(block: ToolUseBlock) -> None:
            self._pending_tool_calls.append(ToolCall(
                name=block.name,
                arguments=dict(block.input) if block.input else {},
            ))
            if prev_tool_call is not None:
                prev_tool_call(block)

        def _record_cost(cost_usd: float) -> None:
            self._cost_usd += cost_usd
            if prev_cost is not None:
                prev_cost(cost_usd)

        self._backend.on_tool_call = _record_tool_call
        self._backend.on_cost = _record_cost

    # --- evaluator-friendly accessors --------------------------------

    @property
    def project_dir(self) -> Path:
        return self._project_dir

    @property
    def protocol_dir(self) -> Path:
        return _protocol_dir(self._project_dir)

    @property
    def cumulative_cost_usd(self) -> float:
        return self._cost_usd


class ClaritySessionAdapter:
    """RAMPART :class:`AgentAdapter` for clarity-agent.

    Manufactures fresh sessions on demand.  Each session gets its own
    project directory (default: a tempdir cleaned up by the caller's
    test harness) and its own ``ChatBackend`` instance — nothing is
    shared across sessions, matching RAMPART's freshness contract.
    """

    def __init__(
        self,
        *,
        clarity_agent_dir: Path,
        backend_factory: Callable[[Path], ChatBackend],
        llm_config: LLMConfig,
        process_name: str = "clarity-agent",
        project_dir_factory: Callable[[], Path] | None = None,
    ) -> None:
        self._clarity_agent_dir = clarity_agent_dir
        self._backend_factory = backend_factory
        self._llm_config = llm_config
        self._process_name = process_name
        self._project_dir_factory = project_dir_factory or _default_project_dir

    @property
    def manifest(self) -> AppManifest:
        return CLARITY_AGENT_MANIFEST

    @property
    def observability_profile(self) -> ObservabilityLevel:
        # ClaritySession exposes structured tool calls via
        # ``backend.on_tool_call`` and we observe ``.clarity-protocol/``
        # writes by snapshot diff.  Both are reliable in-process.
        return ObservabilityLevel.TOOL_AND_SIDE_EFFECTS

    async def create_session_async(self) -> ClaritySessionSession:
        project_dir = self._project_dir_factory()
        backend = self._backend_factory(project_dir)
        return ClaritySessionSession(
            project_dir=project_dir,
            clarity_agent_dir=self._clarity_agent_dir,
            backend=backend,
            llm_config=self._llm_config,
            process_name=self._process_name,
        )


def _default_project_dir() -> Path:
    """Default factory: a fresh tempdir under the OS temp root.

    The caller's test harness is responsible for cleanup — typically
    by passing a pytest ``tmp_path`` factory in tests.  This default
    is for ad-hoc smoke runs.
    """
    return Path(tempfile.mkdtemp(prefix="clarity-rampart-"))
