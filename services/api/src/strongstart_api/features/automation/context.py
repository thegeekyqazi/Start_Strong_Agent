"""Publication context for saved definitions (DEV-B-BUNDLE-002 s5.1, s7.3).

M1: the opportunity identity comes only from what the source/fixture itself declared,
kept as a claim. Without one, publication is blocked; nothing is invented.
M3 extends this with an exact, version-pinned funding case resolved through the funding
feature's public ``FundingCaseReader``.
"""

from __future__ import annotations

from strongstart_contracts import ErrorCode, SessionIdentity
from strongstart_contracts.application_publication import (
    PublicationContext,
    SaveDefinitionRequest,
)
from strongstart_contracts.automation_intake import ApplicationIntakeResult

from ...config import Settings
from .definitions import blocked, declared_context
from .intake_errors import intake_error


def resolve_publication_context(
    cmd: SaveDefinitionRequest,
    intake: ApplicationIntakeResult,
    identity: SessionIdentity,
    settings: Settings,
) -> PublicationContext:
    declared = declared_context(intake)
    if cmd.funding_case_id is not None:
        raise intake_error(
            503,
            ErrorCode.CAPABILITY_UNAVAILABLE,
            "context_unavailable",
            "funding-case context selection is not available yet",
        )
    if declared.opportunity_id is None:
        raise blocked(
            "the opportunity is unknown, so no shared QuestionSet can be published; select a "
            "funding case with an established opportunity identity",
            missing=["opportunity_id"],
        )
    basis = "fixture_registry" if declared.basis == "fixture_registry" else "source_declared_claim"
    notes = (
        ["Opportunity ID comes from the server-registered fixture (engineering-derived)."]
        if basis == "fixture_registry"
        else ["Opportunity ID is the source's own declaration: a claim, not reviewed authority."]
    )
    return PublicationContext(
        opportunity_id=declared.opportunity_id,
        opportunity_basis=basis,
        declared=declared,
        notes=notes,
    )
