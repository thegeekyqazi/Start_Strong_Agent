"""Export canonical JSON Schema for all public contracts.

Usage: python -m strongstart_contracts.export OUTPUT_JSON
The TypeScript declarations in packages/contracts/ts are generated from this file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from . import (
    ActivatePackRequest,
    ActivePackState,
    AnswerSnapshot,
    ApplicationDefinition,
    ApprovalSnapshot,
    CapabilityReport,
    ChangeSet,
    DependencyRegistrationRequest,
    DependencyTargetState,
    ErrorEnvelope,
    EvidenceBundle,
    FixtureBundle,
    FormMap,
    InvalidationSummary,
    JobContext,
    JobResult,
    KnowledgeAvailability,
    KnowledgeRetrievalResult,
    KnowledgeSnapshot,
    LivenessReport,
    Opportunity,
    PackActivationReport,
    PackFactBinding,
    PackManifest,
    PackManifestRequest,
    PackPolicyBinding,
    PdfSourceImportRequest,
    PdfSourceImportResult,
    PrefillAction,
    QuestionSet,
    ReadinessReport,
    RequirementSet,
    RuleCapability,
    SessionIdentity,
    SourceReference,
    SourceValidationReport,
    SourceValidationRequest,
    TextSourceImportRequest,
    TextSourceImportResult,
    ValidationResult,
)
from .answers import ANSWERS_PUBLIC_MODELS
from .application_publication import APPLICATION_PUBLICATION_PUBLIC_MODELS
from .automation_intake import AUTOMATION_INTAKE_PUBLIC_MODELS
from .automation_prefill import AUTOMATION_PREFILL_PUBLIC_MODELS
from .discovery import (
    CaptureCatalogPage,
    CaptureContent,
    CapturedDocument,
    CaptureRequest,
    FundingAvailability,
    SearchRequest,
    SearchResult,
)
from .funding_review import FUNDING_REVIEW_PUBLIC_MODELS
from .skills import SKILLS_PUBLIC_MODELS

PUBLIC_MODELS: tuple[type[BaseModel], ...] = (
    SourceReference,
    ErrorEnvelope,
    EvidenceBundle,
    KnowledgeAvailability,
    KnowledgeSnapshot,
    TextSourceImportRequest,
    TextSourceImportResult,
    PdfSourceImportRequest,
    PdfSourceImportResult,
    KnowledgeRetrievalResult,
    PackFactBinding,
    PackPolicyBinding,
    PackManifestRequest,
    PackManifest,
    ActivatePackRequest,
    DependencyRegistrationRequest,
    DependencyTargetState,
    ActivePackState,
    InvalidationSummary,
    PackActivationReport,
    Opportunity,
    RequirementSet,
    QuestionSet,
    ApplicationDefinition,
    FormMap,
    PrefillAction,
    AnswerSnapshot,
    ApprovalSnapshot,
    ValidationResult,
    SourceValidationRequest,
    SourceValidationReport,
    RuleCapability,
    JobContext,
    JobResult,
    ChangeSet,
    LivenessReport,
    ReadinessReport,
    CapabilityReport,
    SessionIdentity,
    FixtureBundle,
    # B1-DISC-001 (owner B1)
    SearchRequest,
    SearchResult,
    CaptureRequest,
    CapturedDocument,
    CaptureContent,
    FundingAvailability,
    CaptureCatalogPage,  # DEV-B-BUNDLE-002 M2 (owner B1/funding)
    # DEV-B-BUNDLE-002 M3-M5 (owner B1/funding): cases, evaluations, saved research
    *FUNDING_REVIEW_PUBLIC_MODELS,
    # B2-AUTO-001 (owner B2), imported from its module (B1-B2 launch agreement s2)
    *AUTOMATION_INTAKE_PUBLIC_MODELS,
    # DEV-B-BUNDLE-002 M1 (owner B2): saved definitions / question reader
    *APPLICATION_PUBLICATION_PUBLIC_MODELS,
    *AUTOMATION_PREFILL_PUBLIC_MODELS,
    # C1 (owner C), imported from its module like B2's
    *ANSWERS_PUBLIC_MODELS,
    # C4-SKL-001 (owner C): thin practice generator and draft preview
    *SKILLS_PUBLIC_MODELS,
)


def build_schema() -> dict[str, object]:
    _, top = models_json_schema(
        [(m, "serialization") for m in PUBLIC_MODELS],
        title="StrongStartContracts",
        ref_template="#/$defs/{model}",
    )
    defs = top.get("$defs", {})
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "StrongStartContracts",
        "description": "GENERATED from strongstart_contracts (Pydantic). Do not edit by hand.",
        "x-schema-version": "1",
        "$defs": dict(sorted(defs.items())),
    }


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m strongstart_contracts.export OUTPUT_JSON", file=sys.stderr)
        return 2
    out = Path(args[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
