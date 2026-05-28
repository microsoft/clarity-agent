"""Launcher: multi-project server with reverse proxy.

Architecture Overview
---------------------

Clarity supports working on multiple projects simultaneously.  Rather than
switching a single server between projects (which would lose session state),
we run a separate server *subprocess* for each active project and put a thin
launcher in front of them.

The launcher is what the browser actually connects to.  It listens on a
single port (default 8420) and serves the React SPA itself.  When the user
selects a project, the launcher spawns (or reuses) a per-project server on
an ephemeral port and starts proxying traffic to it.  From the browser's
perspective the URL never changes — project switching is invisible.

::

    Browser (localhost:8420)
       │
       ▼
    Launcher (this module, FastAPI on :8420)
       ├── /api/projects/*        handles directly (CRUD, activate/deactivate)
       ├── /api/setup/*           handles directly (shared LLM configuration)
       ├── /ws/chat               bidirectional WebSocket bridge to active project
       └── /api/* (everything else)  HTTP reverse proxy to active project
             │
             ├── Project A server (:49201) ── alive, backgrounded
             ├── Project B server (:49202) ── alive, in foreground (proxied)
             └── Project C server (:49203) ── alive, backgrounded

Two-layer data model
~~~~~~~~~~~~~~~~~~~~

**Project registry** (``~/.clarity/projects.json``, managed by
``clarity_agent.projects.ProjectRegistry``).  Persistent list of known
project directories — name, path, last-opened timestamp, whether a
``.clarity-protocol/`` directory exists.  Survives launcher restarts.  This
is purely a directory-level concept: a project exists in the registry whether
or not it has a running server.

**Process table** (``ProcessTable``, defined below).  In-memory-only tracking
of spawned server subprocesses — project name, PID, port, ``Popen`` handle.
Rebuilt from scratch every time the launcher starts (empty set).  Pruned
automatically when a subprocess dies.

Lifecycle
~~~~~~~~~

1. User clicks a project in the picker (or the frontend activates one).
2. ``POST /api/projects/{name}/activate`` → launcher looks up the project
   in the registry, checks the process table for a running server.
3. If no server is running: find a free ephemeral port (``socket.bind``),
   spawn ``clarity web <path> --port <port>``, poll ``/api/session`` until
   it responds (up to 30 s).
4. Mark the project as "active" — all subsequent HTTP and WebSocket traffic
   is proxied to its port.
5. The old active project's server keeps running in the background.
   Switching back later is instant (no spawn, no health-check wait).

Idle reaping
~~~~~~~~~~~~

A background task checks every 60 seconds for servers that haven't received
a proxied request in 30 minutes.  Idle servers (other than the active one)
are SIGTERM'd and removed from the process table.  They'll be re-spawned on
the next activate.

An ``atexit`` handler calls ``kill_all()`` to clean up all subprocesses when
the launcher itself exits.

CLI modes
~~~~~~~~~

- ``clarity web <dir>`` — single-project mode.  Starts the per-project server
  directly (``create_app`` from ``app.py``), no launcher involved.  This is
  the developer path.

- ``clarity web`` (no directory) — launcher mode.  Starts this module's
  ``create_launcher`` app.  The project picker UI lets the user choose or
  create projects.
"""

from __future__ import annotations

import asyncio
import atexit
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from clarity_agent.projects import ProjectEntry, ProjectRegistry

# ---------------------------------------------------------------------------
# Process table (in-memory, runtime-only)
# ---------------------------------------------------------------------------

@dataclass
class ProcessEntry:
    """A running per-project server subprocess.

    Keyed by ``project_id`` (the registry's path-derived hash) so
    that two projects sharing a display ``project_name`` can coexist
    without overwriting each other in the process table.
    """

    project_id: str
    project_name: str
    pid: int
    port: int
    process: subprocess.Popen[bytes]
    last_activity: float = field(default_factory=time.time)


class ProcessTable:
    """In-memory table of running project server subprocesses, keyed
    by project id.  Display names are not unique (the registry
    allows duplicate labels at different paths) — keying by id
    means two same-named projects can run side-by-side without
    overwriting each other's entries."""

    def __init__(self) -> None:
        self._entries: dict[str, ProcessEntry] = {}

    def get(self, project_id: str) -> ProcessEntry | None:
        entry = self._entries.get(project_id)
        if entry is not None and not self._is_alive(entry):
            del self._entries[project_id]
            return None
        return entry

    def add(self, entry: ProcessEntry) -> None:
        self._entries[entry.project_id] = entry

    def remove(self, project_id: str) -> ProcessEntry | None:
        return self._entries.pop(project_id, None)

    def all(self) -> list[ProcessEntry]:
        self.prune_dead()
        return list(self._entries.values())

    def prune_dead(self) -> None:
        dead = [pid for pid, e in self._entries.items() if not self._is_alive(e)]
        for pid in dead:
            del self._entries[pid]

    def kill_all(self) -> None:
        for entry in self._entries.values():
            try:
                entry.process.terminate()
            except OSError:
                pass
        self._entries.clear()

    def touch(self, project_id: str) -> None:
        entry = self._entries.get(project_id)
        if entry is not None:
            entry.last_activity = time.time()

    def idle_entries(self, max_idle_seconds: float) -> list[ProcessEntry]:
        """Return entries that haven't had activity within the threshold."""
        cutoff = time.time() - max_idle_seconds
        return [e for e in self._entries.values() if e.last_activity < cutoff]

    @staticmethod
    def _is_alive(entry: ProcessEntry) -> bool:
        return entry.process.poll() is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_free_port() -> int:
    """Ask the OS for an ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _wait_for_server(port: int, timeout: float = 30.0) -> bool:
    """Poll until a project server responds on *port*, or timeout."""
    url = f"http://127.0.0.1:{port}/api/session"
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            try:
                resp = await client.get(url, timeout=2.0)
                if resp.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException):
                pass
            await asyncio.sleep(0.3)
    return False


# ---------------------------------------------------------------------------
# Launcher app factory
# ---------------------------------------------------------------------------

_IDLE_TIMEOUT_SECONDS = 30 * 60  # 30 minutes

def create_launcher(
    clarity_agent_dir: Path,
    static_dir: Path | None = None,
    env_path: Path | None = None,
    theme: str = "sage",
) -> FastAPI:
    """Create the launcher FastAPI application.

    Args:
        clarity_agent_dir: Path to clarity-agent installation (for spawning
            project servers and setup routes).
        static_dir: Path to built React app (``web/dist/``).
        env_path: Path to ``.env`` file.
        theme: UI color theme name.
    """
    registry = ProjectRegistry()
    processes = ProcessTable()
    # ``id`` (the registry's stable path-derived hash) — unique
    # even when two projects share a display name.  See the
    # ProcessEntry docstring for why this matters.
    active_project: dict[str, str | None] = {"id": None}

    # Discover projects in the default workspace on startup.
    registry.discover()

    # Restore last-active project id from the persistent registry.
    # ``get_active`` reads the new ``active_id`` key with a legacy
    # fallback to the old name-keyed ``active`` field.
    _persisted_active_id = registry.get_active()
    if _persisted_active_id and registry.get(_persisted_active_id) is not None:
        active_project["id"] = _persisted_active_id

    from clarity_agent.app_paths import clarity_env_path
    _env_path = env_path or clarity_env_path()
    _clarity_py = clarity_agent_dir / "clarity.py"

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Start idle reaper task
        reaper_task = asyncio.create_task(_idle_reaper())
        yield
        reaper_task.cancel()
        processes.kill_all()

    async def _idle_reaper() -> None:
        """Periodically terminate idle project servers."""
        while True:
            await asyncio.sleep(60)
            for entry in processes.idle_entries(_IDLE_TIMEOUT_SECONDS):
                # Don't reap the active project
                if entry.project_id == active_project["id"]:
                    continue
                entry.process.terminate()
                processes.remove(entry.project_id)

    app = FastAPI(title="Clarity Launcher", lifespan=lifespan)

    # Ensure subprocesses are cleaned up on exit.
    atexit.register(processes.kill_all)

    # Setup wizard routes (shared across projects, operates on .env)
    from clarity_agent.web.settings_routes import init as settings_init
    from clarity_agent.web.settings_routes import router as settings_router
    from clarity_agent.web.setup_routes import init as setup_init
    from clarity_agent.web.setup_routes import router as setup_router
    setup_init(
        env_path=_env_path,
        clarity_agent_dir=clarity_agent_dir,
        kill_children=processes.kill_all,
    )
    settings_init(kill_children=processes.kill_all)
    app.include_router(setup_router)
    app.include_router(settings_router)

    # ------------------------------------------------------------------
    # Subprocess management
    # ------------------------------------------------------------------

    def _pipe_output(stream: Any, prefix: str) -> None:
        """Read lines from a subprocess stream and print with a prefix.

        Runs in a daemon thread so the pipe buffer never fills up (which
        would block the subprocess).
        """
        try:
            for line in stream:
                text = line.decode("utf-8", errors="replace").rstrip("\n")
                print(f"  [{prefix}] {text}", flush=True)
        except ValueError:
            # Stream closed
            pass

    def _spawn_server(project: ProjectEntry) -> ProcessEntry:
        """Launch a per-project server subprocess."""
        from clarity_agent.app_paths import is_frozen

        port = _find_free_port()
        # In a frozen (PyInstaller) build, sys.executable is the bundle
        # itself and handles subcommands directly.  In development,
        # we invoke Python with clarity.py as a script.
        if is_frozen():
            cmd = [sys.executable]
        else:
            cmd = [sys.executable, str(_clarity_py)]
        cmd += [
            "web", project.path,
            "--port", str(port),
            "--host", "127.0.0.1",
            "--theme", theme,
        ]
        # Pass stored SDK session ID so the project server can resume
        # the conversation after a launcher restart.
        if project.llm_session_id:
            cmd.extend(["--session-id", project.llm_session_id])
        # Build a clean environment for the project server:
        # - Strip CLAUDECODE to avoid nested-session errors from the CLI.
        # - Ensure PYTHONPATH includes the clarity-agent src/ directory so
        #   that Bash commands like `python -m clarity_agent.protocol...`
        #   work inside the Claude CLI subprocess.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        src_dir = str(clarity_agent_dir / "src")
        existing_pp = env.get("PYTHONPATH", "")
        if src_dir not in existing_pp.split(os.pathsep):
            env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{existing_pp}" if existing_pp else src_dir
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=project.path,
        )
        # Drain stdout/stderr in background threads so the pipe buffer
        # never fills up (a full buffer blocks the subprocess).
        for stream, label in [
            (proc.stdout, f"{project.name}"),
            (proc.stderr, f"{project.name}:err"),
        ]:
            t = threading.Thread(
                target=_pipe_output, args=(stream, label), daemon=True,
            )
            t.start()

        entry = ProcessEntry(
            project_id=project.id,
            project_name=project.name,
            pid=proc.pid,
            port=port,
            process=proc,
        )
        processes.add(entry)
        return entry

    async def _ensure_running(project: ProjectEntry) -> ProcessEntry:
        """Return a running ProcessEntry, spawning if needed."""
        entry = processes.get(project.id)
        if entry is not None:
            processes.touch(project.id)
            return entry

        entry = await asyncio.to_thread(_spawn_server, project)
        ok = await _wait_for_server(entry.port)
        if not ok:
            entry.process.terminate()
            processes.remove(project.id)
            raise RuntimeError(
                f"Project server for {project.name!r} failed to start"
            )
        return entry

    async def _ensure_active_running() -> ProcessEntry | None:
        """If there's an active project, ensure its server is running.

        Returns the ProcessEntry if the server is (now) running, or None
        if there's no active project.  This handles the common case of a
        launcher restart: the active project id is persisted but the
        subprocess is gone.
        """
        project_id = active_project["id"]
        if project_id is None:
            return None
        entry = processes.get(project_id)
        if entry is not None:
            processes.touch(project_id)
            return entry
        # Server not running — try to (re)start it.
        project = registry.get(project_id)
        if project is None or not Path(project.path).is_dir():
            if project is not None:
                registry.remove(project.id)
            active_project["id"] = None
            registry.clear_active()
            return None
        try:
            return await _ensure_running(project)
        except RuntimeError:
            return None

    # ------------------------------------------------------------------
    # REST: Version + update status (handled by the launcher, not
    # proxied — the version is a property of *this* process, the
    # same one the user sees in the menu/badge.  See
    # ``clarity_agent.web.version_endpoint`` for the cache details.
    # The per-project app also serves the same endpoint so
    # single-project mode works without the launcher.
    # ------------------------------------------------------------------

    @app.get("/api/version")
    async def version_info() -> dict[str, Any]:
        # ``clarity_agent_dir`` is needed for the local-mode git
        # check; release builds ignore it.  Hopped onto a worker
        # thread because the git fetch can run for a couple of
        # seconds.  Caching + JSON shaping live in
        # :mod:`~clarity_agent.setup.version`.
        from clarity_agent.setup.version import current_state
        state = await asyncio.to_thread(current_state, clarity_agent_dir)
        return state.to_dict()

    # ------------------------------------------------------------------
    # REST: Project management
    # ------------------------------------------------------------------

    @app.get("/api/projects")
    async def list_projects() -> dict[str, Any]:
        # ``registry.list()`` drops entries whose directories no
        # longer exist on disk and writes the cleaned registry
        # back, so callers see a current view.  We still have to
        # sync the launcher's in-memory ``active_project["id"]``
        # if the pruning happened to drop the active one — the
        # registry can't reach into runtime state.
        projects = registry.list()
        live_ids = {p.id for p in projects}
        if (
            active_project["id"] is not None
            and active_project["id"] not in live_ids
        ):
            active_project["id"] = None
            registry.clear_active()
        running_ids = {e.project_id for e in processes.all()}
        return {
            "projects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "path": p.path,
                    "last_opened": p.last_opened,
                    "has_protocol": p.has_protocol,
                    "running": p.id in running_ids,
                    "active": p.id == active_project["id"],
                }
                for p in projects
            ],
        }

    @app.post("/api/projects")
    async def create_project(body: dict[str, Any]) -> Any:
        """Register a project, possibly setting it up first.

        Body shape::

            {
              "name": str,                              # required
              "path": str | null,                       # required for open_existing
              "intent": "create_new" | "open_existing", # default "open_existing"
              "mode":   "userspace" | "embedded" | null # for open_existing's flow 3
            }

        Behavior (one cell per intent × mode × disk-state combination):

        - ``intent="create_new"``: always USERSPACE.  Creates the
          directory if absent, lays down ``Clarity Protocol/`` + the
          template structure, writes AGENTS.md, registers.
          Returns 200 with the registry entry.
        - ``intent="open_existing"`` with a clean detected layout
          (any mode): registers without touching disk.  Returns 200.
        - ``intent="open_existing"`` with a :class:`LayoutBroken`
          state: returns 409 ``{status: "broken_install", brokenness, ...}``
          so the UI can surface a repair prompt.
        - ``intent="open_existing"`` with no layout and no ``mode``:
          returns 409 ``{status: "needs_setup", looks_like_code, suggested_mode}``
          to drive the SetupPromptDialog.
        - ``intent="open_existing"`` + ``mode="userspace"``: runs
          USERSPACE setup, registers.  Returns 200.
        - ``intent="open_existing"`` + ``mode="embedded"``: returns
          200 ``{status: "embedded_install_required", command}`` with
          the ``clarity install --embedded <path>`` command.  Does
          NOT register — the install hasn't happened yet; the user
          will reopen once it has.
        """
        from clarity_agent.app_paths import (
            clarity_projects_dir,
            get_bundle_dir,
        )
        from clarity_agent.setup.layout import (
            LayoutBroken,
            ProjectLayout,
            detect_layout,
            looks_like_code_directory,
        )
        from clarity_agent.setup.project import setup_userspace_project

        name: str = body.get("name", "").strip()
        path: str | None = body.get("path")
        intent: str = body.get("intent", "open_existing")
        mode: str | None = body.get("mode")

        if not name:
            raise HTTPException(status_code=400, detail="Project name is required")
        if intent not in {"create_new", "open_existing"}:
            raise HTTPException(status_code=400, detail=f"Invalid intent: {intent!r}")
        if mode is not None and mode not in {"userspace", "embedded"}:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode!r}")

        # Resolve the target path.  If unspecified, use the default
        # workspace location (only meaningful for create_new).
        if path:
            project_path = Path(path).resolve()
        else:
            project_path = (clarity_projects_dir() / name).resolve()

        bundle = get_bundle_dir()

        # --- intent: create_new ----------------------------------------
        # Always USERSPACE; no prompt regardless of disk state.
        if intent == "create_new":
            setup_userspace_project(project_path, bundle)
            # Fall through to registry add.

        # --- intent: open_existing -------------------------------------
        else:
            if not project_path.exists():
                raise HTTPException(
                    status_code=400,
                    detail=f"Directory not found: {project_path}",
                )
            layout = detect_layout(project_path, bundled_clarity_agent_dir=bundle)

            if isinstance(layout, ProjectLayout):
                # Clean layout — proceed to registry add.
                pass
            elif isinstance(layout, LayoutBroken):
                # The UI can word the prompt based on the variant.
                return JSONResponse(
                    status_code=409,
                    content={
                        "status": "broken_install",
                        "brokenness": layout.value,
                        "path": str(project_path),
                    },
                )
            else:
                # No markers — decide based on caller's ``mode``.
                if mode is None:
                    code_like = looks_like_code_directory(project_path)
                    return JSONResponse(
                        status_code=409,
                        content={
                            "status": "needs_setup",
                            "looks_like_code": code_like,
                            "suggested_mode": (
                                "embedded" if code_like else "userspace"
                            ),
                            "path": str(project_path),
                        },
                    )
                if mode == "userspace":
                    setup_userspace_project(project_path, bundle)
                    # Fall through to registry add.
                elif mode == "embedded":
                    # Option (ii): we don't run the install ourselves
                    # from the desktop app.  Surface the CLI command;
                    # the user runs it and reopens.  Don't register
                    # — the project isn't a valid Clarity setup yet.
                    return {
                        "status": "embedded_install_required",
                        "command": f"clarity install --embedded {project_path}",
                        "path": str(project_path),
                    }

        # ``registry.add`` is path-keyed and idempotent — same path
        # returns the existing entry, duplicate display names are
        # allowed (two projects in different directories are
        # genuinely different projects).  The name from the request
        # body is supplied as a keyword so the auto-derived default
        # doesn't shadow what the user actually typed.
        try:
            entry = registry.add(project_path, name=name)
        except FileNotFoundError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Directory not found: {project_path}",
            ) from e

        return {
            "status": "ok",
            "id": entry.id,
            "name": entry.name,
            "path": entry.path,
            "last_opened": entry.last_opened,
            "has_protocol": entry.has_protocol,
        }

    def _get_project_or_404(project_id: str) -> ProjectEntry:
        """Look up a project by id; raise 404 if unknown.  Used by
        every id-keyed route so the not-found response is uniform."""
        project = registry.get(project_id)
        if project is None:
            raise HTTPException(
                status_code=404, detail=f"Project not found: {project_id}",
            )
        return project

    @app.delete("/api/projects/{project_id}")
    async def remove_project(project_id: str) -> dict[str, str]:
        # Idempotent: a 404 here means the caller's view was
        # already stale (project disappeared between list and
        # delete) — treat as success rather than surfacing an
        # error the user has no way to act on.
        project = registry.get(project_id)
        if project is not None:
            proc = processes.remove(project.id)
            if proc is not None:
                proc.process.terminate()
            if active_project["id"] == project.id:
                active_project["id"] = None
                registry.clear_active()
            registry.remove(project.id)
        return {"status": "removed"}

    async def _do_activate(project: ProjectEntry) -> dict[str, Any]:
        """Activate a project: start its server and mark it active."""
        if not Path(project.path).is_dir():
            registry.remove(project.id)
            if active_project["id"] == project.id:
                active_project["id"] = None
                registry.clear_active()
            raise HTTPException(
                status_code=410,
                detail=f"Project directory no longer exists: {project.path}",
            )
        entry = await _ensure_running(project)
        active_project["id"] = project.id
        registry.touch(project.id)
        registry.set_active(project.id)

        # Fetch session info from the project server
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"http://127.0.0.1:{entry.port}/api/session",
                    timeout=5.0,
                )
                session_info = resp.json() if resp.status_code == 200 else {}
            except httpx.HTTPError:
                session_info = {}

        return {
            "id": project.id,
            "name": project.name,
            "path": project.path,
            "port": entry.port,
            "session": session_info,
        }

    @app.post("/api/projects/{project_id}/activate")
    async def activate_project(project_id: str) -> dict[str, Any]:
        return await _do_activate(_get_project_or_404(project_id))

    @app.post("/api/projects/{project_id}/deactivate")
    async def deactivate_project(project_id: str) -> dict[str, str]:
        # Idempotent: a 404 here would just confuse the caller.
        # If the project's already gone we treat the deactivate as
        # already-applied; if it's there we tear down its server
        # and clear the active state.
        project = registry.get(project_id)
        if project is not None:
            proc = processes.remove(project.id)
            if proc is not None:
                proc.process.terminate()
            if active_project["id"] == project.id:
                active_project["id"] = None
                registry.clear_active()
        return {"status": "deactivated"}

    @app.get("/api/projects/active")
    async def get_active_project() -> dict[str, Any]:
        project_id = active_project["id"]
        if project_id is None:
            return {"active": False}
        project = registry.get(project_id)
        entry = processes.get(project_id)
        return {
            "active": True,
            "id": project_id,
            "name": project.name if project else None,
            "path": project.path if project else None,
            "running": entry is not None,
        }

    # ------------------------------------------------------------------
    # REST: Update apply (handled by launcher, not proxied).  The
    # *check* now lives on ``/api/version`` — both release-mode and
    # git-mode payloads come back through that single endpoint;
    # UpdateBadge dispatches on ``latest.kind``.
    # ------------------------------------------------------------------

    @app.post("/api/update/run")
    async def run_update_endpoint() -> dict[str, Any]:
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
        """Kill all project servers, then restart the launcher process."""
        from clarity_agent.setup.updater import schedule_restart
        processes.kill_all()
        schedule_restart()
        return {"restarting": True}

    # ------------------------------------------------------------------
    # REST: Launcher session info
    # ------------------------------------------------------------------

    @app.get("/api/session")
    async def launcher_session() -> dict[str, Any]:
        """Return session info — proxied from active project, or launcher state."""
        entry = await _ensure_active_running()
        if entry is not None:
            async with httpx.AsyncClient() as client:
                try:
                    resp = await client.get(
                        f"http://127.0.0.1:{entry.port}/api/session",
                        timeout=5.0,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        data["launcher_mode"] = True
                        # The project server's "active" means "has a
                        # chat session".  In launcher context, "active"
                        # means "has an active project" — which is true
                        # if we got here.  Preserve the chat-session
                        # flag separately so the UI can distinguish.
                        data["active"] = True
                        # Include project id + path so the frontend
                        # can build project-scoped URLs and so the
                        # ProjectSwitcher's ``isCurrent`` comparison
                        # matches the right entry even when display
                        # names collide.  Resolve via id so duplicates
                        # don't fall back to first-match.
                        project_id = active_project["id"]
                        proj = (
                            registry.get(project_id)
                            if project_id else None
                        )
                        if proj:
                            data["project_id"] = proj.id
                            data["project_dir"] = proj.path
                        # Persist SDK session ID so we can resume after
                        # a launcher restart.
                        new_sid = data.get("llm_session_id")
                        if new_sid and proj and proj.llm_session_id != new_sid:
                            try:
                                registry.update(
                                    proj.id, llm_session_id=new_sid,
                                )
                            except Exception:
                                pass  # don't break the proxy
                        return data
                except httpx.HTTPError:
                    pass

        # No active project or project server unreachable
        return {
            "active": False,
            "thread_id": None,
            "process": None,
            "project_dir": None,
            "backend": None,
            "model": None,
            "active_model": None,
            "active_tier": None,
            "theme": theme,
            "launcher_mode": True,
        }

    # ------------------------------------------------------------------
    # WebSocket proxy
    # ------------------------------------------------------------------

    @app.websocket("/ws/chat")
    async def websocket_proxy(ws: WebSocket) -> None:
        await ws.accept()

        entry = await _ensure_active_running()
        if entry is None:
            await ws.send_json({
                "type": "error",
                "message": "No active project. Select a project first.",
                "category": "no_project",
                "retryable": False,
            })
            await ws.close()
            return

        project_id = active_project["id"]
        assert project_id is not None  # guaranteed by _ensure_active_running success

        processes.touch(project_id)

        # Connect to the project server's WebSocket.
        # websockets 13+ uses websockets.asyncio.client.
        from websockets.asyncio.client import connect as ws_connect
        from websockets.exceptions import ConnectionClosed
        ws_url = f"ws://127.0.0.1:{entry.port}/ws/chat"

        try:
            async with ws_connect(ws_url) as upstream:

                async def browser_to_server() -> None:
                    try:
                        while True:
                            data = await ws.receive_text()
                            await upstream.send(data)
                    except WebSocketDisconnect:
                        await upstream.close()

                async def server_to_browser() -> None:
                    try:
                        async for message in upstream:
                            if isinstance(message, str):
                                await ws.send_text(message)
                            else:
                                await ws.send_bytes(message)
                    except ConnectionClosed:
                        pass

                await asyncio.gather(
                    browser_to_server(),
                    server_to_browser(),
                    return_exceptions=True,
                )
        except Exception as e:
            try:
                await ws.send_json({
                    "type": "error",
                    "message": f"Failed to connect to project server: {e}",
                    "category": "network",
                    "retryable": True,
                })
            except Exception:
                pass
        finally:
            try:
                await ws.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # HTTP reverse proxy (catch-all for /api/* routes)
    # ------------------------------------------------------------------

    async def _proxy_request(request: Request) -> Response:
        """Forward an HTTP request to the active project's server."""
        entry = await _ensure_active_running()
        if entry is None:
            raise HTTPException(
                status_code=503,
                detail="No active project. Select a project first.",
            )

        # Build upstream URL
        path = request.url.path
        query = str(request.url.query)
        upstream_url = f"http://127.0.0.1:{entry.port}{path}"
        if query:
            upstream_url += f"?{query}"

        # Forward the request
        body = await request.body()
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.request(
                    method=request.method,
                    url=upstream_url,
                    headers={
                        k: v for k, v in request.headers.items()
                        if k.lower() not in ("host", "connection")
                    },
                    content=body if body else None,
                    timeout=60.0,
                )
            except httpx.ConnectError as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"Cannot reach project server for {entry.project_name!r}.",
                ) from exc

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
        )

    # Register the catch-all proxy for all API routes not handled above.
    # These are the per-project endpoints (protocol, transcripts, packets, etc.)
    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    )
    async def proxy_api(request: Request) -> Response:
        return await _proxy_request(request)

    # ------------------------------------------------------------------
    # Static file serving (SPA) — served once by the launcher
    # ------------------------------------------------------------------

    if static_dir is not None and static_dir.exists():
        from fastapi.responses import FileResponse

        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="assets",
            )

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> FileResponse:
            file_path = static_dir / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(static_dir / "index.html"))

    return app
