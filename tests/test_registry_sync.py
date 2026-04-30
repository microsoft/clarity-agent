"""Cross-check that the codebase's decoupled registries stay in sync.

The clarity-agent has several registries that each enumerate protocol documents
independently: the packet status dependency graph, the init templates, the packet
renderer sources, and the test fixtures. When a new document is added, all of
these need updating. This test file catches the "forgot to update X" problem
at test time.

See UPDATE-CHECKLIST.md for the full list of what needs updating (including
documentation and process guides that tests can't check).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clarity_agent.llm.config import _DEFAULT_PROCESS_TIERS, _PROVIDERS
from clarity_agent.packet import (
    _CANONICAL_PARTS,
    _SOURCES,
    _VIEWS,
    DirectorySource,
    SingleFileSource,
)
from clarity_agent.process_registry import PROCESS_METADATA
from clarity_agent.protocol.initialize import DEFAULT_CONFIG, TEMPLATES
from clarity_agent.protocol.packet_status import (
    DEFAULT_DEPENDENCIES,
    DOCUMENT_PROCESS,
    TEMPLATE_MARKERS,
    WALK_ORDER,
)

# ---------------------------------------------------------------------------
# Packet status system internal consistency
# ---------------------------------------------------------------------------

class TestPacketStatusRegistries:
    """DEFAULT_DEPENDENCIES, WALK_ORDER, and DOCUMENT_PROCESS must agree."""

    def test_walk_order_matches_dependencies(self) -> None:
        """Every document in DEFAULT_DEPENDENCIES appears in WALK_ORDER and vice versa."""
        dep_docs = set(DEFAULT_DEPENDENCIES.keys())
        walk_docs = set(WALK_ORDER)
        assert dep_docs == walk_docs, (
            f"Mismatch between DEFAULT_DEPENDENCIES and WALK_ORDER.\n"
            f"  In dependencies but not walk order: {dep_docs - walk_docs}\n"
            f"  In walk order but not dependencies: {walk_docs - dep_docs}"
        )

    def test_document_process_matches_dependencies(self) -> None:
        """Every document in DEFAULT_DEPENDENCIES has a DOCUMENT_PROCESS entry and vice versa."""
        dep_docs = set(DEFAULT_DEPENDENCIES.keys())
        proc_docs = set(DOCUMENT_PROCESS.keys())
        assert dep_docs == proc_docs, (
            f"Mismatch between DEFAULT_DEPENDENCIES and DOCUMENT_PROCESS.\n"
            f"  In dependencies but not process map: {dep_docs - proc_docs}\n"
            f"  In process map but not dependencies: {proc_docs - dep_docs}"
        )

    def test_dependency_targets_are_known_documents(self) -> None:
        """Every document referenced as a dependency must itself be a tracked document."""
        known = set(DEFAULT_DEPENDENCIES.keys())
        for doc, deps in DEFAULT_DEPENDENCIES.items():
            for dep in deps:
                assert dep in known, (
                    f"{doc} depends on {dep}, but {dep} is not in DEFAULT_DEPENDENCIES"
                )

    def test_walk_order_has_no_duplicates(self) -> None:
        assert len(WALK_ORDER) == len(set(WALK_ORDER)), "WALK_ORDER contains duplicates"


# ---------------------------------------------------------------------------
# Templates ↔ packet status graph
# ---------------------------------------------------------------------------

class TestTemplatesVsPacketStatus:
    """Every tracked document should have a template, and templates should
    generally be tracked (with documented exceptions)."""

    # decisions/decisions.md has a template but is deliberately excluded from
    # the packet status graph — decisions are tracked via decisionState in config.json.
    # notes.md is cross-cutting shared memory (guiding principles + tagged items)
    # that every phase reads/writes. It has no upstream dependencies and no owning
    # process, so staleness tracking doesn't apply.
    # observations.md is a log of interesting footnotes from failure analysis and
    # other processes — it has no upstream dependencies or owning process.
    # goal/resolved-questions.md is a historical record of resolved open questions —
    # it's an append-only log with no downstream dependents.
    KNOWN_TEMPLATE_ONLY = {"decisions/decisions.md", "notes.md", "observations.md", "goal/resolved-questions.md"}

    def test_tracked_documents_have_templates(self) -> None:
        """Every document in DEFAULT_DEPENDENCIES should have an init template."""
        dep_docs = set(DEFAULT_DEPENDENCIES.keys())
        template_docs = set(TEMPLATES.keys())
        missing = dep_docs - template_docs
        assert not missing, (
            f"Documents in DEFAULT_DEPENDENCIES without init templates: {missing}\n"
            f"Add templates in init_protocol.py TEMPLATES dict."
        )

    def test_templates_contain_markers(self) -> None:
        """Every template should contain at least one TEMPLATE_MARKER so
        is_template() correctly identifies unmodified templates."""
        missing = [
            doc_path for doc_path, content in TEMPLATES.items()
            if not any(marker in content for marker in TEMPLATE_MARKERS)
        ]
        assert not missing, (
            f"Templates without any TEMPLATE_MARKER: {missing}\n"
            f"Either add a known marker string to the template content or add "
            f"a new marker to TEMPLATE_MARKERS in packet_status.py."
        )

    def test_templates_are_tracked_or_exempted(self) -> None:
        """Every template should correspond to a tracked document (or be in the known exceptions)."""
        dep_docs = set(DEFAULT_DEPENDENCIES.keys())
        template_docs = set(TEMPLATES.keys())
        untracked = template_docs - dep_docs - self.KNOWN_TEMPLATE_ONLY
        assert not untracked, (
            f"Templates without packet status tracking: {untracked}\n"
            f"Either add to DEFAULT_DEPENDENCIES or add to KNOWN_TEMPLATE_ONLY "
            f"in this test with a comment explaining why."
        )


# ---------------------------------------------------------------------------
# Packet sources ↔ templates
# ---------------------------------------------------------------------------

class TestPacketVsTemplates:
    """Every protocol document should be covered by a packet source."""

    # summary.md is not a packet source — it's handled specially as the
    # document title and preamble via _read_summary() in the packet module.
    KNOWN_NON_SOURCE = {"summary.md"}

    def test_every_template_has_packet_source(self) -> None:
        """Every template document should be reachable from a registered packet source."""
        # Collect all document paths covered by packet sources.
        covered_paths: set[str] = set()
        for source in _SOURCES.values():
            if isinstance(source, SingleFileSource):
                covered_paths.add(source.path)
            elif isinstance(source, DirectorySource):
                covered_paths.add(f"{source.directory}/{source.index_file}")

        template_docs = set(TEMPLATES.keys())
        missing = template_docs - covered_paths - self.KNOWN_NON_SOURCE
        assert not missing, (
            f"Template documents without packet sources: {missing}\n"
            f"Register sources in packet/__init__.py, or add to "
            f"KNOWN_NON_SOURCE with a comment explaining why."
        )

    def test_canonical_parts_reference_registered_sources(self) -> None:
        """Every source name in _CANONICAL_PARTS must be a registered source."""
        registered = set(_SOURCES.keys())
        for part_title, source_names in _CANONICAL_PARTS:
            for name in source_names:
                assert name in registered, (
                    f"_CANONICAL_PARTS '{part_title}' references '{name}', "
                    f"but it's not a registered source. "
                    f"Registered: {sorted(registered)}"
                )

    def test_all_sources_in_canonical_parts(self) -> None:
        """Every registered source should appear in _CANONICAL_PARTS
        (otherwise it silently goes to 'Additional')."""
        in_parts: set[str] = set()
        for _, source_names in _CANONICAL_PARTS:
            in_parts.update(source_names)

        registered = set(_SOURCES.keys())
        orphaned = registered - in_parts
        assert not orphaned, (
            f"Registered sources not in _CANONICAL_PARTS: {orphaned}\n"
            f"These would silently appear in an 'Additional' group. "
            f"Add them to the appropriate part in _CANONICAL_PARTS."
        )


# ---------------------------------------------------------------------------
# Test fixture coverage
# ---------------------------------------------------------------------------

class TestFixtureCoverage:
    """The protocol_dir fixture must cover all tracked documents."""

    def test_fixture_covers_tracked_documents(self) -> None:
        """The conftest.py protocol_dir fixture should have content for every
        document in DEFAULT_DEPENDENCIES, so packet status tests see real content
        rather than templates."""
        # Import the fixture's doc dict indirectly by checking what
        # protocol_dir creates. We can't easily call the fixture outside
        # pytest, so we check the source directly.
        import inspect

        import tests.conftest as conftest_module

        # Get the fixture function source and extract the docs dict keys.
        source = inspect.getsource(conftest_module.protocol_dir)

        dep_docs = set(DEFAULT_DEPENDENCIES.keys())
        missing = []
        for doc in dep_docs:
            if f'"{doc}"' not in source:
                missing.append(doc)

        assert not missing, (
            f"protocol_dir fixture in conftest.py is missing content for: {missing}\n"
            f"Add entries to the docs dict so packet status tests work correctly."
        )


# ---------------------------------------------------------------------------
# Thinker files ↔ config & docs
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
THINKERS_DIR = REPO_ROOT / "thinkers"
PROCESSES_DIR = REPO_ROOT / "processes"
README_DEV = REPO_ROOT / "CONTRIBUTING.md"


class TestThinkerSync:
    """Every thinker .md file in thinkers/ must be documented in
    CONTRIBUTING.md and not accidentally disabled in DEFAULT_CONFIG."""

    def _thinker_files(self) -> set[str]:
        """Return stem names (e.g. 'security-thinker') of all .md files in thinkers/."""
        if not THINKERS_DIR.is_dir():
            return set()
        return {p.stem for p in THINKERS_DIR.glob("*.md")}

    def test_default_config_has_no_enabled_list(self) -> None:
        """DEFAULT_CONFIG should not have an 'enabled' whitelist — all
        discovered thinkers run unless explicitly disabled."""
        thinker_config: dict = DEFAULT_CONFIG["thinkers"]  # type: ignore[index]
        assert "enabled" not in thinker_config, (
            "DEFAULT_CONFIG['thinkers'] should not have an 'enabled' key. "
            "All discovered thinkers run by default; use 'disabled' to exclude."
        )

    def test_thinker_files_in_readme(self) -> None:
        """Every thinker file should be mentioned in CONTRIBUTING.md."""
        thinker_files = self._thinker_files()
        if not thinker_files or not README_DEV.exists():
            return
        readme_text = README_DEV.read_text()
        missing = [
            name for name in sorted(thinker_files)
            if f"{name}.md" not in readme_text
        ]
        assert not missing, (
            f"Thinker files not mentioned in CONTRIBUTING.md: {missing}\n"
            f"Add a row to the thinker guides table in CONTRIBUTING.md."
        )


# ---------------------------------------------------------------------------
# Process files ↔ config & docs
# ---------------------------------------------------------------------------

class TestProcessSync:
    """Every process .md file must be registered in _DEFAULT_PROCESS_TIERS
    and documented in processes/README.md."""

    # Files in processes/ that are not invocable processes.
    KNOWN_NON_PROCESS = {"README.md", "failure-reasoning-guidelines.md"}

    def _process_files(self) -> set[str]:
        """Return stem names of all process .md files."""
        if not PROCESSES_DIR.is_dir():
            return set()
        return {
            p.stem for p in PROCESSES_DIR.glob("*.md")
            if p.name not in self.KNOWN_NON_PROCESS
        }

    def test_process_files_in_registry(self) -> None:
        """Every process file should have an entry in PROCESS_METADATA."""
        process_files = self._process_files()
        missing = process_files - set(PROCESS_METADATA.keys())
        assert not missing, (
            f"Process files without entry in PROCESS_METADATA: {missing}\n"
            f"Add them to PROCESS_METADATA in process_registry.py."
        )

    def test_registry_has_process_files(self) -> None:
        """Every name in PROCESS_METADATA should have a process file."""
        process_files = self._process_files()
        missing = set(PROCESS_METADATA.keys()) - process_files
        assert not missing, (
            f"Registry entries without process files: {missing}\n"
            f"Either create the process file or remove the entry from "
            f"PROCESS_METADATA."
        )

    def test_process_files_in_default_tiers(self) -> None:
        """Every process file should have a tier in _DEFAULT_PROCESS_TIERS."""
        process_files = self._process_files()
        missing = process_files - set(_DEFAULT_PROCESS_TIERS.keys())
        assert not missing, (
            f"Process files without tier in _DEFAULT_PROCESS_TIERS: {missing}\n"
            f"Add them to PROCESS_METADATA in process_registry.py."
        )

    def test_tiers_have_process_files(self) -> None:
        """Every name in _DEFAULT_PROCESS_TIERS should have a process file."""
        process_files = self._process_files()
        missing = set(_DEFAULT_PROCESS_TIERS.keys()) - process_files
        assert not missing, (
            f"Tier entries without process files: {missing}\n"
            f"Either create the process file or remove the entry from "
            f"_DEFAULT_PROCESS_TIERS."
        )

    def test_document_process_values_are_real_processes(self) -> None:
        """Every process name in DOCUMENT_PROCESS should be an actual process file."""
        process_files = self._process_files()
        # Filter out None values (documents with no owning process).
        process_names = {v for v in DOCUMENT_PROCESS.values() if v is not None}
        missing = process_names - process_files
        assert not missing, (
            f"DOCUMENT_PROCESS references non-existent processes: {missing}\n"
            f"Either create the process file or fix the mapping in "
            f"packet_status.py."
        )

    def test_process_files_in_readme(self) -> None:
        """Every process file should be mentioned in processes/README.md."""
        process_files = self._process_files()
        readme_path = PROCESSES_DIR / "README.md"
        if not process_files or not readme_path.exists():
            return
        readme_text = readme_path.read_text()
        missing = [
            name for name in sorted(process_files)
            if f"{name}.md" not in readme_text
        ]
        assert not missing, (
            f"Process files not mentioned in processes/README.md: {missing}\n"
            f"Add them to the process list in processes/README.md."
        )


# ---------------------------------------------------------------------------
# LLM provider sync
# ---------------------------------------------------------------------------

class TestProviderSync:
    """Every provider in _PROVIDERS must have factory branches."""

    # Providers where the claude_sdk auth mode uses ChatBackend directly
    # (no LLMClient).  This is an auth mode, not a provider, so the
    # create_client check below handles it separately.
    CHAT_ONLY_PROVIDERS: set[str] = set()

    def test_providers_have_tier_defaults(self) -> None:
        """Every provider should have a branch in get_provider_tier_defaults()."""
        import inspect

        from clarity_agent.llm.factory import get_provider_tier_defaults
        source = inspect.getsource(get_provider_tier_defaults)
        missing = [
            name for name in _PROVIDERS
            if f'"{name}"' not in source
        ]
        assert not missing, (
            f"Providers without branch in get_provider_tier_defaults(): {missing}\n"
            f"Add a branch in llm/factory.py."
        )

    def test_providers_have_chat_backend(self) -> None:
        """Every provider should be reachable via create_chat_backend().

        Non-SDK providers are handled generically through create_client(),
        so we check that each provider appears in either factory function.
        """
        import inspect

        from clarity_agent.llm.factory import create_chat_backend, create_client
        cb_source = inspect.getsource(create_chat_backend)
        cl_source = inspect.getsource(create_client)
        missing = [
            name for name in _PROVIDERS
            if f'"{name}"' not in cb_source and f'"{name}"' not in cl_source
        ]
        assert not missing, (
            f"Providers without branch in create_chat_backend() or create_client(): {missing}\n"
            f"Add a branch in llm/factory.py."
        )

    def test_providers_have_client(self) -> None:
        """Every non-chat-only provider should have a branch in create_client()."""
        import inspect

        from clarity_agent.llm.factory import create_client
        source = inspect.getsource(create_client)
        missing = [
            name for name in _PROVIDERS
            if name not in self.CHAT_ONLY_PROVIDERS
            and f'"{name}"' not in source
        ]
        assert not missing, (
            f"Providers without branch in create_client(): {missing}\n"
            f"Add a branch in llm/factory.py, or add to CHAT_ONLY_PROVIDERS "
            f"in this test if the provider only supports ChatBackend."
        )


# ---------------------------------------------------------------------------
# Packet views ↔ registered sources
# ---------------------------------------------------------------------------

class TestPacketViewSync:
    """Packet view definitions must reference registered sources."""

    def test_view_sources_are_registered(self) -> None:
        """Every source ID in a view's parts must be a registered source."""
        registered = set(_SOURCES.keys())
        for view in _VIEWS.values():
            for part_title, source_ids in view.parts:
                for sid in source_ids:
                    assert sid in registered, (
                        f"View '{view.id}' part '{part_title}' references "
                        f"source '{sid}', which is not registered. "
                        f"Registered: {sorted(registered)}"
                    )

    def test_complete_view_covers_all_sources(self) -> None:
        """The 'complete' view should cover every registered source."""
        complete = _VIEWS["complete"]
        view_sources = {sid for _, sids in complete.parts for sid in sids}
        registered = set(_SOURCES.keys())
        missing = registered - view_sources
        assert not missing, (
            f"Registered sources not in 'complete' view: {missing}\n"
            f"Add them to the 'complete' view's parts."
        )


# ---------------------------------------------------------------------------
# Data dir resolution: Python ↔ Rust
# ---------------------------------------------------------------------------

class TestDataDirSync:
    """The Rust and Python data-dir resolution must agree.

    ``projects_json_path()`` in ``src-tauri/src/main.rs`` and
    ``clarity_data_dir()`` in ``src/clarity_agent/app_paths.py`` both
    implement the same 4-step resolution:

    1. ``CLARITY_DATA_DIR`` env var
    2. macOS: ``~/Library/Application Support/Clarity/``
    3. Windows: ``%LOCALAPPDATA%\\Clarity\\data\\``
    4. Fallback: ``~/.clarity/``

    These tests verify both sides follow this contract.
    """

    RUST_SOURCE = Path(__file__).parent.parent / "src-tauri" / "src" / "main.rs"

    # The ordered resolution steps that must appear in the Rust source.
    RESOLUTION_STEPS = [
        # Step 1: env var
        "CLARITY_DATA_DIR",
        # Step 2: macOS — ~/Library/Application Support/Clarity/
        "Application Support",
        # Step 3: Windows
        "LOCALAPPDATA",
        # Step 4: fallback
        ".clarity",
    ]

    def test_rust_source_contains_resolution_steps_in_order(self) -> None:
        """The Rust projects_json_path() must check the same sources in order."""
        if not self.RUST_SOURCE.exists():
            pytest.skip("src-tauri/src/main.rs not found (not in repo root?)")

        source = self.RUST_SOURCE.read_text()

        # Extract the function body.
        fn_start = source.find("fn projects_json_path()")
        assert fn_start != -1, "projects_json_path() not found in main.rs"
        fn_body = source[fn_start:]

        # Each step must appear, and in order.
        last_pos = 0
        for step in self.RESOLUTION_STEPS:
            pos = fn_body.find(step, last_pos)
            assert pos != -1, (
                f"Resolution step {step!r} not found in projects_json_path() "
                f"after position {last_pos}.\n"
                f"The Rust and Python data-dir resolution must follow the same "
                f"4-step order. See clarity_agent.app_paths.clarity_data_dir()."
            )
            last_pos = pos

    def test_rust_parses_wrapper_format(self) -> None:
        """The Rust reader must handle the {projects: [...]} wrapper format."""
        if not self.RUST_SOURCE.exists():
            pytest.skip("src-tauri/src/main.rs not found")

        source = self.RUST_SOURCE.read_text()
        # The Rust code should define a ProjectsFile struct with a projects field.
        assert "ProjectsFile" in source, (
            "Rust source must define a ProjectsFile struct to parse the "
            "wrapper format used by Python's ProjectRegistry."
        )
        assert '"projects"' in source or "projects:" in source, (
            "Rust source must reference the 'projects' key from the wrapper format."
        )

    def test_python_clarity_data_dir_respects_env_var(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """CLARITY_DATA_DIR env var takes priority in Python."""
        from clarity_agent.app_paths import clarity_data_dir

        monkeypatch.setenv("CLARITY_DATA_DIR", str(tmp_path))
        assert clarity_data_dir() == tmp_path

    def test_python_clarity_data_dir_fallback(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without env var, Python uses the platform-specific default."""
        import sys

        from clarity_agent.app_paths import clarity_data_dir

        monkeypatch.delenv("CLARITY_DATA_DIR", raising=False)
        result = clarity_data_dir()
        if sys.platform == "darwin":
            assert result == Path.home() / "Library" / "Application Support" / "Clarity"
        elif sys.platform == "win32":
            assert "Clarity" in str(result)
        else:
            assert result == Path.home() / ".clarity"
