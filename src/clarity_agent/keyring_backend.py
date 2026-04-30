"""Fallback keyring backend that stores credentials locally.

Used automatically when no platform keychain is available (headless
Linux, Docker, CI). Logs a warning on first use so the user knows
their credentials are not in a secure keychain.

This backend is registered with ``keyring.set_keyring()`` only when
the auto-detected backend is the ``fail.Keyring`` (meaning no real
keychain exists). On systems with macOS Keychain, Windows Credential
Manager, or Linux Secret Service, the native backend is used instead.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from keyring.backend import KeyringBackend

log = logging.getLogger(__name__)

# Service name used for all Clarity credentials.
SERVICE = "clarity"


class LocalKeyring(KeyringBackend):
    """Store credentials in a local JSON file.

    This is a last-resort fallback — the file is not encrypted.
    It exists so that ``keyring.get_password()`` / ``set_password()``
    always work, regardless of platform.
    """

    priority = 0.5  # Below any real backend, above fail.Keyring (0).  # type: ignore[assignment]

    def __init__(self, path: Path | None = None) -> None:
        super().__init__()
        self._path = path
        self._warned = False

    @property
    def path(self) -> Path:
        if self._path is not None:
            return self._path
        from clarity_agent.app_paths import clarity_data_dir
        return clarity_data_dir() / "secrets.json"

    def _warn_once(self) -> None:
        if not self._warned:
            log.warning(
                "No system keychain available — storing credentials in "
                "plaintext at %s. For better security, install a desktop "
                "environment with a keychain service.",
                self.path,
            )
            self._warned = True

    def _read(self) -> dict[str, dict[str, str]]:
        """Read the secrets file. Returns {service: {key: value}}."""
        p = self.path
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict[str, dict[str, str]]) -> None:
        """Write the secrets file with restricted permissions."""
        p = self.path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2) + "\n")
        try:
            p.chmod(0o600)
        except OSError:
            pass  # Windows doesn't support Unix permissions

    def get_password(self, service: str, username: str) -> str | None:
        return self._read().get(service, {}).get(username)

    def set_password(self, service: str, username: str, password: str) -> None:
        self._warn_once()
        data = self._read()
        data.setdefault(service, {})[username] = password
        self._write(data)

    def delete_password(self, service: str, username: str) -> None:
        data = self._read()
        service_data = data.get(service, {})
        if username in service_data:
            del service_data[username]
            if not service_data:
                del data[service]
            self._write(data)


def ensure_backend() -> None:
    """Ensure a working keyring backend is active.

    If the auto-detected backend is the fail backend, install our
    LocalKeyring as the fallback. Otherwise, leave the native
    backend in place.
    """
    import keyring
    from keyring.backends.fail import Keyring as FailKeyring

    current = keyring.get_keyring()
    if isinstance(current, FailKeyring):
        keyring.set_keyring(LocalKeyring())
