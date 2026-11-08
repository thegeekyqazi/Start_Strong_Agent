# DATA-001 — TigerData and durable application state

**Revision:** 1.0  
**Date:** 2026-11-08, America/Toronto  
**Status:** Implementation specification; no database provisioning, implementation or live TigerData verification claimed by this document.  
**Engineering owner:** Project owner, responsible for former A/B/C engineering. One coding agent, sequential milestones.  
**UI/UX owner:** Sawaab. Preserve his presentation work and publish narrow functional integration notes.  
**Canonical repository:** `thegeekyqazi/strong-start-agent` — renamed from `Start_Strong_Agent`, same repository ID `1449883367`.  
**Verified main:** `bc5acd49f4293dccc564653330bbf26c8f8e1767`, merged PR #19. Post-merge CI run `42480032541` succeeded.  
**Suggested branch:** `data/data-001-tigerdata-application-state`  
**Repo destination:** `docs/specs/DATA-001_TigerData_and_Durable_Application_State.md`

## 1. Outcome

Persist the Applications/Review workflow in TigerData-backed PostgreSQL while preserving the exact approval/content/currentness contracts delivered by INT-001. Saved answers, decisions, notes, reviewer proposals, applied change sets, exports and audit events must survive API restart and be consistently visible to separate API processes.

The defining demonstration is:

1. Save an answer for a real B-published question set and approve it through the existing C routes.
2. Save its exact identifiers, template/rendered hashes and dependency snapshot.
3. Stop the API process and start a fresh process against the same database.
4. Reopen the same history, approval, notes, audit and stored export bytes.
5. Resolve the same approval through C's public reader with unchanged content and a stable durable producer epoch, if its dependencies remain current.
6. Prepare a **new** B plan and complete the restricted representative-portal read-back.
7. Change the answer from another API process and prove the old approval becomes unusable everywhere.

**TigerData is mandatory.** Local PostgreSQL is the development/CI substrate; a local-only pass does not establish hosted TigerData completion.

## 2. Scope and boundaries

### 2.1 Required work

- Secure, configurable TigerData connectivity using existing SQLAlchemy/Psycopg/Alembic architecture.
- Properly sequenced migrations and metadata for the full current C `AnswerStore` data model, including INT-001 additions.
- A durable PostgreSQL implementation of C's store and transactional service boundaries.
- Database-backed concurrency, consistent approval reads and persistent store identity/revision.
- Correct DI, backend selection, readiness and capability reporting.
- Exact persisted DOCX/audit export bytes with bounded storage and verified hashes.
- Real PostgreSQL tests, independent-process/restart tests, INT-001 regressions and explicit TigerData verification tooling/runbook.
- Operator setup, backup/restore and rollback instructions, with honest verification evidence.

### 2.2 Subsequent increments

This is the first bounded slice of the wider durability/real-evidence work requested by the INT-001 handoff. It does not claim to complete that whole handoff.

- **DATA-002:** durable B definitions/cases/capture metadata/plans/grants/runs/claims, plus persistent source/capture artifact storage. This task does not build a general JobStore, worker lease system or browser retry/resume mechanism.
- **EVIDENCE integration:** normal-runtime A evidence workspace, approved writing-policy provider and complete real-evidence/A3 checks at review/export boundaries. Preserve and retest INT-001's existing bounded managed workspace here; do not promote it to a complete production producer.
- Later: practice generator, scheduled monitoring, authentication/roles, remaining change propagation and deployment.

No database connection setting may enable production fixture approval/prefill. Do not add arbitrary portals, submission/signing/upload, new model providers, a new frontend framework or a parallel approval authority.

**Restart distinction:** C approvals become durable here. B's pending plans still bind the API runtime epoch and use development-only files. Old pending B plans may correctly refuse after restart. Prepare a new plan from the preserved approval. Do not remove B's epoch/single-use controls to make a restart demo pass.

## 3. Verified starting point and source of authority

The current canonical repository is `thegeekyqazi/strong-start-agent`. Old repository URLs redirect; discover and use the current origin rather than cloning a second project.

| Component | Verified state at the pinned baseline |
| --- | --- |
| INT-001 / PR #19 | Merged. Actual C producer reaches B; guarded A4 plan/grant registration and Review handoff are implemented. |
| Database head | `0008_browser_bindings`, following `0007_pack_replacement`. |
| C store | `InMemoryAnswerStore`; process-local lock, per-org revisions, random store epoch. |
| C snapshot | `ApprovalRead(version, decision, revision, epoch)`, deep copied, then checked after external reads. |
| Saved version | Includes exact template, rendered answer/renderer version, check report, dependencies, question-set identity and optional `a4_binding`. |
| Public producer | `applications.public.get_approved_prefill_reader` uses the current C store and `StoreApprovedAnswerResolver`. |
| C3 migration request | Unnumbered, deliberately invalid draft under `docs/handoffs/dev-c/c3-migration-request/`; predates some current fields. Not installed. |
| DB client | Existing SQLAlchemy engine, Psycopg driver, Alembic. `get_engine` currently has pre-ping/connect timeout; no complete hosted profile. |
| Normal evidence/policy | Still synthetic/unmanaged fixture workspace and policy. Managed A4 evidence is exercised through a bounded test workspace. |
| B storage | Development-only local repository. No durable distributed browser claims in this task. |
| Authentication | `none` or local fixture identity. Production fixture identity is forbidden. |
| UI/UX | Sawaab owns presentation; his separate redesign is not claimed integrated by PR #19. |

The merged handoff records 782 Python tests, 100 Vitest tests, 46 PostgreSQL smoke tests and 38 Chromium tests passing. Treat those as baseline evidence, not new test results or exact counts to preserve.

Read before coding:

- Current `AGENTS.md`, applicable directory guidance, `docs/coordination/ownership.md` and decision `0005-int-001-engineering-takeover.md`.
- Engineering Plan v1.1 §§2, 4.1–4.3, 5.3, 8.2–8.3, 9.2, 10.5, 12.4, 13.2–13.3, 14–16, 19–21.
- Current check catalog: APP-04/06/07/08, SEC-01/10/13/14, JOB-02/05; preserve AUT-02/03 and PKG-02/03 consumer behavior. General JOB-01/04 completion is outside this task.
- INT-001 spec revision 1.1, final handoff, manual guide and UI contract under `docs/handoffs/integration/`.
- C3 spec and migration draft; current C store, approval/resolver, snapshot, exporter, audit and review routes.
- Current DB metadata, Alembic environment, seed command, readiness checks, environment template, Makefile and CI.

The accepted engineering/task contracts and current code outrank the old draft migration and advisory research examples. A repository mismatch is a reason to reconcile the design, not blindly copy historical files.

## 4. Repository workflow and ownership

1. Inspect current branch/status/worktree and fetch upstream. Preserve uncommitted work. Begin on a fresh task branch from the current agreed main, reconciling newer changes if present.
2. Commit this spec and a task decision first. The pinned SHA is a reference, not permission to reset the working copy to it.
3. Implement sequentially with one coding agent. The owner now controls A/B/C engineering and migration sequencing; do not wait for absent former lane owners.
4. Maintain feature boundaries: B uses C's public reader; consumers use knowledge's public currentness facade. No private table access across features or loopback HTTP bridges.
5. Do not overwrite Sawaab's styles, page redesign or package/lockfile work. Only change UI capability/data labels needed by this task; document component/prop changes in a handoff.
6. Make coherent commits citing this task and engineering sections. Regenerate contracts from Python if changed; preserve all unrelated merged models.
7. Finish implementation/tests/handoffs and publish a draft PR under repository policy. No direct default-branch push, force-push, automatic merge or deployment.
8. Do not send cross-PR comments or messages unless requested. Repo handoffs and the PR description provide the coordination record.

## 5. TigerData connection profile

### 5.1 Reuse the existing stack

TigerData accepts PostgreSQL clients. Keep SQLAlchemy + Psycopg + Alembic, the current Python/package namespaces and existing normal PostgreSQL tables. No second ORM/database, forced time-series schema, mandatory hypertables, new vector engine or vendor-only approval algorithm.

Continue using the existing server-only `STRONGSTART_DATABASE_URL` interface. Document how the TigerData PostgreSQL URL is adapted to the installed Psycopg SQLAlchemy dialect without dropping connection/query parameters. Parse URLs with the supported URL library; do not split credentials on `:`, `@` or `?`. Preserve percent-encoded passwords and test reserved-character handling.

Cloud control-plane API credentials are not required to run ordinary SQL. Do not request or create them just to connect to the database.

### 5.2 Transport, timeouts and pool limits

- For TigerData, require a TLS profile that validates the server certificate and hostname, normally `sslmode=verify-full` with the provider's applicable CA/system-root configuration. Confirm installed libpq support and actual certificate chain; do not assume a CA path.
- Plaintext may remain an explicit local-PostgreSQL profile for existing CI. Cloud mode must not silently fall back to plaintext, weaker verification or a different host.
- Add bounded connect, pool wait, lock and statement timeouts appropriate to short application transactions. Keep existing operational defaults where adequate and document any new settings/units.
- Bound pool size/overflow, account for the number of API processes, and retain stale-connection recovery. Do not guess TigerData plan connection limits; use the actual configured service budget.
- Do not hold DB transactions/connections during model/provider calls, DOCX generation or browser execution. Close/dispose owned resources in tests and shutdown.
- Use supported direct connection semantics first. Add a pooler only after verifying the selected endpoint and its transaction/session behavior against required tests.

### 5.3 Credentials and authorization

Keep credentials out of frontend builds, URLs shown to staff, logs, screenshots, exceptions, PRs and test reports. SQL logs must not expose bound answer content. Disable SQL echo and use sanitized errors; hide sensitive parameters where appropriate.

Separate migration privileges from the runtime application role in the runbook. The runtime role needs only the approved application operations. It must not need schema ownership, superuser access or DDL. Test against a non-owner runtime role locally and on TigerData where available. API organization checks remain mandatory; do not claim row-level security without configuring and testing it.

Do not provision paid services, change a service plan, rotate existing credentials or reset a shared database in this task. Use the owner's explicitly selected development/test TigerData target. If configuration is unavailable, finish all independent implementation/local checks and report the exact pending live gate (§14).

## 6. Backend selection and provenance

Introduce explicit backend selection, preferably `STRONGSTART_ANSWER_STORE_BACKEND=postgres|memory|unconfigured`, with validated settings and a documented default.

- The example database-backed local setup selects `postgres`.
- Memory is an explicitly selected local/test fixture backend; never an outage fallback. Update test fixtures to request it deliberately when they do not need a database.
- Postgres selected without a URL, with a missing migration or with a failed connection is unavailable. Never create an empty in-memory store to hide that condition.
- Unconfigured is unavailable with a useful, sanitized reason.
- Production cannot use memory/fixture identity. A configured durable store does not make unsupported workspace/authentication/review/prefill capabilities available.

**Durability and provenance are different properties.** An approval persisted in TigerData by the fixture identity is still a fixture approval. Its answer may still contain simulated data. Do not set all provenance to `supplied` because the adapter is durable, and do not describe a durable store as process-local simply because its content is synthetic.

Preserve public compatibility where possible. If the current `is_fixture` flag conflates backend and data identity, add explicit backend/durability metadata and derive approval provenance from the saved reviewer/answer/workspace facts. Preserve existing labels and tests. Any contract addition must be generated and consumed together.

## 7. Durable data model and migration

### 7.1 Sequence from actual current head

Inspect `alembic heads` and current upstream. At this baseline the next revision would follow `0008_browser_bindings`; choose an unused revision ID after inspection. Keep one linear head and update `REQUIRED_MIGRATION_REVISION`/readiness accordingly.

The old C3 draft is input material, not a migration to copy unchanged. In particular it lacks current question-set/A4 fields, a complete export-result payload and durable revision/epoch semantics. Reconcile every current store field and read/write operation.

Do not change released migrations to create the new schema. Use additive forward migration(s). Test fresh install, upgrade from populated 0008 and schema metadata parity. Keep a reviewed rollback procedure; downgrade tests that drop new data run only on disposable test databases, never the owner's shared/live target.

### 7.2 Required logical tables

Names may follow current conventions; document any differences.

| Entity | Required persisted content / constraints |
| --- | --- |
| Store identity/state | Durable dataset/organization epoch and monotonic approval-relevant revision. Concurrent initialization is safe. |
| Answer lineage/head | Organization and exact existing question lineage, latest version/revision. Provides a stable serialization row even before the first answer version. |
| Answer versions | Every `StoredVersion` field: exact question/question-set identity, bundle, text/hash, rendering/renderer version, checks/time, dependencies/snapshot, actor/time and optional managed `a4_binding`. Immutable version IDs and unique positive version numbers within current lineage semantics. |
| Decisions | Every `StoredDecision` field; one decision per exact version, unique approval ID, decision enum, exact hashes and reviewer/fixture/acknowledgment fields. |
| Notes | Full typed note, exact answer version, author/time and organization. |
| Reviewer proposals | Full validated proposal with role/provider/provenance data, exact answer version and organization. A proposal never becomes an approval. |
| Applied change sets | Full typed payload, stable change-set ID/hash/time and organization. Exact replay is idempotent; same ID with changed payload is rejected. |
| Exports | Full `ExportResult` metadata, exact DOCX/audit bytes, their hashes, relevant snapshot/version identity and organization. |
| Audit events | Complete event, actor/action/object/version/decision/time and already sanitized details, organization-scoped and append-only through the application. |

Use tenant-consistent composite references for C-owned entities: a foreign answer version must not be attachable to another organization's decision/note/proposal. Enforce unique IDs and positive versions at the database layer, not only in Python.

Preserve the current `(organization_id, question_id)` history/numbering semantics unless a documented compatibility change is necessary. Persist `question_set_id` inside each version; do not silently start a different history because its definition was revised. Demo/null question sets remain readable but cannot impersonate B-published questions.

Existing fixture evidence IDs may not correspond to durable A rows. Do not fabricate approved knowledge records to satisfy a new foreign key. Keep those logical references honestly labelled and validated through the workspace contract; use physical evidence constraints only where valid for the managed producer.

### 7.3 Exact values and validation

- Preserve template/rendered text exactly, including Unicode, spaces and CRLF. No trimming, newline conversion or re-rendering on load.
- Preserve array order where meaningful, including dependency lists, bindings and findings. Hash canonicalization must use existing versioned functions.
- Preserve exact decimals as defined by contracts; do not route authoritative values through binary floats or locale-dependent parsing.
- Serialize typed nested contracts through their supported format and validate on read. Record an explicit stored payload schema version where necessary. Do not use pickle or executable serialization.
- Verify important content/rendered/snapshot/export hashes before authorizing use or returning stored binary content. Inconsistent/corrupted/unknown-version records fail closed and produce sanitized diagnostics.
- Retain timezone-aware timestamps and required provenance. Restoring a value from JSON must not quietly replace missing fields with current facts or current policy.

Index the actual scoped access patterns: version history/latest, exact version, approval lookup, scoped audit order, notes/proposals and exports. Replace C's approval-ID full-history scan with a scoped indexed lookup where possible.

## 8. Transactional store and service boundaries

Implement `PostgresAnswerStore` behind the existing C port, splitting modules if needed. Keep the in-memory fixture implementation for explicit no-DB tests. Consumers continue using C public factories.

Transactions must cover **the business operation**, not just each individual store method. Current services append a version/decision/export and then call `audit.record` separately. Simply giving each call its own transaction would permit unaudited committed state.

Introduce a bounded unit of work or equivalent C-owned operation boundary so successful state changes and their required audit events commit together:

- save version + lineage/revision update + required saved/staled audit;
- decision + revision update + decision audit;
- note/proposal + required audit;
- applied change set + revision update + required change/staleness events;
- stored export + complete result/bytes + export-created audit.

An audit insert or final write failure rolls back the corresponding operation. Blocked-action audit is a separate committed event when no state change occurs; do not report that event as persisted if storage failed. Never return success before commit.

Perform expensive/model/external work before the short commit phase. Pass frozen checked values and expected revisions into the commit phase, recheck applicable C version/revision/hash predicates and reject conflicts. Do not keep an open transaction across `await` on a model or provider call.

If connection loss leaves commit outcome uncertain, do not automatically replay a non-idempotent command or pretend it rolled back. Return a sanitized unknown/unavailable outcome consistent with the error contract and instruct a read/reconciliation. This task does not add a general command/job deduplication system.

## 9. Concurrency and approval currentness

### 9.1 Writes across processes

- Concurrent saves using the same expected latest version produce one committed successor and one conflict. Protect first-version creation too; an absent head row is not a lock.
- Concurrent decisions for the same version produce one decision and one conflict, including approve-versus-reject races.
- A decision racing a new version must not commit as a current approval of an already superseded version. Check latest/expected revision inside the write transaction.
- Revision increments are transactional and committed with the mutation. Failed writes do not advance the committed revision.
- Use row locks/CAS and database uniqueness as the actual authority. Python mutexes, process globals and per-worker caches cannot enforce cross-process consistency.

A coarse per-organization state row is acceptable for this increment; document the serialization cost and use bounded lock waits. Define lock order. If a path also needs A4 locks, preserve INT-001's organization → context → target ordering and never acquire it in reverse through a hidden callback. Prefer two-phase snapshot validation rather than holding C locks during external currentness checks.

### 9.2 `ApprovalRead` and revision recheck

Provide a consistent transactionally captured version/decision/revision/epoch. Validate exact relationships and hashes. Return deep immutable values. After the existing external workspace/currentness checks, `approval_read_current` must use a fresh database observation of epoch/revision, not the same repeatable-read snapshot, a cached result or the same Python object.

An event-controlled mutation committed by another process between capture and final check must be observed and refused. Preserve the shared predicate used by metadata and content readers; do not bypass `StoreApprovedAnswerResolver` to make persistence easier.

The public factory currently uses app-store object identity to detect replacement. Adapt it for logical durable-store identity: connection-pool recreation and another app instance must not revoke every approval, while an actual dataset reset/restore epoch change must. Do not remove the in-memory store-replacement protection.

### 9.3 Durable epoch

- Stable across ordinary app restart, pool recreation and multiple workers using the same dataset.
- Persisted and initialized transactionally; never a fresh random value per store object/request.
- Rotated by an explicit, documented incompatible dataset reset/restore procedure, not by a connectivity failure.
- Scoped so another tenant cannot obtain or alter its approval state.

Keep B's independent runtime epoch and single-use claims intact. Do not promise multi-worker browser execution while B files/claims remain outside this task.

### 9.4 External dependencies

Persisting approval does not make its dependencies permanently valid. Keep live question revision, fact/policy/rule snapshot, managed binding and A4 checks. After restart, inaccessible/unconfigured evidence or a stale pack means the approval is stored historically but unusable for a new action.

This task improves C transaction consistency. It does not claim a distributed transaction spanning B files, evidence providers, model calls and a browser DOM. Preserve INT-001's repeated pre/post checks and exact guarded A4 registration.

## 10. Durable exports and audit

For this bounded increment, persist generated DOCX and JSON audit bytes in PostgreSQL `BYTEA` through the C store. This is a deliberate bounded application-export choice, not the final storage design for large source PDFs/captures in DATA-002.

- Introduce a documented configurable maximum export size and enforce it before commit/response; it is an engineering budget, not a funder rule.
- Store full result metadata and the exact bytes/hashes in the same operation. An oversized/failed export cannot leave half a record or a success audit.
- Downloads remain identity/organization scoped and return stored bytes; do not regenerate the DOCX with a newer renderer or facts.
- Verify download hashes. Historical bytes and synthetic/fixture/review labels remain unchanged across restart.
- Prepare exports from a coherent C snapshot. If required approval/latest-version state changes during compilation, reject a newly published reviewed export at the commit guard. Do not hold row locks while compiling DOCX.
- Preserve reviewed-export gates. Persisting a historical file does not certify it is currently approved; do not add a new `ready` flag that bypasses current checks.

Audit rows must be complete, append-only through supported operations, deterministically ordered and sanitized before persistence. Do not store database passwords/connection URLs or raw submitted answer text in audit details. Existing authorized note/proposal/answer fields remain application data; audit metadata is not a duplicate content repository.

## 11. Runtime wiring, health and UX

- Save/review/export routes and `applications.public.get_approved_prefill_reader` must receive the same selected durable dataset through DI. They may have different adapter instances; correctness must not depend on shared Python memory.
- No store auto-creation/seeding on a GET. Initialization of a missing epoch/state row occurs only through a controlled, idempotent path.
- Do not run migrations automatically inside API requests or each worker startup. Use the explicit migration entry point.
- Readiness must reject a missing/outdated application schema, unreachable DB or required configuration failure without exposing credentials. Liveness should still describe process availability.
- Report store backend/durability separately from evidence simulation and supported application capabilities. Add labels only where needed; keep Sawaab's presentation intact.
- Preserve public route names and core payloads. Add/version fields only when required, regenerate models/schema/TypeScript together, and test old INT-001 consumers.
- Do not erase local `.env` or existing data. Example configuration uses placeholders; test failures may not print the connection string.

## 12. Required test environments

| Environment | What it establishes |
| --- | --- |
| Explicit memory fixtures | Existing pure unit/contract/negative tests and memory-specific replacement semantics. |
| Real local PostgreSQL | Migration, constraints, store contract parity, transactions, separate connections/processes, outages and restart survival. SQLite/mocked SQL is insufficient. |
| Existing INT-001 managed tests | Actual A4 SQL producer, actual C reader and B registration/currentness still work with the durable backend. Controlled browser actuators remain labelled. |
| Real API + Chromium | Durable C save/approve/reopen, restart, new B plan, exact entry/read-back and historical receipts. |
| Explicit TigerData target | Same migration/store/restart/currentness checks and sanitized TLS/role evidence against the hosted service. Local PostgreSQL results are not substituted. |

Extend CI's real PostgreSQL job to run the new durable suite. Keep no-secret default tests offline. Hosted tests are explicit opt-in; no live credentials in ordinary PR jobs or fork workflows.

## 13. Deterministic acceptance matrix

Map every task ID to committed tests/evidence in the handoff. These are acceptance IDs, not additions to the 86-rule catalog.

| ID | Required result |
| --- | --- |
| DATA-01 | Explicit backend selection; memory allowed only when deliberately selected for local/test fixtures. |
| DATA-02 | Selected Postgres with missing URL/schema/DB fails closed; no fallback/empty success store. |
| DATA-03 | Cloud TLS profile validates hostname/certificate; unsafe/missing configuration is rejected. Local plaintext profile remains explicitly local. |
| DATA-04 | Reserved characters in credentials/URL parameters survive parsing; logs/errors/reports/frontend contain no DSN/password. |
| DATA-05 | Fresh database upgrade and populated 0008 upgrade reach one actual head; A4 metadata and existing rows remain intact. |
| DATA-06 | Disposable downgrade/re-upgrade path is tested/documented. Readiness rejects outdated schema; no shared target reset. |
| DATA-07 | All `StoredVersion` fields round-trip, including question-set ID, renderer version, check report and `a4_binding`. |
| DATA-08 | Unicode, leading/trailing spaces, CRLF, exact decimals, timezone-aware timestamps and meaningful array ordering survive unchanged. |
| DATA-09 | Content/rendered/snapshot integrity mismatch, malformed nested payload or unknown storage version cannot authorize reading as usable content. |
| DATA-10 | Version/decision/note/proposal/export/change-set/audit reads are organization scoped; unknown and foreign IDs behave identically. |
| DATA-11 | Database constraints reject cross-org C references, duplicate version numbers/decisions, invalid states and nonpositive versions. |
| DATA-12 | Two independent connections saving the first version with the same expectation yield one success and one conflict. |
| DATA-13 | Two separate processes saving the next version yield one successor, no overwrite/gap caused by a failed attempt and one conflict. |
| DATA-14 | Separate-process approve/approve and approve/reject races yield exactly one immutable decision. |
| DATA-15 | Event-controlled new-version-versus-approval race rejects a stale approval commit or commits approval first then correctly stales it after the save. |
| DATA-16 | Failed mutation rolls back answer/decision/head/revision and required audit together; successful operation persists them together. |
| DATA-17 | Captured approval is internally consistent; another process's committed mutation between capture and final check is detected through a fresh revision read. |
| DATA-18 | Ordinary app/pool restart keeps the durable producer epoch; actual explicit dataset-epoch rotation invalidates earlier reads. Memory-store replacement protection still works. |
| DATA-19 | Two app instances resolve identical approval IDs/text/hashes and immediately observe each other's answer edits without a shared Python cache. |
| DATA-20 | Missing/rejected/superseded/corrupted approvals fail the same metadata/content predicate as INT-001. No rerendering under an old approval. |
| DATA-21 | Notes and reviewer proposals survive restart with exact provenance; neither can grant approval or expand permissions. |
| DATA-22 | Change-set application survives restart. Same ID/same payload replay is idempotent; same ID/different payload is refused; dependent approval remains stale. |
| DATA-23 | Export result and exact DOCX/audit bytes/hashes/labels survive restart; scoped downloads verify hashes and reject corrupted bytes. |
| DATA-24 | Export-size/write/audit failure cannot leave half an export or false success. Concurrent edit during reviewed export compilation prevents stale publication. |
| DATA-25 | Audit events remain complete/redacted/scoped with stable ordering. Provider secrets and database credentials are excluded. |
| DATA-26 | Lock/statement/pool timeouts yield bounded sanitized errors and release resources. Another connection can operate after rollback. |
| DATA-27 | A dropped connection recovers for later reads without switching stores; uncertain write commit is not automatically duplicated or falsely reported as rolled back. |
| DATA-28 | Runtime app role performs required operations without schema-owner/DDL privileges. The migration role is documented separately. No untested RLS claim. |
| DATA-29 | Persistent storage does not erase synthetic/fixture labels or enable production fixture identity/approval/prefill. |
| DATA-30 | Runtime API restart reopens history/notes/approval/audit/export and resolves the same usable approval with identical template/rendered/snapshot hashes. |
| DATA-31 | After restart a newly prepared B plan uses the durable approval and real Chromium final read-back; old pending B plans retain their existing epoch refusal. |
| DATA-32 | Real A4 replacement still blocks managed pending work and historical replay remains unchanged with durable C storage. |
| DATA-33 | Existing INT-001 single-use, registration-race, stale-state, unknown-write, hostile-page/canary and resource-cleanup regression tests pass. |
| DATA-34 | Independent-process contention is actually observed; no fixed sleeps/unfinished Future/`Queue.empty()` used as proof of reaching the lock. |
| DATA-35 | A targeted temporary mutation disabling the chosen C serialization/commit guard makes its concurrency test fail for the intended invariant; exact source is restored and protected rerun passes. |
| DATA-36 | Backend contract tests cover memory and Postgres semantics; intentional differences in epoch/durability/provenance are documented. |
| DATA-37 | Python/schema/TypeScript registrations remain coherent; capability/UX labels accurately separate storage durability from simulated evidence. |
| DATA-38 | Opt-in hosted runner refuses an unspecified/shared/destructive target and does not run local Compose/reset actions or print secrets. |
| DATA-39 | Explicit TigerData run verifies migration, TLS, durable C round-trip, restart/new-client reads, cross-client conflict/currentness and non-owner role where configured. Pending prerequisites are reported honestly. |
| DATA-40 | A database backup restores into a separate disposable target and reproduces selected IDs/hashes/bytes/revisions; explicit restore-epoch policy is verified without touching the source. |
| DATA-41 | Public factory and normal routes select the same logical durable dataset across new adapter instances, preserving C/B public interfaces. |
| DATA-42 | Manual guide and final report distinguish implemented, local-verified, TigerData-verified and remaining B/evidence/auth/deployment work. |

Use deterministic clocks/events/barriers and real transaction/lock observation where needed. A process that has not reached its lock is not contention evidence. Ensure bounded waits, exit-code checks and owned-resource cleanup in failure paths. Do not kill unrelated services or browser processes.

## 14. TigerData verification gate and operator handoff

Provide a clearly named opt-in command, for example `make tigerdata-smoke`, with a Python runner and documented secret input routing. This target must not call the existing `make smoke` blindly: that target currently includes migrations/seed and local assumptions.

The hosted runner must:

1. Require explicit selection of an isolated owner-provided development/test TigerData database/service and an opt-in flag. Sanitize its identity in reports. A hostname substring alone is not proof of service provenance.
2. Separate read-only preflight from permitted migration and uniquely namespaced synthetic test writes. Explain which step changes the selected target. No destructive reset/drop-volume/schema wipe.
3. Verify the negotiated TLS session, applicable verification configuration, server/migration versions and safe runtime-role properties without reporting credentials.
4. Apply approved migrations only to the explicitly selected target, create only owned synthetic fixture rows, test store/currentness/concurrency and reopen from a separate client/process.
5. Clean only its owned fixture records through an explicit test cleanup path. Never broaden production delete permissions merely to simplify a test. Retain evidence needed to reproduce a reported failure.
6. Restore a backup only into another disposable target, never over the source. Record exact selected IDs/hashes and restore-epoch behavior.

Test clients must use the actual configured hosted PostgreSQL/libpq versions. Do not assume TigerData runs the same major release as local PostgreSQL 17. Do not assume a plan's backup/PITR/pooler features without checking the actual service.

If the owner has not supplied the isolated connection/role configuration, complete all code, local DB/browser tests, dry-run/preflight tooling and docs first. Publish the reviewable PR with **TigerData verification pending** and a precise short list of missing inputs. No fabricated service, request to expose passwords in chat or claim of full DATA-001 completion. Hosted verification remains a required gate, not an optional sponsor extra.

## 15. Backup, restore and rollback

Create a runbook covering:

- Migration versus runtime connection configuration, without embedded credentials.
- A non-destructive backup procedure suitable for the selected service/schema and installed tools; use an operator-approved ignored/private destination.
- Restore into an isolated destination, exact hash/row checks, deliberate dataset-epoch policy and how stale work is handled after recovery.
- App rollback constraints: old code may not understand the new backend; preserve data and disable affected routes if needed. Do not fall back to empty memory.
- Shutdown/restart and pool cleanup; readiness failure handling; no automatic destructive repair.

Current TigerData documentation describes PostgreSQL-client connections and separate backup/recovery facilities. Their availability/configuration on the selected account must be verified; a written runbook is not a performed restore.

## 16. Milestones

### M0 — Inventory and contract decision

Commit the spec and task decision. Reconcile actual store fields, existing C routes/audit transactions, INT-001 public contracts, current migration head and Sawaab's active work. Define backend selection, durable epoch/revision, lock order, transaction ownership, payload versions and hosted verification inputs. Record what remains for DATA-002/evidence integration.

### M1 — Connection profile and schema

Implement safe connection/configuration, migrations/metadata/indexes and readiness. Test fresh install/populated upgrade, wrong schema and non-owner runtime-role setup. Do not enable production feature flows.

### M2 — Durable store and transactional commands

Implement all C store operations, exact round-trips, guarded first/latest version and decisions, state/audit atomicity, export-byte persistence and revision/epoch capture. Run real PostgreSQL contract/constraint/concurrency tests plus the targeted mutation test.

### M3 — Runtime integration and restart proof

Wire existing routes/public reader to the durable dataset, preserve provenance and adapt process-identity checks. Prove separate-process reads/edits, restart survival, reviewed export guard and normal API/Chromium new-plan read-back. Run INT-001 managed-currentness regressions.

### M4 — Hosted verification, recovery and publication

Finish the opt-in TigerData runner, perform the live gate when the isolated target is configured, prove backup/restore on a disposable target, and publish full checks/manual guide/handoff/draft PR. If hosted credentials are unavailable, publish the completed reviewable code with the explicit pending gate described in §14.

Do not stop after writing migrations or a store class. Deliver the normal route/reader workflow and all available verification. Leave a precise checkpoint if interrupted.

## 17. Verification commands

Discover actual commands and markers first. At final source checkpoint run targeted durable/concurrency tests, then:

```bash
make contracts
make check
make smoke
make browser-smoke
```

Extend the real PostgreSQL smoke/CI path so new durable tests actually execute. A default pytest run excludes DB/browser markers and cannot establish those results. Record the exact commands for mutation, independent-process/restart and hosted tests. Rerun affected checks after source changes; do not recycle prior handoff counts.

Do not run Compose down/reset or fixture cleanup against a TigerData target. Missing PostgreSQL/Chromium/cloud prerequisites are explicit verification gaps, not mocked passes. No paid model/search/capture calls are needed for persistence verification.

## 18. Required deliverables and definition of done

Commit:

- This spec under its repo destination and a task decision under `docs/decisions/`.
- Connection settings, forward migration(s), metadata, durable store and transactional service integration.
- Unit/contract/API/real PostgreSQL/concurrency/restart/browser tests and the temporary-mutation audit runner where appropriate.
- Hosted opt-in runner and a setup/operations guide, for example `docs/setup/tigerdata.md`.
- `docs/handoffs/data/data-001-durable-applications-r1.md` with acceptance evidence for DATA-01…42.
- `docs/handoffs/data/data-001-manual-test-guide.md` with restart, two-process edit, export download, A4 replacement, outage and recovery steps.
- `docs/handoffs/data/data-001-ui-contract.md` for Sawaab's small label/API/state changes; no implied redesign merge.
- Updated current feature matrix/coordination pointers and old C migration-request status pointing to the actual accepted migration.

Final report/PR must identify exact head/branch/PR, spec revision, engineering sections/rule IDs, migrations, producer contracts, deviations, test commands/results, mutation/restoration evidence and unrun prerequisites. Separate local PostgreSQL success from TigerData success. Separate durable C state from B files, real evidence/authentication and production readiness.

DATA-001 is fully complete when the normal C workflow persists through restart, separate processes enforce the same version/currentness rules, exact approval/content/export/audit identities are preserved, required tests pass and the explicit TigerData gate is verified. A local-only implementation can be reviewable/mergeable by the owner with the live gate clearly pending; it cannot be reported as hosted completion.

Do not promote all catalog rules or G2/G4/G5 because these task checks pass. Next: DATA-002 for B/artifact durability, then the full A-evidence/policy/A3 workspace connection, with deployment preparation after the durable foundation.

## 19. Ready-to-paste Codex prompt

```text
Implement DATA-001 revision 1.0 in the existing Strong Start Agent repository.

Read docs/specs/DATA-001_TigerData_and_Durable_Application_State.md in full.
If supplied outside the repo, copy it there first. The canonical repository is
thegeekyqazi/strong-start-agent; PR #19 is merged, baseline bc5acd49.
Inspect current upstream/status and preserve all existing work before branching.

I own former A/B/C engineering. Work sequentially with one coding agent.
Sawaab owns UI/UX; preserve his presentation work and publish narrow functional notes.
TigerData is mandatory. Implement durable C application state, not another database
or an in-memory fallback. Preserve INT-001's public reader, exact hashes, A4 binding,
single-use browser controls and synthetic/fixture labels.

Complete M0–M4: connection/schema, full Postgres AnswerStore, transactional state/audit,
consistent approval reads, stable durable epoch, restart/separate-process tests,
normal API/Chromium regression, hosted verifier and operational handoffs.
Run all applicable acceptance checks and required commands. Record deviations.

Use only an explicitly selected isolated TigerData test target. Do not provision
paid resources, reset shared data or expose secrets. If its configuration is missing,
finish all independent code/local checks and publish the exact pending hosted gate.
Do not claim live verification that did not happen.

Commit coherent milestones, push the task branch and open a draft PR under repo
policy. Do not merge, deploy, force-push or modify the default branch directly.
Report exact commit/PR, tests, remaining limits and next DATA-002/evidence work.
```

## 20. Source links and checked documentation

Repository facts are pinned to main `bc5acd49f4293dccc564653330bbf26c8f8e1767`:

- [Merged PR #19](https://github.com/thegeekyqazi/strong-start-agent/pull/19)
- [Successful post-merge CI](https://github.com/thegeekyqazi/strong-start-agent/actions/runs/42480032541)
- [INT-001 final handoff](https://github.com/thegeekyqazi/strong-start-agent/blob/bc5acd49f4293dccc564653330bbf26c8f8e1767/docs/handoffs/integration/int-001-approved-content-currentness-r1.md)
- [Current C store](https://github.com/thegeekyqazi/strong-start-agent/blob/bc5acd49f4293dccc564653330bbf26c8f8e1767/services/api/src/strongstart_api/features/applications/store.py)
- [Current approval/content resolver](https://github.com/thegeekyqazi/strong-start-agent/blob/bc5acd49f4293dccc564653330bbf26c8f8e1767/services/api/src/strongstart_api/features/applications/resolver.py)
- [Current public factory](https://github.com/thegeekyqazi/strong-start-agent/blob/bc5acd49f4293dccc564653330bbf26c8f8e1767/services/api/src/strongstart_api/features/applications/public.py)
- [Current migration head](https://github.com/thegeekyqazi/strong-start-agent/blob/bc5acd49f4293dccc564653330bbf26c8f8e1767/migrations/versions/0008_browser_bindings.py)
- [Historical, inactive C3 migration request](https://github.com/thegeekyqazi/strong-start-agent/blob/bc5acd49f4293dccc564653330bbf26c8f8e1767/docs/handoffs/dev-c/c3-migration-request/answers_and_approvals.py)

Official external references checked for this spec; implementation must confirm applicability to installed client/service versions:

- [TigerData: connect using PostgreSQL clients](https://www.tigerdata.com/docs/integrate/find-connection-details)
- [PostgreSQL 17: libpq SSL verification](https://www.postgresql.org/docs/17/libpq-ssl.html) — `verify-full` verifies the certificate chain and hostname; configure an applicable trust root.
- [TigerData: backup and recovery](https://www.tigerdata.com/docs/deploy/tiger-cloud/tiger-cloud-aws/high-availability/backup-restore) — verify actual selected-service configuration/features before claiming managed backup or PITR coverage.
