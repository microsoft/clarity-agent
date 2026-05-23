"""
FastAPI application for the Clarity Agent web UI.

Provides:
- WebSocket ``/ws/chat`` for real-time chat with tool-use streaming
- REST endpoints for protocol browsing, packet status, transcripts, and packets
- Static file serving for the built React SPA
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from clarity_agent.app_paths import protocol_dir as _protocol_dir
from clarity_agent.llm import LLMConfig
from clarity_agent.web.models import FeedbackRequest, ModelOverrideRequest, PacketRequest
from clarity_agent.web.session_manager import WebSessionAdapter

# Canonical directory ordering for the protocol tree sidebar.
_DIR_ORDER: list[str] = [
    ".", "goal", "solution", "failures", "decisions", "mailboxes", "archive",
]


def _dir_sort_key(rel_path: str) -> tuple[int, str]:
    """Return a sort key that orders files by canonical directory, then name."""
    parts = rel_path.split("/")
    top_dir = parts[0] if len(parts) > 1 else "."
    order = _DIR_ORDER.index(top_dir) if top_dir in _DIR_ORDER else len(_DIR_ORDER)
    return (order, rel_path)


async def _drain_events(
    session: Any,
    task: asyncio.Task[Any],
    ws: Any,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Stream events from *session* to *ws* until a ``response`` arrives.

    If *stop_event* is set (by the WebSocket read loop receiving a stop
    message), we cancel the drain, synthesize a partial response, and return.

    This function never reads from the WebSocket — only the main loop does.
    """
    event_iter = session.get_events().__aiter__()

    while True:
        event_future = asyncio.ensure_future(event_iter.__anext__())

        waiters: list[asyncio.Future[Any]] = [event_future, task]
        # Also wait on the stop event if provided.
        stop_future: asyncio.Future[Any] | None = None
        if stop_event and not stop_event.is_set():
            stop_future = asyncio.ensure_future(stop_event.wait())
            waiters.append(stop_future)

        done, _ = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)

        # --- Stop requested ---
        if stop_future and stop_future in done:
            event_future.cancel()
            session.cancel()
            # Send a synthetic response with whatever streamed text we have.
            await ws.send_json({"type": "response", "content": "(stopped)"})
            # Drain any leftover events the backend thread may still queue
            # (tool events, the real response, etc.) so they don't leak
            # into the next turn.  Wait briefly for the task to finish.
            try:
                await asyncio.wait_for(task, timeout=30.0)
            except Exception:
                pass  # Backend is stuck or errored — move on.
            # Flush the event queue.
            while not session._event_queue.empty():
                try:
                    session._event_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            return

        if stop_future and stop_future not in done:
            stop_future.cancel()

        # --- Backend event arrived ---
        if event_future in done:
            event = event_future.result()
            await ws.send_json(event)
            if event.get("type") == "response":
                await task
                return
        else:
            event_future.cancel()

        # --- Task completed (possibly with error) before event ---
        if task in done and event_future not in done:
            task.result()  # raises if the task failed
            return


def create_app(
    project_dir: Path,
    clarity_agent_dir: Path,
    llm_config: LLMConfig,
    static_dir: Path | None = None,
    theme: str = "sage",
    env_path: Path | None = None,
    llm_session_id: str | None = None,
) -> FastAPI:
    """Create the FastAPI application.

    Args:
        project_dir: The project being analyzed.
        clarity_agent_dir: Path to clarity-agent installation.
        llm_config: Resolved LLM configuration.
        static_dir: Path to built React app (``web/dist/``), or ``None``
            for API-only mode.
        theme: UI color theme name.
        env_path: Path to ``.env`` file for the setup wizard.
    """
    # Reconcile ``project_dir/AGENTS.md`` against the current layout
    # at app-construction time — i.e. exactly once per sidecar
    # startup, which is exactly once per "open this directory" event
    # in the desktop / launcher model.  Doing it here (rather than
    # waiting for the first WebSocket chat connection) means AGENTS.md
    # is current before *any* endpoint — WS or REST — runs against it.
    # The helper is idempotent; in the common case (already current)
    # the cost is one file read + comparison and no write.  The
    # ``WebSessionAdapter.start`` hook is kept as defense-in-depth
    # for direct-construction paths (tests, etc.).
    from clarity_agent.setup.snippet import (
        EnsureStatus,
        ensure_for_project,
    )
    _ensure_status = ensure_for_project(project_dir, clarity_agent_dir)
    if _ensure_status is not None and _ensure_status is not EnsureStatus.UNCHANGED:
        print(
            f"  [agents.md] {_ensure_status.value}: "
            f"{project_dir / 'AGENTS.md'}",
            flush=True,
        )

    def _classify_ws_error(error: Exception, provider: str) -> dict[str, Any]:
        """Build a classified error message for the WebSocket client."""
        from clarity_agent.setup.doctor import _classify_error
        hint = _classify_error(error, provider)
        msg = str(error)
        # Strip the misleading SDK boilerplate when there's nothing on stderr.
        msg = msg.replace("\nError output: Check stderr output for details", "")
        # Determine category and retryability
        msg_lower = msg.lower()
        if "exit code" in msg_lower or "command failed" in msg_lower:
            # CLI crash — check for auth hints before classifying generically.
            category, retryable = "backend_crash", True
            if "auth" in msg_lower or "authentication" in msg_lower:
                category, retryable = "auth", False
            if llm_config and llm_config.auth_mode == "claude_sdk" and not hint:
                hint = (
                    "The Claude CLI process exited unexpectedly. "
                    "Run 'claude auth status' in your terminal to verify "
                    "authentication, or 'claude --version' to check the CLI."
                )
        elif "auth" in msg_lower or "api key" in msg_lower or "401" in msg_lower or "403" in msg_lower:
            category, retryable = "auth", False
        elif "rate" in msg_lower or "429" in msg_lower:
            category, retryable = "rate_limit", True
        elif "billing" in msg_lower or "payment" in msg_lower or "quota" in msg_lower:
            category, retryable = "billing", False
        elif "connection" in msg_lower or "timeout" in msg_lower or "resolve" in msg_lower:
            category, retryable = "network", True
        else:
            category, retryable = "unknown", True
        return {
            "type": "error",
            "message": msg,
            "category": category,
            "hint": hint,
            "retryable": retryable,
        }

    state: dict[str, Any] = {"session": None, "llm_config": llm_config}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        if state["session"] is not None:
            await state["session"].stop()

    app = FastAPI(title="Clarity Agent", lifespan=lifespan)

    # Setup wizard routes — pass state so configure can reload the LLM config
    from clarity_agent.app_paths import clarity_env_path
    from clarity_agent.web.settings_routes import init as settings_init
    from clarity_agent.web.settings_routes import router as settings_router
    from clarity_agent.web.setup_routes import init as setup_init
    from clarity_agent.web.setup_routes import router as setup_router
    _env_path = env_path if env_path is not None else clarity_env_path()
    setup_init(env_path=_env_path, clarity_agent_dir=clarity_agent_dir, app_state=state)
    settings_init(app_state=state)
    app.include_router(setup_router)
    app.include_router(settings_router)

    # ------------------------------------------------------------------
    # WebSocket: Chat
    # ------------------------------------------------------------------

    @app.websocket("/ws/chat")
    async def websocket_chat(ws: WebSocket) -> None:
        await ws.accept()

        # Guard: if no LLM provider is configured, tell the frontend.
        current_config: LLMConfig = state["llm_config"]
        if current_config.provider == "none":
            await ws.send_json({
                "type": "error",
                "message": "No LLM provider configured.",
                "category": "setup_required",
                "hint": "Complete the setup wizard to configure an LLM provider.",
                "retryable": False,
            })
            # Reject everything until setup completes.  The frontend
            # finishes setup with ``window.location.reload()``, which
            # drops this socket; the next connection re-evaluates
            # provider config from scratch.
            try:
                while True:
                    await ws.receive_json()
                    await ws.send_json({
                        "type": "error",
                        "message": "No LLM provider configured. Complete setup first.",
                        "category": "setup_required",
                        "retryable": False,
                    })
            except WebSocketDisconnect:
                return

        # Create session on first connection (or after config reload).
        if state["session"] is None:
            # Pick up the latest config in case activate_provider rebuilt it.
            current_config = state["llm_config"]
            session = WebSessionAdapter(
                project_dir, clarity_agent_dir, current_config,
                llm_session_id=llm_session_id,
            )
            try:
                await session.start()
            except (RuntimeError, OSError, ValueError) as e:
                # Backend construction failed before we ever got to a
                # chat turn — e.g. ``gh`` CLI missing on the github
                # provider, claude CLI missing on the SDK auth path,
                # malformed API key.  Without this branch the error
                # propagates out of ``websocket_chat`` and uvicorn
                # logs it to stderr while closing the socket with no
                # message; the FE then reconnects, hits the same
                # failure, and the user just sees "thinking" dots
                # forever (issue #47).  Surface it as a classified
                # error_event and keep the socket open the way the
                # no-provider path does, so a banner has a chance to
                # render.  The session ``state["session"]`` stays
                # ``None`` — once the user resolves the underlying
                # problem (e.g. installs gh) and reloads, the next
                # connection retries ``session.start()`` from scratch.
                error_event = _classify_ws_error(e, current_config.provider)
                try:
                    await ws.send_json(error_event)
                    while True:
                        await ws.receive_json()
                        await ws.send_json(error_event)
                except (WebSocketDisconnect, RuntimeError):
                    return
            state["session"] = session

        session: WebSessionAdapter = state["session"]

        # Message queue: a single WS reader task puts messages here,
        # and the main loop consumes them. This avoids concurrent
        # ws.receive_json() calls which Starlette doesn't support.
        msg_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        stop_event = asyncio.Event()

        async def _ws_reader() -> None:
            """Read WS messages in a loop, dispatch to queue or stop event."""
            try:
                while True:
                    data = await ws.receive_json()
                    if data.get("type") == "stop":
                        stop_event.set()
                    else:
                        await msg_queue.put(data)
            except (WebSocketDisconnect, RuntimeError):
                # Connection closed — put a sentinel to unblock the main loop.
                await msg_queue.put({"type": "_disconnect"})

        reader_task = asyncio.create_task(_ws_reader())

        try:
            while True:
                data: dict[str, Any] = await msg_queue.get()
                msg_type: str = data.get("type", "")

                if msg_type == "_disconnect":
                    return

                if msg_type == "chat":
                    message: str = data.get("message", "")
                    if not message:
                        await ws.send_json({"type": "error", "message": "Empty message"})
                        continue

                    stop_event.clear()
                    try:
                        chat_task = asyncio.create_task(
                            session.chat(message, data.get("system_prompt")),
                        )
                        await _drain_events(session, chat_task, ws, stop_event)
                    except WebSocketDisconnect:
                        return
                    except Exception as e:
                        # Backend errors (RuntimeError from a CLI
                        # crash, auth failures, network blips) all
                        # land here: surface as a classified
                        # error_event so the user sees what went
                        # wrong, then ``continue`` the outer loop so
                        # they can retry without reconnecting.
                        # ``ws.send_json`` itself can raise
                        # ``RuntimeError`` / ``WebSocketDisconnect``
                        # if the socket died between turns — in that
                        # case there's nothing left to surface to,
                        # exit cleanly.
                        import traceback
                        tb = traceback.format_exc()
                        print(f"  [Chat error] {e}\n{tb}", flush=True)
                        try:
                            await ws.send_json(_classify_ws_error(e, current_config.provider))
                        except (WebSocketDisconnect, RuntimeError):
                            return

                elif msg_type == "start_process":
                    process_name: str = data.get("process", "")
                    if not process_name:
                        await ws.send_json({"type": "error", "message": "No process name"})
                        continue

                    stop_event.clear()
                    try:
                        chat_task = asyncio.create_task(
                            session.start_process(process_name),
                        )
                        await _drain_events(session, chat_task, ws, stop_event)
                    except WebSocketDisconnect:
                        return
                    except Exception as e:
                        # Same handling as the ``chat`` branch above —
                        # see the comment there for the rationale.
                        import traceback
                        tb = traceback.format_exc()
                        print(f"  [Process error] {e}\n{tb}", flush=True)
                        try:
                            await ws.send_json(_classify_ws_error(e, current_config.provider))
                        except (WebSocketDisconnect, RuntimeError):
                            return

                elif msg_type == "set_model_override":
                    tier: str = data.get("tier", "auto")
                    if tier == "auto" or tier == "default":
                        session.model_override = None
                    else:
                        session.model_override = tier
                    # Re-resolve active model from current state.
                    resolved = session._resolve_model(session.current_process)
                    session._update_active_model(resolved, session.current_process)
                    await ws.send_json({
                        "type": "model_changed",
                        "tier": session.active_tier,
                        "model": session.active_model,
                        "auto": session.model_override is None,
                    })

                else:
                    await ws.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    })

        except WebSocketDisconnect:
            pass
        finally:
            reader_task.cancel()

    # ------------------------------------------------------------------
    # REST: Process registry
    # ------------------------------------------------------------------

    @app.get("/api/processes")
    async def list_processes() -> dict[str, Any]:
        """Return process metadata for the UI."""
        from clarity_agent.process_registry import PROCESS_METADATA

        return {
            "processes": [
                {
                    "name": m.name,
                    "display_name": m.display_name,
                    "one_liner": m.one_liner,
                    "tier": m.tier,
                    "category": m.category,
                }
                for m in PROCESS_METADATA.values()
            ],
        }

    # ------------------------------------------------------------------
    # REST: Protocol
    # ------------------------------------------------------------------

    @app.get("/api/protocol/tree")
    async def protocol_tree() -> dict[str, Any]:
        """Return the protocol directory structure."""
        protocol_dir: Path = _protocol_dir(project_dir)
        if not protocol_dir.exists():
            return {"exists": False, "tree": []}

        tree: list[dict[str, str]] = []
        for root, dirs, files in os.walk(protocol_dir):
            # Skip hidden directories and __pycache__
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]
            rel_root = Path(root).relative_to(protocol_dir)
            for f in sorted(files):
                if f.startswith("."):
                    continue
                rel_path = (rel_root / f).as_posix() if str(rel_root) != "." else f
                tree.append({"path": rel_path, "name": f})
        tree.sort(key=lambda item: _dir_sort_key(item["path"]))
        return {"exists": True, "tree": tree}

    @app.get("/api/protocol/document/{path:path}")
    async def read_document(path: str) -> dict[str, str]:
        """Read a single protocol document."""
        protocol_dir: Path = _protocol_dir(project_dir)
        file_path: Path = (protocol_dir / path).resolve()
        # Path traversal protection
        if not str(file_path).startswith(str(protocol_dir.resolve())):
            raise HTTPException(status_code=403, detail="Path traversal")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Not found")
        return {"path": path, "content": file_path.read_text(encoding="utf-8")}

    # ------------------------------------------------------------------
    # REST: Packet Status
    # ------------------------------------------------------------------

    @app.get("/api/packet-status")
    async def packet_status() -> dict[str, Any]:
        """Return the full packet status report as JSON."""
        from clarity_agent.protocol.packet_status import (
            check_decision_triggers,
            check_packet_status,
            check_process_availability,
            next_action,
        )

        protocol_dir: Path = _protocol_dir(project_dir)
        if not protocol_dir.exists():
            raise HTTPException(status_code=404, detail="No protocol directory")

        report = check_packet_status(protocol_dir)
        dreport = check_decision_triggers(protocol_dir)
        action = next_action(report)
        phases = check_process_availability(report)
        return {
            "report": report,
            "decisions": dreport,
            "next_action": action,
            "process_availability": phases,
        }

    # ------------------------------------------------------------------
    # REST: Transcripts
    # ------------------------------------------------------------------

    @app.get("/api/transcripts")
    async def list_transcripts() -> dict[str, Any]:
        """List available transcripts."""
        transcript_dir: Path = _protocol_dir(project_dir) / "transcripts"
        if not transcript_dir.exists():
            return {"transcripts": []}
        files = sorted(transcript_dir.glob("*.md"), reverse=True)
        return {
            "transcripts": [
                {"name": f.name, "modified": f.stat().st_mtime}
                for f in files
            ],
        }

    @app.get("/api/transcripts/{name}")
    async def read_transcript(name: str) -> dict[str, str]:
        """Read a single transcript."""
        transcript_dir: Path = _protocol_dir(project_dir) / "transcripts"
        path: Path = (transcript_dir / name).resolve()
        # Path traversal protection
        if not str(path).startswith(str(transcript_dir.resolve())):
            raise HTTPException(status_code=403, detail="Path traversal")
        if not path.exists():
            raise HTTPException(status_code=404, detail="Not found")
        return {"name": name, "content": path.read_text(encoding="utf-8")}

    # ------------------------------------------------------------------
    # REST: Packets
    # ------------------------------------------------------------------

    @app.get("/api/packet/options")
    async def packet_options() -> dict[str, Any]:
        """Return available sources, formats, part groupings, views, and size estimates."""
        from clarity_agent.packet import (
            estimate_source_sizes,
            list_formats,
            list_parts,
            list_sources_with_titles,
            list_views_with_parts,
        )

        protocol_dir: Path = _protocol_dir(project_dir)
        source_sizes = estimate_source_sizes(protocol_dir) if protocol_dir.exists() else {}

        return {
            "sources": list_sources_with_titles(),
            "formats": list_formats(),
            "parts": list_parts(),
            "views": list_views_with_parts(),
            "source_sizes": source_sizes,
        }

    @app.post("/api/packet/generate")
    async def generate_packet_endpoint(request: PacketRequest) -> Response:
        """Generate and return a review packet."""
        from clarity_agent.packet import PacketError, generate_packet

        protocol_dir: Path = _protocol_dir(project_dir)
        if not protocol_dir.exists():
            raise HTTPException(status_code=404, detail="No protocol directory")

        include = request.sections if request.sections else None
        try:
            content: bytes = generate_packet(
                protocol_dir, include=include, format=request.format,
                view=request.view,
            )
        except PacketError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        ext = "md" if request.format == "markdown" else request.format
        media_type = (
            "text/markdown"
            if request.format == "markdown"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="packet.{ext}"'},
        )

    # ------------------------------------------------------------------
    # REST: Model profile
    # ------------------------------------------------------------------

    @app.get("/api/model-profile")
    async def model_profile() -> dict[str, Any]:
        """Return available tiers and current model state."""
        cfg: LLMConfig = state["llm_config"]
        s: WebSessionAdapter | None = state["session"]

        # Build tiers: start with backend defaults, overlay user overrides.
        backend = s._backend if s else None
        tiers: dict[str, str] = {}
        if backend:
            tiers.update(backend.TIER_DEFAULTS)
        tiers.update(cfg.tiers)

        return {
            "tiers": tiers,
            "override": s.model_override if s else None,
            "auto": s.model_override is None if s else True,
            "active_model": s.active_model if s else cfg.tiers["default"],
            "active_tier": s.active_tier if s else "default",
        }

    @app.put("/api/model-profile/override")
    async def set_model_override(request: ModelOverrideRequest) -> dict[str, Any]:
        """Set or clear a manual model tier override."""
        s: WebSessionAdapter | None = state["session"]
        if s is None:
            raise HTTPException(status_code=400, detail="No active session")

        tier = request.tier

        if tier == "auto":
            s.model_override = None
            s._update_active_model(
                s._resolve_model(s.current_process), s.current_process,
            )
        elif tier == "default":
            s.model_override = None
            s._update_active_model(None, None)
        else:
            # Store tier name or model string; backend resolves at chat time.
            s.model_override = tier
            s._update_active_model(tier, s.current_process)

        return {
            "override": s.model_override,
            "auto": s.model_override is None,
            "active_model": s.active_model,
            "active_tier": s.active_tier,
        }

    # ------------------------------------------------------------------
    # REST: Conversation thread
    # ------------------------------------------------------------------

    @app.post("/api/thread/new-chapter")
    async def new_chapter() -> dict[str, Any]:
        """Roll the conversation thread over to a new chapter.

        The current chapter becomes a read-only archive; the next
        user message starts a fresh SDK conversation with no
        carried-over context.  See :meth:`WebSessionAdapter.start_new_chapter`.
        """
        s: WebSessionAdapter | None = state["session"]
        if s is None:
            raise HTTPException(
                status_code=409,
                detail="No active session to start a new chapter on.",
            )
        chapter = s.start_new_chapter()
        return {"chapter": chapter}

    @app.get("/api/thread/current-chapter")
    async def current_chapter_messages() -> dict[str, Any]:
        """Return the current chapter's prior turns as chat messages.

        Used by the frontend at mount to populate the chat panel
        with the user's prior conversation — so opening a project
        immediately shows continuity rather than an empty chat that
        would auto-fire the clarity-agent kickoff.

        Returns ``{"messages": []}`` for fresh projects, projects
        whose current chapter only contains a header, and projects
        with no transcripts directory yet — none of those have
        anything visible to surface.
        """
        from clarity_agent.transcript import Transcript
        return {"messages": Transcript(project_dir).chat_messages()}

    # ------------------------------------------------------------------
    # REST: Session info
    # ------------------------------------------------------------------

    @app.get("/api/session")
    async def session_info() -> dict[str, Any]:
        """Return current session state.

        ``thread_id`` is the persistent identifier of the
        conversation thread for this project — survives reconnects
        and process restarts.  Currently sourced from the backend's
        SDK session id; ``None`` when no thread has been established
        yet.
        """
        cfg: LLMConfig = state["llm_config"]
        s: WebSessionAdapter | None = state["session"]
        return {
            "active": s is not None,
            "thread_id": s.llm_session_id if s else None,
            "process": s.current_process if s else None,
            "project_dir": str(project_dir),
            "backend": cfg.provider,
            "model": cfg.tiers["default"],
            "active_model": s.active_model if s else cfg.tiers["default"],
            "active_tier": s.active_tier if s else "default",
            "theme": theme,
        }

    # ------------------------------------------------------------------
    # REST: Feedback
    # ------------------------------------------------------------------

    @app.post("/api/feedback")
    async def send_feedback(request: FeedbackRequest) -> dict[str, Any]:
        """Assemble and deliver user feedback.

        Tries to upload to Azure Blob Storage.  Falls back to local
        file + mailto: if upload is not configured or fails.
        """
        from clarity_agent.feedback import (
            FeedbackReport,
            gather_llm_info,
            gather_protocol,
            gather_transcript,
            prepare_feedback,
        )

        # Gather optional context.
        llm_info: dict[str, str] = {}
        if request.include_llm_info:
            s: WebSessionAdapter | None = state["session"]
            cfg: LLMConfig = state["llm_config"]
            llm_info = gather_llm_info(
                provider=cfg.provider,
                model=cfg.tiers.get("default"),
                active_model=s.active_model if s else None,
                active_tier=s.active_tier if s else None,
            )

        transcript: str | None = None
        if request.transcript_turns > 0:
            transcript = gather_transcript(
                project_dir, request.transcript_turns,
            )

        protocol: str | None = None
        if request.include_protocol:
            protocol = gather_protocol(project_dir)

        report = FeedbackReport(
            message=request.message,
            contact_ok=request.contact_ok,
            contact_email=request.contact_email,
            llm_info=llm_info,
            transcript_excerpt=transcript,
            protocol_content=protocol,
        )

        result = prepare_feedback(report)

        return {
            "submitted": result.submitted,
            "file_path": str(result.file_path) if result.file_path else None,
        }

    # ------------------------------------------------------------------
    # REST: Update check & apply
    # ------------------------------------------------------------------

    @app.get("/api/update-check")
    async def update_check() -> dict[str, Any]:
        """Check if a newer version of clarity-agent is available."""
        from clarity_agent.setup.updater import check_for_updates

        try:
            status = await asyncio.to_thread(check_for_updates, clarity_agent_dir)
        except Exception:
            return {
                "update_available": False,
                "current_sha": None,
                "remote_sha": None,
                "commit_count": 0,
                "frozen": False,
            }
        return {
            "update_available": status.available,
            "current_sha": status.local_sha[:8] if not status.frozen else status.current_version,
            "remote_sha": (status.remote_sha[:8] if status.remote_sha and not status.frozen
                           else status.latest_version),
            "commit_count": status.commit_count,
            "frozen": status.frozen,
            "current_version": status.current_version,
            "latest_version": status.latest_version,
            "download_url": status.download_url,
        }

    @app.post("/api/update/run")
    async def run_update_endpoint() -> dict[str, Any]:
        """Run the update (git pull, pip install, web rebuild).

        Returns the list of step results. The caller should restart the
        server afterward to pick up the new code.
        """
        from clarity_agent.setup.updater import run_update

        results = await asyncio.to_thread(run_update, clarity_agent_dir)
        return {
            "steps": [
                {"outcome": r.outcome.value, "message": r.message}
                for r in results
            ],
            "success": all(r.outcome.value != "fail" for r in results),
        }

    @app.post("/api/update/restart")
    async def restart_server() -> dict[str, Any]:
        """Restart the server process to pick up updated code."""
        from clarity_agent.setup.updater import schedule_restart
        schedule_restart()
        return {"restarting": True}

    # ------------------------------------------------------------------
    # Static file serving (SPA)
    # ------------------------------------------------------------------

    if static_dir is not None and static_dir.exists():
        # Mount assets directory for hashed static files
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="assets",
            )

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> FileResponse:
            """Serve the React SPA — files if they exist, index.html otherwise."""
            file_path = static_dir / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(static_dir / "index.html"))

    return app
