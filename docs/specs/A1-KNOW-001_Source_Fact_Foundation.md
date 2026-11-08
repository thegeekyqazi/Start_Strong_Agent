# A1-KNOW-001: Source and fact foundation

**Revision:** 1.0  
**Owner:** Dev A  
**Base:** `8df9df8` (`origin/main` after PR #1)  
**Branch:** `dev-a/a1-know-001-source-fact-foundation`  
**Engineering references:** StrongStart Engineering Plan v1.1 sections 4, 5, 10, 11, 13, 18, 19 and 20.  
**Catalog predicates:** SRC-01, SRC-02, SRC-03, SRC-05, NUM-01, NUM-05, SEC-01, SEC-13 and the evidence-contract boundary of PKG-01.

## Outcome

Provide the smallest real Dev A producer path: a server-derived organization can read an immutable, hash-verified source version and an evidence bundle containing a typed, source-linked fact. The Knowledge page exposes the same typed snapshot and clearly labels fixture data.

This revision is the feature-specific contract authorized by the project owner after the initialized repository replaced the old bootstrap assignments. It does not alter Dev B or Dev C feature contracts.

## Required behavior

1. PostgreSQL stores organization-scoped sources, immutable source versions, exact bytes, locators, facts, pack versions and their relationships.
2. Every source read recomputes SHA-256 over the stored bytes. A mismatch withholds the snapshot or bundle and returns a safe integrity error.
3. Facts preserve the exact decimal string, raw value, nullable unit, scope, population, reporting period, status and source reference without float conversion.
4. A locator and fact reference resolve only to the exact source version they name.
5. Unknown and other-organization identifiers are indistinguishable to an API caller.
6. Demo seeding is idempotent, explicitly simulated and derived only from the checked-in fixture bundle plus a checked-in synthetic source artifact.
7. The API derives organization scope from `Identity`; request bodies, headers and query parameters cannot select it.
8. The Knowledge UI has loading, authenticated fixture, empty and safe error states. It does not imply that simulated evidence is supplied or public evidence.

## Public contracts and routes

Additive Dev A contracts:

- `KnowledgeSourceVersion`: source identity, immutable version identity, title, media type, byte size and a complete `SourceReference`.
- `KnowledgePassage`: exact text and locator tied to one source version.
- `KnowledgeSnapshot`: organization-scoped source versions, passages and available evidence bundles.
- `KnowledgeAvailability`: honest authentication/storage/fixture state.

Routes under the existing router:

- `GET /api/knowledge/availability` — no database query; reports whether identity and PostgreSQL are configured.
- `GET /api/knowledge/snapshot` — protected, organization-scoped, integrity-verified snapshot.
- `GET /api/knowledge/evidence/{pack_version_id}` — protected evidence bundle lookup; missing and cross-organization identifiers share one response.

`POST /api/knowledge/packs/import` remains explicitly unimplemented. A later A task owns upload/ingestion and pack replacement.

## Storage contract

Revision `0002_source_fact_foundation` adds sources, source versions, passages, evidence packs, evidence pack versions, facts, fact-source links and pack-fact links. Source-version identifiers are immutable in application code. Exact bytes are retained in PostgreSQL for this bounded foundation so integrity can be exercised without inventing a deployment object store. A later artifact-store migration must preserve IDs, hashes and references and requires a compatibility handoff.

No client path, URL refetch, provider credential, model call or executable document content is accepted in this task.

## Acceptance matrix

| ID | Scenario | Expected result | Catalog predicate |
| --- | --- | --- | --- |
| A1-01 | Seed twice | One copy of each version/link; all records remain simulated | SEC-13 |
| A1-02 | Read source snapshot | Recomputed hash equals recorded hash; locator/version retained | SRC-01, SRC-02, SRC-03 |
| A1-03 | Mutate stored bytes in a test transaction | Content and dependent evidence are withheld with a safe integrity failure | SRC-02, SRC-05 |
| A1-04 | Read typed fact | Decimal string/raw/unit/scope/population/period survive DB-to-contract conversion | NUM-01, NUM-05 |
| A1-05 | Missing and other-org pack | Same status, code and public message | SEC-01 |
| A1-06 | Supply org headers/query fields | Server fixture identity remains `demo-org` | SEC-01 |
| A1-07 | Load Knowledge page | Loading, fixture, empty and error states are distinct | PKG-01 boundary |
| A1-08 | Generate schemas/TypeScript | Additive contracts compile and existing B/C fixtures remain valid | PKG-01 boundary |

## Explicit exclusions and next tasks

- A2: uploads, PDF/OCR/parser provenance, chunks/embeddings and bounded retrieval.
- A3: source/numeric/date validation runner and complete rule-catalog coverage.
- A4: pack activation/replacement and dependency invalidation.
- Dev B: discovery capture and browser automation.
- Dev C: drafting, claims, review, approval, export and practice-skill generation.

Passing A1 tests demonstrates only the predicates in the matrix. It does not claim all source, numeric, security or package checks are complete.
