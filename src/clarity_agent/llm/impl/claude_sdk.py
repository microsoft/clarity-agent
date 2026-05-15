"""Claude Agent SDK chat backend.

Provides a :class:`ChatBackend` implementation that uses the Claude Agent
SDK for tool-using conversations.  Unlike the Anthropic API backends,
this wraps an agent runtime rather than a raw messages API — there is no
corresponding :class:`LLMClient`.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from types import ModuleType
from typing import Any

from clarity_agent.llm.chat import ChatBackend
from clarity_agent.llm.client import extract_tool_detail, truncate
from clarity_agent.llm.impl.anthropic import _ANTHROPIC_TIER_DEFAULTS
from clarity_agent.llm.types import (
    LLMResponse,
    TextBlock,
    TokenUsage,
    ToolHandler,
    ToolUseBlock,
)


def _parse_sdk_usage(usage: dict[str, Any]) -> TokenUsage:
    """Parse a usage dict from the Claude SDK's ResultMessage.

    The SDK may report usage as:
    - ``{"input_tokens": N, "output_tokens": N}`` (Anthropic API style)
    - ``{"total_tokens": N}`` (TaskUsage style, no input/output split)

    Handles both gracefully.
    """
    input_t = usage.get("input_tokens", 0)
    output_t = usage.get("output_tokens", 0)
    if input_t == 0 and output_t == 0:
        # Fallback: total_tokens without a split.
        total = usage.get("total_tokens", 0)
        return TokenUsage(input_tokens=total, output_tokens=0)
    return TokenUsage(input_tokens=input_t, output_tokens=output_t)


class SdkChatBackend(ChatBackend):
    """Chat backend using the Claude Agent SDK.

    Uses the stateless ``query()`` function with ``resume=session_id``
    for multi-turn conversations.  Each :meth:`chat` call is a
    self-contained ``asyncio.run()``, avoiding anyio task group issues
    that arise with ``ClaudeSDKClient`` across multiple
    ``run_until_complete()`` calls.
    """

    supports_tools: bool = True
    # We share defaults with the Anthropic API backend -- same company and same
    # models, just a different interface.
    TIER_DEFAULTS = _ANTHROPIC_TIER_DEFAULTS

    def __init__(
        self,
        *,
        project_dir: Path,
        clarity_agent_dir: Path,
    ) -> None:
        try:
            import claude_agent_sdk
        except ImportError:
            raise ImportError(
                "claude-agent-sdk is not installed. "
                "Install it with: pip install claude-agent-sdk"
            ) from None

        self._sdk: ModuleType = claude_agent_sdk
        self.project_dir: Path = project_dir
        self.clarity_agent_dir: Path = clarity_agent_dir
        self._session_id: str | None = None
        self._current_system_prompt: str | None = None
        self._api_client: Any = None  # lazily-created anthropic.AsyncAnthropic


    @property
    def llm_session_id(self) -> str | None:
        return self._session_id

    @llm_session_id.setter
    def llm_session_id(self, value: str | None) -> None:
        self._session_id = value

    def disconnect(self) -> None:
        self._session_id = None
        self._current_system_prompt = None
        self._api_client = None

    def _build_system_prompt(self, system_prompt: str | None = None) -> str:
        from clarity_agent.app_paths import protocol_dir as _protocol_dir
        pd = _protocol_dir(self.project_dir)
        base: str = (
            "You are running the Clarity Agent framework.  Clarity "
            "helps users think through any kind of project that "
            "involves consequential decisions — a product launch, a "
            "research direction, a hiring plan, a career pivot, a "
            "policy question, a software system, or anything else "
            "where the thinking IS the work.  Do NOT assume the user "
            "is building software or writing code unless they tell "
            "you they are; let them describe the project in their own "
            "terms.\n\n"
            f"The project directory is: {self.project_dir}\n"
            f"Your working directory is the project root. "
            f"The protocol directory is: {pd}\n\n"
            f"The clarity-agent installation directory is: {self.clarity_agent_dir}\n"
            f"Process guides are at: {self.clarity_agent_dir / 'processes'}/\n"
            f"Thinker guides are at: {self.clarity_agent_dir / 'thinkers'}/\n\n"
            "Follow the process guides exactly as written. "
            f"Create actual files in the protocol directory ({pd}) as specified.\n"
            "Use the tools available to you (Read, Write, Edit, Bash, Glob, Grep) "
            "to actually create and modify files."
        )

        if system_prompt:
            base += f"\n\n{system_prompt}"
        return base

    async def _async_chat(
        self,
        user_message: str,
        system_prompt: str | None = None,
        *,
        model: str | None = None,
    ) -> str:
        # When a new system_prompt is provided, start a fresh session
        if system_prompt:
            full_prompt: str = self._build_system_prompt(system_prompt)
            if full_prompt != self._current_system_prompt:
                self._session_id = None
                self._current_system_prompt = full_prompt

        result = await self._run_query(user_message, model=model)

        # If we got nothing and had a stale session, retry without resume.
        if not result and self._session_id is not None:
            print("  [Session] Resume returned empty — retrying fresh", flush=True)
            self._session_id = None
            result = await self._run_query(user_message, model=model)

        return result

    async def _run_query(
        self,
        user_message: str,
        *,
        model: str | None = None,
    ) -> str:
        """Execute a single SDK query, returning the text response."""
        stderr_lines: list[str] = []

        def _capture_stderr(line: str) -> None:
            stderr_lines.append(line)
            print(f"  [Claude CLI stderr] {line}", flush=True)

        had_session = self._session_id is not None

        options = self._sdk.ClaudeAgentOptions(
            system_prompt=self._current_system_prompt,
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            permission_mode="bypassPermissions",
            model=self.resolve_model(model),
            cwd=str(self.project_dir),
            max_turns=25,
            resume=self._session_id,
            stderr=_capture_stderr,
        )

        text_parts: list[str] = []
        try:
            async for message in self._sdk.query(
                prompt=user_message,
                options=options,
            ):
                if isinstance(message, self._sdk.AssistantMessage):
                    for block in message.content:
                        if isinstance(block, self._sdk.TextBlock):
                            text_parts.append(block.text)
                            # Note: the SDK yields complete TextBlocks, not
                            # incremental deltas.  This fires once with the
                            # full text — real token-by-token streaming is
                            # only available via the direct API backends.
                            if self.on_text_delta:
                                self.on_text_delta(block.text)
                        elif isinstance(block, self._sdk.ToolUseBlock):
                            detail = extract_tool_detail(block.name, block.input)
                            print(f"  [Tool] {block.name} -> {truncate(detail)}")
                            if self.on_tool_use:
                                self.on_tool_use(block.name, detail)
                            # Structured tool-call callback for the
                            # transcript layer — preserves the
                            # provider-assigned id and full input
                            # dict that the flattened on_tool_use
                            # discards.  Both callbacks fire here in
                            # parallel; consumers subscribe to
                            # whichever fits their needs.
                            if self.on_tool_call:
                                self.on_tool_call(ToolUseBlock(
                                    id=block.id,
                                    name=block.name,
                                    input=block.input,
                                ))
                elif isinstance(message, self._sdk.ResultMessage):
                    self._session_id = message.session_id
                    if message.total_cost_usd is not None:
                        print(f"  [Cost] ${message.total_cost_usd:.4f}")
                        if self.on_cost:
                            self.on_cost(message.total_cost_usd)
                    if message.usage and self.on_usage:
                        self.on_usage(_parse_sdk_usage(message.usage))
        except Exception as e:
            # If we were resuming a stale session, clear it and let the
            # caller retry from scratch rather than raising immediately.
            if had_session and not text_parts:
                print(f"  [Session] Resume failed ({e}) — will retry fresh", flush=True)
                self._session_id = None
                return ""

            # The Claude CLI sometimes crashes during cleanup *after*
            # delivering a complete response (text + ResultMessage).
            # If we already have a response, treat it as successful.
            if text_parts and self._session_id is not None:
                warn_msg = f"CLI exited with error after delivering response: {e}"
                print(f"  [Warning] {warn_msg}", flush=True)
                if self.on_warning:
                    self.on_warning(warn_msg)
            elif stderr_lines:
                stderr_text = "\n".join(stderr_lines[-20:])
                raise RuntimeError(
                    f"Claude CLI failed: {e}\n\nCLI stderr:\n{stderr_text}"
                ) from e
            else:
                # No stderr captured.  If this looks like a CLI exit-code
                # failure, provide an actionable message instead of the raw
                # SDK error which unhelpfully says "Check stderr output for
                # details" when there is no captured output to show.
                msg = str(e)
                if "exit code" in msg.lower() or "command failed" in msg.lower():
                    raise RuntimeError(
                        "The Claude CLI process exited unexpectedly. "
                        "This often indicates an authentication problem — "
                        "run 'claude auth status' in your terminal to verify. "
                        f"(SDK: {msg})"
                    ) from e
                raise

        return "\n".join(text_parts)

    def chat(
        self,
        user_message: str,
        system_prompt: str | None = None,
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_handler: ToolHandler | None = None,
    ) -> str:
        # SDK backend: tools are described as Bash commands prepended to
        # the system prompt.  The AI invokes them via its built-in Bash
        # tool.  The CLI tools auto-discover .clarity-protocol from cwd,
        # so the commands require no flags — just JSON on stdin.
        #
        # tool_handler is intentionally unused — the CLI handles execution.
        # Only prepend on the initial call (system_prompt is provided).
        _ = tool_handler
        if tools and system_prompt is not None:
            from clarity_agent.ai_actions import format_tools_as_cli
            cli_section = format_tools_as_cli(tools)
            system_prompt = cli_section + "\n\n" + system_prompt
        return asyncio.run(self._async_chat(user_message, system_prompt, model=model))

    def _has_api_key(self) -> bool:
        """Check whether a direct Anthropic API key is available."""
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    # ------------------------------------------------------------------
    # Tool-schema encoding for SDK fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _format_tools_for_prompt(tools: list[dict[str, Any]]) -> str:
        """Render Anthropic-style tool schemas as human-readable text."""
        if not tools:
            return ""
        parts: list[str] = []
        for tool in tools:
            name = tool.get("name", "unknown")
            desc = tool.get("description", "")
            parts.append(f"### {name}\n{desc}\n")
            schema = tool.get("input_schema", {})
            props = schema.get("properties", {})
            required = set(schema.get("required", []))
            if props:
                parts.append("Parameters:")
                for pname, pinfo in props.items():
                    ptype = pinfo.get("type", "any")
                    pdesc = pinfo.get("description", "")
                    req = " (required)" if pname in required else ""
                    parts.append(f"  - {pname} ({ptype}{req}): {pdesc}")
            parts.append("")
        return "\n".join(parts)

    _TOOL_CALL_RE = re.compile(
        r"```tool_call\s*\n(.*?)\n\s*```", re.DOTALL,
    )

    @classmethod
    def _parse_text_tool_calls(
        cls, text: str,
    ) -> list[dict[str, Any]]:
        """Extract tool-call JSON blocks from model text output."""
        results: list[dict[str, Any]] = []
        for match in cls._TOOL_CALL_RE.finditer(text):
            raw = match.group(1).strip()
            try:
                parsed = json.loads(raw)
                if "name" in parsed and "input" in parsed:
                    results.append(parsed)
            except json.JSONDecodeError:
                continue
        return results

    @classmethod
    def _strip_tool_calls(cls, text: str) -> str:
        """Remove ```tool_call fences from model output."""
        return cls._TOOL_CALL_RE.sub("", text).strip()

    # ------------------------------------------------------------------
    # arun_tool_loop — primary entry point
    # ------------------------------------------------------------------

    async def arun_tool_loop(
        self,
        *,
        user_message: str,
        system_prompt: str | None = None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_handler: ToolHandler | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Run a tool-use loop.

        When an ``ANTHROPIC_API_KEY`` is available, uses the raw Anthropic
        messages API with native tool-use support.  Otherwise, falls back to
        the Claude Agent SDK's ``query()`` with tool schemas encoded as text
        in the prompt and tool calls parsed from ``tool_call`` code fences.
        """
        if self._has_api_key():
            return await self._arun_tool_loop_api(
                user_message=user_message,
                system_prompt=system_prompt,
                model=model,
                tools=tools,
                tool_handler=tool_handler,
                max_tokens=max_tokens,
            )
        return await self._arun_tool_loop_sdk(
            user_message=user_message,
            system_prompt=system_prompt,
            model=model,
            tools=tools,
            tool_handler=tool_handler,
        )

    # ------------------------------------------------------------------
    # Path A: direct Anthropic API (when API key is available)
    # ------------------------------------------------------------------

    async def _arun_tool_loop_api(
        self,
        *,
        user_message: str,
        system_prompt: str | None = None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_handler: ToolHandler | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        if self._api_client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise ImportError(
                    "The 'anthropic' package is required for tool-use loops "
                    "with the Claude SDK backend. "
                    "Install with: pip install anthropic"
                ) from exc
            self._api_client = anthropic.AsyncAnthropic()

        resolved_model: str = self.resolve_model(model)
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_message},
        ]

        while True:
            kwargs: dict[str, Any] = {
                "model": resolved_model,
                "max_tokens": max_tokens,
                "messages": messages,
            }
            if system_prompt is not None:
                kwargs["system"] = system_prompt
            if tools:
                kwargs["tools"] = tools

            api_response = await self._api_client.messages.create(**kwargs)

            # Convert to normalized types.
            content: list[TextBlock | ToolUseBlock] = []
            for block in api_response.content:
                if block.type == "text":
                    content.append(TextBlock(text=block.text))
                elif block.type == "tool_use":
                    content.append(ToolUseBlock(
                        id=block.id,
                        name=block.name,
                        input=block.input,
                    ))

            usage = None
            if hasattr(api_response, "usage") and api_response.usage:
                usage = TokenUsage(
                    input_tokens=api_response.usage.input_tokens,
                    output_tokens=api_response.usage.output_tokens,
                )
                if self.on_usage:
                    self.on_usage(usage)

            response = LLMResponse(content=content, stop_reason=api_response.stop_reason, usage=usage)

            # Process tool calls via handler and fire callbacks.
            tool_results: list[dict[str, Any]] = []
            for tc in response.tool_calls:
                # Structured callback fires regardless of whether a
                # handler is supplied — transcript consumers want
                # every tool call recorded.
                if self.on_tool_call:
                    self.on_tool_call(tc)
                if tool_handler is None:
                    detail = extract_tool_detail(tc.name, tc.input)
                    print(f"  [Tool] {tc.name} -> {detail}")
                    if self.on_tool_use:
                        self.on_tool_use(tc.name, detail)

                result_text: str = "OK"
                if tool_handler is not None:
                    result_text = tool_handler(tc)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result_text,
                })

            if api_response.stop_reason != "tool_use":
                return response

            # Feed assistant response and tool results back.
            messages.append({
                "role": "assistant",
                "content": response.content_as_dicts,
            })
            messages.append({"role": "user", "content": tool_results})

    # ------------------------------------------------------------------
    # Path B: SDK query() fallback (no API key — e.g. inside Claude Code)
    # ------------------------------------------------------------------

    async def _arun_tool_loop_sdk(
        self,
        *,
        user_message: str,
        system_prompt: str | None = None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_handler: ToolHandler | None = None,
    ) -> LLMResponse:
        """Run a tool-use loop via SDK query() with text-based tool encoding.

        The SDK manages its own authentication, so this works inside
        Claude Code (where no ``ANTHROPIC_API_KEY`` is in the environment).
        Tool schemas are described in the prompt, and the model outputs
        tool calls as ``tool_call`` code-fenced JSON blocks which are
        parsed and dispatched to *tool_handler*.
        """
        tool_section = self._format_tools_for_prompt(tools or [])
        tool_instructions = (
            "## Available Tools\n\n"
            f"{tool_section}\n"
            "To call a tool, output a JSON block in a fenced code block "
            "with the language tag `tool_call`:\n\n"
            "```tool_call\n"
            '{"name": "tool_name", "input": {"param1": "value1"}}\n'
            "```\n\n"
            "You may make multiple tool calls in a single response. "
            "Call every tool you need, then end your response.\n"
        )
        enhanced_prompt = f"{user_message}\n\n{tool_instructions}"

        options = self._sdk.ClaudeAgentOptions(
            system_prompt=system_prompt or "",
            allowed_tools=[],
            permission_mode="bypassPermissions",
            model=self.resolve_model(model),
            cwd=str(self.project_dir),
            max_turns=1,
            fork_session=True,
            env={"CLAUDECODE": ""},
            debug_stderr=None,
        )

        text_parts: list[str] = []
        async for message in self._sdk.query(
            prompt=enhanced_prompt, options=options,
        ):
            if isinstance(message, self._sdk.AssistantMessage):
                for block in message.content:
                    if isinstance(block, self._sdk.TextBlock):
                        text_parts.append(block.text)
            elif isinstance(message, self._sdk.ResultMessage):
                if message.total_cost_usd is not None:
                    if self.on_cost:
                        self.on_cost(message.total_cost_usd)
                if message.usage and self.on_usage:
                    self.on_usage(_parse_sdk_usage(message.usage))

        response_text = "\n".join(text_parts)

        # Parse tool calls from the text output.
        parsed_calls = self._parse_text_tool_calls(response_text)

        content: list[TextBlock | ToolUseBlock] = []
        clean_text = self._strip_tool_calls(response_text)
        if clean_text:
            content.append(TextBlock(text=clean_text))

        for i, tc_data in enumerate(parsed_calls):
            tc = ToolUseBlock(
                id=f"sdk_tc_{i}",
                name=tc_data["name"],
                input=tc_data.get("input", {}),
            )
            content.append(tc)

            # Structured callback fires regardless of handler — same
            # rationale as the API-path tool loop above.
            if self.on_tool_call:
                self.on_tool_call(tc)
            if tool_handler is not None:
                tool_handler(tc)
            else:
                detail = extract_tool_detail(tc.name, tc.input)
                print(f"  [Tool] {tc.name} -> {detail}")
                if self.on_tool_use:
                    self.on_tool_use(tc.name, detail)

        return LLMResponse(content=content, stop_reason="end_turn")
