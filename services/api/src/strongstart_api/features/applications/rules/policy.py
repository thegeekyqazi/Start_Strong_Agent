"""Writing-policy source for POL-01/POL-02 (C2 spec s5).

C2 has only a SYNTHETIC policy fixture (``tests/fixtures/policy/demo-policy-v1.json``),
loaded only in fixture mode. Without a configured policy, POL-01/POL-02 report
``needs_review`` (missing prerequisite), never ``pass`` (s9.1).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from strongstart_contracts import Provenance

POLICY_RELATIVE = Path("tests/fixtures/policy/demo-policy-v1.json")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TerminologyRule(_Strict):
    rule_id: str
    scope: str = Field(description='"application" or a program name the answer mentions.')
    forbidden_term: str = Field(min_length=1, max_length=60)
    preferred_term: str = Field(min_length=1, max_length=60)


class ProtectedName(_Strict):
    rule_id: str
    full_name: str = Field(min_length=1, max_length=120)
    acronym: str | None = Field(default=None, max_length=20)


class WritingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str
    policy_version: str
    provenance: Provenance
    terminology_rules: list[TerminologyRule] = Field(max_length=200)
    protected_names: list[ProtectedName] = Field(max_length=200)


def _policy_path() -> Path | None:
    repo_root = Path(__file__).resolve().parents[6]
    for candidate in (repo_root / POLICY_RELATIVE, Path.cwd() / POLICY_RELATIVE):
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=4)
def _load(path: Path) -> WritingPolicy:
    return WritingPolicy.model_validate(json.loads(path.read_text(encoding="utf-8")))


def fixture_policy() -> WritingPolicy | None:
    path = _policy_path()
    return _load(path) if path else None
