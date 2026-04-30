#!/usr/bin/env python3
"""Bump the version number across all project files.

Usage:
    python scripts/bump-version.py 1.2.3
    python scripts/bump-version.py          # prints current version

Updates:
    pyproject.toml          version = "X.Y.Z"
    src-tauri/tauri.conf.json   "version": "X.Y.Z"
    src-tauri/Cargo.toml    version = "X.Y.Z" (in [package])
    CHANGELOG.md            Stamps [Unreleased] as [X.Y.Z] with date
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FILES = {
    "pyproject.toml": (
        re.compile(r'^(version\s*=\s*)"[^"]+"', re.MULTILINE),
        lambda v: rf'\g<1>"{v}"',
    ),
    "src-tauri/Cargo.toml": (
        # Only match the version in the [package] section — not dependency versions.
        # The [package] version is always the first `version = "..."` in the file.
        re.compile(r'^(version\s*=\s*)"[^"]+"', re.MULTILINE),
        lambda v: rf'\g<1>"{v}"',
    ),
}

TAURI_CONF = "src-tauri/tauri.conf.json"


def get_current_version() -> str:
    """Read the version from pyproject.toml."""
    text = (REPO_ROOT / "pyproject.toml").read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise RuntimeError("Could not find version in pyproject.toml")
    return m.group(1)


def set_version(new_version: str) -> None:
    """Write the new version to all project files."""
    # Validate semver-ish format
    if not re.match(r"^\d+\.\d+\.\d+(-\w+(\.\w+)*)?$", new_version):
        print(f"Error: '{new_version}' doesn't look like a valid version (expected X.Y.Z)")
        sys.exit(1)

    # TOML files — regex replacement (first match only for Cargo.toml)
    for relpath, (pattern, replacement_fn) in FILES.items():
        filepath = REPO_ROOT / relpath
        text = filepath.read_text()
        new_text, count = pattern.subn(replacement_fn(new_version), text, count=1)
        if count == 0:
            print(f"  Warning: no version found in {relpath}")
        else:
            filepath.write_text(new_text)
            print(f"  Updated {relpath}")

    # tauri.conf.json — proper JSON update
    conf_path = REPO_ROOT / TAURI_CONF
    conf = json.loads(conf_path.read_text())
    conf["version"] = new_version
    conf_path.write_text(json.dumps(conf, indent=2) + "\n")
    print(f"  Updated {TAURI_CONF}")


def _last_release_tag() -> str | None:
    """Return the most recent vX.Y.Z tag, or None if there are no tags."""
    r = subprocess.run(
        ["git", "tag", "--sort=-creatordate", "--list", "v*"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    for line in r.stdout.strip().splitlines():
        if re.match(r"^v\d+\.\d+\.\d+", line):
            return line.strip()
    return None


def _commits_since(tag: str | None) -> list[str]:
    """Return one-line commit messages since *tag* (or all if None).

    Merge commits are excluded to keep the log meaningful.
    """
    cmd = ["git", "log", "--oneline", "--no-merges"]
    if tag:
        cmd.append(f"{tag}..HEAD")
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    return [line.split(" ", 1)[1] for line in r.stdout.strip().splitlines() if " " in line]


_CATEGORY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Added",   re.compile(r"^(add|feat|introduce|create|implement|new)\b", re.I)),
    ("Fixed",   re.compile(r"^(fix|repair|resolve|patch|correct|bug)\b", re.I)),
    ("Changed", re.compile(r"^(update|change|refactor|move|rename|improve|bump|upgrade)\b", re.I)),
    ("Removed", re.compile(r"^(remove|delete|drop|deprecate)\b", re.I)),
]


def _categorize(messages: list[str]) -> dict[str, list[str]]:
    """Sort commit messages into Keep-a-Changelog categories."""
    buckets: dict[str, list[str]] = {}
    for msg in messages:
        category = "Changed"  # default
        for cat, pat in _CATEGORY_PATTERNS:
            if pat.search(msg):
                category = cat
                break
        buckets.setdefault(category, []).append(msg)
    return buckets


def _build_section(version: str, categories: dict[str, list[str]]) -> str:
    """Format a changelog section for *version*."""
    today = date.today().isoformat()
    lines = [f"## [{version}] - {today}", ""]
    for heading in ("Added", "Changed", "Fixed", "Removed"):
        items = categories.get(heading)
        if not items:
            continue
        lines.append(f"### {heading}")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines)


def update_changelog(new_version: str) -> None:
    """Stamp the [Unreleased] section in CHANGELOG.md with *new_version*.

    Replaces the ``## [Unreleased]`` heading and its contents with a dated
    version heading built from commits since the last release tag, then adds
    a fresh ``## [Unreleased]`` above it.
    """
    changelog = REPO_ROOT / "CHANGELOG.md"
    if not changelog.exists():
        print("  Warning: CHANGELOG.md not found, skipping")
        return

    tag = _last_release_tag()
    commits = _commits_since(tag)
    if not commits:
        print("  Warning: no commits since last tag, changelog left unchanged")
        return

    categories = _categorize(commits)
    new_section = _build_section(new_version, categories)

    text = changelog.read_text()

    # Replace [Unreleased] block with new version section + fresh Unreleased.
    unreleased_re = re.compile(
        r"## \[Unreleased\]\n(.*?)(?=\n## \[|(?:\n\[Unreleased\]:)|\Z)",
        re.DOTALL,
    )
    replacement = "## [Unreleased]\n\n" + new_section
    new_text, count = unreleased_re.subn(replacement, text, count=1)
    if count == 0:
        # No [Unreleased] section — prepend after the header.
        header_end = text.index("\n\n") + 2 if "\n\n" in text else 0
        new_text = text[:header_end] + "## [Unreleased]\n\n" + new_section + "\n" + text[header_end:]

    # Update footer links.
    old_tag = tag or f"v{new_version}"
    link_section = (
        f"[Unreleased]: https://github.com/microsoft/clarity-agent/compare/v{new_version}...HEAD\n"
        f"[{new_version}]: https://github.com/microsoft/clarity-agent/compare/{old_tag}...v{new_version}"
    )
    # Replace the existing [Unreleased] link line.
    new_text = re.sub(
        r"\[Unreleased\]: https://[^\n]+",
        link_section,
        new_text,
        count=1,
    )

    changelog.write_text(new_text)
    print("  Updated CHANGELOG.md")


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Current version: {get_current_version()}")
        print(f"Usage: {sys.argv[0]} <new-version>")
        return

    new_version = sys.argv[1]
    old_version = get_current_version()
    print(f"Bumping version: {old_version} -> {new_version}")
    set_version(new_version)
    update_changelog(new_version)
    print("\nDone. Don't forget to commit and tag:")
    print(f"  git commit -am 'Release v{new_version}'")
    print(f"  git tag v{new_version}")
    print(f"  git push origin main v{new_version}")


if __name__ == "__main__":
    main()
