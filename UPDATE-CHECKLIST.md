# Update Checklist

When adding or modifying major components, use the appropriate checklist below to make sure all integration points are updated. These checklists exist because the codebase has several registries and cross-references that need to stay in sync.

## Adding a New Protocol Document

A new tracked `.md` file in `.clarity-protocol/` (e.g., we added `goal/open-questions.md`).

- [ ] **`src/clarity_agent/protocol/packet_status.py`** — `DEFAULT_DEPENDENCIES`: add entry with its upstream dependencies
- [ ] **`src/clarity_agent/protocol/packet_status.py`** — `WALK_ORDER`: add in topological order
- [ ] **`src/clarity_agent/protocol/packet_status.py`** — `DOCUMENT_PROCESS`: map to the process that creates/updates it
- [ ] **`src/clarity_agent/protocol/packet_status.py`** — `TEMPLATE_MARKERS`: add a marker string from the template content
- [ ] **`src/clarity_agent/protocol/initialize.py`** — `TEMPLATES`: add relative path and template content
- [ ] **`src/clarity_agent/packet/__init__.py`** — `register_source()`: register a content source (SingleFileSource or DirectorySource)
- [ ] **`src/clarity_agent/packet/__init__.py`** — `_CANONICAL_PARTS`: add to the appropriate part group
- [ ] **`src/clarity_agent/packet/__init__.py`** — Packet views: add to relevant audience-specific views (at least `complete`)
- [ ] **`tests/conftest.py`** — `protocol_dir` fixture: add sample content to the `docs` dict
- [ ] **`processes/clarity-agent.md`** — Update quality assessment table and routing if the document affects workflow
- [ ] **`CONTRIBUTING.md`** — Update dependency graph diagram and file reference table
- [ ] **`tests/test_registry_sync.py`** — If the document is a legitimate exception to any invariant (e.g., not in the packet status graph, or not a packet source), add it to the appropriate exception set (`KNOWN_TEMPLATE_ONLY`, `KNOWN_NON_SOURCE`) with a comment explaining why

## Adding a New Process

A new `.md` file in `processes/` (e.g., we added `discovery-prototype.md`).

Process files are auto-discovered from the `processes/` directory, so no registration code is needed for loading. But these cross-references need updating:

- [ ] **`src/clarity_agent/llm/config.py`** — `_DEFAULT_PROCESS_TIERS`: add process name → tier mapping
- [ ] **`src/clarity_agent/protocol/packet_status.py`** — `DOCUMENT_PROCESS`: if the process creates/updates tracked documents, add mappings
- [ ] **`processes/clarity-agent.md`** — Add routing logic and add to the Process Map section
- [ ] **`src/clarity_agent/mcp/server.py`** — MCP `instructions` string and `run_clarity` inline guide: check if the new process should be mentioned in tool instructions or inlined by `run_clarity`
- [ ] **`processes/README.md`** — Add to the process list and status table
- [ ] **`CONTRIBUTING.md`** — Add to semantic stages table and file reference table

## Adding a New LLM Backend/Provider

A new provider (e.g., alongside existing anthropic, openai, azure_inference, claude_sdk).

- [ ] **`src/clarity_agent/llm/impl/yourprovider.py`** (new file) — Implement `_TIER_DEFAULTS`, client class, and backend class
- [ ] **`src/clarity_agent/llm/config.py`** — `_PROVIDERS`: add entry with package_name, env_var, auth_modes, default_auth_mode
- [ ] **`src/clarity_agent/llm/factory.py`** — `get_provider_tier_defaults()`: add branch returning provider's tier defaults
- [ ] **`src/clarity_agent/llm/factory.py`** — `create_client()`: add branch instantiating your client
- [ ] **`src/clarity_agent/llm/factory.py`** — `create_chat_backend()`: add branch instantiating your backend
- [ ] **`CONTRIBUTING.md`** — Update LLM backends table with provider name, `--provider` value, and env var

## Adding a New Thinker

A new AI or human thinker for failure brainstorming (e.g., `security-thinker`).

Thinkers are auto-discovered from the `thinkers/` directory via `thinker_registry.py`. The main integration points:

- [ ] **`thinkers/yourname-thinker.md`** (new file) — YAML frontmatter (name, display_name, type, execution, modes, prerequisites, tags) + markdown body
- [ ] **`src/clarity_agent/protocol/initialize.py`** — `DEFAULT_CONFIG["thinkers"]["enabled"]`: add to default enabled list if appropriate
- [ ] **`CONTRIBUTING.md`** — Update thinker guides table

## Modifying a Process Guide

When changing a process guide in `processes/`, check for shared patterns that could drift out of sync across files. These are the known patterns where multiple processes reference or repeat the same concept:

### Shared document formats

Some document formats are defined canonically in one process but used by others. When you change the format, update all references:

- [ ] **Failures index format** — Canonical definition in `failure-analysis.md` (§ Failures Index Format). Referenced by `failure-management.md` (Step 4: Update the Failures Index), which tells the AI how to update entries after adding management plans. If you change the index structure, update both.
- [ ] **Failure mode document template** — The analysis section (above the `---` boundary) is defined in `failure-analysis.md` (§ Failure Mode Document Format). The management plan section (below the boundary) is defined in `failure-management.md` (§ Step 3). If you change either side of the boundary, check the other.
- [ ] **Open questions format** — Canonical definition in `problem-clarification.md` (§ Step 5.5, "Document format for open questions"). The resolution process (moving to `resolved-questions.md`) is also defined there. Referenced by `discovery-prototype.md` (Step 6) and `discovery-research.md` (Step 7), which both say "see problem-clarification.md for the resolved question format." If you change the format or resolution process, check all three files.

### Shared writing guidance

Some documents have a defined voice or style that is described in one process but applied by others. When you change the guidance, update all places that describe or exemplify it:

- [ ] **Summary writing style** — Canonical guidance in `problem-clarification.md` (Step 12: Update summary.md), which describes the conversational, "tell a friend" tone. Referenced by `solution-brainstorming.md` (which updates summary.md after a solution exists) and the template in `src/clarity_agent/protocol/initialize.py` (the `summary.md` TEMPLATES entry). If you change the voice or what a good summary contains, update all three.

### Shared principles

Some design principles are stated in one process and referenced from another. When you change the reasoning, update the canonical source and check references:

- [ ] **Severity vs. likelihood philosophy** — Canonical statement in `failure-management.md` (Principle 5). Referenced from `failure-analysis.md` (note after the failure mode template). If you change the reasoning, update the canonical source; the reference should stay brief.

### Cross-process handoffs

Several processes produce output that another process consumes. When you change what a process produces, check its downstream consumers:

- [ ] **failure-analysis → failure-management** — Analysis produces the `---` boundary and "Management Plan: not yet developed" placeholder. Management expects to find and fill it.
- [ ] **problem-clarification → discovery-prototype / discovery-research** — Clarification defines the open questions format. Discovery processes read and update those questions.
- [ ] **failure-brainstorming → failure-analysis** — Brainstorming produces raw failures in a mailbox. Analysis consumes and groups them. The `record-failure` tool schema and `mailbox snapshot` command must stay compatible.

### Check for new shared patterns

The lists above are not exhaustive — new shared patterns emerge as processes evolve. After making your changes:

- [ ] **Scan for new commonalities** — Grep across all process files for the concept you changed. If your change introduces a format, principle, or handoff that now appears in multiple processes, ensure the instances are consistent and that one is designated the canonical source.
- [ ] **Update this checklist** — If you find a new shared pattern, add it to the appropriate subsection above (Shared document formats, Shared principles, or Cross-process handoffs) so future editors know to check it. This checklist only works if it stays current.

## Adding a New Packet View

A named preset that defines which sections appear and in what order for a specific audience.

- [ ] **`src/clarity_agent/packet/__init__.py`** — `register_view()`: define a `PacketView` with id, title, description, and parts
- [ ] **`tests/test_registry_sync.py`** — `TestPacketViewSync`: the new view's source IDs are automatically checked against registered sources
- [ ] **`CONTRIBUTING.md`** — Update the packet views table if one exists

## Adding New Infrastructure

If you add a new subsystem that interacts with protocol documents, processes, LLM providers, or thinkers (e.g., a new renderer, a new registry, a new output format):

- [ ] **`UPDATE-CHECKLIST.md`** (this file) — Add the new subsystem to every checklist section where it's relevant
- [ ] **`tests/test_registry_sync.py`** — Add cross-check tests for the new subsystem's registry if it enumerates protocol documents, processes, or other registered entities

This file is only useful if it stays current. When you add infrastructure that consumes or registers any of the things above, update the checklists so the next person doesn't hit the same "forgot to update X" problem.

## Why This File Exists

We created this after adding `goal/open-questions.md` to the protocol and forgetting to update the packet renderer. The registries in this codebase are deliberately decoupled (packet status graph, packet renderer, init templates, test fixtures are all separate), which makes each component simple but means additions require touching multiple files. This checklist prevents the "forgot to update X" problem.
