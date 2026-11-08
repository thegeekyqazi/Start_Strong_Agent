"""Application workspace sources (C1 spec s6; C2 spec rev 1.3 s13, phase C2b).

Two question sources, chosen explicitly per request:

- ``question_set_id`` is null: the labelled FIXTURE ``demo-bundle@1`` questions (fixture
  mode only), as in C1/C2.
- ``question_set_id`` is given: that exact Dev B saved definition version, read through B's
  public ``ApplicationDefinitionReader`` with the server-derived organization. Failures are
  surfaced (not found / integrity / unavailable) and **never** fall back to the fixture.

Evidence stays the labelled fixture ``EvidenceBundle`` in both cases (real A evidence is
the other half of G1). Nothing here resolves Dev B's conflicts or unknowns.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from strongstart_contracts import (
    CapabilityUnavailable,
    ChangeSet,
    EvidenceBundle,
    FixtureBundle,
    load_fixture_bundle,
)
from strongstart_contracts.answers import ApplicationWorkspace, DependencyRef, QuestionSetRef
from strongstart_contracts.application_publication import (
    ApplicationDefinitionIntegrityError,
    ApplicationDefinitionNotFound,
    ApplicationDefinitionReader,
    PublishedApplicationVersion,
)
from strongstart_contracts.knowledge_binding import ApprovedKnowledgeBinding

BUNDLE_RELATIVE = Path("tests/fixtures/demo/demo-bundle-v1.json")
APPLICATION_DEFINITION_ID = "demo-gos-app-v1"
FIXTURE_LABEL = "FIXTURE: synthetic demo-bundle@1 data, not partner records"


class WorkspaceNotFound(Exception):
    """No workspace for this organization (unknown and other-org look the same)."""


class QuestionSetNotFound(WorkspaceNotFound):
    """The selected Dev B question set does not exist for this organization."""


class QuestionSetIntegrityError(Exception):
    """Dev B's stored version failed verification; it must be withheld."""


class WorkspaceSource(Protocol):
    is_fixture: bool

    def get(
        self, organization_id: str, question_set_id: str | None = None
    ) -> ApplicationWorkspace: ...


def load_workspace(
    source: WorkspaceSource, organization_id: str, question_set_id: str | None
) -> ApplicationWorkspace:
    """Call ``source.get`` without passing a null selection, so simple sources (and test
    doubles) that only know the fixture workspace keep working."""
    if question_set_id is None:
        return source.get(organization_id)
    return source.get(organization_id, question_set_id)


def current_question_set_id(
    source: WorkspaceSource, organization_id: str, question_set_id: str | None
) -> str | None:
    """The latest question-set ID in the same Dev B lineage (revision staleness)."""
    finder = getattr(source, "current_question_set_id", None)
    if question_set_id is None or finder is None:
        return question_set_id
    current: str | None = finder(organization_id, question_set_id)
    return current


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

    def get(self, organization_id: str, question_set_id: str | None = None) -> ApplicationWorkspace:
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
        if question_set_id is not None and question_set_id != definition.question_set_id:
            raise QuestionSetNotFound()
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


class DefinitionWorkspaceSource:
    """Questions from Dev B's reader (exact version, server org); evidence from the fixture.

    No fallback: a missing, other-org or failed-integrity question set raises; it is never
    replaced by the demo fixture questions.
    """

    def __init__(self, reader: ApplicationDefinitionReader, fixture: FixtureWorkspaceSource):
        self._reader = reader
        self._fixture = fixture
        self.is_fixture = True  # evidence is still the labelled fixture bundle

    def _version(self, organization_id: str, question_set_id: str) -> PublishedApplicationVersion:
        try:
            return self._reader.get_version(organization_id, question_set_id)
        except ApplicationDefinitionNotFound:
            raise QuestionSetNotFound() from None
        except ApplicationDefinitionIntegrityError:
            raise QuestionSetIntegrityError() from None

    def get(self, organization_id: str, question_set_id: str | None = None) -> ApplicationWorkspace:
        fixture = self._fixture.get(organization_id)
        if question_set_id is None:
            return fixture  # explicit choice of the demo questions, not a fallback
        v = self._version(organization_id, question_set_id)
        questions = "FIXTURE " if v.is_fixture else ""
        label = (
            f"Questions: Dev B saved definition {v.definition_id} v{v.version} "
            f"({questions}{v.mode_label}; {v.review_status}). Evidence: {FIXTURE_LABEL}"
        )
        return ApplicationWorkspace(
            application_definition_id=v.application_definition.application_definition_id,
            question_set=v.question_set,
            evidence_bundle=fixture.evidence_bundle,
            is_fixture=True,
            data_label=label,
            question_source="dev_b_saved_definition",
            question_set_ref=QuestionSetRef(
                question_set_id=v.question_set_id,
                definition_id=v.definition_id,
                definition_version=v.version,
                is_fixture=v.is_fixture,
                mode_label=v.mode_label,
                review_status=v.review_status,
                saved_at=v.saved_at,
            ),
            unresolved=list(v.unresolved),
        )

    def current_question_set_id(self, organization_id: str, question_set_id: str) -> str:
        v = self._version(organization_id, question_set_id)
        try:
            current = self._reader.get_current(organization_id, v.definition_id)
        except ApplicationDefinitionNotFound:
            raise QuestionSetNotFound() from None
        except ApplicationDefinitionIntegrityError:
            raise QuestionSetIntegrityError() from None
        return current.question_set_id


def fixture_change_set(change_set_id: str) -> ChangeSet | None:
    """A fixture ChangeSet (A's producer, A4, is not built); injected deliberately."""
    bundle = _load(_bundle_path())
    return next((c for c in bundle.change_sets if c.change_set_id == change_set_id), None)


class UnconfiguredWorkspaceSource:
    is_fixture = False

    def get(self, organization_id: str, question_set_id: str | None = None) -> ApplicationWorkspace:
        raise CapabilityUnavailable(
            "ApplicationWorkspace", "no question/evidence producer configured (fixture mode off)"
        )


def knowledge_binding_for(
    source: WorkspaceSource, organization_id: str, bundle: EvidenceBundle, refs: list[DependencyRef]
) -> ApprovedKnowledgeBinding | None:
    """Optional server-owned managed workspace boundary. No default synthetic binding.

    A TigerData workspace must return its exact saved active-context projection here.
    INT-001's managed tests implement this with the real knowledge public facade.
    """
    binder = getattr(source, "knowledge_binding_for", None)
    if binder is None:
        return None
    binding = binder(organization_id, bundle, refs)
    return ApprovedKnowledgeBinding.model_validate(binding)
