from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from strongstart_api.features.knowledge.packs import PackService
from strongstart_contracts import PackFactBinding, PackManifestRequest, PackPolicyBinding


def manifest(**changes: object) -> PackManifestRequest:
    values: dict[str, object] = {
        "pack_id": "pack-a",
        "pack_version_id": "pack-a-v1",
        "bundle_id": "bundle-a-v1",
        "application_context": "application-1",
        "mapping_version": "pack-mapping-v1",
        "parser_version": "parser-v1",
        "locale": "en-CA",
        "access_labels": ["staff"],
        "facts": [PackFactBinding(fact_id="fact-1", fact_version=1)],
        "source_version_ids": ["source-v1"],
        "policies": [],
        "provenance_class": "simulated",
        "is_simulated": True,
    }
    values.update(changes)
    return PackManifestRequest(**values)


def test_manifest_rejects_duplicates_and_identity_fields() -> None:
    with pytest.raises(ValidationError):
        manifest(source_version_ids=["source-v1", "source-v1"])
    with pytest.raises(ValidationError):
        manifest(
            facts=[
                PackFactBinding(fact_id="fact-1", fact_version=1),
                PackFactBinding(fact_id="fact-1", fact_version=2),
            ]
        )
    policy = PackPolicyBinding(policy_id="policy-1", policy_version=1, content_sha256="a" * 64)
    with pytest.raises(ValidationError):
        manifest(policies=[policy, policy])
    body = manifest().model_dump(mode="json") | {"organization_id": "other-org"}
    with pytest.raises(ValidationError):
        PackManifestRequest.model_validate(body)
    with pytest.raises(ValidationError):
        PackManifestRequest.model_validate(
            manifest().model_dump(mode="json") | {"mapping_version": "unsupported"}
        )


@given(
    old=st.dictionaries(
        st.from_regex(r"fact-[a-z]{1,4}", fullmatch=True),
        st.integers(min_value=1, max_value=20).map(str),
        max_size=20,
    ),
    new=st.dictionaries(
        st.from_regex(r"fact-[a-z]{1,4}", fullmatch=True),
        st.integers(min_value=1, max_value=20).map(str),
        max_size=20,
    ),
)
def test_diff_marks_exact_old_versions_and_never_unchanged(
    old: dict[str, str], new: dict[str, str]
) -> None:
    empty: dict[str, dict[str, str]] = {
        "fact_version": {},
        "source_version": {},
        "policy": {},
    }
    changes, keys = PackService._diff(
        "pack-a-v1",
        "pack-b-v1",
        {**empty, "fact_version": old},
        {**empty, "fact_version": new},
    )
    expected = {
        ("fact_version", ref_id, version)
        for ref_id, version in old.items()
        if new.get(ref_id) != version
    }
    assert keys == expected | {("pack_version", "pack-a-v1", "pack-a-v1")}
    reported = {item.ref_id for item in changes if item.kind == "fact"}
    assert reported == {
        ref_id for ref_id in set(old) | set(new) if old.get(ref_id) != new.get(ref_id)
    }
