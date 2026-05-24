"""Tests for :mod:`clarity_agent.setup.version`.

Covers the env-var override (``PRETEND_TO_BE_VERSION``) and the
fallback to the baked ``_version.py`` defaults.  Together with the
release-feed tests these pin down the *full* current-version
resolution path that the UI badge + update flow depend on.
"""

from __future__ import annotations

import pytest

from clarity_agent.setup.version import (
    PRETEND_ENV_VAR,
    VersionInfo,
    current_version,
)


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
