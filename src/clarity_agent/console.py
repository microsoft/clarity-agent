"""Console output encoding — make our CLI text survive being redirected.

Every Clarity CLI prints non-ASCII: status glyphs (``✓ ⚠ ✗``), arrows
(``→ ↳``), rules (``━``), and em dashes all over the report text.  On
Windows that's a crash waiting to happen.  The console itself is fine —
since 3.6 CPython talks UTF-16 to it directly — but the moment stdout is
a *pipe* (a subprocess call, a ``> out.txt``, CI capturing the run),
Python falls back to the locale encoding, which on a US/Western Windows
box is cp1252::

    UnicodeEncodeError: 'charmap' codec can't encode character '\\u2713'

That's a hard failure of an otherwise successful command, and it only
appears when someone captures the output — exactly the case a developer
running locally never sees and CI hits immediately.

:func:`configure_stdio` fixes it once, at each CLI entry point, instead
of asking every ``print`` to think about encodings.

**Stdlib-only, no side effects on import.** Entry points call it; merely
importing a module never reconfigures a stream out from under a host
process (the desktop app, an MCP client, pytest).
"""

from __future__ import annotations

import sys
from typing import Any

# Characters our CLIs actually print.  If a stream can carry these it
# can carry our output, and we leave it exactly as the platform (or the
# user's PYTHONIOENCODING) configured it.
_PROBE = "✓✗⚠→↳━—"


def _needs_utf8(stream: Any) -> bool:
    """True when *stream* is a text stream that would fail on our glyphs."""
    encoding = getattr(stream, "encoding", None)
    if not encoding or not hasattr(stream, "reconfigure"):
        # Not a reconfigurable text stream — a pytest capture object, an
        # already-wrapped binary stream, something a host app installed.
        # Not ours to touch.
        return False
    try:
        _PROBE.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return True
    return False


def configure_stdio() -> None:
    """Ensure ``stdout``/``stderr`` can encode the CLI's output.

    Switches a stream to UTF-8 only when its current encoding would
    raise on our glyphs — a working stream (any UTF-8 locale, the
    Windows console itself, an explicit ``PYTHONIOENCODING`` that can
    carry them) is left untouched.

    The tradeoff when we do intervene: a cp1252 consumer sees UTF-8
    bytes rather than the command dying halfway through its output.
    Mojibake is recoverable; a ``UnicodeEncodeError`` mid-report is not.
    ``errors="replace"`` is belt-and-braces for anything outside the
    probe set.
    """
    # Typed as Any: what's on ``sys.stdout`` at runtime is whatever the
    # host put there, and ``reconfigure`` is duck-typed — the presence
    # check lives in :func:`_needs_utf8`.
    streams: tuple[Any, ...] = (sys.stdout, sys.stderr)
    for stream in streams:
        if not _needs_utf8(stream):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            # Couldn't re-encode; at least degrade to "?" instead of
            # raising partway through a command's output.
            try:
                stream.reconfigure(errors="replace")
            except (OSError, ValueError):
                pass
