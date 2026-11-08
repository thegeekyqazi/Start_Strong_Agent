"""Application workspace sources (C1 spec s6; deviation D2).

The only source in C1 is a FIXTURE source over the shared synthetic bundle
``tests/fixtures/demo/demo-bundle-v1.json`` (``demo-bundle@1``). It is used only when
the server runs the local fixture identity; otherwise the workspace is explicitly
unavailable. Data is scoped to the server-derived organization. Real producers (B2
``AutomationHandoffExport`` questions, A ``EvidenceBundle`` retrieval) replace it in C2.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from strongstart_contracts import (
    CapabilityUnavailable,
    ChangeSet,
    FixtureBundle,
    load_fixture_bundle,
)
from strongstart_contracts.answers import ApplicationWorkspace

BUNDLE_RELATIVE = Path("tests/fixtures/demo/demo-bundle-v1.json")
APPLICATION_DEFINITION_ID = "demo-gos-app-v1"
FIXTURE_LABEL = "FIXTURE: synthetic demo-bundle@1 data, not partner records"


class WorkspaceNotFound(Exception):
    """No workspace for this organization (unknown and other-org look the same)."""


class WorkspaceSource(Protocol):
    is_fixture: bool

    def get(self, organization_id: str) -> ApplicationWorkspace: ...


def _bundle_path() -> Path:
    repo_root = Path(__file__).resolve().parents[6]
    for candidate in (repo_root / BUNDLE_RELATIVE, Path.cwd() / BUNDLE_RELATIVE):
        if candidate.is_file():
            return candidate
    raise CapabilityUnavailable("ApplicationWorkspace", "fixture bundle not found")


@lru_cache(maxsize=4)
def _load(path: Path) -> FixtureBundle:
    return load_fixture_bundle(path)


class FixtureWorkspaceSource:
    is_fixture = True

    def __init__(self, bundle_path: Path | None = None) -> None:
        self._path = bundle_path

    def get(self, organization_id: str) -> ApplicationWorkspace:
        bundle = _load(self._path or _bundle_path())
        definition = next(
            (
                d
                for d in bundle.application_definitions
                if d.application_definition_id == APPLICATION_DEFINITION_ID
            ),
            None,
        )
        evidence = sorted(
            (e for e in bundle.evidence_bundles if e.organization_id == organization_id),
            key=lambda e: e.bundle_id,
        )
        if definition is None or not evidence:
            raise WorkspaceNotFound()
        question_set = next(
            q for q in bundle.question_sets if q.question_set_id == definition.question_set_id
        )
        return ApplicationWorkspace(
            application_definition_id=definition.application_definition_id,
            question_set=question_set,
            evidence_bundle=evidence[0],
            is_fixture=True,
            data_label=FIXTURE_LABEL,
        )


def fixture_change_set(change_set_id: str) -> ChangeSet | None:
    """A fixture ChangeSet (A's producer, A4, is not built); injected deliberately."""
    bundle = _load(_bundle_path())
    return next((c for c in bundle.change_sets if c.change_set_id == change_set_id), None)


class UnconfiguredWorkspaceSource:
    is_fixture = False

    def get(self, organization_id: str) -> ApplicationWorkspace:
        raise CapabilityUnavailable(
            "ApplicationWorkspace", "no question/evidence producer configured (fixture mode off)"
        )
