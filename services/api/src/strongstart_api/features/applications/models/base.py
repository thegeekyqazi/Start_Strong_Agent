"""ModelAdapter interface for structured tasks (engineering v1.1 s17; C1 spec s4).

An adapter turns a typed ``StructuredTask`` into **raw text**. It never returns a
trusted object: every response is parsed and validated by ``validation.py`` before
the service builds a ``DraftProposal`` (SEC-14). Adapters do not choose a fallback
provider; an unusable adapter raises ``CapabilityUnavailable`` (s17).

Agent-runtime (session/tool) adapters are a separate interface and out of C1 scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from strongstart_contracts import ProvenanceClass


@dataclass(frozen=True)
class ModelCapabilities:
    """What an adapter declares it supports. Tools/streaming/sessions are not offered."""

    adapter: Literal["fake", "gemini"]
    model: str
    structured_output: bool
    max_context_tokens: int | None
    max_output_tokens: int | None
    permitted_data_classes: frozenset[ProvenanceClass]
    is_fixture: bool
    tools: bool = False
    streaming: bool = False
    cancellation: bool = False


@dataclass(frozen=True)
class StructuredTask:
    """A bounded, typed request. Identity/permissions are never part of the payload."""

    task_id: str
    operation: Literal[
        "draft_answer",
        "plan_application",
        "numerical_review",
        "meaning_review",
        "propose_practice",  # C4-SKL-001: structured practice proposal (no tools)
        "screen_practice",  # C4-SKL-001: bounded model-based screening signal
    ]
    instructions: str
    payload: dict[str, Any]
    output_schema: dict[str, Any]
    data_classes: frozenset[ProvenanceClass] = field(default_factory=frozenset)


@runtime_checkable
class ModelAdapter(Protocol):
    def capabilities(self) -> ModelCapabilities:
        """Raise ``CapabilityUnavailable`` if the adapter is not usable as configured."""
        ...

    async def complete(self, task: StructuredTask) -> str:
        """Return the raw model text for ``task``. Never parsed or trusted here."""
        ...


class ModelError(Exception):
    """Base for typed model failures. Messages never include provider bodies or keys."""

    reason: str = "model_error"

    def __init__(self, reason: str | None = None, issues: list[str] | None = None) -> None:
        self.reason = reason or self.reason
        self.issues = list(issues or [])
        super().__init__(self.reason)


class ModelTimeout(ModelError):
    reason = "model_timeout"


class ModelOutputRejected(ModelError):
    reason = "model_output_rejected"


class ModelTransportError(ModelError):
    """reason is one of: auth_rejected, rate_limited, provider_error."""

    reason = "provider_error"


class DataClassNotPermitted(ModelError):
    reason = "data_class_not_permitted"
