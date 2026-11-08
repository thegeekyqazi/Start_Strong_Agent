"""C1 contracts are exported, owned by C and cannot express approval (SEC-14)."""

from __future__ import annotations

from strongstart_contracts.export import build_schema


def test_c1_contracts_exported_owned_by_c_without_approval_fields() -> None:
    defs = build_schema()["$defs"]
    assert isinstance(defs, dict)
    for name in ["DraftRequest", "DraftProposal", "ApplicationWorkspace", "ModelRunInfo"]:
        assert defs[name]["x-owner"] == "C"
        assert defs[name]["x-contract-status"] == "draft"
        assert defs[name]["additionalProperties"] is False
        assert not {"approved", "status", "state", "approval"} & set(defs[name]["properties"])
