"""Tests for :mod:`clarity_agent.setup.version`.

Four layers, all exercised here:

* :class:`VersionInfo` + :func:`current_version` — the baked-version
  reader (env-var override + ``_version.py`` fallback).
* :func:`current_state` dispatch — the release-vs-local fork.
* Local-mode update-status translation — how
  :class:`UpdateStatus` becomes the wire-shape ``update_*`` fields.
* Release-mode caching + :meth:`RuntimeState.to_dict` serialization
  — the responsibilities previously held by ``version_endpoint``.

No network or real git subprocess access — the dependencies that
would touch them are monkeypatched.  The route-handler integration
test (:mod:`tests.test_version_endpoint_integration`) is the only
piece that goes through FastAPI; it lives separately to keep this
file fast.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clarity_agent.setup.release_feed import ReleaseInfo
from clarity_agent.setup.updater import GitUpdate, UpdateStatus
from clarity_agent.setup.version import (
    CACHE_TTL_SECONDS,
    PRETEND_ENV_VAR,
    GitState,
    RuntimeState,
    VersionInfo,
    current_state,
    current_version,
    reset_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache_each_test() -> None:
    # Release-mode cache leaks between cases otherwise — every test
    # gets a fresh module-level cache.
    reset_cache()

# ---------------------------------------------------------------------------
# VersionInfo + current_version (was test_stamped_version.py)
# ---------------------------------------------------------------------------


class TestCurrentVersion:
    def test_defaults_to_baked_module(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # No env override → reads the baked ``_version.py``.  The
        # committed copy of that file has the local defaults, so
        # in any test environment (no release stamping) we expect
        # ``("local", "local")``.
        monkeypatch.delenv(PRETEND_ENV_VAR, raising=False)

        info = current_version()
        assert info.version == "local"
        assert info.source == "local"
        assert info.is_release is False

    def test_pretend_env_var_forces_release(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The whole point of ``PRETEND_TO_BE_VERSION``: a local
        # binary advertises itself as a release at the given
        # version, so the update path activates against the real
        # GitHub feed.  ``source`` must be ``"release"`` regardless
        # of what the baked module says.
        monkeypatch.setenv(PRETEND_ENV_VAR, "v0.0.1")

        info = current_version()
        assert info.version == "v0.0.1"
        assert info.source == "release"
        assert info.is_release is True

    def test_pretend_env_var_passes_string_through_verbatim(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # No normalisation, no validation — whatever the env var
        # holds is what we report.  Manual testing wants the
        # freedom to use weird strings (``v9999.0.0-rc1``) without
        # the runtime second-guessing them.
        monkeypatch.setenv(PRETEND_ENV_VAR, "v9999.0.0-rc1+test")

        info = current_version()
        assert info.version == "v9999.0.0-rc1+test"
        assert info.source == "release"

    def test_empty_env_var_is_ignored(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Setting the env var to "" shouldn't count as a pretend —
        # that's almost certainly a shell mistake.  Fall through
        # to the baked default.
        monkeypatch.setenv(PRETEND_ENV_VAR, "")

        info = current_version()
        assert info.version == "local"
        assert info.source == "local"


class TestVersionInfo:
    def test_is_release_property(self) -> None:
        # Convenience property the update orchestrator branches on.
        assert VersionInfo(version="v1.0.0", source="release").is_release is True
        assert VersionInfo(version="local", source="local").is_release is False

    def test_frozen_dataclass(self) -> None:
        # The version record gets passed around and reported via
        # the REST endpoint — keep it immutable so callers can't
        # mutate the cached value mid-flight.
        from dataclasses import FrozenInstanceError
        info = VersionInfo(version="v1.0.0", source="release")
        with pytest.raises(FrozenInstanceError):
            info.version = "v2.0.0"  # type: ignore[misc]

# ---------------------------------------------------------------------------
# Release mode
# ---------------------------------------------------------------------------


class TestReleaseMode:
    """When ``current_version().source == "release"``, ``current_state``
    goes through the GitHub release feed and ignores ``agent_dir``."""

    def test_release_with_update_available(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(PRETEND_ENV_VAR, "v1.2.3")
        # Stub the feed module so the orchestrator returns a known
        # ReleaseInfo without hitting the network.
        from clarity_agent.setup import release_feed
        from clarity_agent.setup import version as version_mod
        latest = ReleaseInfo(
            version="v1.2.4", assets={"darwin-aarch64": "https://x/y.dmg"},
            release_url="https://github.com/example/releases/tag/v1.2.4",
        )
        avail = release_feed.UpdateAvailability(
            status="available",
            current=version_mod.current_version(),
            latest=latest,
        )
        monkeypatch.setattr(version_mod, "check_for_update", lambda current: avail)

        result = current_state()

        assert result.version.version == "v1.2.3"
        assert result.version.source == "release"
        assert result.git is None
        assert result.update_status == "available"
        assert result.update_latest == latest
        assert result.update_reason is None

    def test_release_ignores_agent_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        # Release mode must not touch git regardless of what
        # ``agent_dir`` points at — a malformed/missing checkout
        # path shouldn't cascade into the release flow.
        monkeypatch.setenv(PRETEND_ENV_VAR, "v1.2.3")
        from clarity_agent.setup import release_feed
        from clarity_agent.setup import version as version_mod
        avail = release_feed.UpdateAvailability(
            status="up_to_date", current=version_mod.current_version(),
        )
        monkeypatch.setattr(version_mod, "check_for_update", lambda current: avail)

        # ``agent_dir`` points at a non-existent directory; should
        # not raise, should not affect the result.
        result = current_state(agent_dir=tmp_path / "does-not-exist")
        assert result.git is None
        assert result.update_status == "up_to_date"


# ---------------------------------------------------------------------------
# Local mode — happy paths
# ---------------------------------------------------------------------------


def _patch_git(
    monkeypatch: pytest.MonkeyPatch,
    *,
    branch: str | None = "main",
    head: str = "abcdef0123456789",
    check_status: UpdateStatus | None = None,
    check_raises: Exception | None = None,
) -> None:
    """Replace every git-touching dependency the state module
    pulls in.  ``check_status`` is what ``check_for_updates``
    returns; ``check_raises`` overrides that with an exception."""
    from clarity_agent.setup import version as version_mod

    monkeypatch.setattr(version_mod, "_git_current_branch", lambda _p: branch)
    monkeypatch.setattr(version_mod, "_git_head", lambda _p: head)

    def _check(_p: Path) -> UpdateStatus:
        if check_raises is not None:
            raise check_raises
        assert check_status is not None
        return check_status

    monkeypatch.setattr(version_mod, "check_for_updates", _check)


class TestLocalModeAvailable:
    def test_commits_behind_yields_git_update(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        # The "5 commits behind main" case — the canonical badge
        # trigger.  ``update_latest`` carries the GitUpdate the
        # sidebar renders.
        monkeypatch.delenv(PRETEND_ENV_VAR, raising=False)
        _patch_git(
            monkeypatch, branch="main", head="aaaaaaaaaaaa1111",
            check_status=UpdateStatus(
                available=True, local_sha="aaaaaaaaaaaa1111",
                remote_sha="bbbbbbbbbbbb2222", commit_count=5,
            ),
        )

        result = current_state(agent_dir=tmp_path)

        assert result.version.source == "local"
        assert result.git == GitState(
            branch="main", local_sha="aaaaaaaaaaaa",  # 12-char truncation
        )
        assert result.update_status == "available"
        assert result.update_latest == GitUpdate(
            branch="main", commit_count=5, remote_sha="bbbbbbbbbbbb",
        )
        assert result.update_reason is None


class TestLocalModeQuiet:
    def test_up_to_date_when_remote_matches(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        # Equal local + remote SHA → genuinely up to date.  Badge
        # stays silent; tooltip says "up to date".
        monkeypatch.delenv(PRETEND_ENV_VAR, raising=False)
        _patch_git(
            monkeypatch, head="aaaaaaaaaaaa1111",
            check_status=UpdateStatus(
                available=False, local_sha="aaaaaaaaaaaa1111",
                remote_sha="aaaaaaaaaaaa1111", commit_count=0,
            ),
        )

        result = current_state(agent_dir=tmp_path)
        assert result.update_status == "up_to_date"
        assert result.update_latest is None
        assert result.update_reason is None
        # GitState is still populated even when there's no update —
        # the version label uses it.
        assert result.git is not None
        assert result.git.branch == "main"

    def test_no_upstream_is_unknown(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        # Local branch with no remote counterpart → remote_sha is
        # None → "unknown" with the diagnostic reason.  Badge stays
        # silent; tooltip can explain.
        monkeypatch.delenv(PRETEND_ENV_VAR, raising=False)
        _patch_git(
            monkeypatch, branch="local-only-branch",
            check_status=UpdateStatus(
                available=False, local_sha="ccccccccccc1",
                remote_sha=None, commit_count=0,
            ),
        )

        result = current_state(agent_dir=tmp_path)
        assert result.update_status == "unknown"
        assert result.update_latest is None
        assert "upstream" in (result.update_reason or "")
        # GitState still reports the local branch — useful for
        # "you're on branch X, no upstream configured" tooltips.
        assert result.git is not None
        assert result.git.branch == "local-only-branch"


# ---------------------------------------------------------------------------
# Local mode — degraded environments
# ---------------------------------------------------------------------------


class TestLocalModeDegraded:
    """``current_state`` must never raise, regardless of how broken
    the environment is.  These tests pin that contract."""

    def test_no_agent_dir_returns_unknown(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Route handler forgot to thread ``agent_dir`` through.
        # Surfaces loudly so the bug is easy to spot in logs.
        monkeypatch.delenv(PRETEND_ENV_VAR, raising=False)

        result = current_state(agent_dir=None)
        assert result.version.source == "local"
        assert result.git is None
        assert result.update_status == "unknown"
        assert "agent_dir" in (result.update_reason or "")

    def test_check_for_updates_exception_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        # git binary missing / .git/ missing / network failure all
        # cascade into Exception from the subprocess layer.  Must
        # be caught and reported, never raised.
        monkeypatch.delenv(PRETEND_ENV_VAR, raising=False)
        _patch_git(
            monkeypatch, head="aaaaaaaaaaaa1111",
            check_raises=RuntimeError("simulated git crash"),
        )

        result = current_state(agent_dir=tmp_path)
        assert result.update_status == "unknown"
        assert "simulated git crash" in (result.update_reason or "")
        # GitState was looked up before the failing call, so it's
        # still present.
        assert result.git is not None

    def test_branch_lookup_failure_collapses_to_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        # ``_git_current_branch`` raising shouldn't propagate —
        # GitState gets ``branch=""`` and the rest still works.
        monkeypatch.delenv(PRETEND_ENV_VAR, raising=False)
        from clarity_agent.setup import version as version_mod

        def _raise_branch(_p: Path) -> str | None:
            raise OSError("git: command not found")

        monkeypatch.setattr(version_mod, "_git_current_branch", _raise_branch)
        monkeypatch.setattr(version_mod, "_git_head", lambda _p: "aaaaaaaaaaaa")
        monkeypatch.setattr(version_mod, "check_for_updates", lambda _p: UpdateStatus(
            available=False, local_sha="aaaaaaaaaaaa",
            remote_sha=None, commit_count=0,
        ))

        result = current_state(agent_dir=tmp_path)
        assert result.git == GitState(branch="", local_sha="aaaaaaaaaaaa")
        assert result.update_status == "unknown"


# ---------------------------------------------------------------------------
# RuntimeState.to_dict — wire shape for /api/version
# ---------------------------------------------------------------------------


class TestRuntimeStateToDict:
    """The discriminated-union shape the frontend reads.  ``to_dict``
    is the single source of truth for that wire contract — frontends
    dispatch on ``latest.kind`` rather than re-deriving the mode."""

    def test_release_with_update_carries_kind_release(self) -> None:
        # Release-mode latest: ReleaseInfo → ``{"kind": "release", ...}``.
        latest = ReleaseInfo(
            version="v1.2.4", assets={"darwin-aarch64": "https://x/y.dmg"},
            release_url="https://example/releases/v1.2.4",
        )
        state = RuntimeState(
            version=VersionInfo(version="v1.2.3", source="release"),
            git=None,
            update_status="available", update_latest=latest,
            update_reason=None,
        )

        assert state.to_dict() == {
            "version": "v1.2.3",
            "source": "release",
            "is_release": True,
            "branch": None,
            "local_sha": None,
            "update_status": "available",
            "latest": {
                "kind": "release",
                "version": "v1.2.4",
                "assets": {"darwin-aarch64": "https://x/y.dmg"},
                "release_url": "https://example/releases/v1.2.4",
            },
            "reason": None,
        }

    def test_local_with_update_carries_kind_git(self) -> None:
        # Local-mode latest: GitUpdate → ``{"kind": "git", ...}``.
        # ``branch`` and ``local_sha`` get hoisted to top level
        # from ``git`` so the sidebar label reads them flat.
        state = RuntimeState(
            version=VersionInfo(version="local", source="local"),
            git=GitState(branch="issue48-1", local_sha="aaaaaaaaaaaa"),
            update_status="available",
            update_latest=GitUpdate(
                branch="issue48-1", commit_count=3,
                remote_sha="bbbbbbbbbbbb",
            ),
            update_reason=None,
        )

        assert state.to_dict() == {
            "version": "local",
            "source": "local",
            "is_release": False,
            "branch": "issue48-1",
            "local_sha": "aaaaaaaaaaaa",
            "update_status": "available",
            "latest": {
                "kind": "git",
                "branch": "issue48-1",
                "commit_count": 3,
                "remote_sha": "bbbbbbbbbbbb",
            },
            "reason": None,
        }

    def test_unknown_status_with_reason_serializes(self) -> None:
        # Diagnostic reason rides on the same envelope — tooltip
        # on the version label reads it.
        state = RuntimeState(
            version=VersionInfo(version="local", source="local"),
            git=GitState(branch="floating", local_sha=""),
            update_status="unknown", update_latest=None,
            update_reason="no upstream branch (or git fetch failed)",
        )

        payload = state.to_dict()
        assert payload["update_status"] == "unknown"
        assert payload["latest"] is None
        assert payload["reason"] == "no upstream branch (or git fetch failed)"


# ---------------------------------------------------------------------------
# current_state — release-mode caching
# ---------------------------------------------------------------------------


class TestCurrentStateCaching:
    """``current_state`` owns the release-mode 1-hour cache; local
    mode bypasses it (freshness > rate-limiting when the user
    controls their own remote)."""

    def _patch_release_state(
        self, monkeypatch: pytest.MonkeyPatch, version: VersionInfo,
    ) -> list[VersionInfo]:
        """Replace ``_release_state`` with a stub that records every
        call and returns a fixed up-to-date result.  Returns the
        call log so tests can count invocations."""
        from clarity_agent.setup import version as version_mod
        calls: list[VersionInfo] = []

        def _stub(v: VersionInfo) -> RuntimeState:
            calls.append(v)
            return RuntimeState(
                version=v, git=None,
                update_status="up_to_date", update_latest=None,
                update_reason=None,
            )

        monkeypatch.setattr(version_mod, "_release_state", _stub)
        return calls

    def test_release_reads_within_ttl_reuse_cache(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(PRETEND_ENV_VAR, "v1.0.0")
        calls = self._patch_release_state(
            monkeypatch, VersionInfo(version="v1.0.0", source="release"),
        )

        # First call: cache miss → release-state runs once.
        current_state(now=1000.0)
        # Two more within TTL: served from cache.
        current_state(now=1000.0 + 100)
        current_state(now=1000.0 + CACHE_TTL_SECONDS - 1)
        assert len(calls) == 1

        # Past the TTL boundary: cache miss → re-runs.
        current_state(now=1000.0 + CACHE_TTL_SECONDS + 1)
        assert len(calls) == 2

    def test_force_refresh_bypasses_cache(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ``force_refresh=True`` ignores the cached value and
        # recomputes; the fresh result replaces the cache so
        # subsequent reads see it.
        monkeypatch.setenv(PRETEND_ENV_VAR, "v1.0.0")
        calls = self._patch_release_state(
            monkeypatch, VersionInfo(version="v1.0.0", source="release"),
        )

        current_state(now=1000.0)
        assert len(calls) == 1
        # Within TTL but force_refresh → fresh call.
        current_state(now=1000.0 + 100, force_refresh=True)
        assert len(calls) == 2
        # Subsequent read without force_refresh hits the freshly-
        # cached value.
        current_state(now=1000.0 + 200)
        assert len(calls) == 2

    def test_local_mode_bypasses_cache(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        # Local-mode results must NOT be cached — freshness wins
        # over rate-limiting because the user controls their own
        # git remote.  Three calls, three lookups.
        monkeypatch.delenv(PRETEND_ENV_VAR, raising=False)
        _patch_git(
            monkeypatch, head="aaaaaaaaaaaa1111",
            check_status=UpdateStatus(
                available=False, local_sha="aaaaaaaaaaaa1111",
                remote_sha="aaaaaaaaaaaa1111", commit_count=0,
            ),
        )

        from clarity_agent.setup import version as version_mod
        # Wrap the real ``check_for_updates`` stub installed by
        # ``_patch_git`` to count calls.
        original = version_mod.check_for_updates
        calls: list[Path] = []

        def _counting(agent_dir: Path) -> UpdateStatus:
            calls.append(agent_dir)
            return original(agent_dir)

        monkeypatch.setattr(version_mod, "check_for_updates", _counting)

        for _ in range(3):
            current_state(agent_dir=tmp_path)
        assert len(calls) == 3

    def test_reset_cache_clears_release_cache(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The autouse fixture relies on this; pin it down explicitly
        # so a future refactor that drops ``reset_cache`` is caught.
        monkeypatch.setenv(PRETEND_ENV_VAR, "v1.0.0")
        calls = self._patch_release_state(
            monkeypatch, VersionInfo(version="v1.0.0", source="release"),
        )

        current_state(now=1000.0)
        current_state(now=1000.0 + 100)
        assert len(calls) == 1

        reset_cache()
        current_state(now=1000.0 + 200)
        assert len(calls) == 2
