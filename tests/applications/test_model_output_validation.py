"""Every model response is validated; bad output cannot pass (C1 spec s5; SEC-14, SEC-05)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from strongstart_api.features.applications.models.base import ModelOutputRejected
from strongstart_api.features.applications.models.validation import (
    MAX_RAW_BYTES,
    validate_draft_output,
)

from .conftest import DRAFT_BODY, DRAFT_URL, FACT, make_client

ALLOWED = frozenset({FACT})


def valid(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "text": f"Demo Org served {{{{fact:{FACT}}}}}.",
        "fact_ids": [FACT],
        "uncertainties": [],
    }
    body.update(changes)
    return body


def issues_for(raw: str) -> list[str]:
    with pytest.raises(ModelOutputRejected) as exc:
        validate_draft_output(raw, ALLOWED)
    return exc.value.issues


def test_valid_output_passes() -> None:
    draft = validate_draft_output(json.dumps(valid()), ALLOWED)
    assert draft.fact_ids == (FACT,)
    assert [s.kind for s in draft.segments] == ["text", "fact_slot", "text"]


@pytest.mark.parametrize(
    "raw",
    ['{"text": "x", "fact_ids": [', "", "not json", "[1, 2]", '"string"', "null"],
)
def test_malformed_json_rejected(raw: str) -> None:
    assert issues_for(raw)[0] in {"malformed_json", "not_an_object"}


def test_duplicate_keys_rejected() -> None:
    raw = '{"text": "a", "text": "b", "fact_ids": [], "uncertainties": []}'
    assert issues_for(raw) == ["duplicate_key"]


def test_non_finite_number_rejected() -> None:
    assert issues_for('{"text": NaN}') == ["non_finite_number"]


def test_unknown_fact_id_rejected() -> None:
    raw = json.dumps(valid(text="x {{fact:demo-fact-invented}}", fact_ids=["demo-fact-invented"]))
    assert issues_for(raw) == ["unknown_fact_id"]


def test_fact_ids_must_match_slots() -> None:
    assert issues_for(json.dumps(valid(fact_ids=[]))) == ["fact_ids_mismatch"]
    assert issues_for(json.dumps(valid(fact_ids=[FACT, FACT]))) == ["fact_ids_mismatch"]


def test_malformed_slot_rejected() -> None:
    raw = json.dumps(valid(text="served {{fact:Bad ID}} and {{fact:" + FACT + "}}"))
    assert issues_for(raw) == ["malformed_slot"]


@pytest.mark.parametrize("extra", [{"confidence": 0.9}, {"tool": "shell"}, {"org_id": "x"}])
def test_extra_fields_rejected(extra: dict[str, Any]) -> None:
    assert issues_for(json.dumps(valid(**extra)))[0] == "schema"


@pytest.mark.parametrize(
    "smuggled",
    [
        {"approved": True},
        {"status": "approved"},
        {"state": "approved"},
        {"approval_status": "approved"},
        {"decision": "approve"},
        {"meta": {"approved": True}},
        {"uncertainties": [{"approved": True}]},
    ],
)
def test_sec14_approval_or_status_fields_rejected(smuggled: dict[str, Any]) -> None:
    assert issues_for(json.dumps(valid(**smuggled))) == ["sec14_forbidden_field"]


def test_wrong_types_rejected() -> None:
    assert issues_for(json.dumps(valid(text=5)))[0] == "schema"
    assert issues_for(json.dumps(valid(fact_ids="demo")))[0] == "schema"


def test_deeply_nested_output_is_a_typed_rejection_not_a_crash() -> None:
    # Under the size cap. 3000 levels parse in json.loads but would crash a recursive walk;
    # 16000 levels exceed the parser's own limit. Both must be typed rejections.
    inside_object = '{"text":' + "[" * 3000 + "]" * 3000 + "}"
    bare = "[" * 16_000 + "]" * 16_000
    assert len(bare.encode()) <= MAX_RAW_BYTES
    assert issues_for(inside_object) == ["too_deeply_nested"]
    assert issues_for(bare) == ["too_deeply_nested"]
    assert issues_for(json.dumps(valid(meta=[[[[[[[[[[[[[[[[[["x"]]]]]]]]]]]]]]]]]]))) == [
        "too_deeply_nested"
    ]


def test_oversize_rejected() -> None:
    assert issues_for(" " * (MAX_RAW_BYTES + 1)) == ["oversize"]


class _CannedAdapter:
    """Test adapter returning fixed raw text through the real service and router."""

    is_fixture = True

    def __init__(self, raw: str) -> None:
        self.raw = raw

    def capabilities(self) -> Any:
        from strongstart_api.features.applications.models.fake import FakeAdapter

        return FakeAdapter().capabilities()

    async def complete(self, task: Any) -> str:
        return self.raw


def test_api_rejects_self_approving_output_with_typed_error() -> None:
    client = make_client(_CannedAdapter(json.dumps(valid(approved=True))), auth_mode="fixture")
    r = client.post(DRAFT_URL, json=DRAFT_BODY)
    assert r.status_code == 502
    body = r.json()
    assert body["code"] == "validation_failed"
    assert body["details"] == {
        "reason": "model_output_rejected",
        "issues": ["sec14_forbidden_field"],
    }
    assert "Demo Org served" not in r.text  # raw model output is never echoed back
