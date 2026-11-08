"""Strong Start shared contracts v1 (canonical source for generated JSON Schema / TS types)."""

from .answers import AnswerSnapshot, ApprovalSnapshot, DependencyRef
from .automation import (
    ApplicationDefinition,
    FieldMapping,
    FormMap,
    LimitConflict,
    PrefillAction,
    Question,
    QuestionLimit,
    QuestionSet,
)
from .common import (
    SCHEMA_VERSION,
    DateKnowledge,
    ErrorCode,
    ErrorEnvelope,
    Provenance,
    ProvenanceClass,
    SourceReference,
)
from .evidence import (
    EvidenceBundle,
    Fact,
    KnowledgeAvailability,
    KnowledgePassage,
    KnowledgeSnapshot,
    KnowledgeSourceVersion,
    TextSourceImportRequest,
    TextSourceImportResult,
)
from .fixtures import FixtureBundle, load_fixture_bundle
from .funding import Opportunity, RequirementCondition, RequirementSet
from .jobs import ChangedVersion, ChangeSet, JobBudget, JobContext, JobResult
from .platform import (
    Capability,
    CapabilityReport,
    LivenessReport,
    ReadinessCheck,
    ReadinessReport,
    SessionIdentity,
)
from .ports import CapabilityUnavailable
from .validation import ValidationResult

__all__ = [
    "SCHEMA_VERSION",
    "AnswerSnapshot",
    "ApplicationDefinition",
    "ApprovalSnapshot",
    "Capability",
    "CapabilityReport",
    "CapabilityUnavailable",
    "ChangeSet",
    "ChangedVersion",
    "DateKnowledge",
    "DependencyRef",
    "ErrorCode",
    "ErrorEnvelope",
    "EvidenceBundle",
    "Fact",
    "FieldMapping",
    "FixtureBundle",
    "FormMap",
    "JobBudget",
    "JobContext",
    "JobResult",
    "KnowledgeAvailability",
    "KnowledgePassage",
    "KnowledgeSnapshot",
    "KnowledgeSourceVersion",
    "LimitConflict",
    "LivenessReport",
    "Opportunity",
    "PrefillAction",
    "Provenance",
    "ProvenanceClass",
    "Question",
    "QuestionLimit",
    "QuestionSet",
    "ReadinessCheck",
    "ReadinessReport",
    "RequirementCondition",
    "RequirementSet",
    "SessionIdentity",
    "SourceReference",
    "TextSourceImportRequest",
    "TextSourceImportResult",
    "ValidationResult",
    "load_fixture_bundle",
]
