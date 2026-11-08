"""C3 answer/approval store (C3 spec s3).

Only a labelled in-memory FIXTURE store exists until Dev A sequences migration
the C3 answers/approvals migration (unnumbered draft in
``docs/handoffs/dev-c/c3-migration-request/answers_and_approvals.py``; number assigned by Dev A).
Writes that must not race (version append, one decision per version) run under one lock,
the in-memory analogue of the guarded transactional writes in s15. All reads are
organization-scoped: unknown and other-org IDs raise the same ``NotFoundInStore``.
"""

from __future__ import annotations

import copy
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

from strongstart_contracts import CapabilityUnavailable, ChangeSet
from strongstart_contracts.answers import (
    AuditEvent,
    CheckReport,
    DependencyRef,
    ExportResult,
    RenderedAnswer,
    ReviewerProposal,
    ReviewNote,
)
from strongstart_contracts.knowledge_binding import ApprovedKnowledgeBinding


class NotFoundInStore(Exception):
    pass


class StaleExpectation(Exception):
    """Optimistic-version mismatch (JOB-02)."""

    def __init__(self, reason: str, current: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.current = current


@dataclass(frozen=True)
class StoredVersion:
    answer_version_id: str
    answer_id: str
    organization_id: str
    question_id: str
    question_version: int
    answer_version: int
    question_set_id: str | None
    evidence_bundle_id: str
    text: str
    content_sha256: str
    rendered: RenderedAnswer
    dependencies: tuple[DependencyRef, ...]
    snapshot_sha256: str
    check: CheckReport
    checked_at: datetime
    created_by: str
    created_at: datetime
    a4_binding: ApprovedKnowledgeBinding | None = None


@dataclass(frozen=True)
class StoredDecision:
    approval_id: str
    answer_version_id: str
    decision: Literal["approve", "reject"]
    content_sha256: str
    snapshot_sha256: str
    reviewer_id: str
    reviewer_is_fixture_identity: bool
    acknowledged_review_items: bool
    note: str
    decided_at: datetime


@dataclass(frozen=True)
class StoredExport:
    organization_id: str
    result: ExportResult
    docx: bytes
    audit: bytes


@dataclass
class _OrgData:
    versions: dict[str, list[StoredVersion]] = field(default_factory=dict)  # by question
    decisions: dict[str, StoredDecision] = field(default_factory=dict)  # by answer version
    notes: list[ReviewNote] = field(default_factory=list)
    proposals: list[ReviewerProposal] = field(default_factory=list)
    exports: dict[str, StoredExport] = field(default_factory=dict)
    change_sets: list[ChangeSet] = field(default_factory=list)
    audit: list[AuditEvent] = field(default_factory=list)


@dataclass(frozen=True)
class ApprovalRead:
    version: StoredVersion
    decision: StoredDecision
    revision: int
    epoch: str


class AnswerStore(Protocol):
    is_fixture: bool

    def capture_approval(self, organization_id: str, approval_id: str) -> ApprovalRead: ...

    def approval_read_current(self, organization_id: str, captured: ApprovalRead) -> bool: ...

    def append_version(
        self,
        organization_id: str,
        question_id: str,
        expected_latest: int | None,
        build: Callable[[int], StoredVersion],
    ) -> StoredVersion: ...

    def versions(self, organization_id: str, question_id: str) -> list[StoredVersion]: ...

    def all_versions(self, organization_id: str) -> list[StoredVersion]: ...

    def get_version(self, organization_id: str, answer_version_id: str) -> StoredVersion: ...

    def record_decision(
        self, organization_id: str, decision: StoredDecision, must_be_latest: bool
    ) -> StoredDecision: ...

    def decision_for(
        self, organization_id: str, answer_version_id: str
    ) -> StoredDecision | None: ...

    def add_note(self, organization_id: str, note: ReviewNote) -> ReviewNote: ...

    def notes(self, organization_id: str) -> list[ReviewNote]: ...

    def add_proposal(
        self, organization_id: str, proposal: ReviewerProposal
    ) -> ReviewerProposal: ...

    def proposals(self, organization_id: str) -> list[ReviewerProposal]: ...

    def add_export(self, organization_id: str, export: StoredExport) -> None: ...

    def get_export(self, organization_id: str, export_id: str) -> StoredExport: ...

    def apply_change_set(self, organization_id: str, change_set: ChangeSet) -> list[str]: ...

    def applied_change_sets(self, organization_id: str) -> list[ChangeSet]: ...

    def add_audit(self, organization_id: str, event: AuditEvent) -> None: ...

    def audit(self, organization_id: str) -> list[AuditEvent]: ...


class InMemoryAnswerStore:
    """FIXTURE store: process-local, lost on restart, labelled everywhere it surfaces."""

    is_fixture = True

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._orgs: dict[str, _OrgData] = {}
        self.epoch = "c-store-" + secrets.token_hex(16)
        self._revisions: dict[str, int] = {}

    def _changed(self, organization_id: str) -> None:
        self._revisions[organization_id] = self._revisions.get(organization_id, 0) + 1

    def capture_approval(self, organization_id: str, approval_id: str) -> ApprovalRead:
        with self._lock:
            org = self._org(organization_id)
            for history in org.versions.values():
                for version in history:
                    decision = org.decisions.get(version.answer_version_id)
                    if decision is not None and decision.approval_id == approval_id:
                        return copy.deepcopy(
                            ApprovalRead(
                                version,
                                decision,
                                self._revisions.get(organization_id, 0),
                                self.epoch,
                            )
                        )
        raise NotFoundInStore()

    def approval_read_current(self, organization_id: str, captured: ApprovalRead) -> bool:
        with self._lock:
            return captured.epoch == self.epoch and captured.revision == self._revisions.get(
                organization_id, 0
            )

    def _org(self, organization_id: str) -> _OrgData:
        return self._orgs.setdefault(organization_id, _OrgData())

    def append_version(
        self,
        organization_id: str,
        question_id: str,
        expected_latest: int | None,
        build: Callable[[int], StoredVersion],
    ) -> StoredVersion:
        with self._lock:
            history = self._org(organization_id).versions.setdefault(question_id, [])
            current = history[-1].answer_version if history else None
            if expected_latest != current:
                raise StaleExpectation("answer_version_conflict", current)
            version = build((current or 0) + 1)
            history.append(copy.deepcopy(version))
            self._changed(organization_id)
            return version

    def versions(self, organization_id: str, question_id: str) -> list[StoredVersion]:
        with self._lock:
            return list(self._org(organization_id).versions.get(question_id, []))

    def all_versions(self, organization_id: str) -> list[StoredVersion]:
        with self._lock:
            return [v for h in self._org(organization_id).versions.values() for v in h]

    def get_version(self, organization_id: str, answer_version_id: str) -> StoredVersion:
        with self._lock:
            for history in self._org(organization_id).versions.values():
                for v in history:
                    if v.answer_version_id == answer_version_id:
                        return v
        raise NotFoundInStore()

    def record_decision(
        self, organization_id: str, decision: StoredDecision, must_be_latest: bool
    ) -> StoredDecision:
        with self._lock:
            org = self._org(organization_id)
            if decision.answer_version_id in org.decisions:
                raise StaleExpectation("already_decided")
            target = None
            for history in org.versions.values():
                for v in history:
                    if v.answer_version_id == decision.answer_version_id:
                        target = (v, history)
            if target is None:
                raise NotFoundInStore()
            version, history = target
            if must_be_latest and history[-1].answer_version_id != version.answer_version_id:
                raise StaleExpectation("not_latest_version")
            org.decisions[decision.answer_version_id] = decision
            self._changed(organization_id)
            return decision

    def decision_for(self, organization_id: str, answer_version_id: str) -> StoredDecision | None:
        with self._lock:
            return self._org(organization_id).decisions.get(answer_version_id)

    def add_note(self, organization_id: str, note: ReviewNote) -> ReviewNote:
        with self._lock:
            self._org(organization_id).notes.append(note)
            return note

    def notes(self, organization_id: str) -> list[ReviewNote]:
        with self._lock:
            return list(self._org(organization_id).notes)

    def add_proposal(self, organization_id: str, proposal: ReviewerProposal) -> ReviewerProposal:
        with self._lock:
            self._org(organization_id).proposals.append(proposal)
            return proposal

    def proposals(self, organization_id: str) -> list[ReviewerProposal]:
        with self._lock:
            return list(self._org(organization_id).proposals)

    def add_export(self, organization_id: str, export: StoredExport) -> None:
        with self._lock:
            export_id = export.result.export_id
            assert export_id is not None
            self._org(organization_id).exports[export_id] = export

    def get_export(self, organization_id: str, export_id: str) -> StoredExport:
        with self._lock:
            found = self._org(organization_id).exports.get(export_id)
        if found is None:
            raise NotFoundInStore()
        return found

    def apply_change_set(self, organization_id: str, change_set: ChangeSet) -> list[str]:
        with self._lock:
            org = self._org(organization_id)
            if all(c.change_set_id != change_set.change_set_id for c in org.change_sets):
                org.change_sets.append(change_set.model_copy(deep=True))
                self._changed(organization_id)
            return [c.change_set_id for c in org.change_sets]

    def applied_change_sets(self, organization_id: str) -> list[ChangeSet]:
        with self._lock:
            return list(self._org(organization_id).change_sets)

    def add_audit(self, organization_id: str, event: AuditEvent) -> None:
        with self._lock:
            self._org(organization_id).audit.append(event)

    def audit(self, organization_id: str) -> list[AuditEvent]:
        with self._lock:
            return list(self._org(organization_id).audit)


class UnconfiguredAnswerStore:
    """No persistence configured (outside fixture mode, until the C3 answers/approvals
    migration exists). Every operation fails closed with ``CapabilityUnavailable``."""

    is_fixture = False

    def capture_approval(self, organization_id: str, approval_id: str) -> ApprovalRead:
        raise self._unavailable()

    def approval_read_current(self, organization_id: str, captured: ApprovalRead) -> bool:
        raise self._unavailable()

    @staticmethod
    def _unavailable() -> CapabilityUnavailable:
        return CapabilityUnavailable(
            "AnswerStore",
            "TigerData durable answer store is not configured; process-local fixture mode only",
        )

    def append_version(
        self,
        organization_id: str,
        question_id: str,
        expected_latest: int | None,
        build: Callable[[int], StoredVersion],
    ) -> StoredVersion:
        raise self._unavailable()

    def versions(self, organization_id: str, question_id: str) -> list[StoredVersion]:
        raise self._unavailable()

    def all_versions(self, organization_id: str) -> list[StoredVersion]:
        raise self._unavailable()

    def get_version(self, organization_id: str, answer_version_id: str) -> StoredVersion:
        raise self._unavailable()

    def record_decision(
        self, organization_id: str, decision: StoredDecision, must_be_latest: bool
    ) -> StoredDecision:
        raise self._unavailable()

    def decision_for(self, organization_id: str, answer_version_id: str) -> StoredDecision | None:
        raise self._unavailable()

    def add_note(self, organization_id: str, note: ReviewNote) -> ReviewNote:
        raise self._unavailable()

    def notes(self, organization_id: str) -> list[ReviewNote]:
        raise self._unavailable()

    def add_proposal(self, organization_id: str, proposal: ReviewerProposal) -> ReviewerProposal:
        raise self._unavailable()

    def proposals(self, organization_id: str) -> list[ReviewerProposal]:
        raise self._unavailable()

    def add_export(self, organization_id: str, export: StoredExport) -> None:
        raise self._unavailable()

    def get_export(self, organization_id: str, export_id: str) -> StoredExport:
        raise self._unavailable()

    def apply_change_set(self, organization_id: str, change_set: ChangeSet) -> list[str]:
        raise self._unavailable()

    def applied_change_sets(self, organization_id: str) -> list[ChangeSet]:
        raise self._unavailable()

    def add_audit(self, organization_id: str, event: AuditEvent) -> None:
        raise self._unavailable()

    def audit(self, organization_id: str) -> list[AuditEvent]:
        raise self._unavailable()
