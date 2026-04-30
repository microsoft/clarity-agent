"""Resume / checkpointing support for eval runs.

An interrupted eval session can pick up where it left off: the
conversation phase and the judgment phase each persist their results
into the per-module output directory, and a resumed run reuses
whatever's on disk that's still consistent with the current inputs.

- Conversations are cached via ``transcript.md`` + ``metadata.json``
  (written by the runner at the end of the user↔target loop).
  Re-running the conversation overwrites them.
- Judgments are cached via ``judge_records.json``.  Each entry is
  keyed by ``(test_function_name, claim)`` and gated by a fingerprint
  (SHA-256 of the transcript) the record was produced against.  If the
  transcript changes for any reason, every cached judgment for that
  module invalidates automatically — no flag required.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from evals.framework.judge import JudgeRecord


def compute_fingerprint(transcript: str) -> str:
    """Return a stable SHA-256 hex digest of *transcript*.

    Used to invalidate cached judge records when the conversation they
    judged against changes.  Identical content produces an identical
    fingerprint regardless of file metadata or write order.
    """
    return hashlib.sha256(transcript.encode("utf-8")).hexdigest()


@dataclass
class JudgeCache:
    """Persistent cache of judge records for a single test module.

    Loaded from ``<module_dir>/judge_records.json`` if present.
    :meth:`lookup` serves a cached record iff its stored fingerprint
    matches the one this cache was constructed with; otherwise the
    cache is treated as stale and cache hits are suppressed.  Fresh
    records written via :meth:`store` adopt the current fingerprint
    and overwrite any stale on-disk contents.
    """

    path: Path
    """File to read from / write to (typically ``judge_records.json``)."""

    fingerprint: str
    """Transcript fingerprint this cache is valid against."""

    _records: dict[tuple[str, str], JudgeRecord] = field(
        default_factory=dict, repr=False,
    )
    _loaded_fingerprint: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._loaded_fingerprint = data.get("conversation_fingerprint")
        for test_name, entries in (data.get("tests") or {}).items():
            for entry in entries:
                try:
                    rec = JudgeRecord(
                        claim=entry["claim"],
                        verdict=entry["verdict"],
                        reasoning=entry.get("reasoning", ""),
                        elapsed=float(entry.get("elapsed", 0.0)),
                        cost_usd=float(entry.get("cost_usd", 0.0)),
                        cached=True,
                        timestamp=entry.get("timestamp"),
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                self._records[(test_name, rec.claim)] = rec

    def lookup(self, test_name: str, claim: str) -> JudgeRecord | None:
        """Return the cached record for ``(test_name, claim)`` if fresh.

        "Fresh" means the stored fingerprint matches the one this cache
        was constructed with.  A mismatch — transcript changed since
        these records were produced — suppresses all hits so the judge
        re-runs and overwrites the file.
        """
        if self._loaded_fingerprint != self.fingerprint:
            return None
        return self._records.get((test_name, claim))

    def store(self, test_name: str, record: JudgeRecord) -> None:
        """Add or replace a record and atomically rewrite the file.

        The on-disk fingerprint advances to :attr:`fingerprint`, so
        subsequent lookups against the same fingerprint succeed even
        if the file was previously stale.
        """
        fresh = JudgeRecord(**{**asdict(record), "cached": False})
        self._records[(test_name, fresh.claim)] = fresh
        self._loaded_fingerprint = self.fingerprint
        self._write()

    def _write(self) -> None:
        tests: dict[str, list[dict[str, Any]]] = {}
        for (test_name, _), rec in self._records.items():
            tests.setdefault(test_name, []).append(asdict(rec))
        # Stable sort for reviewable diffs.
        for entries in tests.values():
            entries.sort(key=lambda e: e["claim"])
        data = {
            "schema_version": 1,
            "conversation_fingerprint": self.fingerprint,
            "tests": {name: tests[name] for name in sorted(tests)},
        }
        # Atomic write: same-filesystem tmp + rename so a crash never
        # leaves a truncated judge_records.json on disk.
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)


__all__ = [
    "JudgeCache",
    "compute_fingerprint",
]
