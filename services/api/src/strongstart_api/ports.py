"""Dependency-injection providers for shared ports.

Defaults are the fail-closed ``Unconfigured*`` implementations. Tests or a later
real adapter replace them with ``app.dependency_overrides[get_capture_store] = ...``.
Fixture adapters must be injected deliberately and report ``is_fixture = True``.
"""

from __future__ import annotations

from strongstart_contracts.ports import (
    ApprovedAnswerResolver,
    CaptureStore,
    EvidenceProvider,
    JobStore,
    UnconfiguredApprovedAnswerResolver,
    UnconfiguredCaptureStore,
    UnconfiguredEvidenceProvider,
    UnconfiguredJobStore,
)


def get_capture_store() -> CaptureStore:
    return UnconfiguredCaptureStore()


def get_evidence_provider() -> EvidenceProvider:
    return UnconfiguredEvidenceProvider()


def get_approved_answer_resolver() -> ApprovedAnswerResolver:
    return UnconfiguredApprovedAnswerResolver()


def get_job_store() -> JobStore:
    return UnconfiguredJobStore()
