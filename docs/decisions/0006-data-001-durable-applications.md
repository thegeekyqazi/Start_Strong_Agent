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
