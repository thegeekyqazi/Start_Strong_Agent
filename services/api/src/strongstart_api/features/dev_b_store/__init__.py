"""Dev B local storage helper (owner: Dev B). DEV-B-BUNDLE-002 s4.1, s10.

DEVELOPMENT/TEST ONLY. A low-level helper shared by the funding and automation repositories.
It contains no business logic. See decision
``docs/decisions/DEV-B-BUNDLE-002-local-repositories-versions-review.md``.

Guarantees provided here:

- organization-derived namespaces (hashed); every path segment validated before any I/O;
  resolved paths confined to the root (symlink escapes rejected);
- exact-byte, content-addressed blobs;
- immutable version envelopes created with a no-clobber atomic ``os.link``; writing
  ``vN+1`` is a compare-and-swap that only one writer can win;
- a cross-process exclusive lock (``fcntl``/``msvcrt``) with a bounded wait;
- idempotency intents written before the version commit; intents are invisible to reads;
- canonical JSON digests verified on every read (integrity identity, not a signature);
- explicit platform durability policy: POSIX full; Windows only with an explicit
  reduced-durability opt-in; anything else refused before success.
"""

from __future__ import annotations

from .core import (
    CANONICAL_ALGORITHM,
    MAX_ENVELOPE_BYTES,
    MAX_SCAN_ENTRIES,
    MAX_VERSIONS,
    CommitResult,
    HistoryLimit,
    IdempotencyReused,
    IntegrityFailure,
    ListPage,
    LocalVersionStore,
    NotFound,
    StoreBusy,
    StoreError,
    StoreUnavailable,
    TooLarge,
    VersionCollection,
    VersionConflict,
    atomic_create,
    canonical_json,
    durability_mode,
    new_object_id,
    sha256_hex,
)

__all__ = [
    "CANONICAL_ALGORITHM",
    "MAX_ENVELOPE_BYTES",
    "MAX_SCAN_ENTRIES",
    "MAX_VERSIONS",
    "CommitResult",
    "HistoryLimit",
    "IdempotencyReused",
    "IntegrityFailure",
    "ListPage",
    "LocalVersionStore",
    "NotFound",
    "StoreBusy",
    "StoreError",
    "StoreUnavailable",
    "TooLarge",
    "VersionCollection",
    "VersionConflict",
    "atomic_create",
    "canonical_json",
    "durability_mode",
    "new_object_id",
    "sha256_hex",
]
