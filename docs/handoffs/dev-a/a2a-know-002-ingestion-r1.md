# A2 KNOW-002 ingestion and retrieval handoff

- Author/lane: Dev A
- Intended consumers: project owner, Dev B and Dev C
- Date: 2026-11-08
- Status: ready-for-review
- Specs: A2a artifact/text ingestion, A2b PDF ingestion and A2c authorized retrieval, revision 1.0
- Engineering/rules: v1.1 sections 4, 5, 10, 12, 13, 19-20; SRC-01/02/05/06/08/10, SEC-01/04/13
- Branch: `dev-a/a2-know-002-ingestion`

## Implemented contract

`POST /api/knowledge/sources/import-text` accepts bounded UTF-8 `title`/`text`, derives organization and provenance from server identity, stores exact bytes through the A-owned artifact port, and commits a distinct source/version/passage with parser metadata. Fixture-auth imports are explicitly simulated. The new response contracts are `TextSourceImportRequest` and `TextSourceImportResult`.

Migration `0003_artifact_text_ingestion` preserves A1 database-byte rows and supports new `local_artifact` versions. Reads verify either backend before returning source metadata or dependent evidence. The local adapter is not a deployment object store and production ingestion returns capability unavailable.

## Validation at checkpoint

- Ruff check/format: passed for Python/contracts/migrations/knowledge tests.
- Mypy: passed for API, Python contracts, migrations and knowledge tests.
- `pytest tests/knowledge tests/contracts tests/unit -q`: 135 passed.
- PostgreSQL 17 local container: migrations through `0004` passed; `tests/smoke/test_db_smoke.py -m db -q`: 6 passed.
- Contract generation/check: passed. Local Node 22.13.1 is below the repository's declared Node 22.22.2+, but the contract-only commands completed.
- Web lint, formatting, TypeScript and production build passed; after reconciling current `main`/C2, Vitest on Node 22.22.2: 54 tests passed.
- Current-main producer/consumer regression (`knowledge`, contracts, applications and unit): 250 tests passed; strict mypy passed across 120 files.

## Completed A2 additions

`POST /api/knowledge/sources/import-pdf` accepts bounded strict-base64 PDFs, rejects invalid/encrypted/image-only inputs, persists extraction coverage and creates exact `page:N` passages. `GET /api/knowledge/retrieve` performs organization-scoped bounded lexical retrieval and verifies source artifacts before returning inert passages. The Knowledge UI exposes text/PDF import and passage search.

Migration `0004_pdf_extraction_coverage` persists page count, processed pages and complete/partial extraction status. See `docs/decisions/A2b-KNOW-002-pdf-parser-boundary.md` for the local parser and lexical retrieval decision.

## Boundaries and next work

No B/C feature contract was changed. B's capture store remains separate; a future capture-to-knowledge handoff must preserve B artifact/source identifiers. C may consume the additive result contract but should not treat an unverified imported source as approved evidence.

OCR, vector reranking, DOCX/HTML parsing, pack activation/replacement and production object storage are not required A2 paths and remain unimplemented. A3 owns deterministic source/numeric/date validation and permission primitives. A4 owns pack activation and dependency invalidation.
