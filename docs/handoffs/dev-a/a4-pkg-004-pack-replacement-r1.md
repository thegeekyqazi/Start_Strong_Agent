# A4 PKG-004: pack replacement and dependency invalidation

- Author/lane: Dev A
- Intended consumers: Dev B (browser grants/jobs), Dev C (answers/checks/approvals/exports/skills)
- UTC timestamp: 2026-11-08
- Status: ready-for-review
- Task spec path/revision: `docs/specs/A4-PKG-004_Pack_Replacement_and_Invalidation.md` revision 1.0
- Engineering version/sections and rule IDs: Engineering Plan v1.1 sections 4.1-4.3, 5.3, 9, 10.5, 10.8, 13.3, 14, 15, 19, 20.3-20.4, 21 and 23.2; PKG-01, PKG-02 and PKG-03
- Branch and exact implementation commit: `dev-a/a4-pack-replacement`; `71f1458`
- PR / Issue links: https://github.com/thegeekyqazi/Start_Strong_Agent/pull/15
- Supersedes / superseded by: consumes the dependency records from `a3c-val-003-numeric-validation-r1.md`

## What works

A4 stores strict immutable pack manifests, resolves their facts, source versions and approved policy hashes inside the authenticated organization, and maintains one optimistic-versioned active pointer per application context. Activation is transactional and serialized at the organization row: it records a canonical A/B change set, finds exact old dependency versions, marks registered mutable consumer currentness stale, records immutable invalidation events, and switches the active pointer. Repeating an already-active transition is idempotent.

The active evidence endpoint returns only the current pack. Direct reads of an A4-managed inactive version fail with a stale-snapshot conflict. Historical A3 receipts remain byte-for-byte replayable; their current/stale state is stored separately. The synthetic fixture `tests/fixtures/demo/a4-pack-replacement.json` replaces a fact and policy while retaining an unrelated fact.

## Contract and dependencies

Public Python, JSON Schema and generated TypeScript contracts include `PackManifestRequest`, `PackManifest`, `ActivatePackRequest`, `ActivePackState`, `DependencyRegistrationRequest`, `DependencyTargetState`, `InvalidationSummary` and `PackActivationReport`. The API exposes manifest create/read, context activation/current evidence, and dependency registration/currentness reads under `/api/knowledge`.

Consumer dependencies use exact `(kind, ref_id, version)` tuples. Supported invalidating pack identities are `fact_version`, `pack_version`, `source_version` and `policy`. Registering a target requires its expected revision and live authorization of those identities. Consumers must re-read target currentness immediately before an action; a historical permission snapshot is not authorization.

C3 durable approvals/exports and B3 browser-grant tables are absent from merged `main`. A4 therefore provides and verifies the real generic persistence seam, but does not claim integration with tables that do not exist. Those owners must register their durable IDs and exact dependencies when the producers land.

## Validation

- `ruff check .`: passed.
- `mypy services packages/contracts/python/src tests`: passed, 133 source files.
- Targeted A4 contracts/API/unit suite: 18 passed.
- Real PostgreSQL migration downgrade `0007 -> 0006` and upgrade `0006 -> 0007`: passed.
- Real PostgreSQL DB suite: 12 passed, including A/B activation, exact invalidation, immutable A3 replay, active-pack gating, cross-organization hiding, stale expected snapshots and idempotency.
- Web Vitest suite under declared Node 22.23.2: 55 passed.
- TypeScript typecheck, generated-contract drift check and production build: passed.
- Repository non-DB suite: 450 passed, 12 deselected, 25 failures. All failures are pre-existing Dev B Windows fixture line-ending/hash or directory-fsync issues in funding/automation; no A4 test failed.
- Repository-wide Prettier check remains red on 52 pre-existing files. Every A4-touched web/generated file passes targeted Prettier; unrelated files were not rewritten.

## Decisions and deviations

No external rules engine or new service was added. The implementation follows the Engineering Plan's strict manifest, exact dependency and immutable-history design. Initial activation and replacement both take a stable organization-row lock because locking a missing active-context row cannot serialize concurrent first activation.

## Consumer action / blockers

Dev C should register answer/check/approval/export/skill IDs when each exact version is created, then block action when the returned target state is stale. Dev B should do the same for pending browser grants and jobs. Both consumers should use the active-context evidence endpoint for new bindings and handle HTTP 409 by refreshing the active snapshot.

Real end-to-end consumer integration remains blocked only by the missing durable C/B producers; the A4 service, API and migration can be reviewed independently.

## Acknowledgments

Pending Dev B and Dev C review.
