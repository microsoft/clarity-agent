"""Shared helpers for the OpenAI-format backends.

Used by both :mod:`clarity_agent.llm.impl.openai` (the direct
OpenAI API) and :mod:`clarity_agent.llm.impl.azure_inference`
(Azure-hosted models, which use the OpenAI request shape).  Add to
this module when a new helper needs to behave identically across
both backends; backend-specific behavior stays in the per-backend
file.
"""

from __future__ import annotations

# Models that still take the legacy ``max_tokens`` kwarg.
#
# Maintained as a *denylist* on purpose: ``max_completion_tokens``
# is the forward-compatible default for every model OpenAI has
# released since the o1 series in late 2024, and continues to be
# the way new models accept token-limit hints.  Treating it as the
# default means future / unknown models work out of the box —
# only the shrinking set of pre-o1 chat models needs special
# handling.
#
# Matched by prefix via :func:`uses_legacy_max_tokens` so that
# date-stamped variants (``gpt-4o-2024-08-06``, ``gpt-3.5-turbo-1106``,
# etc.) are covered without enumerating every snapshot.
#
# **Maintenance**: if a vendor ships a new release in the legacy
# families that still requires ``max_tokens`` — unlikely — add its
# prefix here.  If a legacy model gains support for
# ``max_completion_tokens`` and you want to silently migrate, drop
# its prefix.  See issue #59 for the bug that motivated the
# inversion.
_LEGACY_MAX_TOKENS_PREFIXES: tuple[str, ...] = (
    "gpt-3.5",  # gpt-3.5-turbo and all -turbo-* snapshots
    "gpt-4",    # gpt-4, gpt-4-turbo, gpt-4o, gpt-4-32k, gpt-4o-mini,
                # gpt-4-vision-preview, and date-stamped snapshots.
                # The gpt-4 family appears frozen; if OpenAI ever
                # ships a "gpt-4.5"-style name we'll need to make
                # this matcher smarter.
)


def uses_legacy_max_tokens(model: str) -> bool:
    """Return True if *model* needs ``max_tokens`` instead of
    ``max_completion_tokens``.

    Any model name that doesn't match the legacy prefix list is
    assumed to want the modern kwarg — that's the safe default for
    every currently-supported OpenAI model and for unknown /
    future / fine-tuned model names.
    """
    return model.startswith(_LEGACY_MAX_TOKENS_PREFIXES)
