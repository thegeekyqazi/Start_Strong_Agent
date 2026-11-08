# Local setup and developer commands

These are the actual commands created by INIT-001. Run them from the repository root.

## Prerequisites (tested versions)

| Tool | Tested | Requirement |
| --- | --- | --- |
| Node.js / npm | 22.22.2 / 10.9.7 | `^22.22.2 \|\| ^24.15.0 \|\| >=26` (jsdom/vitest engines); `.nvmrc` = 22 |
| Python | 3.12.15 | `>=3.12,<3.14`; `.python-version` = 3.12 (uv can fetch it) |
| uv | 0.12.23 | Workspace and `uv.lock` |
| Docker + Compose | 29.9.2 / v5.6.1 | Runs local PostgreSQL only |
| GNU make | 4.4.1 | Optional; underlying commands are below |

No paid account, API key or administrator privilege is required.

## First run

```sh
make bootstrap        # uv sync --locked && npm ci && cp .env.example .env (if absent)
make db-up            # docker compose -f infra/compose.yaml up -d --wait postgres
make migrate          # uv run alembic upgrade head
make seed-demo        # uv run strongstart-seed-demo   (idempotent, synthetic)
make dev-api          # http://127.0.0.1:8000  (separate terminal)
make dev-web          # http://127.0.0.1:5173  (separate terminal; proxies /api and /health)
```

Optional browser readiness: `make browser-install` (`uv run playwright install chromium`, downloads into `~/.cache/ms-playwright`), then `make browser-smoke`. On Linux distributions Playwright does not officially support, system libraries may be missing. CI uses `--with-deps` on Ubuntu.

## Command reference

| make target | Underlying commands | Needs DB |
| --- | --- | --- |
| `bootstrap` | `uv sync --locked`; `npm ci`; copy `.env.example` → `.env` | no |
| `db-up` / `db-down` | `docker compose -f infra/compose.yaml up -d --wait postgres` / `down` | – |
| `migrate` | `uv run alembic upgrade head` | yes |
| `seed-demo` | `uv run strongstart-seed-demo` | yes |
| `dev-api` | `uv run uvicorn --factory strongstart_api.app:app_factory --host 127.0.0.1 --port 8000 --reload` | for readiness |
| `dev-web` | `npm run dev -w @strongstart/web` | no |
| `lint` | `uv run ruff check .`; `uv run ruff format --check .`; `npm run lint`; `npm run format:check` | no |
| `format` | `uv run ruff format .`; `uv run ruff check --fix .`; `npm run format` | no |
| `typecheck` | `uv run mypy`; `npm run typecheck` | no |
| `test` | `uv run pytest` (excludes `db`/`browser` markers); `npm test` | no |
| `contracts` | `uv run python -m strongstart_contracts.export packages/contracts/schema/strongstart-contracts.schema.json`; `npm run contracts:generate` | no |
| `contracts-check` | regenerate the schema to a temp file and `cmp` it; `npm run contracts:check` | no |
| `build` | `npm run build`; `uv build --all-packages --out-dir dist/python` | no |
| `smoke` | `migrate`, `seed-demo`, `uv run pytest -q tests/unit/test_imports.py`, `uv run pytest -m db tests/smoke`, `uv run python scripts/smoke_server.py` | yes |
| `browser-smoke` | `uv run pytest -m browser -s tests/browser` | no (needs Chromium) |
| `check` | lint + typecheck + test + contracts-check + build | no |

Every target exits non-zero on failure.

## Services and ports

| Service | Address | Notes |
| --- | --- | --- |
| API | `127.0.0.1:8000` | `/health/live`, `/health/ready`, `/api/capabilities`, `/api/session`, `/api/<feature>/status` |
| Web dev server | `127.0.0.1:5173` | Vite proxies `/api` and `/health` to `WEB_DEV_API_PROXY` (default `http://127.0.0.1:8000`) |
| PostgreSQL 17.11 | `127.0.0.1:55432` | db/user `strongstart`. The password is a local-only placeholder in `.env.example` |

## Environment variables (names only)

API (server-side, `STRONGSTART_` prefix, read from the process env or `.env`):

- `STRONGSTART_ENVIRONMENT`: `local` (default) \| `test` \| `production`
- `STRONGSTART_AUTH_MODE`: `none` (default; protected operations return 401) \| `fixture` (LOCAL fixed demo identity; settings validation rejects it when the environment is `production`)
- `STRONGSTART_DATABASE_URL`: SQLAlchemy URL (`postgresql+psycopg://...`). If unset, readiness is `not_ready`. There is never a SQLite fallback
- `STRONGSTART_DB_CONNECT_TIMEOUT_SECONDS` (default 3)
- `STRONGSTART_CORS_ORIGINS`: JSON list (default `["http://127.0.0.1:5173","http://localhost:5173"]`)
- `STRONGSTART_GEMINI_API_KEY`, `STRONGSTART_TAVILY_API_KEY`, `STRONGSTART_FIRECRAWL_API_KEY`: optional and unused by INIT-001. Leave them empty

Compose (optional overrides): `STRONGSTART_LOCAL_DB_PASSWORD`, `STRONGSTART_LOCAL_DB_PORT`.

Web (public, bundled): `VITE_API_BASE_URL` (optional; empty = same origin). Only `VITE_*` variables reach the browser. Never give a server key a `VITE_` name. `tests/unit/test_secret_boundary.py` checks web sources and build output for server setting names.

## Migrations, seed and contracts

- Migration head: `0001_bootstrap` (`organizations`, `bootstrap_metadata`). `/health/ready` requires exactly this revision (`REQUIRED_MIGRATION_REVISION` in `services/api/src/strongstart_api/db.py`).
- Seed: upserts `demo-org` (simulated) and `bootstrap_metadata.demo_seed_bundle = demo-bundle@1` from `tests/fixtures/demo/demo-bundle-v1.json`. It refuses `production`.
- Contracts: edit Pydantic models in `packages/contracts/python/src/strongstart_contracts/`, then run `make contracts` and commit the regenerated `packages/contracts/schema/strongstart-contracts.schema.json` and `packages/contracts/ts/src/generated.ts`.

## Clean checkout

```sh
git clone <remote-or-path> strongstart && cd strongstart
make bootstrap && make db-up && make smoke && make check
```

## Separate B1 / B2 working directories

Never run two write-capable agents in the same checkout. From the accepted foundation commit:

```sh
git worktree add ../strongstart-b1 -b dev-b/b1-disc-001-foundation <base-commit>
git worktree add ../strongstart-b2 -b dev-b/b2-auto-001-foundation <base-commit>
cd ../strongstart-b1 && make bootstrap   # repeat in strongstart-b2
```

Worktrees share one local PostgreSQL by default, so `make migrate` and `make seed-demo` are shared state. If B1 and B2 need isolated databases, give one worktree a different `STRONGSTART_LOCAL_DB_PORT` plus a different Compose project name (`docker compose -p strongstart-b2 -f infra/compose.yaml up -d`) and a matching `STRONGSTART_DATABASE_URL` in that worktree's `.env`. Separate clones work the same way.

## DATA-001 durable C storage

Use explicit `STRONGSTART_ANSWER_STORE_BACKEND=postgres` for the example DB setup, or
`memory` deliberately for local fixtures. Default `unconfigured` is unavailable. See
[TigerData connection/roles/recovery](tigerdata.md), [current feature status](../coordination/feature-status.md)
and [DATA-001 handoff](../handoffs/data/data-001-durable-applications-r1.md). C database
state survives restart; B files and pending-plan epochs retain their development limits.
Hosted TigerData verification was performed 2026-11-08 on the owner's isolated services; see [TigerData setup](tigerdata.md#hosted-evidence-2026-11-08).
