"""Alembic environment. The URL comes from STRONGSTART_DATABASE_URL (server config only)."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from strongstart_api.config import Settings
from strongstart_api.db import configured_engine, metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def _url() -> str:
    url = config.attributes.get("database_url") or Settings().database_url
    if not url:
        raise RuntimeError("STRONGSTART_DATABASE_URL is not set")
    return str(url)


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    settings = Settings()
    if config.attributes.get("database_url"):
        settings = settings.model_copy(
            update={"database_url": str(config.attributes["database_url"])}
        )
    engine = configured_engine(settings)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
