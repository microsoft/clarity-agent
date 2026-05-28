"""Tests for the clarity_agent.projects module."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from clarity_agent.projects import ProjectEntry, ProjectRegistry


@pytest.fixture
def registry(tmp_path: Path) -> ProjectRegistry:
    """A registry backed by a temp file."""
    return ProjectRegistry(path=tmp_path / "projects.json")


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """A directory that looks like a clarity project."""
    d = tmp_path / "my-project"
    d.mkdir()
    (d / ".clarity-protocol").mkdir()
    return d


class TestProjectEntry:
    def test_refresh_detects_protocol(self, sample_project: Path) -> None:
        entry = ProjectEntry(name="test", path=str(sample_project))
        assert not entry.has_protocol
        entry.refresh()
        assert entry.has_protocol

    def test_refresh_no_protocol(self, tmp_path: Path) -> None:
        d = tmp_path / "bare"
        d.mkdir()
        entry = ProjectEntry(name="bare", path=str(d))
        entry.refresh()
        assert not entry.has_protocol


class TestRegistryBasics:
    def test_empty_list(self, registry: ProjectRegistry) -> None:
        assert registry.list() == []

    def test_add_and_list(
        self, registry: ProjectRegistry, sample_project: Path,
    ) -> None:
        entry = registry.add("proj", sample_project)
        assert entry.name == "proj"
        assert entry.path == str(sample_project.resolve())
        assert entry.has_protocol is True

        entries = registry.list()
        assert len(entries) == 1
        assert entries[0].name == "proj"

    def test_add_duplicate_name_at_different_paths_both_register(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        # Path is the registry's primary key — display ``name`` is
        # not a uniqueness constraint.  Two genuinely-different
        # projects in different directories can share a display
        # label; the entries are still distinguishable by ``id``.
        d1 = tmp_path / "a"
        d1.mkdir()
        d2 = tmp_path / "b"
        d2.mkdir()
        e1 = registry.add("same", d1)
        e2 = registry.add("same", d2)
        assert e1.id != e2.id
        assert {e.path for e in registry.list()} == {str(d1), str(d2)}

    def test_add_same_path_is_idempotent(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        # Re-adding the same path returns the existing entry — no
        # duplicate row, no exception.  This is what makes "open
        # project" safe to call against an already-registered dir.
        d = tmp_path / "proj"
        d.mkdir()
        first = registry.add("proj", d)
        second = registry.add("proj", d)
        assert first.id == second.id
        assert len(registry.list()) == 1

    def test_add_same_path_different_name_renames(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        # User re-opening the same path with a new label: relabel
        # the existing entry rather than creating a duplicate.
        d = tmp_path / "proj"
        d.mkdir()
        registry.add("old-label", d)
        updated = registry.add("new-label", d)
        assert updated.name == "new-label"
        assert len(registry.list()) == 1

    def test_remove(
        self, registry: ProjectRegistry, sample_project: Path,
    ) -> None:
        registry.add("proj", sample_project)
        registry.remove("proj")
        assert registry.list() == []

    def test_remove_nonexistent_is_silent(
        self, registry: ProjectRegistry,
    ) -> None:
        registry.remove("ghost")  # should not raise


class TestRegistryLookup:
    def test_get_by_name(
        self, registry: ProjectRegistry, sample_project: Path,
    ) -> None:
        registry.add("proj", sample_project)
        proj = registry.get("proj")
        assert proj is not None
        assert proj.name == "proj"
        assert registry.get("nope") is None

    def test_find_by_path(
        self, registry: ProjectRegistry, sample_project: Path,
    ) -> None:
        registry.add("proj", sample_project)
        found = registry.find_by_path(sample_project)
        assert found is not None
        assert found.name == "proj"
        assert registry.find_by_path("/nonexistent") is None


class TestRegistryUpdate:
    def test_update_fields(
        self, registry: ProjectRegistry, sample_project: Path,
    ) -> None:
        registry.add("proj", sample_project)
        updated = registry.update("proj", has_protocol=False)
        assert updated.has_protocol is False
        # Persisted
        loaded = registry.get("proj")
        assert loaded is not None
        assert loaded.has_protocol is False

    def test_update_nonexistent_raises(
        self, registry: ProjectRegistry,
    ) -> None:
        with pytest.raises(KeyError, match="not found"):
            registry.update("ghost", has_protocol=True)

    def test_update_bad_field_raises(
        self, registry: ProjectRegistry, sample_project: Path,
    ) -> None:
        registry.add("proj", sample_project)
        with pytest.raises(AttributeError, match="no field"):
            registry.update("proj", bogus=42)

    def test_touch(
        self, registry: ProjectRegistry, sample_project: Path,
    ) -> None:
        registry.add("proj", sample_project)
        before = registry.get("proj")
        assert before is not None
        old_time = before.last_opened
        time.sleep(0.01)
        registry.touch("proj")
        after = registry.get("proj")
        assert after is not None
        assert after.last_opened > old_time


class TestRegistryOrdering:
    def test_list_sorted_by_last_opened(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        for name in ("old", "mid", "new"):
            d = tmp_path / name
            d.mkdir()
            registry.add(name, d)
            time.sleep(0.01)

        entries = registry.list()
        assert [e.name for e in entries] == ["new", "mid", "old"]

    def test_touch_reorders(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        for name in ("a", "b", "c"):
            d = tmp_path / name
            d.mkdir()
            registry.add(name, d)
            time.sleep(0.01)

        registry.touch("a")
        entries = registry.list()
        assert entries[0].name == "a"


class TestDiscover:
    def test_discover_finds_subdirectories(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        base = tmp_path / "Clarity Projects"
        base.mkdir()
        (base / "alpha").mkdir()
        (base / "beta").mkdir()
        (base / "beta" / ".clarity-protocol").mkdir()
        (base / ".hidden").mkdir()  # should be skipped

        added = registry.discover(base)
        assert len(added) == 2
        names = {e.name for e in added}
        assert names == {"alpha", "beta"}

        # beta has protocol
        beta = registry.get("beta")
        assert beta is not None
        assert beta.has_protocol is True

    def test_discover_skips_already_registered(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        base = tmp_path / "Clarity Projects"
        base.mkdir()
        d = base / "existing"
        d.mkdir()
        registry.add("existing", d)

        added = registry.discover(base)
        assert len(added) == 0

    def test_discover_nonexistent_base(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        assert registry.discover(tmp_path / "nope") == []

    def test_discover_deduplicates_names(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        # Register a project with name "dup" at a different path.
        other = tmp_path / "other"
        other.mkdir()
        registry.add("dup", other)

        base = tmp_path / "Clarity Projects"
        base.mkdir()
        (base / "dup").mkdir()

        added = registry.discover(base)
        assert len(added) == 1
        assert added[0].name == "dup-2"


class TestPersistence:
    def test_survives_reload(self, tmp_path: Path) -> None:
        path = tmp_path / "projects.json"
        d = tmp_path / "proj"
        d.mkdir()

        r1 = ProjectRegistry(path=path)
        r1.add("proj", d)

        r2 = ProjectRegistry(path=path)
        entries = r2.list(refresh=False)
        assert len(entries) == 1
        assert entries[0].name == "proj"

    def test_corrupt_file_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "projects.json"
        path.write_text("not json!", encoding="utf-8")

        r = ProjectRegistry(path=path)
        assert r.list(refresh=False) == []
