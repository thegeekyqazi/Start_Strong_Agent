"""Bounded strict JSON command bodies for the Dev B funding routes (DEV-B-BUNDLE-002 s10).

Identity is resolved by the route before this runs. Rejects: oversize bodies (413),
invalid UTF-8/JSON, duplicate keys, NaN/Infinity, excessive depth, and schema mismatch or
coercion (422, ``details.reason = invalid_input``). Validation uses Pydantic strict JSON
mode, so ``"1"``/``1.0``/``true`` are not accepted where an integer is required.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from pydantic import BaseModel, ValidationError

from strongstart_contracts import ErrorCode

from ...errors import ApiError

MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_DEPTH = 12


def _error(status: int, reason: str, message: str, **details: Any) -> ApiError:
    code = ErrorCode.VALIDATION_FAILED
    return ApiError(status, code, message, {"reason": reason, **details})


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate key")
        out[key] = value
    return out


def _reject_constant(value: str) -> Any:
    raise ValueError(f"{value} is not allowed")


def _depth(value: Any, level: int = 0) -> int:
    if level > MAX_DEPTH:
        return level
    if isinstance(value, dict):
        return max((_depth(v, level + 1) for v in value.values()), default=level)
    if isinstance(value, list):
        return max((_depth(v, level + 1) for v in value), default=level)
    return level


async def read_strict[M: BaseModel](
    request: Request, model: type[M], *, counts: dict[str, int] | None = None
) -> M:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise _error(413, "too_large", f"request body exceeds {MAX_BODY_BYTES} bytes")
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_BODY_BYTES:
            raise _error(413, "too_large", f"request body exceeds {MAX_BODY_BYTES} bytes")
        chunks.append(chunk)
    raw = b"".join(chunks)
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_no_duplicates,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError):
        raise _error(422, "invalid_input", "request body is not strict JSON") from None
    if _depth(parsed) > MAX_DEPTH:
        raise _error(422, "invalid_input", "request body is nested too deeply")
    if counts and isinstance(parsed, dict):
        for field, limit in counts.items():
            value = parsed.get(field)
            if isinstance(value, list) and len(value) > limit:
                raise _error(413, "too_large", f"{field} is limited to {limit} items", limit=limit)
    try:
        return model.model_validate_json(raw)
    except ValidationError as exc:
        issues = [{"loc": list(e.get("loc", ())), "type": e.get("type")} for e in exc.errors()[:50]]
        raise _error(
            422, "invalid_input", "request does not match the schema", issues=issues
        ) from None
