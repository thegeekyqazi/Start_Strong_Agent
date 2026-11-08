# Migrations

One shared Alembic history (`alembic.ini` at the repo root). Dev A sequences shared
migrations after INIT-001; other lanes submit bounded migration requests.

- Apply: `make migrate` (`uv run alembic upgrade head`)
- New revision: `uv run alembic revision -m "<message>"`, then hand-edit; keep one head.
- `REQUIRED_MIGRATION_REVISION` in `services/api/src/strongstart_api/db.py` must equal the
  head; `tests/unit/test_migrations.py` enforces this and `/health/ready` requires it.

`0001_bootstrap` creates only `organizations` and `bootstrap_metadata`.
