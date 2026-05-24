"""``GET /api/version`` — the runtime's self-description.

Tiny module on purpose: the route handler is a one-liner around
:func:`get_version_payload`, which is where the cache + the
release-feed delegation live so the same logic powers the launcher
and the per-project app (and stays unit-testable in isolation).

The cache covers the *update check* (a network call to GitHub) —
not the version itself.  The version is essentially free to read
every time.  TTL is one hour per the design discussion; the update
check happens on-read whenever the cache is stale.  No background
task, no asyncio lifecycle plumbing, no thrashing if the process
exits early.  Frontends that want fresher data can simply re-fetch
the endpoint; we'll serve the cached payload until it ages out.
"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict
from typing import Any

from clarity_agent.setup.release_feed import (
    ReleaseFeed,
    UpdateAvailability,
    check_for_update,
)
from clarity_agent.setup.version import current_version

#: Seconds between fresh GitHub Releases queries.  One hour matches
#: the user's "best-practice cadence" call — long enough to be
#: polite to the API, short enough that users see new releases
#: within a working day.
CACHE_TTL_SECONDS = 3600

# Cached update-check result, plus the timestamp it was generated.
# ``None`` means "never checked yet" — the next read refreshes.
# Guarded by a lock because multiple concurrent request handlers
# can hit ``get_version_payload`` simultaneously; without it two
# threads could each see a stale cache and both fire HTTP requests.
_cache: tuple[float, UpdateAvailability] | None = None
_cache_lock = threading.Lock()


def reset_cache() -> None:
    """Drop the cached update check.  Used by tests to ensure a
    fresh check happens with the stub feed they're passing in.
    Production callers shouldn't need this — the TTL handles
    natural staleness.
    """
    global _cache
    with _cache_lock:
        _cache = None


def get_version_payload(
    feed: ReleaseFeed | None = None,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Build the ``/api/version`` response body.

    Caches the update-check result for :data:`CACHE_TTL_SECONDS`.
    The version itself isn't cached — it's cheap to read and never
    changes within a process.

    Parameters exist for tests:

      * ``feed`` — pass a stub :class:`ReleaseFeed` to avoid hitting
        GitHub.  When supplied, the cache is bypassed (no point
        caching against a stub) and the result is returned directly.
      * ``now`` — override the cache-staleness clock; lets tests
        verify TTL behavior without sleeping.
    """
    version = current_version()

    if feed is not None:
        # Test path — never cache stub results, never read the cache.
        availability = check_for_update(feed=feed, current=version)
    else:
        availability = _availability_with_cache(version, now)

    return _payload(version, availability)


def _availability_with_cache(
    version: Any,
    now: float | None,
) -> UpdateAvailability:
    """Production-only cache read.  Pulled out so
    ``get_version_payload`` reads top-to-bottom without nesting."""
    global _cache
    current_time = now if now is not None else time.monotonic()
    with _cache_lock:
        if _cache is not None and (current_time - _cache[0]) < CACHE_TTL_SECONDS:
            return _cache[1]
        availability = check_for_update(current=version)
        _cache = (current_time, availability)
        return availability


def _payload(version: Any, availability: UpdateAvailability) -> dict[str, Any]:
    """Shape the wire response.  ``latest`` is None-or-dict so the
    frontend can ``if (payload.latest)`` without defensive
    null-checks on individual fields."""
    latest_dict: dict[str, Any] | None = None
    if availability.latest is not None:
        latest_dict = asdict(availability.latest)
    return {
        "version": version.version,
        "source": version.source,
        "is_release": version.is_release,
        "update_status": availability.status,
        "latest": latest_dict,
        "reason": availability.reason,
    }
