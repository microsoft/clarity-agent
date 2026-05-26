"""Tests for ``clarity_agent.setup.snippet``.

Covers the public surface around the AGENTS.md Clarity-block
maintenance loop:

- :func:`render_snippet` — template substitution against a
  :class:`~clarity_agent.setup.layout.ProjectLayout`, with mode-aware
  path forms (embedded uses repo-relative, userspace uses absolute).
- :func:`parse_meta` — round-trip + tolerance for malformed input.
- :func:`ensure_agents_md` — every cell in the state table from its
  docstring: file-absent, file-without-markers, half-markers, in-sync
  block, meta drift, body drift, write-only-if-different (the watcher
  contract).
- :func:`has_snippet` — predicate used by ``doctor``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clarity_agent.setup.layout import Mode, ProjectLayout
from clarity_agent.setup.snippet import (
    BEGIN_DELIMITER,
    END_DELIMITER,
    SCHEMA_VERSION,
    EnsureStatus,
    ensure_agents_md,
    ensure_for_project,
    has_snippet,
    parse_meta,
    render_snippet,
    snippet_path,
)

# ---------------------------------------------------------------------------
# Fixtures: build minimal layouts for either mode
# ---------------------------------------------------------------------------


def _userspace_layout(tmp_path: Path) -> ProjectLayout:
    """A USERSPACE layout: project on disk, app bundle elsewhere."""
    project = tmp_path / "project"
    bundle = tmp_path / "bundle"
    project.mkdir()
    bundle.mkdir()
    (bundle / "processes").mkdir()
    return ProjectLayout(
        mode=Mode.USERSPACE,
        project_dir=project,
        clarity_agent_dir=bundle,
        protocol_dir=project / "Clarity Protocol",
    )


def _embedded_layout(tmp_path: Path) -> ProjectLayout:
    """An EMBEDDED layout: clarity-agent lives at .clarity-agent/."""
    project = tmp_path / "repo"
    project.mkdir()
    embedded = project / ".clarity-agent"
    embedded.mkdir()
    (embedded / "processes").mkdir()
    return ProjectLayout(
        mode=Mode.EMBEDDED,
        project_dir=project,
        clarity_agent_dir=embedded,
        protocol_dir=project / ".clarity-protocol",
    )


# ---------------------------------------------------------------------------
# snippet_path / template integrity
# ---------------------------------------------------------------------------


class TestSnippetPath:
    def test_returns_existing_template(self) -> None:
        path = snippet_path()
        assert path.exists()
        assert path.name == "snippet.md"

    def test_template_has_markers(self) -> None:
        # If this fails, the template is structurally broken — every
        # render() call would also fail.  Cheap to assert up front.
        content = snippet_path().read_text(encoding="utf-8")
        assert BEGIN_DELIMITER in content
        assert END_DELIMITER in content


# ---------------------------------------------------------------------------
# render_snippet
# ---------------------------------------------------------------------------


class TestRenderSnippet:
    def test_substitutes_userspace_values(self, tmp_path: Path) -> None:
        layout = _userspace_layout(tmp_path)
        out = render_snippet(layout)
        # No placeholders remain.
        assert "{{MODE}}" not in out
        assert "{{PROTOCOL_DIR_NAME}}" not in out
        assert "{{PROCESSES_DIR}}" not in out
        # USERSPACE renders the visible protocol-dir name and the
        # absolute bundle path.
        assert "Clarity Protocol" in out
        assert layout.processes_dir.as_posix() in out

    def test_substitutes_embedded_values_with_relative_paths(
        self, tmp_path: Path,
    ) -> None:
        # EMBEDDED uses repo-relative paths so the rendered block
        # commits identically across machines — the whole point of
        # the dual-mode split.
        layout = _embedded_layout(tmp_path)
        out = render_snippet(layout)
        assert ".clarity-protocol" in out
        assert ".clarity-agent/processes" in out
        # Absolute path from tmp_path must NOT leak in.
        assert str(tmp_path) not in out

    def test_returns_only_marker_bounded_block(self, tmp_path: Path) -> None:
        # The template carries an out-of-band ``markdownlint-disable``
        # comment above ``<!-- clarity-begin -->`` to suppress an
        # MD041 false-positive on the fragment.  That must NOT show
        # up in the rendered output — only what's between the markers.
        layout = _userspace_layout(tmp_path)
        out = render_snippet(layout)
        assert out.startswith(BEGIN_DELIMITER)
        # End marker is the last meaningful token (modulo trailing \n).
        assert out.rstrip("\n").endswith(END_DELIMITER)
        assert "markdownlint" not in out

    def test_meta_round_trips(self, tmp_path: Path) -> None:
        # The rendered block's meta header must parse back to the
        # exact values that drove the render — that's the contract
        # ensure_agents_md's drift check depends on.
        layout = _userspace_layout(tmp_path)
        out = render_snippet(layout)
        meta = parse_meta(out)
        assert meta == {
            "schema_version": str(SCHEMA_VERSION),
            "mode": "userspace",
            "protocol_dir_name": "Clarity Protocol",
            "processes_dir": layout.processes_dir.as_posix(),
        }


# ---------------------------------------------------------------------------
# parse_meta
# ---------------------------------------------------------------------------


class TestParseMeta:
    def test_returns_none_when_no_meta_comment(self) -> None:
        assert parse_meta(f"{BEGIN_DELIMITER}\nbody\n{END_DELIMITER}") is None

    def test_returns_none_on_unterminated_meta(self) -> None:
        # Open comment without closing ``-->``: tolerated as "no meta",
        # which makes ensure_agents_md re-render.
        bad = f"{BEGIN_DELIMITER}\n<!-- clarity-meta\nkey: value\n"
        assert parse_meta(bad) is None

    def test_returns_none_on_malformed_line(self) -> None:
        # A non-empty, non-blank line without ``key: value`` shape:
        # treat as malformed → rewrite.
        bad = (
            f"{BEGIN_DELIMITER}\n"
            "<!-- clarity-meta\n"
            "key: value\n"
            "just-a-bare-word\n"
            "-->\n"
            f"{END_DELIMITER}"
        )
        assert parse_meta(bad) is None

    def test_tolerates_blank_lines_and_extra_whitespace(self) -> None:
        block = (
            f"{BEGIN_DELIMITER}\n"
            "<!-- clarity-meta\n"
            "  schema_version: 1  \n"
            "\n"
            "mode:   embedded\n"
            "-->\n"
            f"{END_DELIMITER}"
        )
        assert parse_meta(block) == {"schema_version": "1", "mode": "embedded"}


# ---------------------------------------------------------------------------
# has_snippet
# ---------------------------------------------------------------------------


class TestHasSnippet:
    def test_true_when_both_markers_present(self, tmp_path: Path) -> None:
        f = tmp_path / "AGENTS.md"
        f.write_text(f"# Stuff\n{BEGIN_DELIMITER}\ncontent\n{END_DELIMITER}\n")
        assert has_snippet(f) is True

    def test_false_when_only_begin_marker(self, tmp_path: Path) -> None:
        # Damaged file: one marker without the other.  has_snippet
        # treats this as "no snippet" so ensure_agents_md's append
        # path runs.
        f = tmp_path / "AGENTS.md"
        f.write_text(f"# Stuff\n{BEGIN_DELIMITER}\nopen ended\n")
        assert has_snippet(f) is False

    def test_false_when_file_missing(self, tmp_path: Path) -> None:
        assert has_snippet(tmp_path / "nope.md") is False


# ---------------------------------------------------------------------------
# ensure_agents_md — full state-table coverage
# ---------------------------------------------------------------------------


class TestEnsureAgentsMd:
    def test_creates_file_when_absent(self, tmp_path: Path) -> None:
        layout = _userspace_layout(tmp_path)
        assert not layout.agents_md.exists()
        status = ensure_agents_md(layout)
        assert status is EnsureStatus.CREATED
        # The new file contains exactly our block (no extra content).
        content = layout.agents_md.read_text()
        assert content.startswith(BEGIN_DELIMITER)
        assert content.rstrip("\n").endswith(END_DELIMITER)

    def test_appends_block_to_file_without_markers(
        self, tmp_path: Path,
    ) -> None:
        layout = _userspace_layout(tmp_path)
        layout.agents_md.write_text("# Project AGENTS\n\nUser stuff here.\n")
        status = ensure_agents_md(layout)
        assert status is EnsureStatus.UPDATED
        content = layout.agents_md.read_text()
        # User content preserved verbatim.
        assert "User stuff here." in content
        # Our block appears after.
        assert content.index("User stuff here.") < content.index(BEGIN_DELIMITER)

    def test_appends_when_only_one_marker_present(
        self, tmp_path: Path,
    ) -> None:
        # File has BEGIN but no END — has_snippet / _extract_block
        # both treat this as "no snippet", so ensure appends.
        layout = _userspace_layout(tmp_path)
        layout.agents_md.write_text(
            f"existing\n{BEGIN_DELIMITER}\nhalf a block\n",
        )
        status = ensure_agents_md(layout)
        assert status is EnsureStatus.UPDATED
        # The damaged content stays — we don't try to salvage it,
        # we just add a fresh, well-formed block after it.
        content = layout.agents_md.read_text()
        assert "half a block" in content
        # Two BEGIN markers now: the damaged one and our fresh one.
        assert content.count(BEGIN_DELIMITER) == 2
        assert content.count(END_DELIMITER) == 1

    def test_unchanged_when_block_already_current(
        self, tmp_path: Path,
    ) -> None:
        layout = _userspace_layout(tmp_path)
        ensure_agents_md(layout)
        mtime_before = layout.agents_md.stat().st_mtime_ns
        # Re-call must report UNCHANGED *and* not rewrite the file —
        # important for filesystem watchers in host coding agents.
        status = ensure_agents_md(layout)
        assert status is EnsureStatus.UNCHANGED
        assert layout.agents_md.stat().st_mtime_ns == mtime_before

    def test_rewrites_when_meta_drifts_against_layout(
        self, tmp_path: Path,
    ) -> None:
        # First ensure under one layout, then "drift" the meta by
        # editing the file to look like a stale rendering, then
        # re-ensure under the same layout: the rewrite should
        # restore the current values.
        layout = _userspace_layout(tmp_path)
        ensure_agents_md(layout)
        content = layout.agents_md.read_text()
        # Tamper with the meta to look stale.
        bogus = content.replace(
            "protocol_dir_name: Clarity Protocol",
            "protocol_dir_name: .clarity-protocol",
        )
        assert bogus != content
        layout.agents_md.write_text(bogus)

        status = ensure_agents_md(layout)
        assert status is EnsureStatus.UPDATED
        # Restored.
        assert "protocol_dir_name: Clarity Protocol" in layout.agents_md.read_text()

    def test_rewrites_when_body_drifts_inside_markers(
        self, tmp_path: Path,
    ) -> None:
        # User edits inside the managed block: we overwrite on the
        # next reconcile.  Outside-the-markers content stays.
        layout = _userspace_layout(tmp_path)
        layout.agents_md.write_text(
            "# Project AGENTS\n\nUser content.\n\n",
        )
        ensure_agents_md(layout)  # appends block
        original = layout.agents_md.read_text()

        # Sneak in an edit inside the markers.
        tampered = original.replace(
            "Move quickly through what's obvious.",
            "Move slowly and double-check everything.",
        )
        assert tampered != original
        layout.agents_md.write_text(tampered)

        status = ensure_agents_md(layout)
        assert status is EnsureStatus.UPDATED
        restored = layout.agents_md.read_text()
        assert "Move quickly through what's obvious." in restored
        # User's outside-the-markers content untouched.
        assert "User content." in restored

    def test_preserves_content_outside_markers_across_rewrite(
        self, tmp_path: Path,
    ) -> None:
        layout = _userspace_layout(tmp_path)
        prefix = "# Project AGENTS\n\nProject-specific guidance up top.\n\n"
        suffix = "\n\n## Other section\n\nMore prose.\n"
        # First add our block, then wrap with prefix/suffix as if the
        # user maintains material around it.
        ensure_agents_md(layout)
        block = layout.agents_md.read_text().rstrip("\n")
        layout.agents_md.write_text(prefix + block + suffix)

        # Force a rewrite via meta drift.
        tampered = layout.agents_md.read_text().replace(
            "schema_version: 1", "schema_version: 0",
        )
        layout.agents_md.write_text(tampered)

        status = ensure_agents_md(layout)
        assert status is EnsureStatus.UPDATED
        out = layout.agents_md.read_text()
        assert "Project-specific guidance up top." in out
        assert "## Other section" in out
        assert "More prose." in out


# ---------------------------------------------------------------------------
# render contract — embedded vs userspace differ on path form
# ---------------------------------------------------------------------------


# Parametrize value for the EMBEDDED case: a literal path-prefix
# string we expect to find at the start of ``processes_dir``.  The
# USERSPACE case uses ``None`` as a sentinel meaning "instead of a
# literal prefix, assert the rendered path is absolute" — needed
# because absolute paths look different across platforms
# (``/usr/...`` on POSIX, ``C:/Users/...`` on Windows) so a
# ``startswith("/")`` check would falsely fail on Windows CI.
@pytest.mark.parametrize(
    ("layout_factory", "expected_protocol", "expected_processes_prefix"),
    [
        (_userspace_layout, "Clarity Protocol", None),    # absolute path
        (_embedded_layout, ".clarity-protocol", ".clarity-agent/"),  # relative
    ],
)
def test_mode_drives_path_form_in_render(
    tmp_path: Path,
    layout_factory: object,
    expected_protocol: str,
    expected_processes_prefix: str | None,
) -> None:
    layout = layout_factory(tmp_path)  # type: ignore[operator]
    out = render_snippet(layout)
    meta = parse_meta(out)
    assert meta is not None
    assert meta["protocol_dir_name"] == expected_protocol
    if expected_processes_prefix is None:
        # USERSPACE — absolute path expected, but the actual root
        # form is platform-specific.  Use ``Path.is_absolute`` so
        # the test passes on both POSIX and Windows runners.
        assert Path(meta["processes_dir"]).is_absolute()
    else:
        assert meta["processes_dir"].startswith(expected_processes_prefix)


# ---------------------------------------------------------------------------
# ensure_for_project — the shared runtime touchpoint
# ---------------------------------------------------------------------------


class TestEnsureForProject:
    """The reconcile-on-touch helper used by ``WebSessionAdapter.start``,
    ``create_app``, and the MCP server's ``read_behaviors``.  It must
    never write under any of the "no-op by design" conditions —
    those tests are the contract."""

    def test_writes_for_a_clean_userspace_layout(
        self, tmp_path: Path,
    ) -> None:
        # Standard happy path: layout detectable, nothing's stale →
        # ensure_agents_md runs and reports its real status.  This
        # is the case the production code's ``create_app`` hook
        # primarily exists for.
        project = tmp_path / "ws"
        project.mkdir()
        (project / "Clarity Protocol").mkdir()
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        (bundle / "processes").mkdir()

        status = ensure_for_project(project, bundle)
        assert status is EnsureStatus.CREATED
        assert (project / "AGENTS.md").exists()
        # Idempotent on re-call.
        assert ensure_for_project(project, bundle) is EnsureStatus.UNCHANGED

    def test_skips_for_clarity_agent_source_repo(
        self, tmp_path: Path,
    ) -> None:
        # The structural source-repo markers (``clarity.py`` +
        # ``src/clarity_agent/``) drive the skip — not a path-equality
        # check.  Even if a separate bundled clarity_agent_dir is
        # passed in, the source-repo property of *project_dir* alone
        # is enough to opt out of auto-management (the hand-curated
        # AGENTS.md must stay untouched).
        repo = tmp_path / "clarity-agent-checkout"
        repo.mkdir()
        (repo / "clarity.py").write_text("# entry\n")
        (repo / "src" / "clarity_agent").mkdir(parents=True)
        (repo / ".clarity-protocol").mkdir()
        # AGENTS.md with content we want preserved verbatim.
        hand_curated = "# Hand-curated for the source repo\n"
        (repo / "AGENTS.md").write_text(hand_curated)

        bundle = tmp_path / "bundle"
        bundle.mkdir()
        (bundle / "processes").mkdir()

        status = ensure_for_project(repo, bundle)
        assert status is None
        # Unchanged on disk — the source repo's curated AGENTS.md is
        # the contract we're protecting here.
        assert (repo / "AGENTS.md").read_text() == hand_curated

    def test_skips_when_no_layout_detected(self, tmp_path: Path) -> None:
        # Fresh directory with no Clarity markers → no-op.  Mode
        # selection belongs in explicit setup entry points, not
        # this runtime helper.
        project = tmp_path / "empty"
        project.mkdir()
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        (bundle / "processes").mkdir()

        assert ensure_for_project(project, bundle) is None
        assert not (project / "AGENTS.md").exists()

    def test_skips_on_broken_layout(self, tmp_path: Path) -> None:
        # LayoutBroken variants are also "runtime shouldn't touch
        # AGENTS.md" — the launcher's open endpoint surfaces the
        # repair prompt instead.  ensure_for_project just returns
        # None.
        project = tmp_path / "partial"
        project.mkdir()
        (project / ".clarity-protocol").mkdir()  # dotted only → PARTIAL_EMBEDDED_INSTALL
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        (bundle / "processes").mkdir()

        assert ensure_for_project(project, bundle) is None
        assert not (project / "AGENTS.md").exists()
