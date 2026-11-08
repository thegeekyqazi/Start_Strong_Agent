# C3: Exact-version staff approval, invalidation and DOCX/audit export

- Task ID: C3 (lane Dev C)
- Revision: 1.0 (proposal, awaiting the project owner's explicit approval; **no C3 code before "go"**)
- Branch: `dev-c/c3-approval-export` (local only), stacked on `dev-c/c2-draft-claims` (`97be8fd`). Merge order: C1 (PR #4), then C2, then C3
- Upstream at writing: `origin/main` `e73386e`. A1 is merged (migration head `0002_source_fact_foundation`, A's evidence route); Dev B is consolidated into one agent (decision 0004)
- Engineering baseline: v1.1, s8.1 (reviewer roles), s9.2 (gates), s10.5 (APP-04/06/07/08), s10.6 (POL-05), s13.3 (JOB-02/05), s13.2 (SEC-10), s15 (states, approval snapshot, invalidation), s16 (exports), s18 ("Review" view), s20.4 (C3 row), s21 (demo steps 8, 10, 11)
- Lane plan: `docs/coordination/dev-c-lane-plan.md` rev 1.0, s3 "C3"
- Checks: APP-04, JOB-02, JOB-05, SEC-10 (P0); APP-06, APP-07, APP-08, POL-05 (P1). The catalog stays `planned` until tests prove each predicate

## 1. Goal (s20.4 C3 row)

The s20.4 row reads: "Exact-version staff approval, invalidation handler and DOCX/audit export. Needs C2 state contract; use fixture check results initially. Done after A3 real checks and edit-after-approval test. Unblocks B3 real prefill."

The staff-facing result:
1. **Save.** Staff save an answer as an immutable **answer version** (exact text and hash). C2 was stateless; C3 adds persistence (owner decision 2026-11-07 #2).
2. **Review.** The **Review** view (s18) shows:
   - the source excerpt;
   - the exact changes between versions;
   - C2's findings in reviewed mode;
   - **reviewer-role proposals** (s8.1; owner decision #1 deferred them to C3);
   - review controls;
   - export/prefill readiness.
3. **Approve.** An authorized reviewer approves **one exact version** (s9.2 gate). The approval binds the content hash plus the full dependency snapshot (s15, APP-04, JOB-05).
4. **Invalidation.** One edit, or an applicable dependency change (fact/pack/policy/question/rules), makes the approval **stale**. It cannot be replayed (APP-04, APP-06, JOB-02).
5. **Prefill hand-off.** B's prefill resolves approvals only through C's real `ApprovedAnswerResolver`, which refuses missing or stale approvals (ports.py; B2-AUTO-002 dependency).
6. **Export** (s16, APP-07, POL-05):
   - a **working** DOCX, always labelled, which may contain `XXX`;
   - a **reviewed** DOCX, blocked by unresolved blockers, unsupported claims or lost simulation labels;
   - a JSON **audit bundle** (versions, checks, source locators).

## 2. Contracts (producer C, `answers.py`; additive; existing `AnswerSnapshot`/`ApprovalSnapshot`/`DependencyRef` reused)

- `AnswerVersionCreate` (strict): `question_id`, `question_version`, `evidence_bundle_id`, `text`, `expected_answer_version` (optimistic, JOB-02; `null` only for the first version).
- `AnswerVersion`: id, `answer_id`, `answer_version`, `content_sha256`, `rendered` (C2 `RenderedAnswer`), `dependencies: list[DependencyRef]`, `state` (s15: `draft`, `checking`, `needs_attention`, `ready_for_review`, `approved`, `stale`, `rejected`), `created_by` and `created_at`.
  - `state` is **computed by server code**. It is never accepted from a client or model (SEC-14).
- `ApprovalDecisionRequest` (strict): `answer_version_id`, `expected_content_sha256`, `expected_snapshot_sha256`, `decision: approve|reject`, `note`.
- `ApprovalRecord`: the server-side record behind the existing `ApprovalSnapshot.approval_record_ref`, holding:
  - reviewer, decision and time;
  - `snapshot_sha256` (JOB-05 hash over answer, evidence/pack, question/requirements, policy, rules, counter, permissions-scope and evaluation-time policy);
  - `stale_at` / `stale_reason`.
- `ReviewerProposal`: role (`numerical_reviewer` | `meaning_reviewer`), task ID, proposed findings (C2 `AnswerFinding` shape) and `ModelRunInfo`. **A proposal only, never an approval.**
- `ExportRequest` (strict): `mode: working|reviewed`, `expected_snapshot_sha256s`, `question_ids`.
- `ExportResult`: artifact IDs, `docx_sha256`, `audit_sha256`, `blocked_by` (list of findings when reviewed mode is refused), `labels` (e.g. "SYNTHETIC DEMO DATA").
- `AuditEvent` (SEC-10): actor, action, object, version, decision and time. Configured secrets/cookies are redacted; trace access is restricted.

## 3. Persistence (owner decision #2: C3 with Dev A)

- C drafts **one bounded migration request**, `0003_answers_and_approvals`, down-revision `0002_source_fact_foundation`. It has four tables:
  - `answers`;
  - `answer_versions` (immutable rows: `content_sha256`, rendered JSON, dependency JSON);
  - `approval_records` (unique on answer version, plus `snapshot_sha256`);
  - `audit_events`.
  
  It also adds foreign keys to `organizations`, with organization scoping on every query.
- **Dev A sequences and approves the migration** (ownership.md: "A sequences after `0001_bootstrap`; other lanes submit bounded migration requests"). C does not merge a migration A has not accepted.
- **Repository port:** `AnswerStore` (C-owned), with a Postgres implementation and an in-memory **labelled fixture** for non-DB unit tests. DB behaviour is tested under the existing `db` marker (`make smoke`, CI DB job).
- Stale marking and approval are guarded transactional writes. No transaction is held open during a model call (s15).

## 4. Gates and transitions (s9.2, s15; code-controlled, never model-controlled)

| Action | Gate (all must hold) |
| --- | --- |
| Save version | Identity; `expected_answer_version` matches (else 409, JOB-02); question version current |
| Approve | Identity with reviewer authorization (s9.2 "authorized reviewer"); version is the **latest**; `expected_content_sha256` and `expected_snapshot_sha256` match a **fresh** recomputation; C2 reviewed-mode checks have no `fail`; `needs_review` items acknowledged in the decision note |
| Reject | Identity with reviewer authorization; latest version |
| Stale | Automatic: a new version of the same answer; a fixture `ChangeSet` (A's producer, A4, is not built) touching a dependency; a policy/rules/counter version change |
| Resolve (for B) | `ApprovedAnswerResolver.resolve(org, approval_snapshot_id)`: org-scoped; recomputes the snapshot hash; refuses missing, rejected or stale approvals (`ApprovalNotUsable`) |
| Export reviewed | All selected answers approved, current and not stale; no unsupported markers; simulation labels present where the inputs are simulated (POL-05) |

## 5. Reviewer roles (s8.1; owner decision #1)

- **Numerical reviewer:** inputs are the original fact values/periods and the claim bindings. It proposes findings, and arithmetic is executed by code, never by the model.
- **Meaning/policy reviewer:** inputs are the approved wording, the proposed answer and the scoped rules. It proposes meaning-change and unsupported-statement findings.
- Both run through the C2 SEC-12 coordinator. FakeAdapter outputs are deterministic and Gemini is optional.
- Reviewers see the original evidence before any other reviewer's verdict (s8.1). Their output is shown as **proposals**, separate from the deterministic findings.
- Agreement between reviewers is never a pass criterion.

## 6. Export (s16)

- **DOCX:** original questions; answers; counts with the counter version; highlighted missing/review items; source notes for each bound fact.
- **Colours:** s16 says "Use yellow/green/blue according to the supplied guide, preserving separate source approval and answer approval". U01 is not in the repo (open question 4).
- **JSON audit bundle:** answer versions and hashes, approval records, the check reports (rule ID/version, input hashes and evaluation time; APP-08) and source locators.
- **Labels:**
  - A working export is labelled "WORKING DRAFT – NOT REVIEWED".
  - Any simulated input marks the document "SYNTHETIC DEMO DATA" on every page (POL-05).
  - A reviewed export of synthetic data stays labelled synthetic (s16).
- Exports are generated on request and their hashes are recorded in the audit events. There is no background job (no JobStore; same deviation as C1 D1).

## 7. Web (s18 "Review" row; lane plan s6.4)

- The **Review** page (`features/review/`, C-owned, registered as a placeholder today) shows:
  - the answer version list with `StatusDot` (all s15 states) and `HashChip`;
  - a word-level diff between versions;
  - deterministic findings in reviewed mode;
  - reviewer proposals in a separate section;
  - the source excerpt / evidence cards;
  - approve/reject controls bound to the exact hash shown;
  - export buttons (working / reviewed) with the `blocked_by` reasons shown in plain language.
- The **Applications** page gets "Save version" and a status line ("Draft – not reviewed", "Approved (this exact version)", "Out of date – approval no longer applies").
- `StatusDot` is extended to the full s15 state set (lane plan s6.2).

## 8. Tests (each runs real code; positive, negative and boundary per rule)

| Rule | Cases |
| --- | --- |
| APP-04 | Approve v1; a one-character edit gives v2 and v1's approval becomes stale. Resolving v1 fails, and approving v1 again is refused (no replay). A policy-version change stales the approval |
| JOB-02 | Concurrent saves with the same `expected_answer_version`: one 200 and one 409. A stale `expected_snapshot_sha256` on approve → 409 |
| JOB-05 | The snapshot hash changes when any listed dependency changes; an old passing check cannot authorize approve, export or resolve |
| APP-06 | The fixture `ChangeSet` `demo-change-fact-v2` stales every dependent approval (bundle expectation `stale_after_change_set`) and nothing else |
| APP-07 | A working export with `XXX` succeeds and is labelled. A reviewed export is blocked by an unsupported marker, by a stale approval and by a `fail` finding |
| APP-08 | A check record without a rule version or evaluation time is not counted as current |
| POL-05 | A simulated fact in a reviewed export keeps "SYNTHETIC DEMO DATA". Removing the label blocks reviewed-real readiness |
| SEC-10 | Every approve, reject, stale and export writes a complete event. A missing decision fails the completeness check. A dummy secret canary is excluded from events and exports |
| SEC-14 | A client or model `state`/`approved` field is ignored or rejected; only gate code moves state |
| Resolver | Org-scoped (another org's ID behaves like an unknown ID); refuses stale and rejected approvals; contract test against the existing `ApprovedAnswerResolver` port and the B fixture expectations |

Plus the web Vitest tests (review page states, diff, blocked export reasons) and `make check`, `make smoke` (with the migration once A accepts it) and `make browser-smoke`.

## 9. Dependencies and fixtures

| Need | Producer | C3 starts with |
| --- | --- | --- |
| Migration sequencing | A | C's migration request; the in-memory fixture store for unit tests until it is accepted |
| Reviewer authorization roles | A (SEC-01 identity primitive) | The fixture identity (`fixture-staff`), allowed to approve **only** in fixture mode and labelled "fixture approval – not authentication" |
| ChangeSet publisher | A4 (not built) | The bundle fixture `demo-change-fact-v2`, injected deliberately |
| Real checks runner | A3 (not built) | C2 rules (same s9.1 shape) |
| Real questions | B (read-port request pending) | Fixture questions |
| Prefill consumer | B2-AUTO-002 | Contract test against the port; B joins at G2 |

## 10. Out of scope

- Prefill/read-back (B).
- Skills (C4).
- Durable jobs.
- Live Gemini verification (needs a key).
- Real authentication.
- The DOCX "reviewed-real" release for partner data (no supplied data is in the repo).

## 11. Open questions for the owner (please answer with "go")

1. **DOCX library:** add `python-docx` as a new API dependency (lockfile change through Dev B's lockfile coordination), or build minimal OOXML with the standard-library `zipfile` and no dependency? Recommendation: `python-docx`, as it is smaller and safer than hand-written OOXML.
2. **Migration:** may C draft `0003_answers_and_approvals` and send it to Dev A for sequencing? Recommendation: yes. C3 persistence is then integrated only after A accepts.
3. **Who may approve:** in fixture mode, may the drafting fixture identity also approve? The plan does not specify drafter/approver separation. Recommendation: allow it in fixture mode, labelled, and record the question for real roles.
4. **Colours:** yellow/green/blue mean something in U01, which is not in the repo. Recommendation: omit the colour coding and use text labels until U01 is supplied, rather than guess.
5. **Increments:** split C3 into C3a (persistence, gates, resolver, invalidation, review view) and C3b (reviewer roles, export)? Recommendation: yes, two PRs. C3a unblocks B's prefill sooner.

## 12. Owner decisions and implementation notes (2026-11-08; working tree, not committed)

Owner answers to s11:
1. `python-docx` (with `lxml`) is added. `uv.lock` was regenerated and flagged for Dev B.
2. C drafts the migration for Dev A.
3. In fixture mode the demo identity may draft and approve, labelled.
4. Plain text labels, no colours.
5. Full C3 (C3a + C3b) in one increment.

| # | Spec text | Implemented | Why |
| --- | --- | --- | --- |
| 1 | Migration `0003_answers_and_approvals` | Drafted as **`0004_answers_and_approvals`** (down-revision `0003_artifact_text_ingestion`) in `docs/handoffs/dev-c/c3-migration-request/`, **outside** `migrations/` | A2a already took `0003`, and `migrations/` is A-owned. An active file would change the head and break readiness on `main` |
| 2 | Postgres `AnswerStore` plus fixture store | **Fixture in-memory store only** (labelled; lost on restart). Outside fixture mode the store is `CapabilityUnavailable` (503) | There are no tables until Dev A sequences 0004. An untested Postgres store would be dead code |
| 3 | Reviewer roles only | Plus **human review notes** from any signed-in identity, with no approval rights | Owner directive: "secondary reviewers add notes/findings without direct approval rights" |
| 4 | Blocked reviewed export | `POST /exports` returns **200** with `blocked: true`, `blocked_by` and no artifact | A typed result the UI can explain. No file exists when blocked |
| 5 | (not specified) | Working DOCX exports list **working-mode** findings; reviewed exports use reviewed mode | s9.2: working drafts allow incomplete work with visible markers |
| 6 | Fixture ChangeSet injection | `POST /api/applications/fixture/change-sets/{id}/apply` (fixture mode only) records the change set in C's store; staleness is evaluated live | A4 (A's publisher) is not built; nothing of A's is modified |
| 7 | Resolver for B | `StoreApprovedAnswerResolver` and the provider `review_router.get_c_approved_answer_resolver` | Wiring it into the shared `strongstart_api/ports.py` provider is a shared-host change and was **not** made |
| 8 | Shell shared files | `StatusDot` covers all seven s15 states | C-owned shell; additive |
