"""C-owned consistent approval resolution shared by metadata and prefill consumers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import UTC, datetime

from strongstart_contracts import CapabilityUnavailable, Provenance, ProvenanceClass
from strongstart_contracts.answers import ApprovalSnapshot
from strongstart_contracts.automation_prefill import ApprovedPrefillContent
from strongstart_contracts.fixture_adapters import ApprovalNotUsable

from .approval import Context, stale_reason
from .service import build_check_report
from .snapshot import snapshot_sha256
from .store import ApprovalRead, NotFoundInStore
from .workspace import knowledge_binding_for, load_workspace

ContextFactory = Callable[[str], Context]
TOKEN = re.compile(r"\{\{\s*(?:fact|unsupported)\s*:")


class StoreApprovedAnswerResolver:
    """Consistent process-local reader; no store lock crosses a workspace/SQL call."""

    is_c_reader = True

    def __init__(
        self,
        context_for: ContextFactory,
        is_fixture: bool,
        clock: Callable[[], datetime] | None = None,
        store_current: Callable[[], bool] | None = None,
    ) -> None:
        self._context_for = context_for
        self.is_fixture = is_fixture
        self._clock = clock or (lambda: datetime.now(UTC))
        self._store_current = store_current or (lambda: True)

    def _usable(self, organization_id: str, approval_id: str) -> tuple[Context, ApprovalRead]:
        if not self._store_current():
            raise ApprovalNotUsable(approval_id, "producer_store_replaced")
        try:
            return self._read_usable(organization_id, approval_id)
        except (ApprovalNotUsable, CapabilityUnavailable):
            raise
        except Exception:
            raise CapabilityUnavailable(
                "ApprovedPrefillReader", "dependency verification unavailable"
            ) from None

    def _read_usable(self, organization_id: str, approval_id: str) -> tuple[Context, ApprovalRead]:
        ctx = self._context_for(organization_id)
        try:
            read = ctx.store.capture_approval(organization_id, approval_id)
        except NotFoundInStore:
            raise ApprovalNotUsable(approval_id, "no such approval") from None
        v, d = read.version, read.decision
        reason = None
        if d.decision != "approve":
            reason = "rejected"
        elif (
            v.organization_id != organization_id
            or d.answer_version_id != v.answer_version_id
            or hashlib.sha256(v.text.encode("utf-8")).hexdigest() != v.content_sha256
            or d.content_sha256 != v.content_sha256
            or d.snapshot_sha256 != v.snapshot_sha256
            or snapshot_sha256(v.content_sha256, organization_id, list(v.dependencies))
            != v.snapshot_sha256
            or hashlib.sha256(v.rendered.text.encode("utf-8")).hexdigest() != v.rendered.text_sha256
            or v.check.rendered != v.rendered
        ):
            reason = "approval_integrity_mismatch"
        elif (
            v.rendered.unsupported_markers
            or TOKEN.search(v.rendered.text)
            or any(f.result.outcome == "fail" for f in v.check.findings)
            or (
                any(f.result.outcome == "needs_review" for f in v.check.findings)
                and not d.acknowledged_review_items
            )
        ):
            reason = "approval_gate_blocked"
        else:
            stale = stale_reason(ctx, v)
            reason = f"stale: {stale}" if stale else None
        if reason is not None:
            raise ApprovalNotUsable(approval_id, reason)
        workspace = load_workspace(ctx.workspace_source, organization_id, v.question_set_id)
        question = next(
            (q for q in workspace.question_set.questions if q.question_id == v.question_id), None
        )
        if question is None:
            raise ApprovalNotUsable(approval_id, "dependency_changed")
        report = build_check_report(
            question=question,
            bundle=workspace.evidence_bundle,
            text=v.text,
            mode="reviewed",
            policy=ctx.policy,
        )
        if any(f.result.outcome == "fail" for f in report.findings) or (
            any(f.result.outcome == "needs_review" for f in report.findings)
            and not d.acknowledged_review_items
        ):
            raise ApprovalNotUsable(approval_id, "approval_gate_blocked")
        if v.a4_binding is not None:
            workspace = load_workspace(ctx.workspace_source, organization_id, v.question_set_id)
            live_binding = knowledge_binding_for(
                ctx.workspace_source,
                organization_id,
                workspace.evidence_bundle,
                list(v.dependencies),
            )
            if live_binding != v.a4_binding:
                raise ApprovalNotUsable(approval_id, "managed_binding_changed")
        return ctx, read

    def _snapshot(self, read: ApprovalRead) -> ApprovalSnapshot:
        v, d = read.version, read.decision
        simulated = d.reviewer_is_fixture_identity or (
            v.provenance.is_simulated if v.provenance is not None else self.is_fixture
        )
        return ApprovalSnapshot(
            approval_snapshot_id=d.approval_id,
            answer_snapshot_id=v.answer_version_id,
            content_sha256=v.content_sha256,
            dependencies=list(v.dependencies),
            approval_record_ref=d.approval_id,
            decided_at=d.decided_at,
            provenance=Provenance(
                provenance_class=ProvenanceClass.SIMULATED
                if simulated
                else ProvenanceClass.SUPPLIED,
                is_simulated=simulated,
                note="C process-local FIXTURE approval; not authentication."
                if self.is_fixture
                else None,
            ),
        )

    def _finish(self, ctx: Context, read: ApprovalRead) -> None:
        if not self._store_current() or not ctx.store.approval_read_current(
            ctx.organization_id, read
        ):
            raise ApprovalNotUsable(read.decision.approval_id, "approval_changed_during_read")

    def resolve(self, organization_id: str, approval_snapshot_id: str) -> ApprovalSnapshot:
        ctx, read = self._usable(organization_id, approval_snapshot_id)
        result = self._snapshot(read)
        self._finish(ctx, read)
        return result

    def resolve_for_prefill(
        self, organization_id: str, approval_snapshot_id: str
    ) -> ApprovedPrefillContent:
        ctx, read = self._usable(organization_id, approval_snapshot_id)
        v = read.version
        if v.question_set_id is None:
            raise ApprovalNotUsable(approval_snapshot_id, "published_question_set_required")
        result = ApprovedPrefillContent(
            organization_id=organization_id,
            approval=self._snapshot(read),
            answer_version_id=v.answer_version_id,
            answer_version=v.answer_version,
            question_set_id=v.question_set_id,
            question_id=v.question_id,
            question_version=v.question_version,
            template_text=v.text,
            template_sha256=v.content_sha256,
            rendered_text=v.rendered.text,
            rendered_sha256=v.rendered.text_sha256,
            renderer_version=v.rendered.renderer_version,
            unresolved_marker_count=0,
            dependency_snapshot_sha256=v.snapshot_sha256,
            dependencies=list(v.dependencies),
            a4_binding=v.a4_binding,
            currentness="current",
            currentness_checked_at=self._clock(),
            provenance=self._snapshot(read).provenance,
            is_fixture=self._snapshot(read).provenance.is_simulated,
            producer_id="c-approved-answer-store/1",
            producer_epoch=read.epoch,
        )
        self._finish(ctx, read)
        return result
