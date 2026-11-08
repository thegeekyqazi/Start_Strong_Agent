# A1-KNOW-001-postgres-source-bytes: retain bounded source bytes in PostgreSQL

- Author/developer: Dev A
- Date: 2026-11-07
- Status: developer-decision
- Decided/accepted by and evidence: Dev A implementation discretion; owner authorized A work using the initialized project structure.
- Engineering path/version/sections: `docs/engineering/StrongStart_Engineering_Plan.md` v1.1 sections 4, 5, 10, 11 and 18.
- Feature spec path/revision: `docs/specs/A1-KNOW-001_Source_Fact_Foundation.md` revision 1.0.
- PR / Issue: GitHub PR #3
- Supersedes / superseded by: none

## Original requirement

The engineering baseline calls for immutable original artifacts, hashes and source-version lineage, with local/object storage adapters. A1 must exercise real PostgreSQL persistence and integrity checks, but the initialized repository has no Dev A artifact-store configuration or deployment store. Dev B's local capture store is explicitly development-only and B-owned.

## Decision / deviation and reason

A1 retains the one bounded synthetic source artifact as `BYTEA` in PostgreSQL with its exact size and SHA-256. The read repository recomputes both before returning source metadata or dependent facts. No API accepts arbitrary uploads in A1.

This avoids inventing a second local file store, reusing B's private adapter, or claiming a deployment object store exists. The tradeoff is that this schema is not suitable for large PDFs or production artifact volume. A2 must introduce an A-owned artifact-store port before upload/OCR support.

## Impact and coordination

The public `SourceReference`, `EvidenceBundle`, source IDs and hashes are storage-neutral. B/C consumers do not depend on the bytes column. A later migration can move bytes to object storage while retaining source/version IDs, hash, size, media type and locator relationships.

This decision does not replace B1's `CapturedDocumentReader`, and it makes no cross-module contract change. The Dev A handoff will ask B to keep using its local adapter until an explicit capture-to-knowledge import task is specified.

## Validation and rollback

Unit tests cover safe integrity failure and server-derived organization scope. PostgreSQL smoke tests cover idempotent seeding, exact fact reconstruction and tampered-byte rejection. They could not run locally because Docker is unavailable, and passed in PR #3 CI on 2026-11-08.

Rollback is the normal Alembic downgrade before production data exists. Superseding storage must migrate and verify every byte/hash pair before removing the column.
