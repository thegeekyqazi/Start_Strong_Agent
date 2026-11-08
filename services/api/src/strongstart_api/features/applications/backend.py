"""Explicit C backend construction. No request-time migration, seed or memory fallback."""

from __future__ import annotations

from ...config import Settings
from ...database_profile import build_engine
from .postgres_store import PostgresAnswerStore
from .store import AnswerStore, InMemoryAnswerStore, UnconfiguredAnswerStore


def build_answer_store(settings: Settings) -> AnswerStore:
    if settings.answer_store_backend == "memory":
        return InMemoryAnswerStore()
    if settings.answer_store_backend == "unconfigured":
        return UnconfiguredAnswerStore()
    if not settings.database_url:
        return UnconfiguredAnswerStore("postgres_url_missing")
    return PostgresAnswerStore(
        build_engine(
            settings.database_url,
            profile=settings.database_profile,
            root_cert=settings.db_sslrootcert,
            connect_timeout=settings.db_connect_timeout_seconds,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout_seconds,
            lock_timeout_ms=settings.db_lock_timeout_ms,
            statement_timeout_ms=settings.db_statement_timeout_ms,
        ),
        settings.max_export_bytes,
    )
