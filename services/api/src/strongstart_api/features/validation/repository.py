"""Authorized source-context resolver and immutable A3 receipt repository."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import cast

from sqlalchemy import Engine, insert, select

from strongstart_contracts import (
    SourceValidationReport,
    ValidationDependency,
    ValidationResult,
)

from ...db import (
    knowledge_passages,
    knowledge_source_versions,
    knowledge_sources,
    validation_dependencies,
    validation_evaluations,
    validation_results,
)
from ..knowledge.artifacts import ArtifactIntegrityError, ArtifactNotFoundError, ArtifactStore
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
