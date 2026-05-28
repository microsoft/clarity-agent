"""Tests for the clarity_agent.projects module.

The registry is path-keyed with an id derived from the path; the
action verbs (``get``, ``update``, ``touch``, ``remove``) all take
that id.  Name lookups go through :meth:`find_by_name`, which
returns a list because names aren't unique.  These tests pin all
of that down so future drifts get caught.
"""

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


# ---------------------------------------------------------------------------
# ProjectEntry — refresh semantics
# ---------------------------------------------------------------------------


class TestProjectEntry:
    def test_refresh_detects_protocol(self, sample_project: Path) -> None:
        entry = ProjectEntry(name="test", path=str(sample_project))
        assert not entry.has_protocol
        assert entry.refresh() is True
        assert entry.has_protocol

    def test_refresh_no_protocol(self, tmp_path: Path) -> None:
        d = tmp_path / "bare"
        d.mkdir()
        entry = ProjectEntry(name="bare", path=str(d))
        assert entry.refresh() is True
        assert not entry.has_protocol

    def test_refresh_returns_false_when_path_gone(
        self, tmp_path: Path,
    ) -> None:
        # The refresh-returns-bool contract is what lets the
        # registry filter vanished entries on read.
        d = tmp_path / "transient"
        d.mkdir()
        entry = ProjectEntry(name="t", path=str(d))
        assert entry.refresh() is True
        d.rmdir()
        assert entry.refresh() is False


# ---------------------------------------------------------------------------
# add() — path-keyed, default name from basename, idempotent reopens
# ---------------------------------------------------------------------------


class TestAdd:
    def test_basic_add(
        self, registry: ProjectRegistry, sample_project: Path,
    ) -> None:
        entry = registry.add(sample_project, name="proj")
        assert entry.name == "proj"
        assert entry.path == str(sample_project.resolve())
        assert entry.has_protocol is True

        entries = registry.list()
        assert len(entries) == 1
        assert entries[0].id == entry.id

    def test_default_name_from_basename(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        # Without an explicit name=, the entry's display label is
        # the basename of the path the caller supplied — the natural
        # default for menu-driven "Open Project…" flows that have
        # nothing better to suggest.
        d = tmp_path / "my-thing"
        d.mkdir()
        entry = registry.add(d)
        assert entry.name == "my-thing"

    def test_default_name_from_unresolved_basename(
        self, tmp_path: Path,
    ) -> None:
        # When the caller hands us a symlinked path, the default
        # name should come from the symlink itself (what they
        # picked), not from the resolved target's basename.
        target = tmp_path / "actual-name"
        target.mkdir()
        link = tmp_path / "user-picked-name"
        link.symlink_to(target)

        reg = ProjectRegistry(path=tmp_path / "projects.json")
        entry = reg.add(link)
        # The user picked "user-picked-name" — that's what should
        # appear in the project list, not "actual-name".
        assert entry.name == "user-picked-name"
        # But the stored path is resolved so identity is canonical.
        assert entry.path == str(target.resolve())

    def test_duplicate_name_different_paths_both_register(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        # Path is the registry's primary key — display names aren't
        # unique.  Two genuinely-different projects in different
        # directories can share a label; the entries are still
        # distinguishable by id.
        d1 = tmp_path / "a"
        d1.mkdir()
        d2 = tmp_path / "b"
        d2.mkdir()
        e1 = registry.add(d1, name="same")
        e2 = registry.add(d2, name="same")
        assert e1.id != e2.id
        assert {e.path for e in registry.list()} == {str(d1), str(d2)}

    def test_same_path_is_idempotent(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        # Re-adding the same path returns the existing entry — no
        # duplicate row, no exception.  This is what makes "open
        # project" safe to call against an already-registered dir.
        d = tmp_path / "proj"
        d.mkdir()
        first = registry.add(d, name="proj")
        second = registry.add(d, name="proj")
        assert first.id == second.id
        assert len(registry.list()) == 1

    def test_same_path_different_name_renames(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        # User re-opening the same path with a new label: relabel
        # the existing entry rather than creating a duplicate.
        d = tmp_path / "proj"
        d.mkdir()
        registry.add(d, name="old-label")
        updated = registry.add(d, name="new-label")
        assert updated.name == "new-label"
        assert len(registry.list()) == 1

    def test_missing_path_raises(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        # The registry holds entries for directories that actually
        # exist; an attempt to add a vanished path should refuse
        # rather than poisoning the registry with a phantom.
        with pytest.raises(FileNotFoundError):
            registry.add(tmp_path / "nope", name="ghost")


# ---------------------------------------------------------------------------
# Lookups — id is the default (no suffix); name + path get explicit suffixes
# ---------------------------------------------------------------------------


class TestLookups:
    def test_get_by_id(
        self, registry: ProjectRegistry, sample_project: Path,
    ) -> None:
        entry = registry.add(sample_project, name="proj")
        assert registry.get(entry.id) == entry
        assert registry.get("nope-not-an-id") is None

    def test_find_by_name_returns_list(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        # Names aren't unique → ``find_by_name`` returns every
        # match, not just the first.  Callers handle 0/1/N.
        d1 = tmp_path / "a"
        d1.mkdir()
        d2 = tmp_path / "b"
        d2.mkdir()
        d3 = tmp_path / "c"
        d3.mkdir()
        registry.add(d1, name="dup")
        registry.add(d2, name="dup")
        registry.add(d3, name="solo")

        dups = registry.find_by_name("dup")
        assert len(dups) == 2
        assert {e.path for e in dups} == {str(d1), str(d2)}

        solo = registry.find_by_name("solo")
        assert len(solo) == 1

        none = registry.find_by_name("ghost")
        assert none == []

    def test_get_by_path(
        self, registry: ProjectRegistry, sample_project: Path,
    ) -> None:
        # Paths are unique by construction so ``get_by_path`` is
        # single-result (matches the ``get_*`` naming convention).
        registry.add(sample_project, name="proj")
        found = registry.get_by_path(sample_project)
        assert found is not None
        assert found.path == str(sample_project.resolve())
        assert registry.get_by_path("/nonexistent") is None


# ---------------------------------------------------------------------------
# Mutators — all id-keyed
# ---------------------------------------------------------------------------


class TestUpdate:
    def test_update_fields(
        self, registry: ProjectRegistry, sample_project: Path,
    ) -> None:
        entry = registry.add(sample_project, name="proj")
        updated = registry.update(entry.id, has_protocol=False)
        assert updated.has_protocol is False
        # Persisted across re-read.
        loaded = registry.get(entry.id)
        assert loaded is not None
        assert loaded.has_protocol is False

    def test_update_nonexistent_raises(
        self, registry: ProjectRegistry,
    ) -> None:
        with pytest.raises(KeyError, match="not found"):
            registry.update("bogus-id", has_protocol=True)

    def test_update_bad_field_raises(
        self, registry: ProjectRegistry, sample_project: Path,
    ) -> None:
        entry = registry.add(sample_project, name="proj")
        with pytest.raises(AttributeError, match="no field"):
            registry.update(entry.id, bogus=42)


class TestTouch:
    def test_touch_updates_last_opened(
        self, registry: ProjectRegistry, sample_project: Path,
    ) -> None:
        entry = registry.add(sample_project, name="proj")
        old_time = entry.last_opened
        time.sleep(0.01)
        registry.touch(entry.id)
        after = registry.get(entry.id)
        assert after is not None
        assert after.last_opened > old_time

    def test_touch_nonexistent_raises(
        self, registry: ProjectRegistry,
    ) -> None:
        with pytest.raises(KeyError):
            registry.touch("bogus-id")


class TestRemove:
    def test_remove_by_id(
        self, registry: ProjectRegistry, sample_project: Path,
    ) -> None:
        entry = registry.add(sample_project, name="proj")
        registry.remove(entry.id)
        assert registry.list() == []

    def test_remove_nonexistent_is_silent(
        self, registry: ProjectRegistry,
    ) -> None:
        # Defensive: remove() is commonly invoked during cleanup
        # paths that don't already know whether the entry is still
        # present, so it shouldn't raise.
        registry.remove("ghost-id")


# ---------------------------------------------------------------------------
# list() — sorted by last_opened; prunes vanished paths
# ---------------------------------------------------------------------------


class TestList:
    def test_sorted_by_last_opened(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        ids: list[str] = []
        for name in ("old", "mid", "new"):
            d = tmp_path / name
            d.mkdir()
            ids.append(registry.add(d, name=name).id)
            time.sleep(0.01)

        entries = registry.list()
        assert [e.name for e in entries] == ["new", "mid", "old"]

    def test_touch_reorders(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        ids: list[str] = []
        for name in ("a", "b", "c"):
            d = tmp_path / name
            d.mkdir()
            ids.append(registry.add(d, name=name).id)
            time.sleep(0.01)

        # Touch the oldest — it should move to the front of the list.
        registry.touch(ids[0])
        entries = registry.list()
        assert entries[0].name == "a"

    def test_prunes_vanished_paths(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        # ``refresh=True`` (the default) drops entries whose
        # directories no longer exist and writes the cleaned
        # registry back, so callers always see a current view.
        d = tmp_path / "transient"
        d.mkdir()
        entry = registry.add(d, name="t")
        assert len(registry.list()) == 1

        d.rmdir()
        assert registry.list() == []

        # And the prune is persistent — the next read confirms
        # the entry is gone from disk too.
        fresh = ProjectRegistry(path=registry._path)
        assert fresh.list(refresh=False) == []
        # Pin down that we're really exercising the persistence —
        # otherwise this test could pass via a stale in-memory list.
        assert entry.id not in {e.id for e in fresh.list(refresh=False)}

    def test_refresh_false_keeps_vanished_entries(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        # ``refresh=False`` is the "I just want the raw registry,
        # don't touch disk" mode used by tests + persistence
        # round-trips.  Vanished entries stay until a refreshing
        # read prunes them.
        d = tmp_path / "transient"
        d.mkdir()
        registry.add(d, name="t")
        d.rmdir()
        assert len(registry.list(refresh=False)) == 1


# ---------------------------------------------------------------------------
# discover() — auto-register a workspace's subdirectories
# ---------------------------------------------------------------------------


class TestDiscover:
    def test_finds_subdirectories(
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

        # beta has the protocol marker.
        beta_matches = registry.find_by_name("beta")
        assert len(beta_matches) == 1
        assert beta_matches[0].has_protocol is True

    def test_skips_already_registered(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        base = tmp_path / "Clarity Projects"
        base.mkdir()
        d = base / "existing"
        d.mkdir()
        registry.add(d, name="existing")

        added = registry.discover(base)
        assert added == []

    def test_nonexistent_base_returns_empty(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        assert registry.discover(tmp_path / "nope") == []

    def test_deduplicates_names(
        self, registry: ProjectRegistry, tmp_path: Path,
    ) -> None:
        # discover() auto-disambiguates display labels so the
        # project list stays readable even when two scanned dirs
        # would share a name with an existing entry.
        other = tmp_path / "other"
        other.mkdir()
        registry.add(other, name="dup")

        base = tmp_path / "Clarity Projects"
        base.mkdir()
        (base / "dup").mkdir()

        added = registry.discover(base)
        assert len(added) == 1
        assert added[0].name == "dup-2"


# ---------------------------------------------------------------------------
# Persistence — registry survives reload; corrupted file degrades cleanly
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_survives_reload(self, tmp_path: Path) -> None:
        path = tmp_path / "projects.json"
        d = tmp_path / "proj"
        d.mkdir()

        r1 = ProjectRegistry(path=path)
        entry = r1.add(d, name="proj")

        r2 = ProjectRegistry(path=path)
        entries = r2.list(refresh=False)
        assert len(entries) == 1
        assert entries[0].id == entry.id

    def test_corrupt_file_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "projects.json"
        path.write_text("not json!", encoding="utf-8")

        r = ProjectRegistry(path=path)
        assert r.list(refresh=False) == []
