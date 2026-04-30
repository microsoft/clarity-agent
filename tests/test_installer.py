"""Tests for clarity_agent.setup.installer."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from clarity_agent.setup.installer import (
    CLARITY_DIR,
    InstallMode,
    Outcome,
    StepResult,
    _parse_version,
    build_web_frontend,
    check_command_exists,
    check_node_version_preflight,
    check_python_version_preflight,
    clone_or_update,
    create_venv,
    create_wrapper,
    insert_agent_snippet,
    install_python_deps,
    resolve_clone_url,
    resolve_config,
    run_install,
    run_preflight,
    run_tests,
    setup_env_file,
    update_gitignore,
    validate_target,
)

# ---------------------------------------------------------------------------
# _parse_version
# ---------------------------------------------------------------------------

class TestParseVersion:
    def test_python_style(self) -> None:
        assert _parse_version("Python 3.12.1") == (3, 12)

    def test_node_style(self) -> None:
        assert _parse_version("v20.11.0") == (20, 11)

    def test_bare_version(self) -> None:
        assert _parse_version("3.10") == (3, 10)

    def test_no_version(self) -> None:
        assert _parse_version("no version here") == (0, 0)


# ---------------------------------------------------------------------------
# resolve_config
# ---------------------------------------------------------------------------

class TestResolveConfig:
    def test_embedded_config(self, tmp_path: Path) -> None:
        cfg = resolve_config(InstallMode.EMBEDDED, tmp_path, tmp_path / CLARITY_DIR)
        assert cfg.venv_dir == tmp_path / CLARITY_DIR / ".venv"
        assert "[cli,web," in cfg.pip_install_spec
        assert cfg.needs_gitignore is True
        assert cfg.run_tests is False

    def test_standalone_config(self, tmp_path: Path) -> None:
        cfg = resolve_config(InstallMode.STANDALONE, tmp_path, tmp_path)
        assert cfg.venv_dir == tmp_path / ".venv"
        assert cfg.pip_install_spec == ".[dev]"
        assert cfg.needs_gitignore is False
        assert cfg.run_tests is True


# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------

class TestPreflightChecks:
    def test_python_version_ok(self) -> None:
        cp = subprocess.CompletedProcess([], 0, stdout="Python 3.12.1\n", stderr="")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp), \
             patch("clarity_agent.setup.installer.shutil.which", return_value="/usr/bin/python3"):
            r = check_python_version_preflight()
        assert r.outcome == Outcome.OK
        assert "3.12" in r.message

    def test_python_version_too_old(self) -> None:
        cp = subprocess.CompletedProcess([], 0, stdout="Python 3.9.7\n", stderr="")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp), \
             patch("clarity_agent.setup.installer.shutil.which", return_value="/usr/bin/python3"):
            r = check_python_version_preflight()
        assert r.outcome == Outcome.FAIL
        assert "3.10" in r.message

    def test_python_not_found(self) -> None:
        with patch("clarity_agent.setup.installer.shutil.which", return_value=None):
            r = check_python_version_preflight()
        assert r.outcome == Outcome.FAIL

    def test_node_version_ok(self) -> None:
        cp = subprocess.CompletedProcess([], 0, stdout="v20.11.0\n", stderr="")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp), \
             patch("clarity_agent.setup.installer.shutil.which", return_value="/usr/bin/node"):
            r = check_node_version_preflight()
        assert r.outcome == Outcome.OK

    def test_node_version_too_old(self) -> None:
        cp = subprocess.CompletedProcess([], 0, stdout="v16.20.0\n", stderr="")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp), \
             patch("clarity_agent.setup.installer.shutil.which", return_value="/usr/bin/node"):
            r = check_node_version_preflight()
        assert r.outcome == Outcome.FAIL

    def test_node_not_found(self) -> None:
        with patch("clarity_agent.setup.installer.shutil.which", return_value=None):
            r = check_node_version_preflight()
        assert r.outcome == Outcome.FAIL

    def test_command_exists(self) -> None:
        with patch("clarity_agent.setup.installer.shutil.which", return_value="/usr/bin/git"):
            r = check_command_exists("git")
        assert r.outcome == Outcome.OK

    def test_command_missing(self) -> None:
        with patch("clarity_agent.setup.installer.shutil.which", return_value=None):
            r = check_command_exists("git")
        assert r.outcome == Outcome.FAIL

    def test_command_missing_with_hint(self) -> None:
        with patch("clarity_agent.setup.installer.shutil.which", return_value=None):
            r = check_command_exists("npm", "Install Node.js")
        assert r.outcome == Outcome.FAIL
        assert "Install Node.js" in r.message

    def test_run_preflight_returns_four_results(self) -> None:
        cp = subprocess.CompletedProcess([], 0, stdout="v20.0.0\n", stderr="")
        py_cp = subprocess.CompletedProcess([], 0, stdout="Python 3.12.0\n", stderr="")
        with patch("clarity_agent.setup.installer.shutil.which", return_value="/usr/bin/x"), \
             patch("clarity_agent.setup.installer.subprocess.run", side_effect=[py_cp, cp]):
            results = run_preflight()
        assert len(results) == 4

    def test_run_preflight_embedded_downgrades_node_failures(self) -> None:
        """In embedded mode, missing Node.js/npm become warnings, not failures."""
        with patch("clarity_agent.setup.installer.shutil.which", side_effect=lambda cmd: {
            "python3": "/usr/bin/python3", "python": "/usr/bin/python",
            "git": "/usr/bin/git",
        }.get(cmd)), \
             patch("clarity_agent.setup.installer.subprocess.run",
                   return_value=subprocess.CompletedProcess(
                       [], 0, stdout="Python 3.12.0\n", stderr="")):
            results = run_preflight(InstallMode.EMBEDDED)
        node_results = [r for r in results if "Node" in r.message or "npm" in r.message]
        assert all(r.outcome == Outcome.WARN for r in node_results)


# ---------------------------------------------------------------------------
# resolve_clone_url
# ---------------------------------------------------------------------------

class TestResolveCloneUrl:
    def test_ok(self, tmp_path: Path) -> None:
        url = "https://github.com/example/clarity-agent.git"
        cp = subprocess.CompletedProcess([], 0, stdout=f"  {url}  \n", stderr="")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp) as m:
            r = resolve_clone_url(tmp_path)
        assert r.outcome == Outcome.OK
        assert r.message == url
        m.assert_called_once()

    def test_nonzero_return(self, tmp_path: Path) -> None:
        cp = subprocess.CompletedProcess([], 1, stdout="", stderr="error")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
            r = resolve_clone_url(tmp_path)
        assert r.outcome == Outcome.FAIL

    def test_timeout(self, tmp_path: Path) -> None:
        with patch(
            "clarity_agent.setup.installer.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["git"], 10),
        ):
            r = resolve_clone_url(tmp_path)
        assert r.outcome == Outcome.FAIL

    def test_git_not_found(self, tmp_path: Path) -> None:
        with patch(
            "clarity_agent.setup.installer.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            r = resolve_clone_url(tmp_path)
        assert r.outcome == Outcome.FAIL


# ---------------------------------------------------------------------------
# validate_target
# ---------------------------------------------------------------------------

class TestValidateTarget:
    def test_ok(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        r = validate_target(tmp_path)
        assert r.outcome == Outcome.OK

    def test_missing_dir(self, tmp_path: Path) -> None:
        r = validate_target(tmp_path / "nope")
        assert r.outcome == Outcome.FAIL
        assert "does not exist" in r.message

    def test_not_a_repo(self, tmp_path: Path) -> None:
        r = validate_target(tmp_path)
        assert r.outcome == Outcome.FAIL
        assert "Not a git repository" in r.message


# ---------------------------------------------------------------------------
# clone_or_update
# ---------------------------------------------------------------------------

class TestCloneOrUpdate:
    def test_fresh_clone_ok(self, tmp_path: Path) -> None:
        cp = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
            r = clone_or_update(tmp_path, "https://example.com/repo.git")
        assert r.outcome == Outcome.OK
        assert "Cloned" in r.message

    def test_fresh_clone_fail(self, tmp_path: Path) -> None:
        cp = subprocess.CompletedProcess([], 1, stdout="", stderr="err")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
            r = clone_or_update(tmp_path, "https://example.com/repo.git")
        assert r.outcome == Outcome.FAIL

    def test_update_ff_ok(self, tmp_path: Path) -> None:
        dest = tmp_path / CLARITY_DIR
        (dest / ".git").mkdir(parents=True)
        cp = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
            r = clone_or_update(tmp_path, "https://example.com/repo.git")
        assert r.outcome == Outcome.OK
        assert "Updated" in r.message

    def test_update_ff_fail(self, tmp_path: Path) -> None:
        dest = tmp_path / CLARITY_DIR
        (dest / ".git").mkdir(parents=True)
        cp = subprocess.CompletedProcess([], 1, stdout="", stderr="diverged")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
            r = clone_or_update(tmp_path, "https://example.com/repo.git")
        assert r.outcome == Outcome.WARN
        assert "fast-forward" in r.message


# ---------------------------------------------------------------------------
# update_gitignore
# ---------------------------------------------------------------------------

class TestUpdateGitignore:
    def test_adds_all_entries(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()  # simulate git repo
        results = update_gitignore(tmp_path)
        assert len(results) == 5
        assert all(r.outcome == Outcome.OK for r in results)
        content = (tmp_path / ".gitignore").read_text()
        assert f"/{CLARITY_DIR}" in content
        assert "/clarity\n" in content
        assert "/clarity.ps1" in content
        assert "/clarity.bat" in content
        assert "/.clarity-protocol/transcripts/" in content

    def test_already_present(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()  # simulate git repo
        (tmp_path / ".gitignore").write_text(
            f"/{CLARITY_DIR}\n/clarity\n/clarity.ps1\n/clarity.bat\n/.clarity-protocol/transcripts/\n"
        )
        results = update_gitignore(tmp_path)
        assert len(results) == 5
        assert all(r.outcome == Outcome.OK for r in results)
        assert "already" in results[0].message

    def test_partial_present(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()  # simulate git repo
        (tmp_path / ".gitignore").write_text(f"/{CLARITY_DIR}\n")
        results = update_gitignore(tmp_path)
        assert len(results) == 5
        content = (tmp_path / ".gitignore").read_text()
        assert "/clarity\n" in content
        assert "/clarity.ps1" in content
        assert "/clarity.bat" in content

    def test_without_leading_slash(self, tmp_path: Path) -> None:
        """Entries without leading slash should also be recognized."""
        (tmp_path / ".gitignore").write_text(f"{CLARITY_DIR}\nclarity\n")
        results = update_gitignore(tmp_path)
        assert all(r.outcome == Outcome.OK for r in results)
        assert "already" in results[0].message

    def test_appends_newline_separator(self, tmp_path: Path) -> None:
        """A newline is added before the section if the file doesn't end with one."""
        (tmp_path / ".gitignore").write_text("node_modules")
        update_gitignore(tmp_path)
        content = (tmp_path / ".gitignore").read_text()
        assert content.startswith("node_modules\n")


# ---------------------------------------------------------------------------
# create_venv
# ---------------------------------------------------------------------------

class TestCreateVenv:
    def test_already_exists(self, tmp_path: Path) -> None:
        venv = tmp_path / ".venv"
        venv.mkdir()
        r = create_venv(venv)
        assert r.outcome == Outcome.OK
        assert "already exists" in r.message

    def test_created(self, tmp_path: Path) -> None:
        venv = tmp_path / ".venv"
        cp = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
            r = create_venv(venv)
        assert r.outcome == Outcome.OK
        assert "Created" in r.message

    def test_fail(self, tmp_path: Path) -> None:
        venv = tmp_path / ".venv"
        cp = subprocess.CompletedProcess([], 1, stdout="", stderr="err")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
            r = create_venv(venv)
        assert r.outcome == Outcome.FAIL


# ---------------------------------------------------------------------------
# install_python_deps
# ---------------------------------------------------------------------------

class TestInstallPythonDeps:
    def test_ok(self, tmp_path: Path) -> None:
        venv = tmp_path / ".venv"
        cp = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
            r = install_python_deps(tmp_path, venv, ".[dev]")
        assert r.outcome == Outcome.OK

    def test_pip_upgrade_fail(self, tmp_path: Path) -> None:
        venv = tmp_path / ".venv"
        cp = subprocess.CompletedProcess([], 1, stdout="", stderr="err")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
            r = install_python_deps(tmp_path, venv, ".[dev]")
        assert r.outcome == Outcome.FAIL
        assert "pip upgrade" in r.message

    def test_pip_install_fail(self, tmp_path: Path) -> None:
        """pip upgrade succeeds but pip install fails."""
        venv = tmp_path / ".venv"
        ok = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        fail = subprocess.CompletedProcess([], 1, stdout="", stderr="err")
        with patch(
            "clarity_agent.setup.installer.subprocess.run", side_effect=[ok, fail]
        ):
            r = install_python_deps(tmp_path, venv, ".[dev]")
        assert r.outcome == Outcome.FAIL
        assert "pip install" in r.message


# ---------------------------------------------------------------------------
# build_web_frontend
# ---------------------------------------------------------------------------

class TestBuildWebFrontend:
    def test_skip_no_package_json(self, tmp_path: Path) -> None:
        r = build_web_frontend(tmp_path)
        assert r.outcome == Outcome.SKIP

    def test_warn_no_npm(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        with patch("clarity_agent.setup.installer.shutil.which", return_value=None):
            r = build_web_frontend(tmp_path)
        assert r.outcome == Outcome.WARN
        assert "npm not found" in r.message

    def test_npm_install_fail(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        cp = subprocess.CompletedProcess([], 1, stdout="", stderr="err")
        with patch("clarity_agent.setup.installer.shutil.which", return_value="/usr/bin/npm"):
            with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
                r = build_web_frontend(tmp_path)
        assert r.outcome == Outcome.FAIL
        assert "npm install" in r.message

    def test_npm_build_fail(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        ok = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        fail = subprocess.CompletedProcess([], 1, stdout="", stderr="err")
        with patch("clarity_agent.setup.installer.shutil.which", return_value="/usr/bin/npm"):
            with patch(
                "clarity_agent.setup.installer.subprocess.run", side_effect=[ok, fail]
            ):
                r = build_web_frontend(tmp_path)
        assert r.outcome == Outcome.FAIL
        assert "npm run build" in r.message

    def test_ok(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        cp = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with patch("clarity_agent.setup.installer.shutil.which", return_value="/usr/bin/npm"):
            with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
                r = build_web_frontend(tmp_path)
        assert r.outcome == Outcome.OK


# ---------------------------------------------------------------------------
# setup_env_file
# ---------------------------------------------------------------------------

class TestSetupEnvFile:
    def test_already_exists(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("KEY=value")
        r = setup_env_file(tmp_path)
        assert r.outcome == Outcome.OK
        assert "already exists" in r.message

    def test_copies_sample(self, tmp_path: Path) -> None:
        (tmp_path / ".env.sample").write_text("# sample\nKEY=")
        r = setup_env_file(tmp_path)
        assert r.outcome == Outcome.WARN
        assert ".env.sample" in r.message
        assert (tmp_path / ".env").read_text() == "# sample\nKEY="

    def test_no_sample(self, tmp_path: Path) -> None:
        r = setup_env_file(tmp_path)
        assert r.outcome == Outcome.WARN
        assert "No .env.sample" in r.message


# ---------------------------------------------------------------------------
# create_wrapper
# ---------------------------------------------------------------------------

class TestCreateWrapper:
    def test_embedded_wrapper_uses_absolute_dir(self, tmp_path: Path) -> None:
        agent = tmp_path / CLARITY_DIR
        agent.mkdir()
        r = create_wrapper(tmp_path, agent, InstallMode.EMBEDDED)
        assert r.outcome == Outcome.OK

        if sys.platform == "win32":
            ps1 = tmp_path / "clarity.ps1"
            bat = tmp_path / "clarity.bat"
            assert ps1.exists()
            assert bat.exists()
            ps1_content = ps1.read_text()
            assert "python.exe" in ps1_content
            assert "clarity.py" in ps1_content
            assert str(agent) in ps1_content
        else:
            wrapper = tmp_path / "clarity"
            assert wrapper.exists()
            assert wrapper.stat().st_mode & 0o111  # executable
            content = wrapper.read_text()
            assert "#!/usr/bin/env bash" in content
            assert str(agent) in content
            assert "clarity.py" in content

    def test_standalone_wrapper_uses_relative_dir(self, tmp_path: Path) -> None:
        r = create_wrapper(tmp_path, tmp_path, InstallMode.STANDALONE)
        assert r.outcome == Outcome.OK

        if sys.platform == "win32":
            ps1_content = (tmp_path / "clarity.ps1").read_text()
            assert "python.exe" in ps1_content
            assert "clarity.py" in ps1_content
        else:
            content = (tmp_path / "clarity").read_text()
            assert '$(cd "$(dirname "$0")" && pwd)' in content
            # Should NOT contain an absolute path
            assert str(tmp_path) not in content


# ---------------------------------------------------------------------------
# run_tests
# ---------------------------------------------------------------------------

class TestRunTests:
    def test_pytest_pass(self, tmp_path: Path) -> None:
        venv = tmp_path / ".venv"
        cp = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
            results = run_tests(tmp_path, venv)
        assert len(results) == 1
        assert results[0].outcome == Outcome.OK
        assert "Python" in results[0].message

    def test_pytest_fail(self, tmp_path: Path) -> None:
        venv = tmp_path / ".venv"
        cp = subprocess.CompletedProcess([], 1, stdout="", stderr="")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
            results = run_tests(tmp_path, venv)
        assert results[0].outcome == Outcome.FAIL

    def test_vitest_runs_when_package_json_exists(self, tmp_path: Path) -> None:
        venv = tmp_path / ".venv"
        web = tmp_path / "web"
        web.mkdir()
        (web / "package.json").write_text("{}")
        cp = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
            results = run_tests(tmp_path, venv)
        assert len(results) == 2
        assert "Frontend" in results[1].message

    def test_vitest_skipped_when_no_package_json(self, tmp_path: Path) -> None:
        venv = tmp_path / ".venv"
        cp = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with patch("clarity_agent.setup.installer.subprocess.run", return_value=cp):
            results = run_tests(tmp_path, venv)
        assert len(results) == 1  # only pytest


# ---------------------------------------------------------------------------
# run_install (orchestrator)
# ---------------------------------------------------------------------------

class TestRunInstall:
    def test_aborts_on_preflight_fail(self, tmp_path: Path) -> None:
        with patch("clarity_agent.setup.installer.run_preflight") as mock_pf:
            mock_pf.return_value = [
                StepResult(Outcome.FAIL, "python3 not found"),
            ]
            results = run_install(InstallMode.EMBEDDED, tmp_path)
        assert any(r.outcome == Outcome.FAIL for r in results)
        # Should have stopped after preflight
        assert len(results) == 1

    def test_aborts_on_validate_fail(self, tmp_path: Path) -> None:
        ok_preflight = [StepResult(Outcome.OK, "ok")] * 4
        with patch("clarity_agent.setup.installer.run_preflight", return_value=ok_preflight):
            results = run_install(InstallMode.EMBEDDED, tmp_path / "nonexistent")
        assert results[-1].outcome == Outcome.FAIL
        assert "does not exist" in results[-1].message

    def test_embedded_calls_clone(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        ok_preflight = [StepResult(Outcome.OK, "ok")] * 4
        ok_cp = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        url = "https://example.com/repo.git"
        url_cp = subprocess.CompletedProcess(
            [], 0, stdout=f"{url}\n", stderr="",
        )
        with patch("clarity_agent.setup.installer.run_preflight", return_value=ok_preflight), \
             patch("clarity_agent.setup.installer.subprocess.run", side_effect=[
                 url_cp,   # resolve_clone_url
                 ok_cp,    # clone_or_update
                 ok_cp,    # create_venv
                 ok_cp,    # pip upgrade
                 ok_cp,    # pip install
                 ok_cp,    # npm install
                 ok_cp,    # npm run build
             ]), \
             patch("clarity_agent.setup.installer.shutil.which", return_value="/usr/bin/npm"):
            # Need .clarity-agent/web/package.json for build_web_frontend
            web = tmp_path / CLARITY_DIR / "web"
            web.mkdir(parents=True)
            (web / "package.json").write_text("{}")
            results = run_install(InstallMode.EMBEDDED, tmp_path, tmp_path)
        # setup_env_file returns WARN when no .env.sample exists, which is fine
        assert all(
            r.outcome in (Outcome.OK, Outcome.WARN) for r in results
        )

    def test_standalone_mode_skips_clone_and_gitignore(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        ok_preflight = [StepResult(Outcome.OK, "ok")] * 4
        ok_cp = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with patch("clarity_agent.setup.installer.run_preflight", return_value=ok_preflight), \
             patch("clarity_agent.setup.installer.subprocess.run", return_value=ok_cp), \
             patch("clarity_agent.setup.installer.shutil.which", return_value="/usr/bin/npm"):
            (tmp_path / "web" / "package.json").parent.mkdir(exist_ok=True)
            (tmp_path / "web" / "package.json").write_text("{}")
            results = run_install(
                InstallMode.STANDALONE, tmp_path, skip_tests=True,
            )
        messages = " ".join(r.message for r in results)
        # Should NOT contain clone/gitignore messages
        assert "Cloned" not in messages
        assert ".gitignore" not in messages


# ---------------------------------------------------------------------------
# insert_agent_snippet
# ---------------------------------------------------------------------------

class TestInsertAgentSnippet:
    """Snippet insertion into project agent config files.

    Now delegates to ``clarity_agent.setup.snippet`` — no need to copy
    the snippet template into a fake agent dir.
    """

    def test_creates_claude_md(self, tmp_path: Path) -> None:
        agent = tmp_path / CLARITY_DIR
        agent.mkdir()
        r = insert_agent_snippet(tmp_path, agent)
        assert r.outcome == Outcome.OK
        assert "Created" in r.message
        target = tmp_path / "AGENTS.md"
        assert target.exists()
        assert "<!-- clarity-begin -->" in target.read_text()

    def test_appends_to_existing_agents_md(self, tmp_path: Path) -> None:
        agent = tmp_path / CLARITY_DIR
        agent.mkdir()
        (tmp_path / "AGENTS.md").write_text("# My agents\n")
        r = insert_agent_snippet(tmp_path, agent)
        assert r.outcome == Outcome.OK
        assert "appended" in r.message.lower()
        content = (tmp_path / "AGENTS.md").read_text()
        assert "# My agents" in content
        assert "<!-- clarity-begin -->" in content

    def test_idempotent(self, tmp_path: Path) -> None:
        agent = tmp_path / CLARITY_DIR
        agent.mkdir()
        insert_agent_snippet(tmp_path, agent)
        first = (tmp_path / "AGENTS.md").read_text()
        r = insert_agent_snippet(tmp_path, agent)
        assert r.outcome == Outcome.OK
        assert "already" in r.message.lower()
        assert (tmp_path / "AGENTS.md").read_text() == first

    def test_substitutes_processes_dir(self, tmp_path: Path) -> None:
        agent = tmp_path / CLARITY_DIR
        agent.mkdir()
        insert_agent_snippet(tmp_path, agent)
        content = (tmp_path / "AGENTS.md").read_text()
        assert f"{CLARITY_DIR}/processes/clarity-agent.md" in content
        assert "{{PROCESSES_DIR}}" not in content

    def test_skip_when_no_template(self, tmp_path: Path) -> None:
        fake = tmp_path / "nonexistent" / "snippet.md"
        with patch("clarity_agent.setup.snippet.snippet_path", return_value=fake):
            r = insert_agent_snippet(tmp_path, tmp_path / CLARITY_DIR)
        assert r.outcome == Outcome.SKIP

    def test_prefers_claude_md_over_agents_md(self, tmp_path: Path) -> None:
        agent = tmp_path / CLARITY_DIR
        agent.mkdir()
        (tmp_path / "CLAUDE.md").write_text("# Claude\n")
        (tmp_path / "AGENTS.md").write_text("# Agents\n")
        insert_agent_snippet(tmp_path, agent)
        assert "<!-- clarity-begin -->" in (tmp_path / "CLAUDE.md").read_text()
        assert "<!-- clarity-begin -->" not in (tmp_path / "AGENTS.md").read_text()
