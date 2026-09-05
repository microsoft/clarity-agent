"""Building and caching :class:`ModelCatalog` objects.

Two jobs live here:

1. **Construction helpers** shared by every provider implementation —
   turning a backend's ``TIER_DEFAULTS`` / ``MODEL_CONTEXT_WINDOWS``
   tables (or a live provider listing) into a
   :class:`~clarity_agent.llm.types.ModelCatalog`.
2. **Caching**, so opening the model picker doesn't cost a network
   round-trip every time.  Live listings are cached in memory and on
   disk for :data:`CACHE_TTL_SECONDS`.

Provider implementations expose ``builtin_catalog()`` (synchronous, no
network) and ``fetch_models(config)`` (async, live).  ``llm/factory.py``
dispatches to both; nothing else should need to import this module
directly.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from clarity_agent.llm.types import ModelCatalog, ModelInfo

# The three highlight roles, in priority order.  Used for three things
# at once, deliberately: which role a model keeps when it fills more
# than one, what order highlighted models are listed in, and which
# entry :func:`default_model_for` selects.
#
# ``default`` leads because the role means exactly what it says — the
# model we use unless the user picks otherwise.  ``deep`` is the
# heavier option offered alongside it, and ``fast`` the lighter one;
# neither is what we reach for on its own.
ROLE_ORDER: tuple[str, ...] = ("default", "deep", "fast")

# How long a live provider listing stays fresh.  Model lineups change
# on the order of weeks, so a day is generous but still picks up new
# releases without the user having to hit refresh.
CACHE_TTL_SECONDS: int = 24 * 60 * 60

# Cache file, relative to the Clarity data directory.
_CACHE_FILENAME = "model-catalog.json"

# Process-lifetime cache, so repeated picker opens don't re-read disk.
_MEMORY_CACHE: dict[str, tuple[float, ModelCatalog]] = {}

# Trailing release-date stamp on Anthropic-style ids
# ("claude-sonnet-4-5-20250929").  Stripped before humanizing.
_DATE_SUFFIX_RE = re.compile(r"-\d{8}$")

# Segments that should not be title-cased the ordinary way.
_WORD_OVERRIDES: dict[str, str] = {
    "gpt": "GPT",
    "ai": "AI",
    "3n": "3n",
}


# ---------------------------------------------------------------------------
# Display names
# ---------------------------------------------------------------------------

def humanize_model_id(model_id: str) -> str:
    """Derive a readable display name from a model identifier.

    Used for providers whose listings carry no display name of their
    own (OpenAI) and for built-in catalogs.  Consecutive numeric
    segments are rejoined with a dot, so Anthropic's dashed versions
    read the way people write them::

        claude-opus-5              -> Claude Opus 5
        claude-sonnet-4-6          -> Claude Sonnet 4.6
        claude-sonnet-4-5-20250929 -> Claude Sonnet 4.5
        gpt-5.4-mini               -> GPT 5.4 Mini
        gemini-3.1-flash-lite      -> Gemini 3.1 Flash Lite

    Anything unrecognizable is returned close to as-is rather than
    mangled — a slightly ugly name beats a wrong one.
    """
    stripped = _DATE_SUFFIX_RE.sub("", model_id.strip())
    if not stripped:
        return model_id

    segments = [s for s in stripped.split("-") if s]
    if not segments:
        return model_id

    # Collapse runs of purely-numeric segments into dotted versions:
    # ["claude", "sonnet", "4", "6"] -> ["claude", "sonnet", "4.6"].
    merged: list[str] = []
    for segment in segments:
        if segment.isdigit() and merged and _is_version(merged[-1]):
            merged[-1] = f"{merged[-1]}.{segment}"
        else:
            merged.append(segment)

    return " ".join(_titlecase_segment(s) for s in merged)


def _is_version(segment: str) -> bool:
    """True if *segment* is a bare number or dotted version ("4", "4.6")."""
    return bool(segment) and all(part.isdigit() for part in segment.split("."))


def _titlecase_segment(segment: str) -> str:
    override = _WORD_OVERRIDES.get(segment.lower())
    if override is not None:
        return override
    if _is_version(segment):
        return segment
    return segment[:1].upper() + segment[1:]


# ---------------------------------------------------------------------------
# Catalog construction
# ---------------------------------------------------------------------------

def assign_roles(
    models: Sequence[ModelInfo],
    recommended: Mapping[str, str],
) -> list[ModelInfo]:
    """Tag the models named in *recommended* with their highlight role.

    *recommended* is a ``{role: model_id}`` mapping — a backend's
    ``TIER_DEFAULTS`` table.  Roles are applied in :data:`ROLE_ORDER`
    and each model takes at most one, so a provider whose ``default``
    and ``deep`` are the same model shows that model once.

    Models already carrying a role keep it.  Ids in *recommended* that
    aren't in *models* are ignored — the caller decides whether a
    missing recommendation is worth surfacing.
    """
    role_for: dict[str, str] = {}
    for role in ROLE_ORDER:
        model_id = recommended.get(role)
        if model_id and model_id not in role_for:
            role_for[model_id] = role

    return [
        m if m.role is not None else replace(m, role=role_for.get(m.id))
        for m in models
    ]


def order_models(models: Sequence[ModelInfo]) -> list[ModelInfo]:
    """Sort highlighted models to the front, preserving order otherwise.

    ``sorted`` is stable, so unhighlighted models keep whatever order
    the provider returned them in.
    """
    rank = {role: i for i, role in enumerate(ROLE_ORDER)}
    unranked = len(ROLE_ORDER)
    return sorted(models, key=lambda m: rank.get(m.role or "", unranked))


def default_model_for(recommended: Mapping[str, str]) -> str:
    """Pick the model to use when the user has never chosen one.

    Prefers the ``default`` entry, falling back through
    :data:`ROLE_ORDER` for providers that don't declare one.

    Note this is about a *fresh* install.  Migrating an existing user
    is a different question with a different answer: until the tier
    collapse lands, every process maps to the ``"deep"`` tier, so what
    someone is running today is their deep model, and their settings
    migration has to read that rather than this.
    """
    for role in ROLE_ORDER:
        model_id = recommended.get(role)
        if model_id:
            return model_id
    return ""


def build_catalog(
    *,
    recommended: Mapping[str, str],
    context_windows: Mapping[str, int] | None = None,
    model_ids: Iterable[str] | None = None,
    display_names: Mapping[str, str] | None = None,
    descriptions: Mapping[str, str] | None = None,
    source: str = "builtin",
    free_form: bool = False,
    error: str | None = None,
) -> ModelCatalog:
    """Assemble a :class:`ModelCatalog` from provider tables or a listing.

    Args:
        recommended: ``{role: model_id}`` — the backend's
            ``TIER_DEFAULTS``.  Drives highlighting and the default.
        context_windows: ``{model_id: tokens}`` — the backend's
            ``MODEL_CONTEXT_WINDOWS``.  Also supplies the model list
            when *model_ids* is omitted.
        model_ids: Explicit id list, in the order the provider
            returned them.  When omitted, the catalog is built from
            *recommended* plus *context_windows* — which is what a
            built-in catalog wants, since those two tables are the
            vetted model names this codebase already ships.
        display_names: Names from a live listing, keyed by id.  Ids
            not present fall back to :func:`humanize_model_id`.
        descriptions: Optional one-liners keyed by id.
        source: ``"provider"`` or ``"builtin"``.
        free_form: True when the user must type an id (Azure).
        error: Message from a failed live fetch, if any.
    """
    context_windows = context_windows or {}
    display_names = display_names or {}
    descriptions = descriptions or {}

    if model_ids is None:
        # Built-in case: recommendations first (in role order), then any
        # other model the context-window table knows about.  Providers
        # whose ``default`` and ``deep`` are the same model yield a
        # duplicate here, hence the de-dupe.
        candidates = [recommended[role] for role in ROLE_ORDER if recommended.get(role)]
        candidates += list(context_windows)
    else:
        candidates = list(model_ids)
    ids = list(dict.fromkeys(candidates))  # de-dupe, keep first occurrence

    models = [
        ModelInfo(
            id=model_id,
            display_name=display_names.get(model_id) or humanize_model_id(model_id),
            description=descriptions.get(model_id),
            context_window=context_windows.get(model_id),
        )
        for model_id in ids
    ]

    models = order_models(assign_roles(models, recommended))

    default = default_model_for(recommended)
    if default and models and not any(m.id == default for m in models):
        # A recommendation the provider no longer lists.  Keep it
        # selectable rather than silently defaulting to something the
        # user never asked for.
        #
        # Only when the listing found *something*: a provider that
        # returned nothing has told us nothing, and inventing a
        # one-model catalog out of that would hide the anomaly from
        # ``fetch_model_catalog``, which falls back to the built-in
        # list when a live catalog comes back empty.
        models.insert(0, ModelInfo(
            id=default,
            display_name=display_names.get(default) or humanize_model_id(default),
            # Whichever role selected it — normally "default", but a
            # provider that declares no default entry falls further
            # down ROLE_ORDER, and the label has to match.
            role=next(
                (r for r in ROLE_ORDER if recommended.get(r) == default),
                None,
            ),
            context_window=context_windows.get(default),
        ))
    if not default and models:
        default = models[0].id

    return ModelCatalog(
        models=models,
        default_model=default,
        source=source,
        free_form=free_form,
        error=error,
    )


def describe_fetch_error(exc: BaseException) -> str:
    """Render *exc* as a short message for :attr:`ModelCatalog.error`.

    Provider SDKs raise verbose errors; the picker only has room for a
    line.  The type name is kept because "AuthenticationError" is the
    part that tells a user what to do.
    """
    message = str(exc).strip().splitlines()
    detail = message[0] if message else ""
    text = f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__
    return text[:200]


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

def cache_key(provider: str, auth_mode: str | None) -> str:
    """Cache key for a provider + auth mode pair.

    Auth mode is part of the key because it can change which models
    are reachable — Anthropic's ``claude_sdk`` mode has no API key to
    enumerate with, so its catalog is the built-in one.
    """
    return f"{provider}:{auth_mode or 'default'}"


def _cache_path() -> Path:
    from clarity_agent.app_paths import clarity_data_dir
    return clarity_data_dir() / _CACHE_FILENAME


def _read_cache_file() -> dict[str, Any]:
    try:
        path = _cache_path()
        if not path.exists():
            return {}
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}  # corrupt or unreadable — treat as a cold cache
    return data if isinstance(data, dict) else {}


def _catalog_from_dict(data: Mapping[str, Any]) -> ModelCatalog | None:
    """Rebuild a catalog from its cached JSON form, or ``None`` if malformed."""
    try:
        models = [
            ModelInfo(
                id=str(m["id"]),
                display_name=str(m.get("display_name") or m["id"]),
                role=m.get("role"),
                description=m.get("description"),
                context_window=m.get("context_window"),
            )
            for m in data.get("models", [])
        ]
    except (KeyError, TypeError):
        return None
    return ModelCatalog(
        models=models,
        default_model=str(data.get("default_model", "")),
        source=str(data.get("source", "provider")),
        free_form=bool(data.get("free_form", False)),
        error=data.get("error"),
    )


def _catalog_to_dict(catalog: ModelCatalog) -> dict[str, Any]:
    return {
        "models": [
            {
                "id": m.id,
                "display_name": m.display_name,
                "role": m.role,
                "description": m.description,
                "context_window": m.context_window,
            }
            for m in catalog.models
        ],
        "default_model": catalog.default_model,
        "source": catalog.source,
        "free_form": catalog.free_form,
        "error": catalog.error,
    }


def load_cached(key: str) -> ModelCatalog | None:
    """Return the cached catalog for *key*, or ``None`` if absent or stale."""
    now = time.time()

    entry = _MEMORY_CACHE.get(key)
    if entry is not None:
        fetched_at, catalog = entry
        if now - fetched_at < CACHE_TTL_SECONDS:
            return catalog
        del _MEMORY_CACHE[key]

    raw = _read_cache_file().get(key)
    if not isinstance(raw, dict):
        return None
    fetched_at = raw.get("fetched_at")
    if not isinstance(fetched_at, (int, float)):
        return None
    if now - fetched_at >= CACHE_TTL_SECONDS:
        return None

    payload = raw.get("catalog")
    if not isinstance(payload, dict):
        return None
    catalog = _catalog_from_dict(payload)
    if catalog is None:
        return None

    _MEMORY_CACHE[key] = (float(fetched_at), catalog)
    return catalog


def store_cached(key: str, catalog: ModelCatalog) -> None:
    """Cache a live catalog under *key*.

    Only ``source == "provider"`` catalogs are stored: caching a
    built-in fallback would paper over an outage for a full day, and
    the built-in list is free to rebuild anyway.  Disk failures are
    swallowed — the in-memory cache still holds for this process.
    """
    if catalog.source != "provider":
        return

    now = time.time()
    _MEMORY_CACHE[key] = (now, catalog)

    data = _read_cache_file()
    data[key] = {"fetched_at": now, "catalog": _catalog_to_dict(catalog)}
    try:
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")
    except OSError:
        pass


def clear_cache() -> None:
    """Drop every cached catalog, in memory and on disk (for tests)."""
    _MEMORY_CACHE.clear()
    try:
        path = _cache_path()
        if path.exists():
            path.unlink()
    except OSError:
        pass
