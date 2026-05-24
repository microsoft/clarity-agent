"""Tests for :mod:`clarity_agent.setup.release_feed`.

Three concerns covered:

  * :func:`is_newer` — the version-comparison primitive.  Has more
    edge cases than the surface suggests (pre-release suffixes,
    missing components, non-numeric strings), so it gets a
    parametrized matrix.
  * :func:`_parse_release` — translates GitHub Releases API JSON
    into our typed :class:`ReleaseInfo`.  Stable across optional
    fields; only ``tag_name`` and ``assets`` are required.
  * :func:`check_for_update` — the orchestrator.  Exercised
    against a stub :class:`ReleaseFeed` so we get every
    (current source, feed result, error case) without network.
"""

from __future__ import annotations

import pytest

from clarity_agent.setup.release_feed import (
    ReleaseInfo,
    UpdateAvailability,
    _parse_release,
    _platform_keys_for_asset,
    check_for_update,
    is_newer,
)
from clarity_agent.setup.version import VersionInfo

# ---------------------------------------------------------------------------
# is_newer — the comparison primitive
# ---------------------------------------------------------------------------


class TestIsNewer:
    @pytest.mark.parametrize(
        ("candidate", "current", "expected"),
        [
            # Straightforward dotted-int comparisons.
            ("v1.2.3", "v1.2.2", True),
            ("v1.2.2", "v1.2.3", False),
            ("v1.2.3", "v1.2.3", False),
            # Major / minor bumps.
            ("v2.0.0", "v1.99.99", True),
            ("v1.3.0", "v1.2.99", True),
            # Missing trailing components → treated as zero.
            ("v1.2", "v1.2.0", False),
            ("v1.2.0", "v1.2", False),
            ("v1.3", "v1.2.99", True),
            # Leading "v" optional on either side.
            ("1.2.3", "v1.2.2", True),
            ("v1.2.3", "1.2.2", True),
            # Pre-release vs release of the same numeric: release wins.
            ("v1.2.3", "v1.2.3-rc1", True),
            ("v1.2.3-rc1", "v1.2.3", False),
            # Pre-release vs pre-release: lexicographic suffix tiebreak.
            ("v1.2.3-rc2", "v1.2.3-rc1", True),
            ("v1.2.3-rc1", "v1.2.3-rc2", False),
            # Non-numeric strings are NEVER newer than anything —
            # this is what keeps the update path quiet on dev /
            # source builds where current_version() returns "local".
            ("v1.2.3", "local", False),
            ("local", "v1.2.3", False),
            ("local", "local", False),
            ("", "v1.2.3", False),
            ("garbage", "v1.2.3", False),
        ],
    )
    def test_comparison_matrix(
        self, candidate: str, current: str, expected: bool,
    ) -> None:
        assert is_newer(candidate, current) is expected


# ---------------------------------------------------------------------------
# _parse_release — GitHub JSON → ReleaseInfo
# ---------------------------------------------------------------------------


class TestParseRelease:
    def test_minimal_response_round_trips_tag(self) -> None:
        # GitHub's "latest release" response with no assets — still
        # produces a valid ReleaseInfo (empty assets map).  Edge
        # case: a release with binaries-not-yet-uploaded would look
        # like this for a few minutes after tagging.
        info = _parse_release({"tag_name": "v1.0.0", "assets": []})
        assert info.version == "v1.0.0"
        assert info.assets == {}

    def test_extracts_dmg_platform_key(self) -> None:
        # Real-world filename shape from the release workflow.
        info = _parse_release({
            "tag_name": "v1.2.3",
            "assets": [
                {
                    "name": "Clarity_1.2.3_aarch64.dmg",
                    "browser_download_url": "https://example.com/arm.dmg",
                },
                {
                    "name": "Clarity_1.2.3_x64.dmg",
                    "browser_download_url": "https://example.com/x64.dmg",
                },
            ],
        })
        assert info.assets["darwin-aarch64"] == "https://example.com/arm.dmg"
        assert info.assets["darwin-x86_64"] == "https://example.com/x64.dmg"

    def test_universal_dmg_matches_both_arches(self) -> None:
        # A DMG without an arch hint in the filename is treated as
        # universal — match both macOS keys so the per-arch lookup
        # in ``current_platform_key`` resolves cleanly.
        info = _parse_release({
            "tag_name": "v1.0.0",
            "assets": [{
                "name": "Clarity.dmg",
                "browser_download_url": "https://example.com/u.dmg",
            }],
        })
        assert info.assets["darwin-aarch64"] == "https://example.com/u.dmg"
        assert info.assets["darwin-x86_64"] == "https://example.com/u.dmg"

    def test_unknown_extension_yields_no_key(self) -> None:
        # A README.md asset (sometimes attached to releases) should
        # quietly fall out of the assets map rather than ending up
        # under some default key.
        info = _parse_release({
            "tag_name": "v1.0.0",
            "assets": [{
                "name": "README.md",
                "browser_download_url": "https://example.com/r.md",
            }],
        })
        assert info.assets == {}

    def test_skips_assets_missing_required_fields(self) -> None:
        # Defensive — a partially-populated asset (no URL, etc.)
        # gets skipped rather than producing a ReleaseInfo with
        # stale / empty URLs.
        info = _parse_release({
            "tag_name": "v1.0.0",
            "assets": [
                {"name": "x.dmg"},  # no browser_download_url
                {"browser_download_url": "https://example.com/y"},  # no name
            ],
        })
        assert info.assets == {}


class TestPlatformKeys:
    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("clarity_aarch64.dmg", {"darwin-aarch64"}),
            ("clarity_arm64.dmg", {"darwin-aarch64"}),
            ("clarity_x86_64.dmg", {"darwin-x86_64"}),
            ("clarity_x64.dmg", {"darwin-x86_64"}),
            ("clarity.msi", {"windows-x86_64"}),
            ("clarity.AppImage", {"linux-x86_64"}),
            ("clarity.app.tar.gz", {"darwin-aarch64", "darwin-x86_64"}),
            ("Clarity.dmg", {"darwin-aarch64", "darwin-x86_64"}),  # universal
            ("notes.txt", set()),
        ],
    )
    def test_key_extraction(self, filename: str, expected: set[str]) -> None:
        assert set(_platform_keys_for_asset(filename)) == expected


# ---------------------------------------------------------------------------
# check_for_update — the orchestrator
# ---------------------------------------------------------------------------


class _StubFeed:
    """In-memory :class:`ReleaseFeed` for orchestrator tests.

    Two modes: ``of(version)`` returns a ReleaseInfo at that tag;
    ``raising(exc)`` raises when queried.  Plus ``empty()`` for the
    "no releases yet" case.
    """

    def __init__(
        self,
        release: ReleaseInfo | None,
        raises: Exception | None = None,
    ) -> None:
        self._release = release
        self._raises = raises

    @classmethod
    def of(cls, version: str) -> _StubFeed:
        return cls(ReleaseInfo(version=version, assets={}))

    @classmethod
    def empty(cls) -> _StubFeed:
        return cls(None)

    @classmethod
    def raising(cls, exc: Exception) -> _StubFeed:
        return cls(None, raises=exc)

    def latest(self) -> ReleaseInfo | None:
        if self._raises is not None:
            raise self._raises
        return self._release


def _release(version: str) -> VersionInfo:
    return VersionInfo(version=version, source="release")


def _local() -> VersionInfo:
    return VersionInfo(version="local", source="local")


class TestCheckForUpdate:
    def test_local_build_short_circuits_to_unknown(self) -> None:
        # Source clones and locally-built frozen binaries don't
        # auto-update — the orchestrator must never trigger a
        # network call for them and must surface a clear reason
        # the UI can show in a tooltip.
        result = check_for_update(
            feed=_StubFeed.of("v9.9.9"),  # would otherwise be "newer"
            current=_local(),
        )
        assert result.status == "unknown"
        assert result.reason == "not a release build"
        assert result.latest is None

    def test_newer_feed_release_reports_available(self) -> None:
        result = check_for_update(
            feed=_StubFeed.of("v1.2.4"),
            current=_release("v1.2.3"),
        )
        assert result.status == "available"
        assert result.latest is not None
        assert result.latest.version == "v1.2.4"

    def test_same_version_reports_up_to_date(self) -> None:
        result = check_for_update(
            feed=_StubFeed.of("v1.2.3"),
            current=_release("v1.2.3"),
        )
        assert result.status == "up_to_date"
        assert result.latest is not None

    def test_older_feed_release_reports_up_to_date(self) -> None:
        # A local pretend-version higher than what's released is a
        # supported test scenario (manual E2E) — orchestrator
        # should not claim an update is available.
        result = check_for_update(
            feed=_StubFeed.of("v1.2.3"),
            current=_release("v9.9.9"),
        )
        assert result.status == "up_to_date"

    def test_empty_feed_reports_up_to_date(self) -> None:
        # Brand-new repo with no releases yet — distinct from a
        # network error, so we say "up to date" with an explanatory
        # ``reason`` rather than "unknown."
        result = check_for_update(
            feed=_StubFeed.empty(),
            current=_release("v1.2.3"),
        )
        assert result.status == "up_to_date"
        assert result.latest is None
        assert result.reason == "no releases on feed"

    def test_feed_error_reports_unknown_with_reason(self) -> None:
        # Network blip / parse error → UI shows a quiet tooltip
        # rather than a failure modal.  The exception message
        # gets passed through so users can see what went wrong.
        result = check_for_update(
            feed=_StubFeed.raising(RuntimeError("connection reset")),
            current=_release("v1.2.3"),
        )
        assert result.status == "unknown"
        assert result.reason is not None
        assert "connection reset" in result.reason

    def test_carries_current_version_through_every_branch(self) -> None:
        # The result includes the running version so the UI doesn't
        # have to ask twice.  Verify every branch populates it.
        current = _release("v1.2.3")
        for feed in [
            _StubFeed.of("v1.2.4"),
            _StubFeed.of("v1.2.3"),
            _StubFeed.empty(),
            _StubFeed.raising(RuntimeError("x")),
        ]:
            result = check_for_update(feed=feed, current=current)
            assert result.current is current


class TestUpdateAvailability:
    def test_frozen_dataclass(self) -> None:
        # Cached via the version endpoint — must be immutable so
        # the cache can't be poisoned by a misbehaving consumer.
        from dataclasses import FrozenInstanceError
        avail = UpdateAvailability(
            status="up_to_date", current=_release("v1.0.0"),
        )
        with pytest.raises(FrozenInstanceError):
            avail.status = "available"  # type: ignore[misc]
