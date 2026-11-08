"""Port protocols shared between lanes, with default fail-closed implementations.

Default (unconfigured) implementations raise ``CapabilityUnavailable``; they never
return a fabricated success. Fixture implementations live in
``strongstart_contracts.fixture_adapters`` and must be injected deliberately.

| Port                   | Real producer | Early consumers |
| ---------------------- | ------------- | --------------- |
| CaptureStore           | A             | B1, B2          |
| EvidenceProvider       | A             | B1, C           |
| ApprovedAnswerResolver | C             | B2              |
| JobStore               | A (with C)    | A, B, C         |
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .answers import ApprovalSnapshot
from .common import ErrorCode, ErrorEnvelope, SourceReference
from .evidence import EvidenceBundle
from .jobs import JobContext, JobResult


class CapabilityUnavailable(Exception):
    """A port has no configured real implementation."""

    def __init__(self, port: str, detail: str = "no implementation configured") -> None:
        super().__init__(f"{port}: {detail}")
        self.port = port
        self.detail = detail

    def to_envelope(self, request_id: str | None = None) -> ErrorEnvelope:
        return ErrorEnvelope(
            code=ErrorCode.CAPABILITY_UNAVAILABLE,
            message=f"{self.port} is not available",
            request_id=request_id,
            details={"port": self.port, "detail": self.detail},
        )


@dataclass(frozen=True)
class StoredCapture:
    reference: SourceReference
    content: bytes
    media_type: str


@runtime_checkable
class CaptureStore(Protocol):
    is_fixture: bool

    def put(
        self, reference: SourceReference, content: bytes, media_type: str
    ) -> SourceReference: ...

    def get(self, source_version_id: str) -> StoredCapture: ...


@runtime_checkable
class EvidenceProvider(Protocol):
    is_fixture: bool

    def get_bundle(self, organization_id: str, pack_version_id: str) -> EvidenceBundle: ...


@runtime_checkable
class ApprovedAnswerResolver(Protocol):
    is_fixture: bool

    def resolve(self, organization_id: str, approval_snapshot_id: str) -> ApprovalSnapshot:
        """Return the current authoritative approval, or raise if missing/stale."""
        ...


@runtime_checkable
class JobStore(Protocol):
    is_fixture: bool

    def enqueue(self, context: JobContext) -> JobContext: ...

    def get_result(self, job_id: str) -> JobResult: ...


class UnconfiguredCaptureStore:
    is_fixture = False

    def put(self, reference: SourceReference, content: bytes, media_type: str) -> SourceReference:
        raise CapabilityUnavailable("CaptureStore")

    def get(self, source_version_id: str) -> StoredCapture:
        raise CapabilityUnavailable("CaptureStore")


class UnconfiguredEvidenceProvider:
    is_fixture = False

    def get_bundle(self, organization_id: str, pack_version_id: str) -> EvidenceBundle:
        raise CapabilityUnavailable("EvidenceProvider")


class UnconfiguredApprovedAnswerResolver:
    is_fixture = False

    def resolve(self, organization_id: str, approval_snapshot_id: str) -> ApprovalSnapshot:
        raise CapabilityUnavailable("ApprovedAnswerResolver")


class UnconfiguredJobStore:
    is_fixture = False

    def enqueue(self, context: JobContext) -> JobContext:
        raise CapabilityUnavailable("JobStore")

    def get_result(self, job_id: str) -> JobResult:
        raise CapabilityUnavailable("JobStore")
