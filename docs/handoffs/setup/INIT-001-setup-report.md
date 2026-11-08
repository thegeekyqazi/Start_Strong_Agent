# INIT-001: Repository initialization setup report

- Author/lane: INIT-001 setup agent (Claude Code, model claude-opus-5-5) on behalf of the project owner (Dev B)
- Intended consumers: project owner (Dev B), B1 and B2 agents, Dev A, Dev C
- UTC timestamp: 2026-11-08T01:35Z (local 2026-11-07, America/Toronto)
- Status: ready-for-review (local only, not published)
- Task spec path/revision: `docs/specs/INIT-001_Repo_Initialization.md` rev 1.0
- Engineering version/sections and rule IDs: v1.1 s2-5, 9, 14-20, 22-23. Bootstrap boundaries only for SEC-04, PKG-01, SEC-05, SEC-01, SEC-14, SEC-13, SEC-06, SEC-11, JOB-04, AUT-03, JOB-05 (all 86 catalog rules remain `planned`)
- Branch and exact implementation commit: `main`, initial foundation commit (the root commit containing this file; see `git log --reverse | head -1`. A file cannot contain its own commit SHA)
- PR / Issue links: none. No remote is configured
- Supersedes / superseded by: none

## 1. Repository tree, versions and layout deviations

```text
.github/  PULL_REQUEST_TEMPLATE.md  workflows/ci.yml
AGENTS.md  CLAUDE.md(@AGENTS.md)  README.md  Makefile  alembic.ini  pyproject.toml  uv.lock
package.json  package-lock.json  .env.example  .gitignore  .nvmrc  .python-version  .prettierrc.json
apps/web/                      Vite React-TS shell (@strongstart/web)
  src/App.tsx  src/api.ts  src/shell/ApiStatus.tsx  src/App.test.tsx
  src/features/{registry.ts,types.ts,Placeholder.tsx}
  src/features/{knowledge,funding,automation,applications,review,skills}/{index.ts,Page.tsx}
services/api/                  uv member strongstart-api
  src/strongstart_api/{app,config,errors,identity,db,ports,seed}.py
  src/strongstart_api/features/{knowledge,funding,automation,applications}/router.py
services/worker/README.md      extension point only
services/browser/README.md     extension point only (B2)
packages/contracts/
  python/src/strongstart_contracts/  uv member: common, evidence, funding, automation, answers,
                                      validation, jobs, platform, ports, fixtures, fixture_adapters, export
  schema/strongstart-contracts.schema.json   generated
  ts/  (@strongstart/contracts) src/generated.ts generated, scripts/generate.mjs
migrations/  env.py  versions/0001_bootstrap.py  README.md
infra/compose.yaml             local PostgreSQL only
scripts/import_kit.py  scripts/smoke_server.py
tests/  conftest.py  unit/  contracts/  smoke/(db)  browser/(browser)
        fixtures/demo/demo-bundle-v1.json  fixtures/browser/demo-form.html  fixtures/README.md
docs/  engineering/(unchanged baseline + catalog)  decisions/0001,0002,0003,TEMPLATE
       specs/{README,INIT-001_Repo_Initialization}.md  coordination/{README,dev-b-two-agent-plan,ownership}.md
       setup/README.md  handoffs/{TEMPLATE.md,setup/INIT-001-setup-report.md}
.bootstrap-input/ (git-ignored) original ZIP, INIT-001, Dev B plan, coordination guide
```

Runtimes (measured): Node 22.22.2, npm 10.9.7, Python 3.12.15 (via uv), uv 0.12.23, Docker 29.9.2 / Compose v5.6.1, PostgreSQL 17.11 (`postgres:17.11-alpine`, digest `sha256:3540c0362c809df084ffac0ae69fe794515f9de92692f02178bcdce0ef0302ac`), Playwright (Python) 1.64.1 with Chrome Headless Shell 156.0.8078.4 (chromium-headless-shell v1248), GNU make 4.4.1. Host OS: Fedora Linux 44 (kernel 7.2.11).

Locked key dependencies: fastapi 0.162.2, pydantic 2.14.3, pydantic-settings 2.16.2, SQLAlchemy 2.1.8, Alembic 1.20.1, psycopg 3.3.8, uvicorn 0.54.0, pytest 9.2.0, ruff 0.17.4, mypy 2.4.1, httpx 0.28.1. React 19.3.1, Vite 8.3.6, TypeScript 7.0.2, Vitest 5.1.0, jsdom 31.0.0, @testing-library/react 16.3.3, oxlint 1.92.0, Prettier 3.9.10, json-schema-to-typescript 16.0.0. All versions are pinned in `uv.lock` / `package-lock.json`. I did not claim any of them is "latest". Node engine constraints were checked from the installed packages' `engines` fields.

Deviations from the spec's default layout/tools are recorded in `docs/decisions/0003-init-001-stack-and-layout.md`. The main ones are oxlint instead of ESLint (the current Vite template default), the src layout for contracts, Playwright as a root dependency group, DB host port 55432 and hash navigation.

## 2. Commands and results (all run on 2026-11-07)

| Command | Result |
| --- | --- |
| `sha256sum StrongStart_Agent_Repo_Kit.zip` | `d57ed77d...5bcee`, which **matches** the spec reference |
| `python3 -I scripts/import_kit.py <zip> . --expected-sha256 ...` | 9 created, `AGENTS.md` identical, 0 conflicts. No symlinks or executables in the archive |
| `make check` (lint, typecheck, test, contracts-check, build) | exit 0. Ruff/ruff-format/oxlint/Prettier clean. mypy strict: 0 issues in 47 files. **pytest 85 passed** (3 deselected: db/browser). **Vitest 4 passed**. Web build and 2 wheels + 2 sdists built |
| `make smoke` (migrate, seed-demo, imports, db tests, real uvicorn) | exit 0. 28 import tests passed. 2 db tests passed. Real process: live 200, ready 200 (`revision=0001_bootstrap`), capabilities 200 (9 entries) |
| `make browser-smoke` | exit 0. 1 passed: Chromium opened the local fixture, read the preset value back and observed maxlength truncation |
| Clean export (`git checkout-index` into an empty dir) then `make bootstrap && make check && make smoke && make browser-smoke` | all exit 0 (`uv sync --locked`, `npm ci` reproducible) |
| `make contracts-check` after deliberately corrupting `generated.ts` / the schema | exit non-zero with a drift message (both cases), then restored |
| Live shell check: `make dev-api` (fixture auth) + `make dev-web`, then Chromium at `/#/funding` | Header showed "API alive / Database ready / LOCAL FIXTURE MODE". All six features were listed "Planned - not implemented" |
| Stop Postgres while the API runs, `GET /health/ready` via the web proxy | **503** not_ready. Postgres was restarted afterwards |
| Idempotent seed: `strongstart-seed-demo` run twice + `test_seed_is_idempotent` | 1 organization row, metadata `demo-bundle@1` |

Not run / not done:

- GitHub Actions CI has **not run**, because there is no remote. The workflow uses the same commands, but they are untested on Ubuntu runners.
- No dependency/secret/container scanner was run. SEC-11 coverage is limited to pinned lockfiles, SHA-pinned actions and `npm ci` reporting 0 vulnerabilities. That is not a release policy.
- `make db-down` was not exercised. The local Postgres container `strongstart-postgres-1` was left **running** (volume `strongstart_strongstart-pgdata`).

## 3. Services, ports, environment, migrations and contracts

- API `127.0.0.1:8000`; web `127.0.0.1:5173` (proxy `/api`, `/health` → `WEB_DEV_API_PROXY`); PostgreSQL `127.0.0.1:55432` (db/user `strongstart`; local placeholder password only).
- API env names: `STRONGSTART_ENVIRONMENT`, `STRONGSTART_AUTH_MODE`, `STRONGSTART_DATABASE_URL`, `STRONGSTART_DB_CONNECT_TIMEOUT_SECONDS`, `STRONGSTART_CORS_ORIGINS`, `STRONGSTART_GEMINI_API_KEY`, `STRONGSTART_TAVILY_API_KEY`, `STRONGSTART_FIRECRAWL_API_KEY` (the three keys are optional, empty and unused). Compose: `STRONGSTART_LOCAL_DB_PASSWORD`, `STRONGSTART_LOCAL_DB_PORT`. Web (public): `VITE_API_BASE_URL`.
- Migration head `0001_bootstrap` creates `organizations` and `bootstrap_metadata` only. The seed records `demo_seed_bundle = demo-bundle@1`.
- Contract generation: `make contracts` (Pydantic → `packages/contracts/schema/strongstart-contracts.schema.json` → `packages/contracts/ts/src/generated.ts`). Drift is checked by `make contracts-check`.

Full details are in `docs/setup/README.md`.

## 4. Capability status

| Capability | Status | Evidence |
| --- | --- | --- |
| Liveness / readiness (DB + exact migration revision) | **real** | `tests/unit/test_api.py`, `tests/smoke/test_db_smoke.py`, live 503 when DB stopped |
| Capability endpoint, ErrorEnvelope, server request IDs | **real** | unit tests |
| Shared contracts, JSON Schema, generated TS, drift check | **real** | `tests/contracts/*`, `make contracts-check` |
| Kit importer (staged, confined) | **real** (bootstrap input only) | `tests/unit/test_import_kit.py` |
| Demo seed | **fixture-only** (synthetic `demo-org`) | db smoke |
| Identity | **unavailable** by default (protected ops → 401). **Fixture-only** when `STRONGSTART_AUTH_MODE=fixture` (local; rejected in production) | unit tests |
| FixtureCaptureStore, FixtureApprovedAnswerResolver | **fixture-only**, injected deliberately | contract tests |
| Browser readiness (open fixture, read back) | **real** locally | `make browser-smoke` |
| Knowledge, Funding, Automation, Applications, Review, Skills | **not implemented**. API ops return 401 without identity and 501 `not_implemented` with fixture identity | unit tests, shell |
| EvidenceProvider, JobStore, real CaptureStore/resolver | **unavailable** (`Unconfigured*` raises `CapabilityUnavailable`) | contract tests |
| Durable jobs, rule engine, 86 checks, discovery, prefill, approvals | **planned** | none |

Rule boundary coverage. These are narrower than the full rules, and the catalog was not changed:

- SEC-04/SKL-03: archive confinement (traversal, absolute paths, symlinks, executables, unexpected entries and oversize are rejected; edits are not overwritten).
- PKG-01/SEC-05: strict DTOs (bad IDs, float decimals, extra fields, duplicate IDs, dangling links and hash mismatches are rejected). Unknown routes and capabilities are explicit.
- SEC-01/SEC-14: identity comes only from server config. `org_id`/`X-Org-Id`/`approved` from the client are ignored. There is no `approved` field in the contracts. Unconfigured protected operations deny.
- SEC-01/SEC-13: production+fixture configuration fails validation. Fixture resolver lookups are scoped to the organization.
- SEC-06: canary keys are absent from all responses. Known key patterns are absent from repo files. The web source and dist bundle contain no server setting names. A clean scan is not proof that no secrets exist.
- SEC-11: locked, reproducible installs, recorded versions and SHA-pinned actions. There is no scanner or release policy yet.
- JOB-04: readiness is truthful (ready only with DB + required revision). This is not job durability.
- AUT-03: Chromium read-back equality and maxlength truncation are observable on a static fixture. This is not approved prefill.
- JOB-05: schema/TS regeneration is deterministic and drift fails the check. This is not validation-cache invalidation.

## 5. Git, branches, remote, protection

- Repository initialized here with `git init -b main` (the folder was not previously a repo). One local foundation commit on `main`, committed with the existing global Git identity. The global Git config was not modified.
- Remote: **none**. No PR, no push, no GitHub repository created. Branch protection is **not configured**.
- CODEOWNERS is not created because real reviewer handles have not been supplied.

## 6. Ownership and interfaces ready to consume

See `docs/coordination/ownership.md` for the full path table and `packages/contracts/README.md` for the contract inventory. In summary:

- **B1**: `features/funding` (API + web), `strongstart_contracts/funding.py`, common CI/infra/lockfiles. Consumes `CaptureStore` (fixture available), `Opportunity`/`RequirementSet`, fixture `demo-gos`/`demo-gos-req-v1`.
- **B2**: `features/automation` (API + web), `strongstart_contracts/automation.py`, `services/browser`, `tests/fixtures/browser`. Consumes `ApprovedAnswerResolver` (fixture available), `QuestionSet`/`FormMap`/`PrefillAction`, fixtures `demo-gos-questions-v1`, `demo-gos-v1`, `demo-approval-mission-v1`, `demo-change-fact-v2`.
- **A**: `features/knowledge`, `evidence.py`, ChangeSet, migrations after `0001_bootstrap`, `EvidenceProvider`/`CaptureStore`/`JobStore` real producers.
- **C**: shared web shell, `features/{applications,review,skills}`, `answers.py`, real `ApprovedAnswerResolver`.

## 7. Browser readiness, source availability, prerequisites and blockers

- **Browser readiness: ready locally.** Chromium headless shell 156.0.8078.4 is installed in `~/.cache/ms-playwright` (user cache, no system packages). Fedora is not an officially supported Playwright host, but the smoke test passed. CI browser readiness has not been verified.
- **Original sources: absent.** No partner documents (e.g. the sample United Way guide, U09) were in the folder. The question limits in the fixtures are `engineering_derived` from engineering s7 and are not an extraction.
- Remaining prerequisites: a GitHub remote and the owner's authorization to publish; branch protection; reviewer handles for CODEOWNERS; provider keys (only for later B1/C provider work); confirmation of the hosted Postgres major (17 assumed) at deploy time.
- Blockers for cross-machine PR integration: no remote. Nothing blocks local B1/B2 work.

## 8. Clean checkout and separate B1/B2 working directories

```sh
git clone <path-or-remote> strongstart && cd strongstart
make bootstrap && make db-up && make smoke && make check
make browser-install && make browser-smoke     # B2 browser readiness
# From the accepted base commit, one worktree per agent:
git worktree add ../strongstart-b1 -b dev-b/b1-disc-001-foundation <base-commit>
git worktree add ../strongstart-b2 -b dev-b/b2-auto-001-foundation <base-commit>
```

Each worktree needs its own `make bootstrap` (`.venv`, `node_modules` and `.env` are not shared). They share the local Postgres unless a separate Compose project and port are configured (`docs/setup/README.md`). Do not start both write-capable agents in this setup checkout. The B1-DISC-001 and B2-AUTO-001 specs have not been written. No placeholder specs were created.

## Decisions and deviations

- `docs/decisions/0002-dev-b-and-bootstrap.md` (accepted-maintainer: owner decisions from INIT-001 / Dev B plan)
- `docs/decisions/0003-init-001-stack-and-layout.md` (developer-decision: stack/layout choices)

## Consumer action / blockers

- Owner: review and accept this foundation commit as the base. Optionally add a remote and authorize publication. Then write B1-DISC-001 and B2-AUTO-001 against this tree.
- A/C: inspect `packages/contracts/README.md` and the port table. Request contract changes through a PR/decision record.

## Acknowledgments

None yet.
