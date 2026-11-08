# B2-AUTO-002: Approved selected-field prefill and live read-back (r1)

- Author/lane: single Dev B agent (Codex), automation module; continued the existing implementation, no restart or parallel agents.
- Intended consumers: project owner, Dev C (approved-content producer), Dev A (currentness factory).
- UTC date: 2026-11-08.
- Status: ready for review as a **partial draft increment**. P1 fixture/harness complete; P2 producer integration pending. This does not close G2.
- Task: `docs/specs/B2-AUTO-002_Approved_Prefill_and_Read_Back.md`, revision **1.0**.
- Engineering: `docs/engineering/StrongStart_Engineering_Plan.md` v1.1, sections 4, 7, 9.2, 10.5, 10.7, 12.4, 13.2–13.3, 14–16, 18–21. B subsets: AUT-01/02/03, AUT-04 checklist, SEC-03 fixture routing, SEC-08/09, JOB-03. Consumes APP-04 and SEC-01/13/14 boundaries; catalog completion is not inferred.
- Branch: `dev-b/b2-auto-002-approved-prefill`; implementation commit: **0ff8f151d2a25277163a22c2896edda691810505**. This handoff's own commit is the subsequent documentation checkpoint on that branch.
- PR: https://github.com/thegeekyqazi/Start_Strong_Agent/pull/17 (existing draft; not merged).
- Supersedes: no historical handoff. Updates the dependency state of `b2-auto-002-approved-content-request-r1.md` only: C2b's question identity path has now merged.

## Reconstructed checkpoint and phase status

The takeover found a clean worktree at `a2b8146d711cb29c6cccb078e968b892f3ba6989`, equal to PR #17's remote head. No untracked or uncommitted work was discarded. Current upstream `e6df77a` was inspected and merged with a normal merge (`04f68ec`); no force push or default-branch write occurred.

| Phase | Actual delivery |
| --- | --- |
| P0 | Complete: spec/decision and C content-reader request published on #10/#17. Takeover/dependency update: [PR #17 comment](https://github.com/thegeekyqazi/Start_Strong_Agent/pull/17#issuecomment-6720423438). |
| P1 | Complete for the explicit test-provider harness: server planner, original/published ID binding, holds/checklist, atomic single-use claims, bounded Chromium operations, actual live DOM read-back and final reread, UI and automated evidence. The application runtime has no seeded approvals. |
| P2 | **Pending C-owned approved-content reader/factory.** C3 #10 and C2b #18 are merged. C2b now resolves exact B published question IDs; this is no longer a blocker. C's resolver still returns an `ApprovalSnapshot` without template/rendered text. No C private stores/functions or API-loopback calls are used. |
| P3 | Verification, documentation and PR publication for the independent P1 increment. Full feature completion and G2 remain pending P2. |

## What works and what the UI means

Preparation consumes an exact saved question set, a registered local portal and approval IDs. It performs no browser writes. The plan previews exact intended rendered strings/typed choices, separate template/rendered hashes, question/answer versions, scope, expiry, holds, other required fields and attachment evidence. The original 350/500 and Max 300 ambiguities remain held; the dedicated positive fixture does not rewrite them.

Execution requires the explicit **Fill these approved fields** command with the plan hash and a retained idempotency key. The cross-process no-clobber claim precedes possible mutation. There is one run per plan; an incomplete claim is never automatically executed again. A completed replay returns its historical receipt. The executor also rejects direct calls with absent/tampered grants or mismatched action/page bindings before launch.

The real Chromium executor operates on the same inspected document, using registered fill/select/check operations only. It reads live properties rather than HTML value attributes and rereads all entered fields at completion. It stops on mismatches, observable approval/dependency/definition changes, producer restarts, expiry or hostile navigation. It never repairs/retries a field, uploads, submits or signs. The fixture page closes; the receipt is a local demonstration, not saved funder state or application completeness.

The UI guards immediate double clicks, retains the same request identity after a lost response, and uses read-only GETs for refresh recovery. A late load/plan/execute response cannot replace a newer selection. A failed or unknown run never enables automatic re-execution. An unavailable Chromium launch returns 503 with the stored zero-write run ID; staff can read its receipt without another browser execution.

## Public contracts and exact producers

| Interface | Version / producer / actual state |
| --- | --- |
| B saved definitions | `ApplicationDefinitionReader`, `b2-published-definition/1`, merged B bundle #12; consumed through B's public factory. C2b #18 (`e6df77a`, implementation `4c2ebe3`, UI `f688879`) consumes exact versions and published IDs. |
| B prefill | `strongstart_contracts.automation_prefill`: `b2-approved-prefill/1`, `b2-bound-form-map/1`, `b2-prefill-run/1`. Strict prepare/execute requests; immutable plans, grants and receipts. Additive draft fields bind action producer ID/epoch and grant page hash. Regenerate from Python; all 202 upstream schema definitions are preserved (229 combined). |
| Requested C content | `ApprovedPrefillReader.resolve_for_prefill(org, approval_id)` → `b2-requested-approved-prefill-content/1`. **Proposed consumer contract, not adopted by C.** Runtime dependency returns `UnconfiguredApprovedPrefillReader` (503 for usable selections). No fallback. |
| Actual C resolver | C3 #10 merged at `c490dba`; C2b extends resolver/workspace selection. `StoreApprovedAnswerResolver.resolve` returns a simulated `ApprovalSnapshot` only. C3 approvals remain process-local fixture state; no durable answer migration is applied. |
| Test content | `tests/automation/prefill_support.py::TestApprovals`, producer `b2-test-approval-provider`, renderer `test-renderer/1`, explicit fixture labels. Only dependency overrides in tests. `tests/browser/prefill_app.py` is a **test-only** process factory, never the runtime app factory. |
| A4 | #15 merged at `5f1c5a0`, handoff `docs/handoffs/dev-a/a4-pkg-004-pack-replacement-r1.md` (implementation `71f1458`). Exact dependency registration/currentness HTTP contracts exist; no supported in-process factory. Optional B currentness port is exercised only with `TestCurrentness`; A4-to-B propagation is not integrated. |
| Attachment evidence | Unconfigured in runtime. Tests inject labelled trusted synthetic records for existence/detected type/size/count. AUT-04 checklist only; no transfer. |
| Persistence | Existing B development-only local repository, production disabled. No new migration. Existing merged Alembic head `0007_pack_replacement` preserved; C's draft migration under `docs/` was not applied. |

Routes under `/api/automation`: `POST /prefill-plans`, `GET /prefill-plans/{id}`, `POST /prefill-plans/{id}/execute`, `GET /prefill-runs/{id}`. Organization/actor come from server identity. No route accepts answer text, selectors, URL, approval flags or organization as execution authority. Existing read-only `FormInspectionResult.prefill_permitted=false` is unchanged. Production capability endpoints report prefill unavailable; fixture harness capability is distinct from unavailable integrated C3/real-portal/upload/submission support.

Draft record compatibility: older pending local plans/grants lack newly required bindings and fail closed. Prepare a new plan after upgrading/restarting; do not repair old records. No consumer is authorized to turn this draft contract into an approval authority.

## AUTO2 acceptance evidence and omissions

`U` = committed non-browser tests in `tests/automation/test_prefill_plan.py` using a stub browser and explicit test content provider. `B` = committed real Chromium in `tests/browser/test_prefill_browser.py`, with real API routes and test content. `UI` = `apps/web/src/features/automation/prefill.test.tsx`. Existing inspector tests remain real Chromium. These labels never mean joined C3 approval integration.

| AUTO2 | Evidence / limits |
| --- | --- |
| 01 | U: missing identity before store/reader/browser; unknown and other-org plans/runs indistinguishable; scoped approvals. |
| 02 | U: strict shapes/types, extra content/org/URL/selector flags, bounds and repeated mappings rejected. |
| 03 | U: consistent test envelope and unavailable default without seeded fallback. **Real C producer pending.** |
| 04 | U: independent template/rendered hashes, identity/dependency corruption and unresolved tokens refused. |
| 05 | U: source, published and unrelated C fixture identities cannot substitute; publication mapping required. |
| 06 | U: unique bound map; B: missing/duplicate/type/options/new-required-control mutations stop before writes. |
| 07 | B: changed source bytes and live DOM fingerprints in the execution document produce zero operations. |
| 08 | U: preparation launches no browser; forged hash/missing plan rejected; direct executor missing/tampered grant rejected. |
| 09 | U: tampered grant/plan identity, actor, origin, fingerprint and operations rejected; B checks exact grant/action/page bindings. |
| 10 | U: thread and spawned-process claims observe blocked **and acquired_after_wait** events; one execution, historical idempotent replay. B: replay launches no second browser. Mutation evidence below. |
| 11 | U: interrupted claim is historical/unknown, never another write. B: post-write persistence failure stops and closes owned resources. |
| 12 | U: expiry/runtime/producer epoch and unavailable reader; completion cannot outlive grant. |
| 13 | U: unknown/stale approval planning and one-character edit after preparation prevent affected writes. |
| 14 | U: event-controlled edit during action yields entered-then-stale and stops remainder; no zero-race guarantee. |
| 15 | U: definition/case revision stops execution; completion rechecks definition/currentness. |
| 16 | B: two exact text fields, live DOM hashes and final reread; real process UI → HTTP API → Chromium receipt. |
| 17 | U: planner rejects malformed numbers/overlength; B: native truncation, scripted replacement, final overwrite and browser-native numeric rejection. The last uses deliberate test instrumentation at the native fill boundary. No repair/retry. |
| 18 | B: spaces, Unicode/emoji, apostrophes, LF/CRLF; only recorded textarea CRLF→LF convention. |
| 19 | U/B: typed registered choices, exact select/check read-back, no prose inference, changed typed value rejected. **Real C choice producer unavailable.** |
| 20 | U/B: exact parent choice reveals/remaps child; unsupported predicates held; unexpected branch structure stops child. |
| 21 | U: existing conflicts/unknown conventions remain held despite answer approval. |
| 22 | U: missing/wrong/oversize/count/nonexistent attachment findings, trusted-record comparison only, no upload operation. |
| 23 | U/B: operations finite; hostile submit/sign instructions cannot authorize action; fixture endpoint denial and zero submit hits. |
| 24 | B: hostile input attempts exfiltration, private/metadata destinations, mutation, navigation, WebSocket, popup/download; separate redirect case; listening canary receives **zero** prohibited requests. Registered-fixture routing only, not OS egress isolation for arbitrary portals. |
| 25 | B: missing Chromium unavailable/zero writes; stall after possible entry yields outcome_unknown within bounded operation waits. |
| 26 | B: session page/browser and fixture-server thread/socket close after success, mismatch, changed form, hostile attempts, timeout, missing executable and hook failure. Only this test's resources are observed; no unrelated browser termination. |
| 27 | UI/B: exact preview, holds/checklist, explicit button, running/error/partial/unknown/receipt, double-click guard, lost-response same key, read-only refresh recovery and late-response isolation. |
| 28 | U/UI: organization scopes, bounded safe errors and inert rendering, including HTML-looking approved text. No new answer logging. |
| 29 | **Pending P2.** Same consumer contract exercised with test provider only. C2b's real B question path is merged but save→approve→content-reader→entry cannot run without C's reader. |
| 30 | U: explicit test ChangeSet/currentness stales remaining actions. **Actual C/A4 propagation not integrated.** |
| 31 | U: production execution disabled, capabilities honest; arbitrary portals and submission unavailable; read-only literal false unchanged. |
| 32 | Full checks and real process browser test below. A/B/C registrations preserved. **Joined C3/G2 omitted for the documented missing producer.** |

## Verification and retained failure evidence

Final command results are recorded below after the frozen-code verification run. No paid provider call, deployed service, independent review or PR merge is claimed.

- `make contracts` (with a writable temporary uv cache): PASS; generated JSON Schema and TypeScript from the combined Python registry. Independent upstream-schema subset assertion: 202/202 retained; 229 combined.
- `make check`: **PASS**: Ruff/format, oxlint/Prettier, strict mypy (193 files), TypeScript, **751 Python tests passed / 48 deselected**, **97 Vitest tests passed**, schema/TypeScript drift checks and web/Python builds. Final run: Python 49.05 s.
- `make smoke`: **PASS**: 106 import tests + 12 database tests; liveness/readiness/capabilities 200, database connected, current and required migration `0007_pack_replacement`. Command was `make smoke` with only the local database setting supplied from `.env.example` by the temporary runner described below.
- `make browser-smoke`: **PASS**: 36 real Chromium tests, including 20 prefill cases and the real web/API-process receipt test (69.34 s). The other 16 cover existing inspector, funding, saved-definition and smoke regressions.
- Focused prefill tests before final guards: 43 passed; final non-browser prefill suite is included in `make check`.
- UI-focused run: 10 passed; full Vitest includes them.

Initial checkpoint verification was retained and investigated: `make check` stopped on two new-harness mypy errors (unused ignore, untyped model-copy mutation mapping); baseline pytest then had 743 passed and three outdated capability expectations. Assertions now describe actual fixture-only support and explicitly unavailable production/integrated paths; authorization gates were not weakened.

The initial full browser run had **29 passed, 1 failed**: existing hostile inspector returned 504 readiness timeout (`elapsed_ms=15542`). Its isolated rerun passed. Startup now observes the initial document **commit**, then the registered readiness predicate, rather than a DOMContentLoaded lifecycle wait affected by denied navigation. Subsequent complete runs passed. Test proxy logs can include BrokenPipe after intentional UI navigation closes a request; no failed assertion or prohibited canary hit was ignored.

The expanded hostile test initially assumed every denied popup yields a Page event (two runs: 34 passed, 1 failed). A navigation can be denied before Chromium emits that event. The combined case retains its zero-canary-hit, mutation, WebSocket and navigation checks; a separate no-competing-navigation case requires actual popup/download events, denial records and owned-resource cleanup. Both focused cases passed; the final full run passed all 36.

A later no-DB run had 750 passed and one false failure in existing `test_bnd13_altered_limit_withholds_content[False]`: the random request correlation ID contained `5000`, matching the tampered-value sentinel. The test now fixes only its correlation ID to a known UUID after saving the fixture; **the original raw-response leak, 409 and integrity assertions are unchanged**. No runtime error or authorization behavior was changed for this correction.

This worktree had no `.env`. Initial smoke therefore stopped on missing database configuration. Loading all example variables with uv also exposed JSON-quote parsing of CORS; the successful smoke runner supplies **only** the documented local database setting from `.env.example`, without printing it. Existing healthy shared PostgreSQL and data were preserved. Smoke observes `0007_pack_replacement`; no reset/down-volume operation or draft migration was used.

### Lock mutation evidence

Temporary mutation: bypass only `_exclusive_lock` for `prefill-runs.lock`; leave all other locks unchanged. Run:

```bash
uv run pytest tests/automation/test_prefill_plan.py -q -k 'racing_execute_requests or two_processes_claim'
```

Observed mutant result: **2 failed, 43 deselected, exit 1** (21.02 s). Both fail because the competing writer never emits the required real `blocked` event: `second execute never contended for the claim` and `a child never contended for the claim lock`. Tests do not infer arrival from sleeps, `Queue.empty()` or a Future's unfinished state. Thread/process acquisition events are required after release on the protected path.

The runner restores the exact original source in `finally`, verifies byte equality and reports `PROTECTION_RESTORED=true`. The same command after restoration: **2 passed, 43 deselected** (2.99 s). `dev_b_store/core.py` has no final diff; no mutation switch is committed. Full-suite verification ran only with the original protection.

## Decisions, limitations and consumer actions

See `docs/decisions/B2-AUTO-002-approved-prefill-scope.md`, including the takeover update. Runtime remains unconfigured for C content, artifact evidence and actual A4 propagation. C3's process-local fixture state is not made distributed by B's cross-process claim test. Pre/post checks detect observable changes; they cannot prevent a C edit during an in-flight browser operation. Full recovery/resume, real portal handoff and deployment belong to later tasks. Word-count fields remain held until a supported C counter contract exists. No all-86-check or complete application-readiness claim is made.

- **Dev C:** acknowledge/adjust `b2-requested-approved-prefill-content/1` and publish a supported reader/factory with one consistent immutable template/rendered envelope, separate hashes, live dependencies/currentness and producer epoch. Use C2b's exact B published IDs; say whether typed choice authorization is supported. Required acknowledgment remains outstanding. Then B can implement/test P2 using C-owned save/approve → public reader → entry.
- **Dev A:** acknowledge the HTTP contracts; publish an in-process registration/currentness factory for exact dependency tuples and B plan/grant targets, or explicitly decline. B will not call knowledge routes over loopback or import private stores. Durable C/B migration sequencing remains A-owned.
- **Owner/reviewer:** inspect the partial draft and P1 evidence; do not treat the harness as full feature completion or G2. No merge is authorized here.

## Acknowledgments

C2b's acknowledgment of B's question reader is in `docs/handoffs/dev-c/c2b-real-questions.md` at `e6df77a`. It is consumption evidence, not approval of this PR. No acknowledgment of the C content-reader proposal or A4 in-process factory has been received as of the last inspected #17/#10/#15/#18 discussions and fetched upstream `e6df77a`.
