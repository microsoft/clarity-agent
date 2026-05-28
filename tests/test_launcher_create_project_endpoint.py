"""Tests for the launcher's ``POST /api/projects`` endpoint matrix.

The endpoint handles flows 1, 2, and 3 of the project-open story
(see ``setup/layout.py``'s module docstring).  This file pins down
the per-cell behavior: which combinations of ``intent`` + ``mode``
+ disk state produce ok / needs_setup / broken_install /
embedded_install_required responses.

Each test sets ``CLARITY_DATA_DIR`` to a tmp dir so the
``ProjectRegistry`` writes there — keeps the developer's real
projects.json untouched.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clarity_agent.setup.layout import (
    EMBEDDED_AGENT_SUBDIR,
    PROTOCOL_DIR_DOT,
    PROTOCOL_DIR_VISIBLE,
)
from clarity_agent.setup.snippet import snippet_path
from clarity_agent.web.launcher import create_launcher

# ---------------------------------------------------------------------------
# Fixtures: tmp data dir + a stand-in clarity-agent bundle
# ---------------------------------------------------------------------------


@pytest.fixture
def _isolated_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Redirect ``CLARITY_DATA_DIR`` so the registry writes to a tmp
    dir — keeps the dev's real ``projects.json`` untouched."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("CLARITY_DATA_DIR", str(data))
    return data


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    """A minimal clarity-agent bundle: ``processes/`` + a copy of
    the snippet template at its expected location.  Enough for
    ``setup_userspace_project`` and ``ensure_for_project`` to run."""
    b = tmp_path / "bundle"
    setup_dir = b / "src" / "clarity_agent" / "setup"
    setup_dir.mkdir(parents=True)
    shutil.copy2(snippet_path(), setup_dir / "snippet.md")
    (b / "processes").mkdir()
    return b


@pytest.fixture
def client(_isolated_data_dir: Path, bundle: Path) -> TestClient:
    app = create_launcher(clarity_agent_dir=bundle)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Flow 1: intent = "create_new"
# ---------------------------------------------------------------------------


class TestCreateNew:
    def test_creates_userspace_project_with_setup(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        # intent=create_new always means USERSPACE (no prompt) per
        # the user's design rule for flow 1.  The endpoint should
        # mkdir the path, lay down Clarity Protocol/ + template
        # files + AGENTS.md, and register.
        project = tmp_path / "fresh"
        # Not pre-created — setup must mkdir it.

        r = client.post("/api/projects", json={
            "name": "fresh",
            "path": str(project),
            "intent": "create_new",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "ok"
        assert body["name"] == "fresh"
        # Disk: project dir exists, has Clarity Protocol/ and AGENTS.md.
        assert project.is_dir()
        assert (project / PROTOCOL_DIR_VISIBLE).is_dir()
        assert (project / "AGENTS.md").exists()


# ---------------------------------------------------------------------------
# Flow 2: intent = "open_existing", clean layout detected
# ---------------------------------------------------------------------------


class TestOpenExistingClean:
    def test_returns_ok_for_clean_userspace_layout(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        # Already-set-up USERSPACE project: open just registers,
        # no setup work needed.
        project = tmp_path / "ws"
        project.mkdir()
        (project / PROTOCOL_DIR_VISIBLE).mkdir()

        r = client.post("/api/projects", json={
            "name": "ws", "path": str(project),
            "intent": "open_existing",
        })
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "ok"

    def test_returns_ok_for_clean_embedded_layout(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        # An EMBEDDED-installed git repo (full install completed) —
        # both markers present → clean EMBEDDED.  Open just
        # registers without touching disk.
        project = tmp_path / "repo"
        project.mkdir()
        (project / EMBEDDED_AGENT_SUBDIR).mkdir()
        (project / PROTOCOL_DIR_DOT).mkdir()

        r = client.post("/api/projects", json={
            "name": "repo", "path": str(project),
            "intent": "open_existing",
        })
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Flow 3: intent = "open_existing", no mode, no layout / broken layout
# ---------------------------------------------------------------------------


class TestOpenExistingNeedsSetup:
    def test_code_directory_suggests_embedded(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        # Looks like a code repo (has .git/) but no Clarity setup.
        # 409 with looks_like_code=True and suggested_mode="embedded"
        # drives the SetupPromptDialog to recommend embedded.
        project = tmp_path / "coderepo"
        project.mkdir()
        (project / ".git").mkdir()

        r = client.post("/api/projects", json={
            "name": "coderepo", "path": str(project),
            "intent": "open_existing",
        })
        assert r.status_code == 409
        body = r.json()
        assert body["status"] == "needs_setup"
        assert body["looks_like_code"] is True
        assert body["suggested_mode"] == "embedded"
        assert body["path"] == str(project.resolve())

    def test_plain_workspace_suggests_userspace_only(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        # Non-code directory → looks_like_code=False, suggested
        # "userspace".  UI hides the embedded option entirely in
        # this case.
        project = tmp_path / "workspace"
        project.mkdir()
        (project / "notes.md").write_text("# notes\n")

        r = client.post("/api/projects", json={
            "name": "workspace", "path": str(project),
            "intent": "open_existing",
        })
        assert r.status_code == 409
        body = r.json()
        assert body["status"] == "needs_setup"
        assert body["looks_like_code"] is False
        assert body["suggested_mode"] == "userspace"


class TestOpenExistingBrokenLayout:
    def test_partial_embedded_install_returns_broken_status(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        # ``.clarity-protocol/`` present but no ``.clarity-agent/``
        # — the strict state table flags this as broken so the UI
        # can prompt for a repair rather than guess.
        project = tmp_path / "halfinstalled"
        project.mkdir()
        (project / PROTOCOL_DIR_DOT).mkdir()

        r = client.post("/api/projects", json={
            "name": "halfinstalled", "path": str(project),
            "intent": "open_existing",
        })
        assert r.status_code == 409
        body = r.json()
        assert body["status"] == "broken_install"
        assert body["brokenness"] == "partial_embedded_install"

    def test_ambiguous_protocol_dirs_returns_broken_status(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        project = tmp_path / "twoways"
        project.mkdir()
        (project / PROTOCOL_DIR_DOT).mkdir()
        (project / PROTOCOL_DIR_VISIBLE).mkdir()

        r = client.post("/api/projects", json={
            "name": "twoways", "path": str(project),
            "intent": "open_existing",
        })
        assert r.status_code == 409
        body = r.json()
        assert body["status"] == "broken_install"
        assert body["brokenness"] == "ambiguous_protocol_dirs"


# ---------------------------------------------------------------------------
# Flow 3: intent = "open_existing" + explicit mode
# ---------------------------------------------------------------------------


class TestOpenExistingWithExplicitMode:
    def test_mode_userspace_runs_setup_and_registers(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        # User saw the SetupPromptDialog and clicked "Set up as
        # userspace project."  Re-call with mode=userspace runs
        # the setup and registers.
        project = tmp_path / "promote"
        project.mkdir()  # no markers — needs setup

        r = client.post("/api/projects", json={
            "name": "promote", "path": str(project),
            "intent": "open_existing", "mode": "userspace",
        })
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "ok"
        # USERSPACE setup ran on disk.
        assert (project / PROTOCOL_DIR_VISIBLE).is_dir()
        assert (project / "AGENTS.md").exists()

    def test_mode_embedded_returns_install_command_without_registering(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        # Option (ii): the desktop app doesn't run the heavy
        # embedded install itself.  The user picks "embedded" in
        # the prompt, the endpoint returns the CLI command for
        # them to run, and *does not* register the path — the
        # install hasn't happened yet.
        project = tmp_path / "wantembedded"
        project.mkdir()
        (project / ".git").mkdir()

        r = client.post("/api/projects", json={
            "name": "wantembedded", "path": str(project),
            "intent": "open_existing", "mode": "embedded",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "embedded_install_required"
        assert "clarity install --embedded" in body["command"]
        assert str(project) in body["command"]
        # Verify nothing was registered.
        listing = client.get("/api/projects").json()
        names = [p["name"] for p in listing["projects"]]
        assert "wantembedded" not in names


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_rejects_missing_name(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        project = tmp_path / "x"
        project.mkdir()
        (project / PROTOCOL_DIR_VISIBLE).mkdir()
        r = client.post("/api/projects", json={
            "path": str(project), "intent": "open_existing",
        })
        assert r.status_code == 400
        assert "name" in r.json()["detail"].lower()

    def test_rejects_unknown_intent(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        r = client.post("/api/projects", json={
            "name": "x", "path": str(tmp_path), "intent": "bogus",
        })
        assert r.status_code == 400

    def test_rejects_unknown_mode(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        r = client.post("/api/projects", json={
            "name": "x", "path": str(tmp_path),
            "intent": "open_existing", "mode": "weird",
        })
        assert r.status_code == 400

    def test_rejects_open_of_nonexistent_path(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        r = client.post("/api/projects", json={
            "name": "x", "path": str(tmp_path / "nope"),
            "intent": "open_existing",
        })
        assert r.status_code == 400
        assert "not found" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Registry is path-keyed: same path → idempotent ok, same name OK at
# different paths.
# ---------------------------------------------------------------------------


class TestAlreadyRegistered:
    """Regression for the silent-409 bug.  Path is the registry's
    primary key; the display ``name`` is not a uniqueness constraint
    (two projects in different directories are genuinely different
    projects, even if a user wants to call them the same thing)."""

    def test_same_path_is_idempotent_ok(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        project = tmp_path / "raas2"
        project.mkdir()
        (project / PROTOCOL_DIR_VISIBLE).mkdir()

        # First open registers it.
        first = client.post("/api/projects", json={
            "name": "raas2", "path": str(project),
            "intent": "open_existing",
        })
        assert first.status_code == 200
        first_id = first.json()["id"]

        # Second open (same path) — used to silently 409.  Now an
        # idempotent ok returning the same registry entry.
        second = client.post("/api/projects", json={
            "name": "raas2", "path": str(project),
            "intent": "open_existing",
        })
        assert second.status_code == 200, second.text
        assert second.json()["status"] == "ok"
        assert second.json()["id"] == first_id

    def test_same_name_different_path_both_register(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        # Two clean projects at different paths, same display name —
        # both should register successfully.  The launcher
        # disambiguates by ``id`` for activation.
        first_path = tmp_path / "alpha"
        first_path.mkdir()
        (first_path / PROTOCOL_DIR_VISIBLE).mkdir()
        second_path = tmp_path / "beta"
        second_path.mkdir()
        (second_path / PROTOCOL_DIR_VISIBLE).mkdir()

        first = client.post("/api/projects", json={
            "name": "ws", "path": str(first_path),
            "intent": "open_existing",
        })
        assert first.status_code == 200
        first_id = first.json()["id"]

        second = client.post("/api/projects", json={
            "name": "ws", "path": str(second_path),
            "intent": "open_existing",
        })
        assert second.status_code == 200, second.text
        assert second.json()["status"] == "ok"
        # Different paths produce different ids — they're genuinely
        # different entries despite the shared display name.
        assert second.json()["id"] != first_id
        assert second.json()["path"] == str(second_path)

    def test_same_path_different_name_renames(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        # Re-opening the same path with a new name should update
        # the display label rather than refusing — same project,
        # the user is just relabeling it.
        project = tmp_path / "proj"
        project.mkdir()
        (project / PROTOCOL_DIR_VISIBLE).mkdir()

        first = client.post("/api/projects", json={
            "name": "old-name", "path": str(project),
            "intent": "open_existing",
        })
        assert first.status_code == 200

        second = client.post("/api/projects", json={
            "name": "new-name", "path": str(project),
            "intent": "open_existing",
        })
        assert second.status_code == 200, second.text
        assert second.json()["name"] == "new-name"
        # Same path means same id — it's the same project entry.
        assert second.json()["id"] == first.json()["id"]
