"""Tests for :mod:`clarity_agent.web.version_endpoint`.

The endpoint helper has two responsibilities: shape the JSON
response, and cache the (network-touching) update check with a TTL.
Both are exercised here against the same ``StubReleaseFeed`` pattern
used in ``test_release_feed.py`` — no network access, no real
``GitHubReleaseFeed`` instantiation.
"""

from __future__ import annotations

import pytest

from clarity_agent.setup.release_feed import ReleaseInfo
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
        return ReleaseInfo(version=self._version, assets={})


@pytest.fixture(autouse=True)
def _clear_cache_each_test() -> None:
    # Module-level cache leaks between tests otherwise.  ``autouse``
    # so every test starts from a clean slate without remembering.
    reset_cache()


class TestPayloadShape:
    def test_local_build_payload(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # No PRETEND override → ``_version.py`` defaults → "local".
        # Update check short-circuits to ``unknown`` for non-release
        # builds (the orchestrator's responsibility, already
        # tested) — the endpoint just shapes the result.
        monkeypatch.delenv(PRETEND_ENV_VAR, raising=False)
        feed = _StubFeed("v9.9.9")  # would otherwise look "newer"

        payload = get_version_payload(feed=feed)

        assert payload["version"] == "local"
        assert payload["source"] == "local"
        assert payload["is_release"] is False
        assert payload["update_status"] == "unknown"
        assert payload["latest"] is None
        assert payload["reason"] == "not a release build"
        # The feed must NOT be queried for a non-release build —
        # that's the orchestrator's short-circuit.  Verify the
        # endpoint doesn't accidentally bypass it.
        assert feed.call_count == 0

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
        assert payload["latest"] == {"version": "v1.2.4", "assets": {}}
        assert payload["reason"] is None

    def test_release_up_to_date(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(PRETEND_ENV_VAR, "v1.2.3")
        feed = _StubFeed("v1.2.3")

        payload = get_version_payload(feed=feed)

        assert payload["update_status"] == "up_to_date"
        assert payload["latest"] == {"version": "v1.2.3", "assets": {}}


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
