"""Spawn-safe workers: real C commands/readers over independent PostgreSQL connections."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import event

from strongstart_api.database_profile import build_engine
from strongstart_api.features.applications.approval import Context
from strongstart_api.features.applications.postgres_store import PostgresAnswerStore
from strongstart_api.features.applications.resolver import StoreApprovedAnswerResolver
from strongstart_api.features.applications.rules.policy import fixture_policy
from strongstart_api.features.applications.store import StoreState
from strongstart_api.features.applications.workspace import (
    DefinitionWorkspaceSource,
    FixtureWorkspaceSource,
)
from strongstart_api.features.automation.public import build_application_definition_reader
from strongstart_contracts.fixture_adapters import ApprovalNotUsable
from tests.data.support import client_for


def command_worker(
    url: str,
    directory: str,
    path: str,
    body: dict[str, Any],
    results: Any,
    pause: Any = None,
    resume: Any = None,
) -> None:
    engine = build_engine(url)
    store = PostgresAnswerStore(engine)

    def observed(conn: Any, cursor: Any, statement: str, params: Any, ctx: Any, many: bool) -> None:
        if "FROM organizations" in statement and "FOR UPDATE" in statement:
            results.put(("lock_attempt", conn.connection.driver_connection.info.backend_pid))

    event.listen(engine, "before_cursor_execute", observed)
    if pause is not None:
        original = store.unit_of_work
        first = [True]

        @contextmanager
        def paused(org: str, expected: StoreState | None = None) -> Iterator[None]:
            if first[0] and expected is not None:
                first[0] = False
                pause.set()
                if not resume.wait(10):
                    raise RuntimeError("owned worker barrier timed out")
            with original(org, expected):
                yield

        store.unit_of_work = paused  # type: ignore[method-assign, assignment]
    try:
        client, _ = client_for(store, Path(directory))
        with client:
            response = client.post(path, json=body)
            results.put(("result", response.status_code, response.json()))
    finally:
        engine.dispose()


def reader_worker(
    url: str, directory: str, approval: str, captured: Any, resume: Any, results: Any
) -> None:
    engine = build_engine(url)
    store = PostgresAnswerStore(engine)
    _, settings = client_for(store, Path(directory))

    class PausedSource(DefinitionWorkspaceSource):
        def get(self, organization_id: str, question_set_id: str | None = None):
            captured.set()
            if not resume.wait(10):
                raise RuntimeError("owned reader barrier timed out")
            return super().get(organization_id, question_set_id)

    source = PausedSource(build_application_definition_reader(settings), FixtureWorkspaceSource())
    reader = StoreApprovedAnswerResolver(
        lambda org: Context(store, source, fixture_policy(), settings, org), True
    )
    try:
        try:
            value = reader.resolve_for_prefill("demo-org", approval)
            results.put(("usable", value.answer_version_id))
        except ApprovalNotUsable as exc:
            results.put(("refused", exc.reason))
    finally:
        engine.dispose()
