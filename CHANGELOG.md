# Changelog

All notable changes to Clarity are documented here. This project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

- Windows desktop builds now ship an NSIS per-user installer (`.exe`) instead
  of the machine-wide `.msi`. Installs no longer require UAC elevation. Users
  upgrading should uninstall the old machine-wide "Clarity" manually.

## [0.1.2] - 2026-05-29

### Added
- Add Static Text guidelines to AGENTS.md
- Add copy button to Clarity chat responses (#51)
- Add Clarity Agent Discord community link to README and CONTRIBUTING

### Changed
- Snippet: MCP-first instructions, bump schema to v2 (#79)
- Improve project embed snippet handling and tests
- Make everything run by ID/path, not name!
- Better open dialog
- Clean up URL building
- Clean up update links
- Python and JS parts of new udpate flow
- Update changes
- probe goal framings in problem-clarification; add means-vs-ends eval (#10)
- chore: add *.tsbuildinfo to .gitignore and untrack web/tsconfig.tsbuildinfo
- docs: document root cause analysis and fix for failing web CI job
- Initial plan
- No longer keep web/dist in the repo.
- chore: rebuild web/dist/
- Lint fix
- Produce clearer errors when a user has a bad Claude MCP configuration.
- Test fix
- ESLint fixes
- Lint and pyright fixes
- Dist updates
- Clean up layout further, including project open/create
- Restructure layout logic
- Bump idna from 3.11 to 3.15
- Removed .AppImage references
- Removed AppImage reference
- Made discord more discoverable.
- Update README.md and CONTRIBUTING.md
- Handle partial failures during session start
- Surface gh auth errors (etc) to the user
- Merge origin/main and resolve dist conflicts
- chore: rebuild web/dist/

### Fixed
- Fix "Recents" menu: Key by ID, not name!
- Fix GHCP path on mac
- Fix it all up cleanly
- Fix max_tokens vs max_completion_tokens for OAI backend
- fix(web): handle stale projects and add remove-from-list UX (#38)
- fix: capture traceback to clarity-crash.log on startup failure
- fix: save dialog on Windows drops .docx extension

## [0.1.1] - 2026-04-08

### Added
- Add CHANGELOG.md and auto-generate entries on version bump
- Add .gitkeep for binaries/_internal to fix CI

### Changed
- Update cryptography to 46.0.7
- Added a  tighter recomendation summary and more reference material.  Added more thoughts on integration points and architecture.
- Minor fixes to the integration strategy draft. Added a section on testing and validation, and clarified some of the language around the proposed approach.
- The table now shows the top 5 in strategic order:
- Prioritization criteria (in Overview, applies to both sections): 5 explicit criteria — developer adoption, extensibility surface, risk surface, effort-to-reach ratio, and unique strategic relevance. Makes the "why is this high/medium/low priority" reasoning transparent and repeatable.

### Fixed
- Fix missing fields in zero-state flow
- Fix event drain on stop
- Fix up artifacts dir in releases
- Fixing Windows desktop installer issues

## [0.1.0] - 2026-04-07

Initial release.

### Added
- Structured thinking protocol with problem clarification, solution design,
  failure brainstorming, and failure analysis phases.
- Web UI with real-time streaming.
- Desktop app (Tauri) with MSI, DMG, and AppImage packaging.
- LLM provider support: Anthropic, OpenAI, Azure AI Inference, Azure OpenAI
  (Entra ID), Claude CLI.
- Multi-thinker brainstorming with configurable thinker personas.
- Project management with `clarity embed` for coding agent integration.
- Credential storage via system keyring.
- DOCX export for protocol documents.

[Unreleased]: https://github.com/microsoft/clarity-agent/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/microsoft/clarity-agent/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/microsoft/clarity-agent/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/microsoft/clarity-agent/releases/tag/v0.1.0
