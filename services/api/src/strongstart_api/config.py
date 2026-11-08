"""Server-side configuration. Keys stay here; nothing in this module reaches the browser build."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STRONGSTART_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["local", "test", "production"] = "local"
    # "none": no identity provider configured -> protected operations deny.
    # "fixture": LOCAL-ONLY fixed demo identity; rejected for production.
    auth_mode: Literal["none", "fixture"] = "none"
    database_url: str | None = Field(
        default=None, description="SQLAlchemy URL, e.g. postgresql+psycopg://user:pw@host:port/db"
    )
    db_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"]
    )

    # Knowledge artifact storage (owner A2a). The local adapter is development/test only.
    knowledge_artifact_store_dir: Path = Path(".local-data/knowledge-artifacts")
    knowledge_max_text_bytes: int = Field(default=1_000_000, ge=1_000, le=5_000_000)

    # Provider credentials: optional and unused by the bootstrap. Never logged or exposed.
    gemini_api_key: SecretStr | None = None
    tavily_api_key: SecretStr | None = None
    firecrawl_api_key: SecretStr | None = None

    # Funding discovery/capture (owner B1; B1-DISC-001). Budgets are project limits.
    # "fixture" modes serve labelled synthetic data and are rejected in production.
    funding_search_mode: Literal["live", "fixture"] = "live"
    funding_capture_mode: Literal["live", "fixture"] = "live"
    funding_max_results: int = Field(default=5, ge=1, le=5)
    funding_search_timeout_seconds: float = Field(default=15, ge=1, le=30)
    funding_capture_timeout_seconds: float = Field(default=45, ge=5, le=120)
    funding_max_capture_bytes: int = Field(default=2_000_000, ge=10_000, le=10_000_000)
    funding_capture_store_dir: Path = Path(".local-data/funding-captures")
    funding_query_fields: list[Literal["interests", "geography", "program_context"]] = Field(
        default=["interests", "geography", "program_context"]
    )
    funding_source_seed_path: Path | None = None

    # Model adapters (owner C; C1-shell-and-adapter). "fake" is the deterministic fixture
    # adapter (local default; unavailable in production, enforced where the adapter is
    # selected so other lanes' production settings still load). "gemini" needs both a key and an
    # explicitly configured model name; there is no fallback to another provider.
    model_provider: Literal["fake", "gemini"] = "fake"
    gemini_model: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._-]{1,64}$")
    model_timeout_seconds: float = Field(default=20, ge=0.01, le=60)

    @field_validator("gemini_model", mode="before")
    @classmethod
    def _empty_model_is_unset(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def _fixture_mode_is_local_only(self) -> Settings:
        if self.auth_mode == "fixture" and self.environment == "production":
            raise ValueError(
                "STRONGSTART_AUTH_MODE=fixture is forbidden when STRONGSTART_ENVIRONMENT=production"
            )
        if self.environment == "production" and "fixture" in (
            self.funding_search_mode,
            self.funding_capture_mode,
        ):
            raise ValueError("funding fixture providers are forbidden in production")
        return self

    @property
    def fixture_mode(self) -> bool:
        return self.auth_mode == "fixture"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
