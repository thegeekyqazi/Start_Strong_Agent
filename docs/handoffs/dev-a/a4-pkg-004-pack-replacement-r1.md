# A4 PKG-004: pack replacement and dependency invalidation

- Author/lane: Dev A
- Intended consumers: Dev B (browser grants/jobs), Dev C (answers/checks/approvals/exports/skills)
- UTC timestamp: 2026-11-08
- Status: ready-for-review
- Task spec path/revision: `docs/specs/A4-PKG-004_Pack_Replacement_and_Invalidation.md` revision 1.0
- Engineering version/sections and rule IDs: Engineering Plan v1.1 sections 4.1-4.3, 5.3, 9, 10.5, 10.8, 13.3, 14, 15, 19, 20.3-20.4, 21 and 23.2; PKG-01, PKG-02 and PKG-03
- Branch and exact implementation commit: `dev-a/a4-pack-replacement`; `71f1458`
- Integration base: `origin/main` at `51f19f4` (includes Dev B PR #12); resolved on this branch without merging PR #15
- PR / Issue links: https://github.com/thegeekyqazi/Start_Strong_Agent/pull/15
- Supersedes / superseded by: consumes the dependency records from `a3c-val-003-numeric-validation-r1.md`

## What works

A4 stores strict immutable pack manifests, resolves their facts, source versions and approved policy hashes inside the authenticated organization, and maintains one optimistic-versioned active pointer per application context. Activation is transactional and serialized at the organization row: it records a canonical A/B change set, finds exact old dependency versions, marks registered mutable consumer currentness stale, records immutable invalidation events, and switches the active pointer. Repeating an already-active transition is idempotent.

The active evidence endpoint returns only the current pack. Direct reads of an A4-managed inactive version fail with a stale-snapshot conflict. Historical A3 receipts remain byte-for-byte replayable; their current/stale state is stored separately. The synthetic fixture `tests/fixtures/demo/a4-pack-replacement.json` replaces a fact and policy while retaining an unrelated fact.

## Contract and dependencies

Public Python, JSON Schema and generated TypeScript contracts include `PackManifestRequest`, `PackManifest`, `ActivatePackRequest`, `ActivePackState`, `DependencyRegistrationRequest`, `DependencyTargetState`, `InvalidationSummary` and `PackActivationReport`. The API exposes manifest create/read, context activation/current evidence, and dependency registration/currentness reads under `/api/knowledge`.

Consumer dependencies use exact `(kind, ref_id, version)` tuples. Supported invalidating pack identities are `fact_version`, `pack_version`, `source_version` and `policy`. Registering a target requires its expected revision and live authorization of those identities. Consumers must re-read target currentness immediately before an action; a historical permission snapshot is not authorization.

C3 durable approvals/exports and B3 browser-grant tables are absent from merged `main`. A4 therefore provides and verifies the real generic persistence seam, but does not claim integration with tables that do not exist. Those owners must register their durable IDs and exact dependencies when the producers land. Dev B PR #12's application-publication, funding-review and capture models coexist with all A4 pack models in the Python registry and regenerated JSON Schema/TypeScript contracts.

## Validation

- `ruff check .`: passed.
- `mypy services packages/contracts/python/src tests`: passed, 133 source files.
- Targeted A4 contracts/API/unit suite: 18 passed.
- Real PostgreSQL migration downgrade `0007 -> 0006` and upgrade `0006 -> 0007`: passed.
- Real PostgreSQL DB suite: 12 passed, including A/B activation, exact invalidation, immutable A3 replay, active-pack gating, cross-organization hiding, stale expected snapshots and idempotency.
- Web Vitest suite under declared Node 22.23.2: 55 passed.
- TypeScript typecheck, generated-contract drift check and production build: passed.
- `make contracts` after merging `origin/main`: passed; regenerated artifacts contain both A4 and Dev B PR #12 models and no conflict markers.
- `make check` after the merge: Ruff, Ruff format, Oxlint, Prettier, mypy (170 files) and TypeScript typecheck passed. Pytest reached 536 passed and 91 failed (28 deselected); all failures are in Dev B PR #12's Windows directory-fsync, symlink or hash-sensitive fixture paths. No A4 test failed. The Linux PR checks remain the authoritative full-suite result.
- `make smoke`: passed; Alembic reached `0007_pack_replacement`, the synthetic seed completed, 90 import tests and 12 PostgreSQL smoke tests passed, and live/readiness/capability probes returned 200 with 22 capabilities.
- `make browser-smoke`: production build passed and 12 browser tests passed; four Dev B capture/save tests timed out on Windows. Their test harness intentionally strips inherited `STRONGSTART_*` values before starting the API, so `STRONGSTART_DEV_B_STORE_ALLOW_REDUCED_DURABILITY=true` cannot reach the child process; B's store correctly fails closed where Windows cannot directory-fsync. Linux PR checks remain the acceptance environment for those four tests.

## Decisions and deviations

No external rules engine or new service was added. The implementation follows the Engineering Plan's strict manifest, exact dependency and immutable-history design. Initial activation and replacement both take a stable organization-row lock because locking a missing active-context row cannot serialize concurrent first activation.

## Consumer action / blockers

Dev C should register answer/check/approval/export/skill IDs when each exact version is created, then block action when the returned target state is stale. Dev B should do the same for pending browser grants and jobs. Both consumers should use the active-context evidence endpoint for new bindings and handle HTTP 409 by refreshing the active snapshot.

Real end-to-end consumer integration remains blocked only by the missing durable C/B producers; the A4 service, API and migration can be reviewed independently.

## Acknowledgments

Pending Dev B and Dev C review.
