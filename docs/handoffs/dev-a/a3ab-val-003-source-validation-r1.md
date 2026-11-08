# A3a/A3b VAL-003: deterministic source validation handoff

- Author/lane: Dev A
- Intended consumers: project owner, Dev B verification owner, Dev C/C2 and future A4
- UTC timestamp: 2026-11-08
- Status: ready-for-review
- Task spec path/revision: `docs/specs/A3-VAL-003_Deterministic_Validation_Runner.md` rev 1.0, implementation record section 20
- Engineering version/sections and rule IDs: v1.1 sections 4, 5, 9, 10.1, 13.2, 14-15 and 19-21; SRC-01 through SRC-10; SEC-01/13 boundaries
- Branch and exact implementation commit: `dev-a/a3ab-val-003-source-validation`; exact commit attached to the PR
- PR / Issue links, or not published: [PR #13](https://github.com/thegeekyqazi/Start_Strong_Agent/pull/13)
- Supersedes / superseded by: implements A3a/A3b from `docs/handoffs/dev-a/a3-val-003-spec-r1.md`; A3c will supersede only numeric/integration status

## What works

- Strict `SourceValidationRequest` and immutable `SourceValidationReport` contracts.
- Additive, backward-compatible `ValidationResult` reason/action/evaluator fields.
- Closed allow-listed SRC-01-10 registry; client input cannot name code or parameters.
- Pure evaluator module with a forbidden-effect import test.
- Server-derived organization/actor scope before source resolution.
- Real A2 PostgreSQL/local-artifact resolution, byte hashing, locators and passages.
- Versioned whitespace-only quote comparison; changed digits fail.
- Capture, extraction, parser provenance, page coverage and artifact-reference findings.
- Duplicate artifact-hash and canonical-URL detection that retains distinct IDs/provenance.
- Source-change findings and complete forward dependency records for A4.
- Immutable evaluation/result/dependency rows and authorized receipt replay.
- Non-disclosing missing/cross-organization API behavior.

Catalog states are `implemented`, not `verified`, pending Dev B's independent fixture review. A pass proves only the named predicate. SRC-04 does not establish semantic support or document authenticity.

## Contract and dependencies

Public A3 models live in `strongstart_contracts.validation` and generated JSON Schema/TypeScript. Existing C2 construction of `ValidationResult` remains valid because new fields are optional.

Routes:

- `GET /api/validation/rules`
- `POST /api/validation/source`
- `GET /api/validation/receipts/{evaluation_id}`

Migration `0005_validation_receipts` adds optional source origin/canonical URLs plus append-only evaluation, ordered result and ordered dependency tables. PostgreSQL/Tiger Data remains the only database. A3 stores identifiers, hashes and typed result payloads, not copied private source bodies.

A4 may query `validation_dependencies` by kind/ref/version. A3 records forward edges but does not activate packs or mark consumer state stale.

## Validation

- Ruff check and format: passed on the full repository.
- Strict mypy: passed, 135 source files.
- A3/contracts/unit target: 153 passed.
- Real PostgreSQL 17 migration downgrade to `0004`, upgrade to `0005`, seed and DB smoke: 10 passed.
- DB coverage includes local artifacts, exact API/receipt replay, byte tampering, cross-org hiding and hash/canonical-URL duplicates.
- Contract schema and generated TypeScript were regenerated; drift tests pass.
- Full Windows non-DB run: 413 passed, 24 unrelated B-owned failures. Failures reproduce in funding/automation fixture storage due CRLF fixture hashes and Windows directory `os.open` behavior; no B files were changed. Linux CI remains the authoritative full-suite check for this PR.

## Decisions and deviations

- Follows accepted decision `docs/decisions/A3-VAL-003-repository-native-validation-kernel.md`.
- A3a and A3b are combined at the owner's request, with SRC-01 retained as an internal checkpoint.
- No external rule engine or new datastore was introduced.
- No C-owned APP/POL semantics were moved.

## Consumer action / blockers

- Dev B: independently review the SRC fixtures and acknowledge whether catalog states may move from `implemented` to `verified`.
- Dev C: confirm the additive `ValidationResult` fields and dependency shape remain compatible with C2/C3. No C migration is required by this PR.
- A4: consume forward dependencies; do not infer that A3 performed reverse invalidation.
- Project owner: merge only after CI and review. A3c can then branch from updated `main`.

## Acknowledgments

None recorded yet. Review/acknowledgment belongs in the PR thread.
