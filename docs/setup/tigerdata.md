# Durable C storage and TigerData operations

DATA-001 revision 1.0 implements PostgreSQL C persistence. **Hosted TigerData verification
was performed on 2026-11-08** against the owner-selected isolated services
`strongstart-data001-test` (source) and `strongstart-data001-restore` (separate disposable
recovery destination); see [hosted evidence](#hosted-evidence-2026-11-08). Local PostgreSQL
success alone never establishes hosted completion.
Engineering v1.1 §§4,8,10.5,13–16; decision 0006; APP-04/06/07/08, SEC-01/10/13/14,
JOB-02/05. Do not enable production fixture identity/approval/prefill.

## Backend and connection configuration

Keep credentials server-side in the ignored `.env` or private process environment. Never
paste them into chat, browser settings, CLI arguments, screenshots, reports or PR bodies.
The default `STRONGSTART_ANSWER_STORE_BACKEND=unconfigured` is unavailable. Choose `postgres`
for the example DB setup; deliberately choose `memory` only for local fixtures. Memory
is lost on restart and cannot be a production backend or a database-outage fallback.

Set `STRONGSTART_DATABASE_URL` privately to the owner-selected SQL connection URL.
`postgres://`, `postgresql://` and `postgresql+psycopg://` normalize through SQLAlchemy URL
operations to Psycopg without splitting/unescaping credentials manually. Safe query
parameters survive; alternate host/service/credential overrides are refused. Existing
knowledge/validation/migration/readiness also use the shared connection profile.

| Setting | Meaning/default |
| --- | --- |
| `STRONGSTART_DATABASE_PROFILE` | `local` restricts endpoints to loopback/local; `tigerdata` requires a hosted endpoint, verify-full and explicit trust root |
| URL `sslmode=verify-full` | Required in TigerData profile; chain and hostname verification, no weaker fallback |
| `STRONGSTART_DB_SSLROOTCERT` | Actual applicable readable CA path or `system` with installed libpq support; may instead be the URL's sslrootcert parameter |
| `STRONGSTART_DB_CONNECT_TIMEOUT_SECONDS` | 3 seconds |
| `STRONGSTART_DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 3 / 0 per API C pool |
| `STRONGSTART_DB_POOL_TIMEOUT_SECONDS` | 3 seconds (bounded checkout wait) |
| `STRONGSTART_DB_LOCK_TIMEOUT_MS` | 3000 milliseconds |
| `STRONGSTART_DB_STATEMENT_TIMEOUT_MS` | 15000 milliseconds |
| `STRONGSTART_API_PROCESSES` | 1; set actual worker count |
| `STRONGSTART_DB_CONNECTION_BUDGET` | Explicit actual service allowance; no guessed plan limit. Must cover configured process pools and other modules/tools |
| `STRONGSTART_MAX_EXPORT_BYTES` | 8,388,608 combined DOCX+audit bytes; engineering storage budget, not funder rule |

Installed development clients: SQLAlchemy 2.1.8, Psycopg 3.3.8 (binary), libpq 18.6; local
server 17.11. `system` support checks libpq >=16, but see the actual TLS findings below:
`system` did **not** work for the selected services. Retain verify-full and record the
negotiated TLS evidence.

### Actual TigerData TLS findings (2026-11-08)

- Both selected services presented the provider's initial chain: a per-service leaf signed
  by the private self-signed root `O=Timescale Inc, CN=ca.timescale.com` (SHA-256
  `06:5A:75:0D:0D:64:F6:2D:AC:DC:97:9E:3B:83:D2:11:95:40:71:EA:59:B8:F3:40:7C:4E:87:CA:68:34:64:57`,
  valid to 2027-10-20). TigerData documents that new services start self-signed and are
  later re-issued by Google/ZeroSSL, and that free services do not receive signed
  certificates. About 50 minutes after creation neither service had rotated; the plan
  was not inspected or changed.
- Consequently `sslrootcert=system` fails with `certificate verify failed` with every client.
  Separately, the psycopg binary wheel's bundled OpenSSL cannot locate Fedora 44's system
  bundle at its compiled default path; the extracted bundle is
  `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`.
- Configuration used: `sslmode=verify-full` with `STRONGSTART_DB_SSLROOTCERT` pointing at a
  private 0600 bundle = that pinned provider root + the OS public bundle, so a later
  rotation to a public CA keeps verifying without a weaker fallback. Chain and hostname
  verification succeeded (openssl `Verify return code: 0`, `Verified peername` matched)
  and pg_stat_ssl reported TLSv1.3 / TLS_AES_256_GCM_SHA384.
- **Limitation:** no independently authenticated publication of that root was found; it
  was pinned trust-on-first-use, cross-checked as byte-identical from two separately
  created services. Re-check whether the service has rotated to a public CA with
  `openssl s_client -starttls postgres ... -CAfile /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`;
  once it verifies, drop the pin. Owner acceptance of the pin is the remaining TLS gate. Use a direct endpoint first. No pooler,
plan limit, managed backup policy or production capability is inferred from the hostname.

C owns a bounded pool per app; lifespan shutdown disposes it. Shared A/validation/readiness
engines may occupy additional pools, so include their active configurations and operator
clients in the real service budget. Close test/operator pools. No C SQL transaction is
held during workspace/A4/model/DOCX/browser work. Do not migrate during requests/startup.

## Migration and runtime roles

Operator selects an isolated development/test service/database and provisions roles
privately using the approved service process. This task does not create paid services,
change plans, rotate credentials or grant runtime DDL. Migration URL is separate from the
runtime URL. Migration role needs ownership/DDL for the approved migration history and
operator-only fixture/recovery work; it is never the application login.

Apply `uv run alembic upgrade head` explicitly with the migration connection/profile in
the private environment. One head: `0009_durable_applications`, after 0008. Released0001–0008
are unchanged. The historical C3 draft is superseded; never install it. Metadata parity
also declares seven indexes already present in released A migrations.

Illustrative grants for a separately created `strongstart_app` role (operator substitutes
reviewed role/database names; no passwords here):

```sql
GRANT CONNECT ON DATABASE selected_test_database TO strongstart_app;
GRANT USAGE ON SCHEMA public TO strongstart_app;
GRANT SELECT ON alembic_version TO strongstart_app;
GRANT SELECT, UPDATE(id) ON organizations TO strongstart_app;
GRANT SELECT, INSERT ON c_store_state, c_answer_heads, c_answer_versions, c_decisions,
  c_notes, c_proposals, c_change_sets, c_exports, c_audit_events TO strongstart_app;
GRANT UPDATE(revision) ON c_store_state TO strongstart_app;
GRANT UPDATE(latest_version) ON c_answer_heads TO strongstart_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO strongstart_app;
```

Scope sequence privileges to the C ordinal sequences if sharing a schema. There are
**four** (`c_notes`, `c_proposals`, `c_change_sets`, `c_audit_events` ordinals); the hosted
run granted only those four. Revoke
public schema CREATE if the target still grants it, under operator review. Do not grant
runtime UPDATE/DELETE on immutable records, UPDATE(epoch), owner/superuser/CREATEDB/
CREATEROLE/replication/BYPASSRLS. Parent UPDATE(id) permits SELECT FOR UPDATE and has no
supported API mutation. API organization scoping remains required; **RLS is not claimed**.
Other future A endpoints need separately reviewed privileges; this is the bounded C role.

## Opt-in hosted gate

Use `make tigerdata-smoke TIGERDATA_ARGS='--manifest /private/target.json --phase preflight'`.
No normal `make smoke`, Compose/reset, shared seed, wipe or automatic repair is invoked.
Set `DATA001_TIGERDATA_OPT_IN=isolated-development-test` privately. Configure runtime
`STRONGSTART_DATABASE_URL`, TigerData profile/root and explicit budget (at least 7 temporary
connections for the verifier), plus `DATA001_MIGRATION_DATABASE_URL` for write phases.
No control-plane API token is needed for ordinary SQL.

The private, operator-reviewed manifest has no password/URL:

```json
{
  "target_id": "owner-selected-data001-test",
  "provider": "tigerdata",
  "environment": "isolated-development-test",
  "owner_selected": true,
  "host": "EXACT_SELECTED_DIRECT_HOST",
  "database": "EXACT_SELECTED_DATABASE",
  "migration_role": "SELECTED_MIGRATOR",
  "runtime_role": "SELECTED_NONOWNER_APP",
  "allow_migrate": false,
  "allow_test_writes": false
}
```

Use the actual service provenance selected by the owner, not a hostname guess. Exact host,
database and role must match privately configured URLs. Runtime preflight is read-only
and checks negotiated pg_stat_ssl TLS, server version, migration head and nonowner/nonDDL
role flags. It reports a target fingerprint instead of endpoint/credentials. The TLS
client configuration verifies chain/hostname; pg_stat_ssl alone is not proof of trust.

Phases are separate, with no implicit transition:

1. `--phase preflight`: read-only. Missing target/opt-in/profile fails before connecting.
2. Owner edits `allow_migrate:true`, then `--phase migrate`: explicitly changes selected
   schema through the linear Alembic history. Rechecks runtime head afterward.
2b. Before any runtime phase after migration, apply the bounded runtime grants above as the
   migration (owner) role. Migration alone leaves the runtime role unable to read
   `alembic_version`, so the gate's post-migration runtime recheck reports unavailable
   until then (observed on the hosted run; no automatic grant is performed by the gate).
3. Owner edits `allow_test_writes:true`, then `--phase verify --receipt /private/run.json`:
   exclusive mode 0600 ownership receipt is created **before** writes. Migration role
   inserts one random `data001-<32 hex>` synthetic organization; actual B publication and
   C save/approve/note/proposal/export/public reader use the nonowner runtime role. A
   fresh spawned app/pool reopens identical content; second-client edit/conflict and
   observed separate-process SQL contention verify currentness/concurrency. Private
   `.verified.json` records exact IDs/hashes/epoch and sanitized TLS/role evidence.
   Fixture workspace/identity are explicitly namespaced adapters, not real evidence/auth.
3b. `--phase restart --receipt /private/restart.json` (same write permission and ownership
   receipt rules): three actual uvicorn API processes using
   `scripts.data001_workflow:hosted_app_factory` (namespaced synthetic identity/workspace
   adapters only). Save/approve/note/review/export and prepare a B plan; restart and compare
   history, audit, DOCX/audit bytes and C state exactly; C epoch unchanged; the old plan
   reports `runtime_epoch_changed` and a new plan is prepared from the preserved approval;
   apply the fixture A4 replacement and restart again: the old approval is held
   `approval_not_usable` and replay is idempotent. Locally covered by
   `test_hosted_restart_phase_locally_uses_real_processes_with_nonowner_role`.
4. Inspect receipts; optionally `--phase cleanup --receipt /private/run.json`. Only this
   exact fingerprint/org with its matching synthetic ownership label is deleted, child
   C tables first, through the operator connection. Runtime DELETE privileges do not
   expand. On failure, records and ownership receipt remain for reconciliation. Never
   retry an unknown write blindly or use a guessed cleanup prefix.

Verifier B files live in an owned temporary directory, not durable B storage. Hosted
recovery is a separate mandatory operator exercise below; success of `verify` alone does
not establish hosted restore. Do not send secrets in chat. No paid resources were
provisioned and no plan was changed by this work.

### Role provisioning used on the hosted test service

As the service admin, over verify-full: `CREATE ROLE data001_migrator` and `data001_app`,
both `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT`, with
server-enforced `CONNECTION LIMIT` 5 and 15. Passwords were generated locally and sent only
as precomputed SCRAM-SHA-256 verifiers, so no plaintext password can reach statement
statistics or logs. `GRANT CONNECT` on the database to both, `USAGE, CREATE ON SCHEMA
public` to the migrator only, `USAGE` to the runtime role (`PUBLIC` had no CREATE). After
migration, the migrator (table owner) applied the bounded grants above.
`STRONGSTART_DB_CONNECTION_BUDGET=20` is the sum of those enforced limits (service
`max_connections` 105, 12 reserved), not a guessed plan limit.

## Backup, restore and epoch policy

Use compatible PostgreSQL `pg_dump`/`pg_restore` tools (client major must support actual
source server) and an ignored, operator-approved private destination with mode 0600/umask077.
Freeze writes for the recovery evidence window if checking exact row counts/revisions.
Set libpq `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`, TLS trust and credentials privately
(e.g. protected PGPASSFILE); never put a password/DSN in command arguments. Confirm
current_database/current_user against selected source before the read-only dump:

```sh
umask 077
pg_dump --format=custom --no-owner --no-privileges --schema=public --file /private/source.dump
```

TigerData services run PostgreSQL 18.6, so clients must be >= 18. The hosted run used an
ephemeral `postgres:18.6-alpine` client container (`docker run --rm --network host`, libpq
variables passed by name with `-e NAME`, verify-full against the pinned root mounted
read-only). Dumping only `public` avoids TimescaleDB extension/catalog objects.

Record migration head, selected org/version/approval/export IDs, template/rendered/
snapshot/DOCX/audit hashes, full stored state/revision and row counts privately. Hash
and protect the archive; it contains application data. Backups retain sensitive state.
Select and verify a **different, empty, explicitly disposable** restore database and
set its private libpq environment. Never use `--clean`, overwrite the source or run a
schema/volume reset. Restore permissions/extensions must suit the actual service:

```sh
pg_restore --list /private/source.dump > /private/full.toc
# Exclude only pre-existing/provider-owned entries: the public SCHEMA/COMMENT and objects
# owned by the provider's `postgres` role (TigerData ships public.create_playground).
grep -v -E '^[0-9]+; [0-9]+ [0-9]+ (SCHEMA|COMMENT) - (SCHEMA )?public ' /private/full.toc \
  | grep -v -E ' postgres$' > /private/restore.toc
pg_restore --no-owner --no-privileges --single-transaction --exit-on-error \
  --use-list /private/restore.toc --dbname "$PGDATABASE" /private/source.dump
```

Review the excluded lines; every application entry must remain (169 on the hosted run).
The first hosted attempt without the provider-function exclusion failed atomically on
`function "create_playground" already exists` and left the destination empty.

The argument above is only the nonsecret database name; all connection/auth inputs stay
private in libpq environment. Verify rows, IDs, exact hashes/bytes and original revision/
epoch against the receipt before exposing recovered routes. Restore into another target
has been tested locally and, on 2026-11-08, from the hosted test service into the separate
hosted restore service (see evidence below).
Local test uses installed host clients or the explicitly local existing PostgreSQL
container's clients; hosted runner has no Docker/Compose path.

After validation, keep the recovered application offline and explicitly rotate each
restored C organization epoch with operator-only
`applications.maintenance.rotate_dataset_epoch(engine, org, expected_state)`. This locks
the parent/state and guards the expected epoch/revision, changes epoch, increments revision
and appends a recovery audit atomically. Do not grant runtime UPDATE(epoch). Existing
captured C work is invalidated; saved approvals may resolve freshly if dependencies remain
current. Prepare new B plans. Old B plans also retain their runtime-epoch/single-use rules;
restoring C cannot authorize browser replay. Preserve the source and its epoch untouched.

TigerData's documented managed recovery uses service backups and recovery forks. Confirm
actual account retention, PITR/backup history/region/plan availability separately; creating
a paid fork is outside this authorization. A written runbook is not a performed recovery.

## Hosted evidence 2026-11-08

Source commit for the final hosted verify/restart runs: `677060e`. Private sanitized
receipts (mode 0600, outside the repository) hold IDs/hashes only. Target fingerprint
`b3289ae3b5a8c20a`; server PostgreSQL 18.6 with TimescaleDB 2.31.0; TLSv1.3.

| Check | Hosted result |
| --- | --- |
| Preflight (runtime role) | verify-full with explicit root, negotiated TLS, nonowner/no CREATE/no elevated flags |
| Migration (migration role) | `0001`→`0009_durable_applications` applied; 34 tables owned by the migrator |
| Runtime denials | `UPDATE epoch`, `DELETE` audit/exports, `UPDATE` immutable versions/org name, `CREATE TABLE` each `42501`, rolled back |
| `verify` | Actual B publication and C save/approve/note/review/export; spawned fresh app/pool reopens exact approved content; second client edit makes captured approval not current; stale expected version 409; two separate processes observed blocked on the SQL lock (pg_blocking_pids) → one 201, one 409 |
| `restart` | 3 real uvicorn processes: exact history/audit/DOCX/audit bytes and C state after restart; stable epoch; old B plan `runtime_epoch_changed`; new plan from preserved approval with exact rendered value; A4 replacement keeps old approval `approval_not_usable` after a further restart; idempotent replay |
| Backup/restore | Read-only custom dump as migrator; single-transaction restore into the separate empty restore service; all 34 tables' row counts and full content digests, `c_store_state` epochs/revisions and export BYTEA SHA-256 identical; source digest unchanged across the window |
| Epoch policy | On the restore destination only: C store readback equals source; `rotate_dataset_epoch` changed each epoch, revision +1, appended one `operator-recovery`/`dataset_epoch`/`rotate_after_recovery` audit (action `approval_staled`), previously captured approval no longer current; source epochs/revisions unchanged |
| Cleanup | Receipt-owned cleanup removed exactly one synthetic org; three synthetic orgs intentionally retained on the source for owner inspection, plus the restored copy |

Not exercised: TigerData-managed backups/PITR/recovery forks (outside this authorization),
Chromium against the hosted API (Chromium remains local PostgreSQL evidence), and
any non-synthetic data.

## Failure and rollback

Liveness remains alive during DB failure; readiness requires connectivity and exact head.
Selected missing/unreachable/outdated PostgreSQL is unavailable. Never switch to empty
memory, auto-seed, downgrade a shared target or report a failed mutation as successful.
Lock/statement/pool timeouts release resources; pre-ping replaces dead connections.
An uncertain commit returns `commit_outcome_unknown` with read/reconciliation instruction;
no automatic replay or claim of rollback. Inspect history/audit before retrying.

App rollback: retain the database/archive and stop/disable review/prefill routes while
selecting compatible code. Old INT code does not understand this durable backend; do not
use it as a data migration or recreate approvals in memory. Migration downgrade drops C
data and is tested **only** in uniquely created disposable local databases. A live rollback
requires a reviewed forward fix or validated recovery destination. Normal shutdown closes
owned pools; restart preserves C epoch. DATA-002 still owns durable B/artifact storage.

References checked against installed code and official docs November8,2026:
[SQLAlchemy engine/URL](https://docs.sqlalchemy.org/en/20/core/engines.html),
[PostgreSQL verify-full](https://www.postgresql.org/docs/17/libpq-ssl.html),
[TigerData connections](https://www.tigerdata.com/docs/integrate/find-connection-details),
[TigerData recovery](https://www.tigerdata.com/docs/deploy/tiger-cloud/tiger-cloud-aws/high-availability/backup-restore).
