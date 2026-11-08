"""Model adapters for structured tasks (owner C; engineering v1.1 s17)."""

from .base import (
    DataClassNotPermitted,
    ModelAdapter,
    ModelCapabilities,
    ModelError,
    ModelOutputRejected,
    ModelTimeout,
    ModelTransportError,
    StructuredTask,
)

__all__ = [
    "DataClassNotPermitted",
    "ModelAdapter",
    "ModelCapabilities",
    "ModelError",
    "ModelOutputRejected",
    "ModelTimeout",
    "ModelTransportError",
    "StructuredTask",
]
