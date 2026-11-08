# INIT-001: Stack choices and layout deviations

- Author/developer: INIT-001 setup agent (Claude Code) for Dev B
- Date: 2026-11-07
- Status: developer-decision
- Decided/accepted by and evidence: setup agent within INIT-001 s4/s5 discretion; not yet reviewed by the owner
- Engineering path/version/sections: v1.1 s2, s3, s19, s22, s23.1
- Feature spec path/revision: `docs/specs/INIT-001_Repo_Initialization.md` rev 1.0, s4, s5, s8
- PR / Issue: not published (no remote)
- Supersedes / superseded by: none

## Original requirement

INIT-001 s4 lists default tools (React/TS/Vite, npm workspaces, Python 3.12+/FastAPI/Pydantic, uv workspace, PostgreSQL via Compose, SQLAlchemy/Alembic, pytest/Ruff/type checker, TypeScript/ESLint/Vitest, Playwright Python, GitHub Actions) and s5 proposes a concrete layout that "may be adjusted to existing conventions with documented compatibility".

## Decisions / deviations and reasons

| # | Spec default / proposal | Actual | Reason / tradeoff |
| --- | --- | --- | --- |
| 1 | ESLint for TypeScript | **oxlint 1.92** (`apps/web/.oxlintrc.json`, `--deny-warnings`) | The current official `create-vite` react-ts template (Vite 8.3) ships oxlint and TypeScript 7.0. typescript-eslint support for TS 7 was not verified. oxlint implements the same React-hooks/TS rule families. Switch to ESLint later if a needed rule is missing. |
| 2 | Formatter per language | Ruff format (Python), Prettier 3.9 (TS/CSS/JSON in web + contracts) | One formatter per language, as required. |
| 3 | Python type checker | mypy 2.4 `--strict` with the pydantic plugin | Mature with Pydantic; strict mode on all workspace code, scripts and tests. |
| 4 | `packages/contracts/python/strongstart_contracts` | `packages/contracts/python/src/strongstart_contracts` (src layout) | Standard hatchling src layout, so tests import the installed package. Import name unchanged. |
| 5 | "Two or three" Python workspace members incl. a browser-test package | Two members (`services/api`, `packages/contracts/python`). Playwright is in the root `browser` dependency group | No separate package is needed for one smoke test. B2 can promote `services/browser` to a member when a real FormAdapter exists. |
| 6 | Python 3.12+ | `>=3.12,<3.14`, pinned `.python-version` 3.12 (tested 3.12.15) | 3.14 is installed locally but not tested. The upper bound avoids an unverified resolver choice. Raise it deliberately. |
| 7 | PostgreSQL "supported major" | `postgres:17.11-alpine`, host port **127.0.0.1:55432** | PG 17 is a current supported major and is commonly offered by hosted Postgres (Tiger Data compatibility still needs confirming by B1 at deploy time). Port 55432 avoids clashing with a system Postgres on 5432. |
| 8 | Web routing | Tiny hash navigation in `App.tsx` (no router dependency) | Keeps the shell minimal. Dev C owns the shell and can adopt a router later without changing feature folders. |
| 9 | Feature registration | `apps/web/src/features/registry.ts` and `services/api/src/strongstart_api/features/__init__.py` registered once | Lanes edit only their own feature folder for their first tickets (spec s5). |
| 10 | TS type generator | `json-schema-to-typescript` 16.0 from the exported JSON Schema (`packages/contracts/ts/scripts/generate.mjs`) | Small, documented and deterministic. Drift is checked by `make contracts-check` and CI. Property titles are stripped to avoid alias noise. |
| 11 | services/worker, services/browser | README extension points only | No unused service pretends to run (spec s5). |
| 12 | `Agent_Coordination_Guide.md` input | Identical byte-for-byte to the kit's `docs/coordination/README.md`; kept once there | Avoids a duplicate copy. The original input is in ignored `.bootstrap-input/`. |
| 13 | Unknown routes | 404 with `ErrorEnvelope.code = not_implemented` | Keeps every error in the envelope shape. Feature owners may refine this. |
| 14 | Request ID | Always server-generated, returned as `X-Request-ID` | A client-supplied correlation ID is not trusted. |

## Impact and coordination

- Contract consumers (A/B1/B2/C) import `strongstart_contracts` (Python) or `@strongstart/contracts` (TS, generated). Every model carries `x-contract-status` (`draft`/`frozen`) and `x-owner` in the JSON Schema.
- B1 coordinates later changes to `package.json`/`package-lock.json`, `uv.lock`, `infra/compose.yaml`, `.env.example` and CI. Dev A sequences migrations after `0001_bootstrap`.

## Validation and rollback

Validated by `make check`, `make smoke` and `make browser-smoke` (results in the setup report). Each choice is reversible in a normal PR: replace oxlint with ESLint in `apps/web`, add a router, change the Compose image/port and `.env.example` together, or add a workspace member.
