"""PostgreSQL knowledge reader for A1-KNOW-001.

All lookups start with the server-derived organization. Exact source bytes are
hash-checked before any metadata, passages or dependent facts are returned.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import Engine, select

from strongstart_contracts import (
    DateKnowledge,
    EvidenceBundle,
    Fact,
    KnowledgePassage,
    KnowledgeSnapshot,
    KnowledgeSourceVersion,
    Provenance,
    SourceReference,
)

from ...db import (
    evidence_pack_versions,
    evidence_packs,
    fact_source_refs,
    knowledge_facts,
    knowledge_passages,
    knowledge_source_versions,
    knowledge_sources,
    pack_facts,
)
from .artifacts import ArtifactIntegrityError, ArtifactNotFoundError, ArtifactStore


class KnowledgeNotFoundError(Exception):
    """A record is absent or outside the caller's organization."""


class KnowledgeIntegrityError(Exception):
    """Stored bytes do not match their immutable version metadata."""


class PostgresKnowledgeRepository:
    is_fixture = False

    def __init__(self, engine: Engine, artifacts: ArtifactStore | None = None) -> None:
        self.engine = engine
        self.artifacts = artifacts

    def _verify(self, row: dict[str, object]) -> None:
        if row.get("storage_backend") == "local_artifact":
            if self.artifacts is None or not row.get("artifact_key"):
                raise KnowledgeIntegrityError("source artifact storage unavailable")
            try:
                content = self.artifacts.read(str(row["organization_id"]), str(row["artifact_key"]))
            except (ArtifactNotFoundError, ArtifactIntegrityError):
                raise KnowledgeIntegrityError("source version integrity failure") from None
        else:
            content = cast(bytes, row["content_bytes"])
        actual = hashlib.sha256(content).hexdigest()
        if actual != row["content_sha256"] or len(content) != row["size_bytes"]:
            raise KnowledgeIntegrityError("source version integrity failure")

    @staticmethod
    def _source_reference(row: dict[str, object], locator: str | None) -> SourceReference:
        published = row["publication_date"]
        return SourceReference(
            source_id=str(row["source_id"]),
            source_version_id=str(row["source_version_id"]),
            locator=locator,
            provenance=Provenance(
                provenance_class=str(row["source_provenance_class"]),
                is_simulated=bool(row["source_is_simulated"]),
                note=row["source_provenance_note"],
            ),
            captured_at=row["captured_at"],
            publication_date=DateKnowledge(
                status=str(row["publication_status"]),
                value=published.date() if isinstance(published, datetime) else published,
            ),
            reporting_period=row["source_reporting_period"],
            content_hash=str(row["content_sha256"]),
            verification_status=str(row["verification_status"]),
        )

    @staticmethod
    def _source_query(organization_id: str):  # type: ignore[no-untyped-def]
        return (
            select(
                knowledge_sources.c.id.label("source_id"),
                knowledge_sources.c.title,
                knowledge_sources.c.provenance_class.label("source_provenance_class"),
                knowledge_sources.c.is_simulated.label("source_is_simulated"),
                knowledge_sources.c.provenance_note.label("source_provenance_note"),
                knowledge_source_versions.c.id.label("source_version_id"),
                knowledge_source_versions.c.media_type,
                knowledge_source_versions.c.content_bytes,
                knowledge_source_versions.c.storage_backend,
                knowledge_source_versions.c.artifact_key,
                knowledge_source_versions.c.organization_id,
                knowledge_source_versions.c.content_sha256,
                knowledge_source_versions.c.size_bytes,
                knowledge_source_versions.c.captured_at,
                knowledge_source_versions.c.publication_status,
                knowledge_source_versions.c.publication_date,
                knowledge_source_versions.c.reporting_period.label("source_reporting_period"),
                knowledge_source_versions.c.verification_status,
            )
            .select_from(
                knowledge_source_versions.join(
                    knowledge_sources,
                    knowledge_source_versions.c.source_id == knowledge_sources.c.id,
                )
            )
            .where(
                knowledge_source_versions.c.organization_id == organization_id,
                knowledge_sources.c.organization_id == organization_id,
            )
        )

    def get_bundle(self, organization_id: str, pack_version_id: str) -> EvidenceBundle:
        with self.engine.connect() as conn:
            pack = (
                conn.execute(
                    select(
                        evidence_pack_versions.c.id,
                        evidence_pack_versions.c.pack_id,
                        evidence_pack_versions.c.bundle_id,
                        evidence_pack_versions.c.access_context,
                        evidence_pack_versions.c.coverage_notes,
                    )
                    .select_from(
                        evidence_pack_versions.join(
                            evidence_packs, evidence_pack_versions.c.pack_id == evidence_packs.c.id
                        )
                    )
                    .where(
                        evidence_pack_versions.c.id == pack_version_id,
                        evidence_packs.c.organization_id == organization_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if pack is None:
                raise KnowledgeNotFoundError

            rows = (
                conn.execute(
                    select(
                        knowledge_facts,
                        fact_source_refs.c.locator,
                        knowledge_sources.c.id.label("source_id"),
                        knowledge_sources.c.provenance_class.label("source_provenance_class"),
                        knowledge_sources.c.is_simulated.label("source_is_simulated"),
                        knowledge_sources.c.provenance_note.label("source_provenance_note"),
                        knowledge_source_versions.c.id.label("source_version_id"),
                        knowledge_source_versions.c.content_bytes,
                        knowledge_source_versions.c.storage_backend,
                        knowledge_source_versions.c.artifact_key,
                        knowledge_source_versions.c.organization_id,
                        knowledge_source_versions.c.content_sha256,
                        knowledge_source_versions.c.size_bytes,
                        knowledge_source_versions.c.captured_at,
                        knowledge_source_versions.c.publication_status,
                        knowledge_source_versions.c.publication_date,
                        knowledge_source_versions.c.reporting_period.label(
                            "source_reporting_period"
                        ),
                        knowledge_source_versions.c.verification_status,
                    )
                    .select_from(
                        pack_facts.join(
                            knowledge_facts, pack_facts.c.fact_id == knowledge_facts.c.id
                        )
                        .join(fact_source_refs, fact_source_refs.c.fact_id == knowledge_facts.c.id)
                        .join(
                            knowledge_source_versions,
                            fact_source_refs.c.source_version_id == knowledge_source_versions.c.id,
                        )
                        .join(
                            knowledge_sources,
                            knowledge_source_versions.c.source_id == knowledge_sources.c.id,
                        )
                    )
                    .where(
                        pack_facts.c.pack_version_id == pack_version_id,
                        pack_facts.c.allowed.is_(True),
                        knowledge_facts.c.organization_id == organization_id,
                        knowledge_source_versions.c.organization_id == organization_id,
                        knowledge_sources.c.organization_id == organization_id,
                    )
                    .order_by(knowledge_facts.c.id)
                )
                .mappings()
                .all()
            )

        rows_by_fact: dict[str, list[dict[str, object]]] = {}
        for row_obj in rows:
            row = dict(row_obj)
            self._verify(row)
            rows_by_fact.setdefault(str(row["id"]), []).append(row)

        facts: list[Fact] = []
        for fact_id, fact_rows in rows_by_fact.items():
            row = fact_rows[0]
            facts.append(
                Fact(
                    fact_id=fact_id,
                    metric_id=row["metric_id"],
                    value=row["value_exact"],
                    raw_value=row["raw_value"],
                    unit=row["unit"],
                    scope=row["scope"],
                    population=row["population"],
                    reporting_period=row["reporting_period"],
                    status=row["status"],
                    supporting_refs=[
                        self._source_reference(ref_row, str(ref_row["locator"]))
                        for ref_row in fact_rows
                    ],
                    provenance=Provenance(
                        provenance_class=row["provenance_class"],
                        is_simulated=row["is_simulated"],
                        note=row["provenance_note"],
                    ),
                )
            )
        return EvidenceBundle(
            bundle_id=pack["bundle_id"],
            organization_id=organization_id,
            pack_id=pack["pack_id"],
            pack_version_id=pack["id"],
            access_context=pack["access_context"],
            facts=facts,
            allowed_fact_ids=[fact.fact_id for fact in facts],
            coverage_notes=json.loads(pack["coverage_notes"]),
        )

    def get_snapshot(self, organization_id: str, *, is_fixture: bool) -> KnowledgeSnapshot:
        with self.engine.connect() as conn:
            source_rows = [
                dict(row) for row in conn.execute(self._source_query(organization_id)).mappings()
            ]
            passage_rows = (
                conn.execute(
                    select(
                        knowledge_passages.c.id,
                        knowledge_passages.c.source_version_id,
                        knowledge_passages.c.locator,
                        knowledge_passages.c.exact_text,
                        knowledge_source_versions.c.source_id,
                    )
                    .select_from(
                        knowledge_passages.join(
                            knowledge_source_versions,
                            knowledge_passages.c.source_version_id
                            == knowledge_source_versions.c.id,
                        )
                    )
                    .where(knowledge_source_versions.c.organization_id == organization_id)
                    .order_by(knowledge_passages.c.id)
                )
                .mappings()
                .all()
            )
            pack_ids = (
                conn.execute(
                    select(evidence_pack_versions.c.id)
                    .select_from(
                        evidence_pack_versions.join(
                            evidence_packs, evidence_pack_versions.c.pack_id == evidence_packs.c.id
                        )
                    )
                    .where(evidence_packs.c.organization_id == organization_id)
                    .order_by(evidence_pack_versions.c.id)
                )
                .scalars()
                .all()
            )

        source_versions: list[KnowledgeSourceVersion] = []
        for row in source_rows:
            self._verify(row)
            source_versions.append(
                KnowledgeSourceVersion(
                    title=row["title"],
                    media_type=row["media_type"],
                    size_bytes=row["size_bytes"],
                    source_reference=self._source_reference(row, None),
                )
            )
        passages = [
            KnowledgePassage(
                passage_id=row["id"],
                source_id=row["source_id"],
                source_version_id=row["source_version_id"],
                locator=row["locator"],
                exact_text=row["exact_text"],
            )
            for row in passage_rows
        ]
        return KnowledgeSnapshot(
            organization_id=organization_id,
            generated_at=datetime.now(UTC),
            source_versions=source_versions,
            passages=passages,
            evidence_bundles=[self.get_bundle(organization_id, pack_id) for pack_id in pack_ids],
            is_fixture=is_fixture,
        )
