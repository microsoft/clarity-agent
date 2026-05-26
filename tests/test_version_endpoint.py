"""Tests for :mod:`clarity_agent.web.version_endpoint`.

The endpoint helper has three responsibilities now: shape the JSON
response for release-mode builds, do the same for local (git-checkout)
builds, and cache the network-touching part with a TTL.  Both modes
are exercised here without real network or subprocess access —
release mode through the stub ``ReleaseFeed`` pattern, local mode
by monkey-patching the ``check_for_updates`` import.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clarity_agent.setup.release_feed import ReleaseInfo
from clarity_agent.setup.updater import UpdateStatus
from clarity_agent.setup.version import PRETEND_ENV_VAR
from clarity_agent.web.version_endpoint import (
    CACHE_TTL_SECONDS,
    get_version_payload,
    reset_cache,
)


class _StubFeed:
    """Counts calls so we can verify caching behavior end-to-end."""

    def __init__(self, version: str) -> None:
        self._version = version
        self.call_count = 0

    def latest(self) -> ReleaseInfo:
        self.call_count += 1
        return ReleaseInfo(
            version=self._version, assets={},
            release_url=f"https://example/releases/{self._version}",
        )


def _patch_local(
    monkeypatch: pytest.MonkeyPatch,
    status: UpdateStatus,
    branch: str = "main",
) -> None:
    """Monkey-patch the lazily-imported local-mode dependencies that
    ``_local_payload`` uses.  Each test that exercises the local-mode
    branch calls this with the ``UpdateStatus`` it wants the endpoint
    to see; ``branch`` flows into the ``_git_current_branch`` stub so
    the ``latest.branch`` field can be asserted."""
    import clarity_agent.setup.updater as updater_mod
    monkeypatch.setattr(updater_mod, "check_for_updates", lambda _p: status)
    monkeypatch.setattr(updater_mod, "_git_current_branch", lambda _p: branch)


@pytest.fixture(autouse=True)
def _clear_cache_each_test() -> None:
    # Module-level cache leaks between tests otherwise.  ``autouse``
    # so every test starts from a clean slate without remembering.
    reset_cache()


class TestPayloadShape:
    def test_local_build_with_update_available(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        # No PRETEND override → ``_version.py`` defaults → "local".
        # The endpoint dispatches to the git check; we stub it to
        # report "5 commits behind on main."  This shape is what
        # the UpdateBadge will switch on.
        monkeypatch.delenv(PRETEND_ENV_VAR, raising=False)
        _patch_local(monkeypatch, UpdateStatus(
            available=True, local_sha="aaaa", remote_sha="bbbbbbbbbbbbbbbb",
            commit_count=5,
        ), branch="main")

        payload = get_version_payload(agent_dir=tmp_path)

        assert payload["version"] == "local"
        assert payload["source"] == "local"
        assert payload["is_release"] is False
        assert payload["update_status"] == "available"
        assert payload["latest"] == {
            "kind": "git",
            "branch": "main",
            "commit_count": 5,
            "remote_sha": "bbbbbbbbbbbb",  # truncated to 12 chars
        }
        assert payload["reason"] is None

    def test_local_build_up_to_date(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        # When the git check returns available=False with a known
        # remote_sha, the endpoint surfaces ``up_to_date``.
        monkeypatch.delenv(PRETEND_ENV_VAR, raising=False)
        _patch_local(monkeypatch, UpdateStatus(
            available=False, local_sha="aaaa", remote_sha="aaaa",
            commit_count=0,
        ))

        payload = get_version_payload(agent_dir=tmp_path)
        assert payload["update_status"] == "up_to_date"
        assert payload["latest"] is None
        assert payload["reason"] is None

    def test_local_build_no_upstream(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        # When the branch has no upstream (rev-parse failed →
        # remote_sha is None), the badge stays silent: status is
        # ``unknown`` with a reason the tooltip can show.
        monkeypatch.delenv(PRETEND_ENV_VAR, raising=False)
        _patch_local(monkeypatch, UpdateStatus(
            available=False, local_sha="aaaa", remote_sha=None,
            commit_count=0,
        ))

        payload = get_version_payload(agent_dir=tmp_path)
        assert payload["update_status"] == "unknown"
        assert payload["latest"] is None
        assert payload["reason"] is not None
        assert "upstream" in payload["reason"]

    def test_local_build_git_error_is_unknown(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        # An unexpected exception from the git layer must NOT
        # cascade into the route — it gets shaped as ``unknown``
        # with the exception message in ``reason``.
        monkeypatch.delenv(PRETEND_ENV_VAR, raising=False)
        import clarity_agent.setup.updater as updater_mod

        def _raise(_p: Path) -> UpdateStatus:
            raise RuntimeError("simulated git crash")
        monkeypatch.setattr(updater_mod, "check_for_updates", _raise)

        payload = get_version_payload(agent_dir=tmp_path)
        assert payload["update_status"] == "unknown"
        assert payload["latest"] is None
        assert "simulated git crash" in (payload["reason"] or "")

    def test_local_build_without_agent_dir_is_misconfig(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Route handlers must thread ``agent_dir`` through.  If they
        # forget, surface that as a configuration error rather than
        # silently returning "up_to_date" — the badge being wrong
        # in either direction is worse than this loud signal.
        monkeypatch.delenv(PRETEND_ENV_VAR, raising=False)

        payload = get_version_payload()
        assert payload["source"] == "local"
        assert payload["update_status"] == "unknown"
        assert "agent_dir" in (payload["reason"] or "")

    def test_release_with_available_update(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(PRETEND_ENV_VAR, "v1.2.3")
        feed = _StubFeed("v1.2.4")

        payload = get_version_payload(feed=feed)

        assert payload["version"] == "v1.2.3"
        assert payload["source"] == "release"
        assert payload["is_release"] is True
        assert payload["update_status"] == "available"
        assert payload["latest"] == {
            "kind": "release",
            "version": "v1.2.4",
            "assets": {},
            "release_url": "https://example/releases/v1.2.4",
        }
        assert payload["reason"] is None

    def test_release_up_to_date(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(PRETEND_ENV_VAR, "v1.2.3")
        feed = _StubFeed("v1.2.3")

        payload = get_version_payload(feed=feed)

        assert payload["update_status"] == "up_to_date"
        assert payload["latest"] == {
            "kind": "release",
            "version": "v1.2.3",
            "assets": {},
            "release_url": "https://example/releases/v1.2.3",
        }


class TestCaching:
    """Cache behavior gets exercised by injecting a counting stub
    feed.  Tests that go through the cache use ``feed=None`` (the
    production path); tests that bypass it pass a feed.

    These tests substitute ``check_for_update`` itself rather than
    relying on the GitHub network call — that way "first call hits
    the feed; subsequent calls within TTL don't" is verifiable
    deterministically.
    """

    def test_repeated_reads_within_ttl_hit_the_cache(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Patch the orchestrator the endpoint module uses to count
        # how many times it's invoked.  ``feed=None`` is the
        # production path; without caching the orchestrator would
        # run on every read.
        monkeypatch.setenv(PRETEND_ENV_VAR, "v1.0.0")
        calls = []
        from clarity_agent.setup.release_feed import UpdateAvailability
        from clarity_agent.setup.version import VersionInfo
        from clarity_agent.web import version_endpoint as ve

        def _stub_check(current: VersionInfo) -> UpdateAvailability:
            calls.append(current.version)
            return UpdateAvailability(
                status="up_to_date", current=current,
            )

        # Monkey-patch the bound name the endpoint module imported.
        monkeypatch.setattr(ve, "check_for_update", _stub_check)

        # First read: cache miss → orchestrator runs once.
        get_version_payload()
        assert len(calls) == 1
        # Second read at the same logical time: cache hit, no extra call.
        get_version_payload()
        get_version_payload()
        assert len(calls) == 1

    def test_cache_expires_after_ttl(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Drive the clock manually via the ``now`` kwarg so we can
        # verify TTL behavior without ``time.sleep``.
        monkeypatch.setenv(PRETEND_ENV_VAR, "v1.0.0")
        calls = []
        from clarity_agent.setup.release_feed import UpdateAvailability
        from clarity_agent.setup.version import VersionInfo
        from clarity_agent.web import version_endpoint as ve

        def _stub_check(current: VersionInfo) -> UpdateAvailability:
            calls.append(current.version)
            return UpdateAvailability(
                status="up_to_date", current=current,
            )

        monkeypatch.setattr(ve, "check_for_update", _stub_check)

        get_version_payload(now=1000.0)
        assert len(calls) == 1
        # Just before TTL boundary: still cached.
        get_version_payload(now=1000.0 + CACHE_TTL_SECONDS - 1)
        assert len(calls) == 1
        # Past the boundary: refresh fires.
        get_version_payload(now=1000.0 + CACHE_TTL_SECONDS + 1)
        assert len(calls) == 2

    def test_stub_feed_bypasses_cache(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Explicit ``feed`` arg means a test is providing its own
        # source of truth.  Caching a stub result against
        # subsequent real calls would poison the production path,
        # so the helper must refuse to cache when a feed is passed.
        monkeypatch.setenv(PRETEND_ENV_VAR, "v1.0.0")
        feed = _StubFeed("v1.0.0")

        for _ in range(3):
            get_version_payload(feed=feed)

        # Each call must hit the stub; no caching.
        assert feed.call_count == 3
