#!/usr/bin/env python3
"""
Mailbox library for asynchronous operations in the clarity agent.

Provides a general-purpose mechanism for multiple actors (human and AI) to
produce responses over time. Each async operation gets a "mailbox" — a
directory where responses accumulate as files. A "collector" processes them.

Two invariants:
1. Responses are safe to write in parallel (one file per response).
2. Collectors are reentrant (can process partial inputs repeatedly).

Mailboxes live at ``.clarity-protocol/mailboxes/{name}/`` with corresponding
archives at ``.clarity-protocol/archive/{name}/``.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple, TypedDict

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class LockInfo(NamedTuple):
    """Information about an active async-thinker lockfile."""

    thinker: str
    created_at: datetime
    expires_at: datetime


class MailboxConfig(TypedDict, total=False):
    """Contents of _config.json for a mailbox.

    Required keys: display_name, collector, collector_type.
    Additional keys are allowed for collector-specific data.
    """
    display_name: str
    collector: str
    collector_type: str  # "batch" | "single-response"


class MailboxInfo(TypedDict):
    """Summary returned by list_nonempty_mailboxes."""
    name: str
    config: dict[str, Any]
    item_count: int


class MailboxError(Exception):
    """Base exception for mailbox operations."""


class MailboxNotFoundError(MailboxError):
    """Raised when a mailbox does not exist."""


class MailboxNotEmptyError(MailboxError):
    """Raised when trying to end a mailbox that has pending items."""


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------

def _validate_protocol_dir(protocol_dir: Path) -> None:
    """Check for common misuse of the protocol_dir parameter.

    Detects two patterns:
    1. Double-nesting: path contains .clarity-protocol/.clarity-protocol
    2. Wrong argument type: caller passed project_dir instead of protocol_dir
       (i.e., protocol_dir/.clarity-protocol/config.json exists but
       protocol_dir/config.json does not)

    Raises MailboxError with a helpful message on detection.
    """
    # Check for double-nesting in the path.
    from clarity_agent.app_paths import _PROTOCOL_DIR_DOT, _PROTOCOL_DIR_VISIBLE
    _PROTO_NAMES = {_PROTOCOL_DIR_DOT, _PROTOCOL_DIR_VISIBLE}
    parts: tuple[str, ...] = protocol_dir.parts
    for i in range(len(parts) - 1):
        if parts[i] in _PROTO_NAMES and parts[i + 1] in _PROTO_NAMES:
            raise MailboxError(
                f"Double-nested protocol directory detected in path: {protocol_dir}. "
                f"Pass the protocol directory itself, not a path "
                f"that contains a nested protocol directory."
            )

    # Check if the caller passed project_dir instead of protocol_dir.
    own_config: Path = protocol_dir / "config.json"
    if not own_config.exists():
        for name in _PROTO_NAMES:
            nested_config = protocol_dir / name / "config.json"
            if nested_config.exists():
                raise MailboxError(
                    f"It looks like you passed the project root instead of the "
                    f"protocol directory: {protocol_dir}. "
                    f"Expected: {protocol_dir / name}"
                )


# ---------------------------------------------------------------------------
# Mailbox class
# ---------------------------------------------------------------------------

CONFIG_FILENAME: str = "_config.json"

# Item names must be lowercase alphanumeric with dashes (no leading/trailing).
_ITEM_NAME_RE: re.Pattern[str] = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Timestamp prefix on generated filenames: YYYYMMDD-HHMMSS
_TIMESTAMP_FMT: str = "%Y%m%d-%H%M%S"

# Matches the full item filename pattern: YYYYMMDD-HHMMSS-NN-name.md
_ITEM_FILENAME_RE: re.Pattern[str] = re.compile(r"^\d{8}-\d{6}-\d{2}-.+\.md$")


def _is_item_file(path: Path) -> bool:
    """True if *path* is a mailbox item (matches timestamp-counter-name.md)."""
    return path.is_file() and bool(_ITEM_FILENAME_RE.match(path.name))


class Mailbox:
    """Represents a single mailbox within the clarity protocol.

    A mailbox is a directory at ``.clarity-protocol/mailboxes/{name}/``
    with a corresponding archive at ``.clarity-protocol/archive/{name}/``.
    """

    def __init__(self, protocol_dir: Path, name: str) -> None:
        _validate_protocol_dir(protocol_dir)
        self.protocol_dir = protocol_dir
        self.name = name
        self.mailbox_dir = protocol_dir / "mailboxes" / name
        self.archive_dir = protocol_dir / "archive" / name

    @property
    def config_path(self) -> Path:
        """Path to _config.json in the mailbox directory."""
        return self.mailbox_dir / CONFIG_FILENAME

    @property
    def archive_config_path(self) -> Path:
        """Path to _config.json in the archive directory."""
        return self.archive_dir / CONFIG_FILENAME

    @property
    def exists(self) -> bool:
        """Whether this mailbox exists (directory + config present)."""
        return self.mailbox_dir.exists() and self.config_path.exists()

    def load_config(self) -> dict[str, Any]:
        """Load and return _config.json contents.

        Raises MailboxNotFoundError if the mailbox does not exist.
        """
        if not self.exists:
            raise MailboxNotFoundError(f"Mailbox '{self.name}' does not exist")
        return json.loads(self.config_path.read_text())

    def save_config(self, config: dict[str, Any]) -> None:
        """Write config to _config.json in both mailbox and archive.

        Raises MailboxNotFoundError if the mailbox does not exist.
        """
        if not self.exists:
            raise MailboxNotFoundError(f"Mailbox '{self.name}' does not exist")
        content: str = json.dumps(config, indent=2) + "\n"
        self.config_path.write_text(content)
        if self.archive_dir.exists():
            self.archive_config_path.write_text(content)

    # --- Factory ---

    @classmethod
    def create(
        cls,
        protocol_dir: Path,
        name: str,
        config: dict[str, Any],
    ) -> Mailbox:
        """Create a new async operation (mailbox + archive + _config.json).

        Raises MailboxError if the mailbox already exists.
        """
        mailbox = cls(protocol_dir, name)
        if mailbox.exists:
            raise MailboxError(f"Mailbox '{name}' already exists")

        mailbox.mailbox_dir.mkdir(parents=True, exist_ok=True)
        mailbox.archive_dir.mkdir(parents=True, exist_ok=True)

        content: str = json.dumps(config, indent=2) + "\n"
        mailbox.config_path.write_text(content)
        mailbox.archive_config_path.write_text(content)

        return mailbox

    @classmethod
    def open_or_create(
        cls,
        protocol_dir: Path,
        name: str,
        config: dict[str, Any],
    ) -> Mailbox:
        """Open an existing mailbox or create a new one.

        If the mailbox already exists, returns it without modifying its
        config.  If it does not exist, creates it with the given config.
        """
        mailbox = cls(protocol_dir, name)
        if mailbox.exists:
            return mailbox
        return cls.create(protocol_dir, name, config)

    # --- Operations ---

    def end(self, force: bool = False) -> None:
        """End an async operation (delete the mailbox directory).

        The archive directory is preserved. Raises MailboxNotEmptyError
        if there are pending items and force is False.
        Raises MailboxNotFoundError if the mailbox does not exist.
        """
        if not self.exists:
            raise MailboxNotFoundError(f"Mailbox '{self.name}' does not exist")

        items: list[Path] = self.list_items()
        if items and not force:
            raise MailboxNotEmptyError(
                f"Mailbox '{self.name}' has {len(items)} pending item(s). "
                f"Use force=True to delete anyway."
            )
        shutil.rmtree(self.mailbox_dir)

    def write(self, name: str, content: str) -> Path:
        """Write a response file to the mailbox.

        Generates a filename of the form ``{timestamp}-{counter}-{name}.md``.
        The caller provides only the semantic *name* (e.g. ``"auth-bypass"``);
        the timestamp and counter are determined automatically.

        Returns the path of the written file.
        Raises MailboxNotFoundError if the mailbox does not exist.
        Raises MailboxError if *name* is not a valid item name
        (lowercase alphanumeric with dashes).
        """
        if not self.exists:
            raise MailboxNotFoundError(f"Mailbox '{self.name}' does not exist")
        if not _ITEM_NAME_RE.match(name):
            raise MailboxError(
                f"Invalid item name '{name}'. "
                f"Names must be lowercase alphanumeric with dashes "
                f"(e.g. 'auth-bypass', '001-sql-injection')."
            )

        now: str = datetime.now(timezone.utc).strftime(_TIMESTAMP_FMT)
        counter: int = 0

        while True:
            path = self.mailbox_dir / f"{now}-{counter:02d}-{name}.md"
            try:
                with path.open("x") as f:
                    f.write(content)
                return path
            except FileExistsError:
                counter += 1

    def list_items(self) -> list[Path]:
        """List all response files in the mailbox.

        Only files matching the item filename pattern
        (``YYYYMMDD-HHMMSS-NN-name.md``) are returned. Metadata files
        like ``_config.json`` and ``_packet.md`` are excluded.

        Returns paths sorted by name.
        Raises MailboxNotFoundError if the mailbox does not exist.
        """
        if not self.exists:
            raise MailboxNotFoundError(f"Mailbox '{self.name}' does not exist")
        return sorted(f for f in self.mailbox_dir.iterdir() if _is_item_file(f))

    def archive_item(self, filename: str) -> Path:
        """Move a single item from the mailbox to the archive.

        Returns the new path of the archived item.
        """
        if not self.exists:
            raise MailboxNotFoundError(f"Mailbox '{self.name}' does not exist")
        src: Path = self.mailbox_dir / filename
        if not src.exists():
            raise MailboxError(f"Item '{filename}' not found in mailbox '{self.name}'")
        dst: Path = self.archive_dir / filename
        shutil.move(str(src), str(dst))
        return dst

    def unarchive_item(self, filename: str) -> Path:
        """Move a single item from the archive back to the mailbox.

        Returns the new path of the unarchived item.
        """
        if not self.exists:
            raise MailboxNotFoundError(f"Mailbox '{self.name}' does not exist")
        src: Path = self.archive_dir / filename
        if not src.exists():
            raise MailboxError(
                f"Item '{filename}' not found in archive for mailbox '{self.name}'"
            )
        dst: Path = self.mailbox_dir / filename
        shutil.move(str(src), str(dst))
        return dst

    def snapshot(self) -> Path:
        """Create a timestamped snapshot of all current items.

        Moves ALL items (excluding _config.json) into a new subdirectory
        of the archive. The mailbox is left empty (config stays).

        Returns the path of the snapshot directory.
        """
        if not self.exists:
            raise MailboxNotFoundError(f"Mailbox '{self.name}' does not exist")

        now: str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        snapshot_dir: Path = self.archive_dir / f"snapshot-{now}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        items: list[Path] = self.list_items()
        for item in items:
            shutil.move(str(item), str(snapshot_dir / item.name))

        return snapshot_dir

    # --- File storage ---

    def store_file(self, filename: str, data: bytes) -> Path:
        """Store an arbitrary file in the mailbox directory.

        Use underscore-prefixed names (e.g. ``_packet.md``) for metadata
        files that should not appear in :meth:`list_items`.

        Returns the path of the written file.
        Raises MailboxNotFoundError if the mailbox does not exist.
        """
        if not self.exists:
            raise MailboxNotFoundError(f"Mailbox '{self.name}' does not exist")
        path: Path = self.mailbox_dir / filename
        path.write_bytes(data)
        return path

    def load_file(self, filename: str) -> bytes | None:
        """Load a file from the mailbox directory.

        Returns the file contents as bytes, or ``None`` if the file does
        not exist.
        Raises MailboxNotFoundError if the mailbox does not exist.
        """
        if not self.exists:
            raise MailboxNotFoundError(f"Mailbox '{self.name}' does not exist")
        path: Path = self.mailbox_dir / filename
        if not path.exists():
            return None
        return path.read_bytes()

    # --- Lockfiles (async thinker tracking) ---

    _LOCK_SUFFIX: str = ".lock"

    def create_lock(self, thinker_name: str, expires_at: datetime) -> Path:
        """Create a lockfile indicating a thinker is working asynchronously.

        The lockfile is named ``_thinker-name.lock`` and contains JSON with
        the thinker name, creation time, and expiration time.

        Raises MailboxNotFoundError if the mailbox does not exist.
        """
        if not self.exists:
            raise MailboxNotFoundError(f"Mailbox '{self.name}' does not exist")
        lock_data: dict[str, str] = {
            "thinker": thinker_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        lock_path: Path = self.mailbox_dir / f"_{thinker_name}{self._LOCK_SUFFIX}"
        lock_path.write_text(json.dumps(lock_data, indent=2) + "\n")
        return lock_path

    def remove_lock(self, thinker_name: str) -> None:
        """Remove a thinker's lockfile.

        No-op if the lockfile does not exist (idempotent).
        Raises MailboxNotFoundError if the mailbox does not exist.
        """
        if not self.exists:
            raise MailboxNotFoundError(f"Mailbox '{self.name}' does not exist")
        lock_path: Path = self.mailbox_dir / f"_{thinker_name}{self._LOCK_SUFFIX}"
        if lock_path.exists():
            lock_path.unlink()

    def active_locks(self) -> list[LockInfo]:
        """List all non-expired lockfiles in the mailbox.

        Returns a list of :class:`LockInfo` named tuples.  Expired locks
        are excluded but not removed.

        Returns an empty list if the mailbox does not exist (graceful
        handling for state checking).
        """
        if not self.exists:
            return []
        now = datetime.now(timezone.utc)
        result: list[LockInfo] = []
        for path in self.mailbox_dir.iterdir():
            if path.name.startswith("_") and path.name.endswith(self._LOCK_SUFFIX):
                try:
                    data: dict[str, Any] = json.loads(path.read_text())
                    created = datetime.fromisoformat(data["created_at"])
                    expires = datetime.fromisoformat(data["expires_at"])
                    if expires > now:
                        result.append(LockInfo(
                            thinker=data["thinker"],
                            created_at=created,
                            expires_at=expires,
                        ))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue  # skip malformed lock files
        return result

    def clean_expired_locks(self) -> list[str]:
        """Remove all expired lockfiles.  Returns names of removed thinkers.

        Raises MailboxNotFoundError if the mailbox does not exist.
        """
        if not self.exists:
            raise MailboxNotFoundError(f"Mailbox '{self.name}' does not exist")
        now = datetime.now(timezone.utc)
        removed: list[str] = []
        for path in self.mailbox_dir.iterdir():
            if path.name.startswith("_") and path.name.endswith(self._LOCK_SUFFIX):
                try:
                    data = json.loads(path.read_text())
                    expires = datetime.fromisoformat(data["expires_at"])
                    if expires <= now:
                        path.unlink()
                        removed.append(data.get("thinker", path.stem))
                except (json.JSONDecodeError, KeyError, ValueError):
                    path.unlink()  # remove malformed locks
                    removed.append(path.stem)
        return removed


# ---------------------------------------------------------------------------
# Module-level functions
# ---------------------------------------------------------------------------

def list_nonempty_mailboxes(protocol_dir: Path) -> list[MailboxInfo]:
    """Scan all mailboxes and return info for each that has pending items.

    Used by the packet status checker to surface active async operations.
    """
    _validate_protocol_dir(protocol_dir)
    mailboxes_dir: Path = protocol_dir / "mailboxes"
    if not mailboxes_dir.exists():
        return []

    result: list[MailboxInfo] = []
    for entry in sorted(mailboxes_dir.iterdir()):
        if not entry.is_dir():
            continue
        config_path: Path = entry / CONFIG_FILENAME
        if not config_path.exists():
            continue

        items: list[Path] = [f for f in entry.iterdir() if _is_item_file(f)]
        if not items:
            continue

        config: dict[str, Any] = json.loads(config_path.read_text())
        result.append({
            "name": entry.name,
            "config": config,
            "item_count": len(items),
        })

    return result


def ensure_suggestion_box(protocol_dir: Path) -> Mailbox:
    """Ensure the permanent 'suggestions' mailbox exists.

    Creates it if missing. Called by init_protocol. The suggestion box
    is never ended — it is always available for any process to write
    suggestions into.
    """
    mailbox = Mailbox(protocol_dir, "suggestions")
    if not mailbox.exists:
        return Mailbox.create(protocol_dir, "suggestions", {
            "display_name": "suggestion box",
            "collector": "suggestion-review",
            "collector_type": "single-response",
            "permanent": True,
        })
    return mailbox


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Manage clarity protocol mailboxes for async operations",
    )
    parser.add_argument(
        "--protocol-dir",
        default=None,
        help="Path to protocol directory (default: auto-detected from cwd)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Mailbox operation")

    # create
    p_create = subparsers.add_parser("create", help="Create a new mailbox")
    p_create.add_argument("--name", required=True, help="Mailbox name")
    p_create.add_argument("--display-name", required=True, help="Human-readable name")
    p_create.add_argument("--collector", required=True, help="Collector agent/function name")
    p_create.add_argument(
        "--type", required=True, dest="collector_type",
        choices=["batch", "single-response"],
        help="Collector type",
    )
    p_create.add_argument(
        "--extra", nargs="*", metavar="KEY=VALUE",
        help="Additional config key-value pairs",
    )

    # end
    p_end = subparsers.add_parser("end", help="End an async operation")
    p_end.add_argument("--name", required=True, help="Mailbox name")
    p_end.add_argument("--force", action="store_true", help="Force end even with pending items")

    # write
    p_write = subparsers.add_parser("write", help="Write a response to a mailbox")
    p_write.add_argument("--name", required=True, help="Mailbox name")
    p_write.add_argument(
        "--item-name", required=True,
        help="Item name (e.g. 'auth-bypass'). Timestamp and counter are added automatically.",
    )
    p_write.add_argument("--content", help="Response content (reads stdin if omitted)")

    # list
    p_list = subparsers.add_parser("list", help="List items in a mailbox")
    p_list.add_argument("--name", required=True, help="Mailbox name")

    # archive
    p_archive = subparsers.add_parser("archive", help="Archive a single item")
    p_archive.add_argument("--name", required=True, help="Mailbox name")
    p_archive.add_argument("--file", required=True, dest="filename", help="Item filename")

    # unarchive
    p_unarchive = subparsers.add_parser("unarchive", help="Unarchive a single item")
    p_unarchive.add_argument("--name", required=True, help="Mailbox name")
    p_unarchive.add_argument("--file", required=True, dest="filename", help="Item filename")

    # snapshot
    p_snapshot = subparsers.add_parser("snapshot", help="Snapshot all items to archive")
    p_snapshot.add_argument("--name", required=True, help="Mailbox name")

    # status
    p_status = subparsers.add_parser("status", help="Show nonempty mailboxes")
    p_status.add_argument("--json", action="store_true", dest="json_output", help="Output JSON")

    args: argparse.Namespace = parser.parse_args()

    if not args.command:
        parser.error("a command is required")

    if args.protocol_dir is not None:
        protocol_dir: Path = Path(args.protocol_dir).resolve()
    else:
        from clarity_agent.app_paths import find_protocol_dir
        protocol_dir = find_protocol_dir()

    try:
        if args.command == "create":
            config: dict[str, Any] = {
                "display_name": args.display_name,
                "collector": args.collector,
                "collector_type": args.collector_type,
            }
            if args.extra:
                for kv in args.extra:
                    key, _, value = kv.partition("=")
                    config[key] = value
            mailbox = Mailbox.create(protocol_dir, args.name, config)
            print(f"Created mailbox: {mailbox.mailbox_dir}")

        elif args.command == "end":
            mailbox = Mailbox(protocol_dir, args.name)
            mailbox.end(force=args.force)
            print(f"Ended mailbox: {args.name}")

        elif args.command == "write":
            mailbox = Mailbox(protocol_dir, args.name)
            content: str = args.content if args.content else sys.stdin.read()
            path: Path = mailbox.write(args.item_name, content)
            print(f"Written: {path}")

        elif args.command == "list":
            mailbox = Mailbox(protocol_dir, args.name)
            items: list[Path] = mailbox.list_items()
            if items:
                for item in items:
                    print(item.name)
            else:
                print("(empty)")

        elif args.command == "archive":
            mailbox = Mailbox(protocol_dir, args.name)
            new_path: Path = mailbox.archive_item(args.filename)
            print(f"Archived: {args.filename} → {new_path}")

        elif args.command == "unarchive":
            mailbox = Mailbox(protocol_dir, args.name)
            new_path = mailbox.unarchive_item(args.filename)
            print(f"Unarchived: {args.filename} → {new_path}")

        elif args.command == "snapshot":
            mailbox = Mailbox(protocol_dir, args.name)
            snapshot_path: Path = mailbox.snapshot()
            print(f"Snapshot created: {snapshot_path}")

        elif args.command == "status":
            mailbox_infos: list[MailboxInfo] = list_nonempty_mailboxes(protocol_dir)
            if args.json_output:
                print(json.dumps(mailbox_infos, indent=2))
            elif mailbox_infos:
                for info in mailbox_infos:
                    display: str = info["config"].get("display_name", info["name"])
                    status: str = info["config"].get("status", "active")
                    print(f"  {info['name']}: {info['item_count']} item(s) ({status}) — {display}")
            else:
                print("No nonempty mailboxes.")

    except MailboxError as e:
        raise SystemExit(f"Error: {e}") from e


if __name__ == "__main__":
    main()
