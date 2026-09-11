"""Borrowing Claude Code's OAuth token to enumerate Anthropic models.

The ``claude_sdk`` auth mode signs in by running ``claude login`` and
letting the Claude Agent SDK hold the resulting credential.  That works
fine for chat — the SDK does the talking — but the SDK exposes no model
listing, and the Anthropic API client we would use for one has no
credential of its own.  So a ``claude_sdk`` user with no separate API
key would see only the model list baked into this release.

This module closes that gap by reading the token Claude Code stored and
handing it to the Anthropic API client.  That is a deeper reach into
Claude Code's business than the SDK reuse elsewhere in this package: we
handle the credential ourselves rather than leaving it to the SDK, the
storage layout is undocumented, and Anthropic may change or withdraw
it at any time.  Everything here is therefore best-effort and silent —
:func:`find_oauth_token` returns ``None`` on anything unexpected, and
the caller falls back to the built-in catalog exactly as it does today.

Security notes for anyone editing this file:

* The token must never be logged, printed, written to disk, or put in
  an exception message.  Failures are reported as ``None``, never as
  a value.
* Reading the macOS keychain item from a process other than Claude
  Code may prompt the user for keychain access.  That's why nothing
  here runs at import or during startup — only when a model listing is
  actually requested.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

# Beta header Anthropic requires on requests authenticated with a
# Claude Code OAuth token rather than an API key.  Harmless if the
# endpoint doesn't require it.
OAUTH_BETA_HEADER = "oauth-2025-04-20"

# Sanctioned escape hatch: Claude Code reads this for headless use.
# Checked first because it needs no keychain access at all.
_TOKEN_ENV_VAR = "CLAUDE_CODE_OAUTH_TOKEN"

# macOS: keychain service name Claude Code stores under.
_KEYCHAIN_SERVICE = "Claude Code-credentials"

# Linux/Windows: file Claude Code stores the same JSON blob in.
_CREDENTIALS_FILE = Path.home() / ".claude" / ".credentials.json"

# Key the OAuth material sits under inside that blob.
_OAUTH_KEY = "claudeAiOauth"

# Refuse a token this close to expiry (seconds), so we don't start a
# request with a credential that dies mid-flight.
_EXPIRY_MARGIN_SECONDS = 60


def find_oauth_token() -> str | None:
    """Return Claude Code's OAuth access token, or ``None``.

    ``None`` means "no usable token" for any reason — not installed,
    not logged in, expired, access denied, or a storage layout we
    don't recognize.  Callers treat all of those the same way.  Use
    :func:`diagnose` when you need to know *which*.
    """
    return _find_token_with_reason()[0]


def diagnose() -> str:
    """Describe how the token lookup went, for ``clarity models --debug``.

    Reports which stage succeeded or failed and nothing else.  The
    token, its length, and its prefix are all deliberately absent: the
    point of this function is to make an undocumented storage layout
    debuggable without putting credential material on a terminal that
    may well be in a screenshot or a bug report.
    """
    token, reason = _find_token_with_reason()
    status = "found a usable token" if token else "no usable token"
    return f"{status} ({reason})"


def _find_token_with_reason() -> tuple[str | None, str]:
    """Locate the token, returning it alongside a non-sensitive reason."""
    from_env = os.environ.get(_TOKEN_ENV_VAR)
    if from_env and from_env.strip():
        return from_env.strip(), f"read from ${_TOKEN_ENV_VAR}"

    keychain_raw = _read_from_keychain()
    file_raw = _read_from_file()
    if keychain_raw is None and file_raw is None:
        return None, (
            "nothing in the keychain or "
            f"{_CREDENTIALS_FILE} — is Claude Code installed and logged in?"
        )

    source = "keychain" if keychain_raw is not None else str(_CREDENTIALS_FILE)
    blob = _parse_first_valid(keychain_raw, file_raw)
    if blob is None:
        return None, f"{source} holds something that isn't a JSON object"

    oauth = blob.get(_OAUTH_KEY)
    if not isinstance(oauth, dict):
        return None, f"{source} has no {_OAUTH_KEY!r} object — layout changed?"

    token = oauth.get("accessToken")
    if not isinstance(token, str) or not token.strip():
        return None, f"{source} has no usable 'accessToken' — layout changed?"

    expires_at = oauth.get("expiresAt")
    if _is_expired(expires_at):
        if not isinstance(expires_at, (int, float)) or isinstance(expires_at, bool):
            return None, f"{source} has no readable 'expiresAt' — layout changed?"
        # Refreshing is Claude Code's job — the refresh flow needs
        # client credentials we don't have, and racing it would risk
        # invalidating the user's live session.
        return None, "the stored token has expired — re-run 'claude login'"

    return token.strip(), f"read from the {source}"


def _parse_first_valid(*candidates: str | None) -> dict[str, Any] | None:
    """Return the first candidate that parses as a JSON object."""
    for raw in candidates:
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _read_from_keychain() -> str | None:
    """Read the credential from the platform keychain.

    Uses ``keyring`` rather than shelling out to ``security`` so this
    works the same way on every platform, and so a system with no
    keychain degrades to a miss instead of an error.  The account name
    is the OS username, which is what Claude Code stores under.
    """
    try:
        import getpass

        import keyring

        return keyring.get_password(_KEYCHAIN_SERVICE, getpass.getuser())
    except Exception:  # noqa: BLE001 — locked, denied, or no backend
        return None


def _read_from_file() -> str | None:
    """Read the credential from ``~/.claude/.credentials.json``."""
    try:
        if not _CREDENTIALS_FILE.exists():
            return None
        return _CREDENTIALS_FILE.read_text()
    except OSError:
        return None


def _is_expired(expires_at: Any) -> bool:
    """True if *expires_at* (epoch milliseconds) has passed or is unusable.

    An unparseable value counts as expired: a token we can't reason
    about is one we shouldn't spend a request on.
    """
    if not isinstance(expires_at, (int, float)) or isinstance(expires_at, bool):
        return True
    return (expires_at / 1000) - _EXPIRY_MARGIN_SECONDS <= time.time()
