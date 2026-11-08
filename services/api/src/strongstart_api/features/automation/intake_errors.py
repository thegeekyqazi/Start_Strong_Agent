"""Automation-specific failure reasons carried in the shared ErrorEnvelope (B2-AUTO-001 s8).

The shared ``ErrorCode`` enum is not extended (common.py is a shared contract). The
specific reason travels in ``details.reason`` with a stable vocabulary:

malformed_request, malformed_definition, duplicate_id, unsupported_input,
input_too_large, source_unavailable, hash_mismatch, browser_unavailable,
fixture_not_allowed, timeout, unknown_form_version.

Mapping findings (mapping_missing/ambiguous/changed, unresolved_requirement) are
returned as typed findings inside a 200 inspection result, not as errors.
"""

from __future__ import annotations

from typing import Any

from strongstart_contracts import ErrorCode

from ...errors import ApiError


def intake_error(
    status: int, code: ErrorCode, reason: str, message: str, **details: Any
) -> ApiError:
    return ApiError(status, code, message, {"reason": reason, **details})


def malformed(message: str, **details: Any) -> ApiError:
    return intake_error(
        422, ErrorCode.VALIDATION_FAILED, "malformed_definition", message, **details
    )


def too_large(limit: int, kind: str) -> ApiError:
    return intake_error(
        413,
        ErrorCode.VALIDATION_FAILED,
        "input_too_large",
        f"{kind} exceeds the {limit}-byte limit",
        limit_bytes=limit,
    )


def unsupported(message: str, **details: Any) -> ApiError:
    return intake_error(422, ErrorCode.VALIDATION_FAILED, "unsupported_input", message, **details)


def duplicate_id(message: str, ids: list[str]) -> ApiError:
    return intake_error(
        422, ErrorCode.VALIDATION_FAILED, "duplicate_id", message, duplicate_ids=sorted(ids)[:50]
    )


def fixture_not_allowed(message: str = "fixture mode is not enabled here") -> ApiError:
    return intake_error(403, ErrorCode.FORBIDDEN, "fixture_not_allowed", message)


def source_unavailable(message: str = "capture source is unavailable or not found") -> ApiError:
    return intake_error(404, ErrorCode.DEPENDENCY_UNAVAILABLE, "source_unavailable", message)
