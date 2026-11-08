"""A3 source-validation orchestration: resolve, authorize, freeze, evaluate, persist."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

from strongstart_contracts import (
    NumericValidationReport,
    NumericValidationRequest,
    SourceValidationReport,
    SourceValidationRequest,
    ValidationDependency,
)

from .numeric_rules import EVALUATOR_ID as NUMERIC_EVALUATOR_ID
from .numeric_rules import run as run_numeric
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


class NumericValidationService:
    def __init__(self, repository: SourceValidationRepository) -> None:
        self.repository = repository

    def evaluate(
        self,
        organization_id: str,
        actor_id: str,
        request: NumericValidationRequest,
        *,
        now: datetime | None = None,
    ) -> NumericValidationReport:
        frozen_time = now or datetime.now(UTC)
        ctx = self.repository.resolve_numeric(organization_id, request)
        rule_ids = [str(value) for value in request.rule_ids]
        results = run_numeric(ctx, rule_ids)
        payload = {
            "context": asdict(ctx),
            "rule_ids": sorted(rule_ids),
            "frozen_time": frozen_time.isoformat(),
        }
        input_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        dependencies = [
            ValidationDependency(
                kind="fact_version", ref_id=ctx.fact.fact_id, version=str(ctx.fact.version)
            ),
            ValidationDependency(
                kind="pack_version", ref_id=request.pack_version_id, version=request.pack_version_id
            ),
            ValidationDependency(
                kind="rounding_policy",
                ref_id="decimal-half-up",
                version=f"places:{request.rounding_places}",
            ),
            ValidationDependency(
                kind="permission_snapshot", ref_id=actor_id, version="server-derived-v1"
            ),
        ]
        if ctx.project_input is not None:
            dependencies.append(
                ValidationDependency(
                    kind="project_input",
                    ref_id=ctx.project_input[0],
                    version=str(ctx.project_input[1]),
                )
            )
        if ctx.numerator is not None or ctx.denominator is not None:
            dependencies.append(ValidationDependency(kind="formula", ref_id="ratio", version="1"))
        report = NumericValidationReport(
            evaluation_id=f"val-{uuid4()}",
            organization_id=organization_id,
            pack_version_id=request.pack_version_id,
            fact_id=ctx.fact.fact_id,
            fact_version=ctx.fact.version,
            input_sha256=input_hash,
            evaluator_build=NUMERIC_EVALUATOR_ID,
            frozen_time=frozen_time,
            results=results,
            dependencies=dependencies,
        )
        self.repository.persist_numeric(report, actor_id=actor_id)
        return report
