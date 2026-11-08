"""FIXTURE-ONLY port implementations. Inject deliberately in tests or local fixture mode.

These are not production adapters. Each sets ``is_fixture = True`` so callers and
the capability report can label results. They never fabricate approvals: the
resolver only returns snapshots present in a fixture bundle and refuses ones a
recorded change set has made stale.
"""

from __future__ import annotations

from .answers import ApprovalSnapshot
from .common import SourceReference
from .fixtures import FixtureBundle
from .ports import CapabilityUnavailable, StoredCapture


class ApprovalNotUsable(Exception):
    def __init__(self, approval_snapshot_id: str, reason: str) -> None:
        super().__init__(f"{approval_snapshot_id}: {reason}")
        self.approval_snapshot_id = approval_snapshot_id
        self.reason = reason


class FixtureCaptureStore:
    """In-memory capture store labelled fixture. Bytes are copied, never mutated in place."""

    is_fixture = True

    def __init__(self) -> None:
        self._items: dict[str, StoredCapture] = {}

    def put(self, reference: SourceReference, content: bytes, media_type: str) -> SourceReference:
        if reference.source_version_id in self._items:
            raise ValueError("source versions are immutable; use a new source_version_id")
        self._items[reference.source_version_id] = StoredCapture(
            reference, bytes(content), media_type
        )
        return reference

    def get(self, source_version_id: str) -> StoredCapture:
        try:
            return self._items[source_version_id]
        except KeyError:
            raise CapabilityUnavailable("FixtureCaptureStore", "unknown source version") from None


class FixtureApprovedAnswerResolver:
    """Resolves approvals from a fixture bundle; applied change sets stale dependents."""

    is_fixture = True

    def __init__(self, bundle: FixtureBundle, applied_change_set_ids: frozenset[str] = frozenset()):
        self._bundle = bundle
        self._approvals = {a.approval_snapshot_id: a for a in bundle.approval_snapshots}
        self._org_ids = {o.organization_id for o in bundle.organizations}
        self._changed: set[tuple[str, str]] = set()
        for cs in bundle.change_sets:
            if cs.change_set_id in applied_change_set_ids:
                for ch in cs.changes:
                    self._changed.add((ch.ref_id, ch.previous_version or ""))

    def resolve(self, organization_id: str, approval_snapshot_id: str) -> ApprovalSnapshot:
        if organization_id not in self._org_ids:
            raise ApprovalNotUsable(approval_snapshot_id, "organization not in fixture scope")
        approval = self._approvals.get(approval_snapshot_id)
        if approval is None:
            raise ApprovalNotUsable(approval_snapshot_id, "no such approval")
        for dep in approval.dependencies:
            if (dep.ref_id, dep.version) in self._changed:
                raise ApprovalNotUsable(approval_snapshot_id, f"stale: {dep.ref_id} changed")
        return approval
