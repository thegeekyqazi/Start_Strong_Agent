"""B2-AUTO-001 orchestration: intake, fixture inspection and handoff export.

Bounded request-based operations (no JobStore exists yet; recorded as a scoped
deviation from engineering s14). Every result is nonpersistent and not approved.
Organization scope always comes from the server-side identity.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from strongstart_contracts import ErrorCode, SessionIdentity
from strongstart_contracts.automation_intake import (
    ApplicationIntakeResult,
    AutomationHandoffExport,
    BrowserActivity,
    CaptureIntakeSource,
    CaptureLineage,
    Finding,
    FixtureEntry,
    FixtureIntakeSource,
    FormInspectionResult,
    HtmlIntakeSource,
    InputRepresentation,
    InspectionBudget,
    IntakeCoverage,
    IntakeQuestion,
    SourceLocator,
    StructuredJsonIntakeSource,
    UnresolvedItem,
)
from strongstart_contracts.common import (
    DateKnowledge,
    Provenance,
    ProvenanceClass,
    SourceReference,
)
from strongstart_contracts.ports import CapabilityUnavailable

from ...config import Settings
from . import html_form, structured
from .capture import CaptureNotFound, CaptureRecord, CaptureSource
from .inspection import build_form_map, check_mappings, fingerprint, observed_fields
from .inspector import InspectionFailure, InspectorConfig, inspect_page
from .intake_errors import (
    fixture_not_allowed,
    intake_error,
    source_unavailable,
    too_large,
    unsupported,
)
from .normalize import NORMALIZATION_VERSION, QuestionDraft, exact, finalize_question, project
from .registry import (
    FIXTURE_LABEL,
    FIXTURE_PROVENANCE,
    FORM_VERSIONS,
    INTAKE_FIXTURES,
    PORTAL_FIXTURES,
    REP_PORTAL_EXPECTED_MAP,
    portal_page,
    read_fixture_bytes,
)

MAX_CAPTURE_BYTES = 1024 * 1024
UPLOAD_PROVENANCE = Provenance(
    provenance_class=ProvenanceClass.SUPPLIED,
    is_simulated=False,
    note="Staff-uploaded input; authority unverified; the uploader did not label it simulated.",
)
UPLOAD_LABEL = "UPLOADED - unverified staff-supplied input; authority not reviewed; not approved."

Origin = Literal["fixture", "uploaded_unverified", "capture"]


def fixtures_enabled(settings: Settings) -> bool:
    return settings.fixture_mode and settings.environment != "production"


def require_fixtures(settings: Settings) -> None:
    if not fixtures_enabled(settings):
        raise fixture_not_allowed(
            "fixture intake/inspection is only available in local fixture mode"
        )


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _import_id(org: str, mode: str, data: bytes) -> str:
    return "imp-" + _sha(f"{org}\0{mode}\0".encode() + data)[:24]


class _Ctx:
    """Per-import evidence context: one immutable representation, many locators."""

    def __init__(
        self,
        *,
        data: bytes,
        origin: Origin,
        provenance: Provenance,
        source_id: str,
        source_version_id: str,
        captured_at: datetime | None = None,
    ) -> None:
        self.data = data
        self.sha = _sha(data)
        self.origin = origin
        self.provenance = provenance
        self.source_id = source_id
        self.source_version_id = source_version_id
        self.captured_at = captured_at

    def source_ref(self, locator: str) -> SourceReference:
        return SourceReference(
            source_id=self.source_id,
            source_version_id=self.source_version_id,
            locator=locator[:500],
            provenance=self.provenance,
            captured_at=self.captured_at,
            publication_date=DateKnowledge(status="unknown"),
            content_hash=self.sha,
            verification_status="unverified",
        )


def _representation(
    ctx: _Ctx,
    *,
    rep_type: Any,
    media_type: str,
    parser_id: str,
    parser_version: str,
    capture: CaptureLineage | None = None,
) -> InputRepresentation:
    return InputRepresentation(
        representation_id="rep-" + ctx.sha[:24],
        origin=ctx.origin,
        representation_type=rep_type,
        media_type=media_type,
        byte_size=len(ctx.data),
        sha256=ctx.sha,
        integrity="hash_verified_against_capture_record" if capture else "computed_on_receipt",
        parser_id=parser_id,
        parser_version=parser_version,
        normalization_version=NORMALIZATION_VERSION,
        storage="capture_port_reference" if capture else "nonpersistent_response",
        capture=capture,
    )


def _finalize(
    drafts: list[QuestionDraft],
) -> tuple[list[IntakeQuestion], list[Any]]:
    questions: list[IntakeQuestion] = []
    findings: list[Any] = []
    for d in drafts:
        q, f = finalize_question(d)
        questions.append(q)
        findings.extend(f)
    return questions, findings


# --------------------------------------------------------------------------- intake


def _structured_result(
    org: str,
    data: bytes,
    ctx: _Ctx,
    label: str,
    is_fixture: bool,
    capture_source: CaptureSource,
) -> ApplicationIntakeResult:
    if len(data) > structured.MAX_JSON_BYTES:
        raise too_large(structured.MAX_JSON_BYTES, "structured JSON definition")
    definition, drafts, original_evidence, findings = structured.parse_structured(
        data, ctx.source_ref
    )
    if definition.source is not None:
        findings.append(_resolve_claimed_source(org, definition.source, capture_source))
        original_evidence["claimed_source"] = definition.source.model_dump()
    if definition.provenance_note:
        original_evidence["provenance_note"] = definition.provenance_note
    questions, qfindings = _finalize(drafts)
    import_id = _import_id(org, f"{ctx.origin}:structured_json", data)
    qs, app, notes = project(
        import_id=import_id,
        definition_id=definition.definition_id,
        opportunity_id=definition.opportunity_id,
        form_id=None,
        questions=questions,
        provenance=ctx.provenance,
        primary_stream=definition.stream_id,
    )
    return ApplicationIntakeResult(
        import_id=import_id,
        application_definition_id=definition.definition_id,
        opportunity_id=definition.opportunity_id,
        stream_id=definition.stream_id,
        cycle_id=definition.cycle_id,
        title=(
            exact(definition.title, SourceLocator(kind="json_pointer", value="/title"))
            if definition.title
            else None
        ),
        is_fixture=is_fixture,
        mode_label=label,
        input=_representation(
            ctx,
            rep_type="structured_json",
            media_type="application/json",
            parser_id=structured.PARSER_ID,
            parser_version=structured.PARSER_VERSION,
        ),
        provenance=ctx.provenance,
        coverage=IntakeCoverage(
            status="supported_complete",
            questions_extracted=len(questions),
            controls_seen=0,
            unsupported_elements=sum(q.answer_kind == "unsupported" for q in questions),
            notes=notes,
        ),
        questions=questions,
        findings=[*findings, *qfindings],
        original_evidence=original_evidence,
        question_set=qs,
        application_definition=app,
    )


def _resolve_claimed_source(org: str, src: structured.InSource, capture: CaptureSource) -> Any:
    try:
        record = capture.get_record(org, src.capture_id)
        art = next(a for a in record.artifacts if a.artifact_id == src.artifact_id)
        data = capture.read_artifact(org, src.capture_id, src.artifact_id)
        ok = _sha(data) == art.sha256
    except (CaptureNotFound, CapabilityUnavailable, StopIteration):
        ok = False
    if ok:
        return Finding(
            code="source_claim_unresolved",
            severity="info",
            message=f"Claimed source {src.capture_id}/{src.artifact_id} resolved through the "
            "capture port with a matching hash. The definition itself is still unreviewed.",
        )
    return Finding(
        code="source_claim_unresolved",
        severity="warning",
        message="The definition names a source that could not be resolved through an authorized "
        "capture adapter; it is shown as an unverified claim only.",
    )


def _html_result(
    org: str,
    data: bytes,
    ctx: _Ctx,
    label: str,
    is_fixture: bool,
    *,
    rep_type: Any = "html_form",
    media_type: str = "text/html; charset=utf-8",
    capture: CaptureLineage | None = None,
    opportunity_id: str | None = None,
    stream_id: str | None = None,
    cycle_id: str | None = None,
) -> ApplicationIntakeResult:
    if len(data) > html_form.MAX_HTML_BYTES:
        raise too_large(html_form.MAX_HTML_BYTES, "HTML input")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise unsupported("HTML input is not valid UTF-8") from None
    if "\x00" in text:
        raise unsupported("HTML input contains NUL bytes")
    parsed = html_form.parse_html(text, ctx.source_ref)
    questions, qfindings = _finalize(parsed.drafts)
    findings = [*parsed.findings, *qfindings]
    if questions and all(q.scope == "unknown" for q in questions):
        findings.append(
            Finding(
                code="scope_unknown",
                severity="info",
                message="HTML forms do not state organization/program scope; all scopes unknown.",
            )
        )
    if not questions:
        findings.append(
            Finding(
                code="no_supported_form_content",
                severity="blocker",
                message="No supported form controls were found. The input is preserved as "
                "evidence; a manual definition is needed. No questions were invented.",
            )
        )
    status: Any
    if not questions:
        status = "unsupported_needs_manual_definition"
    elif parsed.unsupported_elements or parsed.limit_reached:
        status = "supported_partial"
    else:
        status = "supported_complete"
    import_id = _import_id(org, f"{ctx.origin}:html", data)
    qs, app, notes = project(
        import_id=import_id,
        definition_id=None,
        opportunity_id=opportunity_id,
        form_id=parsed.form_id,
        questions=questions,
        provenance=ctx.provenance,
        primary_stream=stream_id,
    )
    return ApplicationIntakeResult(
        import_id=import_id,
        application_definition_id=app.application_definition_id if app else None,
        opportunity_id=opportunity_id,
        stream_id=stream_id,
        cycle_id=cycle_id,
        title=parsed.title,
        is_fixture=is_fixture,
        mode_label=label,
        input=_representation(
            ctx,
            rep_type=rep_type,
            media_type=media_type,
            parser_id=html_form.PARSER_ID,
            parser_version=html_form.PARSER_VERSION,
            capture=capture,
        ),
        provenance=ctx.provenance,
        coverage=IntakeCoverage(
            status=status,
            questions_extracted=len(questions),
            controls_seen=parsed.controls_seen,
            unsupported_elements=parsed.unsupported_elements,
            notes=notes,
        ),
        questions=questions,
        findings=findings,
        evidence_excerpt=parsed.excerpt,
        evidence_excerpt_truncated=parsed.excerpt_truncated,
        question_set=qs,
        application_definition=app,
    )


def _unsupported_result(
    org: str,
    data: bytes,
    ctx: _Ctx,
    label: str,
    is_fixture: bool,
    *,
    rep_type: Any,
    media_type: str,
    capture: CaptureLineage,
    code: Any,
    message: str,
    text_excerpt: bool,
) -> ApplicationIntakeResult:
    excerpt = None
    truncated = False
    if text_excerpt:
        try:
            text = data.decode("utf-8", errors="strict")
            truncated = len(text) > html_form.EXCERPT_CHARS
            excerpt = exact(
                text[: html_form.EXCERPT_CHARS],
                SourceLocator(kind="whole_input", value="artifact text"),
            )
        except UnicodeDecodeError:
            excerpt = None
    return ApplicationIntakeResult(
        import_id=_import_id(org, f"{ctx.origin}:unsupported", data),
        opportunity_id=capture.opportunity_id,
        stream_id=capture.stream_id,
        cycle_id=capture.cycle_id,
        is_fixture=is_fixture,
        mode_label=label,
        input=_representation(
            ctx,
            rep_type=rep_type,
            media_type=media_type,
            parser_id="none",
            parser_version="0",
            capture=capture,
        ),
        provenance=ctx.provenance,
        coverage=IntakeCoverage(
            status="unsupported_needs_manual_definition",
            questions_extracted=0,
            controls_seen=0,
            unsupported_elements=0,
            notes=[message],
        ),
        findings=[Finding(code=code, severity="blocker", message=message)],
        evidence_excerpt=excerpt,
        evidence_excerpt_truncated=truncated,
    )


def _capture_result(
    org: str, src: CaptureIntakeSource, capture_source: CaptureSource
) -> ApplicationIntakeResult:
    try:
        record: CaptureRecord = capture_source.get_record(org, src.capture_id)
    except CaptureNotFound:
        raise source_unavailable() from None
    except CapabilityUnavailable:
        raise intake_error(
            503,
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "source_unavailable",
            "no capture producer is configured for this environment",
        ) from None
    art = next((a for a in record.artifacts if a.artifact_id == src.artifact_id), None)
    if art is None:
        raise source_unavailable()
    if art.byte_size > MAX_CAPTURE_BYTES:
        raise too_large(MAX_CAPTURE_BYTES, "captured artifact")
    try:
        data = capture_source.read_artifact(org, src.capture_id, src.artifact_id)
    except (CaptureNotFound, CapabilityUnavailable):
        raise source_unavailable("captured artifact bytes are unavailable") from None
    if len(data) > MAX_CAPTURE_BYTES:
        raise too_large(MAX_CAPTURE_BYTES, "captured artifact")
    actual = _sha(data)
    if actual != art.sha256 or len(data) != art.byte_size:
        raise intake_error(
            409,
            ErrorCode.VERSION_CONFLICT,
            "hash_mismatch",
            "stored capture bytes do not match the registered artifact hash; nothing imported",
            capture_id=record.capture_id,
            artifact_id=art.artifact_id,
        )
    lineage = CaptureLineage(
        capture_id=record.capture_id,
        source_version_id=record.source_version_id,
        artifact_id=art.artifact_id,
        representation_type=art.representation_type,
        opportunity_id=record.opportunity_id,
        stream_id=record.stream_id,
        cycle_id=record.cycle_id,
        original_url=record.urls.original,
        requested_url=record.urls.requested,
        final_url=record.urls.final,
        final_url_status=record.urls.final_status,
        provider=record.provider,
        captured_at=record.captured_at,
        authority_review_status=record.authority_review_status,
        extraction_warnings=[f"coverage={record.extraction.coverage}", *record.extraction.warnings],
        capture_is_fixture=capture_source.is_fixture,
    )
    ctx = _Ctx(
        data=data,
        origin="capture",
        provenance=record.provenance,
        source_id=record.source_id,
        source_version_id=record.source_version_id,
        captured_at=record.captured_at,
    )
    label = (
        "CAPTURE (B2 FIXTURE PRODUCER) - synthetic capture record; not a live capture; "
        "not approved."
        if capture_source.is_fixture
        else f"CAPTURE - authority review: {record.authority_review_status}; not approved."
    )
    media = art.media_type.lower()
    rep = art.representation_type
    rep_type: Any = (
        rep
        if rep in ("provider_html", "provider_raw_html", "original_http_bytes", "provider_markdown")
        else "unknown"
    )
    if media.startswith("application/pdf") or data.startswith(b"%PDF"):
        return _unsupported_result(
            org, data, ctx, label, capture_source.is_fixture, rep_type="pdf",
            media_type=art.media_type, capture=lineage, code="pdf_parsing_not_implemented",
            message="Original PDF parsing is not implemented in this task; the artifact is "
            "preserved by reference and needs a manual definition.", text_excerpt=False,
        )  # fmt: skip
    if rep == "provider_markdown" or media.startswith("text/markdown"):
        return _unsupported_result(
            org, data, ctx, label, capture_source.is_fixture, rep_type="provider_markdown",
            media_type=art.media_type, capture=lineage, code="markdown_not_parsed",
            message="Provider markdown/prose is shown as read-only context only; no questions "
            "are extracted from prose.", text_excerpt=True,
        )  # fmt: skip
    if media.startswith("text/html") and rep in (
        "provider_html",
        "provider_raw_html",
        "original_http_bytes",
    ):
        return _html_result(
            org, data, ctx, label, capture_source.is_fixture, rep_type=rep_type,
            media_type=art.media_type, capture=lineage, opportunity_id=record.opportunity_id,
            stream_id=record.stream_id, cycle_id=record.cycle_id,
        )  # fmt: skip
    return _unsupported_result(
        org, data, ctx, label, capture_source.is_fixture, rep_type=rep_type,
        media_type=art.media_type, capture=lineage, code="no_supported_form_content",
        message=f"Representation {rep} ({art.media_type}) is not a supported intake format.",
        text_excerpt=False,
    )  # fmt: skip


def run_intake(
    source: Any,
    identity: SessionIdentity,
    settings: Settings,
    capture_source: CaptureSource,
) -> ApplicationIntakeResult:
    org = identity.organization_id
    if isinstance(source, FixtureIntakeSource):
        require_fixtures(settings)
        fx = INTAKE_FIXTURES.get(source.fixture_id)
        if fx is None:
            raise fixture_not_allowed(f"'{source.fixture_id}' is not a registered intake fixture")
        data = read_fixture_bytes(fx.relative_path)
        ctx = _Ctx(
            data=data,
            origin="fixture",
            provenance=FIXTURE_PROVENANCE,
            source_id=f"fixture-{fx.fixture_id}",
            source_version_id=f"fixture-{fx.fixture_id}-{_sha(data)[:12]}",
        )
        if fx.kind == "structured_definition":
            return _structured_result(org, data, ctx, FIXTURE_LABEL, True, capture_source)
        return _html_result(
            org, data, ctx, FIXTURE_LABEL, True, opportunity_id="demo-gos", stream_id="standard"
        )
    if isinstance(source, StructuredJsonIntakeSource | HtmlIntakeSource):
        try:
            data = source.content.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            raise unsupported("input contains unpaired surrogate characters") from None
        h = _sha(data)
        ctx = _Ctx(
            data=data,
            origin="uploaded_unverified",
            provenance=UPLOAD_PROVENANCE,
            source_id=f"upload-{h[:16]}",
            source_version_id=f"upload-{h[:24]}",
        )
        if isinstance(source, StructuredJsonIntakeSource):
            return _structured_result(org, data, ctx, UPLOAD_LABEL, False, capture_source)
        return _html_result(org, data, ctx, UPLOAD_LABEL, False)
    if isinstance(source, CaptureIntakeSource):
        return _capture_result(org, source, capture_source)
    raise unsupported("unknown intake mode")


# --------------------------------------------------------------------------- inspection


def run_inspection(
    fixture_id: str,
    identity: SessionIdentity,
    settings: Settings,
    config: InspectorConfig,
    capture_source: CaptureSource,
    *,
    expected_form_version: int | None = None,
    client_expected_fingerprint: str | None = None,
) -> FormInspectionResult:
    require_fixtures(settings)
    portal = PORTAL_FIXTURES.get(fixture_id)
    if portal is None:
        raise fixture_not_allowed(f"'{fixture_id}' is not a registered portal fixture")
    versions = FORM_VERSIONS[portal.form_id]
    version = expected_form_version or max(versions)
    if version not in versions:
        raise intake_error(
            422,
            ErrorCode.VALIDATION_FAILED,
            "unknown_form_version",
            f"form {portal.form_id} has no stored map version {version}",
            known_versions=sorted(versions),
        )
    expected_fp = versions[version]
    definition = run_intake(
        FixtureIntakeSource(mode="fixture", fixture_id=portal.definition_fixture_id),
        identity,
        settings,
        capture_source,
    )
    started = time.monotonic()
    try:
        raw = inspect_page(portal_page(portal), ready_selector=portal.ready_selector, config=config)
    except InspectionFailure as exc:
        status = 503 if exc.reason == "browser_unavailable" else 504
        code = (
            ErrorCode.CAPABILITY_UNAVAILABLE
            if exc.reason == "browser_unavailable"
            else ErrorCode.DEPENDENCY_UNAVAILABLE
        )
        raise intake_error(
            status,
            code,
            exc.reason,
            exc.message,
            elapsed_ms=int((time.monotonic() - started) * 1000),
        ) from None
    fields = observed_fields(raw.fields)
    fp = fingerprint(fields)
    questions = {q.question_id: q for q in definition.questions}
    checks, findings = check_mappings(fields, REP_PORTAL_EXPECTED_MAP, questions)
    fp_status: Literal["matches_expected", "changed"] = (
        "matches_expected" if fp == expected_fp else "changed"
    )
    if fp_status == "changed":
        findings.insert(
            0,
            Finding(
                code="fingerprint_changed",
                severity="blocker",
                message=f"Observed form fingerprint differs from stored map version {version}; "
                "the stored map is not reused. Remap and re-review.",
            ),
        )
    if client_expected_fingerprint and client_expected_fingerprint != fp:
        findings.insert(
            0,
            Finding(
                code="mapping_changed",
                severity="blocker",
                message="Observed fingerprint differs from the fingerprint the caller expected.",
            ),
        )
    if raw.truncated:
        findings.append(
            Finding(
                code="field_limit_reached",
                severity="blocker",
                message=f"More than {config.max_fields} controls; enumeration truncated.",
            )
        )
    a = raw.activity
    for e in a.entries[:20]:
        blocked_code: Any = {"popup": "blocked_popup", "download": "blocked_download"}.get(
            e.resource_type,
            "blocked_navigation" if e.resource_type == "document" else "blocked_request",
        )
        findings.append(
            Finding(
                code=blocked_code,
                severity="info",
                message=f"Blocked {e.method} {e.target} ({e.reason}).",
            )
        )
    blocking = any(f.severity == "blocker" for f in findings)
    map_valid = not blocking and all(c.status == "matched" for c in checks)
    form_map = (
        build_form_map(
            form_id=portal.form_id,
            version=version,
            origin=portal.origin_label,
            fp=fp,
            checks=checks,
            fields=fields,
            provenance=FIXTURE_PROVENANCE,
        )
        if map_valid
        else None
    )
    return FormInspectionResult(
        inspection_id="insp-" + uuid.uuid4().hex[:24],
        fixture_id=portal.fixture_id,
        form_id=portal.form_id,
        origin=portal.origin_label,
        mode_label=FIXTURE_LABEL + " Read-only inspection; no values entered; not approved.",
        question_set_id=definition.question_set.question_set_id
        if definition.question_set
        else "unknown",
        ready_condition=portal.ready_selector,
        fingerprint=fp,
        expected_form_version=version,
        expected_fingerprint=expected_fp,
        client_expected_fingerprint=client_expected_fingerprint,
        fingerprint_status=fp_status,
        map_status="valid" if map_valid else "invalid",
        fields=fields,
        fields_truncated=raw.truncated,
        mappings=checks,
        findings=findings,
        form_map=form_map,
        activity=BrowserActivity(
            requests_allowed=a.allowed,
            requests_blocked=a.blocked,
            mutation_requests_blocked=a.mutation_blocked,
            fixture_server_mutation_hits=raw.fixture_server_mutation_hits,
            popups_blocked=a.popups,
            downloads_blocked=a.downloads,
            navigations_blocked=a.navigations_blocked,
            blocked_log=a.entries,
            blocked_log_truncated=a.truncated,
        ),
        browser_name="chromium",
        browser_version=raw.browser_version,
        budget=InspectionBudget(
            timeout_ms=config.timeout_ms,
            max_fields=config.max_fields,
            max_text_chars=config.max_text_chars,
        ),
    )


# --------------------------------------------------------------------------- export


def unresolved_items(intake: ApplicationIntakeResult) -> list[UnresolvedItem]:
    out: list[UnresolvedItem] = []
    for q in intake.questions:
        for c in q.limit_conflicts:
            kind: Any = (
                "limit_conflict"
                if c.kind == "competing_instruction_limits"
                else "native_maxlength_conflict"
            )
            out.append(UnresolvedItem(question_id=q.question_id, kind=kind, detail=c.description))
        for lim in q.limits:
            if lim.kind in ("instruction_text", "structured_definition"):
                if lim.unit == "unknown":
                    out.append(
                        UnresolvedItem(
                            question_id=q.question_id,
                            kind="unknown_limit_unit",
                            detail=f'"{lim.evidence.display_text}" has no unit',
                        )
                    )
                elif (
                    lim.unit in ("words", "characters")
                    and lim.convention_status != "declared_in_source"
                ):
                    out.append(
                        UnresolvedItem(
                            question_id=q.question_id,
                            kind="unknown_counting_convention",
                            detail=f"{lim.maximum} {lim.unit}: counting convention unknown",
                        )
                    )
        if q.required_status == "unknown":
            out.append(
                UnresolvedItem(
                    question_id=q.question_id, kind="required_status_unknown", detail="not stated"
                )
            )
        if any(c.status == "unresolved" for c in q.conditions) or (
            q.required_status == "conditional" and not q.conditions
        ):
            out.append(
                UnresolvedItem(
                    question_id=q.question_id,
                    kind="condition_unresolved",
                    detail="condition not resolved",
                )
            )
        if q.answer_kind == "file" and (
            q.attachment is None
            or None
            in (q.attachment.accepted_types, q.attachment.max_size_bytes, q.attachment.max_count)
        ):
            out.append(
                UnresolvedItem(
                    question_id=q.question_id,
                    kind="attachment_constraints_unknown",
                    detail="type/size/count partly unknown",
                )
            )
        if q.scope == "unknown":
            out.append(
                UnresolvedItem(
                    question_id=q.question_id,
                    kind="scope_unknown",
                    detail="organization/program scope not stated",
                )
            )
    return out


def build_export(
    intake: ApplicationIntakeResult, inspection: FormInspectionResult | None
) -> AutomationHandoffExport:
    notes = [
        "Not approved. Imported limits are provisional until authority review; a valid form "
        "map is not permission to fill it.",
        "C owns counting (APP-01), drafting, approval and the ApprovedAnswerResolver. "
        "B2-AUTO-002 consumes those for prefill/read-back; no prefill exists here.",
        "persisted=false: this export is a snapshot of a nonpersistent server result.",
    ]
    if intake.is_fixture or (inspection is not None):
        notes.append(
            "Fixture material is engineering-derived (original_guide_present=false); the "
            "representative portal is not the United Way portal."
        )
    if (
        inspection is not None
        and intake.question_set is not None
        and (inspection.question_set_id != intake.question_set.question_set_id)
    ):
        notes.append(
            f"The inspection compared the portal with fixture question set "
            f"{inspection.question_set_id}, not with this import's question set."
        )
    return AutomationHandoffExport(
        export_id="exp-" + uuid.uuid4().hex[:24],
        exported_at=datetime.now(UTC),
        label="B2 intake/form-map handoff - NOT APPROVED - imported/provisional"
        + (" - FIXTURE" if intake.is_fixture else ""),
        is_fixture=intake.is_fixture,
        intake=intake,
        inspection=inspection,
        question_set=intake.question_set,
        application_definition=intake.application_definition,
        form_map=inspection.form_map if inspection is not None else None,
        unresolved=unresolved_items(intake),
        consumer_notes=notes,
    )


def capture_fixture_entries(capture_source: CaptureSource, org: str) -> list[FixtureEntry]:
    if not capture_source.is_fixture:
        return []
    return [
        FixtureEntry(
            fixture_id=f"{r.capture_id}:{a.artifact_id}",
            kind="capture",
            variant="representative" if r.capture_id == "cap-fixture-portal-html" else "malformed",
            label="FIXTURE capture record (B2 fixture producer; not a live capture)",
            description=f"{a.representation_type} {a.media_type} ({r.capture_id})",
        )
        for r in capture_source.list_records(org)
        for a in r.artifacts
    ]
