"""A3 source-validation orchestration: resolve, authorize, freeze, evaluate, persist."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

from strongstart_contracts import (
    SourceValidationReport,
    SourceValidationRequest,
    ValidationDependency,
)

from .registry import run
from .repository import SourceValidationRepository
from .rules import EVALUATOR_ID, SourceContext


def _canonical_hash(ctx: SourceContext, rules: list[str], frozen_time: datetime) -> str:
    payload = {
        "context": asdict(ctx),
        "rule_ids": sorted(rules),
        "frozen_time": frozen_time.isoformat(),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _dependencies(ctx: SourceContext, actor_id: str) -> list[ValidationDependency]:
    dependencies = [
        ValidationDependency(
            kind="subject", ref_id=ctx.source_version_id, version=ctx.registered_sha256
        ),
        ValidationDependency(
            kind="source_version",
            ref_id=ctx.source_version_id,
            version=ctx.registered_sha256,
            content_hash=ctx.registered_sha256,
        ),
        ValidationDependency(
            kind="artifact_hash",
            ref_id=ctx.source_version_id,
            version=ctx.registered_sha256,
            content_hash=ctx.registered_sha256,
        ),
        ValidationDependency(
            kind="permission_snapshot", ref_id=actor_id, version="server-derived-v1"
        ),
    ]
    if ctx.requested_locator is not None:
        dependencies.append(
            ValidationDependency(
                kind="passage_locator",
                ref_id=ctx.source_version_id,
                version=ctx.requested_locator,
            )
        )
    if ctx.claimed_quote is not None:
        dependencies.append(
            ValidationDependency(
                kind="normalization_policy",
                ref_id="quote-whitespace-v1",
                version="1",
            )
        )
    return dependencies


class SourceValidationService:
    def __init__(self, repository: SourceValidationRepository) -> None:
        self.repository = repository

    def evaluate(
        self,
        organization_id: str,
        actor_id: str,
        request: SourceValidationRequest,
        *,
        now: datetime | None = None,
    ) -> SourceValidationReport:
        frozen_time = now or datetime.now(UTC)
        ctx = self.repository.resolve_source(
            organization_id,
            request.source_version_id,
            locator=request.locator,
            claimed_quote=request.claimed_quote,
        )
        rule_ids = [str(value) for value in request.rule_ids]
        results = run(ctx, rule_ids)
        report = SourceValidationReport(
            evaluation_id=f"val-{uuid4()}",
            organization_id=organization_id,
            source_version_id=request.source_version_id,
            input_sha256=_canonical_hash(ctx, rule_ids, frozen_time),
            evaluator_build=EVALUATOR_ID,
            frozen_time=frozen_time,
            results=results,
            dependencies=_dependencies(ctx, actor_id),
        )
        self.repository.persist(report, actor_id=actor_id)
        return report
