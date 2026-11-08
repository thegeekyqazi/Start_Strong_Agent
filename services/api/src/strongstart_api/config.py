"""Server-side configuration. Keys stay here; nothing in this module reaches the browser build."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
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

    # Provider credentials: optional and unused by the bootstrap. Never logged or exposed.
    gemini_api_key: SecretStr | None = None
    tavily_api_key: SecretStr | None = None
    firecrawl_api_key: SecretStr | None = None

    @model_validator(mode="after")
    def _fixture_mode_is_local_only(self) -> Settings:
        if self.auth_mode == "fixture" and self.environment == "production":
            raise ValueError(
                "STRONGSTART_AUTH_MODE=fixture is forbidden when STRONGSTART_ENVIRONMENT=production"
            )
        return self

    @property
    def fixture_mode(self) -> bool:
        return self.auth_mode == "fixture"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
