# 0006: DATA-001 durable application state

- Status: accepted-maintainer (task scope/ownership); developer-decision (layout below).
- Authority: DATA-001 revision 1.0, project owner, 2026-11-08.
- Baseline: main bc5acd49f4293dccc564653330bbf26c8f8e1767; merged INT-001 #19.
- Branch: data/data-001-tigerdata-application-state, isolated worktree.
- Engineering v1.1 §§2, 4.1–4.3, 5.3, 8.2–8.3, 9.2, 10.5, 12.4,
  13.2–13.3, 14–16, 19–21; APP-04/06/07/08, SEC-01/10/13/14, JOB-02/05;
  preserve AUT-02/03 and PKG-02/03. No general JOB-01/04 claim.

## Inventory and adopted contract

The complete current C port includes versions (question set, rendering/check/dependencies,
A4 binding), decisions, notes, proposals, change sets, exact export metadata/bytes and audit.
The old C3 draft lacks current fields and transaction semantics; do not copy it as-is.
Migration head is 0008_browser_bindings. New additive migration follows that head.

Explicit backend selection: postgres, memory or unconfigured (default unavailable).
Memory must be selected deliberately for local tests; no outage fallback. Example local
DB setup selects postgres. Durability and simulation/reviewer provenance are separate.
Normal production fixture identity/approval/prefill remains prohibited.

Postgres uses a coarse C organization state row with durable epoch/revision and explicit
lineage rows. Lock order: existing organizations parent row, C state, lineage/record.
This serializes C writes within an organization, including first-save initialization, at
the cost of organization-level write concurrency. It preserves A4's parent-first order.
No C lock is held while calling A4/workspace/model/browser or compiling DOCX.

C-owned units of work commit business mutations and their audit together. Prepare expensive
checks outside the transaction; capture expected C state first and recheck under the lock.
A fresh final reader observation must use a new database observation after external checks.
Persistent epochs survive adapters/pools/processes; explicit reset/restore rotates them.
Keep INT-001's memory object-replacement checks, public reader and immutable rendering.

Store nested typed payloads with explicit storage versions, relational scoped references,
exact hashes/bytes and stable ordering. BYTEA exports have a configurable combined-byte
budget. Runtime privileges permit only required operations; no schema-owner/DDL dependency.

## Hosted and recovery boundaries

Owner confirmed no TigerData target is currently available. Implement all independent
code/local tests and opt-in hosted tooling. Hosted TLS/migration/role/restart verification
and hosted restore remain required pending gates, never represented by local tests.
Do not provision resources, rotate credentials, reset shared data or ask for passwords in
chat. Read-only hosted preflight is separate from explicitly selected isolated writes.
Local downgrade/backup/restore tests use separate disposable targets, never the shared DB.

DATA-002 owns durable B/artifact storage and claims. Normal A evidence/policy/A3 integration
is subsequent work. Sawaab owns UI/UX; functional durability labels only. No redesign,
new providers, unrestricted portals, submit/sign/upload, merge or deployment.

## M1 connection/schema evidence

New migration 0009_durable_applications declares nine C-prefixed tables, preserving released
0001–0008. Typed payloads retain the complete current dataclasses/models; scoped relational
keys/indexes enforce lineage, decisions and version-associated notes/proposals. Evidence
references remain logical because fixture IDs need not exist in real A tables.
Full metadata parity also reconciled seven indexes already installed by 0005/0007 but
missing from runtime metadata; no old physical index or released migration was changed.

Connection parsing uses SQLAlchemy URL operations and the Psycopg dialect, preserves escaped
password/query values, forbids alternate endpoint overrides and hides statement parameters.
Hosted profile requires verify-full plus an explicit trust root and configured connection
budget across API processes. Installed clients: SQLAlchemy 2.1.8, Psycopg 3.3.8, libpq 18.6.
System-root support is checked against installed libpq, but no hosted chain is claimed
verified. Existing settings-aware knowledge/validation/seed/migration/readiness paths now
share this profile. Local plaintext is restricted to explicit loopback/local endpoints.

Validation: 11 profile cases and 154 existing unit cases (165 total) passed; 3 real-PostgreSQL
schema tests passed, including full metadata parity, populated 0008 preservation, disposable
rollback/re-upgrade and a non-owner/non-DDL runtime role. The shared DB was not downgraded
or reset: schema tests create/drop only uniquely named disposable databases and test roles.
Runtime role grants include parent-row locking, C state/head updates and append/read C
records; no DDL or table ownership. Data/state CRUD parity is verified at M2.

## M2 implementation and verification

PostgresAnswerStore implements every C port operation without a process cache. Frozen typed
payload version 1 plus relational identities/hashes are validated on reads. SQL units of
work cover saved/staled events, decisions, notes, proposals, change sets and exports with
required audit; external checks/model calls/DOCX compilation precede the commit guard.
Unknown commit outcomes discard the connection and require read/reconciliation, with no
command replay. Note text is no longer duplicated in decision audit metadata: only its
presence is recorded; authorized decision/note application data is preserved.

Real process tests observe pg_blocking_pids and Lock waits before releasing the parent
transaction; events control approval/read/export races. The targeted C predicate mutation
fails specifically on stale_export_publication, restores exact bytes and passes protected.
Test DBs/roles are uniquely created and removed, never shared resets. Commit-fault injection
is explicitly labelled injection; connection termination and timeout tests use real SQL.

## M3 runtime and UI

App construction selects the backend explicitly without connecting/seeding; its lifespan
disposes its owned C pool. The default stays unavailable. Public reader factory permits
new PostgreSQL adapters to address the same dataset; memory replacement protection is
retained. PostgreSQL identity/revision is observed fresh after external checks. Recovery
rotation requires operator UPDATE(epoch), intentionally absent from runtime grants.

Additive optional AnswerHistory.store separates storage from synthetic evidence. Existing
legacy store_is_fixture is retained. Review changes only functional paragraphs. All test
fixtures that need memory now choose it explicitly; production fixture restrictions stay.
Managed INT tests use actual durable C and A4 SQL, isolated per-test databases. Browser CI
now supplies PostgreSQL for the normal runtime restart/Chromium test; no hosted secrets.

## M4 hosted/recovery evidence

Opt-in hosted runner requires exact owner-selected isolated manifest, opt-in, verify-full
trust root, private separate connections and explicit temporary service budget. Read-only
preflight, approved migration, random namespaced synthetic workflow and exact receipt-owned
cleanup are separate phases. Sanitized mode0600 receipts precede writes; failures retain
owned records for reconciliation. The real nonowner C/B workflow/fresh process/SQL lock
contention scenario is verified locally; hosted preflight/TLS/migration/role/restore remain
pending. No hostname-based provenance guess, cloud provisioning or hosted reset path.

Actual local pg_dump/pg_restore into a second empty disposable DB reproduces exact state,
IDs/export bytes/hashes/audit/revision. Operator rotation changes only recovered epoch;
source stays unchanged. Host clients may be used, or existing explicitly local PG container
clients in the local test only. Hosted backup/recovery uses the separate operator runbook.
See DATA-01..42 mapping and final commands in the data handoff. Current main remainsbc5acd4.
