# A2b-KNOW-002: bounded PDF parser boundary

- Author/developer: Dev A
- Date: 2026-11-08
- Status: developer-decision
- Specs: `docs/specs/A2b-KNOW-002_PDF_Ingestion.md` revision 1.0 and `A2c-KNOW-002_Authorized_Retrieval.md` revision 1.0
- Engineering: v1.1 sections 5, 12, 13 and 20

## Decision

A2 uses strict base64 JSON transport and `pypdf` behind a bounded parser adapter. Byte, page and extracted-character limits apply before or during extraction; encrypted, malformed and image-only documents fail explicitly. This avoids multipart filename/path handling and does not claim OCR. Exact bytes enter immutable storage only after successful extraction.

The local/test implementation parses in the API process. Production ingestion is disabled, so this does not weaken the plan's requirement for a credential-free resource-limited parser worker before deployment. Enabling production PDF ingestion requires a superseding accepted decision and worker/object-store implementation.

Retrieval uses deterministic PostgreSQL lexical filtering/ranking. Optional embeddings are deferred because they are unnecessary for the required A2 producer contract and cannot determine factual truth or numeric conflicts.

## Compatibility and rollback

Contracts are additive. Migration `0004` adds nullable coverage fields and is reversible. B/C public contracts are unchanged; C can consume the new retrieval response without gaining write, approval or submission permissions.
