# A2a-KNOW-002 artifact/text ingestion checkpoint

- Author/lane: Dev A
- Intended consumers: project owner, Dev B and Dev C
- Date: 2026-11-08
- Status: implementation-checkpoint
- Spec: `docs/specs/A2a-KNOW-002_Artifact_Storage_and_Text_Ingestion.md`, revision 1.0
- Engineering/rules: v1.1 sections 4, 5, 10, 12, 13, 19-20; SRC-01/02/05/06/08/10, SEC-01/04/13
- Branch: `dev-a/a2-know-002-ingestion`

## Implemented contract

`POST /api/knowledge/sources/import-text` accepts bounded UTF-8 `title`/`text`, derives organization and provenance from server identity, stores exact bytes through the A-owned artifact port, and commits a distinct source/version/passage with parser metadata. Fixture-auth imports are explicitly simulated. The new response contracts are `TextSourceImportRequest` and `TextSourceImportResult`.

Migration `0003_artifact_text_ingestion` preserves A1 database-byte rows and supports new `local_artifact` versions. Reads verify either backend before returning source metadata or dependent evidence. The local adapter is not a deployment object store and production ingestion returns capability unavailable.

## Validation at checkpoint

- Ruff check/format: passed for Python/contracts/migrations/knowledge tests.
- Mypy: passed for API, Python contracts, migrations and knowledge tests.
- `pytest tests/knowledge tests/contracts tests/unit -q`: 127 passed.
- PostgreSQL 17 local container: migration `0002 -> 0003` passed; `tests/smoke/test_db_smoke.py -m db -q`: 5 passed.
- Contract generation/check: passed. Local Node 22.13.1 is below the repository's declared Node 22.22.2+, but the contract-only commands completed.

## Boundaries and next work

No B/C feature contract was changed. B's capture store remains separate; a future capture-to-knowledge handoff must preserve B artifact/source identifiers. C may consume the additive result contract but should not treat an unverified imported source as approved evidence.

Next A2 work: PDF signature/size containment, page-level provenance and extraction reports, followed by bounded authorized retrieval. OCR, embeddings, pack activation/replacement and production object storage are not implemented at this checkpoint.
