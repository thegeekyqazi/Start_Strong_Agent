"""Supported public entry points of the automation feature (owner: B2). DEV-B-BUNDLE-002 s5.3.

Other features (C2b) may import **only** these factories plus the models, protocol and
errors in ``strongstart_contracts.application_publication``. Everything else in this
package is private.

FastAPI wiring for a consumer route::

    from typing import Annotated
    from fastapi import Depends
    from strongstart_contracts.application_publication import (
        ApplicationDefinitionIntegrityError,
        ApplicationDefinitionNotFound,
        ApplicationDefinitionReader,
    )
    from strongstart_api.features.automation.public import get_application_definition_reader

    ReaderDep = Annotated[ApplicationDefinitionReader, Depends(get_application_definition_reader)]

    def handler(identity: Identity, reader: ReaderDep, question_set_id: str) -> ...:
        version = reader.get_version(identity.organization_id, question_set_id)
        ...  # use version.question_set (shared Questions) + version.unresolved + version.intake

Missing and other-organization IDs raise ``ApplicationDefinitionNotFound``; a failed
verification raises ``ApplicationDefinitionIntegrityError``; production raises
``CapabilityUnavailable`` (no fixture or memory fallback). Tests override the dependency
with ``app.dependency_overrides`` or call ``build_application_definition_reader``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from strongstart_contracts.application_publication import (
    ApplicationDefinitionReader,
    UnconfiguredApplicationDefinitionReader,
)

from ...config import Settings, get_settings
from ..dev_b_store.factory import local_store
from .definitions import DefinitionRepository


def build_definition_repository(settings: Settings) -> DefinitionRepository | None:
    store = local_store(settings)
    return DefinitionRepository(store) if store is not None else None


def build_application_definition_reader(settings: Settings) -> ApplicationDefinitionReader:
    repo = build_definition_repository(settings)
    return repo if repo is not None else UnconfiguredApplicationDefinitionReader()


def get_application_definition_reader(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApplicationDefinitionReader:
    """FastAPI dependency: the configured reader for this process's settings."""
    return build_application_definition_reader(settings)


__all__ = [
    "build_application_definition_reader",
    "build_definition_repository",
    "get_application_definition_reader",
]
