#!/usr/bin/env python3
"""
Refresh Security Catalog

Standalone tool for updating catalogs/security-catalog.csv with the latest
threat intelligence. Runs an interactive AI conversation that searches the
web for updates to OWASP, MITRE ATLAS, and other threat frameworks, then
proposes additions or modifications for human approval.

This is a maintenance tool for the clarity-agent package itself — it updates
a shared asset that ships with the repo. It is separate from the main
clarity-agent flow of control and should be run by engineers periodically.

Usage:
    python dev-tools/refresh-catalog.py
    python dev-tools/refresh-catalog.py --dry-run
    python dev-tools/refresh-catalog.py --provider anthropic
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the clarity_agent package importable when running without pip install
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from clarity_agent.llm import ChatBackend, LLMConfig

CATALOG_RELATIVE = "catalogs/security-catalog.csv"


def _build_system_prompt(catalog_path: Path, *, dry_run: bool) -> str:
    """Build the system prompt for the catalog refresh session."""
    catalog_content = catalog_path.read_text() if catalog_path.exists() else ""

    dry_run_instruction = ""
    if dry_run:
        dry_run_instruction = (
            "\n\n**DRY RUN MODE**: Do NOT write any changes to the CSV file. "
            "Show what you would change, but do not modify the file."
        )

    return f"""\
You are a security threat intelligence analyst maintaining a curated threat \
catalog for the clarity-agent framework.

## Your task

Search the web for the latest versions of these threat frameworks and compare \
them against the current catalog:

1. **OWASP Top 10 for LLM Applications** — search for the latest version
2. **OWASP Agentic AI Security Top 10** — search for the latest version
3. **MITRE ATLAS** — search for new AI attack techniques
4. **Recent CVEs** — search for high-impact CVEs relevant to AI/LLM systems

For each source, compare what you find against the current catalog contents \
below. Identify:
- New entries that should be added
- Existing entries that need updating (e.g., revised descriptions, new mitigations)
- Entries that may be outdated or superseded

## Current catalog

The catalog is at `{catalog_path}` with this CSV format:
```
category,id,title,summary,key_impacts,key_mitigations,source
```

Field conventions:
- `category`: lowercase grouping (e.g., `llm`, `stride`, `agent`)
- `id`: framework identifier (e.g., `LLM01:2025`, `STRIDE-S`, `ASI01`)
- Use semicolons to separate items within `key_impacts` and `key_mitigations`
- Quote fields that contain commas
- `source`: name of the framework or standard

Current contents:
```csv
{catalog_content}
```

## Process

1. Search the web for each framework listed above
2. Compare findings against the current catalog
3. Present a summary of proposed changes (additions, updates, removals)
4. **Wait for human approval** before writing any changes
5. After approval, update the CSV file

Always show the proposed CSV rows before writing them. The human may want to \
edit or reject specific changes.{dry_run_instruction}"""


def main() -> None:
    script_dir = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description="Refresh the security threat catalog with latest intelligence",
    )
    parser.add_argument(
        "--clarity-agent",
        default="",
        help="Path to clarity agent installation (default: repo root)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show proposed changes without writing to the catalog",
    )
    LLMConfig.add_arguments(parser, default_provider="anthropic")

    args = parser.parse_args()

    clarity_agent_dir = Path(args.clarity_agent or script_dir.parent).resolve()
    catalog_path = clarity_agent_dir / CATALOG_RELATIVE

    if not catalog_path.exists():
        print(f"Warning: Catalog not found at {catalog_path}")
        print("A new catalog will be created.\n")

    llm_config = LLMConfig.create(args)

    # The refresh tool operates on the clarity-agent repo itself,
    # so project_dir is the repo root.
    backend: ChatBackend = llm_config.create_chat_backend(
        project_dir=clarity_agent_dir,
        clarity_agent_dir=clarity_agent_dir,
    )

    system_prompt = _build_system_prompt(catalog_path, dry_run=args.dry_run)

    mode_label = " (dry run)" if args.dry_run else ""
    print(f"\n  Security Catalog Refresh{mode_label}")
    print(f"  Catalog: {catalog_path}")
    print(f"  Provider: {llm_config.provider}\n")

    try:
        from prompt_toolkit import prompt as pt_prompt
    except ImportError:
        pt_prompt = None  # type: ignore[assignment]

    def _multiline_input() -> str:
        """Read multi-line input (Alt+Enter to send)."""
        if pt_prompt is not None:
            from prompt_toolkit.key_binding import KeyBindings

            bindings = KeyBindings()

            @bindings.add("escape", "enter")
            def _(event: object) -> None:
                buf = getattr(event, "current_buffer", None) or getattr(
                    getattr(event, "app", None), "current_buffer", None
                )
                if buf:
                    buf.validate_and_handle()

            return pt_prompt(
                "You: ", multiline=True, key_bindings=bindings,
            )
        return input("You: ")

    with backend:
        initial = "Please search the web for the latest threat intelligence and compare against the current catalog."
        response = backend.chat(initial, system_prompt=system_prompt)
        print(f"Assistant: {response}\n")

        print("(Enter for newline, Alt+Enter to send, 'done' to end)\n")
        while True:
            try:
                user_input = _multiline_input()
            except (EOFError, KeyboardInterrupt):
                print("\nEnding catalog refresh.")
                break
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "done"):
                print("\nEnding catalog refresh.")
                break

            response = backend.chat(user_input)
            print(f"Assistant: {response}\n")


if __name__ == "__main__":
    main()
