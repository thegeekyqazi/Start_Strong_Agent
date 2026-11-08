# A1-KNOW-001: source and fact foundation handoff

- Author/lane: Dev A
- Intended consumers: Dev B, Dev C and project owner
- UTC timestamp: 2026-11-08T03:30:00Z
- Status: ready-for-review
- Task spec path/revision: `docs/specs/A1-KNOW-001_Source_Fact_Foundation.md`, revision 1.0
- Engineering version/sections and rule IDs: v1.1 sections 4, 5, 10, 11, 13, 18-20; SRC-01/02/03/05, NUM-01/05, SEC-01/13, PKG-01 evidence-contract boundary
- Branch and exact implementation commit: `dev-a/a1-know-001-source-fact-foundation` at `f4323c2503dc463500e011c8202236ce428b17d7`
- PR / Issue links, or not published: pending push/draft PR
- Supersedes / superseded by: none

## What works

Revision `0002_source_fact_foundation` stores organization-scoped sources, exact version bytes and hashes, passages, evidence packs, typed facts and their source/pack links. The repository verifies byte length and SHA-256 before returning metadata or dependent facts. Unknown and other-organization pack IDs share one safe API response.

`seed_demo` now idempotently persists one conspicuously simulated source, passage and historical fact from the checked-in demo bundle. No partner document is present. The exact value `120`, raw value, unit, scope, population and reporting period survive the contract path without float conversion.

The existing Knowledge page now reports availability, fixture state, source version/hash and typed fact fields, with distinct loading, empty and integrity-failure states.

## Contract and dependencies

Additive schema-v1 models are `KnowledgeSourceVersion`, `KnowledgePassage`, `KnowledgeSnapshot` and `KnowledgeAvailability`. Existing `EvidenceBundle`, `Fact` and `SourceReference` shapes remain compatible. Generated JSON Schema and TypeScript declarations are committed.

New routes are:

- `GET /api/knowledge/availability`
- `GET /api/knowledge/snapshot` (identity required)
- `GET /api/knowledge/evidence/{pack_version_id}` (identity required)

`POST /api/knowledge/packs/import` remains 501. Ingestion, parsing, OCR, retrieval, pack replacement and dependency invalidation are not implemented in A1.

Dev B's `CapturedDocumentReader` and local capture store were not changed. A future capture-to-knowledge import contract must preserve B1 capture/artifact/source IDs and hashes and may call an A-owned write port; B should not couple to A1's private PostgreSQL tables. Dev C can continue using the existing `EvidenceBundle` fixture and can additionally inspect the real read route after this PR is integrated and seeded.

## Validation

- `.venv\\Scripts\\ruff.exe check packages/contracts/python/src services/api/src migrations tests/knowledge tests/smoke/test_db_smoke.py` — passed.
- `.venv\\Scripts\\mypy.exe services/api/src packages/contracts/python/src tests migrations` — 68 files, passed after installing the repository's Playwright Python dependency.
- `.venv\\Scripts\\pytest.exe tests/knowledge tests/contracts tests/unit -q` — 101 passed.
- `npm run contracts:check` — passed.
- `npm run typecheck` — passed.
- `npm run lint` — passed.
- `npm run build` — passed.
- `npm run format:check` — passed.

Not run locally: PostgreSQL smoke tests, because Docker/PostgreSQL is unavailable on this machine. The new smoke cases cover migration readiness, seed idempotency, exact reconstruction and tamper rejection and must run in CI.

The Knowledge Vitest file could not start on local Node 22.13.1 because `undici` requires a newer runtime; the repository declares Node 22.22.2+. TypeScript build succeeds, and CI on the declared runtime is the browser-unit gate.

The full Python non-DB run found 12 existing Dev B Windows failures: directory `fsync` via `os.open(directory)` is denied on Windows, and checked-out CRLF artifact bytes no longer match B1's stored hashes. No B-owned files were changed. A-owned/unit/contract tests pass.

## Decisions and deviations

`docs/decisions/A1-KNOW-001-postgres-source-bytes.md` records the bounded PostgreSQL `BYTEA` choice. It is not a production large-artifact design. A2 must add an A-owned artifact-store port before arbitrary upload/PDF/OCR support while preserving source/version/hash identities.

## Consumer action / blockers

- Project owner/reviewer: run CI with PostgreSQL and the supported Node version; review the storage decision and migration.
- Dev B: no code action for A1. Acknowledge that B1 remains on its development store until a separately specified import seam exists.
- Dev C: consume `EvidenceBundle` unchanged; do not treat simulated `needs_review` facts as verified/current.

Real integration is blocked only on PR review, migration smoke and supported-runtime UI tests. No live or partner evidence has been claimed.

## Acknowledgments

Pending consumer review; none recorded by Dev A.
