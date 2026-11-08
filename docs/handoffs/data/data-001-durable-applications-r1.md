# DATA-001 durable application state — revision 1.0

**Local implementation/verification complete; TigerData verification pending.** Owner
confirmed no hosted target is available. This is a reviewable durable C increment, not
full hosted DATA-001 completion, production readiness, deployment or completed DATA-002.

Branch `data/data-001-tigerdata-application-state`, canonical repository
`thegeekyqazi/strong-start-agent`. Baseline main `bc5acd49f4293dccc564653330bbf26c8f8e1767`
(PR #19 merged). Sawaab's presentation update reached main at `41a80efc477044203cf94cc44a289c56a50003f3`
during publication; it was inspected and reconciled into this branch without style changes. One agent,
sequential M0–M4. The project owner owns former A/B/C engineering/migration sequencing;
Sawaab owns UI/UX. No other worktree/branch changes discarded, default branch writes,
force-push, merge or deployment. Draft [PR #20](https://github.com/thegeekyqazi/strong-start-agent/pull/20) is published.
Initial verified implementation checkpoint: `d2d76a0232c48cbf6922133837c9cbbd65a562c5`;
post-publication reconciliation preserves current main presentation and reruns required
checks. Exact task branch head/CI are visible in the PR. No PR merge or deployment performed.

Spec: [DATA-001 revision 1.0](../../specs/DATA-001_TigerData_and_Durable_Application_State.md).
Engineering v1.1 §§2,4.1–4.3,5.3,8.2–8.3,9.2,10.5,12.4,13.2–13.3,14–16,19–21;
APP-04/06/07/08, SEC-01/10/13/14, JOB-02/05. Preserve AUT-02/03, PKG-02/03 and INT-001
revision 1.1. No blanket86-rule, general JOB-01/04 or G2/G4/G5 completion claim.

## Milestones and behavior

- M0 `13a5eac`: complete supplied spec copied to docs/specs, decision 0006, ownership and
  implementation baseline recorded on a dedicated current-main worktree/branch.
- M1 `2901600`: strict local/TigerData profiles, bounded pools/timeouts, explicit settings,
  additive0009 schema/readiness, populated upgrade/metadata parity/nonowner role tests.
- M2 `36c6d29`: full PostgresAnswerStore, typed exact payloads, consistent approval capture,
  guarded commands+audit, exports and process/failure/constraint/mutation evidence.
- M3 `ac48f01`: actual normal runtime/public factory, explicit fixture selection, durable
  metadata/UI labels, operator epoch rotation, fresh API/restart/Chromium and managed A4.
- M4 `d2d76a0`: hosted opt-in tooling, actual local backup/restore, complete acceptance/runbooks,
  required final checks and draft PR publication. Hosted execution/restore remain pending.

All C state persists: every version/check/render/dependency/question-set/A4 field,
immutable decisions, exact notes/proposals, full applied change sets, full export result
plus BYTEA bytes/hashes and complete sanitized ordered audit. Unicode/spaces/CRLF and
exact decimal strings are preserved. No re-rendering on load, float conversion or default
facts/policy added. Typed payload storage version1 rejects unknown/malformed/non-roundtrip
nested values and checks content/rendered/snapshot/export hashes before usable reads.

Lock order is organization parent → C state → lineage/record, serializing C writes per
organization. Freeze checks outside SQL; expected epoch/revision is rechecked under the
lock. Required mutation/audit commits together. No model/workspace/A4/DOCX/browser call
runs under a C SQL transaction. A single SQL statement captures version/decision/state;
a fresh SQL observation after external checks detects another process's commit.

Epoch is durable per organization, initialized only on controlled mutation, never GET.
App/pool/adapter restart preserves it. Operator-only recovery rotation increments revision
and appends audit atomically; runtime cannot update epoch. Memory object-replacement
protection remains. Public factory uses logical PostgreSQL selection plus the shared
usable-approval predicate; B still consumes C through the supported public factory.

Default storage is unavailable; explicit postgres/memory selection never falls back.
Missing URL/schema/outage yields sanitized 503. Connection loss at commit discards the
connection, returns commit_outcome_unknown and requires read/reconciliation; no replay or
false rollback claim. Fixture identity/evidence remain synthetic even in durable storage.
Production fixture identity/memory/prefill stay disabled. New optional AnswerHistory.store
backend/durable metadata is generated through Python/schema/TypeScript; 231 baseline schema
definitions retained, 232 now present with only AnswerStoreMetadata added. Review changes
only functional paragraphs. See [UI contract](data-001-ui-contract.md).

## Migration and operational contract

One head `0009_durable_applications`, after 0008; released migrations untouched. Nine new
C-prefixed tables: c_store_state, c_answer_heads, c_answer_versions, c_decisions, c_notes,
c_proposals, c_change_sets, c_exports, c_audit_events. Composite C references enforce tenant
scope; immutable IDs/lineage numbers/one decision and valid states are DB constraints.
Logical fixture evidence IDs intentionally have no fabricated A foreign-key rows. Seven
existing physical indexes from released A migrations were reconciled into runtime metadata.
The old unnumbered C3 migration draft stays inactive and now points to 0009.

Runtime nonowner grants support scoped parent lock, C append/read and state/head updates,
with no DDL/ownership/DELETE/epoch update. No RLS is claimed. Local tests create and drop
only unique disposable DBs/roles. The final normal make smoke path explicitly upgraded the
existing local development DB to 0009 and idempotently seeded demo metadata; it was not
reset or downgraded. No laptop desktop/system configuration or service startup was changed.

[Setup/roles/backup/recovery/rollback](../../setup/tigerdata.md) and
[manual guide](data-001-manual-test-guide.md) cover failure handling and exact verification.
Exports have an 8 MiB default combined byte budget, not a funder rule. Recovery was performed
with actual PostgreSQL tools into a different empty disposable DB, verified exact bytes/
IDs/revisions, rotated only the restored epoch and confirmed the source stayed unchanged.
A downgrade drops C data: it was exercised only on owned disposable DBs. App rollback must
preserve DB/archive and disable incompatible routes, never recreate approvals in memory.

## Acceptance evidence

All rows refer to committed real tests; DB/browser markers run explicitly. Local results
are not substituted for hosted TLS, roles, migration or recovery. `D` paths below are
`tests/smoke/test_data001_*.py`; other paths are spelled out. Tests use actual C services,
B publication and PostgreSQL; controlled fixture workspace/identity/browser actuators are
labelled. No TestApprovals provider substitutes for C in durable integration.

| ID | Status and evidence |
| --- | --- |
| DATA-01 | Local verified: tests/data/test_backend.py, test_connection_profile.py; every no-DB C fixture explicitly chooses memory; default unconfigured; production refuses memory |
| DATA-02 | Local verified: backend missing URL/unreachable tests; Dschema populated0008 normal API rejects missing C schema; readiness exact-head; no fallback |
| DATA-03 | Profile verified: verify-full/root/libpq and local endpoint checks in test_connection_profile.py; **actual hosted chain/TLS session pending** |
| DATA-04 | Local verified: reserved credential/query roundtrip, hidden SQL parameters/repr/config dumps, sanitized outage; Dstore exact-decimal/audit test persists redacted URL/password canary; existing frontend/provider canary suite |
| DATA-05 | Local verified: Dschema fresh full metadata parity and populated0008 preservation; one Alembic head |
| DATA-06 | Local verified: Dschema disposable downgrade/re-upgrade and outdated readiness; no shared reset |
| DATA-07 | Local verified: Dstore complete C route roundtrip plus actual managed INT tests persisting current a4_binding through durable store |
| DATA-08 | Local verified: Dstore Unicode/whitespace/CRLF/exact 12345678901234567890.001230 binding, dependency order, timezone timestamps; typed serialization |
| DATA-09 | Local verified: Dstore text/render/snapshot/unknown-version/malformed nested corruption all fail sanitized; strict nested canonical roundtrip and existing INT predicate corruption cases |
| DATA-10 | Local verified: Dstore scope tests for versions/approval capture, Dfailures foreign/unknown exports/decision/notes/proposals/audit/change-set reads; existing identity API tests |
| DATA-11 | Local verified: Dfailures six actual SQL constraints, exact FK/unique/check SQLSTATE and named state checks; scoped version references and nonpositive versions |
| DATA-12 | Local verified: Dprocesses first-save race with two spawned API/store workers, actual SQL wait observed, exactly one success |
| DATA-13 | Local verified: Dprocesses next-save race, one successor/conflict, contiguous committed versions |
| DATA-14 | Local verified: Dprocesses approve/approve and approve/reject, one immutable decision/audit |
| DATA-15 | Local verified: Dprocesses event-controlled save after approval precheck refuses stale commit; no decision stored |
| DATA-16 | Local verified: Dstore six injected required-audit failures roll back version/decision/note/proposal/change-set/export plus state/revision/audit; successful workflow persists together |
| DATA-17 | Local verified: Dprocesses reader capture barrier, another process commits, final fresh observation refuses approval_changed_during_read; one joined SQL capture |
| DATA-18 | Local verified: Druntime new apps/adapters and real API/pool restart keep epoch; explicit operator rotation invalidates captured read; INT memory replacement tests remain |
| DATA-19 | Local verified: Druntime two normal apps match content/IDs/hashes, separate adapter objects, second-app edit visible; Dprocesses external commit detection |
| DATA-20 | Local verified: full tests/integration/test_content_reader.py + test_prefill_currentness.py regression, Dstore corruption and Druntime stored-but-stale approvals; shared predicate unchanged |
| DATA-21 | Local verified: Dstore and Druntime exact notes/proposals/provenance reopened through fresh real API; proposal never grants approval |
| DATA-22 | Local verified: Dstore exact replay/id conflict; Druntime change-set survives another process restart, one audit on replay and dependent approval unusable |
| DATA-23 | Local verified: Druntime exact export/history/audit survive API restart; Dfailures hash-corrupted download 503 and foreign/unknown behavior; Dstore full result equality |
| DATA-24 | Local verified: Dfailures byte budget/no half export; Dstore injected audit rollback; Dprocesses compilation event + external process edit rejects stale reviewed publication with 409 |
| DATA-25 | Local verified: Dstore ordered complete audit, no submitted-text duplication, persisted DB canary redaction; C3 provider/redaction tests; Druntime exact audit after restart |
| DATA-26 | Local verified: Dfailures real row lock, server statement timeout and pool exhaustion; bounded errors, rollback then new operation succeeds |
| DATA-27 | Local verified: Dfailures terminates only owned connection, pre-ping recovers; explicitly injected commit failure yields unknown/no replay and discards pool connection. Actual ambiguous network-at-commit event is not claimed reproduced |
| DATA-28 | Local verified: Dschema and Dstore nonowner/nonDDL role; Druntime hosted scenario locally runs actual C/public factory/nonowner process contention. **Hosted role gate pending** |
| DATA-29 | Local verified: saved/reviewer/workspace-derived provenance, Dstore/resolver/API production boundary tests; Review unit + restarted Chromium show durability and simulation labels together |
| DATA-30 | Local verified: Druntime actual owned uvicorn stop/start retains full history/notes/proposal/approval/audit/export/epoch/hash identity |
| DATA-31 | Local verified: tests/browser/test_data001_restart.py uses actual restarted API and new B plan, real Chromium selected-field final read-back, exact stored rendering; old plan retains runtime-epoch refusal |
| DATA-32 | Local verified: all tests/smoke/test_int001_joined.py and test_int001_a4.py use actual SQL A4 + durable C; replacement blocks pending work, historical receipt replay unchanged |
| DATA-33 | Local verified: complete INT/automation DB/unit/Chromium suites retain single-use, registration-race, stale/unknown-write, hostile-page/canary and cleanup assertions |
| DATA-34 | Local verified: Dprocesses + scripts/data001_workflow.py measure pg_blocking_pids/Lock for both workers; bounded events/queues/joins, no unfinished-Future/Queue.empty/fixed-sleep proof |
| DATA-35 | Local verified: scripts/verify_data001_commit_mutation.py disables only expected-state predicate, catches stale_export_publication, restores exact bytes/checksum and protected rerun passes; final checksum recorded below |
| DATA-36 | Local verified: Dstore parametrizes real C memory/Postgres workflow; durable new-adapter/restart parity; intentional memory epoch/loss vs durable epoch plus separate provenance documented |
| DATA-37 | Local verified: make contracts/check,231 existing schema definitions preserved + AnswerStoreMetadata, optional history field and narrow Review paragraph/tests |
| DATA-38 | Tooling verified locally: tests/data/test_hosted_gate.py refuses absent/shared/unowned/mismatched targets; exclusive private receipt; no Compose/reset hosted code path; make tigerdata-smoke without target intentionally refuses before connection |
| DATA-39 | **TigerData verification pending**: owner supplied no selected isolated target/roles/root/budget; opt-in runner implements TLS/migration/nonowner/scoped roundtrip/fresh process and observed contention checks. Local scenario is explicitly local PostgreSQL, not hosted evidence |
| DATA-40 | Local verified: Drecovery actual pg_dump/pg_restore into separate empty disposable DB; same IDs/hashes/bytes/revision, deliberate restored-epoch rotation and untouched source. **Hosted restore pending** separate selected destination |
| DATA-41 | Local verified: Druntime normal route/public factory same logical dataset across separate app adapters/processes; existing C/B interfaces retained |
| DATA-42 | Delivered: this mapping, setup, manual/UI contracts, current feature matrix/coordination and historical migration pointer; precise hosted/B/evidence/auth/deployment limits |

## Final check evidence

Final source checks all returned exit 0:

- `make contracts`: generated JSON Schema and TypeScript; no drift; all 231 previous
  definitions retained, 232 total with only AnswerStoreMetadata added.
- `make check`: Ruff/format (328 Python files), strict mypy (233 source files), TypeScript,
  **808 Python tests**, **101 Vitest tests** (15 files), contract drift, web/Python builds.
- `STRONGSTART_DATABASE_URL=<private-local> make smoke`: migration/seed, 114 import checks,
  **85 real PostgreSQL smoke tests**, real API liveness/readiness/capabilities 200.
- `STRONGSTART_DATABASE_URL=<private-local> make browser-smoke`: web build,
  **39 real Chromium tests**, including durable API restart/new B plan/read-back.
- `STRONGSTART_DATABASE_URL=<private-local> uv run python scripts/verify_data001_commit_mutation.py`:
  mutant failed specifically stale_export_publication; exact source restored; protected
  rerun **1 passed**. Restored SHA-256:
  `7898e1406b399e14043439089b37e3f6e2b66da04f930122b399c1cc041a0b0b`.
- `make tigerdata-smoke` with no target intentionally exits 2 before any connection:
  explicit isolated target manifest and opt-in required. Seven hosted-gate unit cases
  and the real nonowner local scenario pass; **no hosted SQL/TLS/restore execution**.

Verification environment: local PostgreSQL 17.11, SQLAlchemy 2.1.8, Psycopg 3.3.8/libpq 18.6,
Python 3.12.15, Node 22.22.2 and installed Playwright Chromium. Logs remain local under
`/tmp/data001-final-*.log`; no passwords/DSNs, raw partner data or binary exports are
committed. The deliberate mutant failure is success evidence for the mutation audit,
not a failing final test suite. Hosted verification remains mandatory and pending.

## Deviations, limits and next consumers

Decision0006 documents compatible engineering choices, not a lowered acceptance contract:
C-prefixed tables; coarse per-org SQL serialization; typed versioned JSON text plus scoped
relational identities; bounded BYTEA exports; durable epoch rotation; optional additive
metadata preserving the legacy flag. Note text stays authorized application data but is
removed from duplicate decision audit metadata, as required by this spec's privacy rule.
Tests now assert that stronger audit property. Seven metadata index declarations correct
existing released-migration parity. Existing assertions were not weakened to simulate
integration. Hosted gate deferral is explicitly authorized because no target exists.

TigerData inputs still needed privately: owner-selected isolated service/database and
actual connection budget; separate migration/runtime nonowner role connections; applicable
verify-full trust root; separate disposable restore target and operator backup/PITR choices.
Use staged preflight/migrate/verify/cleanup and record actual TLS/server/role/restart plus
separate restore evidence. No paid resources/provisioning or credential rotation done.

DATA-002 next: durable B definitions/cases/capture/plans/grants/runs/single-use claims and
persistent artifacts, with real distributed execution semantics. Then normal A evidence,
approved writing policy and full A3 review/export workspace; bounded managed tests are
not that production integration. Authentication/roles, practice jobs and deployment remain.
Sawaab can incorporate the functional metadata paragraphs into his presentation work.
The owner reviews/merges the draft PR under policy; no merge/deploy is authorized here.
