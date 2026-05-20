# RAMPART migration log

This file is the running log for the migration of `evals/framework/`
to [RAMPART](https://github.com/microsoft/RAMPART).  See
`evals/README.md` for the user-facing migration banner.

## Pinned version

**RAMPART `==0.1.0`** (released 2026-05-19).

The pin is strict.  Bumps are intentional — open a PR that updates
this file with the new version, the change-log scan, and any
adapter-side updates.  Do not let the pin float.

## Phase 1 — adapter foundation (this PR)

Lands together:

- `pyproject.toml` adds `[project.optional-dependencies] evals = ["rampart==0.1.0"]`.
- `evals/rampart_adapter/` — `ClaritySessionAdapter`, `ClaritySessionSession`,
  `AppManifest`, and a thin config wrapper around `evals/framework/config.py`.
- `evals/cases_rampart/` — one async smoke test proving the wiring.
- `.github/workflows/evals.yml` — second job running `pytest evals/cases_rampart/`.
- `evals/README.md` — migration banner + dependencies subsection.

Nothing in `evals/framework/` or `evals/cases/` changes.

## Mapping decisions (Phase 2 work — not yet implemented)

Each row decides what happens to a Clarity-specific eval feature.
Filled in as the Phase-2 PRs land.

| Feature | Decision | Notes |
|---|---|---|
| Priming with process guide + packet-status report | re-implement on adapter side | Done in Phase 1 — `ClaritySessionSession._build_system_prompt`. |
| `STATUS: ONGOING/CLOSING/DONE` termination | TBD (Phase 2) | Likely a custom `PromptDriver` subclass of `LLMDriver`. |
| Goodbye-detection heuristic | TBD (Phase 2) | Same custom driver. |
| `refusal_acceptable` marker | TBD (Phase 2) | RAMPART has no direct success-short-circuit equivalent; verify a custom evaluator + outcome resolver works. |
| `advisory` decorator | likely keep | Framework-agnostic pytest mark; no RAMPART dependency. |
| Persona-adoption smoke check (turn 1) | TBD (Phase 2) | Precondition `Evaluator`. |
| Substantivity / goal-pursued gates | TBD (Phase 2) | Precondition `Evaluator`s. |
| `--rebuild=conversation\|judgment\|all` | drop | Accept RAMPART's caching model. |
| SHA-256 transcript-fingerprint judge cache | drop | RAMPART has its own cache layer. |
| `summary.md` with `.clarity-protocol/` deep links | TBD (Phase 2) | Either accept RAMPART's report or contribute a hook upstream. |

## Open questions (Phase 1)

- **Tool-call observation under the SDK backend.**  The Claude Agent
  SDK backend invokes ai_actions via Bash, not native tool-use.  In
  that mode, ``backend.on_tool_call`` may not fire, so
  ``Response.tool_calls`` will be empty even when the agent ran an
  action.  Phase 1 ignores this — verify in Phase 2 when an
  evaluator actually depends on tool-call observation.

- **Cumulative cost cap.**  No per-session or per-test cost ceiling
  yet.  RAMPART's execution layer may grow one; if not, add a
  Phase-2 wrapper that aborts a session over a budget.

- **Concurrent-session safety.**  ``asyncio.to_thread`` lets two
  RAMPART tasks each hold their own session simultaneously, but they
  share environment state (env vars, working directory).  Phase 1's
  smoke test exercises ``-n 2`` to flush bridge issues; deeper
  parallelism is a Phase 2/3 concern.
