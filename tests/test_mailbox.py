"""Tests for the mailbox library."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from clarity_agent.protocol.mailbox import (
    Mailbox,
    MailboxError,
    MailboxNotEmptyError,
    MailboxNotFoundError,
    _validate_protocol_dir,
    ensure_suggestion_box,
    list_nonempty_mailboxes,
)


def _make_config(**overrides: object) -> dict[str, object]:
    """Create a minimal mailbox config with optional overrides."""
    config: dict[str, object] = {
        "display_name": "test operation",
        "collector": "test-collector",
        "collector_type": "batch",
    }
    config.update(overrides)
    return config


# ---------------------------------------------------------------------------
# Mailbox.create
# ---------------------------------------------------------------------------

class TestMailboxCreate:
    """Mailbox.create() sets up directory structure and config."""

    def test_creates_mailbox_directory(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        assert mb.mailbox_dir.is_dir()

    def test_creates_archive_directory(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        assert mb.archive_dir.is_dir()

    def test_writes_config_to_mailbox(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        assert mb.config_path.exists()
        config = json.loads(mb.config_path.read_text())
        assert config["display_name"] == "test operation"
        assert config["collector"] == "test-collector"

    def test_writes_config_to_archive(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        assert mb.archive_config_path.exists()
        config = json.loads(mb.archive_config_path.read_text())
        assert config["display_name"] == "test operation"

    def test_config_content_matches_input(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        input_config = _make_config(status="collecting", sources=["sec", "ux"])
        mb = Mailbox.create(pd, "test-op", input_config)
        config = json.loads(mb.config_path.read_text())
        assert config["status"] == "collecting"
        assert config["sources"] == ["sec", "ux"]

    def test_raises_on_duplicate_creation(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        Mailbox.create(pd, "test-op", _make_config())
        with pytest.raises(MailboxError, match="already exists"):
            Mailbox.create(pd, "test-op", _make_config())

    def test_creates_nested_parents(self, tmp_path: Path) -> None:
        pd = tmp_path / "deep" / "nesting" / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        assert mb.exists

    def test_exists_property(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb_before = Mailbox(pd, "test-op")
        assert not mb_before.exists
        Mailbox.create(pd, "test-op", _make_config())
        mb_after = Mailbox(pd, "test-op")
        assert mb_after.exists


# ---------------------------------------------------------------------------
# Mailbox.end
# ---------------------------------------------------------------------------

class TestMailboxEnd:
    """Mailbox.end() removes the mailbox but preserves archive."""

    def test_removes_mailbox_directory(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        mb.end()
        assert not mb.mailbox_dir.exists()

    def test_preserves_archive(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        mb.end()
        assert mb.archive_dir.exists()
        assert mb.archive_config_path.exists()

    def test_raises_when_not_empty(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        mb.write("item", "content")
        with pytest.raises(MailboxNotEmptyError, match="1 pending"):
            mb.end()

    def test_force_removes_despite_items(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        mb.write("item", "content")
        mb.end(force=True)
        assert not mb.mailbox_dir.exists()

    def test_raises_when_mailbox_not_found(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox(pd, "nonexistent")
        with pytest.raises(MailboxNotFoundError):
            mb.end()


# ---------------------------------------------------------------------------
# Mailbox.write
# ---------------------------------------------------------------------------

class TestMailboxWrite:
    """Mailbox.write() adds a file to the mailbox."""

    def test_writes_file_with_content(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        path = mb.write("response", "# Hello\n\nContent here.\n")
        assert path.read_text() == "# Hello\n\nContent here.\n"

    def test_returns_correct_path(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        path = mb.write("response", "content")
        assert path.parent == mb.mailbox_dir
        assert path.name.endswith("-response.md")

    def test_raises_when_mailbox_not_found(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox(pd, "nonexistent")
        with pytest.raises(MailboxNotFoundError):
            mb.write("response", "content")

    def test_collision_avoidance(self, tmp_path: Path) -> None:
        """Two writes with the same name produce different files."""
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        path1 = mb.write("response", "first write")
        path2 = mb.write("response", "second write")
        assert path1 != path2
        assert path1.read_text() == "first write"
        assert path2.read_text() == "second write"
        assert len(mb.list_items()) == 2

    def test_generates_timestamped_filename(self, tmp_path: Path) -> None:
        """Returned path matches YYYYMMDD-HHMMSS-NN-name.md pattern."""
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        path = mb.write("item", "content")
        assert re.match(r"\d{8}-\d{6}-\d{2}-.+\.md$", path.name)

    def test_counter_increments(self, tmp_path: Path) -> None:
        """Multiple writes produce sequential counters."""
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        path1 = mb.write("alpha", "a")
        path2 = mb.write("alpha", "b")
        path3 = mb.write("alpha", "c")
        # Extract counter portion (third segment: YYYYMMDD-HHMMSS-NN-name.md)
        counter1 = path1.name.split("-")[2]
        counter2 = path2.name.split("-")[2]
        counter3 = path3.name.split("-")[2]
        assert counter1 == "00"
        assert counter2 == "01"
        assert counter3 == "02"

    def test_rejects_invalid_name(self, tmp_path: Path) -> None:
        """Names with uppercase, spaces, dots, or leading/trailing dashes raise MailboxError."""
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        invalid_names = [
            "UpperCase",
            "has space",
            "has.dot",
            "-leading-dash",
            "trailing-dash-",
            "double--dash",
            "",
            "has_underscore",
        ]
        for name in invalid_names:
            with pytest.raises(MailboxError, match="Invalid item name"):
                mb.write(name, "content")

    def test_accepts_valid_names(self, tmp_path: Path) -> None:
        """Valid semantic names are accepted without error."""
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        valid_names = ["auth-bypass", "response", "a", "001-sql-injection"]
        for name in valid_names:
            path = mb.write(name, f"content for {name}")
            assert path.exists()
            assert path.name.endswith(f"-{name}.md")


# ---------------------------------------------------------------------------
# Mailbox.list_items
# ---------------------------------------------------------------------------

class TestMailboxListItems:
    """Mailbox.list_items() returns files excluding _config.json."""

    def test_empty_mailbox_returns_empty_list(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        assert mb.list_items() == []

    def test_excludes_config_json(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        # _config.json exists but should not appear in list
        assert mb.config_path.exists()
        assert mb.list_items() == []

    def test_raises_when_not_found(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox(pd, "nonexistent")
        with pytest.raises(MailboxNotFoundError):
            mb.list_items()


# ---------------------------------------------------------------------------
# Mailbox.archive_item
# ---------------------------------------------------------------------------

class TestMailboxArchiveItem:
    """Mailbox.archive_item() moves file from mailbox to archive."""

    def test_moves_file_to_archive(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        path = mb.write("item", "content")
        filename = path.name
        mb.archive_item(filename)
        assert not (mb.mailbox_dir / filename).exists()
        assert (mb.archive_dir / filename).exists()
        assert (mb.archive_dir / filename).read_text() == "content"

    def test_returns_new_path(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        path = mb.write("item", "content")
        filename = path.name
        new_path = mb.archive_item(filename)
        assert new_path == mb.archive_dir / filename

    def test_file_no_longer_in_mailbox(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        path = mb.write("item", "content")
        mb.archive_item(path.name)
        assert mb.list_items() == []

    def test_raises_when_file_not_found(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        with pytest.raises(MailboxError, match="not found"):
            mb.archive_item("nonexistent.md")


# ---------------------------------------------------------------------------
# Mailbox.unarchive_item
# ---------------------------------------------------------------------------

class TestMailboxUnarchiveItem:
    """Mailbox.unarchive_item() moves file from archive to mailbox."""

    def test_moves_file_back_to_mailbox(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        path = mb.write("item", "content")
        filename = path.name
        mb.archive_item(filename)
        mb.unarchive_item(filename)
        assert (mb.mailbox_dir / filename).exists()
        assert not (mb.archive_dir / filename).exists()

    def test_returns_new_path(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        path = mb.write("item", "content")
        filename = path.name
        mb.archive_item(filename)
        new_path = mb.unarchive_item(filename)
        assert new_path == mb.mailbox_dir / filename

    def test_roundtrip_archive_unarchive(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        path = mb.write("item", "original content")
        filename = path.name
        mb.archive_item(filename)
        mb.unarchive_item(filename)
        assert (mb.mailbox_dir / filename).read_text() == "original content"

    def test_raises_when_not_in_archive(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        with pytest.raises(MailboxError, match="not found in archive"):
            mb.unarchive_item("nonexistent.md")


# ---------------------------------------------------------------------------
# Mailbox.snapshot
# ---------------------------------------------------------------------------

class TestMailboxSnapshot:
    """Mailbox.snapshot() creates timestamped archive subdirectory."""

    def test_creates_snapshot_directory(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        mb.write("item", "content")
        snapshot_path = mb.snapshot()
        assert snapshot_path.is_dir()
        assert snapshot_path.name.startswith("snapshot-")

    def test_moves_all_items_to_snapshot(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        path_a = mb.write("a", "aaa")
        path_b = mb.write("b", "bbb")
        snapshot_path = mb.snapshot()
        assert (snapshot_path / path_a.name).read_text() == "aaa"
        assert (snapshot_path / path_b.name).read_text() == "bbb"

    def test_mailbox_is_empty_after_snapshot(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        mb.write("item", "content")
        mb.snapshot()
        assert mb.list_items() == []

    def test_config_json_stays_in_mailbox(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        mb.write("item", "content")
        mb.snapshot()
        assert mb.config_path.exists()
        assert mb.exists

    def test_returns_snapshot_path(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        mb.write("item", "content")
        snapshot_path = mb.snapshot()
        assert snapshot_path.parent == mb.archive_dir

    def test_snapshot_name_format(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        mb.write("item", "content")
        snapshot_path = mb.snapshot()
        # Format: snapshot-YYYYMMDD-HHMMSS
        name = snapshot_path.name
        assert name.startswith("snapshot-")
        assert len(name) == len("snapshot-YYYYMMDD-HHMMSS")

    def test_empty_mailbox_snapshot(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        snapshot_path = mb.snapshot()
        # Snapshot dir is created but empty
        assert snapshot_path.is_dir()
        items = list(snapshot_path.iterdir())
        assert items == []


# ---------------------------------------------------------------------------
# Mailbox.load_config / save_config
# ---------------------------------------------------------------------------

class TestMailboxConfig:
    """Config loading and saving."""

    def test_load_config(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config(status="collecting"))
        config = mb.load_config()
        assert config["display_name"] == "test operation"
        assert config["status"] == "collecting"

    def test_save_config_updates_both(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        config = mb.load_config()
        config["status"] = "ready for analysis"
        mb.save_config(config)
        # Both mailbox and archive should be updated
        mb_config = json.loads(mb.config_path.read_text())
        ar_config = json.loads(mb.archive_config_path.read_text())
        assert mb_config["status"] == "ready for analysis"
        assert ar_config["status"] == "ready for analysis"

    def test_load_raises_when_not_found(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox(pd, "nonexistent")
        with pytest.raises(MailboxNotFoundError):
            mb.load_config()


# ---------------------------------------------------------------------------
# list_nonempty_mailboxes
# ---------------------------------------------------------------------------

class TestListNonemptyMailboxes:
    """list_nonempty_mailboxes() scans all mailboxes."""

    def test_no_mailboxes_dir_returns_empty(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        assert list_nonempty_mailboxes(pd) == []

    def test_empty_mailbox_excluded(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        Mailbox.create(pd, "empty-op", _make_config())
        assert list_nonempty_mailboxes(pd) == []

    def test_nonempty_mailbox_included(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        mb.write("item", "content")
        result = list_nonempty_mailboxes(pd)
        assert len(result) == 1
        assert result[0]["name"] == "test-op"
        assert result[0]["item_count"] == 1
        assert result[0]["config"]["display_name"] == "test operation"

    def test_multiple_mailboxes(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb1 = Mailbox.create(pd, "alpha", _make_config(display_name="Alpha"))
        mb1.write("a", "a")
        Mailbox.create(pd, "beta-empty", _make_config(display_name="Beta"))
        mb3 = Mailbox.create(pd, "gamma", _make_config(display_name="Gamma"))
        mb3.write("g1", "g1")
        mb3.write("g2", "g2")
        result = list_nonempty_mailboxes(pd)
        assert len(result) == 2
        names = [r["name"] for r in result]
        assert names == ["alpha", "gamma"]  # sorted
        assert result[1]["item_count"] == 2

    def test_returns_config_for_each(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config(status="collecting"))
        mb.write("item", "content")
        result = list_nonempty_mailboxes(pd)
        assert result[0]["config"]["collector"] == "test-collector"
        assert result[0]["config"]["status"] == "collecting"


# ---------------------------------------------------------------------------
# ensure_suggestion_box
# ---------------------------------------------------------------------------

class TestEnsureSuggestionBox:
    """ensure_suggestion_box() creates/verifies the suggestions mailbox."""

    def test_creates_if_missing(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = ensure_suggestion_box(pd)
        assert mb.exists
        assert mb.name == "suggestions"

    def test_idempotent_if_exists(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb1 = ensure_suggestion_box(pd)
        mb1.write("idea", "# Idea\n")
        mb2 = ensure_suggestion_box(pd)
        assert mb2.exists
        # Item survives
        assert len(mb2.list_items()) == 1

    def test_config_has_correct_fields(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = ensure_suggestion_box(pd)
        config = mb.load_config()
        assert config["display_name"] == "suggestion box"
        assert config["collector"] == "suggestion-review"
        assert config["collector_type"] == "single-response"
        assert config["permanent"] is True

    def test_archive_created(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = ensure_suggestion_box(pd)
        assert mb.archive_dir.is_dir()
        assert mb.archive_config_path.exists()


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------

class TestValidateProtocolDir:
    """Tests for _validate_protocol_dir defensive checks."""

    def test_accepts_correct_protocol_dir(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        pd.mkdir()
        (pd / "config.json").write_text("{}")
        # Should not raise.
        _validate_protocol_dir(pd)

    def test_accepts_nonexistent_protocol_dir(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        # Path doesn't exist yet — should still be accepted (for creation).
        _validate_protocol_dir(pd)

    def test_rejects_double_nested_path(self, tmp_path: Path) -> None:
        bad = tmp_path / ".clarity-protocol" / ".clarity-protocol"
        with pytest.raises(MailboxError, match="Double-nested protocol directory"):
            _validate_protocol_dir(bad)

    def test_rejects_project_dir_passed_as_protocol_dir(self, tmp_path: Path) -> None:
        """Detects when caller passes project root instead of protocol dir."""
        # Set up: project root with a .clarity-protocol/ inside it.
        project = tmp_path / "my-project"
        protocol = project / ".clarity-protocol"
        protocol.mkdir(parents=True)
        (protocol / "config.json").write_text("{}")
        # Passing project root should be caught.
        with pytest.raises(MailboxError, match="project root"):
            _validate_protocol_dir(project)

    def test_no_false_positive_when_config_absent(self, tmp_path: Path) -> None:
        """No false positive if neither config exists (fresh init)."""
        pd = tmp_path / "fresh"
        pd.mkdir()
        # No config.json anywhere — should not raise.
        _validate_protocol_dir(pd)

    def test_mailbox_constructor_validates(self, tmp_path: Path) -> None:
        bad = tmp_path / ".clarity-protocol" / ".clarity-protocol"
        with pytest.raises(MailboxError, match="Double-nested"):
            Mailbox(bad, "test")

    def test_list_nonempty_validates(self, tmp_path: Path) -> None:
        bad = tmp_path / ".clarity-protocol" / ".clarity-protocol"
        with pytest.raises(MailboxError, match="Double-nested"):
            list_nonempty_mailboxes(bad)


# ---------------------------------------------------------------------------
# Positive item filtering
# ---------------------------------------------------------------------------

class TestItemFiltering:
    """list_items() and list_nonempty_mailboxes() use positive pattern matching."""

    def test_list_items_ignores_non_item_files(self, tmp_path: Path) -> None:
        """Files that don't match the item pattern are excluded."""
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        # Write a proper item
        mb.write("real-item", "content")
        # Manually create files that shouldn't be counted
        (mb.mailbox_dir / "notes.txt").write_text("some notes")
        (mb.mailbox_dir / "random.md").write_text("not an item")
        assert len(mb.list_items()) == 1

    def test_end_succeeds_when_only_packet_present(self, tmp_path: Path) -> None:
        """A stored file doesn't prevent end() from succeeding."""
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        mb.store_file("_packet.md", b"# Review\n\nSome content.")
        # No items — end() should succeed without force
        mb.end()
        assert not mb.mailbox_dir.exists()

    def test_nonempty_mailboxes_ignores_non_items(self, tmp_path: Path) -> None:
        """list_nonempty_mailboxes() doesn't count non-item files."""
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        # Only non-item files present
        mb.store_file("_packet.md", b"# Packet content")
        (mb.mailbox_dir / "notes.txt").write_text("extra file")
        assert list_nonempty_mailboxes(pd) == []
        # Now add a real item
        mb.write("item", "content")
        result = list_nonempty_mailboxes(pd)
        assert len(result) == 1
        assert result[0]["item_count"] == 1


# ---------------------------------------------------------------------------
# Packet storage
# ---------------------------------------------------------------------------

class TestFileStorage:
    """Mailbox.store_file() and load_file() manage arbitrary files."""

    def test_store_and_load_roundtrip(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        data = b"# Review Packet\n\nHere is the problem statement.\n"
        mb.store_file("_packet.md", data)
        assert mb.load_file("_packet.md") == data

    def test_load_returns_none_when_absent(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        assert mb.load_file("_packet.md") is None

    def test_store_overwrites_existing(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        mb.store_file("_packet.md", b"version 1")
        mb.store_file("_packet.md", b"version 2")
        assert mb.load_file("_packet.md") == b"version 2"

    def test_store_returns_path(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        path = mb.store_file("_packet.md", b"content")
        assert path.name == "_packet.md"
        assert path.parent == mb.mailbox_dir

    def test_different_filenames(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        mb.store_file("_packet.html", b"<html>packet</html>")
        assert mb.load_file("_packet.html") == b"<html>packet</html>"
        assert mb.load_file("_packet.md") is None


# ---------------------------------------------------------------------------
# Mailbox.open_or_create
# ---------------------------------------------------------------------------

class TestMailboxOpenOrCreate:
    """open_or_create is idempotent: create when absent, open when exists."""

    def test_creates_when_absent(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.open_or_create(pd, "test-op", _make_config())
        assert mb.exists
        config = mb.load_config()
        assert config["display_name"] == "test operation"

    def test_opens_when_exists(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        Mailbox.create(pd, "test-op", _make_config(status="collecting"))
        mb = Mailbox.open_or_create(pd, "test-op", _make_config(status="ready"))
        # Should return the existing mailbox without overwriting config.
        config = mb.load_config()
        assert config["status"] == "collecting"

    def test_preserves_items(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb1 = Mailbox.open_or_create(pd, "test-op", _make_config())
        mb1.write("item", "content")
        mb2 = Mailbox.open_or_create(pd, "test-op", _make_config())
        assert len(mb2.list_items()) == 1


# ---------------------------------------------------------------------------
# Mailbox lockfile methods
# ---------------------------------------------------------------------------

class TestMailboxLockfiles:
    """Lockfile methods track async thinker progress."""

    def test_create_lock(self, tmp_path: Path) -> None:
        from datetime import datetime, timedelta, timezone

        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        path = mb.create_lock("sec-thinker", expires)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["thinker"] == "sec-thinker"

    def test_active_locks_returns_non_expired(self, tmp_path: Path) -> None:
        from datetime import datetime, timedelta, timezone

        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        mb.create_lock("alive", future)
        locks = mb.active_locks()
        assert len(locks) == 1
        assert locks[0].thinker == "alive"

    def test_active_locks_excludes_expired(self, tmp_path: Path) -> None:
        from datetime import datetime, timedelta, timezone

        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        mb.create_lock("expired", past)
        assert mb.active_locks() == []

    def test_remove_lock_idempotent(self, tmp_path: Path) -> None:
        from datetime import datetime, timedelta, timezone

        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        mb.create_lock("target", future)
        mb.remove_lock("target")
        assert mb.active_locks() == []
        # Second remove is a no-op.
        mb.remove_lock("target")

    def test_clean_expired_locks(self, tmp_path: Path) -> None:
        from datetime import datetime, timedelta, timezone

        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        mb.create_lock("expired-one", past)
        mb.create_lock("still-alive", future)
        removed = mb.clean_expired_locks()
        assert "expired-one" in removed
        assert len(mb.active_locks()) == 1

    def test_locks_invisible_to_list_items(self, tmp_path: Path) -> None:
        from datetime import datetime, timedelta, timezone

        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox.create(pd, "test-op", _make_config())
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        mb.create_lock("sec-thinker", future)
        assert mb.list_items() == []

    def test_active_locks_on_nonexistent_mailbox(self, tmp_path: Path) -> None:
        pd = tmp_path / ".clarity-protocol"
        mb = Mailbox(pd, "nonexistent")
        assert mb.active_locks() == []
