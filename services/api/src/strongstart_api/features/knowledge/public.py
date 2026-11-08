"""Supported in-process A4 boundary; no consumer reads knowledge SQL tables."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import Depends

from strongstart_contracts import (
    DependencyRegistrationRequest,
    EvidenceBundle,
    ValidationDependency,
)
from strongstart_contracts.answers import DependencyRef
from strongstart_contracts.automation_prefill import DependencyCurrentness
from strongstart_contracts.knowledge_binding import (
    ApprovedKnowledgeBinding,
    KnowledgeRegistration,
    binding_digest,
    c_dependency_digest,
    dependency_union,
)

from ...config import Settings, get_settings
from ...db import configured_engine
from .packs import PackConflictError, PackManifestError, PackNotFoundError, PackService
from .repository import PostgresKnowledgeRepository


class KnowledgeCurrentness:
    """Exact pack-root projection. C/B still verify question/rule/requirement refs."""

    is_fixture = False

    def __init__(self, service: PackService, repository: PostgresKnowledgeRepository) -> None:
        self.service, self.repository = service, repository

    def resolve_active(self, organization_id: str, application_context: str) -> EvidenceBundle:
        state = self.service.active_state(organization_id, application_context)
        return self.repository.get_bundle(organization_id, state.pack_version_id)

    def project(
        self,
        organization_id: str,
        application_context: str,
        bundle: EvidenceBundle,
        refs: list[DependencyRef],
    ) -> ApprovedKnowledgeBinding:
        state = self.service.require_active(
            organization_id, application_context, bundle.pack_version_id
        )
        manifest = self.service.get_manifest(organization_id, bundle.pack_version_id)
        actual = self.repository.get_bundle(organization_id, bundle.pack_version_id)
        if (
            manifest.request.application_context != application_context
            or actual != bundle
            or bundle.organization_id != organization_id
        ):
            raise PackManifestError("evidence_binding_mismatch")
        original = dependency_union(refs)
        pack_refs = [r for r in original if r.kind == "pack"]
        if pack_refs != [
            DependencyRef(kind="pack", ref_id=actual.pack_id, version=actual.pack_version_id)
        ]:
            raise PackManifestError("exact_pack_dependency_required")
        projected = [
            ValidationDependency(
                kind="pack_version", ref_id=state.pack_version_id, version=state.pack_version_id
            )
        ]
        facts = {f.fact_id: f for f in actual.facts}
        policies = {p.policy_id: p for p in manifest.request.policies}
        sources = {s.source_version_id: s for f in actual.facts for s in f.supporting_refs}
        for ref in original:
            if ref.kind == "fact":
                fact = facts.get(ref.ref_id)
                if fact is None or ref.ref_id not in actual.allowed_fact_ids:
                    raise PackManifestError("fact_binding_not_authorized")
                # C's legacy content digest is NOT an A4 fact version. Validate it,
                # then obtain the actual integer version from authoritative A4 evidence.
                import hashlib
                import json

                digest = hashlib.sha256(
                    json.dumps(
                        fact.model_dump(mode="json"),
                        sort_keys=True,
                        separators=(",", ":"),
                        default=str,
                    ).encode()
                ).hexdigest()
                if ref.version != f"{actual.pack_version_id}:{digest[:16]}":
                    raise PackManifestError("legacy_fact_binding_mismatch")
                projected.append(
                    ValidationDependency(
                        kind="fact_version", ref_id=ref.ref_id, version=str(fact.fact_version)
                    )
                )
            elif ref.kind == "policy":
                policy = policies.get(ref.ref_id)
                if policy is None or ref.version != str(policy.policy_version):
                    raise PackManifestError("policy_binding_mismatch")
                projected.append(
                    ValidationDependency(
                        kind="policy",
                        ref_id=ref.ref_id,
                        version=str(policy.policy_version),
                        content_hash=policy.content_sha256,
                    )
                )
            elif ref.kind == "source_version":
                source = sources.get(ref.ref_id)
                if source is None or ref.version != source.content_hash:
                    raise PackManifestError("source_binding_mismatch")
                projected.append(
                    ValidationDependency(
                        kind="source_version", ref_id=ref.ref_id, version=source.content_hash
                    )
                )
            elif ref.kind not in {"pack", "question", "rule_set"}:
                # No live C requirement-set verifier exists in this increment.
                raise PackManifestError("uncovered_dependency")
        projected.sort(key=lambda d: (d.kind, d.ref_id, d.version))
        binding = ApprovedKnowledgeBinding(
            organization_id=organization_id,
            application_context=application_context,
            pack_version_id=state.pack_version_id,
            active_revision=state.revision,
            c_dependencies_sha256=c_dependency_digest(original),
            dependencies=projected,
            projection_sha256="0" * 64,
        )
        return binding.model_copy(update={"projection_sha256": binding_digest(binding)})

    def register(
        self,
        organization_id: str,
        target_kind: Literal["browser_plan", "browser_grant"],
        target_id: str,
        binding: ApprovedKnowledgeBinding,
        expected_revision: int = 0,
    ) -> KnowledgeRegistration:
        target = self.service.register_browser_target(
            organization_id,
            DependencyRegistrationRequest(
                target_kind=target_kind,
                target_id=target_id,
                expected_revision=expected_revision,
                dependencies=binding.dependencies,
            ),
            binding,
        )
        return KnowledgeRegistration(
            target_kind=target_kind,
            target_id=target_id,
            target_revision=target.revision,
            binding=binding,
        )

    def check_registration(
        self, organization_id: str, registration: KnowledgeRegistration
    ) -> DependencyCurrentness:
        binding = registration.binding
        if (
            organization_id != binding.organization_id
            or binding_digest(binding) != binding.projection_sha256
        ):
            return DependencyCurrentness(status="stale", detail="binding_mismatch")
        try:
            target = self.service.get_target(
                organization_id, registration.target_kind, registration.target_id
            )
            active = self.service.active_state(organization_id, binding.application_context)
            self.service.validate_dependencies(organization_id, binding.dependencies)
            current = (
                target.state == "current"
                and target.revision == registration.target_revision
                and target.dependencies == binding.dependencies
                and target.application_context == binding.application_context
                and target.pack_version_id == binding.pack_version_id
                and target.active_revision == binding.active_revision
                and target.projection_sha256 == binding.projection_sha256
                and active.pack_version_id == binding.pack_version_id
                and active.revision == binding.active_revision
            )
            return DependencyCurrentness(
                status="current" if current else "stale",
                detail="a4_current" if current else "source_pack_changed",
            )
        except (PackConflictError, PackNotFoundError, PackManifestError):
            return DependencyCurrentness(status="stale", detail="managed_target_unusable")
        except Exception:
            return DependencyCurrentness(
                status="unavailable", detail="managed_verifier_unavailable"
            )

    def check(
        self, organization_id: str, target_id: str, dependencies: list[DependencyRef]
    ) -> DependencyCurrentness:
        # Legacy callback is not an authority for managed content. B uses the immutable
        # registration plus full union, not a per-field subset.
        return DependencyCurrentness(status="unavailable", detail="registration_required")


def get_prefill_currentness(
    settings: Annotated[Settings, Depends(get_settings)],
) -> KnowledgeCurrentness | None:
    if not settings.database_url:
        return None
    engine = configured_engine(settings)
    return KnowledgeCurrentness(PackService(engine), PostgresKnowledgeRepository(engine))
