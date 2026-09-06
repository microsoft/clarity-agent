"""``clarity models`` — show the models available from a provider.

Answers "what can I actually put in ``--model``?" using the same
credential resolution the app uses, so what it prints is what the app
would offer.
"""

from __future__ import annotations

import argparse
import asyncio

from clarity_agent.llm.config import LLMConfig, LLMConfigError, get_provider_names
from clarity_agent.llm.factory import fetch_model_catalog
from clarity_agent.llm.types import ModelCatalog, ModelInfo

# Column widths, sized for the display names and ids providers actually
# return.  Over-long values push the row wider rather than being cut —
# a truncated model id is useless, and these are meant to be copied.
_LABEL_WIDTH = 11
_NAME_WIDTH = 30
_ID_WIDTH = 32

_ROLE_LABELS: dict[str, str] = {
    "deep": "Deep",
    "default": "Recommended",
    "fast": "Fast",
}


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Register the ``clarity models`` flags on *parser*."""
    parser.add_argument(
        "provider",
        nargs="?",
        default=None,
        choices=sorted(get_provider_names()),
        help="Provider to list (default: the configured one)",
    )
    parser.add_argument(
        "--auth-mode",
        default=None,
        help="Authentication mode (default: the configured one)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch from the provider instead of using the cached list",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "Explain how the list was resolved — which credential was "
            "used and where it came from"
        ),
    )


def cli_main(args: argparse.Namespace) -> None:
    """Print the model catalog for the requested provider."""
    config = _resolve_config(args)
    if getattr(args, "debug", False):
        _print_diagnostics(config)
    catalog = asyncio.run(fetch_model_catalog(config, refresh=args.refresh))
    _print_catalog(config, catalog)


def _print_diagnostics(config: LLMConfig) -> None:
    """Report how credentials resolved, before the listing is attempted.

    Says which credential will be used and, for the Claude Code OAuth
    path, how the lookup went — that store is undocumented and can
    change shape, and this is the difference between "no token found"
    and "token found but the API refused it".

    Prints only presence and provenance.  No credential material, not
    even a length or prefix.
    """
    from clarity_agent.llm.factory import _listing_client

    print("--- debug ---")
    print(f"  provider:     {config.provider}")
    print(f"  auth mode:    {config.auth_mode}")
    print(f"  api key:      {'present' if config.api_key else 'absent'}")
    print(f"  endpoint:     {config.endpoint or '(none)'}")

    if config.provider == "anthropic" and config.auth_mode == "claude_sdk":
        if config.api_key:
            print("  claude code:  not consulted (an API key takes precedence)")
        else:
            from clarity_agent.llm.claude_code_auth import diagnose
            print(f"  claude code:  {diagnose()}")

    client = _listing_client(config)
    if client is None:
        print("  listing:      no usable credential; built-in list only")
    else:
        print(f"  listing:      via {type(client).__name__}")
    print()


def _resolve_config(args: argparse.Namespace) -> LLMConfig:
    """Resolve credentials for the requested provider, without side effects.

    :meth:`LLMConfig.create` persists the provider and auth mode it
    settles on back to ``settings.json`` — sensible when starting a
    session, wrong for a read-only query: asking about a provider you
    aren't using would quietly switch you to it.  So the write is
    suppressed for the duration of the call and the in-memory values
    are put back afterwards.
    """
    from clarity_agent.settings import Settings

    namespace = argparse.Namespace(
        provider=args.provider,
        api_key=None,
        endpoint=None,
        auth_mode=args.auth_mode,
        model=None,
    )

    settings = Settings.current()
    saved = (settings.provider, settings.auth_mode)
    original_save = Settings.save
    Settings.save = lambda self: None  # type: ignore[method-assign]
    try:
        return LLMConfig.create(namespace)
    except LLMConfigError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    finally:
        Settings.save = original_save  # type: ignore[method-assign]
        settings.provider, settings.auth_mode = saved


def _print_catalog(config: LLMConfig, catalog: ModelCatalog) -> None:
    origin = (
        "fetched from the provider" if catalog.source == "provider"
        else "built in (no live listing available)"
    )
    print(f"Provider:      {config.provider}")
    print(f"Auth mode:     {config.auth_mode}")
    print(f"Model list:    {origin}")
    print(f"Default model: {catalog.default_model or '(none)'}")
    if catalog.error:
        # stdout, not stderr: the command succeeded and is showing a
        # usable list.  On stderr this would also jump ahead of the
        # header when a terminal interleaves the two streams.
        print(f"Fetch failed:  {catalog.error}")
        print("               Showing the built-in list instead.")
    print()

    if catalog.free_form:
        print(
            "This provider's models are deployment names you chose when "
            "provisioning,\nso there is no list to fetch. The names below "
            "are the conventional ones;\nany deployment name is valid.\n",
        )

    if catalog.highlighted:
        print("RECOMMENDED")
        _print_header()
        for model in catalog.highlighted:
            _print_model(model, label=_ROLE_LABELS.get(model.role or "", ""))
        print()

    if catalog.rest:
        print(f"OTHER MODELS ({len(catalog.rest)})")
        if not catalog.highlighted:
            _print_header()
        for model in catalog.rest:
            _print_model(model, label="")

    if not catalog.models:
        print("No models found.")


def _print_header() -> None:
    print(
        f"  {'':{_LABEL_WIDTH}} {'NAME':{_NAME_WIDTH}} "
        f"{'MODEL ID':{_ID_WIDTH}} {'CONTEXT':>11}",
    )


def _print_model(model: ModelInfo, *, label: str) -> None:
    context = f"{model.context_window:,}" if model.context_window else "-"
    print(
        f"  {label:{_LABEL_WIDTH}} {model.display_name:{_NAME_WIDTH}} "
        f"{model.id:{_ID_WIDTH}} {context:>11}",
    )
    if model.description:
        # Only Gemini supplies these, and they're already shortened to
        # one line at fetch time.
        print(f"  {'':{_LABEL_WIDTH}} {model.description}")
