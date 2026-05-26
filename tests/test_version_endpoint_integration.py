"""End-to-end integration test for ``GET /api/version``.

Goes through the real FastAPI route handler — including the
``asyncio.to_thread(current_state, clarity_agent_dir)`` call
inside it and the ``.to_dict()`` serialization — so signature
mismatches between the route and the library are caught.  This
is the test that would have caught the earlier
``get_version_payload(None, clarity_agent_dir)`` bug where the
route passed two positional args but the function only accepted
one before its keyword-only barrier.

The unit-level coverage of payload shape + caching lives in
:mod:`tests.test_version`; this file is intentionally narrow —
just enough to lock down the wire contract between
``create_launcher`` / ``create_app`` and the library.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clarity_agent.setup.snippet import snippet_path
from clarity_agent.setup.version import reset_cache
from clarity_agent.web.launcher import create_launcher


@pytest.fixture(autouse=True)
def _isolate_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redirect ``CLARITY_DATA_DIR`` so the launcher's registry
    writes to a tmp dir, and drop the version cache between tests
    so each call goes through ``current_state`` again."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("CLARITY_DATA_DIR", str(data))
    reset_cache()


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    """Minimal clarity-agent bundle — same shape the launcher tests
    use.  The version endpoint doesn't actually read from this in
    a non-release build with no ``PRETEND_TO_BE_VERSION``, but
    ``create_launcher`` requires a valid path."""
    b = tmp_path / "bundle"
    setup_dir = b / "src" / "clarity_agent" / "setup"
    setup_dir.mkdir(parents=True)
    shutil.copy2(snippet_path(), setup_dir / "snippet.md")
    (b / "processes").mkdir()
    return b


@pytest.fixture
def client(bundle: Path) -> TestClient:
    app = create_launcher(clarity_agent_dir=bundle)
    return TestClient(app)


class TestVersionRoute:
    """Whatever the env, ``GET /api/version`` returns a 200 with
    the documented envelope shape.  The point is the *contract*
    between the route handler and the library — not the field
    values, which depend on environment specifics the unit tests
    already cover exhaustively."""

    def test_returns_200_with_envelope_shape(
        self, client: TestClient,
    ) -> None:
        # Earlier code in this PR called
        # ``to_thread(get_version_payload, None, clarity_agent_dir)``
        # which raised ``TypeError`` at request time because
        # ``get_version_payload`` only accepts one positional arg.
        # This test would have caught that — any route/library
        # signature drift now fails fast.
        response = client.get("/api/version")
        assert response.status_code == 200, response.text

        body = response.json()
        # Envelope keys that must always be present, regardless of
        # release vs. local mode.  Per-mode specifics (``branch``,
        # ``latest.kind``, etc.) are tested in test_version_endpoint.
        for key in (
            "version", "source", "is_release",
            "branch", "local_sha",
            "update_status", "latest", "reason",
        ):
            assert key in body, f"missing key {key!r} in {body!r}"
        assert body["source"] in {"release", "local"}
        assert body["update_status"] in {"available", "up_to_date", "unknown"}
