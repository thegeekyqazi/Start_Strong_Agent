"""Funding cases, evidence anchors, reviews and evaluations (DEV-B-BUNDLE-002 M3/M4).

Development/test repository over the Dev B local store. Implements the public
``FundingCaseReader``. All identity comes from the server; anchors are resolved against
hash-verified stored capture bytes through ``CapturedDocumentReader`` (never a URL).
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from strongstart_contracts import (
    DateKnowledge,
    Opportunity,
    Provenance,
    ProvenanceClass,
    RequirementCondition,
    RequirementSet,
    SourceReference,
)
from strongstart_contracts.discovery import (
    CapturedDocumentReader,
    CaptureIntegrityError,
    CaptureNotFoundError,
)
from strongstart_contracts.funding_review import (
    MAX_ANCHORS,
    MAX_QUOTE_CODE_POINTS,
    MAX_REQUIREMENTS,
    CaptureLink,
    CaseReview,
    ChangeObservation,
    DeadlineSpec,
    EvaluateCommand,
    EvaluationEntry,
    EvaluationList,
    EvaluationReport,
    EvidenceAnchor,
    FundingCaseCommand,
    FundingCaseEnvelope,
    FundingCaseIntegrityError,
    FundingCaseList,
    FundingCaseNotFound,
    FundingCaseSummary,
    FundingCaseVersion,
    FundingCaseVersionChanged,
    FundingContext,
    Requirement,
    ReviewCommand,
    SourceFinding,
)

from ..dev_b_store import (
    IntegrityFailure,
    LocalVersionStore,
    NotFound,
    VersionConflict,
    canonical_json,
    sha256_hex,
)
from . import rules

CASES = "cases"
REVIEWS = "case-reviews"
EVALUATIONS = "evaluations"
CASE_OBSERVATIONS = "case-observations"
MAX_OBSERVATIONS_READ = 100

REVIEW_STATEMENT = (
    "Staff confirmed these typed interpretations of the cited passages for this exact case "
    "version. This does not verify organizational facts, approve answers, grant browser "
    "permissions or establish funder eligibility."
)
CONDITION_KIND = {
    "deadline": "deadline",
    "project_window": "other",
    "amount_range": "limit",
    "geography": "eligibility",
    "organization_type": "eligibility",
    "activity": "eligibility",
    "invitation": "stage",
}


class CaseCommandError(Exception):
    """A command was well-formed but cannot be applied; carries a funding reason."""

    def __init__(self, status: int, reason: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.status = status
        self.reason = reason
        self.message = message
        self.details = details


def derived_id(prefix: str, case_id: str, label: str) -> str:
    return f"{prefix}-{sha256_hex(f'{case_id}\0{label}'.encode())[:16]}"


def digest(record: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(record))


def load[M: BaseModel](model: type[M], record: dict[str, Any]) -> M:
    """Validate a stored record in JSON mode (strict models accept ISO dates there)."""
    return model.model_validate_json(canonical_json(record))


# --------------------------------------------------------------------------- resolution


def resolve_links(
    reader: CapturedDocumentReader, org: str, cmd: FundingCaseCommand
) -> list[CaptureLink]:
    ids = {link.capture_id for link in cmd.capture_links} | {a.capture_id for a in cmd.anchors}
    links: list[CaptureLink] = []
    for capture_id in sorted(ids):
        try:
            r = reader.get_record(org, capture_id)
        except CaptureNotFoundError:
            raise CaseCommandError(
                404, "capture_not_found", "a linked capture was not found", capture_id=capture_id
            ) from None
        except CaptureIntegrityError:
            raise CaseCommandError(
                409, "integrity_failure", "a linked capture failed verification"
            ) from None
        links.append(
            CaptureLink(
                capture_id=r.capture_id,
                source_id=r.source_reference.source_id,
                source_version_id=r.source_reference.source_version_id,
                page_title=r.page_title,
                requested_url=r.requested_url,
                final_url=r.final_url,
                coverage=r.coverage,
                provider_mode=r.provider_mode,
                is_simulated=r.provenance.is_simulated,
                authority_review=r.authority_review,
                declared_opportunity_id=r.opportunity_id,
                declared_stream_id=r.stream_id,
                declared_cycle_id=r.cycle_id,
            )
        )
    return links


def resolve_anchors(
    reader: CapturedDocumentReader, org: str, cmd: FundingCaseCommand
) -> list[EvidenceAnchor]:
    keys = [a.anchor_key for a in cmd.anchors]
    if len(keys) != len(set(keys)):
        raise CaseCommandError(422, "invalid_input", "anchor keys must be unique")
    out: list[EvidenceAnchor] = []
    for a in cmd.anchors:
        where = {"anchor_key": a.anchor_key}
        if len(a.quote) > MAX_QUOTE_CODE_POINTS:
            raise CaseCommandError(
                413,
                "anchor_too_large",
                f"select a narrower passage (at most {MAX_QUOTE_CODE_POINTS} characters)",
                **where,
            )
        try:
            record = reader.get_record(org, a.capture_id)
            verified = reader.read_artifact(org, a.capture_id, a.artifact_id)
        except CaptureNotFoundError:
            raise CaseCommandError(
                404, "capture_not_found", "anchor source not found", **where
            ) from None
        except CaptureIntegrityError:
            raise CaseCommandError(
                409, "integrity_failure", "anchor source failed integrity verification", **where
            ) from None
        if verified.artifact.sha256 != a.expected_artifact_sha256:
            raise CaseCommandError(
                409,
                "anchor_source_changed",
                "the stored representation differs from the one staff selected from",
                **where,
            )
        try:
            text = verified.content.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise CaseCommandError(422, "anchor_mismatch", "source is not UTF-8", **where) from None
        if a.end > len(text):
            raise CaseCommandError(
                422, "anchor_mismatch", "anchor range is outside the stored text", **where
            )
        if text[a.start : a.end] != a.quote:
            raise CaseCommandError(
                422,
                "anchor_mismatch",
                "the quote does not exactly match the stored text at that range",
                **where,
            )
        out.append(
            EvidenceAnchor(
                anchor_key=a.anchor_key,
                capture_id=record.capture_id,
                artifact_id=verified.artifact.artifact_id,
                source_id=record.source_reference.source_id,
                source_version_id=record.source_reference.source_version_id,
                artifact_sha256=verified.artifact.sha256,
                representation=verified.artifact.representation,
                start=a.start,
                end=a.end,
                quote=a.quote,
                coverage=record.coverage,
                warnings=list(record.warnings)[:20],
                provider_mode=record.provider_mode,
                is_simulated=record.provenance.is_simulated,
            )
        )
    return out


def build_requirements(cmd: FundingCaseCommand, anchors: list[EvidenceAnchor]) -> list[Requirement]:
    keys = [r.requirement_key for r in cmd.requirements]
    if len(keys) != len(set(keys)):
        raise CaseCommandError(422, "invalid_input", "requirement keys must be unique")
    known = {a.anchor_key for a in anchors}
    out = []
    for r in cmd.requirements:
        missing = [k for k in r.anchor_keys if k not in known]
        if missing:
            raise CaseCommandError(
                422,
                "invalid_input",
                "every requirement needs a verified evidence anchor",
                requirement_key=r.requirement_key,
                missing_anchor_keys=missing,
            )
        out.append(
            Requirement(
                requirement_key=r.requirement_key,
                spec=r.spec,
                anchor_keys=list(r.anchor_keys),
                scope=r.scope,
                applicability=r.applicability,
                interpretation=r.interpretation,
                rule_ids=rules.RULE_IDS[r.spec.kind],
            )
        )
    return out


def build_context(case_id: str, cmd: FundingCaseCommand) -> FundingContext:
    c = cmd.context
    unknown = [
        name
        for name, value in (
            ("funder", c.funder_label),
            ("stream", c.stream_label),
            ("cycle", c.cycle_label),
            ("stage", None if c.stage == "unknown" else c.stage),
        )
        if value is None
    ]
    return FundingContext(
        funder_label=c.funder_label,
        stream_label=c.stream_label,
        cycle_label=c.cycle_label,
        stage=c.stage,
        opportunity_title=c.opportunity_title,
        funder_id=derived_id("fnd", case_id, c.funder_label) if c.funder_label else None,
        stream_id=derived_id("str", case_id, c.stream_label) if c.stream_label else None,
        cycle_id=derived_id("cyc", case_id, c.cycle_label) if c.cycle_label else None,
        unknown_fields=unknown,
    )


# --------------------------------------------------------------------------- repository


class FundingCaseRepository:
    is_fixture = False

    def __init__(self, store: LocalVersionStore, reader: CapturedDocumentReader | None) -> None:
        self.store = store
        self.reader = reader

    def _cases(self, org: str) -> Any:
        return self.store.collection(org, CASES)

    def _require_reader(self) -> CapturedDocumentReader:
        if self.reader is None:
            raise CaseCommandError(503, "store_unavailable", "no capture store is available")
        return self.reader

    # -- writes ---------------------------------------------------------------

    def save(
        self, org: str, actor: str, case_id: str | None, cmd: FundingCaseCommand
    ) -> tuple[FundingCaseEnvelope, bool]:
        if len(cmd.requirements) > MAX_REQUIREMENTS or len(cmd.anchors) > MAX_ANCHORS:
            raise CaseCommandError(413, "too_large", "case version exceeds its rule/anchor budget")
        if (case_id is None) != (cmd.expected_version is None):
            raise CaseCommandError(
                422, "invalid_input", "revisions name the case and its expected version"
            )
        reader = self._require_reader()
        links = resolve_links(reader, org, cmd)
        anchors = resolve_anchors(reader, org, cmd)
        requirements = build_requirements(cmd, anchors)
        command_hash = sha256_hex(
            canonical_json(
                {"case_id": case_id, **cmd.model_dump(mode="json", exclude={"idempotency_key"})}
            )
        )
        now = datetime.now(UTC)

        def build(object_id: str, version: int, prev: dict[str, Any] | None) -> dict[str, Any]:
            record = FundingCaseVersion(
                organization_id=org,
                case_id=object_id,
                version=version,
                revision_of_version=version - 1 if version > 1 else None,
                created_by=actor,
                created_at=now,
                context=build_context(object_id, cmd),
                capture_links=links,
                anchors=anchors,
                requirements=requirements,
            )
            dumped: dict[str, Any] = record.model_dump(mode="json")
            return dumped

        result = self._cases(org).commit(
            idempotency_key=cmd.idempotency_key,
            command_hash=command_hash,
            object_id=case_id,
            expected_version=cmd.expected_version or 0,
            build=build,
            id_prefix="case",
        )
        return self.get_version(org, result.object_id, result.version), result.replayed

    def review(
        self, org: str, actor: str, case_id: str, version: int, cmd: ReviewCommand
    ) -> tuple[FundingCaseEnvelope, bool]:
        env = self.get_version(org, case_id, version)
        if not env.is_current:
            raise CaseCommandError(
                409,
                "not_current_version",
                "only the current case version can be reviewed",
                current_version=env.current_version,
            )
        if cmd.version_digest != env.version_digest:
            raise CaseCommandError(
                409, "stale_snapshot", "the reviewed digest does not match this version"
            )
        keys = sorted(r.requirement_key for r in env.version.requirements)
        if not keys or sorted(cmd.requirement_keys) != keys:
            raise CaseCommandError(
                409,
                "review_scope_mismatch",
                "review must name exactly this version's requirements",
                requirement_keys=keys,
            )
        now = datetime.now(UTC)
        reviews = self.store.collection(org, REVIEWS)

        def build(object_id: str, v: int, prev: dict[str, Any] | None) -> dict[str, Any]:
            dumped: dict[str, Any] = CaseReview(
                case_id=case_id,
                version=version,
                version_digest=env.version_digest,
                reviewer=actor,
                reviewed_at=now,
                requirement_keys=keys,
                statement=REVIEW_STATEMENT,
            ).model_dump(mode="json")
            return dumped

        try:
            result = reviews.commit(
                idempotency_key=cmd.idempotency_key,
                command_hash=sha256_hex(
                    canonical_json(
                        cmd.model_dump(mode="json", exclude={"idempotency_key"})
                        | {"case": case_id, "version": version}
                    )
                ),
                object_id=f"{case_id}.v{version}",
                expected_version=0,
                build=build,
            )
        except VersionConflict:
            raise CaseCommandError(
                409, "already_reviewed", "this version is already reviewed"
            ) from None
        return self.get_version(org, case_id, version), result.replayed

    @contextlib.contextmanager
    def pinned(self, org: str, case_id: str, version: int, version_digest: str) -> Iterator[None]:
        """``FundingCaseVersionPin``: hold the case lock while the caller writes."""
        coll = self._cases(org)
        with coll.locked():
            try:
                current = coll.current_version(case_id)
            except NotFound:
                raise FundingCaseNotFound(case_id) from None
            if current == 0:
                raise FundingCaseNotFound(case_id)
            if current != version:
                raise FundingCaseVersionChanged(current)
            try:
                _, d = self._load_version(org, case_id, version)
            except IntegrityFailure:
                raise FundingCaseIntegrityError(case_id) from None
            if d != version_digest:
                raise FundingCaseVersionChanged(current)
            yield

    def record_observation(self, org: str, observation: ChangeObservation) -> None:
        if observation.linked_case_id is None:
            return
        coll = self.store.collection(org, CASE_OBSERVATIONS, scope=observation.linked_case_id)
        coll.commit(
            idempotency_key=observation.observation_id,
            command_hash=observation.observation_id,
            object_id=observation.observation_id,
            expected_version=0,
            build=lambda o, v, p: observation.model_dump(mode="json"),
        )

    # -- reads ----------------------------------------------------------------

    def _load_version(self, org: str, case_id: str, version: int) -> tuple[FundingCaseVersion, str]:
        record = self._cases(org).read(case_id, version)
        try:
            v = load(FundingCaseVersion, record)
        except ValidationError:
            raise IntegrityFailure("case version does not match its schema") from None
        if v.organization_id != org or v.case_id != case_id or v.version != version:
            raise IntegrityFailure("case version identity mismatch")
        anchor_keys = {a.anchor_key for a in v.anchors}
        if any(k not in anchor_keys for r in v.requirements for k in r.anchor_keys):
            raise IntegrityFailure("requirement cites an anchor that is not stored")
        return v, digest(record)

    def _review(
        self, org: str, case_id: str, version: int, version_digest: str
    ) -> CaseReview | None:
        try:
            record = self.store.collection(org, REVIEWS).read(f"{case_id}.v{version}", 1)
        except NotFound:
            return None
        try:
            review = load(CaseReview, record)
        except ValidationError:
            raise IntegrityFailure("review record does not match its schema") from None
        if review.version_digest != version_digest or review.case_id != case_id:
            raise IntegrityFailure("review is bound to a different digest")
        return review

    def observations(self, org: str, case_id: str) -> list[ChangeObservation]:
        coll = self.store.collection(org, CASE_OBSERVATIONS, scope=case_id)
        page = coll.list_ids(None, MAX_OBSERVATIONS_READ)
        out = []
        for oid in page.object_ids:
            try:
                out.append(load(ChangeObservation, coll.read(oid, 1)))
            except (NotFound, IntegrityFailure, ValidationError):
                continue
        return out

    def get_version(self, org: str, case_id: str, version: int) -> FundingCaseEnvelope:
        try:
            v, d = self._load_version(org, case_id, version)
            review = self._review(org, case_id, version, d)
            current = self._cases(org).current_version(case_id)
            observations = self.observations(org, case_id)
        except NotFound:
            raise FundingCaseNotFound(case_id) from None
        except IntegrityFailure:
            raise FundingCaseIntegrityError(case_id) from None
        return build_envelope(v, d, review, current, observations)

    def get_current(self, org: str, case_id: str) -> FundingCaseEnvelope:
        try:
            current = self._cases(org).current_version(case_id)
        except NotFound:
            raise FundingCaseNotFound(case_id) from None
        if current == 0:
            raise FundingCaseNotFound(case_id)
        return self.get_version(org, case_id, current)

    def list(self, org: str, cursor: str | None, limit: int) -> FundingCaseList:
        page = self._cases(org).list_ids(cursor, limit)
        items: list[FundingCaseSummary] = []
        for cid in page.object_ids:
            try:
                env = self.get_current(org, cid)
            except (FundingCaseNotFound, FundingCaseIntegrityError):
                items.append(FundingCaseSummary(case_id=cid, status="integrity_failure"))
                continue
            c = env.version.context
            items.append(
                FundingCaseSummary(
                    case_id=cid,
                    status="ok",
                    current_version=env.version.version,
                    title=c.opportunity_title,
                    funder_label=c.funder_label,
                    stream_label=c.stream_label,
                    cycle_label=c.cycle_label,
                    stage=c.stage,
                    review_status=env.review_status,
                    source_status=env.source_status,
                    requirement_count=len(env.version.requirements),
                    created_at=env.version.created_at,
                )
            )
        return FundingCaseList(
            items=items,
            next_cursor=page.next_cursor,
            more=page.more,
            incomplete=page.incomplete,
            limit=limit,
        )

    # -- evaluations ------------------------------------------------------------

    def evaluate(
        self, org: str, actor: str, case_id: str, cmd: EvaluateCommand
    ) -> tuple[EvaluationReport, bool]:
        env = self.get_version(org, case_id, cmd.case_version)
        blocked = None
        if env.review is None:
            blocked = (
                "Not reviewed: this interpretation is inactive until staff review this exact "
                "case version."
            )
        elif env.source_status == "requires_re_review":
            blocked = "A cited source changed or could not be rechecked; it requires re-review."
        clock = cmd.clock or datetime.now(UTC)
        anchors = {a.anchor_key: a for a in env.version.anchors}
        results, excluded, group = rules.evaluate_case(
            env.version.requirements,
            env.version.context,
            cmd.scope,
            clock,
            cmd.inputs,
            anchors,
            blocked_reason=blocked,
        )
        inputs_digest = sha256_hex(
            canonical_json(
                {
                    "case_digest": env.version_digest,
                    "review_digest": env.review.version_digest if env.review else None,
                    "clock": clock.isoformat(),
                    "scope": cmd.scope.model_dump(mode="json"),
                    "inputs": cmd.inputs.model_dump(mode="json"),
                    "evaluator": rules.EVALUATOR_VERSION,
                }
            )
        )
        summary = scenario_summary(group, results, excluded)
        provenances = sorted({p for p in _input_provenances(cmd)})
        reliance = (
            "Reliance: not confirmed. Inputs are "
            + (", ".join(provenances) if provenances else "absent")
            + " scenario values; no verified organizational facts were available (Dev A "
            "EvidenceProvider mapping not configured). Nothing was written to the knowledge "
            "store. Funder eligibility is not confirmed."
        )
        now = datetime.now(UTC)
        coll = self.store.collection(org, EVALUATIONS, scope=case_id)

        def build(object_id: str, v: int, prev: dict[str, Any] | None) -> dict[str, Any]:
            dumped: dict[str, Any] = EvaluationReport(
                evaluation_id=object_id,
                organization_id=org,
                case_id=case_id,
                case_version=cmd.case_version,
                case_digest=env.version_digest,
                review_digest=env.review.version_digest if env.review else None,
                clock=clock,
                clock_source="request" if cmd.clock else "server",
                scope=cmd.scope,
                inputs=cmd.inputs,
                inputs_digest=inputs_digest,
                readiness_at_evaluation=env.readiness,
                results=results,
                excluded=excluded,
                eligibility_group_outcome=group,
                scenario_summary=summary,
                reliance_explanation=reliance,
                created_by=actor,
                created_at=now,
            ).model_dump(mode="json")
            return dumped

        result = coll.commit(
            idempotency_key=cmd.idempotency_key,
            command_hash=sha256_hex(
                canonical_json(
                    cmd.model_dump(mode="json", exclude={"idempotency_key"})
                    | {"server_clock": None if cmd.clock else "server"}
                )
            ),
            object_id=None,
            expected_version=0,
            build=build,
            id_prefix="eval",
        )
        return load(EvaluationReport, result.record), result.replayed

    def list_evaluations(
        self, org: str, case_id: str, cursor: str | None, limit: int
    ) -> EvaluationList:
        current = self.get_current(org, case_id)
        observations = self.observations(org, case_id)
        coll = self.store.collection(org, EVALUATIONS, scope=case_id)
        page = coll.list_ids(cursor, limit)
        items = []
        for eid in page.object_ids:
            try:
                report = load(EvaluationReport, coll.read(eid, 1))
            except (NotFound, IntegrityFailure, ValidationError):
                continue
            reasons = []
            if report.case_version != current.version.version:
                reasons.append(
                    f"case version {current.version.version} is newer than the evaluated "
                    f"version {report.case_version}"
                )
            later = [
                o
                for o in observations
                if o.overall != "unchanged" and o.observed_at > report.created_at
            ]
            if later:
                reasons.append("a source change/recheck problem was observed after this evaluation")
            reasons.append("time-stamped at its evaluation clock; re-evaluate at the next action")
            items.append(
                EvaluationEntry(report=report, stale=len(reasons) > 1, stale_reasons=reasons)
            )
        return EvaluationList(
            items=items,
            next_cursor=page.next_cursor,
            more=page.more,
            incomplete=page.incomplete,
            limit=limit,
        )


def _input_provenances(cmd: EvaluateCommand) -> list[str]:
    out = []
    for value in cmd.inputs.model_dump().values():
        if isinstance(value, dict) and "provenance" in value:
            out.append(str(value["provenance"]))
    return out


def scenario_summary(group: str | None, results: list[Any], excluded: list[Any]) -> str:
    if group == "met":
        head = (
            "These encoded rules are met using these inputs; funder eligibility is not confirmed."
        )
    elif group == "not_met":
        head = "At least one encoded rule is not met using these inputs."
    elif group == "not_applicable":
        head = "The encoded eligibility rules do not apply to this scenario."
    elif group == "unknown":
        head = "The encoded rules cannot be decided with these inputs (missing or unreviewed)."
    else:
        head = "No reviewed eligibility rule applies to this scope."
    deadlines = [r for r in results if r.kind == "deadline"]
    if not deadlines:
        head += " No reviewed deadline applies to this stream/stage/cycle."
    if excluded:
        head += f" {len(excluded)} requirement(s) were not used (see reasons)."
    return head


# --------------------------------------------------------------------------- envelope


def _source_refs(v: FundingCaseVersion) -> list[SourceReference]:
    refs = []
    for a in v.anchors:
        refs.append(
            SourceReference(
                source_id=a.source_id,
                source_version_id=a.source_version_id,
                locator=f"{a.artifact_id} code points {a.start}-{a.end}",
                provenance=_provenance(a.is_simulated),
                publication_date=DateKnowledge(status="unknown"),
                content_hash=a.artifact_sha256,
                verification_status="unverified",
            )
        )
    if not refs:
        for link in v.capture_links:
            refs.append(
                SourceReference(
                    source_id=link.source_id,
                    source_version_id=link.source_version_id,
                    provenance=_provenance(link.is_simulated),
                    publication_date=DateKnowledge(status="unknown"),
                    verification_status="unverified",
                )
            )
    return refs


def _provenance(simulated: bool) -> Provenance:
    if simulated:
        return Provenance(
            provenance_class=ProvenanceClass.SIMULATED,
            is_simulated=True,
            note="Simulated/fixture capture; not a real funder source.",
        )
    return Provenance(
        provenance_class=ProvenanceClass.PUBLIC,
        is_simulated=False,
        note="Publicly captured page; interpretation is staff-reviewed only.",
    )


def build_envelope(
    v: FundingCaseVersion,
    version_digest: str,
    review: CaseReview | None,
    current: int,
    observations: list[ChangeObservation],
) -> FundingCaseEnvelope:
    captures = {link.capture_id for link in v.capture_links} | {a.capture_id for a in v.anchors}
    cutoff = review.reviewed_at if review else v.created_at
    findings = [
        SourceFinding(
            observation_id=o.observation_id,
            capture_id=o.old_capture_id,
            overall=o.overall,
            observed_at=o.observed_at,
            message=o.explanation,
        )
        for o in observations
        if o.old_capture_id in captures and o.overall != "unchanged" and o.observed_at > cutoff
    ]
    source_status = "requires_re_review" if findings else "current"
    if not v.requirements:
        readiness = "no_rules"
    elif review is None:
        readiness = "not_reviewed"
    elif findings:
        readiness = "requires_re_review"
    else:
        readiness = "ready_for_evaluation"
    c = v.context
    refs = _source_refs(v)
    missing = [
        name
        for name, value in (
            ("funder", c.funder_id),
            ("stream", c.stream_id),
            ("cycle", c.cycle_id),
            ("source link", refs[0] if refs else None),
        )
        if value is None
    ]
    opportunity = None
    notes = [
        "A funding case is a staff-selected context, not a certified opportunity.",
        "Opportunity.deadline is a date only; use the reviewed DeadlineSpec for time/zone.",
    ]
    if not missing:
        assert c.funder_id and c.stream_id and c.cycle_id
        deadline = DateKnowledge(status="unknown")
        if review is not None:
            for r in v.requirements:
                if (
                    isinstance(r.spec, DeadlineSpec)
                    and r.spec.date is not None
                    and (rules.scope_mismatch(r, c, rules.case_scope(c, _empty_scope())) is None)
                ):
                    deadline = DateKnowledge(status="known", value=r.spec.date)
                    break
        title = c.opportunity_title or " - ".join(
            x for x in (c.funder_label, c.stream_label, c.cycle_label) if x
        )
        opportunity = Opportunity(
            opportunity_id=f"opp-{v.case_id.removeprefix('case-')}",
            funder_id=c.funder_id,
            stream_id=c.stream_id,
            cycle_id=c.cycle_id,
            stage_id=None if c.stage == "unknown" else f"stg-{c.stage.replace('_', '-')}",
            title=title,
            deadline=deadline,
            source_refs=refs,
            requirement_set_ids=[f"rs-{v.case_id}-v{v.version}"] if review else [],
            provenance=_provenance(any(r.provenance.is_simulated for r in refs)),
        )
    requirement_set = None
    if review is not None and opportunity is not None:
        anchors = {a.anchor_key: a for a in v.anchors}
        requirement_set = RequirementSet(
            requirement_set_id=f"rs-{v.case_id}-v{v.version}",
            requirement_version=v.version,
            opportunity_id=opportunity.opportunity_id,
            conditions=[
                RequirementCondition(
                    condition_id=r.requirement_key,
                    kind=CONDITION_KIND[r.spec.kind],
                    description=r.interpretation,
                    evaluation="unknown",
                    missing_inputs=["verified organizational facts (no A EvidenceProvider)"],
                    source_refs=[
                        SourceReference(
                            source_id=anchors[k].source_id,
                            source_version_id=anchors[k].source_version_id,
                            locator=f"{anchors[k].artifact_id} code points "
                            f"{anchors[k].start}-{anchors[k].end}",
                            provenance=_provenance(anchors[k].is_simulated),
                            publication_date=DateKnowledge(status="unknown"),
                            content_hash=anchors[k].artifact_sha256,
                        )
                        for k in r.anchor_keys
                    ],
                )
                for r in v.requirements
            ],
            uncertainty_notes=[
                "Staff-reviewed interpretation of cited text; not funder confirmation.",
                "Scenario evaluations are reported separately and never set these to met.",
            ],
        )
    return FundingCaseEnvelope(
        version=v,
        version_digest=version_digest,
        current_version=current,
        is_current=current == v.version,
        review=review,
        review_status="reviewed" if review else "unreviewed",
        source_status=source_status,
        source_findings=findings,
        readiness=readiness,
        opportunity=opportunity,
        opportunity_missing=missing,
        requirement_set=requirement_set,
        notes=notes,
    )


def _empty_scope() -> Any:
    from strongstart_contracts.funding_review import EvaluationScope

    return EvaluationScope()
