"""FastAPI application factory (shared host; feature owners edit their own routers)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from strongstart_contracts import (
    Capability,
    CapabilityReport,
    LivenessReport,
    ReadinessReport,
    SessionIdentity,
)

from .config import Settings, get_settings
from .db import check_readiness
from .errors import install_error_handling
from .features import FEATURE_CAPABILITIES, FEATURE_ROUTERS
from .identity import Identity

SERVICE_NAME = "strongstart-api"


def platform_capabilities(settings: Settings) -> list[Capability]:
    return [
        Capability(
            feature="platform.health",
            owner="shared",
            status="available",
            detail="Liveness and DB/migration readiness endpoints.",
        ),
        Capability(
            feature="platform.identity",
            owner="shared",
            status="fixture_only" if settings.fixture_mode else "unavailable",
            detail=(
                "Local fixed demo identity (not authentication)."
                if settings.fixture_mode
                else "No identity provider configured; protected operations deny."
            ),
        ),
        Capability(
            feature="platform.demo_seed",
            owner="shared",
            status="fixture_only",
            detail="Idempotent synthetic demo-org seed for local development.",
        ),
    ]


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Strong Start API", version="0.1.0")
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
    cors_settings = settings or get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    install_error_handling(app)

    @app.get("/health/live", response_model=LivenessReport)
    def live() -> LivenessReport:
        return LivenessReport(status="alive", service=SERVICE_NAME)

    @app.get("/health/ready", response_model=ReadinessReport)
    def ready(s: Annotated[Settings, Depends(get_settings)]) -> JSONResponse:
        report = check_readiness(s.database_url, s.db_connect_timeout_seconds)
        return JSONResponse(
            status_code=200 if report.status == "ready" else 503,
            content=report.model_dump(mode="json"),
        )

    @app.get("/api/capabilities", response_model=CapabilityReport)
    def capabilities(s: Annotated[Settings, Depends(get_settings)]) -> CapabilityReport:
        return CapabilityReport(
            environment=s.environment,
            auth_mode=s.auth_mode,
            fixture_mode=s.fixture_mode,
            capabilities=[*platform_capabilities(s), *FEATURE_CAPABILITIES],
        )

    @app.get("/api/session", response_model=SessionIdentity)
    def session(identity: Identity) -> SessionIdentity:
        return identity

    for router in FEATURE_ROUTERS:
        app.include_router(router)
    return app


def app_factory() -> FastAPI:
    """Uvicorn entry point: ``uvicorn --factory strongstart_api.app:app_factory``."""
    return create_app()
