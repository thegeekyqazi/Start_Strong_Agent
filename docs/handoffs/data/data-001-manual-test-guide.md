# DATA-001 manual verification

Spec revision 1.0, decision 0006. Use synthetic local data or an explicitly selected isolated
TigerData development target. No production fixture flows, real portal credentials,
submission/signing/upload, paid provider calls or shared resets. Automated evidence and
hosted pending inputs are in the [final handoff](data-001-durable-applications-r1.md).

1. Configure private server-only URL/profile, `ANSWER_STORE_BACKEND=postgres`, local
   fixture identity and retained B local-store directory. Migrate explicitly to 0009
   using migration-role credentials; switch to the nonowner runtime connection. Follow
   [setup](../../setup/tigerdata.md). Liveness is 200; readiness must be 200 at exact head.
   Missing URL/schema/outage must return 503 without a new memory store.
2. Publish `rep-prefill-definition-v1` through Automation intake/definition save. In
   Applications select that exact saved question set. Save `pf-org-name` and `pf-summary`
   published IDs (not the original IDs) with Unicode/leading spaces/CRLF and a linked
   synthetic fact. Record version IDs, exact text, hashes, dependencies and timestamps.
3. In Review acknowledge review items and approve the exact version. Add a note and a
   meaning-reviewer proposal. The proposal never grants approval. Download reviewed
   DOCX/audit, record SHA-256 and export ID, and retain bytes privately. Review says
   durable PostgreSQL; fixture reviewer/SYNTHETIC labels remain visible.
4. Prepare a pending B plan and record its runtime epoch and C producer epoch. Stop the
   owned API normally; start a fresh process against the same DB and B directory. Reopen
   history, approval, notes, proposal, audit and stored downloads; compare exact IDs,
   bytes/hashes/order. C epoch is unchanged. The old pending plan says runtime epoch
   changed. Prepare a **new** plan and fill only selected representative fields. Receipt
   must show selected_fields_verified, entered_verified and final reread all_match;
   actual text/hash equals the preserved approved rendering. No external/mutation traffic.
5. Run a second API on a different local port against the same dataset/B files. Save a
   successor from it with expected latest 1. First app immediately refuses the old approval
   and pending plan. A second save with expected 1 conflicts; no overwrite/version gap.
   Concurrent decision requests yield one immutable decision. Automated tests use process
   barriers and actual pg_blocking_pids wait observation, not manual timing, for proof.
6. Managed A4 path is bounded test-only workspace, not the normal fixture. Run
   `uv run pytest -m db tests/smoke/test_int001_joined.py tests/smoke/test_int001_a4.py`.
   Actual C save/approve and A4 replacement must block pending work; completed receipt
   replay stays historical. The existing managed rehearsal remains explicitly synthetic.
7. Outage exercise only on an owned disposable target/process. Select an unreachable
   local endpoint or revoke only an owned test connection, without changing a shared
   service. Read/save/export must be503, liveness alive, readiness not ready. Restore
   connection; existing state reappears without fallback. Unknown commit outcome requires
   reading/reconciling history/audit before retry; do not replay automatically.
8. Run `uv run python scripts/verify_data001_commit_mutation.py` only in a dedicated
   worktree with local test DB configured and no other writers. Mutant must fail the
   stale_export_publication invariant; exact source checksum is restored in finally;
   protected rerun passes. Never weaken the assertion or leave mutation active.
9. Follow backup/restore runbook into a different empty disposable database. Compare
   selected IDs/hashes/bytes/revision, then explicitly rotate restored C epochs using
   operator credentials before exposing routes. Confirm earlier capture fails and source
   state is unchanged. Prepare new B plans; do not replay historical browser writes.
10. Hosted gate: owner supplies selected target/roles/CA/budget and distinct recovery
    destination privately. Run read-only preflight, separately permitted migration,
    namespaced verification and receipt-owned cleanup. Record actual TLS/server/role
    evidence and separately performed hosted restore. **Not run: no target supplied.**

Final source checks: `make contracts`, `make check`, `make smoke`, `make browser-smoke`.
DB/browser markers execute explicitly; a default pytest pass is insufficient. Hosted
`make tigerdata-smoke` is opt-in and never invokes the local smoke/reset workflow.
