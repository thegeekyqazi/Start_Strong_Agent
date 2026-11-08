"""Idempotent demo seed: upserts synthetic fixture organizations. Never targets production."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import func

from strongstart_contracts import load_fixture_bundle

from .config import get_settings
from .db import (
    bootstrap_metadata,
    evidence_pack_versions,
    evidence_packs,
    fact_source_refs,
    get_engine,
    knowledge_facts,
    knowledge_passages,
    knowledge_source_versions,
    knowledge_sources,
    organizations,
    pack_facts,
)

DEFAULT_BUNDLE = Path("tests/fixtures/demo/demo-bundle-v1.json")
DEMO_SOURCE_BYTES = (
    b"SIMULATED FIXTURE - not partner data. Children served: 120; "
    b"population: children enrolled; reporting period: 2025-09/2026-06.\n"
)


def seed_demo(engine: Engine, bundle_path: Path) -> int:
    bundle = load_fixture_bundle(bundle_path)
    if not bundle.provenance.is_simulated:
        raise ValueError("refusing to seed a bundle that is not labelled simulated")
    with engine.begin() as conn:
        for org in bundle.organizations:
            stmt = insert(organizations).values(
                id=org.organization_id,
                display_name=org.display_name,
                provenance_class=org.provenance.provenance_class.value,
                is_simulated=org.provenance.is_simulated,
            )
            conn.execute(
                stmt.on_conflict_do_update(
                    index_elements=[organizations.c.id],
                    set_={
                        "display_name": stmt.excluded.display_name,
                        "provenance_class": stmt.excluded.provenance_class,
                        "is_simulated": stmt.excluded.is_simulated,
                        "updated_at": func.now(),
                    },
                )
            )
        evidence = bundle.evidence_bundles[0]
        fact = evidence.facts[0]
        original_ref = fact.supporting_refs[0]
        source_hash = hashlib.sha256(DEMO_SOURCE_BYTES).hexdigest()
        conn.execute(
            insert(knowledge_sources)
            .values(
                id=original_ref.source_id,
                organization_id=evidence.organization_id,
                title="Synthetic enrollment metric fixture",
                provenance_class="simulated",
                is_simulated=True,
                provenance_note="Synthetic A1 fixture; not partner data.",
            )
            .on_conflict_do_nothing(index_elements=[knowledge_sources.c.id])
        )
        conn.execute(
            insert(knowledge_source_versions)
            .values(
                id=original_ref.source_version_id,
                source_id=original_ref.source_id,
                organization_id=evidence.organization_id,
                media_type="text/plain",
                content_bytes=DEMO_SOURCE_BYTES,
                content_sha256=source_hash,
                size_bytes=len(DEMO_SOURCE_BYTES),
                publication_status="known",
                publication_date=original_ref.publication_date.value,
                reporting_period=fact.reporting_period,
                verification_status="verified",
            )
            .on_conflict_do_nothing(index_elements=[knowledge_source_versions.c.id])
        )
        conn.execute(
            insert(knowledge_passages)
            .values(
                id="demo-passage-children-served-v1",
                source_version_id=original_ref.source_version_id,
                locator="line:1",
                exact_text=DEMO_SOURCE_BYTES.decode("utf-8").strip(),
            )
            .on_conflict_do_nothing(index_elements=[knowledge_passages.c.id])
        )
        conn.execute(
            insert(evidence_packs)
            .values(id=evidence.pack_id, organization_id=evidence.organization_id)
            .on_conflict_do_nothing(index_elements=[evidence_packs.c.id])
        )
        conn.execute(
            insert(evidence_pack_versions)
            .values(
                id=evidence.pack_version_id,
                pack_id=evidence.pack_id,
                bundle_id=evidence.bundle_id,
                access_context=evidence.access_context,
                coverage_notes=json.dumps(evidence.coverage_notes),
            )
            .on_conflict_do_nothing(index_elements=[evidence_pack_versions.c.id])
        )
        conn.execute(
            insert(knowledge_facts)
            .values(
                id=fact.fact_id,
                organization_id=evidence.organization_id,
                metric_id=fact.metric_id,
                value_exact=fact.value,
                raw_value=fact.raw_value,
                unit=fact.unit,
                scope=fact.scope,
                population=fact.population,
                reporting_period=fact.reporting_period,
                status=fact.status,
                provenance_class=fact.provenance.provenance_class.value,
                is_simulated=fact.provenance.is_simulated,
                provenance_note=fact.provenance.note,
            )
            .on_conflict_do_nothing(index_elements=[knowledge_facts.c.id])
        )
        conn.execute(
            insert(fact_source_refs)
            .values(
                fact_id=fact.fact_id,
                source_version_id=original_ref.source_version_id,
                locator="line:1",
            )
            .on_conflict_do_nothing()
        )
        conn.execute(
            insert(pack_facts)
            .values(pack_version_id=evidence.pack_version_id, fact_id=fact.fact_id, allowed=True)
            .on_conflict_do_nothing()
        )
        meta = insert(bootstrap_metadata).values(
            key="demo_seed_bundle",
            value=f"{bundle.fixture_bundle_id}@{bundle.fixture_version}",
        )
        conn.execute(
            meta.on_conflict_do_update(
                index_elements=[bootstrap_metadata.c.key],
                set_={"value": meta.excluded.value, "updated_at": func.now()},
            )
        )
    return len(bundle.organizations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed synthetic demo metadata (idempotent).")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    args = parser.parse_args(argv)
    settings = get_settings()
    if settings.environment == "production":
        print("refusing to seed demo data in production", file=sys.stderr)
        return 1
    if not settings.database_url:
        print("STRONGSTART_DATABASE_URL is not set", file=sys.stderr)
        return 1
    count = seed_demo(get_engine(settings.database_url), args.bundle)
    print(f"seeded {count} synthetic organization(s) from {args.bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
