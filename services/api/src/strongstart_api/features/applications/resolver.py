"""Real ``ApprovedAnswerResolver`` for Dev B's prefill (ports.py; C3 spec s4).

Resolves an approval only when it is organization-scoped, an ``approve`` decision, for the
latest answer version, and its dependency snapshot still recomputes to the approved hash
with no applied ChangeSet touching it. Anything else raises ``ApprovalNotUsable`` with a
reason; unknown and other-organization IDs are indistinguishable.
"""

from __future__ import annotations

from collections.abc import Callable

from strongstart_contracts import Provenance, ProvenanceClass
from strongstart_contracts.answers import ApprovalSnapshot
from strongstart_contracts.fixture_adapters import ApprovalNotUsable

from .approval import Context, stale_reason
from .store import StoredDecision, StoredVersion

ContextFactory = Callable[[str], Context]


class StoreApprovedAnswerResolver:
    """Implements the shared ``ApprovedAnswerResolver`` port over C's answer store."""

    def __init__(self, context_for: ContextFactory, is_fixture: bool) -> None:
        self._context_for = context_for
        self.is_fixture = is_fixture

    def _find(self, ctx: Context, approval_id: str) -> tuple[StoredVersion, StoredDecision] | None:
        try:
            questions = ctx.workspace_source.get(ctx.organization_id).question_set.questions
        except Exception:  # an unknown org/workspace behaves like an unknown approval
            return None
        for q in questions:
            for v in ctx.store.versions(ctx.organization_id, q.question_id):
                d = ctx.store.decision_for(ctx.organization_id, v.answer_version_id)
                if d is not None and d.approval_id == approval_id:
                    return v, d
        return None

    def resolve(self, organization_id: str, approval_snapshot_id: str) -> ApprovalSnapshot:
        ctx = self._context_for(organization_id)
        found = self._find(ctx, approval_snapshot_id)
        if found is None:
            raise ApprovalNotUsable(approval_snapshot_id, "no such approval")
        version, decision = found
        if decision.decision != "approve":
            raise ApprovalNotUsable(approval_snapshot_id, "rejected")
        reason = stale_reason(ctx, version)
        if reason is not None:
            raise ApprovalNotUsable(approval_snapshot_id, f"stale: {reason}")
        return ApprovalSnapshot(
            approval_snapshot_id=decision.approval_id,
            answer_snapshot_id=version.answer_version_id,
            content_sha256=version.content_sha256,
            dependencies=list(version.dependencies),
            approval_record_ref=decision.approval_id,
            decided_at=decision.decided_at,
            provenance=Provenance(
                provenance_class=ProvenanceClass.SIMULATED
                if self.is_fixture
                else ProvenanceClass.SUPPLIED,
                is_simulated=self.is_fixture,
                note=(
                    "Approval from the C3 in-memory FIXTURE store by the fixture identity; "
                    "not authentication."
                )
                if self.is_fixture
                else None,
            ),
        )
