# A2a-KNOW-002: local immutable artifact adapter for development

- Author/developer: Dev A
- Date: 2026-11-08
- Status: developer-decision
- Engineering path/version/sections: `docs/engineering/StrongStart_Engineering_Plan.md` v1.1 sections 4, 5, 10, 12, 13 and 20
- Feature spec path/revision: `docs/specs/A2a-KNOW-002_Artifact_Storage_and_Text_Ingestion.md` revision 1.0
- Supersedes / superseded by: partially supersedes `A1-KNOW-001-postgres-source-bytes.md` for new ingested sources

## Decision

New text imports store exact bytes through an A-owned content-addressed artifact port. The initial adapter uses an organization-hashed local directory and is available only in local/test environments. PostgreSQL retains hashes, sizes, artifact keys and parser provenance; existing A1 `BYTEA` rows remain readable without rewriting IDs or evidence references.

The API accepts bounded JSON plain text rather than multipart files in this revision. This provides a real vertical ingestion path without introducing a general-purpose upload/parser boundary before PDF signature, containment and page-coverage requirements are specified.

## Consequences and rollback

Identical bytes in one organization share a blob while distinct imports retain distinct source origins. Artifact reads reauthorize organization scope and recompute SHA-256. Production ingestion remains unavailable until an approved private object-store adapter exists.

Migration `0003` is additive for A1 data. Downgrade deliberately refuses while external artifact rows exist, preventing silent loss; those rows must be migrated back to verified database bytes or exported before downgrade.
