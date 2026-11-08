# Current feature status — DATA-001

This matrix supersedes earlier process-local C status. Local implementation/verification
is distinct from the required hosted gate. See [acceptance evidence](../handoffs/data/data-001-durable-applications-r1.md).

| Area | Current behavior | Boundary / next work |
| --- | --- | --- |
| C backend | Explicit PostgreSQL, explicit memory fixture or unavailable default | No outage fallback; production memory prohibited |
| C version/review | Durable exact versions, immutable decisions, notes/proposals/change sets/audit | Fixture identity remains simulation; real auth pending |
| C export | Durable full result + exact BYTEA DOCX/audit, size/hash verification | Bounded engineering budget; source artifact durability later |
| C public reader | Same usable predicate for metadata/content, stable SQL dataset epoch | Explicit restore/reset rotation; independent fresh revision checks |
| TigerData | Secure profile and opt-in isolated runner; hosted TLS/migration/roles/verify/real API restart/restore verified 2026-11-08 on isolated services | **Owner acceptance of pinned provider TLS root pending**; managed PITR/fork and hosted Chromium not exercised |
| A4 managed evidence | Real SQL producer + actual durable C + guarded B registration tested | Bounded test workspace; normal real A/policy/A3 integration pending |
| B publication/browser | Real publication/C handoff and restricted Chromium read-back tested after restart | B files/plans/grants/claims still development-only; DATA-002 |
| UI | Functional durable-storage label separate from synthetic/reviewer labels | Sawaab owns presentation; no redesign branch integrated |
| Models | Existing Fake/Gemini adapter contracts retained | No paid calls/new provider/policy authority added |
| Production | Fixture identity/prefill disabled | No production-ready auth/evidence/deployment claim |
| Practice skills / jobs | Existing planned/unavailable boundaries retained | No general JobStore, lease or browser resume system |
