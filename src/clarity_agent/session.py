"""
Clarity session management.

Contains :class:`ClaritySession`, the core orchestrator for running clarity
processes interactively. Used by the CLI (``clarity.py``) and the web
backend (``clarity_agent.web``).

A ClaritySession is a *process run* — one execution of one or more
protocol processes against a project.  It is NOT a persistent
conversation; that's the :class:`clarity_agent.transcript.Transcript`'s
job.  When a transcript is provided, the session records every user
turn, assistant response, tool call, and process boundary as
structured events on the transcript's current chapter.  Multiple
ClaritySessions over the lifetime of a project append to the same
chapter (with :class:`SessionResume` boundaries marking each new
attach) — they don't create new chapters; that's the user's explicit
"Start new chapter" action.

See :mod:`clarity_agent.transcript` and GitHub issue #35.
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from prompt_toolkit import prompt as pt_prompt

from clarity_agent.llm import ChatBackend, LLMConfig
from clarity_agent.llm.types import ToolHandler, ToolUseBlock
from clarity_agent.protocol.packet_status import (
    PacketStatusReport,
    check_packet_status,
    format_for_agent,
    format_report,
    record_hashes,
)
from clarity_agent.transcript import (
    AssistantText,
    ChapterStarted,
    ProcessStarted,
    SessionResume,
    ToolUse,
    Transcript,
    UserTurn,
)


def _now() -> datetime:
    """Wall-clock timestamp for transcript events, with timezone."""
    return datetime.now(UTC)


def _prepend_behaviors(
    system_prompt: str | None, behaviors: str,
) -> str | None:
    """Prepend the AGENTS.md behaviors block to *system_prompt*.

    Both arguments may be empty/None; result is ``None`` when
    everything was empty (preserves the "no system prompt" semantics
    for backends that distinguish it from an empty string).
    Centralised so :meth:`ClaritySession.chat` and
    :meth:`run_custom_process` produce identically-formatted system
    prompts — same separator, same handling of missing behaviors.
    """
    if not behaviors:
        return system_prompt
    if not system_prompt:
        return behaviors
    return f"{behaviors}\n\n{system_prompt}"


def _git_username(project_dir: Path) -> str | None:
    """Return a filesystem-safe git identity for the current user, or None."""
    for field in ("user.name", "user.email"):
        try:
            result = subprocess.run(
                ["git", "-C", str(project_dir), "config", field],
                capture_output=True, text=True, timeout=3,
            )
            value = result.stdout.strip()
            if value:
                # Sanitize: keep alphanumeric, dot, hyphen; collapse everything else to -
                safe = re.sub(r"[^a-zA-Z0-9.\-]+", "-", value).strip("-")
                if safe:
                    return safe
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


class ClaritySession:
    """Orchestrator for one CLI / web-session process run.

    Wraps a :class:`ChatBackend` and (optionally) a
    :class:`Transcript` that captures the conversation as structured
    events.  See module docstring for ownership notes — the
    ClaritySession does not own the Transcript's lifecycle; callers
    construct the Transcript, pass it in, and close it themselves.
    """

    def __init__(
        self,
        project_dir: str | Path,
        clarity_agent_dir: str | Path,
        backend: ChatBackend,
        llm_config: LLMConfig,
        transcript: Transcript | None = None,
    ) -> None:
        self.project_dir: Path = Path(project_dir)
        self.clarity_agent_dir: Path = Path(clarity_agent_dir)
        from clarity_agent.app_paths import protocol_dir as _protocol_dir
        self.protocol_dir: Path = _protocol_dir(self.project_dir)
        self.backend: ChatBackend = backend
        self.llm_config: LLMConfig = llm_config
        self._transcript: Transcript | None = transcript
        # ``_git_username`` is still referenced by some tooling that
        # imports this module; keep the helper available even though
        # the per-session timestamped-filename code path it was
        # introduced for has been retired in favor of chaptered
        # transcripts.  Calling it here would only matter if we
        # wanted to record the username somewhere — defer.

        if self._transcript is not None:
            # Record the boundary at which this process run attached
            # to the transcript.  Empty transcript → write the chapter
            # header (this is the very first event in chapter 1).
            # Otherwise → write a SessionResume marking the new
            # attach, with backend name and SDK session id (if any).
            backend_name = type(backend).__name__
            if self._transcript.is_empty:
                self._transcript.write(ChapterStarted(
                    timestamp=_now(),
                    project_dir=str(self.project_dir),
                    backend=backend_name,
                ))
            else:
                self._transcript.write(SessionResume(
                    timestamp=_now(),
                    backend=backend_name,
                    llm_session_id=backend.llm_session_id,
                ))
            # Structured tool-call callback writes ``ToolUse`` events
            # to the transcript with full fidelity (provider id +
            # structured input dict).  The legacy ``on_tool_use``
            # path (display string) is left untouched here — UI
            # consumers like WebSessionAdapter set their own.
            backend.on_tool_call = self._record_tool_use

    def _record_tool_use(self, block: ToolUseBlock) -> None:
        """Structured-tool-call callback — append a ``ToolUse`` event.

        Wired into ``backend.on_tool_call`` in :meth:`__init__` when
        a transcript is configured.  Fires from whichever thread the
        backend uses to process tool blocks (the SDK runs queries on
        the asyncio loop; the API tool loop runs synchronously in
        the caller's thread).  The Transcript's writer is
        thread-safe so the callback site doesn't need to coordinate.
        """
        if self._transcript is None:
            return
        self._transcript.write(ToolUse(
            timestamp=_now(),
            tool_use_id=block.id,
            name=block.name,
            input=block.input,
        ))

    def __enter__(self) -> ClaritySession:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        # We deliberately do NOT close the Transcript here — the
        # caller passed it in and owns its lifecycle.  Multiple
        # ClaritySessions over the lifetime of a project can append
        # to the same transcript; closing in our __exit__ would force
        # the next session to reopen the writer (currently a no-op
        # since Transcript lazily re-opens, but the explicit
        # separation of ownership is the cleaner contract).
        return None

    def load_behaviors(self) -> str:
        """Load the cross-cutting behavioral guidelines from the
        project's ``AGENTS.md`` — specifically the Clarity-managed
        block between the ``<!-- clarity-begin -->`` and
        ``<!-- clarity-end -->`` markers.

        Reading from ``project_dir/AGENTS.md`` means we share the
        same file the host coding agent (Claude Code, Cursor, …) sees
        — the file every modern LLM coding agent reads by default —
        so there's one rendered artifact per project, kept current by
        :func:`~clarity_agent.setup.snippet.ensure_agents_md` at
        session-start time.

        Returns the marker-bounded block (markers included) if found;
        an empty string if the file or block is absent (e.g. a fresh
        project where setup hasn't run yet).  Any text outside the
        markers is the user's own project guidance, deliberately
        excluded — we want only the content Clarity is responsible
        for.
        """
        from clarity_agent.setup.snippet import _extract_block
        agents_md = self.project_dir / "AGENTS.md"
        if not agents_md.exists():
            return ""
        block = _extract_block(agents_md.read_text(encoding="utf-8"))
        return block.strip() if block else ""

    def load_process(self, process_name: str) -> str:
        """Load a process guide from the clarity agent directory."""
        process_path: Path = self.clarity_agent_dir / "processes" / f"{process_name}.md"
        if not process_path.exists():
            raise FileNotFoundError(f"Process guide not found: {process_path}")
        return process_path.read_text()

    def load_thinker(self, thinker_name: str) -> str:
        """Load a thinker guide from the clarity agent directory."""
        thinker_path: Path = self.clarity_agent_dir / "thinkers" / f"{thinker_name}.md"
        if not thinker_path.exists():
            raise FileNotFoundError(f"Thinker guide not found: {thinker_path}")
        return thinker_path.read_text()

    def chat(
        self,
        user_message: str,
        system_prompt: str | None = None,
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_handler: ToolHandler | None = None,
    ) -> str:
        """Send a message and get a response from Claude.

        Args:
            model: Optional per-call model override. When set, the backend
                uses this model for the API call while preserving conversation
                history on the same backend instance.
            tools: Optional tool schemas to provide to the model.
            tool_handler: Callable that receives a :class:`ToolUseBlock`
                and returns a result string.
        """
        # Record the user turn before the backend runs.  The
        # assistant turn (and any tool calls) are recorded as they
        # happen: tool calls via the structured callback fired by
        # the backend during streaming; the assistant text in one
        # event after the response completes.  This mirrors the
        # legacy ordering (User → tool events → Assistant) and keeps
        # the markdown matching what users used to see.
        if self._transcript is not None:
            self._transcript.write(UserTurn(timestamp=_now(), content=user_message))
        # Prepend the project's behaviors block to the system prompt
        # so non-SDK backends (Anthropic API direct, OpenAI, Azure,
        # Gemini — which don't auto-discover ``AGENTS.md`` from the
        # cwd the way the Claude CLI does) still see the
        # cross-cutting guidance.  Symmetric with
        # :meth:`run_custom_process`'s system-prompt construction;
        # the SDK path sees the same content twice (once via
        # auto-discovery, once via injection) which is harmless.
        effective_system_prompt = _prepend_behaviors(
            system_prompt, self.load_behaviors(),
        )
        response: str = self.backend.chat(
            user_message, effective_system_prompt, model=model,
            tools=tools, tool_handler=tool_handler,
        )
        if self._transcript is not None:
            self._transcript.write(AssistantText(timestamp=_now(), content=response))
        return response

    def get_packet_status_report(self) -> str | None:
        """Run the packet status checker and return agent-formatted report, or None."""
        if not self.protocol_dir.exists():
            return None
        report: PacketStatusReport = check_packet_status(self.protocol_dir)
        # Include if there's something interesting to report
        if (
            report["summary"]["stale"]
            or report["summary"]["empty"]
            or report["summary"]["untracked"]
            or report.get("mailboxes")
        ):
            return format_for_agent(report)
        return None

    def record_document_state(self) -> None:
        """Record content hashes for all documents after a process completes."""
        if not self.protocol_dir.exists():
            return
        recorded: list[str] = record_hashes(self.protocol_dir)
        if recorded:
            print(f"\n  Recorded document state for {len(recorded)} file(s).")

    def run_main(self) -> None:
        """Run the clarity-agent process to assess state and determine next steps."""
        self.run_custom_process("clarity-agent")

    def _resolve_model(self, process_name: str) -> str:
        """Return the model (or tier name) for *process_name*.

        The returned value may be a tier name (like ``"deep"``) or a
        concrete model string; the backend's ``resolve_model()``
        handles both.
        """
        return self.llm_config.resolve(process_name)

    def run_custom_process(self, process_name: str) -> None:
        """Run a custom process by name."""
        print(f"\n{'=' * 80}")
        print(f"RUNNING {process_name.upper()} PROCESS")
        print(f"{'=' * 80}\n")

        # Resolve the model for this process.  May be a tier name ("deep")
        # or a concrete model string; the backend's resolve_model() handles both.
        model_for_process: str = self._resolve_model(process_name)
        tier: str = self.llm_config.resolve_tier(process_name)
        resolved_model: str = self.backend.resolve_model(model_for_process)
        if tier != "default":
            print(f"  Model: {resolved_model} (tier: {tier})")

        # Record the process boundary as a single ``ProcessStarted``
        # event.  The renderer emits both the ``## Process: name``
        # heading and the ``**Model override:**`` line (the latter
        # only for non-default tiers), so this one event captures
        # everything the legacy two-write code did.
        if self._transcript is not None:
            self._transcript.write(ProcessStarted(
                timestamp=_now(),
                process_name=process_name,
                tier=tier,
                model=resolved_model,
            ))

        # Always include the feedback tool so users can send feedback
        # from any process.
        from clarity_agent.ai_actions.feedback import (
            create_feedback_handler,
            create_feedback_tools,
        )

        feedback_tools = create_feedback_tools()
        feedback_handler = create_feedback_handler(
            self.project_dir,
            provider=self.llm_config.provider,
            model=self.llm_config.tiers.get("default"),
            on_tool_use=self.backend.on_tool_use,
        )

        tools: list[dict[str, Any]] = list(feedback_tools)
        tool_handler: ToolHandler = feedback_handler

        # For failure-brainstorming, add tools so the AI can record
        # findings with controlled formatting.
        if process_name == "failure-brainstorming":
            from clarity_agent.ai_actions.brainstorm import (
                create_brainstorm_handler,
                create_brainstorm_tools,
                format_available_thinkers,
            )
            from clarity_agent.protocol.thinker_registry import select_thinkers

            all_thinkers = select_thinkers(
                self.clarity_agent_dir, self.protocol_dir, mode="deep",
            )
            # Exclude general-thinker — the AI IS the general thinker now.
            specialists = [t for t in all_thinkers if t.name != "general-thinker"]

            brainstorm_tools = create_brainstorm_tools(specialists or None)
            brainstorm_handler = create_brainstorm_handler(
                self.protocol_dir,
                self.clarity_agent_dir,
                on_tool_use=self.backend.on_tool_use,
            )

            tools.extend(brainstorm_tools)
            _fb_handler = feedback_handler

            def _combined(tc: Any) -> str:
                if tc.name == "send_feedback":
                    return _fb_handler(tc)
                return brainstorm_handler(tc)

            tool_handler = _combined

        # Load process
        try:
            process_content: str = self.load_process(process_name)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            return

        process_specific: str = (
            f"You are running the {process_name} process. "
            f"Here is the process guide:\n\n{process_content}\n\n"
            f"Follow this process step by step.\n\n"
            f"The clarity-agent directory (containing process guides and "
            f"thinker definitions) is: {self.clarity_agent_dir}\n"
            f"Process guides: {self.clarity_agent_dir / 'processes'}/\n"
            f"Thinker guides: {self.clarity_agent_dir / 'thinkers'}/"
        )
        # ``_prepend_behaviors`` matches the formatting that
        # :meth:`chat` uses, so both paths produce identically-shaped
        # system prompts.
        system_prompt: str = (
            _prepend_behaviors(process_specific, self.load_behaviors())
            or process_specific
        )

        # Include packet status report for processes that benefit from it
        status_report: str | None = self.get_packet_status_report()
        if status_report:
            system_prompt += (
                f"\n\nThe following packet status analysis was performed by checking "
                f"content hashes against the document dependency graph. Use this "
                f"to inform your assessment:\n\n{status_report}"
            )

        # For failure-brainstorming, append methodology and specialist info.
        if process_name == "failure-brainstorming":
            methodology_path = (
                self.clarity_agent_dir / "processes" / "failure-reasoning-guidelines.md"
            )
            if methodology_path.exists():
                system_prompt += (
                    f"\n\n## Failure Reasoning Methodology\n\n"
                    f"{methodology_path.read_text()}"
                )
            if specialists:  # type: ignore[possibly-undefined]
                system_prompt += f"\n\n{format_available_thinkers(specialists)}"  # type: ignore[possibly-undefined]

        initial_message: str = f"Let's run the {process_name} process."

        response: str = self.chat(
            initial_message,
            system_prompt=system_prompt,
            model=model_for_process,
            tools=tools,
            tool_handler=tool_handler,
        )

        print(f"Assistant: {response}\n")

        # Interactive conversation
        print("(Enter for newline, Alt+Enter to send, 'exit' to end)\n")
        while True:
            try:
                user_input: str = _multiline_input()
            except (EOFError, KeyboardInterrupt):
                print(f"\nEnding {process_name} process.")
                break
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "done"):
                print(f"\nEnding {process_name} process.")
                break

            # Process handoff: intercept "run <process-name>" to load
            # the next process guide into the conversation.  Works for
            # all backends since it injects text, not tools.
            handoff_match: re.Match[str] | None = re.match(
                r"^run\s+([\w-]+)\s*$", user_input.strip(), re.IGNORECASE,
            )
            if handoff_match:
                next_process: str = handoff_match.group(1)
                try:
                    next_content: str = self.load_process(next_process)
                    process_name = next_process
                    print(f"\nLoading {next_process} process guide...\n")
                    user_input = (
                        f"We're now running the {next_process} process. "
                        f"Here is the process guide:\n\n{next_content}\n\n"
                        f"Follow this process from its beginning, taking "
                        f"into account our conversation so far."
                    )
                except FileNotFoundError:
                    print(f"  Unknown process: {next_process}")
                    continue

            response = self.chat(
                user_input, model=model_for_process,
                tools=tools, tool_handler=tool_handler,
            )
            print(f"\nAssistant: {response}\n")

        # Record document state after process completes
        self.record_document_state()

    def interactive_mode(self) -> None:
        """Run in interactive mode with command menu."""
        print(f"\n{'=' * 80}")
        print("CLARITY CLI - Interactive Mode")
        backend_label: str = (
            "tools enabled" if self.backend.supports_tools else "talk only"
        )
        print(f"Backend: {backend_label}")
        print("=" * 80)
        print(f"\nProject directory: {self.project_dir}")
        print(f"Clarity agent: {self.clarity_agent_dir}")
        print(f"Protocol exists: {self.protocol_dir.exists()}")

        while True:
            print(f"\n{'-' * 80}")
            print("Commands:")
            print("  run              - Run clarity-agent (assess state, determine next step)")
            print("  process <name>   - Run a specific process by name")
            print("  brainstorm       - Run AI thinkers to brainstorm failure modes")
            print("  packet [opts]    - Generate a review packet (--list for sources)")
            print("  chat             - Free-form chat with Claude")
            print("  status           - Show project status")
            print("  packet-status    - Check packet status (staleness, dependencies)")
            print("  record           - Record current document hashes as baseline")
            print("  quit             - Exit")
            print("-" * 80)

            command: str = input("\nCommand: ").strip().lower()

            if command == "quit":
                print("\nGoodbye!")
                break
            elif command == "run":
                self.run_main()
            elif command.startswith("process "):
                process_name: str = command.split(" ", 1)[1]
                self.run_custom_process(process_name)
            elif command == "brainstorm" or command.startswith("brainstorm "):
                self.run_brainstorm(command)
            elif command == "packet" or command.startswith("packet "):
                self.run_packet(**_parse_packet_command(command))
            elif command == "chat":
                self.free_chat()
            elif command == "status":
                self.show_status()
            elif command == "packet-status":
                self.show_packet_status()
            elif command == "record":
                self.record_document_state()
            else:
                print(f"Unknown command: {command}")

    def free_chat(self) -> None:
        """Free-form chat mode."""
        print(f"\n{'=' * 80}")
        print("FREE CHAT MODE")
        print(f"{'=' * 80}")
        print("(Enter for newline, Alt+Enter to send, 'exit' to return to menu)\n")

        from clarity_agent.ai_actions.feedback import (
            create_feedback_handler,
            create_feedback_tools,
        )

        tools = create_feedback_tools()
        tool_handler: ToolHandler = create_feedback_handler(
            self.project_dir,
            provider=self.llm_config.provider,
            model=self.llm_config.tiers.get("default"),
            on_tool_use=self.backend.on_tool_use,
        )

        while True:
            try:
                user_input: str = _multiline_input()
            except (EOFError, KeyboardInterrupt):
                break
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit"):
                break

            response: str = self.chat(
                user_input, tools=tools, tool_handler=tool_handler,
            )
            print(f"\nAssistant: {response}\n")

    def show_status(self) -> None:
        """Show current project status."""
        print(f"\n{'=' * 80}")
        print("PROJECT STATUS")
        print("=" * 80)

        print(f"\nProject directory: {self.project_dir}")
        print(f"Protocol exists: {self.protocol_dir.exists()}")

        if self.protocol_dir.exists():
            print("\nProtocol contents:")
            for root, _dirs, files in os.walk(self.protocol_dir):
                level: int = root.replace(str(self.protocol_dir), "").count(os.sep)
                indent: str = "  " * level
                print(f"{indent}{os.path.basename(root)}/")
                sub_indent: str = "  " * (level + 1)
                for file in files:
                    print(f"{sub_indent}{file}")

    def show_packet_status(self) -> None:
        """Show packet status report."""
        if not self.protocol_dir.exists():
            print(f"\nNo {self.protocol_dir} directory found. Run main clarity agent first.")
            return

        report: PacketStatusReport = check_packet_status(self.protocol_dir)
        print()
        print(format_report(report, verbose=True))

    def run_brainstorm(self, command: str) -> None:
        """Run AI-driven failure brainstorming via the process guide."""
        if not self.protocol_dir.exists():
            print(f"\nNo {self.protocol_dir} directory found. Run main clarity agent first.")
            return
        self.run_custom_process("failure-brainstorming")

    def run_packet(
        self,
        *,
        include: list[str] | None = None,
        output: str | None = None,
        fmt: str = "markdown",
        show_list: bool = False,
    ) -> None:
        """Generate a review packet and write it to a file."""
        from clarity_agent.packet import (
            PacketError,
            generate_packet,
            list_formats,
            list_sources,
        )

        if show_list:
            print(f"\nAvailable sources: {', '.join(list_sources())}")
            print(f"Available formats: {', '.join(list_formats())}")
            return

        if not self.protocol_dir.exists():
            print(f"\nNo {self.protocol_dir} directory found. Run main clarity agent first.")
            return

        if output is None:
            ext: str = "md" if fmt == "markdown" else fmt
            output = f"packet.{ext}"

        print(f"\n{'=' * 80}")
        print("GENERATING REVIEW PACKET")
        print(f"{'=' * 80}")

        sources_desc: str = ", ".join(include) if include else "all"
        print(f"\n  Sources: {sources_desc}")
        print(f"  Format:  {fmt}")
        print(f"  Output:  {output}")

        try:
            content: bytes = generate_packet(
                self.protocol_dir, include=include, format=fmt,
            )
        except PacketError as e:
            print(f"\n  Error: {e}")
            return

        output_path: Path = Path(output)
        output_path.write_bytes(content)
        print(f"\n  Packet written to {output_path.resolve()}")


def _multiline_input(label: str = "You: ") -> str:
    """Read multiline input. Enter adds a newline; Alt+Enter submits."""
    return pt_prompt(label, multiline=True).strip()


def _parse_packet_command(command: str) -> dict[str, Any]:
    """Parse an interactive-mode packet command into keyword arguments.

    Handles syntax like::

        packet                          # all sources, default format
        packet problem,failures         # specific sources
        packet -o review.md             # custom output
        packet --format docx            # explicit format
        packet --list                   # show available sources/formats
    """
    parts: list[str] = command.split()
    kwargs: dict[str, Any] = {}

    i: int = 1  # skip "packet"
    while i < len(parts):
        if parts[i] == "--list":
            kwargs["show_list"] = True
            i += 1
        elif parts[i] == "-o" and i + 1 < len(parts):
            kwargs["output"] = parts[i + 1]
            i += 2
        elif parts[i] == "--format" and i + 1 < len(parts):
            kwargs["fmt"] = parts[i + 1]
            i += 2
        else:
            kwargs["include"] = parts[i].split(",")
            i += 1

    return kwargs
