"""C3 approval engine: frozen versions, live staleness and the s9.2 approve gate.

State and staleness are computed by this code on every read and action; no request or
model output can set them (SEC-14). An approval is usable only while it is for the latest
version AND a fresh recomputation of the dependency snapshot equals the approved one AND no
applied ChangeSet touches its dependencies (APP-04, APP-06, JOB-02, JOB-05).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from strongstart_contracts import (
    ChangeSet,
    EvidenceBundle,
    Provenance,
    ProvenanceClass,
    Question,
    SessionIdentity,
)
from strongstart_contracts.answers import (
    AnswerFinding,
    AnswerHistory,
    AnswerState,
    AnswerStoreMetadata,
    AnswerVersion,
    AnswerVersionCreate,
    ApplicationWorkspace,
    ApprovalDecisionRequest,
    ApprovalRecord,
    ReviewNote,
    ReviewNoteCreate,
)

from ...config import Settings
from . import audit
from .rules.policy import WritingPolicy
from .service import (
    EvidenceBundleNotFound,
    QuestionNotFound,
    QuestionVersionConflict,
    build_check_report,
)
from .snapshot import dependency_refs, snapshot_sha256
from .store import AnswerStore, NotFoundInStore, StoredDecision, StoredVersion
from .workspace import (
    QuestionSetIntegrityError,
    WorkspaceNotFound,
    WorkspaceSource,
    current_question_set_id,
    knowledge_binding_for,
    load_workspace,
)

CHANGE_KIND_TO_DEP = {
    "fact": "fact",
    "pack": "pack",
    "policy": "policy",
    "question": "question",
    "requirement_set": "requirement_set",
    "source": "source_version",
}


class ApprovalForbidden(Exception):
    pass


class GateBlocked(Exception):
    def __init__(self, reason: str, findings: list[AnswerFinding] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.findings = findings or []


class SnapshotConflict(Exception):
    """Expected hash/snapshot no longer matches (JOB-02 / JOB-05)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Context:
    store: AnswerStore
    workspace_source: WorkspaceSource
    policy: WritingPolicy | None
    settings: Settings
    organization_id: str


def can_approve(identity: SessionIdentity, settings: Settings) -> bool:
    """Only the local fixture identity in fixture mode may approve (owner decision #3,
    labelled everywhere). Real reviewer roles arrive with A's SEC-01 identity primitive."""
    return identity.is_fixture and settings.fixture_mode


def _workspace(ctx: Context, question_set_id: str | None) -> ApplicationWorkspace:
    return load_workspace(ctx.workspace_source, ctx.organization_id, question_set_id)


def _question(ws: ApplicationWorkspace, question_id: str) -> Question:
    q = next((q for q in ws.question_set.questions if q.question_id == question_id), None)
    if q is None:
        raise QuestionNotFound()
    return q


def _bundle(ws: ApplicationWorkspace, bundle_id: str) -> EvidenceBundle:
    if ws.evidence_bundle.bundle_id != bundle_id:
        raise EvidenceBundleNotFound()
    return ws.evidence_bundle


def current_snapshot(ctx: Context, version: StoredVersion) -> str | None:
    """Recompute the snapshot from current dependencies; None if they no longer exist."""
    try:
        ws = _workspace(ctx, version.question_set_id)
        question = _question(ws, version.question_id)
        bundle = _bundle(ws, version.evidence_bundle_id)
    except (
        QuestionNotFound,
        EvidenceBundleNotFound,
        WorkspaceNotFound,
        QuestionSetIntegrityError,
    ):
        return None  # an unreadable dependency can never leave an approval usable
    if question.question_version != version.question_version:
        return None
    report = build_check_report(
        question=question, bundle=bundle, text=version.text, mode="reviewed", policy=ctx.policy
    )
    if report.rendered != version.rendered:
        return None
    refs = dependency_refs(question, bundle, report.rendered, ctx.policy)
    return snapshot_sha256(version.content_sha256, ctx.organization_id, refs)


def stale_reason(ctx: Context, version: StoredVersion) -> str | None:
    history = ctx.store.versions(ctx.organization_id, version.question_id)
    if history and history[-1].answer_version_id != version.answer_version_id:
        return "newer_version_saved"
    for change_set in ctx.store.applied_change_sets(ctx.organization_id):
        for change in change_set.changes:
            kind = CHANGE_KIND_TO_DEP.get(change.kind)
            if any(d.kind == kind and d.ref_id == change.ref_id for d in version.dependencies):
                return f"change_set_applied:{change_set.change_set_id}"
    try:
        current_set = current_question_set_id(
            ctx.workspace_source, ctx.organization_id, version.question_set_id
        )
    except (WorkspaceNotFound, QuestionSetIntegrityError):
        return "dependency_changed"
    if current_set != version.question_set_id:
        return "question_definition_revised"  # Dev B saved a newer definition version
    if current_snapshot(ctx, version) != version.snapshot_sha256:
        return "dependency_changed"
    return None


def _state(ctx: Context, version: StoredVersion) -> tuple[AnswerState, str | None]:
    decision = ctx.store.decision_for(ctx.organization_id, version.answer_version_id)
    reason = stale_reason(ctx, version)
    if decision is not None and decision.decision == "approve":
        return ("stale", reason) if reason else ("approved", None)
    if decision is not None:
        return "rejected", None
    if reason == "newer_version_saved":
        return "draft", None
    if any(f.result.outcome == "fail" for f in version.check.findings):
        return "needs_attention", reason
    return "ready_for_review", reason


def to_contract(ctx: Context, version: StoredVersion, latest_id: str) -> AnswerVersion:
    state, _ = _state(ctx, version)
    return AnswerVersion(
        answer_version_id=version.answer_version_id,
        answer_id=version.answer_id,
        question_id=version.question_id,
        question_version=version.question_version,
        question_set_id=version.question_set_id,
        answer_version=version.answer_version,
        is_latest=version.answer_version_id == latest_id,
        text=version.text,
        content_sha256=version.content_sha256,
        rendered=version.rendered,
        dependencies=list(version.dependencies),
        snapshot_sha256=version.snapshot_sha256,
        check=version.check,
        checked_at=version.checked_at,
        state=state,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def _record(ctx: Context, decision: StoredDecision, version: StoredVersion) -> ApprovalRecord:
    reason = stale_reason(ctx, version) if decision.decision == "approve" else None
    return ApprovalRecord(
        approval_id=decision.approval_id,
        answer_version_id=decision.answer_version_id,
        answer_id=version.answer_id,
        question_id=version.question_id,
        decision=decision.decision,
        content_sha256=decision.content_sha256,
        snapshot_sha256=decision.snapshot_sha256,
        reviewer_id=decision.reviewer_id,
        reviewer_is_fixture_identity=decision.reviewer_is_fixture_identity,
        note=decision.note,
        decided_at=decision.decided_at,
        is_stale=reason is not None,
        stale_reason=reason,
    )


def save_version(
    ctx: Context, identity: SessionIdentity, body: AnswerVersionCreate
) -> AnswerVersion:
    expected_state = ctx.store.state(ctx.organization_id)
    ws = _workspace(ctx, body.question_set_id)
    question = _question(ws, body.question_id)
    if question.question_version != body.question_version:
        raise QuestionVersionConflict(question.question_version)
    bundle = _bundle(ws, body.evidence_bundle_id)
    report = build_check_report(
        question=question, bundle=bundle, text=body.text, mode="reviewed", policy=ctx.policy
    )
    content = hashlib.sha256(body.text.encode("utf-8")).hexdigest()
    refs = dependency_refs(question, bundle, report.rendered, ctx.policy)
    snap = snapshot_sha256(content, ctx.organization_id, refs)
    managed_binding = knowledge_binding_for(ctx.workspace_source, ctx.organization_id, bundle, refs)
    now = datetime.now(UTC)

    def build(n: int) -> StoredVersion:
        return StoredVersion(
            answer_version_id="av-" + uuid.uuid4().hex[:24],
            answer_id=f"ans-{question.question_id}",
            organization_id=ctx.organization_id,
            question_id=question.question_id,
            question_version=question.question_version,
            answer_version=n,
            question_set_id=body.question_set_id,
            evidence_bundle_id=bundle.bundle_id,
            text=body.text,
            content_sha256=content,
            rendered=report.rendered,
            dependencies=tuple(refs),
            snapshot_sha256=snap,
            check=report,
            checked_at=now,
            created_by=identity.actor_id,
            created_at=now,
            a4_binding=managed_binding,
            provenance=Provenance(
                provenance_class=ProvenanceClass.SIMULATED
                if ws.is_fixture or any(f.provenance.is_simulated for f in bundle.facts)
                else ProvenanceClass.SUPPLIED,
                is_simulated=ws.is_fixture or any(f.provenance.is_simulated for f in bundle.facts),
            ),
        )

    with ctx.store.unit_of_work(ctx.organization_id, expected_state):
        previous = ctx.store.versions(ctx.organization_id, question.question_id)
        version = ctx.store.append_version(
            ctx.organization_id, question.question_id, body.expected_answer_version, build
        )
        audit.record(
            ctx.store,
            ctx.settings,
            organization_id=ctx.organization_id,
            actor_id=identity.actor_id,
            action="answer_version_saved",
            object_type="answer_version",
            object_id=version.answer_version_id,
            object_version=str(version.answer_version),
            decision="saved",
            details={"content_sha256": content, "snapshot_sha256": snap},
        )
        if previous:
            prior = previous[-1]
            prior_decision = ctx.store.decision_for(ctx.organization_id, prior.answer_version_id)
            if prior_decision is not None and prior_decision.decision == "approve":
                audit.record(
                    ctx.store,
                    ctx.settings,
                    organization_id=ctx.organization_id,
                    actor_id=identity.actor_id,
                    action="approval_staled",
                    object_type="approval",
                    object_id=prior_decision.approval_id,
                    object_version=str(prior.answer_version),
                    decision="stale",
                    details={"reason": "newer_version_saved"},
                )
    return to_contract(ctx, version, version.answer_version_id)


def history(ctx: Context, question_id: str, question_set_id: str | None = None) -> AnswerHistory:
    _question(_workspace(ctx, question_set_id), question_id)
    versions = ctx.store.versions(ctx.organization_id, question_id)
    latest_id = versions[-1].answer_version_id if versions else ""
    contracts = [to_contract(ctx, v, latest_id) for v in versions]
    ids = {v.answer_version_id for v in versions}
    approvals = []
    for v in versions:
        d = ctx.store.decision_for(ctx.organization_id, v.answer_version_id)
        if d is not None:
            approvals.append(_record(ctx, d, v))
    return AnswerHistory(
        question_id=question_id,
        answer_id=versions[0].answer_id if versions else None,
        versions=contracts,
        approvals=approvals,
        notes=[n for n in ctx.store.notes(ctx.organization_id) if n.answer_version_id in ids],
        proposals=[
            p for p in ctx.store.proposals(ctx.organization_id) if p.answer_version_id in ids
        ],
        prefill_ready=bool(contracts) and contracts[-1].state == "approved",
        store_is_fixture=ctx.store.is_fixture,
        store=AnswerStoreMetadata(backend=ctx.store.backend, durable=ctx.store.durable),
    )


def decide(
    ctx: Context, identity: SessionIdentity, body: ApprovalDecisionRequest
) -> ApprovalRecord:
    if not can_approve(identity, ctx.settings):
        raise ApprovalForbidden()
    expected_state = ctx.store.state(ctx.organization_id)
    version = ctx.store.get_version(ctx.organization_id, body.answer_version_id)
    if body.expected_content_sha256 != version.content_sha256:
        raise SnapshotConflict("content_changed")
    if body.expected_snapshot_sha256 != version.snapshot_sha256:
        raise SnapshotConflict("snapshot_changed")
    reason = stale_reason(ctx, version)
    if reason is not None:
        raise SnapshotConflict(reason)
    if body.decision == "approve":
        ws = _workspace(ctx, version.question_set_id)
        fresh = build_check_report(
            question=_question(ws, version.question_id),
            bundle=_bundle(ws, version.evidence_bundle_id),
            text=version.text,
            mode="reviewed",
            policy=ctx.policy,
        )
        failing = [f for f in fresh.findings if f.result.outcome == "fail"]
        if failing:
            raise GateBlocked("blocking_findings", failing)
        open_items = [f for f in fresh.findings if f.result.outcome == "needs_review"]
        if open_items and not body.acknowledge_review_items:
            raise GateBlocked("review_items_not_acknowledged", open_items)
    with ctx.store.unit_of_work(ctx.organization_id, expected_state):
        decision = ctx.store.record_decision(
            ctx.organization_id,
            StoredDecision(
                approval_id="apr-" + uuid.uuid4().hex[:24],
                answer_version_id=version.answer_version_id,
                decision=body.decision,
                content_sha256=version.content_sha256,
                snapshot_sha256=version.snapshot_sha256,
                reviewer_id=identity.actor_id,
                reviewer_is_fixture_identity=identity.is_fixture,
                acknowledged_review_items=body.acknowledge_review_items,
                note=body.note,
                decided_at=datetime.now(UTC),
            ),
            must_be_latest=True,
        )
        audit.record(
            ctx.store,
            ctx.settings,
            organization_id=ctx.organization_id,
            actor_id=identity.actor_id,
            action="approval_decided",
            object_type="answer_version",
            object_id=version.answer_version_id,
            object_version=str(version.answer_version),
            decision=body.decision,
            details={
                "content_sha256": version.content_sha256,
                "note_present": str(bool(body.note)),
            },
        )
    return _record(ctx, decision, version)


def add_note(ctx: Context, identity: SessionIdentity, body: ReviewNoteCreate) -> ReviewNote:
    """Secondary reviewers may comment; notes never change state or grant approval."""
    expected_state = ctx.store.state(ctx.organization_id)
    version = ctx.store.get_version(ctx.organization_id, body.answer_version_id)
    note = ReviewNote(
        note_id="note-" + uuid.uuid4().hex[:24],
        answer_version_id=version.answer_version_id,
        author_id=identity.actor_id,
        text=body.text,
        created_at=datetime.now(UTC),
    )
    with ctx.store.unit_of_work(ctx.organization_id, expected_state):
        ctx.store.add_note(ctx.organization_id, note)
        audit.record(
            ctx.store,
            ctx.settings,
            organization_id=ctx.organization_id,
            actor_id=identity.actor_id,
            action="review_note_added",
            object_type="answer_version",
            object_id=version.answer_version_id,
            object_version=str(version.answer_version),
            decision="note",
            details={"note_id": note.note_id},
        )
    return note


__all__ = [
    "ApprovalForbidden",
    "Context",
    "GateBlocked",
    "NotFoundInStore",
    "SnapshotConflict",
    "add_note",
    "can_approve",
    "decide",
    "history",
    "save_version",
    "stale_reason",
]


def apply_changes(ctx: Context, identity: SessionIdentity, change_set: ChangeSet) -> list[str]:
    expected = ctx.store.state(ctx.organization_id)
    previous = ctx.store.applied_change_sets(ctx.organization_id)
    found = next((c for c in previous if c.change_set_id == change_set.change_set_id), None)
    if found is not None:
        if found != change_set:
            from .store import StaleExpectation

            raise StaleExpectation("change_set_payload_conflict")
        return [c.change_set_id for c in previous]
    affected = []
    for version in ctx.store.all_versions(ctx.organization_id):
        d = ctx.store.decision_for(ctx.organization_id, version.answer_version_id)
        if (
            d is not None
            and d.decision == "approve"
            and any(
                ref.kind == CHANGE_KIND_TO_DEP.get(change.kind) and ref.ref_id == change.ref_id
                for ref in version.dependencies
                for change in change_set.changes
            )
        ):
            affected.append((version, d))
    with ctx.store.unit_of_work(ctx.organization_id, expected):
        applied = ctx.store.apply_change_set(ctx.organization_id, change_set)
        audit.record(
            ctx.store,
            ctx.settings,
            organization_id=ctx.organization_id,
            actor_id=identity.actor_id,
            action="change_set_applied",
            object_type="change_set",
            object_id=change_set.change_set_id,
            object_version="1",
            decision="applied",
        )
        for version, d in affected:
            audit.record(
                ctx.store,
                ctx.settings,
                organization_id=ctx.organization_id,
                actor_id=identity.actor_id,
                action="approval_staled",
                object_type="approval",
                object_id=d.approval_id,
                object_version=str(version.answer_version),
                decision="stale",
                details={"reason": "change_set_applied:" + change_set.change_set_id},
            )
    return applied
