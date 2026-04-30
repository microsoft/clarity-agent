# Changelog

All notable changes to Clarity are documented here. This project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/microsoft/clarity-agent/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/microsoft/clarity-agent/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/microsoft/clarity-agent/releases/tag/v0.1.0
