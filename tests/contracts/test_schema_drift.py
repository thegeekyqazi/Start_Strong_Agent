"""Contract generation is consistent (JOB-05 boundary only): committed schema == regenerated."""

from __future__ import annotations

import json

from strongstart_contracts.export import build_schema
from tests.conftest import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "packages/contracts/schema/strongstart-contracts.schema.json"


def test_schema_export_is_deterministic() -> None:
    assert json.dumps(build_schema(), sort_keys=True) == json.dumps(build_schema(), sort_keys=True)


def test_committed_schema_matches_models() -> None:
    committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(build_schema())), "run `make contracts`"


def test_schema_marks_contract_status_and_owner() -> None:
    defs = build_schema()["$defs"]
    assert isinstance(defs, dict)
    for name in [
        "SourceReference",
        "Opportunity",
        "QuestionSet",
        "ApprovalSnapshot",
        "ErrorEnvelope",
    ]:
        assert defs[name]["x-contract-status"] in {"draft", "frozen"}
        assert defs[name]["x-owner"]
