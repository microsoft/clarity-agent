"""Tests for clarity_agent.setup.doctor."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clarity_agent.setup.doctor import (
    CheckResult,
    Status,
    check_backend_health,
    check_clarity_command,
    check_installation_type,
    check_llm_provider,
    check_npm_dependencies,
    check_python_dependencies,
    check_python_version,
    check_repo_freshness,
    run_all_checks,
)

# ---------------------------------------------------------------------------
# check_installation_type
# ---------------------------------------------------------------------------

class TestCheckInstallationType:
    """Installation type detection and agent config snippet sub-check."""

    def test_standalone(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        results = check_installation_type(tmp_path)
        assert len(results) == 1
        assert results[0].status == Status.PASS
        assert "Standalone" in results[0].message

    def test_not_a_git_repo(self, tmp_path: Path) -> None:
        results = check_installation_type(tmp_path)
        assert len(results) == 1
        assert results[0].status == Status.WARN

    def test_embedded_with_snippet(self, tmp_path: Path) -> None:
        from clarity_agent.setup.snippet import BEGIN_DELIMITER, END_DELIMITER

        host = tmp_path / "myproject"
        host.mkdir()
        (host / ".git").mkdir()
        agent = host / ".clarity-agent"
        agent.mkdir()
        (agent / ".git").mkdir()
        (host / "CLAUDE.md").write_text(
            f"# Config\n{BEGIN_DELIMITER}\nclarity\n{END_DELIMITER}\n"
        )

        results = check_installation_type(agent)
        assert len(results) == 2
        assert results[0].status == Status.PASS
        assert "In-repo" in results[0].message
        assert results[1].status == Status.PASS
        assert "snippet" in results[1].message

    def test_embedded_legacy_clarity_reference(self, tmp_path: Path) -> None:
        """Old-style AGENTS.md that mentions clarity still passes."""
        host = tmp_path / "myproject"
        host.mkdir()
        (host / ".git").mkdir()
        agent = host / ".clarity-agent"
        agent.mkdir()
        (agent / ".git").mkdir()
        (host / "AGENTS.md").write_text("# AGENTS\nUses clarity protocol\n")

        results = check_installation_type(agent)
        assert len(results) == 2
        assert results[1].status == Status.PASS
        assert "legacy" in results[1].message

    def test_embedded_no_clarity_reference(self, tmp_path: Path) -> None:
        host = tmp_path / "myproject"
        host.mkdir()
        (host / ".git").mkdir()
        agent = host / ".clarity-agent"
        agent.mkdir()
        (agent / ".git").mkdir()
        (host / "AGENTS.md").write_text("# AGENTS\nSome unrelated content\n")

        results = check_installation_type(agent)
        assert len(results) == 2
        assert results[1].status == Status.WARN
        assert "no clarity snippet" in results[1].message
        assert results[1].fix_fn is not None

    def test_embedded_fix_inserts_snippet(self, tmp_path: Path) -> None:
        from clarity_agent.setup.snippet import BEGIN_DELIMITER

        host = tmp_path / "myproject"
        host.mkdir()
        (host / ".git").mkdir()
        agent = host / ".clarity-agent"
        agent.mkdir()
        (agent / ".git").mkdir()
        (host / "AGENTS.md").write_text("# AGENTS\nExisting content\n")

        results = check_installation_type(agent)
        fix = results[1].fix_fn
        assert fix is not None
        assert fix()
        content = (host / "AGENTS.md").read_text()
        assert "Existing content" in content
        assert BEGIN_DELIMITER in content

    def test_embedded_no_config_file(self, tmp_path: Path) -> None:
        host = tmp_path / "myproject"
        host.mkdir()
        (host / ".git").mkdir()
        agent = host / ".clarity-agent"
        agent.mkdir()
        (agent / ".git").mkdir()

        results = check_installation_type(agent)
        assert len(results) == 2
        assert results[1].status == Status.WARN
        assert results[1].fix_fn is not None

    def test_embedded_no_config_fix_creates_file(self, tmp_path: Path) -> None:
        from clarity_agent.setup.snippet import BEGIN_DELIMITER

        host = tmp_path / "myproject"
        host.mkdir()
        (host / ".git").mkdir()
        agent = host / ".clarity-agent"
        agent.mkdir()
        (agent / ".git").mkdir()

        results = check_installation_type(agent)
        fix = results[1].fix_fn
        assert fix is not None
        assert fix()
        # Should create the default target (AGENTS.md).
        target = host / "AGENTS.md"
        assert target.exists()
        assert BEGIN_DELIMITER in target.read_text()


# ---------------------------------------------------------------------------
# check_repo_freshness
# ---------------------------------------------------------------------------

class TestCheckRepoFreshness:
    """Repo freshness checks — always WARN-level."""

    def test_not_a_git_repo(self, tmp_path: Path) -> None:
        result = check_repo_freshness(tmp_path)
        assert result.status == Status.WARN

    def test_up_to_date(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        with patch("clarity_agent.setup.doctor.subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),              # fetch
                MagicMock(returncode=0, stdout="0\n"),  # rev-list
            ]
            result = check_repo_freshness(tmp_path)
        assert result.status == Status.PASS

    def test_behind_remote(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        with patch("clarity_agent.setup.doctor.subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),              # fetch
                MagicMock(returncode=0, stdout="5\n"),  # rev-list
            ]
            result = check_repo_freshness(tmp_path)
        assert result.status == Status.WARN
        assert "5 commit(s)" in result.message
        assert result.fix_fn is not None

    def test_no_upstream_branch(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        with patch("clarity_agent.setup.doctor.subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),              # fetch
                MagicMock(returncode=128, stdout=""),  # rev-list fails
            ]
            result = check_repo_freshness(tmp_path)
        assert result.status == Status.WARN
        assert "upstream" in result.message.lower() or "freshness" in result.message.lower()

    def test_timeout(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        with patch("clarity_agent.setup.doctor.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("git", 15)
            result = check_repo_freshness(tmp_path)
        assert result.status == Status.WARN


# ---------------------------------------------------------------------------
# check_python_version
# ---------------------------------------------------------------------------

class TestCheckPythonVersion:
    """Python version check."""

    def test_current_python_passes(self) -> None:
        result = check_python_version()
        assert result.status == Status.PASS

    def test_old_python_fails(self) -> None:
        with patch.object(sys, "version_info", (3, 9, 0)):
            result = check_python_version()
        assert result.status == Status.FAIL
        assert "3.12" in result.message


# ---------------------------------------------------------------------------
# check_python_dependencies
# ---------------------------------------------------------------------------

class TestCheckPythonDependencies:
    """Python dependency checks."""

    def test_all_installed(self, tmp_path: Path) -> None:
        with patch("clarity_agent.setup.doctor._try_import", return_value=True), \
             patch("clarity_agent.llm.config._has_package", return_value=True):
            results = check_python_dependencies(tmp_path)
        assert all(r.status == Status.PASS for r in results)

    def test_core_dep_missing(self, tmp_path: Path) -> None:
        def _selective_import(name: str) -> bool:
            if name == "prompt_toolkit":
                return False
            return True

        with patch("clarity_agent.setup.doctor._try_import", side_effect=_selective_import), \
             patch("clarity_agent.llm.config._has_package", return_value=True):
            results = check_python_dependencies(tmp_path)

        prompt_result = next(r for r in results if "prompt-toolkit" in r.name)
        assert prompt_result.status == Status.FAIL
        assert prompt_result.fix_fn is not None

    def test_cli_dep_missing(self, tmp_path: Path) -> None:
        def _selective_import(name: str) -> bool:
            if name == "anthropic":
                return False
            return True

        with patch("clarity_agent.setup.doctor._try_import", side_effect=_selective_import), \
             patch("clarity_agent.llm.config._has_package", return_value=True):
            results = check_python_dependencies(tmp_path)

        anthropic_result = next(r for r in results if "anthropic" in r.name)
        assert anthropic_result.status == Status.WARN


# ---------------------------------------------------------------------------
# check_npm_dependencies
# ---------------------------------------------------------------------------

class TestCheckNpmDependencies:
    """NPM / web dependency checks — all WARN-level."""

    def test_no_web_dir(self, tmp_path: Path) -> None:
        results = check_npm_dependencies(tmp_path)
        assert results == []

    def test_node_not_installed(self, tmp_path: Path) -> None:
        (tmp_path / "web").mkdir()
        (tmp_path / "web" / "package.json").write_text("{}")
        with patch("clarity_agent.setup.doctor.shutil.which", return_value=None):
            results = check_npm_dependencies(tmp_path)
        assert len(results) == 1
        assert results[0].status == Status.WARN
        assert "Node.js not found" in results[0].message

    def test_node_old_version(self, tmp_path: Path) -> None:
        (tmp_path / "web").mkdir()
        (tmp_path / "web" / "package.json").write_text("{}")
        (tmp_path / "web" / "node_modules").mkdir()
        (tmp_path / "web" / "dist").mkdir()
        with patch("clarity_agent.setup.doctor.shutil.which", return_value="/usr/bin/node"), \
             patch("clarity_agent.setup.doctor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="v20.0.0\n")
            results = check_npm_dependencies(tmp_path)
        node_ver = next(r for r in results if "version" in r.name.lower())
        assert node_ver.status == Status.WARN

    def test_node_modules_missing(self, tmp_path: Path) -> None:
        (tmp_path / "web").mkdir()
        (tmp_path / "web" / "package.json").write_text("{}")
        with patch("clarity_agent.setup.doctor.shutil.which", return_value="/usr/bin/node"), \
             patch("clarity_agent.setup.doctor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="v22.0.0\n")
            results = check_npm_dependencies(tmp_path)
        npm_result = next(r for r in results if "NPM" in r.name)
        assert npm_result.status == Status.WARN
        assert npm_result.fix_fn is not None

    def test_all_present(self, tmp_path: Path) -> None:
        (tmp_path / "web").mkdir()
        (tmp_path / "web" / "package.json").write_text("{}")
        (tmp_path / "web" / "node_modules").mkdir()
        (tmp_path / "web" / "dist").mkdir()
        with patch("clarity_agent.setup.doctor.shutil.which", return_value="/usr/bin/node"), \
             patch("clarity_agent.setup.doctor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="v22.0.0\n")
            results = check_npm_dependencies(tmp_path)
        assert all(r.status == Status.PASS for r in results)


# ---------------------------------------------------------------------------
# check_clarity_command
# ---------------------------------------------------------------------------

class TestCheckClarityCommand:
    """Clarity wrapper command detection."""

    def test_standalone_wrapper_exists(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        wrapper = tmp_path / "clarity"
        wrapper.write_text("#!/usr/bin/env bash\nexec python clarity.py\n")
        wrapper.chmod(0o755)
        result = check_clarity_command(tmp_path)
        assert result.status == Status.PASS
        assert str(wrapper) in result.message

    def test_embedded_wrapper_exists(self, tmp_path: Path) -> None:
        host = tmp_path / "myproject"
        host.mkdir()
        (host / ".git").mkdir()
        agent = host / ".clarity-agent"
        agent.mkdir()
        (agent / ".git").mkdir()
        wrapper = host / "clarity"
        wrapper.write_text("#!/usr/bin/env bash\nexec python clarity.py\n")
        wrapper.chmod(0o755)
        result = check_clarity_command(agent)
        assert result.status == Status.PASS
        assert str(wrapper) in result.message

    def test_wrapper_on_path(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        # No wrapper at expected location, but on PATH
        with patch("clarity_agent.setup.doctor.shutil.which", return_value="/usr/local/bin/clarity"):
            result = check_clarity_command(tmp_path)
        assert result.status == Status.PASS
        assert "/usr/local/bin/clarity" in result.message

    def test_wrapper_missing_standalone(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        with patch("clarity_agent.setup.doctor.shutil.which", return_value=None):
            result = check_clarity_command(tmp_path)
        assert result.status == Status.WARN
        assert result.fix_fn is not None
        assert result.fix_hint is not None
        assert "install.sh" in result.fix_hint

    def test_wrapper_missing_embedded(self, tmp_path: Path) -> None:
        host = tmp_path / "myproject"
        host.mkdir()
        (host / ".git").mkdir()
        agent = host / ".clarity-agent"
        agent.mkdir()
        (agent / ".git").mkdir()
        with patch("clarity_agent.setup.doctor.shutil.which", return_value=None):
            result = check_clarity_command(agent)
        assert result.status == Status.WARN
        assert result.fix_hint is not None
        assert "install.sh" in result.fix_hint

    def test_fix_creates_standalone_wrapper(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        with patch("clarity_agent.setup.doctor.shutil.which", return_value=None):
            result = check_clarity_command(tmp_path)
        assert result.fix_fn is not None
        assert result.fix_fn()
        wrapper = tmp_path / "clarity"
        assert wrapper.exists()
        content = wrapper.read_text()
        assert "clarity.py" in content
        assert '$(cd "$(dirname "$0")" && pwd)' in content

    def test_fix_creates_embedded_wrapper(self, tmp_path: Path) -> None:
        host = tmp_path / "myproject"
        host.mkdir()
        (host / ".git").mkdir()
        agent = host / ".clarity-agent"
        agent.mkdir()
        (agent / ".git").mkdir()
        with patch("clarity_agent.setup.doctor.shutil.which", return_value=None):
            result = check_clarity_command(agent)
        assert result.fix_fn is not None
        assert result.fix_fn()
        wrapper = host / "clarity"
        assert wrapper.exists()
        content = wrapper.read_text()
        assert "clarity.py" in content
        assert str(agent) in content


# ---------------------------------------------------------------------------
# check_llm_provider
# ---------------------------------------------------------------------------

class TestDetectProvider:
    """_detect_provider — extends auto-detection with SDK fallback."""

    def test_delegates_to_auto_detect(self) -> None:
        from clarity_agent.setup.doctor import _detect_provider
        with patch("clarity_agent.llm.config._auto_detect_provider", return_value=("anthropic", "api_key")):
            assert _detect_provider() == ("anthropic", "api_key")

    def test_falls_back_to_sdk_when_package_installed(self) -> None:
        from clarity_agent.setup.doctor import _detect_provider
        with patch("clarity_agent.llm.config._auto_detect_provider", return_value=None), \
             patch("clarity_agent.llm.config._has_package", return_value=True):
            assert _detect_provider() == ("anthropic", "claude_sdk")

    def test_returns_none_when_nothing_available(self) -> None:
        from clarity_agent.setup.doctor import _detect_provider
        with patch("clarity_agent.llm.config._auto_detect_provider", return_value=None), \
             patch("clarity_agent.llm.config._has_package", return_value=False):
            assert _detect_provider() is None


class TestCheckLlmProvider:
    """LLM provider detection check."""

    def test_provider_detected(self, tmp_path: Path) -> None:
        with patch("clarity_agent.setup.doctor._detect_provider", return_value=("anthropic", "api_key")):
            result = check_llm_provider(tmp_path)
        assert result.status == Status.PASS
        assert "anthropic" in result.message

    def test_no_provider(self, tmp_path: Path) -> None:
        with patch("clarity_agent.setup.doctor._detect_provider", return_value=None):
            result = check_llm_provider(tmp_path)
        assert result.status == Status.FAIL
        assert result.fix_hint is not None
        assert result.fix_fn is not None


# ---------------------------------------------------------------------------
# check_backend_health
# ---------------------------------------------------------------------------

class TestCheckBackendHealth:
    """Backend health probes."""

    def test_no_provider_detected(self, tmp_path: Path) -> None:
        with patch("clarity_agent.setup.doctor._detect_provider", return_value=None):
            result = check_backend_health(tmp_path)
        assert result.status == Status.FAIL

    def test_api_provider_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
        mock_response = MagicMock()
        mock_response.text = "ok"

        mock_client = MagicMock()

        with patch("clarity_agent.setup.doctor._detect_provider", return_value=("anthropic", "api_key")), \
             patch("clarity_agent.llm.factory.get_provider_tier_defaults", return_value={"default": "test-model"}), \
             patch("clarity_agent.llm.config.LLMConfig.create_client", return_value=mock_client), \
             patch("clarity_agent.setup.doctor.asyncio.run", return_value=mock_response):
            result = check_backend_health(tmp_path)
        assert result.status == Status.PASS

    def test_api_provider_auth_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "bad-key")

        with patch("clarity_agent.setup.doctor._detect_provider", return_value=("openai", "api_key")), \
             patch("clarity_agent.llm.factory.get_provider_tier_defaults", return_value={"default": "test-model"}), \
             patch("clarity_agent.llm.config.LLMConfig.create_client", side_effect=Exception("401 Unauthorized: invalid API key")):
            result = check_backend_health(tmp_path)
        assert result.status == Status.FAIL
        assert result.fix_hint is not None
        assert "invalid" in result.fix_hint.lower() or "api key" in result.fix_hint.lower()
        assert result.fix_fn is not None

    def test_sdk_provider_success(self, tmp_path: Path) -> None:
        mock_backend = MagicMock()
        mock_backend.chat.return_value = "ok"

        with patch("clarity_agent.setup.doctor._detect_provider", return_value=("anthropic", "claude_sdk")), \
             patch("clarity_agent.llm.impl.claude_sdk.SdkChatBackend", return_value=mock_backend):
            result = check_backend_health(tmp_path)
        assert result.status == Status.PASS
        mock_backend.disconnect.assert_called_once()

    def test_sdk_provider_failure(self, tmp_path: Path) -> None:
        mock_backend = MagicMock()
        mock_backend.chat.side_effect = Exception("billing quota exceeded")

        with patch("clarity_agent.setup.doctor._detect_provider", return_value=("anthropic", "claude_sdk")), \
             patch("clarity_agent.llm.impl.claude_sdk.SdkChatBackend", return_value=mock_backend):
            result = check_backend_health(tmp_path)
        assert result.status == Status.FAIL
        mock_backend.disconnect.assert_called_once()


# ---------------------------------------------------------------------------
# run_all_checks
# ---------------------------------------------------------------------------

class TestRunAllChecks:
    """Integration test for the orchestrator."""

    def test_returns_results_for_all_categories(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / ".env").write_text("")
        # Create clarity wrapper so that check passes
        wrapper = tmp_path / "clarity"
        wrapper.write_text("#!/usr/bin/env bash\n")
        wrapper.chmod(0o755)

        with patch("clarity_agent.setup.doctor.subprocess.run") as mock_run, \
             patch("clarity_agent.setup.doctor._try_import", return_value=True), \
             patch("clarity_agent.llm.config._has_package", return_value=True), \
             patch("clarity_agent.setup.doctor._detect_provider", return_value=("anthropic", "api_key")), \
             patch("clarity_agent.setup.doctor.check_backend_health") as mock_health:
            mock_run.side_effect = [
                MagicMock(returncode=0),
                MagicMock(returncode=0, stdout="0\n"),
            ]
            mock_health.return_value = CheckResult(
                name="Backend health",
                status=Status.PASS,
                message="ok",
            )
            results = run_all_checks(tmp_path)

        names = [r.name for r in results]
        assert "Installation type" in names
        assert "Repo freshness" in names
        assert "Python version" in names
        assert "Clarity command" in names
        assert "LLM provider" in names
        assert "Backend health" in names

    def test_skips_health_when_no_provider(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / ".env").write_text("")

        with patch("clarity_agent.setup.doctor.subprocess.run") as mock_run, \
             patch("clarity_agent.setup.doctor._try_import", return_value=True), \
             patch("clarity_agent.llm.config._has_package", return_value=True), \
             patch("clarity_agent.setup.doctor._detect_provider", return_value=None), \
             patch("clarity_agent.setup.doctor.shutil.which", return_value=None):
            mock_run.side_effect = [
                MagicMock(returncode=0),
                MagicMock(returncode=0, stdout="0\n"),
            ]
            results = run_all_checks(tmp_path)

        health = next(r for r in results if r.name == "Backend health")
        assert health.status == Status.FAIL
        assert "Skipped" in health.message


# ---------------------------------------------------------------------------
# _classify_error
# ---------------------------------------------------------------------------

class TestClassifyError:
    """Error classification for fix hints."""

    def test_auth_error(self) -> None:
        from clarity_agent.setup.doctor import _classify_error
        hint = _classify_error(Exception("401 Unauthorized"), "anthropic")
        assert "invalid" in hint.lower() or "expired" in hint.lower()

    def test_network_error(self) -> None:
        from clarity_agent.setup.doctor import _classify_error
        hint = _classify_error(Exception("Connection timeout"), "openai")
        assert "network" in hint.lower() or "internet" in hint.lower()

    def test_rate_limit(self) -> None:
        from clarity_agent.setup.doctor import _classify_error
        hint = _classify_error(Exception("429 Too Many Requests"), "azure")
        assert "rate" in hint.lower()

    def test_billing_error(self) -> None:
        from clarity_agent.setup.doctor import _classify_error
        hint = _classify_error(Exception("billing quota exceeded"), "anthropic")
        assert "billing" in hint.lower()

    def test_generic_error(self) -> None:
        from clarity_agent.setup.doctor import _classify_error
        hint = _classify_error(ValueError("something weird"), "openai")
        assert "ValueError" in hint


# ---------------------------------------------------------------------------
# _update_env_var
# ---------------------------------------------------------------------------

class TestUpdateEnvVar:
    """Tests for the .env file updater."""

    def test_creates_new_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from clarity_agent.setup.doctor import _update_env_var
        env_path = tmp_path / ".env"
        monkeypatch.delenv("MY_KEY", raising=False)
        _update_env_var(env_path, "MY_KEY", "my-value")
        assert env_path.exists()
        assert "MY_KEY=my-value" in env_path.read_text()

    def test_replaces_existing_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from clarity_agent.setup.doctor import _update_env_var
        env_path = tmp_path / ".env"
        env_path.write_text("OTHER=foo\nMY_KEY=old-value\nANOTHER=bar\n")
        monkeypatch.delenv("MY_KEY", raising=False)
        _update_env_var(env_path, "MY_KEY", "new-value")
        content = env_path.read_text()
        assert "MY_KEY=new-value" in content
        assert "old-value" not in content
        assert "OTHER=foo" in content
        assert "ANOTHER=bar" in content

    def test_uncomments_commented_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from clarity_agent.setup.doctor import _update_env_var
        env_path = tmp_path / ".env"
        env_path.write_text("# MY_KEY=placeholder\n")
        monkeypatch.delenv("MY_KEY", raising=False)
        _update_env_var(env_path, "MY_KEY", "real-value")
        content = env_path.read_text()
        assert "MY_KEY=real-value" in content
        assert "# MY_KEY" not in content

    def test_sets_os_environ(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from clarity_agent.setup.doctor import _update_env_var
        env_path = tmp_path / ".env"
        monkeypatch.delenv("MY_KEY", raising=False)
        _update_env_var(env_path, "MY_KEY", "env-value")
        import os
        assert os.environ["MY_KEY"] == "env-value"


# ---------------------------------------------------------------------------
# _make_configure_provider_fn
# ---------------------------------------------------------------------------

class TestConfigureProviderFix:
    """Tests for the interactive provider configuration fix."""

    def test_writes_api_key_to_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from clarity_agent.setup.doctor import _make_configure_provider_fn
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        fix = _make_configure_provider_fn(tmp_path)
        # Simulate selecting provider 1 (anthropic) and entering a key.
        inputs = iter(["1", "sk-ant-test-key"])
        with patch("clarity_agent.setup.doctor._prompt", side_effect=lambda _: next(inputs)):
            result = fix()
        assert result is True
        env_content = (tmp_path / ".env").read_text()
        assert "ANTHROPIC_API_KEY=sk-ant-test-key" in env_content

    def test_cancel_returns_false(self, tmp_path: Path) -> None:
        from clarity_agent.setup.doctor import _make_configure_provider_fn
        fix = _make_configure_provider_fn(tmp_path)
        # Select cancel (last option = number of providers + 1)
        with patch("clarity_agent.setup.doctor._prompt", return_value="99"):
            result = fix()
        assert result is False


# ---------------------------------------------------------------------------
# _make_update_key_fn
# ---------------------------------------------------------------------------

class TestUpdateKeyFix:
    """Tests for the backend auth error key-update fix."""

    def test_updates_key_in_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from clarity_agent.setup.doctor import _make_update_key_fn
        (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=old-key\n")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        fix = _make_update_key_fn(tmp_path, "anthropic")
        with patch("clarity_agent.setup.doctor._prompt", return_value="sk-ant-new-key"):
            result = fix()
        assert result is True
        assert "sk-ant-new-key" in (tmp_path / ".env").read_text()

    def test_empty_key_returns_false(self, tmp_path: Path) -> None:
        from clarity_agent.setup.doctor import _make_update_key_fn
        fix = _make_update_key_fn(tmp_path, "anthropic")
        with patch("clarity_agent.setup.doctor._prompt", return_value=""):
            result = fix()
        assert result is False


# ---------------------------------------------------------------------------
# cli_main
# ---------------------------------------------------------------------------

class TestCliMain:
    """Smoke tests for the CLI entry point."""

    def test_all_pass_returns_normally(self, tmp_path: Path) -> None:
        from clarity_agent.setup.doctor import cli_main

        all_pass = [
            CheckResult(name="Test", status=Status.PASS, message="ok"),
        ]
        with patch("clarity_agent.get_agent_dir", return_value=tmp_path), \
             patch("clarity_agent.setup.doctor.run_all_checks", return_value=all_pass):
            cli_main()  # should return normally, no SystemExit

    def test_failure_exits_one(self, tmp_path: Path) -> None:
        from clarity_agent.setup.doctor import cli_main

        has_fail = [
            CheckResult(name="Test", status=Status.FAIL, message="bad"),
        ]
        with patch("clarity_agent.get_agent_dir", return_value=tmp_path), \
             patch("clarity_agent.setup.doctor.run_all_checks", return_value=has_fail), \
             patch("clarity_agent.setup.doctor._cli_confirm", return_value=False), \
             pytest.raises(SystemExit) as exc_info:
            cli_main()
        assert exc_info.value.code == 1
