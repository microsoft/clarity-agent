# Releasing Clarity

## Quick release

```bash
# 1. Bump version in all project files
python scripts/bump-version.py 1.2.0

# 2. Commit and tag
git commit -am "Release v1.2.0"
git tag v1.2.0

# 3. Push — this triggers the release workflow
git push origin main v1.2.0
```

The release workflow builds macOS, Windows, and Linux artifacts, then creates a GitHub Release with all of them attached.

After the workflow finishes, validate the auto-updater end-to-end — see [AUTOUPDATE-TESTING.md](AUTOUPDATE-TESTING.md).

## What gets built

| Platform | Artifacts                        |
|----------|----------------------------------|
| macOS    | `Clarity.app`, `.dmg`            |
| Windows  | `.msi` installer                 |
| Linux    | `.deb` package, `.AppImage`      |

Release builds use `--release` (optimized, stripped). Debug builds are
roughly 50% larger.

## Version management

The version lives in three files that must stay in sync:

- `pyproject.toml`
- `src-tauri/tauri.conf.json`
- `src-tauri/Cargo.toml`

Always use the bump script rather than editing manually:

```bash
python scripts/bump-version.py          # show current version
python scripts/bump-version.py 1.2.0    # set new version
```

The bump script also stamps `CHANGELOG.md` — it replaces the `[Unreleased]` section with a dated version heading built from commits since the last tag, then adds a fresh `[Unreleased]` above it. Review the generated entry before committing; edit categories or wording as needed.

## Local builds

To build the desktop app locally (for testing before a release):

```bash
# Debug build (faster, larger binary)
uv run python clarity.py install

# Release build (optimized, what users get)
uv run python clarity.py install --release
```

Outputs land in `dist/`.

## Troubleshooting

**Build fails locally**: Run `uv run python clarity.py install` and check which step fails. Prerequisites are Rust, Node.js, and Python with the `bundle` extra (`pip install -e ".[bundle]"`).

**CI release fails**: Check the Actions tab for the failed run. Common issues:
- Missing system dependencies on Linux (the workflow installs them, but package names can change between Ubuntu versions)
- Stale Cargo cache (delete the cache in Actions → Caches if Rust compilation fails after a dependency update)
- DMG creation fails on macOS if a previous Clarity volume is still mounted

**Version mismatch**: If `clarity --version` shows a different version than expected, run `python scripts/bump-version.py` (no argument) to check which files have which version, then re-run with the correct version.
