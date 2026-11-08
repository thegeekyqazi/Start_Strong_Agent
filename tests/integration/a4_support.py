"""Real migrated PostgreSQL fixtures; only owned synthetic rows are removed."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, insert, select

from strongstart_api.config import Settings
from strongstart_api.db import (
    active_pack_contexts,
    dependency_target_refs,
    dependency_targets,
    evidence_pack_versions,
    evidence_packs,
    fact_source_refs,
    get_engine,
    invalidation_events,
    knowledge_facts,
    pack_change_sets,
    pack_changes,
    pack_facts,
    pack_manifest_policies,
    pack_manifest_sources,
    pack_manifests,
    pack_policies,
)
from strongstart_api.features.knowledge.packs import PackService
from strongstart_api.features.knowledge.public import KnowledgeCurrentness
from strongstart_api.features.knowledge.repository import PostgresKnowledgeRepository
from strongstart_api.seed import seed_demo
from strongstart_contracts import PackManifestRequest
from strongstart_contracts.answers import DependencyRef
from tests.conftest import BUNDLE_PATH, REPO_ROOT


@dataclass
class Managed:
    url: str
    prefix: str
    service: PackService
    facade: KnowledgeCurrentness
    manifests: list[PackManifestRequest]

    @property
    def context(self):
        return self.manifests[0].application_context

    def binding(self, fact_index=0, include_policy=False):
        bundle = self.facade.resolve_active("demo-org", self.context)
        from strongstart_api.features.applications.snapshot import fact_digest

        fact = bundle.facts[fact_index]
        refs = [
            DependencyRef(kind="pack", ref_id=bundle.pack_id, version=bundle.pack_version_id),
            DependencyRef(
                kind="fact",
                ref_id=fact.fact_id,
                version=f"{bundle.pack_version_id}:{fact_digest(fact)[:16]}",
            ),
            DependencyRef(kind="question", ref_id="q-test", version="1"),
            DependencyRef(kind="rule_set", ref_id="c-rules", version="1"),
        ]
        if include_policy:
            refs.append(DependencyRef(kind="policy", ref_id=self.prefix + "policy", version="1"))
        return self.facade.project("demo-org", self.context, bundle, refs), refs

    def replace(self, index=1):
        current = self.service.active_state("demo-org", self.context)
        return self.service.activate(
            "demo-org",
            "fixture-staff",
            self.context,
            self.manifests[index].pack_version_id,
            current.pack_version_id,
        )


@pytest.fixture
def managed():
    url = Settings().database_url
    if not url:
        pytest.fail("real PostgreSQL required: set STRONGSTART_DATABASE_URL")
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.attributes["database_url"] = url
    command.upgrade(cfg, "head")
    engine = get_engine(url)
    seed_demo(engine, BUNDLE_PATH)
    prefix = "int-" + secrets.token_hex(6) + "-"
    fact_ids = [prefix + f"fact-{i}" for i in range(3)]
    context = prefix + "context"
    service = PackService(engine)
    facade = KnowledgeCurrentness(service, PostgresKnowledgeRepository(engine))
    manifests = []
    try:
        with engine.begin() as conn:
            for i, fact_id in enumerate(fact_ids):
                conn.execute(
                    insert(knowledge_facts).values(
                        id=fact_id,
                        organization_id="demo-org",
                        fact_version=i + 1,
                        metric_id="children-served",
                        value_exact=str(120 + i),
                        raw_value=str(120 + i),
                        unit="children",
                        scope="Demo Org",
                        population="children",
                        reporting_period="2026",
                        status="verified",
                        provenance_class="simulated",
                        is_simulated=True,
                    )
                )
                conn.execute(
                    insert(fact_source_refs).values(
                        fact_id=fact_id,
                        source_version_id="demo-synthetic-metrics-v1",
                        locator="line:1",
                    )
                )
            for version in (1, 2):
                text = f"Synthetic approved policy {version}"
                conn.execute(
                    insert(pack_policies).values(
                        policy_id=prefix + "policy",
                        policy_version=version,
                        organization_id="demo-org",
                        content=text,
                        content_sha256=hashlib.sha256(text.encode()).hexdigest(),
                        status="approved",
                    )
                )
        # v1 -> fact-only replacement; v1 -> policy-only replacement; v1 -> same content/new ID.
        for i, facts, policy in [(0, [0, 1], 1), (1, [1, 2], 1), (2, [0, 1], 2), (3, [0, 1], 1)]:
            request = PackManifestRequest(
                pack_id=prefix + "pack",
                pack_version_id=prefix + f"v{i}",
                bundle_id=prefix + f"bundle-{i}",
                application_context=context,
                mapping_version="pack-mapping-v1",
                parser_version="int-test/1",
                locale="en-CA",
                access_labels=["fixture-staff"],
                facts=[{"fact_id": fact_ids[j], "fact_version": j + 1} for j in facts],
                source_version_ids=["demo-synthetic-metrics-v1"],
                policies=[
                    {
                        "policy_id": prefix + "policy",
                        "policy_version": policy,
                        "content_sha256": hashlib.sha256(
                            f"Synthetic approved policy {policy}".encode()
                        ).hexdigest(),
                    }
                ],
                provenance_class="simulated",
                is_simulated=True,
            )
            service.create_manifest("demo-org", "fixture-staff", request)
            manifests.append(request)
        service.activate("demo-org", "fixture-staff", context, manifests[0].pack_version_id, None)
        yield Managed(url, prefix, service, facade, manifests)
    finally:
        with engine.begin() as conn:
            changes = select(pack_change_sets.c.id).where(
                pack_change_sets.c.application_context.like(prefix + "%")
            )
            conn.execute(
                delete(invalidation_events).where(invalidation_events.c.change_set_id.in_(changes))
            )
            conn.execute(delete(pack_changes).where(pack_changes.c.change_set_id.in_(changes)))
            conn.execute(
                delete(pack_change_sets).where(
                    pack_change_sets.c.application_context.like(prefix + "%")
                )
            )
            for table in (dependency_target_refs, dependency_targets):
                conn.execute(delete(table).where(table.c.target_id.like(prefix + "%")))
            conn.execute(
                delete(active_pack_contexts).where(
                    active_pack_contexts.c.application_context.like(prefix + "%")
                )
            )
            for table in (
                pack_manifest_policies,
                pack_manifest_sources,
                pack_facts,
                pack_manifests,
            ):
                conn.execute(delete(table).where(table.c.pack_version_id.like(prefix + "%")))
            conn.execute(
                delete(evidence_pack_versions).where(evidence_pack_versions.c.id.like(prefix + "%"))
            )
            conn.execute(delete(evidence_packs).where(evidence_packs.c.id.like(prefix + "%")))
            conn.execute(
                delete(pack_policies).where(pack_policies.c.policy_id == prefix + "policy")
            )
            conn.execute(delete(fact_source_refs).where(fact_source_refs.c.fact_id.in_(fact_ids)))
            conn.execute(delete(knowledge_facts).where(knowledge_facts.c.id.in_(fact_ids)))
