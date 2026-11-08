"""Implementation of the Dev B local version store (see package docstring)."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import secrets
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

CANONICAL_ALGORITHM = "dev-b-canonical-json-sha256/1"
ENVELOPE_FORMAT = "dev-b-store-envelope/1"
MAX_VERSIONS = 20
MAX_SCAN_ENTRIES = 2000
MAX_ENVELOPE_BYTES = 4 * 1024 * 1024
DEFAULT_LOCK_TIMEOUT_S = 5.0

OBJECT_ID = re.compile(r"^[a-z][a-z0-9]{1,15}-[0-9a-f]{26}$")
DERIVED_ID = re.compile(r"^[a-z][a-z0-9-]{0,40}\.[a-z0-9.-]{1,80}$")
COLLECTION = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
CAPTURE_SCOPE = re.compile(r"^cap-[0-9a-f]{32}$")
VERSION_FILE = re.compile(r"^v([0-9]{6})\.json$")

Durability = Literal["full_posix", "reduced_windows"]


class StoreError(Exception):
    reason = "store_error"


class StoreUnavailable(StoreError):
    reason = "store_unavailable"

    def __init__(self, detail: str, reason: str = "store_unavailable") -> None:
        super().__init__(detail)
        self.detail = detail
        self.reason = reason


class StoreBusy(StoreError):
    reason = "store_busy"


class NotFound(StoreError):
    reason = "not_found"


class IntegrityFailure(StoreError):
    reason = "integrity_failure"


class VersionConflict(StoreError):
    reason = "version_conflict"

    def __init__(self, current_version: int) -> None:
        super().__init__(f"current version is {current_version}")
        self.current_version = current_version


class IdempotencyReused(StoreError):
    reason = "idempotency_key_reused"


class HistoryLimit(StoreError):
    reason = "history_limit"


class TooLarge(StoreError):
    reason = "too_large"


# --------------------------------------------------------------------------- primitives


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    """Versioned canonical form: UTF-8, sorted keys, compact, no NaN, no ASCII escaping."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def new_object_id(prefix: str) -> str:
    """Server-generated, time-ordered ID: ``<prefix>-<12 hex ms><14 hex random>``."""
    if not re.fullmatch(r"[a-z][a-z0-9]{1,15}", prefix):
        raise ValueError("invalid object ID prefix")
    return f"{prefix}-{int(time.time() * 1000):012x}{secrets.token_hex(7)}"


def durability_mode(allow_reduced: bool, os_name: str | None = None) -> Durability:
    """Write durability for this platform, or refuse before any write succeeds."""
    name = os.name if os_name is None else os_name
    if name == "posix":
        return "full_posix"
    if name == "nt":
        if allow_reduced:
            return "reduced_windows"
        raise StoreUnavailable(
            "Windows has no directory fsync; set STRONGSTART_DEV_B_STORE_ALLOW_REDUCED_DURABILITY"
            "=true to accept file-flush-only durability for local development",
            reason="platform_durability_unsupported",
        )
    raise StoreUnavailable(
        f"platform {name!r} is not a supported local store platform",
        reason="platform_durability_unsupported",
    )


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_create(path: Path, data: bytes, durability: Durability) -> bool:
    """Create ``path`` with exactly ``data``; never overwrite. Returns False if it existed.

    The file is fully written and flushed under a temporary name, then hard-linked into
    place. ``os.link`` fails when the target exists, so concurrent creators cannot clobber
    each other and no reader ever sees a partial file.
    """
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            return False
    finally:
        Path(tmp).unlink(missing_ok=True)
    if durability == "full_posix":
        _fsync_dir(path.parent)
    return True


LockEvent = Literal["blocked", "acquired_after_wait"]
LockObserver = Callable[[Path, LockEvent], None]
_lock_observer: LockObserver | None = None


def set_lock_observer(observer: LockObserver | None) -> LockObserver | None:
    """Test instrumentation: observe real lock contention in this process.

    The observer is called with ``"blocked"`` the first time a non-blocking acquisition
    attempt fails because another holder has the lock, and with ``"acquired_after_wait"``
    once that waiter finally acquires it. It never changes locking behaviour. Returns the
    previous observer so callers can restore it.
    """
    global _lock_observer
    previous, _lock_observer = _lock_observer, observer
    return previous


def _notify(path: Path, event: LockEvent) -> None:
    observer = _lock_observer
    if observer is not None:
        observer(path, event)


@contextlib.contextmanager
def _exclusive_lock(path: Path, timeout_s: float) -> Iterator[None]:
    """Cross-process exclusive lock with a bounded wait (process-local locks are not enough)."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle = open(path, "a+b")  # held for the lock's lifetime
    deadline = time.monotonic() + timeout_s
    waited = False
    try:
        if sys.platform == "win32":  # pragma: no cover - exercised on Windows only
            import msvcrt

            while True:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if not waited:
                        waited = True
                        _notify(path, "blocked")
                    if time.monotonic() >= deadline:
                        raise StoreBusy("store lock wait exceeded") from None
                    time.sleep(0.01)
            if waited:
                _notify(path, "acquired_after_wait")
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if not waited:
                        waited = True
                        _notify(path, "blocked")
                    if time.monotonic() >= deadline:
                        raise StoreBusy("store lock wait exceeded") from None
                    time.sleep(0.01)
            if waited:
                _notify(path, "acquired_after_wait")
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


# --------------------------------------------------------------------------- store


@dataclass(frozen=True)
class CommitResult:
    object_id: str
    version: int
    record: dict[str, Any]
    replayed: bool


@dataclass(frozen=True)
class ListPage:
    object_ids: list[str]
    next_cursor: str | None
    more: bool
    incomplete: bool
    scanned: int


Builder = Callable[[str, int, dict[str, Any] | None], dict[str, Any]]


class LocalVersionStore:
    """Root of the Dev B local store. Organization namespaces are hashed, never raw IDs."""

    def __init__(
        self,
        root: Path,
        *,
        allow_reduced_durability: bool = False,
        lock_timeout_s: float = DEFAULT_LOCK_TIMEOUT_S,
        os_name: str | None = None,
    ) -> None:
        self.root = root.resolve()
        self.allow_reduced_durability = allow_reduced_durability
        self.lock_timeout_s = lock_timeout_s
        self._os_name = os_name

    def durability(self) -> Durability:
        return durability_mode(self.allow_reduced_durability, self._os_name)

    def confined(self, path: Path) -> Path:
        resolved = path.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise NotFound("path escapes the store root")
        return resolved

    def org_dir(self, organization_id: str) -> Path:
        digest = sha256_hex(organization_id.encode("utf-8"))[:32]
        return self.confined(self.root / f"org-{digest}")

    def collection(
        self, organization_id: str, name: str, scope: str | None = None
    ) -> VersionCollection:
        if not COLLECTION.fullmatch(name):
            raise ValueError("invalid collection name")
        if scope is not None and not (valid_object_id(scope) or CAPTURE_SCOPE.fullmatch(scope)):
            raise NotFound("invalid scope")
        return VersionCollection(self, organization_id, name, scope)

    # -- blobs ------------------------------------------------------------------

    def put_blob(self, organization_id: str, data: bytes) -> str:
        sha = sha256_hex(data)
        path = self.confined(self.org_dir(organization_id) / "blobs" / sha)
        if not atomic_create(path, data, self.durability()):
            self._verify_blob_bytes(path, sha, len(data))
        return sha

    def read_blob(self, organization_id: str, sha: str, size: int) -> bytes:
        if not SHA.fullmatch(sha):
            raise IntegrityFailure("invalid blob hash")
        path = self.confined(self.org_dir(organization_id) / "blobs" / sha)
        return self._verify_blob_bytes(path, sha, size)

    @staticmethod
    def _verify_blob_bytes(path: Path, sha: str, size: int) -> bytes:
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            raise IntegrityFailure("stored bytes are missing") from None
        if len(data) != size or sha256_hex(data) != sha:
            raise IntegrityFailure("stored bytes failed integrity verification")
        return data


def valid_object_id(value: str) -> bool:
    return bool(OBJECT_ID.fullmatch(value) or DERIVED_ID.fullmatch(value))


class VersionCollection:
    """Immutable versioned objects of one kind inside one organization namespace."""

    def __init__(
        self, store: LocalVersionStore, organization_id: str, name: str, scope: str | None
    ) -> None:
        self.store = store
        self.organization_id = organization_id
        self.name = name
        base = store.org_dir(organization_id) / name
        self.dir = store.confined(base / scope if scope else base)
        self._idem_dir = store.confined(
            store.org_dir(organization_id) / "idempotency" / (f"{name}-{scope}" if scope else name)
        )
        self._lock = store.confined(store.org_dir(organization_id) / "locks" / f"{name}.lock")

    # -- paths ------------------------------------------------------------------

    def _object_dir(self, object_id: str) -> Path:
        if not valid_object_id(object_id):
            raise NotFound(object_id)
        return self.store.confined(self.dir / object_id)

    def _version_path(self, object_id: str, version: int) -> Path:
        if not 1 <= version <= MAX_VERSIONS:
            raise NotFound(f"{object_id} v{version}")
        return self.store.confined(self._object_dir(object_id) / f"v{version:06d}.json")

    # -- reads ------------------------------------------------------------------

    def current_version(self, object_id: str) -> int:
        directory = self._object_dir(object_id)
        try:
            names = [e.name for e in os.scandir(directory)]
        except (FileNotFoundError, NotADirectoryError):
            return 0
        versions = [int(m.group(1)) for n in names if (m := VERSION_FILE.fullmatch(n))]
        return max(versions, default=0)

    def read(self, object_id: str, version: int) -> dict[str, Any]:
        path = self._version_path(object_id, version)
        try:
            raw = path.read_bytes()
        except (FileNotFoundError, NotADirectoryError):
            raise NotFound(f"{object_id} v{version}") from None
        if len(raw) > MAX_ENVELOPE_BYTES + 4096:
            raise IntegrityFailure("stored envelope exceeds its size bound")
        try:
            env = json.loads(raw.decode("utf-8"))
            record = env["record"]
            ok = (
                env.get("format") == ENVELOPE_FORMAT
                and env.get("algorithm") == CANONICAL_ALGORITHM
                and env.get("object_id") == object_id
                and env.get("version") == version
                and isinstance(record, dict)
                and env.get("digest") == sha256_hex(canonical_json(record))
            )
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            ok = False
        if not ok:
            raise IntegrityFailure(f"{object_id} v{version} failed integrity verification")
        result: dict[str, Any] = record
        return result

    def read_current(self, object_id: str) -> tuple[int, dict[str, Any]]:
        version = self.current_version(object_id)
        if version == 0:
            raise NotFound(object_id)
        return version, self.read(object_id, version)

    def list_ids(self, cursor: str | None, limit: int) -> ListPage:
        """Newest-first page of object IDs; bounded scan with an explicit incomplete flag."""
        names: list[str] = []
        scanned = 0
        incomplete = False
        try:
            with os.scandir(self.dir) as it:
                for entry in it:
                    scanned += 1
                    if scanned > MAX_SCAN_ENTRIES:
                        incomplete = True
                        break
                    if valid_object_id(entry.name) and not entry.is_symlink():
                        names.append(entry.name)
        except FileNotFoundError:
            pass
        names.sort(reverse=True)
        if cursor is not None:
            names = [n for n in names if n < cursor]
        page = names[:limit]
        more = len(names) > limit
        return ListPage(
            object_ids=page,
            next_cursor=page[-1] if more and page else None,
            more=more,
            incomplete=incomplete,
            scanned=min(scanned, MAX_SCAN_ENTRIES),
        )

    # -- writes -----------------------------------------------------------------

    def _envelope(self, object_id: str, version: int, record: dict[str, Any], cmd: str) -> bytes:
        body = canonical_json(record)
        if len(body) > MAX_ENVELOPE_BYTES:
            raise TooLarge(f"record exceeds {MAX_ENVELOPE_BYTES} bytes")
        return canonical_json(
            {
                "format": ENVELOPE_FORMAT,
                "algorithm": CANONICAL_ALGORITHM,
                "object_id": object_id,
                "version": version,
                "digest": sha256_hex(body),
                "command_hash": cmd,
                "record": record,
            }
        )

    def _read_command_hash(self, object_id: str, version: int) -> str | None:
        try:
            raw = self._version_path(object_id, version).read_bytes()
            value = json.loads(raw.decode("utf-8")).get("command_hash")
        except (FileNotFoundError, NotADirectoryError, ValueError, UnicodeDecodeError):
            return None
        return value if isinstance(value, str) else None

    @contextlib.contextmanager
    def locked(self) -> Iterator[None]:
        """Hold this collection's cross-process write lock (the same lock ``commit`` takes).

        Used to make a check on this collection atomic with a write elsewhere: while held,
        no other process or thread can commit a new version here. Lock order rule: a
        caller holding this lock may take the lock of a *different* collection (e.g.
        ``cases`` then ``definitions``), never the reverse, and must not commit to this
        same collection (that would wait on itself until the bounded timeout).
        """
        with _exclusive_lock(self._lock, self.store.lock_timeout_s):
            yield

    def replay(self, idempotency_key: str, command_hash: str) -> CommitResult | None:
        """Completed result for this key, if any (before doing external work such as a
        provider call). Raises IdempotencyReused for the same key with another command."""
        key_hash = sha256_hex(f"{self.name}\0{idempotency_key}".encode())
        intent = self._load_intent(self.store.confined(self._idem_dir / f"{key_hash}.json"))
        if intent is None:
            return None
        if intent["command_hash"] != command_hash:
            raise IdempotencyReused("idempotency key was used for a different command")
        oid, ver = intent["object_id"], intent["version"]
        if self._read_command_hash(oid, ver) != command_hash:
            return None
        return CommitResult(oid, ver, self.read(oid, ver), replayed=True)

    def commit(
        self,
        *,
        idempotency_key: str,
        command_hash: str,
        object_id: str | None,
        expected_version: int,
        build: Builder,
        id_prefix: str = "obj",
    ) -> CommitResult:
        """Commit version ``expected_version + 1`` (0 creates a lineage).

        Order: idempotency replay first, then expected-version check, intent record, then
        the no-clobber version create (the commit point). Raises VersionConflict on a stale
        expectation, IdempotencyReused for a key reused with a different command.
        """
        durability = self.store.durability()  # refuse unsupported platforms before work
        key_hash = sha256_hex(f"{self.name}\0{idempotency_key}".encode())
        intent_path = self.store.confined(self._idem_dir / f"{key_hash}.json")
        with _exclusive_lock(self._lock, self.store.lock_timeout_s):
            intent = self._load_intent(intent_path)
            if intent is not None:
                if intent["command_hash"] != command_hash:
                    raise IdempotencyReused("idempotency key was used for a different command")
                oid, ver = intent["object_id"], intent["version"]
                existing = self._read_command_hash(oid, ver)
                if existing == command_hash:
                    return CommitResult(oid, ver, self.read(oid, ver), replayed=True)
                if existing is not None:
                    raise VersionConflict(self.current_version(oid))
                # Intent without its version: a crash leftover. Complete the same target.
                target_id, version = oid, ver
                if self.current_version(target_id) != version - 1:
                    raise VersionConflict(self.current_version(target_id))
            else:
                target_id = object_id or new_object_id(id_prefix)
                current = self.current_version(target_id)
                if current != expected_version:
                    if object_id is None and expected_version == 0:
                        raise StoreError("generated ID collision")  # pragma: no cover
                    raise VersionConflict(current)
                version = expected_version + 1
                if version > MAX_VERSIONS:
                    raise HistoryLimit(f"version history is capped at {MAX_VERSIONS}")
                intent_body = canonical_json(
                    {
                        "command_hash": command_hash,
                        "object_id": target_id,
                        "version": version,
                    }
                )
                if not atomic_create(intent_path, intent_body, durability):
                    raise StoreError("idempotency intent appeared concurrently")  # pragma: no cover
            previous = self.read(target_id, version - 1) if version > 1 else None
            record = build(target_id, version, previous)
            data = self._envelope(target_id, version, record, command_hash)
            if not atomic_create(self._version_path(target_id, version), data, durability):
                raise VersionConflict(self.current_version(target_id))
            return CommitResult(target_id, version, record, replayed=False)

    def _load_intent(self, path: Path) -> dict[str, Any] | None:
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
            if (
                isinstance(data, dict)
                and isinstance(data.get("command_hash"), str)
                and isinstance(data.get("object_id"), str)
                and valid_object_id(data["object_id"])
                and isinstance(data.get("version"), int)
                and not isinstance(data.get("version"), bool)
                and 1 <= data["version"] <= MAX_VERSIONS
            ):
                return data
        except (ValueError, UnicodeDecodeError):
            pass
        raise IntegrityFailure("idempotency record failed integrity verification")
