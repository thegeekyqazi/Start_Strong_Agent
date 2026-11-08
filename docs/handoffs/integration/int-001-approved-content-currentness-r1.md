# INT-001 approved content and prefill currentness — revision 1.1

- Owner: project owner, former A/B/C engineering; one coding agent, sequential M0–M4.
- UI/UX owner: Sawaab; functional changes only. No separate UI/UX branch was integrated.
- Repository: `thegeekyqazi/strong-start-agent` (renamed from `Start_Strong_Agent` by explicit
  owner instruction). Display title: **Strong Start Agent**. Package namespaces retained.
- Branch: `integration/int-001-approved-content-currentness`.
- Baseline: `b543454255c45e9a079e3090337585b375fe34f0`, merged PR #17; upstream rechecked at
  M3 and unchanged. Existing worktrees/untracked input spec preserved; isolated worktree.
- Spec: `docs/specs/INT-001_Approved_Content_and_Prefill_Currentness.md`, revision 1.1.
- Engineering: v1.1 §§4, 5.3, 8.2–8.3, 9.2, 10.5, 10.7–10.8, 12.4, 13.2–13.3,
  14–16, 18–21. APP-04/06, AUT-01/02/03, PKG-01/02/03, JOB-02/03/05,
  SEC-01/08/09/10/13/14. AUT-04 remains checklist-only. No blanket catalog promotion.
- Decisions: [0005](../../decisions/0005-int-001-engineering-takeover.md); no scope deviation.
  Conservative pack-root coverage, nullable migration metadata and format versioning are
  documented implementation choices explicitly permitted by the task.
- Current verification/publication: final command results and exact implementation/PR refs
  are recorded in the final verification section below. This note does not close G2/G4.

## Delivered behavior and public boundaries

C's `applications.public.get_approved_prefill_reader` supplies the same app-scoped store,
workspace/policy and stable store epoch as save/decide. Metadata/content share one usable
predicate. A deep-copy approval/version snapshot is captured under the store lock; external
workspace/SQL reads happen after release; org revision and active-store identity are checked
again before return. Saves, decisions and applied changes advance the revision. Both hashes,
decision hashes, the exact dependency snapshot, live gates and saved rendering verify.
Unresolved/unsupported content, inaccessible/foreign IDs and stale versions are refused.
The reader never re-renders under an old approval or infers typed choices from prose.

`knowledge.public.KnowledgeCurrentness` supplies active evidence, versioned projection,
guarded registration and read-only target verification. Original C dependencies are retained;
legacy fact digests are validated against authoritative facts, then mapped to actual fact
versions. Pack references become `(pack_version, version-ID, version-ID)`. Independently
managed source hashes/policy versions remain exact. Unknown requirement-set coverage holds;
C/B keep live question/rule checks. A conservative pack root invalidates every consumer of a
replaced pack, even when only an unrelated member or same-content/new-version pack changed.

Migration `0008_browser_bindings` adds nullable context, pack, active revision and projection
hash columns to existing targets. The new `browser_plan` kind is additive (string column).
Registration locks organization → context → target, sharing activation's organization lock,
rechecks active identity and writes in one transaction. Identical registration only reads;
stale/mismatched targets cannot be revived by GET, replay, guarded or generic registration.
No C/B/browser operation occurs under those SQL locks. C3's draft migration is not installed.

B plan `/2` stores exact actions, their bindings, the full original dependency union and an
aggregate plan registration. Grant `/2` names its actual grant ID/registration and hashes it.
The plan registers before publication; the grant registers after the atomic single-use claim
and before mutation. A failed step can leave a non-authorizing orphan registration, never
an executable managed operation without its checks. Both targets and C content are checked
before/after each field and at completion. Checks use the whole target union. Completed
receipt replay happens first and retains history without a new browser. Old pending formats
require a new plan; old completed receipts remain readable/replayable without rehashing.
GET usability is separate from immutable plan data and does not register, execute or renew.

Review → Automation passes IDs only through an ephemeral client adapter. It loads exact
saved questions and server approvals, previews saved rendered values/hashes/versions, displays
C-connected/unmanaged/managed labels and retains explicit prepare/execute. Double-click,
same-key retry, refresh recovery, accessibility and late-response checks are preserved.
See [UI contract](int-001-ui-contract.md) and [manual guide](int-001-manual-test-guide.md).

## Evidence paths (do not conflate)

- **R**: `tests/integration/test_content_reader.py`: actual C save/decide/store/reader,
  B saved question producer; no browser. Deliberately corrupted fixtures are negative tests.
- **P**: `tests/integration/test_prefill_currentness.py`: actual C/B API with a clearly
  controlled browser actuator. Includes consumer envelope tampering and historical fixtures.
- **D**: `tests/smoke/test_int001_a4.py`: migrated PostgreSQL, actual knowledge records,
  manifests, activation, projection/registration/currentness, lock wait and isolation.
- **J**: `tests/smoke/test_int001_joined.py`: actual C producer + real PostgreSQL/A4 + B
  planner/runner, controlled browser actuator. Verifier outage is an injected failure;
  the C reader/store are never replaced by `TestApprovals`.
- **CB**: `tests/browser/test_int001_browser.py`: normal application factory, real API
  process, actual C save/Review approval/ID handoff and real Chromium two-field final reread;
  plus event-controlled C edit during real Chromium entry. No test approval factory.
- **U**: `tests/automation/test_prefill_plan.py`: retained explicit `TestApprovals` harness
  and controlled browser. Thread/process contention tests still observe actual blocked and
  acquired-after-wait events. Its snapshot builder was tightened to the shared algorithm.
- **BB**: `tests/browser/test_prefill_browser.py`: retained real Chromium hostile-page,
  canary, truncation, overwrite, restrictions and cleanup tests with explicit test approvals.
- **UI**: `apps/web/src/features/automation/prefill.test.tsx`, plus existing Review tests.
- **C3**: `tests/applications/test_c3_approval.py`, `test_c3_export_review.py` and audit tests in
  `tests/applications/`: actual C gates/invalidation with synthetic evidence.
- **HTTP**: `scripts/int001_managed_rehearsal.py` + `scripts/verify_int001_managed_api.py`:
  opt-in test workspace, actual HTTP C/A4/B/Chromium. Locally verified two fields, both SQL
  targets, actual activation, stale GET, zero-write blocked receipt and unchanged replay.

## All 38 acceptance cases

Function names below resolve in the evidence files above. Parameterized cases run all rows.
The four required checks execute these Python/DB/browser/UI suites separately; mocked
actuators and injected failures are explicitly labelled above.

| ID | Executable evidence / exact predicate |
| --- | --- |
| INT-01 | R `test_factory_store_epoch_parity_and_saved_rendering`: same C store; distinct app epochs/state. |
| INT-02 | P `test_missing_identity_precedes_factories_and_other_org_is_hidden`; R `test_unknown_other_org_indistinguishable`; U `test_auto2_01_identity_precedes_everything_and_other_org_is_unknown`. |
| INT-03 | R factory test and CB normal-runtime joined test; P `test_actual_c_demo_question_approval_cannot_substitute_for_b_published_ids`. |
| INT-04 | R factory test compares actual saved fact rendering and distinct verified hashes; CB previews/enters it. |
| INT-05 | R `test_corrupted_saved_state_refused_by_both_readers` (7 corruptions); P `test_b_independently_refuses_tampered_real_c_envelope`. |
| INT-06 | R `test_old_version_rejection_and_store_replacement`; P real C change tests; C3 policy/fact/change-set tests share the reader predicate. |
| INT-07 | R corruption tests and `test_inconsistent_unknown_fact_fixture_cannot_authorize_a_fill`; U unresolved-token case. |
| INT-08 | R `test_concurrent_save_during_resolution_is_explicitly_refused`: bounded explicit events, save while resolution is paused. |
| INT-09 | R factory/replacement tests; P store replacement before/after entry and completion. Factory reconstruction preserves epoch. |
| INT-10 | R factory test compares metadata snapshot with content approval; corruption/rejection tests exercise both shared reader methods. |
| INT-11 | P `test_actual_c_choice_prose_never_authorizes_options_or_conditional_fields`; U typed-choice/condition boundary cases. |
| INT-12 | U `test_auto2_21_existing_conflicts_stay_held_despite_approval`, counter and attachment tests; original representative fixture unchanged. |
| INT-13 | D exact projection, source-hash, noncanonical versions and uncovered-dependency cases; legacy digest never becomes an integer version. |
| INT-14 | J `test_managed_actual_plan_grant_and_full_union_replay`; D exact target assertions; HTTP checks actual targets. |
| INT-15 | D scoped registration/currentness, mapping mismatch and other-context cases; existing DB pack test hides foreign manifests; U foreign target reads. |
| INT-16 | J missing verifier, grant-registration failure and verifier outage cases; no managed-to-unmanaged downgrade. |
| INT-17 | D `test_replacement_wins_before_old_registration`; J `test_replacement_before_preparation_registration_publishes_no_executable_plan`. |
| INT-18 | D `test_registration_lock_serializes_replacement_and_prevents_stale_registration`: observed `pg_blocking_pids`/Lock wait, then stale target. |
| INT-19 | `scripts/verify_int001_registration_mutation.py`: removed registration locks cause the exact stale-registration assertion; exact source restoration and protected rerun pass. |
| INT-20 | D replacement/idempotency/nonrevival cases; J `test_get_reads_never_register_retarget_or_renew`; same-content/new-ID replacement parameter. |
| INT-21 | J fact-only/policy-only/same-content replacement parameters at preparation and after grant registration; root behavior documented. |
| INT-22 | D unrelated-context and another-organization replacement tests; existing `tests/smoke/test_db_smoke.py::test_pack_replacement_stales_exact_dependents_and_keeps_history` preserves dependency-omitting targets. |
| INT-23 | CB normal runtime C save → Review approval → B prepare → two actual Chromium fields/final reread; HTTP also proves managed path. |
| INT-24 | P one-character edit prevents launch; CB one-character edit stales the visible plan and real API execute returns zero writes. |
| INT-25 | P question-revision case uses B's actual newer publication and blocks old plan; C2b regression tests preserve exact IDs. |
| INT-26 | J actual replacement before entry and after actual grant registration; HTTP activation → blocked receipt with zero operations. |
| INT-27 | CB event-controlled real C edit stops after one actual field; J event-controlled actual policy-only activation preserves partial receipt. |
| INT-28 | J two different fact bindings in two fields, actual plan/grant exact union and repeated boundary checks; no per-action subset equality requirement. |
| INT-29 | P expiry/store replacement after first action and at completion; J verifier outage at both boundaries; U runtime epoch/completion TTL cases. |
| INT-30 | J/HTTP completed replay unchanged after real A4 replacement; U completed/uncertain claims; P old completed-format historical replay never launches again. |
| INT-31 | U real thread/process contention unchanged; BB hostile canary, truncation, overwrite and owned-resource cleanup regressions. |
| INT-32 | CB normal Review selection/preview/action/receipt, accurate labels and changed-source next action; UI handoff/currentness tests. |
| INT-33 | J GET nonregistration/nonrenewal; CB refresh receipt recovery; UI late handoff/preparation/execution response isolation and same-key recovery. |
| INT-34 | P `test_old_pending_format_refused_but_completed_receipt_replays_historically`, including unchanged stored record/hash and direct old-grant refusal. |
| INT-35 | U production/unregistered boundaries; C3 unconfigured store/approval gates; platform production fixture-setting tests. |
| INT-36 | U other-org/strict error cases; C3 audit/redaction tests; P/CB/J zero-write reasons and hashes without answer text in errors. Authorized receipts intentionally show read-back text. |
| INT-37 | `tests/contracts` deterministic/drift/registry suites, `make contracts` + TypeScript; U strict request authority-field rejection. No unrelated registration removed. |
| INT-38 | Manual guide and opt-in HTTP verifier; normal CB and managed J/D/HTTP reproduce both labelled paths; this handoff records process-local and TigerData boundaries. |

## Limitations and next engineering increment

C storage is **process-local**, lost on restart and unsuitable across API workers. B's
filesystem repository is development-only, not TigerData durability. A4 is real PostgreSQL,
but no TigerData host was verified. The normal workspace still uses unmanaged synthetic
evidence; the managed rehearsal source is a bounded test adapter. Its writing-policy
adapter is absent (honest review items). Real authentication/permissions, real organizational
evidence/A3 check workflow and remaining export/skill consumers are separate project gates.

No typed-choice authority, public B word-counter adapter, attachment transfer, arbitrary
funder portal, navigation/upload/submit/sign tool, deployment or merge is added. Existing
registered-fixture browser restrictions are preserved, not expanded into an arbitrary-portal
or OS-level egress guarantee. Repeated C/A4 checks detect observable changes; they are not
a distributed transaction over a remote DOM. Partial writes are preserved, never repaired.

Next: **TigerData durability plus real A-evidence/workspace integration**. Sequence the
actual answer/version/decision/audit migration after 0008, implement transactional snapshot
reads with the same public predicate, persist B plan/grant/run claims and leases in PostgreSQL,
and integrate authorized A evidence/writing-policy providers. Preserve exact hashes,
original dependencies, registration unions, immutable history, tenant checks and single-use
execution. Then prove worker restart/concurrent-worker behavior and real-evidence/A3 gates;
do not enable production merely because persistence exists.

## Rollback / machine footprint

Revert task commits through review. Do not reset main or force-push. Before downgrading
0008 → 0007 stop consumers and preserve any guarded metadata; no C3 migration was applied.
New worktree `.venv`/`node_modules` are local; no global Python/npm settings changed. The
existing local PostgreSQL service was migrated forward without resetting data. Rehearsal
API processes and their temporary files/owned SQL rows were cleaned. Shared Git origin now
uses the renamed repository URL; old historical GitHub links redirect. Original worktrees
and the root input spec were preserved.

## Final verification and publication

Final tested source: `8f312bba8747bab3b2f0ed94a1dd97930a97f956` (M4 source/test
checkpoint `3a741afdb34db3dfac1d6e8409ff473fcaf4ab6b` plus frontend lint fix).
Subsequent commits only record this evidence/publication. Worktree was clean at test exit.
Final upstream fetch still resolved main to `b543454255c45e9a079e3090337585b375fe34f0`.

| Command / environment | Result |
| --- | --- |
| `make contracts` | Exit 0; deterministic schema/TS generation. All 229 baseline schema definitions retained; 231 now, adding only binding/registration models. |
| `make check` | Exit 0: Ruff and formatting, oxlint/Prettier, strict mypy (210 files), TypeScript, **782 Python tests** (84 DB/browser deselected), **100 Vitest tests**, schema/TS drift and web/Python builds. |
| `make smoke` with local PostgreSQL URL configured | Exit 0: forward migration/seed, **110 import tests**, **46 real PostgreSQL smoke tests**, real API live/ready/capabilities 200; head `0008_browser_bindings`. |
| `make browser-smoke` | Exit 0: web build and **38 real Chromium tests**, including both new normal C integration tests and all existing hostile/canary/truncation/cleanup cases. |
| `uv run python scripts/verify_int001_registration_mutation.py` with real DB | Exit 0 for audit: mutant failed specifically at `stale_registration: replacement missed the new target`; exact source restored, protected race passed. Restored SHA-256 `e0574503c6d2e4698c9c51cacf1202e70f62308ad12575d52764bc34815f44ea`. |
| `uv run python -m scripts.verify_int001_managed_api --port 18008 --replacement <printed synthetic ID>` against owned rehearsal | Exit 0: actual HTTP C/A4/B/Chromium two-field entry/final reread, both registered targets, real activation, stale GET, blocked zero operations and unchanged historical replay. Server then stopped; owned data cleaned. |

Environment: Linux, Python 3.12.15, Node 22.22.2, local PostgreSQL 17, installed Playwright
Chromium. No SQLite/mocked database substitutes, live model/search/capture calls, TigerData
host, production authentication, deployment or merge. No required task check is unrun.
The full browser suite printed test-proxy BrokenPipe messages for disconnected requests;
all 38 assertions/tests passed. The initial final-check attempt found two React effect lint
warnings; they were fixed in `8f312bb`, then the complete required checks ran successfully.

All INT-01 through INT-38 rows above have executed evidence. This is **not** a claim that
all 86 catalog predicates, G2/G4, real-data integration or release readiness are complete.
Published as **draft PR [#19](https://github.com/thegeekyqazi/strong-start-agent/pull/19)**,
base main `b543454`, task branch pushed without force. Verification-only commit `c34a550`
records local results; this publication-link commit changes documentation only. The exact
reviewable branch head is the PR head. No merge, deployment or default-branch write.
Remote CI status is reported in the completion message; local required checks above passed.
