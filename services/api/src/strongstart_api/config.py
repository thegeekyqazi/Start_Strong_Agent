"""Server-side configuration. Keys stay here; nothing in this module reaches the browser build."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STRONGSTART_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    environment: Literal["local", "test", "production"] = "local"
    # "none": no identity provider configured -> protected operations deny.
    # "fixture": LOCAL-ONLY fixed demo identity; rejected for production.
    auth_mode: Literal["none", "fixture"] = "none"
    database_url: str | None = Field(
        default=None, repr=False, exclude=True, description="Server-only PostgreSQL connection URL"
    )
    db_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)
    answer_store_backend: Literal["postgres", "memory", "unconfigured"] = "unconfigured"
    database_profile: Literal["local", "tigerdata"] = "local"
    db_sslrootcert: str | None = None
    db_pool_size: int = Field(default=3, ge=1, le=50)
    db_max_overflow: int = Field(default=0, ge=0, le=20)
    db_pool_timeout_seconds: float = Field(default=3, ge=0.01, le=30)
    db_lock_timeout_ms: int = Field(default=3000, ge=1, le=30000)
    db_statement_timeout_ms: int = Field(default=15000, ge=1, le=120000)
    db_connection_budget: int | None = Field(default=None, ge=1)
    api_processes: int = Field(default=1, ge=1, le=100)
    max_export_bytes: int = Field(default=8_388_608, ge=1024, le=67_108_864)
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"]
    )

    # Knowledge artifact storage (owner A2a). The local adapter is development/test only.
    knowledge_artifact_store_dir: Path = Path(".local-data/knowledge-artifacts")
    knowledge_max_text_bytes: int = Field(default=1_000_000, ge=1_000, le=5_000_000)
    knowledge_max_pdf_bytes: int = Field(default=5_000_000, ge=10_000, le=20_000_000)
    knowledge_max_pdf_pages: int = Field(default=100, ge=1, le=500)
    knowledge_max_extracted_chars: int = Field(default=1_000_000, ge=1_000, le=5_000_000)
    knowledge_retrieval_limit: int = Field(default=8, ge=1, le=25)

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

    # Dev B local repositories (DEV-B-BUNDLE-002 s4.1): saved definitions, capture catalog,
    # funding cases, evaluations, profiles and change observations. Development/test only;
    # disabled in production. Windows writes need an explicit reduced-durability opt-in.
    dev_b_store_dir: Path = Path(".local-data/dev-b-store")
    dev_b_store_allow_reduced_durability: bool = False

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
        if self.environment == "production" and self.answer_store_backend == "memory":
            raise ValueError("memory answer storage is forbidden in production")
        if self.database_url:
            from .database_profile import postgres_url

            postgres_url(self.database_url, self.database_profile, self.db_sslrootcert)
        if self.database_profile == "tigerdata":
            required = (self.db_pool_size + self.db_max_overflow) * self.api_processes
            if self.db_connection_budget is None or required > self.db_connection_budget:
                raise ValueError("configure the service connection budget for all API processes")
        return self

    @property
    def fixture_mode(self) -> bool:
        return self.auth_mode == "fixture"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
