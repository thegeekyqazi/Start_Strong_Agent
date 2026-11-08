"""Publication context for saved definitions (DEV-B-BUNDLE-002 s5.1, s7.3).

M1: the opportunity identity comes only from what the source/fixture itself declared,
kept as a claim. Without one, publication is blocked; nothing is invented.
M3 extends this with an exact, version-pinned funding case resolved through the funding
feature's public ``FundingCaseReader``.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

from strongstart_contracts import ErrorCode, SessionIdentity
from strongstart_contracts.application_publication import (
    FundingContextBinding,
    PublicationContext,
    SaveDefinitionRequest,
)
from strongstart_contracts.automation_intake import ApplicationIntakeResult
from strongstart_contracts.funding_review import (
    FundingCaseEnvelope,
    FundingCaseIntegrityError,
    FundingCaseNotFound,
    FundingCaseVersionChanged,
)
from strongstart_contracts.ports import CapabilityUnavailable

from ...config import Settings
from ..dev_b_store import StoreBusy, StoreUnavailable
from ..funding.public import (  # supported public factories only
    build_funding_case_reader,
    build_funding_case_version_pin,
)
from .definitions import blocked, declared_context
from .intake_errors import intake_error


def resolve_publication_context(
    cmd: SaveDefinitionRequest,
    intake: ApplicationIntakeResult,
    identity: SessionIdentity,
    settings: Settings,
) -> PublicationContext:
    declared = declared_context(intake)
    if cmd.funding_case_id is not None and cmd.funding_case_version is not None:
        return _case_context(
            cmd.funding_case_id, cmd.funding_case_version, intake, identity, settings, declared
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


def _case_context(
    case_id: str,
    version: int,
    intake: ApplicationIntakeResult,
    identity: SessionIdentity,
    settings: Settings,
    declared: object,
) -> PublicationContext:
    """Bind one exact, staff-selected case version. Disagreement is held, never overwritten."""
    from strongstart_contracts.application_publication import DeclaredContext

    assert isinstance(declared, DeclaredContext)
    org = identity.organization_id
    reader = build_funding_case_reader(settings)
    try:
        env: FundingCaseEnvelope = reader.get_version(org, case_id, version)
        current = reader.get_current(org, case_id)
    except FundingCaseNotFound:
        raise intake_error(
            404, ErrorCode.FORBIDDEN, "context_not_found", "funding case not found"
        ) from None
    except FundingCaseIntegrityError:
        raise intake_error(
            409,
            ErrorCode.VERSION_CONFLICT,
            "integrity_failure",
            "the funding case failed verification; nothing was saved",
        ) from None
    except CapabilityUnavailable:
        raise intake_error(
            503,
            ErrorCode.CAPABILITY_UNAVAILABLE,
            "context_unavailable",
            "no funding case repository is available",
        ) from None
    if current.version.version != version:
        raise intake_error(
            409,
            ErrorCode.VERSION_CONFLICT,
            "context_changed",
            "the selected funding case has a newer version; select it explicitly",
            current_version=current.version.version,
        )
    opp = env.opportunity
    if opp is None:
        raise intake_error(
            422,
            ErrorCode.VALIDATION_FAILED,
            "context_incomplete",
            "the funding case does not establish funder, stream, cycle and a source yet",
            missing=env.opportunity_missing,
        )
    v = env.version
    linked = {link.capture_id for link in v.capture_links} | {a.capture_id for a in v.anchors}
    conflicts: list[str] = []
    lineage = intake.input.capture
    if lineage is not None:
        if lineage.capture_id not in linked:
            conflicts.append("this capture is not linked to the selected funding case")
        link = next((x for x in v.capture_links if x.capture_id == lineage.capture_id), None)
        if link is not None:
            for name, claimed, chosen in (
                ("opportunity", link.declared_opportunity_id, opp.opportunity_id),
                ("stream", link.declared_stream_id, opp.stream_id),
                ("cycle", link.declared_cycle_id, opp.cycle_id),
            ):
                if claimed is not None and claimed != chosen:
                    conflicts.append(
                        f"the capture declares {name} {claimed!r}; the case selects {chosen!r}"
                    )
    if conflicts:
        raise intake_error(
            409,
            ErrorCode.VERSION_CONFLICT,
            "context_conflict",
            "the source and the selected funding case disagree; held for staff review",
            conflicts=conflicts,
        )
    notes = ["Opportunity identity comes from the exact staff-selected funding case version."]
    if declared.opportunity_id is not None and lineage is None:
        notes.append(
            f"The source also declares opportunity {declared.opportunity_id!r}; kept as a claim "
            "(different ID namespace), not used as authority."
        )
    return PublicationContext(
        opportunity_id=opp.opportunity_id,
        opportunity_basis="funding_case",
        declared=declared,
        binding=FundingContextBinding(
            funding_case_id=case_id,
            funding_case_version=version,
            funding_case_digest=env.version_digest,
            opportunity_id=opp.opportunity_id,
            funder_id=opp.funder_id,
            stream_id=opp.stream_id,
            cycle_id=opp.cycle_id,
            stage=v.context.stage,
            case_review_status=env.review_status,
            linked_capture_ids=sorted(linked),
        ),
        notes=notes,
    )


@contextlib.contextmanager
def publication_guard(
    context: PublicationContext, identity: SessionIdentity, settings: Settings
) -> Iterator[None]:
    """Make the bound case's current-version check atomic with the definition commit.

    ``resolve_publication_context`` is only an early, user-friendly check. The binding is
    re-validated here *while holding the funding-case store's cross-process lock*, and the
    caller commits the definition inside this block, so no case revision can commit between
    the check and the write. Lock order: cases -> definitions (never the reverse).
    """
    binding = context.binding
    if binding is None:
        yield
        return
    pin = build_funding_case_version_pin(settings)
    if pin is None:
        raise intake_error(
            503,
            ErrorCode.CAPABILITY_UNAVAILABLE,
            "context_unavailable",
            "no funding case repository is available",
        )
    # Body exceptions (the definition commit) are re-raised through this generator; only
    # the pin's own entry failures match the case-specific handlers below.
    try:
        with pin.pinned(
            identity.organization_id,
            binding.funding_case_id,
            binding.funding_case_version,
            binding.funding_case_digest,
        ):
            yield
    except FundingCaseVersionChanged as exc:
        raise intake_error(
            409,
            ErrorCode.VERSION_CONFLICT,
            "context_changed",
            "the selected funding case changed before the definition was saved; nothing "
            "was published",
            current_version=exc.current_version,
        ) from None
    except FundingCaseNotFound:
        raise intake_error(
            404, ErrorCode.FORBIDDEN, "context_not_found", "funding case not found"
        ) from None
    except FundingCaseIntegrityError:
        raise intake_error(
            409,
            ErrorCode.VERSION_CONFLICT,
            "integrity_failure",
            "the funding case failed verification; nothing was saved",
        ) from None
    except StoreBusy:
        raise intake_error(
            503, ErrorCode.CAPABILITY_UNAVAILABLE, "store_busy", "store is busy; retry later"
        ) from None
    except StoreUnavailable as exc:
        raise intake_error(
            503, ErrorCode.CAPABILITY_UNAVAILABLE, exc.reason, "funding case store unavailable"
        ) from None
