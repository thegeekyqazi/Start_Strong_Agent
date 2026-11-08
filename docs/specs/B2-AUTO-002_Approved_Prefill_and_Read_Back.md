# B2-AUTO-002: Approved prefill and verified read-back

**Revision:** 1.0  
**Owner:** Dev B, one agent; automation module  
**Prepared:** November 8, 2026, America/Toronto  
**Repository:** `thegeekyqazi/Start_Strong_Agent`  
**Inspected main:** `51f19f41c585a183e859e989044190bdc18fc6aa`  
**Suggested branch:** `dev-b/b2-auto-002-approved-prefill`  
**Repository spec path:** `docs/specs/B2-AUTO-002_Approved_Prefill_and_Read_Back.md`

**Engineering baseline:** `docs/engineering/StrongStart_Engineering_Plan.md` v1.1, sections 4, 7, 9.2, 10.5, 10.7, 12.4, 13.2–13.3, 14–16, 18–20 and 21. Especially: exact-version approval, source/permission currentness, bounded actions, staff-only submission, public module contracts, and G1/G2.

## 1. Outcome

Staff select an application definition and a registered representative portal, select existing approved answers, inspect a server-built entry plan, and explicitly authorize filling the selected fields. The tool enters only server-resolved approved content in a real restricted Chromium page, reads the actual field values back, and shows exactly what matched or failed. Nothing submits, signs or sends an application to a funder.

This is the next normal Dev B feature task after DEV-B-BUNDLE-002. It is not another broad discovery/deployment bundle. It includes basic stale-input rejection, bounded execution and honest partial/unknown outcomes necessary for prefill. Full recovery/resume and A4 propagation belong to B2-AUTO-003; production deployment belongs to B1-OPS-001.

The first runtime is a **registered local fixture portal**. A real Chromium interaction with simulated approvals is a functional demo, not production funder-portal automation. Arbitrary URLs, authenticated funder accounts, file upload and submission are outside this task.

## 2. Verified baseline and real dependency gaps

| Component | State at inspection | Consequence |
| --- | --- | --- |
| DEV-B-BUNDLE-002, PR #12 | Merged, including atomic funding-case binding and contention-event tests | Saved definitions, original/published ID mapping and public readers exist. |
| B2 inspection | Real restricted Chromium; representative portal, fingerprints, mapping and blocked-network evidence | Reuse these boundaries; do not rewrite the inspector into unrestricted automation. |
| C2 | Merged, but workspace still fixture-backed | B's saved definitions do not automatically appear in C's approval workspace. C2b remains a separate integration. |
| C3, PR #10 | Open; inspected head `de8c2a2e8077015f12133cf11092cb4032866675` | Proposed resolver can be inspected, but is not a merged production dependency. |
| C3 answer storage | Labelled process-local fixture store; no active approval migration | Approval state is lost on restart; production prefill must stay unavailable. |
| C3 `ApprovedAnswerResolver` | `resolve(org, approval_id)` returns `ApprovalSnapshot`: approval ID, answer-version ID, hashes and dependencies | **It does not return answer text or rendered text.** B cannot fill a field from this interface alone. |
| C3 hash semantics | `content_sha256` hashes the editor/template text; stored `RenderedAnswer` has a separate text hash | Never compare a template hash directly with rendered field text, or insert unresolved fact tokens. |
| A3 | Source and numeric validation merged, migration `0006_numeric_validation` | This is not automatically a browser-action authorizer or a shared DAT/ELG registry extension. |
| A4, PR #15 | Open at inspected head `db3c28eec4a8f6700276a456b2f02290cf5b83aa` | Pack currentness/dependency registration proposal exists, but no live B browser-grant integration is assumed. |
| Shared API port provider | `strongstart_api.ports.get_approved_answer_resolver` still defaults to unconfigured | Adapter wiring is explicit; no hidden seeded approval fallback. |

The original inspection maps source IDs such as `rp-mission`; saved definitions publish namespaced IDs such as `def-…:rp-mission`. C's old fixture uses IDs such as `mission-q1`. **These are different identities. Similar wording is not a mapping.**

Main and the pending branches are moving during merge resolution. Fetch current upstream at task start and at dependency checkpoints; record actual SHAs and updated interfaces. If C3/A4 merge before implementation, use their final merged contracts, not stale PR snippets. No agent should manually merge generated contract outputs from several lanes.

## 3. Execution phases and definition of done

| Phase | Authorized work | Dependency/status gate |
| --- | --- | --- |
| **P0** | Read code/specs; publish the approved-content contract request to C; define B's plan/run models | Can start now from current main. |
| **P1** | Planner, finite form mapping, scoped action grants, executor/read-back, attachment checklist and UI, using an explicitly injected test approval provider | No C internals or approval fabrication in application runtime. Label this fixture/harness-complete. |
| **P2** | Consume merged C3 through its public approved-content interface; test real save/approve/resolve/entry path | Requires C3 merge plus the content interface below. Matching real B question identities requires C2b or a C-owned test workspace adapter. |
| **P3** | Final verification, browser evidence, handoff and PR | Full task completion requires P2. If upstream remains absent, finish all independent P1 work and open a clearly partial draft PR with exact blockers. |

Do not block P0/P1 on pending merges. Do not merge C3/A4 yourself, copy their private modules into B, invent an approval, or call a test double a joined integration. Maintain one active task branch/worktree for Dev B and preserve local work. The owner handing over this spec authorizes implementation within scope; routine implementation choices do not require another confirmation.

## 4. Read first and preserve ownership

Read `AGENTS.md`, decision 0004, current ownership/single-agent plan, the applicable catalog entries, B2-AUTO-001, DEV-B-BUNDLE-002 and its final/question-reader/funding-case handoffs. Read C3's current spec, resolver, public dependency wiring and handoff; C2's question-reader request; A4's current dependency/currentness handoff when available.

B owns the executor, form bindings, grants, read-back reports, attachment checklist and Automation UI. C owns answer content, approval decisions/currentness and access to its answer store. A owns active-pack/access primitives, database migration sequencing and TigerData. Consumers use public contracts/factories, not another lane's private tables, functions or HTTP routes called through loopback.

Narrow shared changes allowed: additive B-owned contracts and registrations, generated Schema/TypeScript, automation capability/dependency wiring and appropriate tests. Any C-owned approved-content implementation is a coordinated C change, not permission for B to rewrite C. Publish a concrete contract request and continue independent work.

## 5. Required approved-content interface — coordinate with C

### 5.1 Missing producer, not a client payload

`ApprovalSnapshot` proves which version C resolved but contains no content. Do **not** fetch a browser-supplied answer and compare only its claimed hash. Do not reach into C's `StoredVersion`, `AnswerStore`, resolver private `_find`, or the approval router's internal context.

Request one narrow C-owned public reader, preserving the existing shared resolver protocol. Suggested semantics:

```python
class ApprovedPrefillReader(Protocol):
    is_fixture: bool

    def resolve_for_prefill(
        self, organization_id: str, approval_snapshot_id: str
    ) -> ApprovedPrefillContent: ...
```

The response must be one authorized, consistent envelope, not unrelated unchecked reads:

| Content | Required verification/meaning |
| --- | --- |
| `ApprovalSnapshot` | C resolves it live and rejects missing, rejected, stale and other-organization approvals. |
| Answer/question identity | Exact answer-version ID, question ID/version and question-set/application selection identity. Matches the selected B published version, not a title. |
| Approved editor/template text | Exact text and its SHA-256; agrees with C's `ApprovalSnapshot.content_sha256`. |
| Approved rendered text | Exact saved `RenderedAnswer.text`, its independent SHA-256 and renderer/dependency metadata; no unresolved `{{fact:…}}` or `{{unsupported:…}}` goes to the form. |
| Dependency snapshot | C's exact approval snapshot hash, dependency versions and currentness result; a fresh recomputation must still match. |
| Provenance/runtime | Fixture/simulation labels, supported data class and current producer instance/availability as needed. A real reader over a fixture store still returns simulated data. |

C must verify that the returned rendered text belongs to the same approved immutable answer/dependency snapshot. B independently recomputes both hashes and rejects any mismatch. B does not rerender facts using a different evidence bundle or substitute values after approval.

C may implement the reader by extending its resolver with an additive supported method or publishing a separate interface. Agree the exact names/imports in a handoff. Default is unconfigured and fails closed. Do not weaken or change the existing `ApprovedAnswerResolver.resolve()` return type silently.

### 5.2 Field values and typed answers

Text inputs receive the approved rendered string. Number controls receive that exact approved string only when it conforms to the field's confirmed input format; do not strip currency symbols, trim, round or translate words into digits. Select/radio/checkbox fields require an explicit C-authorized typed value matching a registered option/control. A prose answer is not automatically a choice value.

If C does not yet expose approved choice values, enable text-field entry and report choice controls unsupported/held. P1's explicit test provider may exercise typed choices and conditions; P2 capability must distinguish the supported real producer types. Do not claim full conditional entry until that producer path works.

### 5.3 Currentness and concurrent edits

Resolve C's live approval at planning time and again immediately before **each** field action; compare exact identity, template/rendered hashes and dependency snapshot with the grant. Revalidate after the field action and at run completion. B's own definition, case binding, map and grant must also remain current.

An edit before an action prevents that action. An edit during an in-flight browser operation may occur after the last precheck: stop remaining actions, label the run stale/partial or outcome-unknown as appropriate, and do not present it as a current verified handoff. Do not claim a zero-race guarantee for external writes from pre/post checks alone. A stronger atomic authorization primitive requires a separately agreed C/A action permit or coordinated lock; B's funding-case pin does not pin C approvals or A packs.

Do not hold an unrelated B repository lock while invoking C or operating Chromium. If a shared action guard is added upstream, consume its published contract, document lock order/lifetime and prove contention with events. No lock may silently freeze staff editing for an unbounded browser operation.

## 6. Server-built form binding and entry plan

### 6.1 Definition and portal identity

Select one exact saved `question_set_id` through `ApplicationDefinitionReader`. Bind it to a registered fixture portal's ID, exact page/source hash, form ID/version and fingerprint algorithm. The server derives selectors and expected types from the trusted registry; clients cannot provide arbitrary URLs, HTML, JavaScript or selectors.

Use the saved publication's original-to-published ID mapping to connect the registry's original question IDs with the published IDs. Require a unique, complete mapping for every selected field and expected control group. C approvals must name those exact published IDs/versions. Never map by question wording or list position; never rename an approval's question ID to make it fit.

Keep any generated bound form map in a new versioned wrapper. The old inspection `FormMap` is tied to its original IDs; do not silently reuse it as a map for a saved definition. Preserve old read-only inspection behavior and fingerprint semantics for existing consumers.

Reinspect on execution in the same browser document that will receive input, before its first mutation. A fingerprint/map prepared in an earlier browser instance is an expectation, not proof that the new document still matches. Reject unexpected missing/duplicate controls, option changes, unsupported widgets, newly required controls or an unexpected origin before writing.

### 6.2 Plan contents

Add B-owned contracts in a new module such as `automation_prefill.py`; do not expand the old read-only contracts by changing their literal false fields. Suggested `PrefillPlan` includes:

- Format `b2-approved-prefill/1`, ID, exact plan hash, definition/question-set/version/digest and provenance.
- Registered fixture ID, source/page hash, form/fingerprint version, logical origin and inspected structural state.
- Ordered selected field actions: published question ID/version, trusted field ID/control type, approval/answer-version IDs, approved template/rendered hashes, intended value, type/counter/normalization versions and dependencies.
- Held/excluded fields with specific reasons; original unresolved requirements, conditional dependencies and attachment checklist.
- Scope label: selected-fields demo only; it is not the entire application's completeness or eligibility result.
- Created actor/time, expiry expectation, producer/runtime epoch and capability labels.

Plan construction performs no DOM writes. The staff sees the exact text/value to be entered, which version was approved and what remains held. A pending/stale approval, integrity failure or mapping conflict must not be hidden by an empty plan or a success badge.

### 6.3 Requirements gate and conditional fields

An answer approval does not resolve B's competing limits, unknown units, unmatched context or unsupported mapping. Hold fields with `held_unresolved_requirement` or missing action-critical constraints. Unknown conventions must not be reported as a passing count.

For deterministic positive fixtures, use clearly labelled source definitions with unambiguous supported constraints, such as native maxlength with its known UTF-16 convention. If necessary add a dedicated prefill fixture; do not rewrite the existing 350/500/Max 300 cases or mark their ambiguity resolved just to demonstrate success. The original malformed/held fixtures remain negative cases.

For eligible fields with confirmed limits/conventions, enforce the applicable C-owned counter through its public/shared supported contract or a documented adapter; do not invent a second word-count convention. Independently respect native maxlength/range/choice constraints before entry and verify browser behavior afterward.

A selected conditional child requires a supported explicit predicate and the exact approved parent choice. Parent entry may reveal a child; wait for the registered ready condition, then remap/check the declared branch state before child entry. Only declared visibility/branch transitions are allowed. Unexpected fields/options/fingerprint changes stop the run. An unresolved or unsupported predicate stays held; no execution of source-supplied condition strings.

Partial prefill is explicit: staff can select eligible fields while other fields remain held, but the result says only those selected fields were verified. An empty selected action list is not an executable successful plan. Missing required fields/attachments remain visible.

## 7. Exact action authorization and single-use execution

Add a separate explicit **Fill these approved fields** command. Preparing a plan is not permission to execute it. The execution request carries plan ID, expected plan hash and a request/idempotency key, not field content, a selector, organization, `approved=true` or a model-created action list.

The server derives a short-lived grant bound to:

- Server organization and actor; exact selected plan and approval/dependency hashes.
- Registered logical portal identity and runtime-resolved fixture origin; exact form fingerprint/state and allowed fields/operations.
- Creation/expiry time, one execution nonce and supported runtime epoch.
- Finite budgets; no capability to click submit/sign, navigate elsewhere or upload files.

Use the existing Dev B local store behind a small public B-owned grant/run repository port, with production disabled. Claim execution atomically across threads/processes. One plan/grant must not produce duplicate field writes when two execute requests race. A completed idempotent retry returns its historical receipt without launching a browser or writing again; label any later dependency staleness separately. Reusing a key for a different command is 409.

Persist the claim/intent before the first possible DOM mutation and per-field progress sufficient to distinguish not-started, entered/read-back, failed and uncertain. A process crash after a possible write is not automatically retryable. An already claimed incomplete run returns running/unknown status; do not silently execute it again. A new staff action requires a newly prepared/revalidated plan where permitted. Full resumable recovery is B2-AUTO-003.

Initial budgets: 120-second maximum plan/grant lifetime; one Chromium execution per claimed grant; at most 20 selected actions; 30-second overall execution cap; bounded per-operation waits and source/field text sizes using existing limits. Use an injected server clock for tests. No automatic retries of field writes, no scheduled run and no fake durable JobStore.

C3's current fixture store is process-local. Until a durable producer exists, integrated runtime support is **local, single API process, fixture-only**. Bind plans/grants to a runtime epoch; after restart or routing to an incompatible process, fail before browser entry. B's cross-process claim tests do not establish that C's approval store is distributed.

## 8. Restricted Chromium execution and read-back

Create a fresh browser context for the registered local fixture, using the established network boundary: allowed registered GET document/resources only; reject redirects and other origins/private services, WebSockets, popups, downloads, service workers and mutation requests. The narrow local loopback exception is only for the server-owned fixture instance, not arbitrary localhost URLs.

Use finite registered operations: text `fill`, approved `select_option`, radio/checkbox `check`/`uncheck` where supported. No general `click`, keyboard Enter, submitted form, arbitrary script, uploaded JavaScript or model-generated browser instructions. DOM inspection uses trusted fixed application code. Source page scripts may attempt requests; interception and the fixture server must still deny mutation/submit/sign endpoints.

Keep the same document/context from execution-time inspection through entry and read-back. For each field:

1. Recheck live authorization/current versions and grant expiry; resolve approved content through C.
2. Resolve the expected unique control/group; verify its type, enabled/visible/editable state, applicable branch and confirmed constraints.
3. Record the intended action/hash, then perform exactly that bounded registered operation.
4. Read the final DOM property/value, checked option or selected value. Do not read a stale HTML `value` attribute as proof of the live control state.
5. Compare actual with intended and record exact hashes, lengths, comparison convention and result.
6. Recheck dependencies; stop on mismatched value, unexpected navigation/state or stale inputs. After all entries, reread every written field so a later script cannot silently overwrite an earlier verified value.

Default comparison is exact Unicode string equality. A narrow documented textarea newline convention may account for native DOM line-ending normalization; record raw and compared values/hashes plus the algorithm version. No trimming, case folding, Unicode normalization, truncation acceptance, currency removal or other repair. The staff must edit/reapprove any materially transformed content.

Detect maxlength truncation, rejected numeric input, script replacement, disabled-field rejection and unexpected choice coercion. Stop further writes, preserve the mismatch, and do not auto-correct or retry. Mark completed fields and partial effects plainly. Known browser launch failure before any writes is a failed zero-effect run; a timeout/connection loss after a possible write may be `outcome_unknown`.

Close context/browser/Playwright and fixture server in `finally`, including timeout/cancellation/error paths. The demo does not save form values to a real funder service or leave an authenticated portal session for staff. The UI shows a read-only entry receipt backed by actual Chromium read-back; say that the ephemeral fixture page closes after the run. Real portal handoff is later scope.

## 9. Attachment checklist — no upload in this slice

Preserve source-required attachment types/counts/sizes and their confirmation status. Compare a server-resolved artifact/manifest, when a supported authorized reader exists, against those constraints using actual size/hash/type evidence. A client filename/MIME declaration is not proof of file type; a manifest field cannot make a nonexistent file available.

With no approved artifact reader or an unresolved source rule, show **needs review / unavailable**. Use explicit trusted synthetic artifact records in tests. Keep wrong type, excessive size/count and missing required items visible. This is **AUT-04 checklist coverage**, not actual upload verification.

No `set_input_files`, multipart POST, file transfer to a third party or `attach_file` execution is enabled. Existing shared `PrefillAction` may represent attach_file, but this executor's operation allowlist refuses it. Selected text entry may still be demonstrated while required attachments remain outstanding; the report cannot say the application is complete or ready to submit.

## 10. API, UI and report semantics

Suggested routes under the existing automation router:

| Route | Result |
| --- | --- |
| POST `/prefill-plans` | Server-derived plan/held fields from selected immutable definition, fixture and approval IDs; no writes. |
| GET `/prefill-plans/{id}` | Authorized saved plan and current availability/staleness, not a refreshed replacement for the same hash. |
| POST `/prefill-plans/{id}/execute` | Explicit staff-authorized bounded run; a completed replay returns its receipt. |
| GET `/prefill-runs/{id}` | Authorized immutable progress/result history with separate currentness. |

Add strict B request models and safe structured errors. Identity checks precede body/store/approval/browser work. Missing/other-org IDs are indistinguishable; use 409 for stale/hash/grant conflicts, 422 for malformed/unsupported commands, 503 for unavailable reader/browser, and meaningful bounded-timeout/unknown-outcome reasons. No raw exceptions, filesystem paths, credentials or full private answer content in generic errors/logs.

Report per field: intended approved answer/version/hash, actual read-back/hash, result, source/requirement refs, comparison convention and clear next action. Report per run: actor/time, definition/form/fingerprint versions, grant scope, fields entered/verified/failed/not attempted, blocked network activity, freshness/revocation checks, final outcome and simulation labels. Use **selected fields verified**, **stopped with partial entry**, **blocked before entry** or **outcome unknown**. No automatic final-submitted state exists.

Extend Automation UI with preparation, exact plan preview, held-field/attachment list, explicit execute button, bounded running state and receipt. Preserve current intake/saved definitions/inspection. Disable double clicks, keep run/request identity across a lost response, and never re-execute on page refresh. A UI page click or a model message cannot bypass the server action gate.

Capabilities must distinguish read-only inspection, plan preparation, fixture-provider execution, integrated C3 execution, attachment checklist and unavailable real-portal/upload/submission features. Existing `FormInspectionResult.prefill_permitted=false` stays unchanged; an inspection result alone never authorizes entry.

## 11. A4 integration boundary and future recovery

If A4 is merged and a supported in-process dependency/currentness interface is available, register B plan/grant target IDs with exact pack/source/fact/policy versions and read currentness immediately before action. Use an explicit adapter; no private A table reads or API-loopback calls. Missing registration/currentness for an A4-managed dependency must be unavailable/held, never assumed current.

If the merged A4 exposes only routes and no supported in-process consumer factory, publish the precise B request and keep that integration pending. P1 uses a deliberately injected test currentness provider. A C3 fixture ChangeSet test can prove the resolver rejects stale approvals; it is not proof of real A4-to-B propagation.

B2-AUTO-003 owns the complete pack-switch → stale grant → recovery sequence and real restart/resume strategy. This task must nevertheless reject observable staleness and must never reuse a pending action after known invalidation. Separate **B/C fixture currentness**, **A4 currentness adapter** and **full G4 integration** in the handoff.

## 12. Deterministic acceptance matrix

These **32 task-local cases** implement/test specific catalog predicates, not 32 new catalog rules. Primary B coverage: AUT-01/02/03, AUT-04 checklist subset, SEC-03 fixture boundary, SEC-08/09 and JOB-03 bounded action subset. Consume C's APP-04 and shared SEC-01/13/14 boundaries; do not claim all 86 checks verified.

| ID | Required evidence |
| --- | --- |
| AUTO2-01 | Missing identity returns 401 before approval/store/browser access; other-org plan/approval/run indistinguishable from unknown. |
| AUTO2-02 | Strict requests reject extra approval/content/org/selector/URL fields, coercion, malformed IDs, oversize lists and repeated field/approval mappings. |
| AUTO2-03 | Public approved-content reader returns one consistent authorized envelope; unavailable reader never falls back to seeded approvals. |
| AUTO2-04 | Template hash and rendered hash tested independently; mismatched IDs/hash/dependency snapshot rejected; unresolved fact tokens never entered. |
| AUTO2-05 | Source `rp-*`, published `def-…:rp-*` and C fixture IDs cannot substitute; explicit publication mapping works and ambiguous mapping fails. |
| AUTO2-06 | Every selected field/control group resolves uniquely; duplicate, missing, changed type/options/new required widget fails before writes. |
| AUTO2-07 | Prepared fingerprint/page hash changes before execution: blocked with zero writes in the actual execution document. |
| AUTO2-08 | A plan request performs no entry; forged model/client approval or direct executor call without a valid grant fails. |
| AUTO2-09 | Grant binds actor/org/plan/form/origin/fields/hash/expiry/runtime epoch; changing any action-critical value prevents entry. |
| AUTO2-10 | Two concurrent execute requests/process claim attempts produce one execution; completed retry returns receipt with zero new browser writes. |
| AUTO2-11 | Interrupted/incomplete claimed execution is not replayed as another write; unknown effect is labelled and later actions stopped. |
| AUTO2-12 | Expired grant, restart epoch or unavailable C fixture store prevents execution; historical receipts remain historical only. |
| AUTO2-13 | Unknown/rejected/stale approval blocked at planning and immediately before its field; one-character edit after preparation causes zero affected-field writes. |
| AUTO2-14 | Approval/dependency edit during an action triggers postcheck staleness, stops remainder and cannot yield a current successful receipt. Use events/barriers at exact steps. |
| AUTO2-15 | Definition/case context version or requirement hold changes before execution; no silently substituted latest definition/map or approval. |
| AUTO2-16 | Two approved text fields filled in real Chromium; live DOM values/hashes match and final reread verifies both. |
| AUTO2-17 | Browser maxlength truncation, scripted replacement and invalid number rejection detected; no trim/repair/retry accepted. |
| AUTO2-18 | Leading/trailing spaces, Unicode/emoji, apostrophes and line breaks tested; only declared narrow textarea newline comparison allowed. |
| AUTO2-19 | Typed approved choice resolves exact registered option; prose-to-choice inference and absent option rejected. If real C choices unavailable, capability remains held. |
| AUTO2-20 | Supported conditional parent reveals child; declared branch remapped before entry. Unresolved predicate/unexpected structural change stops it. |
| AUTO2-21 | 350/500 conflict, Max 300 unknown unit and unconfirmed action-critical conventions remain held despite C answer approval. Positive fixture does not rewrite them. |
| AUTO2-22 | Wrong/missing/oversize attachment manifest produces findings; nonexistent/client-claimed artifact not treated as validated; upload operation denied. |
| AUTO2-23 | Submit/sign/button-click/Enter/navigation operations unrepresentable or denied; fixture submit endpoint denies automation even if page text requests submission. |
| AUTO2-24 | Hostile page attempts external/private/metadata/redirect/WebSocket/POST/popup/download activity; denied with canary service zero hits. |
| AUTO2-25 | Browser missing/launch failure is unavailable with zero writes; timeout after possible entry is partial/unknown, not a fake success. |
| AUTO2-26 | Browser/context/server close on every exit, with bounded waits, no write retry and no orphan runtime session. |
| AUTO2-27 | Plan/execution UI preserves selected scope, exact approved preview, held fields and receipt; refresh or late response does not cause duplicate entry or overwrite a newer selection. |
| AUTO2-28 | Runtime and stored source strings render inertly; reports/logs are org-scoped and redact credentials; plans/grants do not leak across tenants. |
| AUTO2-29 | Same plan/provider contract tested against explicit fixture double and merged C3 real provider. Actual C-owned save→approve→resolve→entry tested for matching question IDs. If blocked, report P2 pending. |
| AUTO2-30 | C3 ChangeSet/dependency change rejects remaining actions; A4-managed target stale/unavailable prevents action when its adapter is enabled. Distinguish fixture vs actual A4 integration. |
| AUTO2-31 | Production and unsupported arbitrary portals remain unavailable; no hidden local/fixture fallback. Existing read-only literal-false contracts remain unchanged. |
| AUTO2-32 | Existing funding/intake/library/case/search, C and A regressions pass after additive contract generation; new real-API Chromium test proves the selected-fields receipt. |

Do not infer lock contention from sleeps, Future.done() or Queue.empty(). If testing atomic claims/guards, use explicit observed contention/acquisition events and run a mutation check with the protection disabled. Keep the correction and proven patterns from BND-26 rather than reintroducing timing-dependent tests.

## 13. Implementation and integration checkpoints

1. Commit this spec and a short task decision on scope, exact-content/hash semantics, ephemeral fixture execution and unavailable producers. Record current baseline and open upstream PRs.
2. Publish `docs/handoffs/dev-b/b2-auto-002-approved-content-request-r1.md` with the concrete C producer gap and proposed DTO/protocol. Coordinate through the existing repo PR discussions when authorized by AGENTS.md; do not send unrelated messages.
3. Add strict B-owned plan/grant/run/read-back contracts and unconfigured producer adapters. Regenerate schema/types at a coherent checkpoint, preserving every A/B/C registration.
4. Implement planner and original/published ID binding; then claim/grant repository and finite executor. Reuse restricted-browser primitives without weakening existing read-only inspection.
5. Add fixture/harness tests and UI. Start with two eligible text fields, then supported typed choices/conditions and attachment checklist. Preserve clear capability granularity for anything still blocked.
6. After C3 and required producer interfaces merge, update the task branch with current main. Resolve Python contracts first and **regenerate** schema/types; do not repeatedly hand-merge generated files. Join P2 against the final public C reader and exact question identities.
7. Verify, write a durable handoff and open/update the task PR. Do not merge directly or claim that P1 alone closes G2.

For one-owner cross-module B code, use supported public readers/factories, including the funding-case pin only where its semantics apply. Keep lock order explicit. No C/A source rewrite is authorized to hide an unavailable dependency. Do not apply C's draft migration request; A assigns the actual next migration revision after its own branches land.

## 14. Verification, manual demonstration and delivery

Discover current repo commands; at inspection:

```bash
make contracts
make check
make smoke
make browser-smoke
```

Run focused tests during implementation, then the complete required checks on final code. Use current merged A migration head, not a hardcoded historical number. No paid Tavily/Firecrawl/Gemini call is required for this task. Do not inspect/copy secret values into test output or handoffs.

Manual/real-browser demonstration:

1. Open a saved definition with known original/published IDs and an eligible registered prefill fixture. Explain the fixture's source labels.
2. Use C's real fixture-mode save/review API/UI to create a current approval for a matching question; show exact approved template versus rendered text and hashes.
3. Prepare a plan. Show selected values, source/approval versions, held conflicting fields and missing attachments. No entry has happened yet.
4. Explicitly execute. Show read-back for the actual Chromium control values and the final selected-fields receipt, with no submission.
5. Edit an answer after planning and show execution rejected for the stale approval. Demonstrate duplicate execute returning the same historical receipt without writing again.
6. Trigger truncation or a changed form and show a concrete failure, unchanged approval history, stopped remaining fields and honest partial/unknown status.
7. Show that the browser session closes, the receipt is a local demo artifact, and no funder portal state was saved.

If C2b's real question selection is not joined, perform the C3 producer contract test through a C-owned test workspace adapter and record that the staff UI G1/G2 path is still pending. Do not silently relabel approvals from `demo-bundle@1` as approvals for B's new IDs.

Required final handoff: `docs/handoffs/dev-b/b2-auto-002-approved-prefill-r1.md`, with exact branch/head/PR, spec revision, P0–P3 status, public contracts/factories, producer versions, all AUTO2 acceptance outcomes, test commands/results/omissions, fixture vs integrated status, race guarantees/limitations, unresolved A/C dependencies and the next task.

Update the current Dev B plan and task-specific decision record. Use the repo PR template and detailed engineering/task/check citations in commits. Keep historical handoffs intact. State **fixture/harness complete, integrated producer pending** when appropriate; full completion requires the C3 producer path and truthful capability status.

## 15. Review references

- [Merged B baseline](https://github.com/thegeekyqazi/Start_Strong_Agent/tree/51f19f41c585a183e859e989044190bdc18fc6aa)
- [B bundle PR #12](https://github.com/thegeekyqazi/Start_Strong_Agent/pull/12)
- [C3 PR #10](https://github.com/thegeekyqazi/Start_Strong_Agent/pull/10)
- [Inspected C3 resolver](https://github.com/thegeekyqazi/Start_Strong_Agent/blob/de8c2a2e8077015f12133cf11092cb4032866675/services/api/src/strongstart_api/features/applications/resolver.py)
- [C3 save/hash/render semantics](https://github.com/thegeekyqazi/Start_Strong_Agent/blob/de8c2a2e8077015f12133cf11092cb4032866675/services/api/src/strongstart_api/features/applications/approval.py)
- [Existing B inspector](https://github.com/thegeekyqazi/Start_Strong_Agent/blob/51f19f41c585a183e859e989044190bdc18fc6aa/services/api/src/strongstart_api/features/automation/inspector.py)
- [Existing registered portal mapping](https://github.com/thegeekyqazi/Start_Strong_Agent/blob/51f19f41c585a183e859e989044190bdc18fc6aa/services/api/src/strongstart_api/features/automation/registry.py)
- [A4 PR #15](https://github.com/thegeekyqazi/Start_Strong_Agent/pull/15)
- [A4 currentness/dependency handoff](https://github.com/thegeekyqazi/Start_Strong_Agent/blob/db3c28eec4a8f6700276a456b2f02290cf5b83aa/docs/handoffs/dev-a/a4-pkg-004-pack-replacement-r1.md)

This document specifies future work. No feature implementation, live model/provider call or test execution occurred while preparing it.
