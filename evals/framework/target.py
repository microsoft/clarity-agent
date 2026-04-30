"""The system under test: a ClaritySession in a temp project directory.

``TargetSession`` wraps ``ClaritySession`` and exposes a single
``chat(user_message)`` method.  On the first call, it primes the
session with the ``clarity-agent`` process guide — matching what a
real user would see when they first launch the tool.
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType

from clarity_agent.app_paths import protocol_dir as _protocol_dir
from clarity_agent.llm.chat import ChatBackend
from clarity_agent.llm.config import LLMConfig
from clarity_agent.protocol.initialize import init_protocol
from clarity_agent.session import ClaritySession


class TargetSession:
    """Wrap a ClaritySession for eval-driven use.

    The caller controls the conversation turn-by-turn via ``chat()``.
    Transcripts and protocol files accumulate in ``project_dir``.
    """

    def __init__(
        self,
        *,
        project_dir: Path,
        clarity_agent_dir: Path,
        backend: ChatBackend,
        llm_config: LLMConfig,
        process_name: str = "clarity-agent",
    ) -> None:
        self.project_dir = project_dir
        self.clarity_agent_dir = clarity_agent_dir
        self._process_name = process_name
        self._backend = backend
        self._primed = False
        self._cost_usd = 0.0

        # Initialize a .clarity-protocol/ tree so the agent has somewhere
        # to write.  init_protocol is idempotent.
        init_protocol(project_dir)
        self.protocol_dir = _protocol_dir(project_dir)

        # Transcripts land in the standard location.  ClaritySession
        # creates a timestamped .md file on first chat.
        transcript_dir = self.protocol_dir / "transcripts"
        self._session = ClaritySession(
            project_dir,
            clarity_agent_dir,
            backend,
            llm_config,
            transcript_dir=transcript_dir,
        )
        self._session.__enter__()

        # Hook cost callback so we can report total spend per test.
        prev_on_cost = backend.on_cost

        def _track_cost(cost_usd: float) -> None:
            self._cost_usd += cost_usd
            if prev_on_cost:
                prev_on_cost(cost_usd)

        backend.on_cost = _track_cost

    def chat(self, user_message: str) -> str:
        """Send *user_message* to the target and return its response.

        On the first call, primes the session with the process system
        prompt — matching ``ClaritySession.run_custom_process()``.
        """
        if not self._primed:
            self._primed = True
            system_prompt = self._build_system_prompt()
            # Send the priming message first so the target has context,
            # then send the actual user message.
            kickoff = f"Let's run the {self._process_name} process."
            self._session.chat(kickoff, system_prompt=system_prompt)

        return self._session.chat(user_message)

    def _build_system_prompt(self) -> str:
        """Mirror the system prompt ClaritySession.run_custom_process uses."""
        process_content = self._session.load_process(self._process_name)
        behaviors = self._session.load_behaviors()
        behaviors_block = f"{behaviors}\n\n" if behaviors else ""
        prompt: str = (
            f"{behaviors_block}"
            f"You are running the {self._process_name} process. "
            f"Here is the process guide:\n\n{process_content}\n\n"
            f"Follow this process step by step.\n\n"
            f"The clarity-agent directory (containing process guides and "
            f"thinker definitions) is: {self.clarity_agent_dir}\n"
            f"Process guides: {self.clarity_agent_dir / 'processes'}/\n"
            f"Thinker guides: {self.clarity_agent_dir / 'thinkers'}/"
        )
        status_report = self._session.get_packet_status_report()
        if status_report:
            prompt += (
                f"\n\nPacket status analysis:\n\n{status_report}"
            )
        return prompt

    @property
    def transcript_file(self) -> Path | None:
        """Path to the on-disk transcript .md, if ClaritySession wrote one."""
        transcript = getattr(self._session, "_transcript", None)
        if transcript is None:
            return None
        try:
            return Path(transcript.name)
        except (AttributeError, ValueError):
            return None

    @property
    def cost_usd(self) -> float:
        """Total cost accumulated across all turns (if reported by backend)."""
        return self._cost_usd

    def close(self) -> None:
        """Release resources held by the underlying ClaritySession."""
        self._session.__exit__(None, None, None)

    def __enter__(self) -> TargetSession:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
