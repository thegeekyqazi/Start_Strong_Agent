# A2a-KNOW-002: Artifact storage and text ingestion

**Revision:** 1.0

**Owner:** Dev A

**Base:** `122d407` (`origin/main`)

**Branch:** `dev-a/a2-know-002-ingestion`

**Engineering references:** StrongStart Engineering Plan v1.1 sections 4, 5, 10, 12, 13, 19 and 20.

**Catalog predicates:** SRC-01, SRC-02, SRC-05, SRC-06, SRC-08, SRC-10, SEC-01, SEC-04 and SEC-13.

## Outcome

Add the first real A2 ingestion path: an authenticated organization can submit bounded UTF-8 plain text, the API stores its exact bytes through an A-owned immutable artifact interface, records a source/version/passage in PostgreSQL, and returns complete parser and artifact provenance. Local filesystem storage is a development/test adapter and is forbidden in production.

## Required behavior

1. Artifact writes are organization-scoped, content-addressed, atomic and immutable. Reads recompute size and SHA-256 before returning bytes.
2. Missing and cross-organization artifact IDs are indistinguishable. Client text, titles and IDs cannot select filesystem paths.
3. The initial parser accepts only nonempty UTF-8 plain text within the configured byte limit and rejects NUL characters. It performs no HTML, executable, PDF or OCR parsing.
4. Each accepted import creates a distinct source and source-version origin while identical bytes may share one content-addressed artifact in the same organization.
5. PostgreSQL records artifact key/backend, hash, size, parser name/version, warnings, capture time and one exact `char:0-N` passage locator.
6. Organization and simulation state come from server identity. Fixture identity produces conspicuously simulated records.
7. Reads verify artifact bytes against source-version metadata before exposing source metadata or passages.

## API contract

`POST /api/knowledge/sources/import-text` accepts JSON with `title` and `text`. It returns the generated source, source-version and passage identifiers plus artifact hash/size, parser provenance and warnings. The request has no organization, provenance, path, verification or approval fields.

This route is intentionally not a general upload endpoint. Multipart uploads, PDFs, OCR, page locators, chunking, embeddings, retrieval and pack activation require later revisions with parser containment and coverage tests.

## Acceptance matrix

| ID | Scenario | Expected result | Predicate |
| --- | --- | --- | --- |
| A2a-01 | Store/read bytes | Hash and size are recomputed and match | SRC-02 |
| A2a-02 | Alter stored bytes | Read and dependent knowledge fail closed | SRC-02, SRC-05 |
| A2a-03 | Cross-org read | Same result as an unknown artifact | SEC-01, SEC-13 |
| A2a-04 | Duplicate bytes, distinct imports | Artifact is shared; origins remain distinct | SRC-06 |
| A2a-05 | Empty, oversize, invalid content | Rejected before evidence records are committed | SEC-04, SRC-05 |
| A2a-06 | Successful text import | Version has artifact reference, parser version, warnings and exact locator | SRC-01, SRC-08, SRC-10 |

Passing this matrix does not verify PDF page coverage, quote normalization, OCR, retrieval quality or all project checks.
