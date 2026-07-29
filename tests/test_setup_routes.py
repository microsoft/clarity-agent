"""Tests for the setup-wizard API helpers in
:mod:`clarity_agent.web.setup_routes`.

Focus: a failed connection test must carry a ``setup_url`` — a direct
link to the tool's download / credential page — so the wizard can
render a clickable install link next to the error instead of bare
"install it" prose (issue #124).
"""

from __future__ import annotations

import pytest

from clarity_agent.llm.config import _PROVIDERS, get_auth_mode_names
from clarity_agent.setup import doctor
from clarity_agent.setup.doctor import CheckResult, Status
from clarity_agent.web import setup_routes


class TestSetupUrlLookup:
    """``_setup_url`` resolves the download/credential link, with a
    provider-level fallback so failures always have somewhere to point."""

    def test_returns_auth_mode_url_when_present(self) -> None:
        # The gh auth mode is the issue's motivating example.
        assert (
            setup_routes._setup_url("github", "gh_cli")
            == "https://cli.github.com/"
        )

    def test_falls_back_to_provider_level_url(self) -> None:
        # azure/device_code defines no setup_url of its own, so the
        # lookup should fall back to the provider-level Azure URL.
        assert _PROVIDERS["azure"].get("setup_url")
        assert (
            setup_routes._setup_url("azure", "device_code")
            == _PROVIDERS["azure"]["setup_url"]
        )

    def test_returns_none_for_unknown_provider(self) -> None:
        assert setup_routes._setup_url("nonexistent", "api_key") is None

    def test_every_provider_and_mode_resolves_a_url(self) -> None:
        """Invariant: every provider/auth-mode combination resolves a
        setup_url. This guarantees a missing-tool error can always show
        a link, and guards against a new mode landing without one."""
        for provider in _PROVIDERS:
            for mode in get_auth_mode_names(provider):
                assert setup_routes._setup_url(provider, mode), (
                    f"{provider}/{mode} has no resolvable setup_url — a "
                    "failed test would show no download link"
                )


class TestTestConnectionSetupUrl:
    """``_test_connection`` attaches ``setup_url`` on failure only."""

    def _patch_probe(self, monkeypatch: pytest.MonkeyPatch, fn) -> None:
        # _test_connection routes non-anthropic-sdk, non-github
        # providers through _probe_api.
        monkeypatch.setattr(doctor, "_probe_api", fn)

    def test_attaches_url_when_probe_raises(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def boom(*_a, **_k):
            raise RuntimeError("The GitHub CLI (gh) is not installed.")

        self._patch_probe(monkeypatch, boom)
        result = setup_routes._test_connection("openai", "api_key")

        assert result["ok"] is False
        assert result["setup_url"] == "https://platform.openai.com/api-keys"
        # The classifier hint is still present alongside the link.
        assert "hint" in result

    def test_attaches_url_when_probe_reports_non_pass(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def warn(*_a, **_k):
            return CheckResult(
                name="Backend health",
                status=Status.WARN,
                message="Empty response",
            )

        self._patch_probe(monkeypatch, warn)
        result = setup_routes._test_connection("openai", "api_key")

        assert result["ok"] is False
        assert result["setup_url"] == "https://platform.openai.com/api-keys"

    def test_no_url_on_success(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def ok(*_a, **_k):
            return CheckResult(
                name="Backend health",
                status=Status.PASS,
                message="Provider responded successfully",
            )

        self._patch_probe(monkeypatch, ok)
        result = setup_routes._test_connection("openai", "api_key")

        assert result["ok"] is True
        assert "setup_url" not in result
