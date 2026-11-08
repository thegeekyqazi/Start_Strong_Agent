"""Versioned shared fixture bundle schema and cross-reference validation.

Fixture bundles are synthetic. Every record keeps its provenance label; the bundle
itself must be marked simulated. Loading a bundle validates types (strict DTOs) and
cross-references (IDs, versions and content hashes) and raises on any dangling link.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .answers import AnswerSnapshot, ApprovalSnapshot
from .automation import ApplicationDefinition, FormMap, QuestionSet
from .common import ContractModel, Provenance, StableId, contract_model_config
from .evidence import EvidenceBundle
from .funding import Opportunity, RequirementSet
from .jobs import ChangeSet, JobResult


class FixtureOrganization(ContractModel):
    model_config = contract_model_config("draft", "A")

    organization_id: StableId
    display_name: str
    provenance: Provenance


class FixturePack(ContractModel):
    model_config = contract_model_config("draft", "A")

    pack_id: StableId
    pack_version_id: StableId
    organization_id: StableId
    provenance: Provenance


class FixtureExpectations(ContractModel):
    """Expected outcomes later feature tests assert against (not results of any engine)."""

    model_config = contract_model_config("draft", "shared")

    stale_after_change_set: dict[StableId, list[StableId]] = Field(
        default_factory=dict,
        description="change_set_id -> approval_snapshot_ids that must become stale.",
    )
    unknown_condition_ids: list[StableId] = Field(default_factory=list)
    conflicting_question_ids: list[StableId] = Field(default_factory=list)
    typed_failure_job_ids: list[StableId] = Field(default_factory=list)


class FixtureBundle(ContractModel):
    model_config = contract_model_config("draft", "shared")

    fixture_schema_version: Literal["1"] = "1"
    fixture_bundle_id: StableId
    fixture_version: int = Field(ge=1)
    provenance: Provenance
    organizations: list[FixtureOrganization]
    packs: list[FixturePack]
    evidence_bundles: list[EvidenceBundle]
    opportunities: list[Opportunity]
    requirement_sets: list[RequirementSet]
    question_sets: list[QuestionSet]
    application_definitions: list[ApplicationDefinition]
    form_maps: list[FormMap]
    answer_snapshots: list[AnswerSnapshot]
    approval_snapshots: list[ApprovalSnapshot]
    change_sets: list[ChangeSet]
    job_results: list[JobResult]
    expectations: FixtureExpectations

    @model_validator(mode="after")
    def _validate_links(self) -> FixtureBundle:
        errors = cross_reference_errors(self)
        if errors:
            raise ValueError("fixture cross-reference errors: " + "; ".join(errors))
        return self


def _dupes(kind: str, ids: list[str], errors: list[str]) -> set[str]:
    seen: set[str] = set()
    for item in ids:
        if item in seen:
            errors.append(f"duplicate {kind} id {item!r}")
        seen.add(item)
    return seen


def cross_reference_errors(b: FixtureBundle) -> list[str]:
    errors: list[str] = []
    if not b.provenance.is_simulated:
        errors.append("fixture bundle must be labelled simulated")

    orgs = _dupes("organization", [o.organization_id for o in b.organizations], errors)
    pack_versions = _dupes("pack_version", [p.pack_version_id for p in b.packs], errors)
    opps = _dupes("opportunity", [o.opportunity_id for o in b.opportunities], errors)
    req_sets = _dupes("requirement_set", [r.requirement_set_id for r in b.requirement_sets], errors)
    qsets = _dupes("question_set", [q.question_set_id for q in b.question_sets], errors)
    forms = _dupes("form", [f.form_id for f in b.form_maps], errors)
    answers = _dupes("answer_snapshot", [a.answer_snapshot_id for a in b.answer_snapshots], errors)
    approvals = _dupes(
        "approval_snapshot", [a.approval_snapshot_id for a in b.approval_snapshots], errors
    )
    change_sets = _dupes("change_set", [c.change_set_id for c in b.change_sets], errors)
    jobs = _dupes("job", [j.job_id for j in b.job_results], errors)

    questions = {q.question_id: q for qs in b.question_sets for q in qs.questions}
    facts = {f.fact_id: f for eb in b.evidence_bundles for f in eb.facts}
    conditions = {c.condition_id: c for rs in b.requirement_sets for c in rs.conditions}

    for p in b.packs:
        if p.organization_id not in orgs:
            errors.append(
                f"pack {p.pack_version_id!r} references unknown org {p.organization_id!r}"
            )
    for eb in b.evidence_bundles:
        if eb.organization_id not in orgs:
            errors.append(f"evidence bundle {eb.bundle_id!r}: unknown org")
        if eb.pack_version_id not in pack_versions:
            errors.append(f"evidence bundle {eb.bundle_id!r}: unknown pack version")
        local = {f.fact_id for f in eb.facts}
        for fid in eb.allowed_fact_ids:
            if fid not in local:
                errors.append(f"evidence bundle {eb.bundle_id!r}: allowed fact {fid!r} missing")
        for f in eb.facts:
            if eb.organization_id in orgs and not f.provenance.is_simulated:
                errors.append(f"fact {f.fact_id!r} in a fixture must be labelled simulated")
    for o in b.opportunities:
        for rid in o.requirement_set_ids:
            if rid not in req_sets:
                errors.append(f"opportunity {o.opportunity_id!r}: unknown requirement set {rid!r}")
    for r in b.requirement_sets:
        if r.opportunity_id not in opps:
            errors.append(f"requirement set {r.requirement_set_id!r}: unknown opportunity")
    for qs in b.question_sets:
        if qs.opportunity_id not in opps:
            errors.append(f"question set {qs.question_set_id!r}: unknown opportunity")
    for ad in b.application_definitions:
        if ad.opportunity_id not in opps:
            errors.append(f"application definition {ad.application_definition_id!r}: unknown opp")
        if ad.question_set_id not in qsets:
            errors.append(f"application definition {ad.application_definition_id!r}: unknown qset")
        if ad.form_id is not None and ad.form_id not in forms:
            errors.append(f"application definition {ad.application_definition_id!r}: unknown form")
    for fm in b.form_maps:
        for fld in fm.fields:
            if fld.question_id not in questions:
                errors.append(f"form {fm.form_id!r} field {fld.field_id!r}: unknown question")
    snapshots = {a.answer_snapshot_id: a for a in b.answer_snapshots}
    for a in b.answer_snapshots:
        q = questions.get(a.question_id)
        if q is None:
            errors.append(f"answer snapshot {a.answer_snapshot_id!r}: unknown question")
        elif q.question_version != a.question_version:
            errors.append(f"answer snapshot {a.answer_snapshot_id!r}: question version mismatch")
        if hashlib.sha256(a.content.encode("utf-8")).hexdigest() != a.content_sha256:
            errors.append(f"answer snapshot {a.answer_snapshot_id!r}: content hash mismatch")
        for dep in a.dependencies:
            if dep.kind == "fact" and dep.ref_id not in facts:
                errors.append(
                    f"answer snapshot {a.answer_snapshot_id!r}: unknown fact {dep.ref_id!r}"
                )
    for ap in b.approval_snapshots:
        snap = snapshots.get(ap.answer_snapshot_id)
        if snap is None:
            errors.append(f"approval {ap.approval_snapshot_id!r}: unknown answer snapshot")
        elif snap.content_sha256 != ap.content_sha256:
            errors.append(f"approval {ap.approval_snapshot_id!r}: content hash differs from answer")
    known_ids = (
        orgs
        | pack_versions
        | opps
        | req_sets
        | qsets
        | forms
        | answers
        | approvals
        | set(questions)
        | set(facts)
        | set(conditions)
    )
    for cs in b.change_sets:
        for ref in cs.affected_refs:
            if ref not in known_ids:
                errors.append(f"change set {cs.change_set_id!r}: unknown affected ref {ref!r}")
    exp = b.expectations
    for cs_id, ap_ids in exp.stale_after_change_set.items():
        if cs_id not in change_sets:
            errors.append(f"expectation: unknown change set {cs_id!r}")
        for ap_id in ap_ids:
            if ap_id not in approvals:
                errors.append(f"expectation: unknown approval {ap_id!r}")
    for cid in exp.unknown_condition_ids:
        cond = conditions.get(cid)
        if cond is None or cond.evaluation != "unknown":
            errors.append(f"expectation: condition {cid!r} missing or not 'unknown'")
    for qid in exp.conflicting_question_ids:
        if qid not in questions or not questions[qid].conflicts:
            errors.append(f"expectation: question {qid!r} missing or has no conflict")
    for jid in exp.typed_failure_job_ids:
        job = next((j for j in b.job_results if j.job_id == jid), None)
        if jid not in jobs or job is None or job.state != "failed" or job.error is None:
            errors.append(f"expectation: job {jid!r} missing or not a typed failure")
    return errors


def load_fixture_bundle(path: Path) -> FixtureBundle:
    return FixtureBundle.model_validate(json.loads(path.read_text(encoding="utf-8")))
