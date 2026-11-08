"""Test-only C workspace using real A4 public evidence. Reader/store are never replaced."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.applications.deps import get_policy, get_workspace_source
from strongstart_api.features.applications.workspace import (
    DefinitionWorkspaceSource,
    FixtureWorkspaceSource,
)
from strongstart_api.features.automation.public import build_application_definition_reader
from strongstart_contracts import EvidenceBundle
from strongstart_contracts.answers import ApplicationWorkspace, DependencyRef
from strongstart_contracts.application_publication import ApplicationDefinitionReader
from strongstart_contracts.knowledge_binding import ApprovedKnowledgeBinding

from .a4_support import Managed


class ManagedWorkspace(DefinitionWorkspaceSource):
    def __init__(self, reader: ApplicationDefinitionReader, managed: Managed) -> None:
        super().__init__(reader, FixtureWorkspaceSource())
        self.managed = managed

    def get(self, organization_id: str, question_set_id: str | None = None) -> ApplicationWorkspace:
        questions = super().get(organization_id, question_set_id)
        evidence = self.managed.facade.resolve_active(organization_id, self.managed.context)
        return questions.model_copy(
            update={
                "evidence_bundle": evidence,
                "data_label": "SYNTHETIC real A4 DB evidence; test workspace",
            }
        )

    def knowledge_binding_for(
        self, organization_id: str, bundle: EvidenceBundle, refs: list[DependencyRef]
    ) -> ApprovedKnowledgeBinding:
        return self.managed.facade.project(organization_id, self.managed.context, bundle, refs)


def managed_client(
    managed: Managed, tmp_path: Path
) -> tuple[TestClient, Settings, ManagedWorkspace]:
    settings = Settings(
        _env_file=None,
        auth_mode="fixture",
        answer_store_backend="postgres",
        database_url=managed.url,
        dev_b_store_dir=tmp_path / "b-store",
    )
    app = create_app(settings)
    source = ManagedWorkspace(build_application_definition_reader(settings), managed)
    app.dependency_overrides[get_workspace_source] = lambda: source
    app.dependency_overrides[get_policy] = lambda: (
        None
    )  # missing policy stays needs_review, explicitly acknowledged
    return TestClient(app), settings, source
