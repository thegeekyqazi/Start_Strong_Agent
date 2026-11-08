"""Structured error handling: every error response is an ErrorEnvelope, never a raw exception."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from strongstart_contracts import CapabilityUnavailable, ErrorCode, ErrorEnvelope

logger = logging.getLogger("strongstart_api")


class ApiError(Exception):
    def __init__(
        self, status_code: int, code: ErrorCode, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def not_implemented(feature: str, operation: str) -> ApiError:
    return ApiError(
        501,
        ErrorCode.NOT_IMPLEMENTED,
        f"{feature}.{operation} is not implemented yet",
        {"feature": feature, "operation": operation},
    )


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _envelope(
    request: Request, status: int, code: ErrorCode, message: str, details: dict[str, Any]
) -> JSONResponse:
    request_id = _request_id(request)
    body = ErrorEnvelope(code=code, message=message, request_id=request_id, details=details)
    headers = {"X-Request-ID": request_id} if request_id else None
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"), headers=headers)


def install_error_handling(app: FastAPI) -> None:
    from .features.applications.store import StoreFailure

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Server-generated correlation ID; a client-supplied value is not trusted.
        request.state.request_id = uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _envelope(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StoreFailure)
    async def _store_failure(request: Request, exc: StoreFailure) -> JSONResponse:
        return _envelope(
            request,
            503,
            ErrorCode.CAPABILITY_UNAVAILABLE,
            "application storage unavailable",
            {
                "port": exc.port,
                "reason": exc.reason,
                "next_action": "Read stored state before retrying; reconcile uncertain writes.",
            },
        )

    @app.exception_handler(CapabilityUnavailable)
    async def _unavailable(request: Request, exc: CapabilityUnavailable) -> JSONResponse:
        return _envelope(
            request,
            503,
            ErrorCode.CAPABILITY_UNAVAILABLE,
            f"{exc.port} is not available",
            {"port": exc.port, "detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        issues = [{"loc": list(e.get("loc", ())), "type": e.get("type")} for e in exc.errors()]
        return _envelope(
            request,
            422,
            ErrorCode.VALIDATION_FAILED,
            "request validation failed",
            {"issues": issues},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = ErrorCode.FORBIDDEN if exc.status_code == 403 else ErrorCode.VALIDATION_FAILED
        if exc.status_code == 404:
            return _envelope(request, 404, ErrorCode.NOT_IMPLEMENTED, "no such route", {})
        return _envelope(request, exc.status_code, code, "request rejected", {})

    @app.exception_handler(Exception)
    async def _internal(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error (request_id=%s)", _request_id(request))
        return _envelope(request, 500, ErrorCode.INTERNAL_ERROR, "internal error", {})
