"""Authorized source-context resolver and immutable A3 receipt repository."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, cast

from sqlalchemy import Engine, insert, select

from strongstart_contracts import (
    NumericValidationReport,
    NumericValidationRequest,
    SourceValidationReport,
    ValidationDependency,
    ValidationResult,
)

from ...db import (
    evidence_pack_versions,
    evidence_packs,
    knowledge_facts,
    knowledge_passages,
    knowledge_source_versions,
    knowledge_sources,
    pack_facts,
    project_numeric_inputs,
    validation_dependencies,
    validation_evaluations,
    validation_results,
)
from ..knowledge.artifacts import ArtifactIntegrityError, ArtifactNotFoundError, ArtifactStore
from .numeric_rules import NumericContext, NumericFact
from .rules import SourceContext


class ValidationSubjectNotFoundError(Exception):
    """Subject is absent or outside the server-derived organization."""


class ValidationReceiptNotFoundError(Exception):
    """Receipt is absent or outside the server-derived organization."""


class SourceValidationRepository:
    def __init__(self, engine: Engine, artifacts: ArtifactStore | None = None) -> None:
        self.engine = engine
        self.artifacts = artifacts

    def resolve_source(
        self,
        organization_id: str,
        source_version_id: str,
        *,
        locator: str | None,
        claimed_quote: str | None,
    ) -> SourceContext:
        with self.engine.connect() as conn:
            row_obj = (
                conn.execute(
                    select(
                        knowledge_source_versions,
                        knowledge_sources.c.organization_id.label("source_organization_id"),
                        knowledge_sources.c.canonical_url,
                    )
                    .select_from(
                        knowledge_source_versions.join(
                            knowledge_sources,
                            knowledge_source_versions.c.source_id == knowledge_sources.c.id,
                        )
                    )
                    .where(
                        knowledge_source_versions.c.id == source_version_id,
                        knowledge_source_versions.c.organization_id == organization_id,
                        knowledge_sources.c.organization_id == organization_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row_obj is None:
                raise ValidationSubjectNotFoundError
            row = dict(row_obj)
            passage_rows = conn.execute(
                select(knowledge_passages.c.locator, knowledge_passages.c.exact_text)
                .where(knowledge_passages.c.source_version_id == source_version_id)
                .order_by(knowledge_passages.c.locator, knowledge_passages.c.id)
            ).all()
            duplicate_ids = tuple(
                conn.execute(
                    select(knowledge_source_versions.c.id)
                    .where(
                        knowledge_source_versions.c.organization_id == organization_id,
                        knowledge_source_versions.c.content_sha256 == row["content_sha256"],
                        knowledge_source_versions.c.id != source_version_id,
                    )
                    .order_by(knowledge_source_versions.c.id)
                ).scalars()
            )
            previous_hashes = tuple(
                conn.execute(
                    select(knowledge_source_versions.c.content_sha256)
                    .where(
                        knowledge_source_versions.c.organization_id == organization_id,
                        knowledge_source_versions.c.source_id == row["source_id"],
                        knowledge_source_versions.c.id != source_version_id,
                        knowledge_source_versions.c.created_at <= row["created_at"],
                    )
                    .order_by(
                        knowledge_source_versions.c.created_at,
                        knowledge_source_versions.c.id,
                    )
                ).scalars()
            )
            duplicate_url_source_ids = (
                tuple(
                    conn.execute(
                        select(knowledge_sources.c.id)
                        .where(
                            knowledge_sources.c.organization_id == organization_id,
                            knowledge_sources.c.canonical_url == row["canonical_url"],
                            knowledge_sources.c.id != row["source_id"],
                        )
                        .order_by(knowledge_sources.c.id)
                    ).scalars()
                )
                if row["canonical_url"] is not None
                else ()
            )

        artifact_resolvable = True
        try:
            if row["storage_backend"] == "local_artifact":
                if self.artifacts is None or not row["artifact_key"]:
                    artifact_resolvable = False
                    content = b""
                else:
                    content = self.artifacts.read(organization_id, str(row["artifact_key"]))
            else:
                raw = row["content_bytes"]
                if raw is None:
                    artifact_resolvable = False
                    content = b""
                else:
                    content = cast(bytes, raw)
        except (ArtifactNotFoundError, ArtifactIntegrityError):
            artifact_resolvable = False
            content = b""

        warnings_raw = row["parser_warnings"]
        warnings: tuple[str, ...] | None
        if warnings_raw is None:
            warnings = None
        else:
            try:
                decoded = json.loads(str(warnings_raw))
                warnings = tuple(str(item) for item in decoded) if isinstance(decoded, list) else ()
            except json.JSONDecodeError:
                warnings = ()

        return SourceContext(
            source_version_id=source_version_id,
            source_id=str(row["source_id"]),
            media_type=str(row["media_type"]),
            registered_sha256=str(row["content_sha256"]),
            actual_sha256=hashlib.sha256(content).hexdigest(),
            registered_size=int(row["size_bytes"]),
            actual_size=len(content),
            artifact_resolvable=artifact_resolvable,
            captured_at=(
                row["captured_at"].isoformat() if isinstance(row["captured_at"], datetime) else None
            ),
            parser_name=cast(str | None, row["parser_name"]),
            parser_version=cast(str | None, row["parser_version"]),
            parser_warnings=warnings,
            page_count=cast(int | None, row["page_count"]),
            processed_pages=cast(int | None, row["processed_pages"]),
            extraction_status=cast(str | None, row["extraction_status"]),
            passages=tuple((str(item.locator), str(item.exact_text)) for item in passage_rows),
            duplicate_version_ids=duplicate_ids,
            duplicate_url_source_ids=duplicate_url_source_ids,
            canonical_url=cast(str | None, row["canonical_url"]),
            previous_version_hashes=previous_hashes,
            requested_locator=locator,
            claimed_quote=claimed_quote,
        )

    def persist(
        self,
        report: SourceValidationReport,
        *,
        actor_id: str,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(validation_evaluations).values(
                    id=report.evaluation_id,
                    organization_id=report.organization_id,
                    actor_id=actor_id,
                    subject_kind="source_version",
                    subject_id=report.source_version_id,
                    input_sha256=report.input_sha256,
                    evaluator_build=report.evaluator_build,
                    frozen_time=report.frozen_time,
                )
            )
            conn.execute(
                insert(validation_results),
                [
                    {
                        "evaluation_id": report.evaluation_id,
                        "ordinal": index,
                        "rule_id": result.rule_id,
                        "rule_version": result.rule_version,
                        "outcome": result.outcome,
                        "reason_code": result.reason_code,
                        "payload_json": result.model_dump_json(),
                    }
                    for index, result in enumerate(report.results)
                ],
            )
            conn.execute(
                insert(validation_dependencies),
                [
                    {
                        "evaluation_id": report.evaluation_id,
                        "ordinal": index,
                        **dependency.model_dump(mode="json"),
                    }
                    for index, dependency in enumerate(report.dependencies)
                ],
            )

    @staticmethod
    def _numeric_fact(row: Any) -> NumericFact:
        item = dict(row)
        return NumericFact(
            fact_id=str(item["id"]),
            version=int(item["fact_version"]),
            metric_id=str(item["metric_id"]),
            value=item["value_exact"],
            raw_value=item["raw_value"],
            unit=item["unit"],
            currency=item["currency"],
            scale=item["scale"],
            scope=str(item["scope"]),
            program=item["program"],
            geography=item["geography"],
            population=item["population"],
            period=item["reporting_period"],
            status=str(item["status"]),
        )

    def resolve_numeric(
        self, organization_id: str, request: NumericValidationRequest
    ) -> NumericContext:
        with self.engine.connect() as conn:
            base = (
                knowledge_facts.join(pack_facts, pack_facts.c.fact_id == knowledge_facts.c.id)
                .join(
                    evidence_pack_versions,
                    evidence_pack_versions.c.id == pack_facts.c.pack_version_id,
                )
                .join(evidence_packs, evidence_packs.c.id == evidence_pack_versions.c.pack_id)
            )
            rows = (
                conn.execute(
                    select(knowledge_facts)
                    .select_from(base)
                    .where(
                        pack_facts.c.pack_version_id == request.pack_version_id,
                        pack_facts.c.allowed.is_(True),
                        knowledge_facts.c.organization_id == organization_id,
                        evidence_packs.c.organization_id == organization_id,
                    )
                )
                .mappings()
                .all()
            )
            by_id = {str(row["id"]): self._numeric_fact(row) for row in rows}
            fact = by_id.get(request.fact_id)
            if fact is None:
                raise ValidationSubjectNotFoundError
            comparable = tuple(
                candidate
                for candidate in by_id.values()
                if (
                    candidate.metric_id,
                    candidate.scope,
                    candidate.program,
                    candidate.geography,
                    candidate.population,
                    candidate.period,
                )
                == (
                    fact.metric_id,
                    fact.scope,
                    fact.program,
                    fact.geography,
                    fact.population,
                    fact.period,
                )
            )
            project_input = None
            if request.project_input_id:
                row = (
                    conn.execute(
                        select(project_numeric_inputs).where(
                            project_numeric_inputs.c.id == request.project_input_id,
                            project_numeric_inputs.c.organization_id == organization_id,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is not None:
                    project_input = (
                        str(row["id"]),
                        int(row["input_version"]),
                        str(row["status"]),
                        bool(row["is_simulated"]),
                    )
        aggregate = tuple(by_id[item] for item in request.aggregate_fact_ids if item in by_id)
        return NumericContext(
            fact=fact,
            raw_value=request.raw_value,
            locale=request.locale,
            claimed_value=request.claimed_value,
            claimed_unit=request.claimed_unit,
            claimed_currency=request.claimed_currency,
            claimed_scale=request.claimed_scale,
            expected_metric_id=request.expected_metric_id,
            claimed_scope=request.claimed_scope,
            claimed_program=request.claimed_program,
            claimed_geography=request.claimed_geography,
            claimed_population=request.claimed_population,
            claimed_period=request.claimed_reporting_period,
            rounding_places=request.rounding_places,
            line_items=tuple(request.line_items),
            declared_total=request.declared_total,
            numerator=by_id.get(request.numerator_fact_id or ""),
            denominator=by_id.get(request.denominator_fact_id or ""),
            comparable_facts=comparable,
            change_operation=request.change_operation,
            before_value=request.before_value,
            after_value=request.after_value,
            aggregate_facts=aggregate,
            disjoint_scopes=request.disjoint_scope_declaration,
            project_input=project_input,
        )

    def persist_numeric(self, report: NumericValidationReport, *, actor_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(validation_evaluations).values(
                    id=report.evaluation_id,
                    organization_id=report.organization_id,
                    actor_id=actor_id,
                    subject_kind="fact",
                    subject_id=report.fact_id,
                    input_sha256=report.input_sha256,
                    evaluator_build=report.evaluator_build,
                    frozen_time=report.frozen_time,
                )
            )
            conn.execute(
                insert(validation_results),
                [
                    {
                        "evaluation_id": report.evaluation_id,
                        "ordinal": i,
                        "rule_id": result.rule_id,
                        "rule_version": result.rule_version,
                        "outcome": result.outcome,
                        "reason_code": result.reason_code,
                        "payload_json": result.model_dump_json(),
                    }
                    for i, result in enumerate(report.results)
                ],
            )
            conn.execute(
                insert(validation_dependencies),
                [
                    {
                        "evaluation_id": report.evaluation_id,
                        "ordinal": i,
                        **dep.model_dump(mode="json"),
                    }
                    for i, dep in enumerate(report.dependencies)
                ],
            )

    def get_receipt(self, organization_id: str, evaluation_id: str) -> SourceValidationReport:
        with self.engine.connect() as conn:
            evaluation = (
                conn.execute(
                    select(validation_evaluations).where(
                        validation_evaluations.c.id == evaluation_id,
                        validation_evaluations.c.organization_id == organization_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if evaluation is None:
                raise ValidationReceiptNotFoundError
            result_rows = conn.execute(
                select(validation_results.c.payload_json)
                .where(validation_results.c.evaluation_id == evaluation_id)
                .order_by(validation_results.c.ordinal)
            ).scalars()
            dependency_rows = conn.execute(
                select(
                    validation_dependencies.c.kind,
                    validation_dependencies.c.ref_id,
                    validation_dependencies.c.version,
                    validation_dependencies.c.content_hash,
                )
                .where(validation_dependencies.c.evaluation_id == evaluation_id)
                .order_by(validation_dependencies.c.ordinal)
            ).mappings()
            return SourceValidationReport(
                evaluation_id=evaluation["id"],
                organization_id=evaluation["organization_id"],
                source_version_id=evaluation["subject_id"],
                input_sha256=evaluation["input_sha256"],
                evaluator_build=evaluation["evaluator_build"],
                frozen_time=evaluation["frozen_time"],
                results=[ValidationResult.model_validate_json(value) for value in result_rows],
                dependencies=[ValidationDependency.model_validate(row) for row in dependency_rows],
            )

    def get_numeric_receipt(
        self, organization_id: str, evaluation_id: str
    ) -> NumericValidationReport:
        with self.engine.connect() as conn:
            evaluation = (
                conn.execute(
                    select(validation_evaluations).where(
                        validation_evaluations.c.id == evaluation_id,
                        validation_evaluations.c.organization_id == organization_id,
                        validation_evaluations.c.subject_kind == "fact",
                    )
                )
                .mappings()
                .one_or_none()
            )
            if evaluation is None:
                raise ValidationReceiptNotFoundError
            result_rows = list(
                conn.execute(
                    select(validation_results.c.payload_json)
                    .where(validation_results.c.evaluation_id == evaluation_id)
                    .order_by(validation_results.c.ordinal)
                ).scalars()
            )
            dependency_rows = list(
                conn.execute(
                    select(
                        validation_dependencies.c.kind,
                        validation_dependencies.c.ref_id,
                        validation_dependencies.c.version,
                        validation_dependencies.c.content_hash,
                    )
                    .where(validation_dependencies.c.evaluation_id == evaluation_id)
                    .order_by(validation_dependencies.c.ordinal)
                ).mappings()
            )
        dependencies = [ValidationDependency.model_validate(row) for row in dependency_rows]
        fact_version = next(item for item in dependencies if item.kind == "fact_version")
        pack_version = next(item for item in dependencies if item.kind == "pack_version")
        return NumericValidationReport(
            evaluation_id=evaluation["id"],
            organization_id=evaluation["organization_id"],
            pack_version_id=pack_version.ref_id,
            fact_id=evaluation["subject_id"],
            fact_version=int(fact_version.version),
            input_sha256=evaluation["input_sha256"],
            evaluator_build=evaluation["evaluator_build"],
            frozen_time=evaluation["frozen_time"],
            results=[ValidationResult.model_validate_json(value) for value in result_rows],
            dependencies=dependencies,
        )
