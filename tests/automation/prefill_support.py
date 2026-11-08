"""B2-AUTO-002 P1 harness: an explicit, labelled **test** approval provider and helpers.

``TestApprovals`` implements B's consumer port ``ApprovedPrefillReader`` for tests only.
It is injected with ``app.dependency_overrides``; runtime code has no seeded approvals.
It mirrors C3's semantics that matter to B: an edit makes the old approval stale, and
template and rendered text are hashed separately. It is **not** C3 and is never
reported as an integrated producer.
"""

from __future__ import annotations

import hashlib
import itertools
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.automation.prefill_deps import (
    PrefillBrowserConfig,
    get_approved_prefill_reader,
    get_attachment_evidence_reader,
    get_prefill_browser_config,
    get_prefill_clock,
    get_prefill_currentness,
    get_runtime_epoch,
)
from strongstart_api.identity import require_identity
from strongstart_contracts import Provenance, ProvenanceClass, SessionIdentity
from strongstart_contracts.answers import ApprovalSnapshot, DependencyRef
from strongstart_contracts.automation_prefill import (
    ApprovedPrefillContent,
    ApprovedTypedValue,
    DependencyCurrentness,
    TrustedAttachmentRecord,
)
from strongstart_contracts.fixture_adapters import ApprovalNotUsable

PREFILL_SRC = {"mode": "fixture", "fixture_id": "rep-prefill-definition-v1"}
PORTAL_SRC = {"mode": "fixture", "fixture_id": "rep-portal-definition-v1"}
ORG = "demo-org"
OTHER = SessionIdentity(
    actor_id="x", organization_id="other-org", roles=[], is_fixture=True, label="TEST other org"
)
_ids = itertools.count(1)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def key(prefix: str = "key") -> str:
    return f"{prefix}-{next(_ids):08d}"


@dataclass
class Approval:
    approval_id: str
    organization_id: str
    question_set_id: str
    question_id: str
    question_version: int
    template: str
    rendered: str
    typed: list[str] | None
    answer_version: int = 1
    stale_reason: str | None = None
    dependencies: list[DependencyRef] = field(
        default_factory=lambda: [DependencyRef(kind="pack", ref_id="pack-demo", version="1")]
    )
    # deliberate corruption switches for integrity tests
    corrupt: str | None = None


class TestApprovals:
    """Explicit TEST provider (``is_fixture=True``); it is never ``is_c_reader``."""

    __test__ = False
    is_fixture = True

    def __init__(self) -> None:
        self._approvals: dict[str, Approval] = {}
        self._lock = threading.Lock()
        self.calls: list[str] = []
        # Called with the approval ID on every resolve (exact-step synchronization).
        self.on_resolve: Callable[[str], None] | None = None
        self.epoch = "test-producer-epoch-1"

    def approve(
        self,
        question_set_id: str,
        question_id: str,
        text: str,
        *,
        rendered: str | None = None,
        typed: list[str] | None = None,
        question_version: int = 1,
        organization_id: str = ORG,
    ) -> str:
        approval_id = f"apr-test-{next(_ids):06d}"
        with self._lock:
            self._approvals[approval_id] = Approval(
                approval_id,
                organization_id,
                question_set_id,
                question_id,
                question_version,
                template=text,
                rendered=text if rendered is None else rendered,
                typed=typed,
            )
        return approval_id

    def edit(self, approval_id: str, new_text: str) -> None:
        """Staff saves a new answer version: the old approval becomes stale (C3 semantics)."""
        with self._lock:
            a = self._approvals[approval_id]
            self._approvals[approval_id] = replace(a, stale_reason="newer_version_saved")
            del new_text

    def change_dependency(self, approval_id: str) -> None:
        with self._lock:
            a = self._approvals[approval_id]
            self._approvals[approval_id] = replace(a, stale_reason="change_set_applied:cs-1")

    def corrupt(self, approval_id: str, how: str) -> None:
        with self._lock:
            self._approvals[approval_id] = replace(self._approvals[approval_id], corrupt=how)

    def resolve_for_prefill(
        self, organization_id: str, approval_snapshot_id: str
    ) -> ApprovedPrefillContent:
        self.calls.append(approval_snapshot_id)
        if self.on_resolve is not None:
            self.on_resolve(approval_snapshot_id)
        with self._lock:
            a = self._approvals.get(approval_snapshot_id)
        if a is None or a.organization_id != organization_id:
            raise ApprovalNotUsable(approval_snapshot_id, "no such approval")
        if a.stale_reason is not None:
            raise ApprovalNotUsable(approval_snapshot_id, f"stale: {a.stale_reason}")
        template_sha = sha(a.template)
        rendered_sha = sha(a.rendered)
        if a.corrupt == "template_hash":
            template_sha = sha(a.template + "x")
        if a.corrupt == "rendered_hash":
            rendered_sha = sha(a.rendered + "x")
        snapshot = ApprovalSnapshot(
            approval_snapshot_id=a.approval_id,
            answer_snapshot_id=f"av-test-{a.approval_id}-{a.answer_version}",
            content_sha256=sha(a.template) if a.corrupt != "snapshot_hash" else sha("other"),
            dependencies=list(a.dependencies),
            approval_record_ref=a.approval_id,
            decided_at=datetime(2026, 11, 8, tzinfo=UTC),
            provenance=Provenance(
                provenance_class=ProvenanceClass.SIMULATED,
                is_simulated=True,
                note="TEST approval provider (B2-AUTO-002 P1 harness); not C3.",
            ),
        )
        return ApprovedPrefillContent(
            organization_id=a.organization_id,
            approval=snapshot,
            answer_version_id=snapshot.answer_snapshot_id
            if a.corrupt != "answer_id"
            else "av-other",
            answer_version=a.answer_version,
            question_set_id=a.question_set_id,
            question_id=a.question_id,
            question_version=a.question_version,
            template_text=a.template,
            template_sha256=template_sha,
            rendered_text=a.rendered,
            rendered_sha256=rendered_sha,
            renderer_version="test-renderer/1",
            unresolved_marker_count=a.rendered.count("{{"),
            dependency_snapshot_sha256=sha("snapshot:" + a.approval_id),
            dependencies=list(a.dependencies)
            if a.corrupt != "dependencies"
            else [DependencyRef(kind="fact", ref_id="fact-x", version="9")],
            currentness="current",
            currentness_checked_at=datetime(2026, 11, 8, tzinfo=UTC),
            typed_value=ApprovedTypedValue(kind="choice", values=a.typed) if a.typed else None,
            provenance=snapshot.provenance,
            is_fixture=True,
            producer_id="b2-test-approval-provider",
            producer_epoch=self.epoch,
        )


class TestAttachments:
    __test__ = False
    is_fixture = True

    def __init__(self, records: list[TrustedAttachmentRecord]) -> None:
        self.records = records

    def list_for(self, organization_id: str, question_set_id: str) -> list[TrustedAttachmentRecord]:
        return list(self.records) if organization_id == ORG else []


class TestCurrentness:
    __test__ = False
    is_fixture = True

    def __init__(self) -> None:
        self.status = "current"

    def check(
        self, organization_id: str, target_id: str, dependencies: list[DependencyRef]
    ) -> DependencyCurrentness:
        return DependencyCurrentness(status=self.status, detail="TEST currentness provider")  # type: ignore[arg-type]


class Clock:
    __test__ = False

    def __init__(self) -> None:
        self.now = datetime(2026, 11, 8, 15, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@dataclass
class Harness:
    client: TestClient
    settings: Settings
    approvals: TestApprovals
    clock: Clock
    epoch: list[str]
    browser: list[PrefillBrowserConfig]
    attachments: list[Any]
    currentness: list[Any]

    def other_org_client(self) -> TestClient:
        app = self.client.app
        c = TestClient(app)
        app.dependency_overrides[require_identity] = lambda: OTHER  # type: ignore[attr-defined]
        return c


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "auth_mode": "fixture",
        "funding_capture_store_dir": tmp_path / "captures",
        "dev_b_store_dir": tmp_path / "dev-b",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def harness(tmp_path: Path, *, reader: Any = "test", **overrides: Any) -> Harness:
    settings = make_settings(tmp_path, **overrides)
    app = create_app(settings)
    approvals = TestApprovals()
    clock = Clock()
    epoch = ["epoch-test-1"]
    browser = [PrefillBrowserConfig()]
    attachments: list[Any] = []
    currentness: list[Any] = [None]
    if reader == "test":
        app.dependency_overrides[get_approved_prefill_reader] = lambda: approvals
    app.dependency_overrides[get_prefill_clock] = lambda: clock
    app.dependency_overrides[get_runtime_epoch] = lambda: epoch[0]
    app.dependency_overrides[get_prefill_browser_config] = lambda: browser[0]
    app.dependency_overrides[get_prefill_currentness] = lambda: currentness[0]

    def attach() -> Any:
        if attachments:
            return attachments[0]
        from strongstart_contracts.automation_prefill import UnconfiguredAttachmentEvidenceReader

        return UnconfiguredAttachmentEvidenceReader()

    app.dependency_overrides[get_attachment_evidence_reader] = attach
    return Harness(
        TestClient(app), settings, approvals, clock, epoch, browser, attachments, currentness
    )


def save_definition(c: TestClient, source: dict[str, Any] = PREFILL_SRC) -> dict[str, Any]:
    sha_in = c.post("/api/automation/intake", json={"source": source}).json()["input"]["sha256"]
    r = c.post(
        "/api/automation/definitions",
        json={"source": source, "expected_input_sha256": sha_in, "idempotency_key": key("save")},
    )
    assert r.status_code == 201, r.text
    pub: dict[str, Any] = r.json()["publication"]
    return pub


def published(pub: dict[str, Any], original: str) -> str:
    return str(
        next(
            m["published_question_id"]
            for m in pub["id_mapping"]
            if m["original_question_id"] == original
        )
    )


def plan(
    h: Harness,
    pub: dict[str, Any],
    selections: list[tuple[str, str]],
    portal: str = "rep-prefill-v1",
    client: TestClient | None = None,
) -> Any:
    body = {
        "question_set_id": pub["question_set_id"],
        "portal_fixture_id": portal,
        "selections": [
            {"published_question_id": published(pub, o), "approval_snapshot_id": a}
            for o, a in selections
        ],
    }
    return (client or h.client).post("/api/automation/prefill-plans", json=body)


def approve(h: Harness, pub: dict[str, Any], original: str, text: str, **kw: Any) -> str:
    return h.approvals.approve(pub["question_set_id"], published(pub, original), text, **kw)


def execute(h: Harness, p: dict[str, Any], idem: str | None = None, **extra: Any) -> Any:
    body = {
        "expected_plan_sha256": p["plan_sha256"],
        "idempotency_key": idem or key("exec"),
        **extra,
    }
    return h.client.post(f"/api/automation/prefill-plans/{p['plan_id']}/execute", json=body)


def fields(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["field_id"]: f for f in result["run"]["run"]["fields"]}


@dataclass
class Steps:
    """Records harness hook events for exact-step synchronization in tests."""

    events: list[str] = field(default_factory=list)

    def __iter__(self) -> Iterator[str]:
        return iter(self.events)
