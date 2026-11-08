"""Shared DTOs reject malformed data; fixture links and provenance stay exact.

PKG-01 / SEC-05 bootstrap boundary only.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any

import pytest
from pydantic import ValidationError

from strongstart_contracts import (
    ApprovalSnapshot,
    CapabilityUnavailable,
    ErrorEnvelope,
    Fact,
    FixtureBundle,
    PrefillAction,
    QuestionSet,
    load_fixture_bundle,
)
from strongstart_contracts.fixture_adapters import (
    ApprovalNotUsable,
    FixtureApprovedAnswerResolver,
    FixtureCaptureStore,
)
from strongstart_contracts.ports import (
    UnconfiguredApprovedAnswerResolver,
    UnconfiguredCaptureStore,
    UnconfiguredEvidenceProvider,
    UnconfiguredJobStore,
)
from tests.conftest import BUNDLE_PATH


@pytest.fixture
def bundle() -> FixtureBundle:
    return load_fixture_bundle(BUNDLE_PATH)


def test_demo_bundle_validates_and_has_required_ids(bundle: FixtureBundle) -> None:
    assert [o.organization_id for o in bundle.organizations] == ["demo-org"]
    assert {p.pack_version_id for p in bundle.packs} == {"demo-a-v1", "demo-b-v1"}
    assert bundle.opportunities[0].opportunity_id == "demo-gos"
    assert bundle.form_maps[0].form_id == "demo-gos-v1"
    questions = {q.question_id: q for q in bundle.question_sets[0].questions}
    mission = questions["mission-q1"]
    assert mission.limit is not None and (mission.limit.maximum, mission.limit.unit) == (
        50,
        "words",
    )
    assert questions["pending-q4"].limit is not None
    assert questions["pending-q4"].limit.unit == "unknown"  # missing unit stays unknown


def test_required_fixture_cases_present(bundle: FixtureBundle) -> None:
    fact = bundle.evidence_bundles[0].facts[0]
    assert fact.provenance.is_simulated and fact.reporting_period == "2025-09/2026-06"
    assert fact.supporting_refs[0].publication_date.status == "known"
    cond = bundle.requirement_sets[0].conditions[0]
    assert cond.evaluation == "unknown" and cond.missing_inputs
    conflict = next(q for q in bundle.question_sets[0].questions if q.conflicts).conflicts[0]
    assert {c.maximum for c in conflict.candidate_limits} == {350, 500}
    assert conflict.resolution == "unresolved"
    failed = bundle.job_results[0]
    assert failed.state == "failed" and failed.error is not None
    assert failed.error.code == "capability_unavailable"


def test_every_record_keeps_a_simulation_label(bundle_json: dict[str, Any]) -> None:
    labels: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "provenance" in node:
                labels.append(node["provenance"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(bundle_json)
    assert labels and all(p["is_simulated"] is True for p in labels)
    assert all(p["provenance_class"] in {"simulated", "engineering_derived"} for p in labels)


def _mutated(data: dict[str, Any], fn: Any) -> dict[str, Any]:
    d = copy.deepcopy(data)
    fn(d)
    return d


@pytest.mark.parametrize(
    ("label", "mutation"),
    [
        ("dangling pack", lambda d: d["evidence_bundles"][0].update(pack_version_id="nope-v9")),
        ("dangling org", lambda d: d["packs"][0].update(organization_id="other-org")),
        ("dangling question", lambda d: d["form_maps"][0]["fields"][0].update(question_id="q-x")),
        ("dangling req set", lambda d: d["opportunities"][0].update(requirement_set_ids=["x"])),
        ("hash mismatch", lambda d: d["answer_snapshots"][0].update(content="edited text")),
        (
            "approval hash drift",
            lambda d: d["approval_snapshots"][0].update(content_sha256="0" * 64),
        ),
        ("question version", lambda d: d["answer_snapshots"][0].update(question_version=2)),
        ("not simulated", lambda d: d["provenance"].update(is_simulated=False)),
        ("bad id", lambda d: d["organizations"][0].update(organization_id="Demo Org")),
        ("float decimal", lambda d: d["evidence_bundles"][0]["facts"][0].update(value=120.5)),
        ("extra field", lambda d: d["approval_snapshots"][0].update(approved=True)),
        (
            "duplicate field",
            lambda d: d["form_maps"][0]["fields"].append(d["form_maps"][0]["fields"][0]),
        ),
        ("unknown change ref", lambda d: d["change_sets"][0]["affected_refs"].append("ghost")),
    ],
)
def test_malformed_bundles_rejected(bundle_json: dict[str, Any], label: str, mutation: Any) -> None:
    with pytest.raises(ValidationError):
        FixtureBundle.model_validate(_mutated(bundle_json, mutation))


def test_decimal_strings_are_exact() -> None:
    base = load_fixture_bundle(BUNDLE_PATH).evidence_bundles[0].facts[0].model_dump()
    for bad in ["1e3", "01", "1.", "NaN", " 1", "1,000"]:
        with pytest.raises(ValidationError):
            Fact.model_validate({**base, "value": bad})
    assert Fact.model_validate({**base, "value": "-0.125"}).value == "-0.125"


def test_prefill_cannot_express_submit_or_client_approval(bundle: FixtureBundle) -> None:
    good = {
        "action_id": "a1",
        "operation": "fill_field",
        "origin": "fixture://demo-gos.local",
        "form_id": "demo-gos-v1",
        "form_version": 1,
        "field_id": "mission-field",
        "question_id": "mission-q1",
        "approval_snapshot_id": "demo-approval-mission-v1",
    }
    PrefillAction.model_validate(good)
    for bad in ({"operation": "submit"}, {"operation": "sign"}, {"approved": True}):
        with pytest.raises(ValidationError):
            PrefillAction.model_validate({**good, **bad})
    assert "approved" not in ApprovalSnapshot.model_fields


def test_duplicate_question_ids_rejected(bundle: FixtureBundle) -> None:
    qs = bundle.question_sets[0].model_dump()
    qs["questions"].append(qs["questions"][0])
    with pytest.raises(ValidationError):
        QuestionSet.model_validate(qs)


@pytest.mark.parametrize(
    "call",
    [
        lambda: UnconfiguredCaptureStore().get("x"),
        lambda: UnconfiguredEvidenceProvider().get_bundle("demo-org", "demo-a-v1"),
        lambda: UnconfiguredApprovedAnswerResolver().resolve(
            "demo-org", "demo-approval-mission-v1"
        ),
        lambda: UnconfiguredJobStore().get_result("j"),
    ],
)
def test_unconfigured_ports_fail_explicitly(call: Any) -> None:
    with pytest.raises(CapabilityUnavailable) as info:
        call()
    env = info.value.to_envelope()
    assert isinstance(env, ErrorEnvelope) and env.code == "capability_unavailable"


def test_fixture_resolver_stales_after_change_set(bundle: FixtureBundle) -> None:
    fresh = FixtureApprovedAnswerResolver(bundle)
    assert fresh.is_fixture is True
    ap = fresh.resolve("demo-org", "demo-approval-mission-v1")
    assert (
        ap.content_sha256 == hashlib.sha256(bundle.answer_snapshots[0].content.encode()).hexdigest()
    )
    changed = FixtureApprovedAnswerResolver(bundle, frozenset({"demo-change-fact-v2"}))
    expected = bundle.expectations.stale_after_change_set["demo-change-fact-v2"]
    for approval_id in expected:
        with pytest.raises(ApprovalNotUsable, match="stale"):
            changed.resolve("demo-org", approval_id)


def test_fixture_resolver_scopes_organization(bundle: FixtureBundle) -> None:
    resolver = FixtureApprovedAnswerResolver(bundle)
    with pytest.raises(ApprovalNotUsable):
        resolver.resolve("other-org", "demo-approval-mission-v1")
    with pytest.raises(ApprovalNotUsable):
        resolver.resolve("demo-org", "missing-approval")


def test_fixture_capture_store_versions_are_immutable(bundle: FixtureBundle) -> None:
    store = FixtureCaptureStore()
    ref = bundle.opportunities[0].source_refs[0]
    store.put(ref, b"original", "text/plain")
    with pytest.raises(ValueError, match="immutable"):
        store.put(ref, b"changed", "text/plain")
    assert store.get(ref.source_version_id).content == b"original"
    with pytest.raises(CapabilityUnavailable):
        store.get("unknown-version")
