"""Saved application definitions (DEV-B-BUNDLE-002 M1, owner: automation/B2).

Publishes an immutable version of one bounded intake and exposes it through the public
``ApplicationDefinitionReader``. Saving re-runs the existing importer on the exact source,
keeps the exact input bytes in the Dev B local store, and never trusts a client-built
question set, organization, actor, approval or provenance label.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from strongstart_contracts import ErrorCode, SessionIdentity
from strongstart_contracts.application_publication import (
    MAX_PUBLISHED_QUESTIONS,
    ApplicationDefinitionIntegrityError,
    ApplicationDefinitionNotFound,
    DeclaredContext,
    DefinitionList,
    DefinitionSummary,
    PublicationContext,
    PublicationIntegrity,
    PublishedApplicationVersion,
    QuestionIdMapping,
    SaveDefinitionRequest,
)
from strongstart_contracts.automation import ApplicationDefinition, QuestionSet
from strongstart_contracts.automation_intake import (
    ApplicationIntakeResult,
    CaptureIntakeSource,
    FixtureIntakeSource,
    HtmlIntakeSource,
    IntakeQuestion,
    StructuredJsonIntakeSource,
)

from ...config import Settings
from ...errors import ApiError
from ..dev_b_store import (
    HistoryLimit,
    IdempotencyReused,
    IntegrityFailure,
    LocalVersionStore,
    NotFound,
    StoreBusy,
    StoreUnavailable,
    TooLarge,
    VersionConflict,
    canonical_json,
    sha256_hex,
)
from .capture import CaptureIntegrity, CaptureNotFound, CaptureSource
from .intake_errors import intake_error
from .normalize import to_shared_question
from .registry import INTAKE_FIXTURES, read_fixture_bytes
from .service import run_intake, unresolved_items

COLLECTION = "definitions"
QS_ID = re.compile(r"^qs-(def-[0-9a-f]{26})-v([0-9]{1,2})$")
DEF_ID = re.compile(r"^def-[0-9a-f]{26}$")

CONSUMER_NOTES = [
    "Saved is not reviewed or approved: approval_status=not_approved, prefill_permitted=false.",
    "Limits, conflicts, unknown units/conventions and conditions keep their imported meaning; "
    "nothing is resolved on the consumer's behalf. C owns counting (APP-01) and approval.",
    "question_version equals the definition version; every question advances on a revision.",
    "The rich intake keeps ORIGINAL question IDs; use id_mapping to join it to published IDs.",
]


# --------------------------------------------------------------------------- identity


def published_question_id(definition_id: str, original_id: str) -> str:
    candidate = f"{definition_id}:{original_id}"
    if len(candidate) <= 128:
        return candidate
    return f"{definition_id}:h{sha256_hex(original_id.encode())[:24]}"


def question_set_id(definition_id: str, version: int) -> str:
    return f"qs-{definition_id}-v{version}"


def _normalized_digest(
    question_set: QuestionSet,
    application_definition: ApplicationDefinition,
    intake: ApplicationIntakeResult,
    id_mapping: list[QuestionIdMapping],
    unresolved: list[Any],
    context: PublicationContext,
) -> str:
    return sha256_hex(
        canonical_json(
            {
                "question_set": question_set.model_dump(mode="json"),
                "application_definition": application_definition.model_dump(mode="json"),
                "intake": intake.model_dump(mode="json"),
                "id_mapping": [m.model_dump(mode="json") for m in id_mapping],
                "unresolved": [u.model_dump(mode="json") for u in unresolved],
                "context": context.model_dump(mode="json"),
            }
        )
    )


class AmbiguousIdentity(Exception):
    pass


def build_publication(
    *,
    organization_id: str,
    actor: str,
    definition_id: str,
    version: int,
    previous: PublishedApplicationVersion | None,
    intake: ApplicationIntakeResult,
    raw_size: int,
    context: PublicationContext,
    now: datetime,
) -> PublishedApplicationVersion:
    originals = [q.question_id for q in intake.questions]
    if len(set(originals)) != len(originals):
        raise AmbiguousIdentity("duplicate original question IDs; identity is ambiguous")
    mapping = {o: published_question_id(definition_id, o) for o in originals}
    if len(set(mapping.values())) != len(mapping):
        raise AmbiguousIdentity("published question IDs would collide")
    if previous is not None:
        for m in previous.id_mapping:  # retained identity within one lineage
            if m.original_question_id in mapping and (
                mapping[m.original_question_id] != m.published_question_id
            ):
                raise AmbiguousIdentity("published ID for a retained question would change")

    def publish(q: IntakeQuestion) -> IntakeQuestion:
        conditions = [
            c.model_copy(
                update={
                    "depends_on_question_id": mapping.get(c.depends_on_question_id)
                    if c.depends_on_question_id
                    else None
                }
            )
            for c in q.conditions
        ]
        return q.model_copy(
            update={
                "question_id": mapping[q.question_id],
                "question_version": version,
                "conditions": conditions,
            }
        )

    qs_id = question_set_id(definition_id, version)
    question_set = QuestionSet(
        question_set_id=qs_id,
        opportunity_id=context.opportunity_id,
        questions=[to_shared_question(publish(q), intake.stream_id) for q in intake.questions],
        provenance=intake.provenance,
    )
    application_definition = ApplicationDefinition(
        application_definition_id=f"appdef-{definition_id}-v{version}",
        opportunity_id=context.opportunity_id,
        question_set_id=qs_id,
        form_id=None,  # inspection stays separate until version-bound prefill work
        provenance=intake.provenance,
    )
    id_mapping = [
        QuestionIdMapping(
            original_question_id=q.question_id,
            published_question_id=mapping[q.question_id],
            question_version=version,
            order=q.order,
        )
        for q in intake.questions
    ]
    unresolved = [
        u.model_copy(update={"question_id": mapping.get(u.question_id, u.question_id)})
        for u in unresolved_items(intake)
    ]
    prev_originals = {m.original_question_id for m in previous.id_mapping} if previous else set()
    return PublishedApplicationVersion(
        organization_id=organization_id,
        definition_id=definition_id,
        version=version,
        question_set_id=qs_id,
        revision_of_version=version - 1 if version > 1 else None,
        saved_by=actor,
        saved_at=now,
        integrity=PublicationIntegrity(
            raw_input_sha256=intake.input.sha256,
            raw_input_size=raw_size,
            normalized_digest=_normalized_digest(
                question_set, application_definition, intake, id_mapping, unresolved, context
            ),
        ),
        question_set=question_set,
        application_definition=application_definition,
        intake=intake,
        id_mapping=id_mapping,
        added_original_ids=[o for o in originals if previous and o not in prev_originals],
        removed_original_ids=sorted(prev_originals - set(originals)) if previous else [],
        unresolved=unresolved,
        context=context,
        provenance=intake.provenance,
        is_fixture=intake.is_fixture,
        mode_label=intake.mode_label,
        consumer_notes=CONSUMER_NOTES,
    )


def verify_publication(
    pub: PublishedApplicationVersion, organization_id: str, definition_id: str, version: int
) -> None:
    """Cross-field checks beyond the envelope digest. Raises IntegrityFailure."""
    ok = (
        pub.organization_id == organization_id
        and pub.definition_id == definition_id
        and pub.version == version
        and pub.question_set_id == question_set_id(definition_id, version)
        and pub.question_set.question_set_id == pub.question_set_id
        and pub.application_definition.question_set_id == pub.question_set_id
        and pub.integrity.raw_input_sha256 == pub.intake.input.sha256
        and pub.integrity.raw_input_size == pub.intake.input.byte_size
        and pub.question_set.opportunity_id == pub.context.opportunity_id
    )
    if ok:
        originals = [q.question_id for q in pub.intake.questions]
        ok = (
            [m.original_question_id for m in pub.id_mapping] == originals
            and all(
                m.published_question_id
                == published_question_id(definition_id, m.original_question_id)
                and m.question_version == version
                for m in pub.id_mapping
            )
            and [q.question_id for q in pub.question_set.questions]
            == [m.published_question_id for m in pub.id_mapping]
            and all(q.question_version == version for q in pub.question_set.questions)
        )
    if ok:
        ok = pub.integrity.normalized_digest == _normalized_digest(
            pub.question_set,
            pub.application_definition,
            pub.intake,
            pub.id_mapping,
            pub.unresolved,
            pub.context,
        )
    if not ok:
        raise IntegrityFailure("saved definition failed cross-field verification")


# --------------------------------------------------------------------------- repository


class DefinitionRepository:
    """Development/test repository over the Dev B local store; implements the reader."""

    is_fixture = False

    def __init__(self, store: LocalVersionStore) -> None:
        self.store = store

    def _coll(self, organization_id: str) -> Any:
        return self.store.collection(organization_id, COLLECTION)

    def _load(self, organization_id: str, definition_id: str, version: int) -> Any:
        record = self._coll(organization_id).read(definition_id, version)
        try:
            pub = PublishedApplicationVersion.model_validate(record)
        except ValidationError:
            raise IntegrityFailure("saved definition does not match its schema") from None
        verify_publication(pub, organization_id, definition_id, version)
        self.store.read_blob(
            organization_id, pub.integrity.raw_input_sha256, pub.integrity.raw_input_size
        )
        return pub

    # -- reader port ----------------------------------------------------------

    def get_version(
        self, organization_id: str, question_set_id: str
    ) -> PublishedApplicationVersion:
        m = QS_ID.fullmatch(question_set_id)
        if m is None:
            raise ApplicationDefinitionNotFound(question_set_id)
        try:
            pub: PublishedApplicationVersion = self._load(
                organization_id, m.group(1), int(m.group(2))
            )
            return pub
        except NotFound:
            raise ApplicationDefinitionNotFound(question_set_id) from None
        except IntegrityFailure:
            raise ApplicationDefinitionIntegrityError(question_set_id) from None

    def get_current(self, organization_id: str, definition_id: str) -> PublishedApplicationVersion:
        if not DEF_ID.fullmatch(definition_id):
            raise ApplicationDefinitionNotFound(definition_id)
        try:
            version = self._coll(organization_id).current_version(definition_id)
            if version == 0:
                raise ApplicationDefinitionNotFound(definition_id)
            pub: PublishedApplicationVersion = self._load(organization_id, definition_id, version)
            return pub
        except NotFound:
            raise ApplicationDefinitionNotFound(definition_id) from None
        except IntegrityFailure:
            raise ApplicationDefinitionIntegrityError(definition_id) from None

    # -- listing --------------------------------------------------------------

    def list(self, organization_id: str, cursor: str | None, limit: int) -> DefinitionList:
        page = self._coll(organization_id).list_ids(cursor, limit)
        items: list[DefinitionSummary] = []
        for did in page.object_ids:
            try:
                pub = self.get_current(organization_id, did)
            except (ApplicationDefinitionIntegrityError, ApplicationDefinitionNotFound):
                items.append(
                    DefinitionSummary(
                        definition_id=did,
                        status="integrity_failure",
                        detail="This saved definition failed verification; content withheld.",
                    )
                )
                continue
            items.append(
                DefinitionSummary(
                    definition_id=did,
                    status="ok",
                    current_version=pub.version,
                    question_set_id=pub.question_set_id,
                    title=pub.intake.title.display_text if pub.intake.title else None,
                    question_count=len(pub.question_set.questions),
                    unresolved_count=len(pub.unresolved),
                    opportunity_id=pub.context.opportunity_id,
                    saved_at=pub.saved_at,
                    saved_by=pub.saved_by,
                    is_fixture=pub.is_fixture,
                    mode_label=pub.mode_label,
                    raw_input_sha256=pub.integrity.raw_input_sha256,
                )
            )
        return DefinitionList(
            items=items,
            next_cursor=page.next_cursor,
            more=page.more,
            incomplete=page.incomplete,
            limit=limit,
        )

    # -- save -----------------------------------------------------------------

    def save(
        self,
        *,
        organization_id: str,
        actor: str,
        cmd: SaveDefinitionRequest,
        intake: ApplicationIntakeResult,
        raw: bytes,
        context: PublicationContext,
    ) -> tuple[PublishedApplicationVersion, bool]:
        sha = self.store.put_blob(organization_id, raw)
        if sha != intake.input.sha256:  # pragma: no cover - guarded by the caller
            raise IntegrityFailure("input bytes changed during save")
        command = cmd.model_dump(mode="json", exclude={"idempotency_key"})
        command_hash = sha256_hex(canonical_json(command))
        now = datetime.now(UTC)

        def build(object_id: str, version: int, prev: dict[str, Any] | None) -> dict[str, Any]:
            previous = None
            if prev is not None:
                previous = PublishedApplicationVersion.model_validate(prev)
                verify_publication(previous, organization_id, object_id, version - 1)
            pub = build_publication(
                organization_id=organization_id,
                actor=actor,
                definition_id=object_id,
                version=version,
                previous=previous,
                intake=intake,
                raw_size=len(raw),
                context=context,
                now=now,
            )
            dumped: dict[str, Any] = pub.model_dump(mode="json")
            return dumped

        result = self._coll(organization_id).commit(
            idempotency_key=cmd.idempotency_key,
            command_hash=command_hash,
            object_id=cmd.definition_id,
            expected_version=cmd.expected_version or 0,
            build=build,
            id_prefix="def",
        )
        pub: PublishedApplicationVersion = self._load(
            organization_id, result.object_id, result.version
        )
        return pub, result.replayed


# --------------------------------------------------------------------------- service


def intake_with_input_bytes(
    source: Any, identity: SessionIdentity, settings: Settings, capture: CaptureSource
) -> tuple[ApplicationIntakeResult, bytes]:
    """Run the existing bounded intake and return the exact parsed bytes (no refetch)."""
    result = run_intake(source, identity, settings, capture)
    if isinstance(source, FixtureIntakeSource):
        data = read_fixture_bytes(INTAKE_FIXTURES[source.fixture_id].relative_path)
    elif isinstance(source, StructuredJsonIntakeSource | HtmlIntakeSource):
        data = source.content.encode("utf-8")
    elif isinstance(source, CaptureIntakeSource):
        try:
            data = capture.read_artifact(
                identity.organization_id, source.capture_id, source.artifact_id
            )
        except (CaptureNotFound, CaptureIntegrity):
            raise _changed("captured bytes changed or disappeared during save") from None
    else:  # pragma: no cover - the request union is closed
        raise intake_error(422, ErrorCode.VALIDATION_FAILED, "unsupported_input", "unknown mode")
    if sha256_hex(data) != result.input.sha256 or len(data) != result.input.byte_size:
        raise _changed("input bytes changed between parsing and saving")
    return result, data


def _changed(message: str) -> ApiError:
    return intake_error(409, ErrorCode.VERSION_CONFLICT, "input_changed", message)


def declared_context(intake: ApplicationIntakeResult) -> DeclaredContext:
    basis: Any = (
        "fixture_registry"
        if intake.input.origin == "fixture"
        else ("source_declared_claim" if intake.opportunity_id else "none")
    )
    return DeclaredContext(
        opportunity_id=intake.opportunity_id,
        stream_id=intake.stream_id,
        cycle_id=intake.cycle_id,
        basis=basis,
    )


def store_error(exc: Exception) -> ApiError:
    """Map Dev B store failures onto the shared envelope (reason in details)."""
    if isinstance(exc, ApplicationDefinitionNotFound | NotFound):
        return intake_error(
            404, ErrorCode.FORBIDDEN, "definition_not_found", "saved definition not found"
        )
    if isinstance(exc, ApplicationDefinitionIntegrityError | IntegrityFailure):
        return intake_error(
            409,
            ErrorCode.VERSION_CONFLICT,
            "integrity_failure",
            "stored definition failed integrity verification; content withheld",
        )
    if isinstance(exc, AmbiguousIdentity):
        return intake_error(
            422, ErrorCode.VALIDATION_FAILED, "ambiguous_question_identity", str(exc)
        )
    if isinstance(exc, VersionConflict):
        return intake_error(
            409,
            ErrorCode.VERSION_CONFLICT,
            "version_conflict",
            "the definition changed; reload and revise the current version",
            current_version=exc.current_version,
        )
    if isinstance(exc, IdempotencyReused):
        return intake_error(
            409,
            ErrorCode.VERSION_CONFLICT,
            "idempotency_key_reused",
            "this idempotency key was already used for a different save",
        )
    if isinstance(exc, HistoryLimit):
        return intake_error(
            413, ErrorCode.VALIDATION_FAILED, "history_limit", "version history limit reached"
        )
    if isinstance(exc, TooLarge):
        return intake_error(
            413, ErrorCode.VALIDATION_FAILED, "input_too_large", "saved envelope too large"
        )
    if isinstance(exc, StoreBusy):
        return intake_error(
            503, ErrorCode.CAPABILITY_UNAVAILABLE, "store_busy", "store is busy; retry later"
        )
    if isinstance(exc, OSError):
        return intake_error(
            503,
            ErrorCode.CAPABILITY_UNAVAILABLE,
            "store_write_failed",
            "the saved-definition store could not complete the write; nothing was committed",
        )
    if isinstance(exc, StoreUnavailable):
        return intake_error(
            503, ErrorCode.CAPABILITY_UNAVAILABLE, exc.reason, "saved-definition store unavailable"
        )
    raise exc


def blocked(message: str, **details: Any) -> ApiError:
    return intake_error(422, ErrorCode.VALIDATION_FAILED, "publication_blocked", message, **details)


def check_publishable(intake: ApplicationIntakeResult) -> None:
    if not intake.questions:
        raise blocked(
            "no supported questions were extracted; nothing can be published",
            coverage=intake.coverage.status,
        )
    if len(intake.questions) > MAX_PUBLISHED_QUESTIONS:
        raise intake_error(
            413,
            ErrorCode.VALIDATION_FAILED,
            "too_many_questions",
            f"saved definitions are limited to {MAX_PUBLISHED_QUESTIONS} questions",
        )
