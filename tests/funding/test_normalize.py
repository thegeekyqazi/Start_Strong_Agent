"""DISC-05 query builder and DISC-06 normalization/dedup predicates."""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from strongstart_api.features.funding import normalize
from strongstart_api.features.funding.normalize import build_query, normalize_url
from strongstart_contracts.discovery import SearchProfile, SearchRequest


def test_fragment_tracking_case_and_default_port_collapse() -> None:
    a = normalize_url("https://Demo-Funder.Example:443/p/grants?utm_source=x&fbclid=1#apply")
    b = normalize_url("https://demo-funder.example/p/grants")
    assert a == b == "https://demo-funder.example/p/grants"


def test_semantic_query_and_path_differences_remain_distinct() -> None:
    base = "https://demo-funder.example/p/grants"
    variants = {
        normalize_url(base),
        normalize_url(base + "?cycle=2025"),
        normalize_url(base + "?cycle=2026"),
        normalize_url(base + "?stream=network"),
        normalize_url(base + "/"),
        normalize_url("https://demo-funder.example/P/Grants"),
    }
    assert len(variants) == 6


def test_query_uses_only_allowlisted_public_profile_fields() -> None:
    profile = SearchProfile(
        interests=["early learning"], geography="Demo Region", program_context="family literacy"
    )
    q, used = build_query(profile, ["interests", "geography", "program_context"])
    assert q == "early learning family literacy Demo Region grant funding"
    assert used == ["interests", "program_context", "geography"]
    q2, used2 = build_query(profile, ["interests"])
    assert "Demo Region" not in q2 and used2 == ["interests"]


def test_query_builder_has_no_access_to_private_ports() -> None:
    params = inspect.signature(build_query).parameters
    assert list(params) == ["profile", "allowed_fields"]
    source = inspect.getsource(normalize)
    for forbidden in ("EvidenceProvider", "ApprovedAnswerResolver", "CaptureStore", "JobStore"):
        assert forbidden not in source


@pytest.mark.parametrize(
    "profile",
    [
        {"interests": []},
        {"interests": ["x" * 61]},
        {"interests": ["a", "b"]},
        {"interests": ["ok term"] * 6},
        {"interests": ["<script>"]},
        {"interests": ["line\nbreak"]},
        {"interests": ["early learning"], "geography": "g" * 81},
        {"interests": ["early learning"], "private_notes": "family story"},
    ],
)
def test_malformed_or_oversized_profiles_rejected(profile: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SearchProfile.model_validate(profile)


def test_result_limit_is_bounded_by_contract() -> None:
    with pytest.raises(ValidationError):
        SearchRequest.model_validate(
            {"profile": {"interests": ["early learning"]}, "max_results": 6}
        )
