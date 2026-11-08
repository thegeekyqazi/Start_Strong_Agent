"""A4 pack manifests, transactional activation and reverse invalidation."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import Engine, delete, insert, select, update

from strongstart_contracts import (
    ActivePackState,
    ChangedVersion,
    ChangeSet,
    DependencyRegistrationRequest,
    DependencyTargetState,
    InvalidationSummary,
    PackActivationReport,
    PackManifest,
    PackManifestRequest,
    ValidationDependency,
)
from strongstart_contracts.packs import DependencyTargetKind

from ...db import (
    active_pack_contexts,
    dependency_target_refs,
    dependency_targets,
    evidence_pack_versions,
    evidence_packs,
    fact_source_refs,
    invalidation_events,
    knowledge_facts,
    knowledge_source_versions,
    organizations,
    pack_change_sets,
    pack_changes,
    pack_facts,
    pack_manifest_policies,
    pack_manifest_sources,
    pack_manifests,
    pack_policies,
    validation_dependencies,
    validation_evaluations,
)


class PackNotFoundError(Exception):
    """A pack object is absent or outside the server-derived organization."""


class PackConflictError(Exception):
    """An immutable ID exists or the expected active/revision snapshot is stale."""


class PackManifestError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _manifest_hash(request: PackManifestRequest) -> str:
    return hashlib.sha256(
        _canonical_json(request.model_dump(mode="json")).encode("utf-8")
    ).hexdigest()


def _dependency_key(item: ValidationDependency) -> tuple[str, str, str]:
    return item.kind, item.ref_id, item.version


class PackService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create_manifest(
        self, organization_id: str, actor_id: str, request: PackManifestRequest
    ) -> PackManifest:
        manifest_hash = _manifest_hash(request)
        with self.engine.begin() as conn:
            existing_version = conn.execute(
                select(evidence_pack_versions.c.id).where(
                    evidence_pack_versions.c.id == request.pack_version_id
                )
            ).scalar_one_or_none()
            if existing_version is not None:
                raise PackConflictError
            duplicate_bundle = conn.execute(
                select(evidence_pack_versions.c.id)
                .select_from(
                    evidence_pack_versions.join(
                        evidence_packs,
                        evidence_pack_versions.c.pack_id == evidence_packs.c.id,
                    )
                )
                .where(
                    evidence_packs.c.organization_id == organization_id,
                    evidence_pack_versions.c.bundle_id == request.bundle_id,
                )
            ).scalar_one_or_none()
            duplicate_hash = conn.execute(
                select(pack_manifests.c.pack_version_id).where(
                    pack_manifests.c.organization_id == organization_id,
                    pack_manifests.c.manifest_sha256 == manifest_hash,
                )
            ).scalar_one_or_none()
            if duplicate_bundle is not None or duplicate_hash is not None:
                raise PackConflictError
            pack_org = conn.execute(
                select(evidence_packs.c.organization_id).where(
                    evidence_packs.c.id == request.pack_id
                )
            ).scalar_one_or_none()
            if pack_org is not None and pack_org != organization_id:
                raise PackNotFoundError

            fact_ids = [item.fact_id for item in request.facts]
            fact_rows = (
                conn.execute(
                    select(
                        knowledge_facts.c.id,
                        knowledge_facts.c.fact_version,
                        knowledge_facts.c.status,
                    ).where(
                        knowledge_facts.c.organization_id == organization_id,
                        knowledge_facts.c.id.in_(fact_ids),
                    )
                )
                .mappings()
                .all()
            )
            facts = {str(row["id"]): row for row in fact_rows}
            if len(facts) != len(fact_ids):
                raise PackManifestError("fact_not_found")
            for binding in request.facts:
                row = facts[binding.fact_id]
                if int(row["fact_version"]) != binding.fact_version:
                    raise PackManifestError("fact_version_mismatch")
                if row["status"] not in {"verified", "needs_review", "conflicting"}:
                    raise PackManifestError("fact_status_unsupported")

            source_ids = set(request.source_version_ids)
            resolved_sources = set(
                conn.execute(
                    select(knowledge_source_versions.c.id).where(
                        knowledge_source_versions.c.organization_id == organization_id,
                        knowledge_source_versions.c.id.in_(source_ids),
                    )
                ).scalars()
            )
            if resolved_sources != source_ids:
                raise PackManifestError("source_version_not_found")
            required_sources = set(
                conn.execute(
                    select(fact_source_refs.c.source_version_id).where(
                        fact_source_refs.c.fact_id.in_(fact_ids)
                    )
                ).scalars()
            )
            if not required_sources.issubset(source_ids):
                raise PackManifestError("fact_support_missing_from_manifest")

            for policy in request.policies:
                policy_row = (
                    conn.execute(
                        select(pack_policies).where(
                            pack_policies.c.organization_id == organization_id,
                            pack_policies.c.policy_id == policy.policy_id,
                            pack_policies.c.policy_version == policy.policy_version,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if policy_row is None:
                    raise PackManifestError("policy_not_found")
                if policy_row["status"] != "approved":
                    raise PackManifestError("policy_not_approved")
                if policy_row["content_sha256"] != policy.content_sha256:
                    raise PackManifestError("policy_hash_mismatch")

            if pack_org is None:
                conn.execute(
                    insert(evidence_packs).values(
                        id=request.pack_id, organization_id=organization_id
                    )
                )
            conn.execute(
                insert(evidence_pack_versions).values(
                    id=request.pack_version_id,
                    pack_id=request.pack_id,
                    bundle_id=request.bundle_id,
                    access_context=",".join(sorted(request.access_labels)),
                    coverage_notes=json.dumps(request.coverage_notes),
                )
            )
            conn.execute(
                insert(pack_manifests).values(
                    pack_version_id=request.pack_version_id,
                    organization_id=organization_id,
                    application_context=request.application_context,
                    manifest_sha256=manifest_hash,
                    manifest_json=request.model_dump_json(),
                    created_by=actor_id,
                )
            )
            conn.execute(
                insert(pack_facts),
                [
                    {
                        "pack_version_id": request.pack_version_id,
                        "fact_id": item.fact_id,
                        "allowed": True,
                    }
                    for item in request.facts
                ],
            )
            conn.execute(
                insert(pack_manifest_sources),
                [
                    {
                        "pack_version_id": request.pack_version_id,
                        "source_version_id": source_id,
                    }
                    for source_id in sorted(source_ids)
                ],
            )
            if request.policies:
                conn.execute(
                    insert(pack_manifest_policies),
                    [
                        {
                            "pack_version_id": request.pack_version_id,
                            "policy_id": item.policy_id,
                            "policy_version": item.policy_version,
                        }
                        for item in request.policies
                    ],
                )
            created_at = conn.execute(
                select(pack_manifests.c.created_at).where(
                    pack_manifests.c.pack_version_id == request.pack_version_id
                )
            ).scalar_one()
        return PackManifest(
            organization_id=organization_id,
            manifest_sha256=manifest_hash,
            created_at=created_at,
            request=request,
        )

    def get_manifest(self, organization_id: str, pack_version_id: str) -> PackManifest:
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(pack_manifests).where(
                        pack_manifests.c.organization_id == organization_id,
                        pack_manifests.c.pack_version_id == pack_version_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise PackNotFoundError
        return PackManifest(
            organization_id=organization_id,
            manifest_sha256=row["manifest_sha256"],
            created_at=row["created_at"],
            request=PackManifestRequest.model_validate_json(row["manifest_json"]),
        )

    def _validate_dependency(
        self, conn: Any, organization_id: str, dependency: ValidationDependency
    ) -> None:
        if dependency.kind == "fact_version":
            try:
                version = int(dependency.version)
            except ValueError as exc:
                raise PackManifestError("dependency_version_invalid") from exc
            found = conn.execute(
                select(knowledge_facts.c.id).where(
                    knowledge_facts.c.organization_id == organization_id,
                    knowledge_facts.c.id == dependency.ref_id,
                    knowledge_facts.c.fact_version == version,
                )
            ).scalar_one_or_none()
        elif dependency.kind == "pack_version":
            found = conn.execute(
                select(pack_manifests.c.pack_version_id).where(
                    pack_manifests.c.organization_id == organization_id,
                    pack_manifests.c.pack_version_id == dependency.ref_id,
                    pack_manifests.c.pack_version_id == dependency.version,
                )
            ).scalar_one_or_none()
        elif dependency.kind == "source_version":
            found = conn.execute(
                select(knowledge_source_versions.c.id).where(
                    knowledge_source_versions.c.organization_id == organization_id,
                    knowledge_source_versions.c.id == dependency.ref_id,
                    knowledge_source_versions.c.content_sha256 == dependency.version,
                )
            ).scalar_one_or_none()
        elif dependency.kind == "policy":
            try:
                version = int(dependency.version)
            except ValueError as exc:
                raise PackManifestError("dependency_version_invalid") from exc
            found = conn.execute(
                select(pack_policies.c.policy_id).where(
                    pack_policies.c.organization_id == organization_id,
                    pack_policies.c.policy_id == dependency.ref_id,
                    pack_policies.c.policy_version == version,
                    pack_policies.c.status == "approved",
                )
            ).scalar_one_or_none()
        else:
            return
        if found is None:
            raise PackManifestError("dependency_not_authorized")

    def register_target(
        self,
        organization_id: str,
        request: DependencyRegistrationRequest,
    ) -> DependencyTargetState:
        dependencies = sorted(request.dependencies, key=_dependency_key)
        if len({_dependency_key(item) for item in dependencies}) != len(dependencies):
            raise PackManifestError("duplicate_dependency")
        with self.engine.begin() as conn:
            for dependency in dependencies:
                self._validate_dependency(conn, organization_id, dependency)
            current = (
                conn.execute(
                    select(dependency_targets)
                    .where(
                        dependency_targets.c.organization_id == organization_id,
                        dependency_targets.c.target_kind == request.target_kind,
                        dependency_targets.c.target_id == request.target_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            actual_revision = 0 if current is None else int(current["revision"])
            if actual_revision != request.expected_revision:
                raise PackConflictError
            revision = actual_revision + 1
            if current is None:
                conn.execute(
                    insert(dependency_targets).values(
                        organization_id=organization_id,
                        target_kind=request.target_kind,
                        target_id=request.target_id,
                        revision=revision,
                        state="current",
                    )
                )
            else:
                conn.execute(
                    update(dependency_targets)
                    .where(
                        dependency_targets.c.organization_id == organization_id,
                        dependency_targets.c.target_kind == request.target_kind,
                        dependency_targets.c.target_id == request.target_id,
                    )
                    .values(
                        revision=revision,
                        state="current",
                        stale_change_set_id=None,
                        updated_at=datetime.now().astimezone(),
                    )
                )
                conn.execute(
                    delete(dependency_target_refs).where(
                        dependency_target_refs.c.organization_id == organization_id,
                        dependency_target_refs.c.target_kind == request.target_kind,
                        dependency_target_refs.c.target_id == request.target_id,
                    )
                )
            conn.execute(
                insert(dependency_target_refs),
                [
                    {
                        "organization_id": organization_id,
                        "target_kind": request.target_kind,
                        "target_id": request.target_id,
                        "ordinal": index,
                        **dependency.model_dump(mode="json"),
                    }
                    for index, dependency in enumerate(dependencies)
                ],
            )
        return DependencyTargetState(
            organization_id=organization_id,
            target_kind=request.target_kind,
            target_id=request.target_id,
            revision=revision,
            state="current",
            dependencies=dependencies,
        )

    def get_target(
        self, organization_id: str, target_kind: str, target_id: str
    ) -> DependencyTargetState:
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(dependency_targets).where(
                        dependency_targets.c.organization_id == organization_id,
                        dependency_targets.c.target_kind == target_kind,
                        dependency_targets.c.target_id == target_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise PackNotFoundError
            refs = (
                conn.execute(
                    select(
                        dependency_target_refs.c.kind,
                        dependency_target_refs.c.ref_id,
                        dependency_target_refs.c.version,
                        dependency_target_refs.c.content_hash,
                    )
                    .where(
                        dependency_target_refs.c.organization_id == organization_id,
                        dependency_target_refs.c.target_kind == target_kind,
                        dependency_target_refs.c.target_id == target_id,
                    )
                    .order_by(dependency_target_refs.c.ordinal)
                )
                .mappings()
                .all()
            )
            if not refs and target_kind == "validation":
                refs = (
                    conn.execute(
                        select(
                            validation_dependencies.c.kind,
                            validation_dependencies.c.ref_id,
                            validation_dependencies.c.version,
                            validation_dependencies.c.content_hash,
                        )
                        .where(validation_dependencies.c.evaluation_id == target_id)
                        .order_by(validation_dependencies.c.ordinal)
                    )
                    .mappings()
                    .all()
                )
        return DependencyTargetState(
            organization_id=organization_id,
            target_kind=row["target_kind"],
            target_id=row["target_id"],
            revision=row["revision"],
            state=row["state"],
            stale_change_set_id=row["stale_change_set_id"],
            dependencies=[ValidationDependency.model_validate(item) for item in refs],
        )

    def active_state(self, organization_id: str, context: str) -> ActivePackState:
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(active_pack_contexts).where(
                        active_pack_contexts.c.organization_id == organization_id,
                        active_pack_contexts.c.application_context == context,
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise PackNotFoundError
        return ActivePackState(
            organization_id=organization_id,
            application_context=context,
            pack_version_id=row["pack_version_id"],
            revision=row["revision"],
        )

    def require_active(
        self, organization_id: str, context: str, pack_version_id: str
    ) -> ActivePackState:
        state = self.active_state(organization_id, context)
        if state.pack_version_id != pack_version_id:
            raise PackConflictError
        return state

    @staticmethod
    def _load_members(conn: Any, pack_version_id: str) -> dict[str, dict[str, str]]:
        facts = {
            str(row.id): str(row.fact_version)
            for row in conn.execute(
                select(knowledge_facts.c.id, knowledge_facts.c.fact_version)
                .select_from(pack_facts.join(knowledge_facts))
                .where(pack_facts.c.pack_version_id == pack_version_id)
            )
        }
        sources = {
            str(row.id): str(row.content_sha256)
            for row in conn.execute(
                select(knowledge_source_versions.c.id, knowledge_source_versions.c.content_sha256)
                .select_from(
                    pack_manifest_sources.join(
                        knowledge_source_versions,
                        pack_manifest_sources.c.source_version_id == knowledge_source_versions.c.id,
                    )
                )
                .where(pack_manifest_sources.c.pack_version_id == pack_version_id)
            )
        }
        policies = {
            str(row.policy_id): str(row.policy_version)
            for row in conn.execute(
                select(
                    pack_manifest_policies.c.policy_id,
                    pack_manifest_policies.c.policy_version,
                ).where(pack_manifest_policies.c.pack_version_id == pack_version_id)
            )
        }
        return {"fact_version": facts, "source_version": sources, "policy": policies}

    @staticmethod
    def _diff(
        previous_pack: str | None,
        new_pack: str,
        old: dict[str, dict[str, str]],
        new: dict[str, dict[str, str]],
    ) -> tuple[list[ChangedVersion], set[tuple[str, str, str]]]:
        changes = [
            ChangedVersion(
                kind="pack",
                ref_id=previous_pack or new_pack,
                previous_version=previous_pack,
                new_version=new_pack,
            )
        ]
        changed_keys: set[tuple[str, str, str]] = set()
        if previous_pack is not None:
            changed_keys.add(("pack_version", previous_pack, previous_pack))
        report_kind = {"fact_version": "fact", "source_version": "source", "policy": "policy"}
        for kind in ("fact_version", "source_version", "policy"):
            for ref_id in sorted(set(old[kind]) | set(new[kind])):
                before, after = old[kind].get(ref_id), new[kind].get(ref_id)
                if before == after:
                    continue
                changes.append(
                    ChangedVersion(
                        kind=cast(Any, report_kind[kind]),
                        ref_id=ref_id,
                        previous_version=before,
                        new_version=after or "removed",
                    )
                )
                if before is not None:
                    changed_keys.add((kind, ref_id, before))
        return changes, changed_keys

    def activate(
        self,
        organization_id: str,
        actor_id: str,
        context: str,
        new_pack_version_id: str,
        expected_active_pack_version_id: str | None,
    ) -> PackActivationReport:
        with self.engine.begin() as conn:
            # A stable parent-row lock serializes the first activation as well as
            # replacements; locking a missing context row would not do that.
            organization = conn.execute(
                select(organizations.c.id)
                .where(organizations.c.id == organization_id)
                .with_for_update()
            ).scalar_one_or_none()
            if organization is None:
                raise PackNotFoundError
            manifest = (
                conn.execute(
                    select(pack_manifests).where(
                        pack_manifests.c.organization_id == organization_id,
                        pack_manifests.c.application_context == context,
                        pack_manifests.c.pack_version_id == new_pack_version_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if manifest is None:
                raise PackNotFoundError
            active = (
                conn.execute(
                    select(active_pack_contexts)
                    .where(
                        active_pack_contexts.c.organization_id == organization_id,
                        active_pack_contexts.c.application_context == context,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            previous = None if active is None else str(active["pack_version_id"])
            if previous != expected_active_pack_version_id:
                raise PackConflictError
            if previous == new_pack_version_id:
                assert active is not None
                state = ActivePackState(
                    organization_id=organization_id,
                    application_context=context,
                    pack_version_id=new_pack_version_id,
                    revision=int(active["revision"]),
                )
                return PackActivationReport(
                    active=state,
                    previous_pack_version_id=previous,
                    change_set=None,
                    invalidated=[],
                    idempotent=True,
                )

            old_members = (
                self._load_members(conn, previous)
                if previous is not None
                else {"fact_version": {}, "source_version": {}, "policy": {}}
            )
            new_members = self._load_members(conn, new_pack_version_id)
            changes, changed_keys = self._diff(
                previous, new_pack_version_id, old_members, new_members
            )
            change_set_id = f"chg-{uuid4()}"
            conn.execute(
                insert(pack_change_sets).values(
                    id=change_set_id,
                    organization_id=organization_id,
                    application_context=context,
                    previous_pack_version_id=previous,
                    new_pack_version_id=new_pack_version_id,
                    actor_id=actor_id,
                )
            )
            conn.execute(
                insert(pack_changes),
                [
                    {
                        "change_set_id": change_set_id,
                        "ordinal": index,
                        **item.model_dump(mode="json"),
                    }
                    for index, item in enumerate(changes)
                ],
            )

            matches: dict[tuple[str, str], list[ValidationDependency]] = defaultdict(list)
            registered = conn.execute(
                select(dependency_target_refs).where(
                    dependency_target_refs.c.organization_id == organization_id
                )
            ).mappings()
            for row in registered:
                key = (str(row["kind"]), str(row["ref_id"]), str(row["version"]))
                if key in changed_keys:
                    matches[(str(row["target_kind"]), str(row["target_id"]))].append(
                        ValidationDependency.model_validate(
                            {
                                "kind": row["kind"],
                                "ref_id": row["ref_id"],
                                "version": row["version"],
                                "content_hash": row["content_hash"],
                            }
                        )
                    )
            evaluation_rows = conn.execute(
                select(
                    validation_evaluations.c.id,
                    validation_dependencies.c.kind,
                    validation_dependencies.c.ref_id,
                    validation_dependencies.c.version,
                    validation_dependencies.c.content_hash,
                )
                .select_from(
                    validation_evaluations.join(
                        validation_dependencies,
                        validation_dependencies.c.evaluation_id == validation_evaluations.c.id,
                    )
                )
                .where(validation_evaluations.c.organization_id == organization_id)
            ).mappings()
            for row in evaluation_rows:
                key = (str(row["kind"]), str(row["ref_id"]), str(row["version"]))
                if key in changed_keys:
                    matches[("validation", str(row["id"]))].append(
                        ValidationDependency.model_validate(
                            {
                                "kind": row["kind"],
                                "ref_id": row["ref_id"],
                                "version": row["version"],
                                "content_hash": row["content_hash"],
                            }
                        )
                    )

            summaries: list[InvalidationSummary] = []
            for (target_kind, target_id), matched in sorted(matches.items()):
                matched = sorted(
                    {_dependency_key(item): item for item in matched}.values(),
                    key=_dependency_key,
                )
                target = (
                    conn.execute(
                        select(dependency_targets).where(
                            dependency_targets.c.organization_id == organization_id,
                            dependency_targets.c.target_kind == target_kind,
                            dependency_targets.c.target_id == target_id,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if target is None:
                    conn.execute(
                        insert(dependency_targets).values(
                            organization_id=organization_id,
                            target_kind=target_kind,
                            target_id=target_id,
                            revision=1,
                            state="stale",
                            stale_change_set_id=change_set_id,
                        )
                    )
                else:
                    conn.execute(
                        update(dependency_targets)
                        .where(
                            dependency_targets.c.organization_id == organization_id,
                            dependency_targets.c.target_kind == target_kind,
                            dependency_targets.c.target_id == target_id,
                        )
                        .values(state="stale", stale_change_set_id=change_set_id)
                    )
                conn.execute(
                    insert(invalidation_events).values(
                        change_set_id=change_set_id,
                        target_kind=target_kind,
                        target_id=target_id,
                        matched_dependencies_json=json.dumps(
                            [item.model_dump(mode="json") for item in matched]
                        ),
                    )
                )
                summaries.append(
                    InvalidationSummary(
                        target_kind=cast(DependencyTargetKind, target_kind),
                        target_id=target_id,
                        matched_dependencies=matched,
                    )
                )

            revision = 1 if active is None else int(active["revision"]) + 1
            values = {
                "pack_version_id": new_pack_version_id,
                "revision": revision,
                "updated_by": actor_id,
                "updated_at": datetime.now().astimezone(),
            }
            if active is None:
                conn.execute(
                    insert(active_pack_contexts).values(
                        organization_id=organization_id,
                        application_context=context,
                        **values,
                    )
                )
            else:
                conn.execute(
                    update(active_pack_contexts)
                    .where(
                        active_pack_contexts.c.organization_id == organization_id,
                        active_pack_contexts.c.application_context == context,
                    )
                    .values(**values)
                )
        state = ActivePackState(
            organization_id=organization_id,
            application_context=context,
            pack_version_id=new_pack_version_id,
            revision=revision,
        )
        change_set = ChangeSet(
            change_set_id=change_set_id,
            changes=changes,
            affected_refs=[item.target_id for item in summaries],
        )
        return PackActivationReport(
            active=state,
            previous_pack_version_id=previous,
            change_set=change_set,
            invalidated=summaries,
            idempotent=False,
        )
