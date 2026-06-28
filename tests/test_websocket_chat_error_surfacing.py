"""Tests for the ``/ws/chat`` error-surfacing paths.

Regression coverage for issue #47: when backend construction or a
chat turn fails with an actionable error (missing ``gh`` CLI, bad
API key, network blip), the WebSocket must send a classified
``error_event`` to the frontend before closing.  Previously these
errors propagated silently — uvicorn logged them to stderr and the
socket closed with no message, so the FE just reconnected in a loop
and the user saw "thinking" dots indefinitely.

We assert two paths:

1. ``session.start()`` failure (eager backend construction) →
   error_event + socket stays open to drain follow-up messages.
2. ``session.chat()`` failure (per-turn) → error_event sent + the
   outer loop continues so the user can retry without reconnecting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clarity_agent.llm import LLMConfig
from clarity_agent.web import app as app_module


def _make_app(project_dir: Path, *, provider: str = "anthropic") -> Any:
    """Build a FastAPI app pointed at *project_dir*.

    Uses a real :class:`LLMConfig` so the no-provider short-circuit
    in ``websocket_chat`` doesn't fire and we exercise the
    ``session.start()`` path under test.
    """
    # ``WebSessionAdapter.__init__`` reads ``tiers["default"]`` before
    # start() runs, so it has to be populated even though the test
    # never exercises a real provider.
    cfg = LLMConfig(
        provider=provider,
        api_key="fake-key",
        tiers={"default": "fake-model"},
    )
    return app_module.create_app(
        project_dir=project_dir,
        clarity_agent_dir=project_dir / "agent",
        llm_config=cfg,
    )


def _receive_event(ws: Any, event_type: str) -> dict[str, Any]:
    """Receive until the requested event type arrives, skipping log frames."""
    skipped: list[dict[str, Any]] = []
    for _ in range(20):
        msg = ws.receive_json()
        if msg["type"] == event_type:
            return msg
        skipped.append(msg)
    raise AssertionError(f"Did not receive {event_type!r}; skipped={skipped!r}")


class TestSessionStartFailure:
    """Backend construction failure surfaces as a classified error."""

    def test_gh_cli_missing_surfaces_auth_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Simulate ``get_gh_cli_token(raise_on_failure=True)`` failing
        # during backend construction — the real-world cause of #47.
        # The message contains "gh auth login" so ``_classify_ws_error``
        # routes it to the ``auth`` category.
        async def _broken_start(self: Any) -> None:
            raise RuntimeError(
                "The GitHub CLI (gh) is not installed.\n"
                "Install it from https://cli.github.com/ and run "
                "'gh auth login'.",
            )

        monkeypatch.setattr(
            "clarity_agent.web.app.WebSessionAdapter.start",
            _broken_start,
        )

        app = _make_app(tmp_path)
        client = TestClient(app)
        with client.websocket_connect("/ws/chat") as ws:
            msg = _receive_event(ws, "error")

        assert msg["type"] == "error"
        assert msg["category"] == "auth"
        assert "gh" in msg["message"]
        # Auth failures aren't retryable from the FE's perspective —
        # the user has to fix the underlying setup and reload.
        assert msg["retryable"] is False

    def test_socket_stays_open_to_re_emit_error_on_followup_message(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The FE may try sending a queued chat message before it
        # processes the initial error banner.  Each such send must
        # come back with the same classified error rather than a
        # silent close — otherwise the FE has nothing to display and
        # falls back to its reconnect/hang loop.
        async def _broken_start(self: Any) -> None:
            raise RuntimeError("Bad API key (401 unauthorized)")

        monkeypatch.setattr(
            "clarity_agent.web.app.WebSessionAdapter.start",
            _broken_start,
        )

        app = _make_app(tmp_path)
        client = TestClient(app)
        with client.websocket_connect("/ws/chat") as ws:
            initial = _receive_event(ws, "error")
            assert initial["type"] == "error"
            assert initial["category"] == "auth"

            ws.send_json({"type": "chat", "message": "hello"})
            echoed = _receive_event(ws, "error")

        assert echoed["type"] == "error"
        assert echoed["category"] == "auth"
        assert echoed["message"] == initial["message"]

    def test_non_runtime_failure_also_surfaces(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # OSError covers things like a missing claude CLI on the SDK
        # auth path (FileNotFoundError from subprocess).  ValueError
        # covers malformed configs.  Both must produce an error_event
        # the same way ``RuntimeError`` does — the except clause
        # explicitly catches all three.
        async def _broken_start(self: Any) -> None:
            raise FileNotFoundError("claude: command not found")

        monkeypatch.setattr(
            "clarity_agent.web.app.WebSessionAdapter.start",
            _broken_start,
        )

        app = _make_app(tmp_path)
        client = TestClient(app)
        with client.websocket_connect("/ws/chat") as ws:
            msg = _receive_event(ws, "error")

        assert msg["type"] == "error"
        assert msg["category"] == "setup_required"
        assert msg["retryable"] is False
        assert "dependency" in msg["hint"]


class TestChatTurnFailure:
    """Per-turn RuntimeError surfaces as error_event, loop continues."""

    def test_chat_runtime_error_does_not_silently_close_socket(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ``session.start`` succeeds, but the first chat turn raises
        # RuntimeError (e.g. the SDK process crashed mid-turn).  The
        # pre-fix behavior was to silently ``return`` from the
        # handler, closing the socket; the fix routes RuntimeError
        # through the generic Exception arm which sends an
        # error_event and continues the outer loop.
        async def _ok_start(self: Any) -> None:
            return None

        async def _broken_chat(
            self: Any, message: str, system_prompt: str | None = None,
        ) -> str:
            raise RuntimeError("Authentication failed: 401 Unauthorized")

        monkeypatch.setattr(
            "clarity_agent.web.app.WebSessionAdapter.start", _ok_start,
        )
        monkeypatch.setattr(
            "clarity_agent.web.app.WebSessionAdapter.chat", _broken_chat,
        )

        app = _make_app(tmp_path)
        client = TestClient(app)
        with client.websocket_connect("/ws/chat") as ws:
            ws.send_json({"type": "chat", "message": "hi"})
            msg = _receive_event(ws, "error")

        assert msg["type"] == "error"
        assert msg["category"] == "auth"
        assert "Authentication" in msg["message"]

    def test_mcp_tool_schema_error_is_non_retryable_with_remediation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # A malfunctioning MCP server makes the API reject the whole
        # request.  This is not retryable — the bad tool ships on every
        # request until the user removes the server — and the hint must
        # point at the ``claude mcp`` commands rather than the API key.
        async def _ok_start(self: Any) -> None:
            return None

        async def _broken_chat(
            self: Any, message: str, system_prompt: str | None = None,
        ) -> str:
            raise RuntimeError(
                "API Error: 400 tools.195.custom_input_schema: "
                "input_schema does not support oneOf, allOf, or anyOf "
                "at top level",
            )

        monkeypatch.setattr(
            "clarity_agent.web.app.WebSessionAdapter.start", _ok_start,
        )
        monkeypatch.setattr(
            "clarity_agent.web.app.WebSessionAdapter.chat", _broken_chat,
        )

        app = _make_app(tmp_path)
        client = TestClient(app)
        with client.websocket_connect("/ws/chat") as ws:
            ws.send_json({"type": "chat", "message": "hi"})
            msg = _receive_event(ws, "error")

        assert msg["type"] == "error"
        assert msg["category"] == "mcp_config"
        assert msg["retryable"] is False
        assert "claude mcp list" in msg["hint"]
        assert "claude mcp remove" in msg["hint"]
