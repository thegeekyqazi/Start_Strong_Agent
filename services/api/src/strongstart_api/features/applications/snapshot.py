"""Dependency snapshot for exact-version approval (APP-04, JOB-05; C3 spec s2, s4).

The snapshot hash covers: the exact content hash, the organization (permission scope), the
question and its version, the evidence pack version, a content digest of every bound fact
(``Fact`` has no version field yet, so any change to its value/unit/scope/period/status or
support changes the digest), the writing-policy version, the rule-set version, the counter
set and the evaluation-time policy. Recomputing it at action time and comparing with the
stored value detects every dependency change, so an old approval can never be replayed.
"""

from __future__ import annotations

import hashlib
import json

from strongstart_contracts import EvidenceBundle, Fact, Question
from strongstart_contracts.answers import DependencyRef, RenderedAnswer
from strongstart_contracts.approval_integrity import approval_snapshot_sha256

from .rules.checks import RULE_VERSION
from .rules.policy import WritingPolicy

EVALUATION_TIME_POLICY = "live-at-action"


def _digest(data: object) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fact_digest(fact: Fact) -> str:
    return _digest(fact.model_dump(mode="json"))


def dependency_refs(
    question: Question,
    bundle: EvidenceBundle,
    rendered: RenderedAnswer,
    policy: WritingPolicy | None,
) -> list[DependencyRef]:
    facts = {f.fact_id: f for f in bundle.facts}
    refs = [
        DependencyRef(
            kind="question", ref_id=question.question_id, version=str(question.question_version)
        ),
        DependencyRef(kind="pack", ref_id=bundle.pack_id, version=bundle.pack_version_id),
        DependencyRef(kind="rule_set", ref_id="c-rules", version=RULE_VERSION),
    ]
    for fact_id in sorted({b.fact_id for b in rendered.bindings}):
        refs.append(
            DependencyRef(
                kind="fact",
                ref_id=fact_id,
                version=f"{bundle.pack_version_id}:{fact_digest(facts[fact_id])[:16]}",
            )
        )
    if policy is not None:
        refs.append(
            DependencyRef(kind="policy", ref_id=policy.policy_id, version=policy.policy_version)
        )
    return refs


def snapshot_sha256(content_sha256: str, organization_id: str, refs: list[DependencyRef]) -> str:
    return approval_snapshot_sha256(content_sha256, organization_id, refs)
