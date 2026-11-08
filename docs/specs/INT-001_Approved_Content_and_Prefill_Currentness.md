# INT-001 — Approved content and prefill currentness integration

**Revision:** 1.1  
**Date:** 2026-11-08, America/Toronto  
**Status:** Implementation specification; no implementation or deployment claimed.  
**Owner:** Project owner, now responsible for engineering across former A/B/C lanes. One coding agent, sequential milestones.  
**UI/UX owner:** Sawaab. Coordinate functional frontend changes with his presentation work.  
**Repository:** `thegeekyqazi/Start_Strong_Agent`  
**Verified baseline:** `main` at `b543454255c45e9a079e3090337585b375fe34f0`, merged PR #17. Post-merge CI run `42474740195` succeeded.  
**Suggested task branch:** `integration/int-001-approved-content-currentness`  
**Repo destination for this file:** `docs/specs/INT-001_Approved_Content_and_Prefill_Currentness.md`

Revision 1.1 names Sawaab as UI/UX owner; implementation scope and acceptance cases are unchanged.

## 1. Objective and scope

Connect the existing Applications save/approval implementation to the existing approved-prefill implementation through supported public interfaces. Add the real A4 registration/currentness bridge so a changed active knowledge pack prevents a pending browser operation from using the old dependency snapshot.

At completion, a staff member can save and approve an answer for B's actual published question IDs, prepare selected fields, explicitly execute once on the registered representative portal, and inspect real Chromium read-back. Editing the answer, revising the question definition or replacing its managed pack stops the affected pending operation. Synthetic data and the representative portal remain visibly labelled.

This increment closes the remaining **P2 producer connection** of B2-AUTO-002 for the supported local-demo scope. It supplies evidence toward G2/G4; it does **not** independently close those project-wide gates. G2 also needs the real organizational evidence/check workflow, and G4 includes other consumers such as exports and skills.

### 1.1 Required deliverables

1. A C-owned, consistent approved-content reader and public factory.
2. A supported in-process A4 currentness facade with guarded registration.
3. Explicit mapping between C approval dependencies and A4 dependency identities.
4. B plan/grant registration, action-boundary checks and accurate currentness labels.
5. A usable Applications/Review → Automation handoff with minimal functional UI changes.
6. Joined API/Chromium tests using C's actual save/approve producer, plus real PostgreSQL/A4 invalidation tests.
7. Updated ownership notes, capability descriptions, decision record and final handoff.

### 1.2 Deliberately separate work

- **TigerData is mandatory for the project.** The next increment will integrate/verify TigerData and durable C/B stores. This task must retain PostgreSQL/SQLAlchemy/Alembic compatibility and must not introduce a competing database or a second approval authority.
- Do not implement the C3 durable answer migration, a general job system, scheduled discovery, unrestricted funder portals, attachment upload, submission, signing, additional model providers or the C4 practice generator here.
- Do not claim process-local approvals survive restart or work across API workers. Do not enable production prefill or production fixture identity.
- General replacement of C's fixture evidence workspace with A's real evidence producer remains the next integration increment. A bounded **test workspace backed by real A4 evidence** is required here to prove this seam; it is not a claim of production workspace completion.
- No visual redesign. Coordinate functional props/API/state changes with Sawaab, who owns UI/UX.

## 2. Authority, references and takeover decision

Read current `AGENTS.md`, applicable directory instructions, this spec, and the referenced engineering sections before implementation. Newer owner instructions take precedence. Preserve existing architecture and tested controls.

References:

- `docs/engineering/StrongStart_Engineering_Plan.md`, v1.1: §§4, 5.3, 8.2–8.3, 9.2, 10.5, 10.7–10.8, 12.4, 13.2–13.3, 14–16, 18–21.
- `docs/engineering/StrongStart_Check_Catalog.json`: APP-04/06, AUT-01/02/03, PKG-01/02/03, JOB-02/03/05, SEC-01/08/09/10/13/14. AUT-04 remains an attachment checklist boundary.
- `docs/specs/B2-AUTO-002_Approved_Prefill_and_Read_Back.md`, revision 1.0.
- `docs/handoffs/dev-b/b2-auto-002-approved-content-request-r1.md`.
- `docs/handoffs/dev-b/b2-auto-002-approved-prefill-r1.md`.
- `docs/specs/C3-approval-and-export.md` and `docs/handoffs/dev-c/c2b-real-questions.md`.
- `docs/specs/A4-PKG-004_Pack_Replacement_and_Invalidation.md` and `docs/handoffs/dev-a/a4-pkg-004-pack-replacement-r1.md`.
- `docs/research/A3-deep-research-alignment-audit.md`: adopt exact identities, pure predicates, immutable history and action-specific gates; do not rebuild A3 from the advisory report.

The owner has taken over A/B/C engineering. Record that decision in a new dated decision file and update the current ownership/coordination pointers. A/B/C remain useful module/contract labels; keep existing machine-readable owners and identifiers unless a specific contract change requires otherwise. Sawaab owns UI/UX presentation. The project owner now sequences migrations and resolves cross-module engineering dependencies.

Former instructions to wait for another lane's human acknowledgment do not block this assigned integration. Publish the adopted producer/consumer agreement in the task decision/handoff. Preserve historical notes rather than silently rewriting them as if integration had already happened.

## 3. Verified starting state

These are observations at the pinned baseline, not assumptions about future main:

| Area | Actual state |
| --- | --- |
| PR #17 | Merged. P1 planner, executor, UI and test-provider harness complete; P2 still pending. |
| C2b | B's saved definitions and published question IDs reach C's workspace. |
| `applications/resolver.py` | Returns `ApprovalSnapshot` metadata; no rendered/template answer text. |
| `applications/store.py` | `InMemoryAnswerStore`, per-app fixture state, individual reads protected by a lock. |
| `applications/deps.py` | Production workspace/store unconfigured. Fixture mode composes saved B questions with fixture evidence. |
| `automation/prefill_deps.py` | Approved reader unconfigured; A4 currentness `None`; attachment evidence unconfigured. |
| `automation/prefill_runner.py` | Rechecks C content before/after operations and at completion; uses an optional currentness port. Single-use claim and idempotent receipt replay exist. |
| `knowledge/packs.py` | `PackService` persists manifests, active contexts, target dependencies and invalidation. Existing generic registration validates existence/authorization, not an atomic active-context binding. |
| A4 target kinds | `browser_grant` exists; an explicit browser-plan kind is not yet present. |
| Database | Alembic head `0007_pack_replacement`. C3's draft migration under `docs/` is not installed. |

The merged handoff reports `make check` passing with 751 Python and 97 web tests, `make smoke` passing, and 36 Chromium tests passing. These are baseline results, not a requirement to preserve an exact test count.

## 4. Repository workflow and change boundaries

1. Inspect Git status, active branch/worktree, remote and latest upstream. Preserve all existing work. Never reset, discard, force-push or recreate the repository.
2. Start a short-lived task branch from the agreed current main. The baseline above is a reference, not permission to ignore newer upstream work. Reconcile changed contracts before implementing against them.
3. Copy this spec into `docs/specs/` and record the takeover decision first. Checkpoint milestone work in coherent commits.
4. Implement A/C/B changes sequentially in the same engineering branch. No additional parallel coding sessions for this task.
5. Use supported public factories across feature boundaries. C may refactor its own store/resolver internals; B must not import C's private store or call its private lookup helpers. B/C must not inspect A4 tables directly or call local HTTP routes as an integration bridge.
6. Functional frontend changes must be narrow. Produce a UI handoff describing routes, props and states before changing components Sawaab is editing. Prefer an isolated adapter/hook/handoff component. Do not reformat or redesign whole pages.
7. Regenerate JSON Schema and TypeScript from Python after contract changes. Never resolve generated conflicts by choosing an entire side. Preserve every unrelated merged registration.
8. Follow the repository's PR policy. This implementation assignment permits task-branch commits and a draft PR when GitHub is available; no default-branch push, automatic merge or deployment. Put consumer updates in repo handoffs and the PR description; do not send unrelated messages or cross-PR comments unless requested.

## 5. C-owned approved-content reader

### 5.1 Public interface

Adopt the existing `ApprovedPrefillReader` and `ApprovedPrefillContent` from `strongstart_contracts.automation_prefill` unless a demonstrably necessary additive/versioned change is documented. Do not create another incompatible answer envelope.

Publish a C-owned public module/factory, for example:

```python
# Proposed public API; reconcile names with current repository conventions.
def get_approved_prefill_reader(...) -> ApprovedPrefillReader: ...

class ApprovedPrefillReader(Protocol):
    is_fixture: bool

    def resolve_for_prefill(
        self, organization_id: str, approval_snapshot_id: str
    ) -> ApprovedPrefillContent: ...
```

FastAPI dependency injection must supply **the same per-app C store** used by save/review routes, the same workspace/policy providers, and a stable store epoch. Do not instantiate a new empty store for each reader/request. Avoid circular imports through routers. Standalone service tests may construct the reader with explicit dependencies.

Keep the old `ApprovedAnswerResolver` compatible. Shared C-owned resolution logic should enforce the same usable-approval predicate; do not maintain divergent approval rules in the metadata resolver and content reader.

### 5.2 Envelope invariants

| Field | Required invariant |
| --- | --- |
| Organization | Server-derived scope. Unknown and other-org approvals have indistinguishable public behavior. |
| Approval | A recorded `approve` decision for the exact latest answer version, passing existing C3 freshness/gate semantics. Rejected, missing, unsigned, stale or inaccessible versions are unusable. |
| Answer identity | Version ID/number and approval snapshot agree with the same saved immutable version. Validate stored decision hashes against that version; do not assume database corruption is impossible. |
| Question identity | Exact saved `question_set_id`, published `question_id` and question version. Never rename a demo question into a B published question. A null/demo question set cannot be used as a B-published approval. |
| Template | Exact stored editor text. Its UTF-8 SHA-256 equals the stored content hash and approval content hash. |
| Rendered answer | Exact stored `RenderedAnswer.text` and its verified `text_sha256`. Return the saved rendering; never substitute a newly rendered answer under the old approval. |
| Renderer version | A real version attached to the saved rendering or verified renderer implementation path. Add a bounded saved-version field/default migration strategy if needed. Do not invent a label that suggests a different renderer produced it. |
| Dependencies | Exact saved dependency list and snapshot hash. A fresh check must still agree. No dropped rule/question/policy/fact dependencies. |
| Unsupported content | Unresolved fact tokens or unsupported markers cannot become fillable merely because a hash matches. Preserve existing approval gates and reject an inconsistent stored rendering. |
| Time | Server-generated, timezone-aware check time; freshness checks use an injectable server clock where needed. |
| Typed values | Default `None`. Do not infer a select/radio/checkbox value from answer prose or option similarity. |
| Provenance | Preserve supplied/public/simulated labels. Fixture approvals remain fixture approvals even when using the actual C producer. |
| Producer identity | Stable producer identifier; store epoch changes whenever process-local approval state is replaced/restarted. It must not change on every request. |

Return `ApprovalNotUsable` for unusable approvals and `CapabilityUnavailable` for an unconfigured required producer. Follow existing sanitized error mapping. Do not expose answer text or foreign identifiers in error details or logs.

### 5.3 Consistency and concurrency

Several individually locked reads are not one consistent approved snapshot. Introduce a C-owned consistent read operation, or an equivalent generation-checked snapshot:

1. Under the C store's lock, copy the exact version, decision, latest-version identity and an approval-relevant store revision/epoch.
2. Release the lock before workspace, B-reader or A4 calls.
3. Perform current dependency/question/policy checks against that captured version.
4. Recheck the approval-relevant revision and record identities before returning. If anything changed, refuse with a stable changed/stale reason; no unbounded retry loop.

Changes to answer versions, decisions and applied dependency changes must participate in the consistency mechanism. Test the chosen linearization boundary explicitly. Snapshot values must not expose mutable nested references that can change after the lock is released.

Do not hold a C store lock across browser work or A4 database calls. Do not claim distributed consistency: the current C store is process-local. The later TigerData implementation must satisfy the same public contract through transactional reads.

An edit after the final successful read can still happen before a browser operation. This increment uses repeated checks to detect observable changes; it does not provide a cross-system transaction over a remote DOM.

## 6. A4 public facade and dependency mapping

### 6.1 Public service boundary

Publish a knowledge-owned in-process facade over `PackService` for:

- resolving an authorized pack manifest/current active context;
- registering an exact consumer target against an expected active pack/context revision;
- reading/checking an existing target, its registered dependency set and current active context.

Use existing settings/engine providers and transaction handling. No extra database service, loopback HTTP, cross-module table imports or duplicate invalidation graph.

Retain generic A4 APIs for current consumers. Add a narrow guarded registration operation for browser consumers rather than silently changing the semantics of historical registrations.

### 6.2 Typed knowledge binding

Provide a strict, server-constructed binding for A4-managed content. Suggested shared type: `ApprovedKnowledgeBinding`, exposed as an additive `a4_binding` on approved content and bound into the resulting plan/actions:

- organization and application context;
- exact pack-version ID and active-context revision;
- canonical A4 dependency projection;
- projection/mapping version and canonical digest.

Equivalent names/layout are allowed with a recorded decision, but all these semantics must be represented and hashed. The binding is not client input or an approval. Preserve the full original C dependency snapshot alongside it. B must check that later reader results reproduce the bound identity/projection; a changed binding requires a new plan.

If C evidence is the existing unmanaged demo bundle, do not fabricate a managed binding. The local demo may run with explicit `A4 not integrated for this evidence` status. If a managed binding is present, A4 is mandatory: absence, timeout or inability to verify blocks the affected execution. Never silently downgrade a managed plan to the unmanaged demo path.

### 6.3 Mapping rules

C's `DependencyRef` and A4's `ValidationDependency` have different meanings. Define and test an explicit versioned projection:

| C identity | A4 identity / treatment |
| --- | --- |
| `pack`, pack ID, pack-version ID | `pack_version`, **pack-version ID**, **same pack-version ID**. Resolve and authorize the manifest/context; do not use the pack ID as A4's version identity. |
| `fact`, fact ID, legacy digest string | Resolve the exact saved binding and authoritative fact version. Never parse a digest as an integer version or substitute the latest fact. |
| `source_version` | Resolve the authoritative A4 version/hash convention; validate the original association. |
| `policy` | Use the exact approved policy version, checking its authorization/identity. Do not reinterpret arbitrary policy-version text as an integer. |
| `question`, `rule_set`, `requirement_set` | Retain C/B checks. Do not claim A4 invalidates kinds it does not manage. |

A conservative **pack-root projection** is acceptable for this increment: register the exact active pack-version dependency, covering any replacement of that pack. Record that it may invalidate more consumers than a fine-grained fact graph. Include independently managed policy/source dependencies where applicable. If an original dependency is not demonstrably covered by the pack root or its own verifier, hold the action; do not omit it and claim complete coverage.

Test policy-only, fact-only and same-value/new-version replacement. Content equality is not version equality.

### 6.4 Target identities and registration lifecycle

Register both:

- a plan target under an explicit browser-plan kind, preferably additive `browser_plan`;
- the actual execution grant under existing `browser_grant`, using its actual grant ID.

At the baseline, target kinds are string columns and the public union lacks `browser_plan`. Inspect actual current constraints before deciding whether a migration is required. Do not mislabel a plan as an approved answer or fake grant. Any necessary migration must be bounded to this integration, sequenced from the actual current head and tested; do not apply the C3 draft migration.

Registration binds organization, target kind/ID, expected target revision, expected active context/revision and exact projected dependencies. Immutable plan/grant data must bind the registration identity/projection. Repeated identical registration may reuse the existing target without resetting it; mismatch or a stale target requires a fresh plan. Reading/checking currentness never creates a target or resets stale state.

There is no distributed transaction between B's local files and A4 SQL. Define the ordering explicitly: failure may leave an orphan non-authorizing registration, but must not leave an executable managed plan/grant without its required verified registration. Failed preparation performs no browser writes. Any partial failure is visible and bounded.

## 7. Guard registration against pack replacement

At baseline, `PackService.register_target` checks that versions exist and are authorized. A historical pack can still exist after replacement. Calling `require_active` and then generic registration in unrelated transactions leaves a race.

The browser-specific registration must check the expected active context and write dependencies in **one transaction**, serialized against `PackService.activate`:

1. Acquire the same stable organization-row lock used by activation, then the context/target locks in documented order.
2. Recheck expected active pack ID/revision under that lock.
3. Resolve/authorize the exact projected dependency identities and verify target revision.
4. Register the target inside the same transaction, or return a conflict.

Never hold this SQL lock while calling C, acquiring B file-store locks or running Chromium. Existing generic registration behavior must remain compatible unless a separately documented security fix requires a change.

Required race outcomes:

- Replacement wins first: the attempted old-pack registration is refused and no executable managed plan is published.
- Registration wins first: activation waits; after release it finds and stales the newly registered target.
- A stale/missing target cannot become current through a GET/check, idempotent replay or re-registering the old plan.

Use real transaction/lock evidence in tests. Events/barriers or an observed database lock wait may coordinate the competing writer; elapsed sleeps, `Queue.empty()` and an unfinished Future are insufficient proof it reached the protected operation. Use bounded waits and a mutation test that demonstrably catches the removed protection.

## 8. B wiring and execution semantics

Wire B to C's supported factory and A4's facade. Retain the existing fail-closed defaults when a required producer is absent. Do not inject test approvals into the normal runtime.

### 8.1 Preparation

- Authenticate before resource access, then resolve the saved B definition and exact C approval.
- Independently validate template/rendered hashes, IDs, dependency snapshot, producer epoch and any managed binding.
- Preserve all existing limit/condition/mapping holds. In particular, approval does not resolve the 350/500-word conflict or the unknown unit in `Max 300`.
- Register the managed plan against its exact expected active pack before publishing it as executable. Include registration/projection data in the canonical plan hash.
- Do not advertise `a4_adapter` merely because an object implements a protocol. Report the actual successful producer/registration path. Unmanaged demo evidence remains explicitly `not_integrated`.

### 8.2 Execution

Preserve completed/idempotent receipt replay before new execution decisions. An old completed receipt remains historical after changes; replay never launches another browser or renews authority.

For a new managed execution:

1. Verify exact plan/hash, actor, epoch, expiry and definition/case currentness.
2. Claim once through the existing atomic single-use mechanism.
3. Bind/register the actual grant and check both managed targets before any browser mutation. Registration failure after a claim produces a zero-write blocked/unknown receipt as appropriate, never an automatic retry.
4. Read C approval/content and A4 currentness before **each** action, after each action and at completion.
5. Compare exact live values and perform the existing final reread.

If C/A4 is stale or unavailable before entry, make zero writes. If it changes after one field, stop further fields and preserve the partial receipt. Do not repair or undo values automatically. A failure to determine whether a browser write happened remains `outcome_unknown`.

Checks must cover the **whole target's registered dependency union**. The current callback receives one action's dependencies; do not mistakenly require that subset to equal the full plan union or validate only the first action. Use an explicit stored binding/union and prove multi-field behavior.

Keep the portal registry, request restrictions, real DOM read-back, no navigation/upload/submit/sign controls and resource cleanup from #17. No authorization or egress guarantee is expanded by this integration.

### 8.3 Read-time status

Return live plan usability separately from the immutable stored plan/hash. Add explicit stale/dependency-unavailable labels if the existing `PrefillPlanView.availability` union cannot express them. A GET may read currentness but must never launch Chromium, register targets, renew expiry or execute.

Historical run receipts retain their original outcome and data. Add separate current/historical labels where necessary; do not rewrite a past verified result to imply it never happened.

### 8.4 Contracts and compatibility

Use additive typed fields where safe. If new hash-bound fields make old pending plans/grants incomplete, increment the relevant format version and refuse execution of incomplete old records with a clear `prepare a new plan` action. Do not silently enrich/re-hash an old grant. Preserve a safe historical-read path where feasible. Do not loosen strict request parsing or accept authority fields from clients.

## 9. Minimal functional UX

Sawaab remains responsible for UI/UX presentation. This task supplies the functional connection:

- From a current approved answer, let staff select it for the matching saved question set in Automation. Use the existing server-issued approval and question identifiers.
- Prefer a small client-side handoff/context containing IDs only. Do not put answer text, selectors or authority flags in URL parameters/local storage as execution input.
- Show exact rendered text, template/rendered hashes or inspectable details, version, source/simulation labels and the existing explicit execution button.
- Show C producer connected, unmanaged-demo evidence, or managed A4 currentness accurately.
- Explain holds and errors in simple words with a next action: for example, “The source pack changed after this plan was prepared. Review the answer and prepare a new plan.”
- Preserve double-click protection, same-key lost-response retries, read-only refresh recovery and late-response isolation.
- Preserve existing accessibility and stable labels where possible. Update meaningful assertions when behavior changes; do not weaken tests or add `force` clicks to hide broken flow.

Manual copying of IDs may remain as an advanced diagnostic, but it is not the primary completion path. Commit a UI handoff with component/prop/state changes for Sawaab.

## 10. Required integration environments

Maintain separate, accurately labelled test paths:

| Path | Real components | Permitted controlled inputs |
| --- | --- | --- |
| Normal local-demo path | Runtime app factory, B publication, C save/decide/content reader, B planner/runner and Chromium | Existing synthetic evidence, local fixture identity and registered representative portal. |
| Managed A4 path | Migrated PostgreSQL, actual knowledge records/manifests, `PackService` activation/registration, actual C producer and B consumer | A test-only C workspace adapter may obtain actual A4 active evidence through its public boundary. Synthetic records remain labelled. No replacement of C's content reader/approval store with B test approvals. |
| Production boundary | Normal dependency wiring/capabilities | Verify unavailable configuration refuses; no fixture identity/portal execution. |

The managed path must prove real A4 mutation reaches the consumer. Injecting `TestCurrentness` is supplementary unit evidence and cannot satisfy it. The normal local-demo flow must not require the test-only `prefill_app.py` factory to obtain C approvals.

No paid/live model or search calls are necessary: the test can submit a deterministic template and approve through real C routes. Provider integration and deployment are separate work.

## 11. Deterministic acceptance matrix

Every row needs a committed executable test or explicit applicable existing test evidence. These are task acceptance IDs, not new catalog rules. Group cases where useful, but map every ID in the handoff.

| ID | Required result |
| --- | --- |
| INT-01 | Factory reads the same app-scoped store as C save/approve; independent app instances have distinct fixture-store state/epochs. |
| INT-02 | Missing identity is rejected before reader, store, A4 or browser side effects. Unknown/other-org resources behave identically. |
| INT-03 | A C-created approval under B's exact published question IDs resolves and prepares successfully. Unrelated demo IDs cannot substitute. |
| INT-04 | Template with a fact slot returns the exact saved rendered value. Template and rendered hashes differ where expected and both verify. |
| INT-05 | Corrupted stored text, rendered hash, decision hash or snapshot is refused. B independently rejects a tampered producer envelope. |
| INT-06 | Missing approval, rejection, old answer version, changed question/policy/fact or inaccessible dependency makes the approval unusable. |
| INT-07 | Unresolved fact tokens and unsupported markers never authorize a fill, including inconsistent stored-state fixtures. |
| INT-08 | Event-controlled concurrent save during reader resolution yields a consistent snapshot or an explicit refusal, never mixed old/new records. |
| INT-09 | Fixture-store replacement changes producer epoch; old plans cannot execute. Reconstructing a dependency provider alone does not change the epoch. |
| INT-10 | Existing metadata resolver and new content reader agree on usable approval cases. |
| INT-11 | Missing typed-choice authority holds select/radio/checkbox and dependent conditional fields; prose is never inferred into a choice. |
| INT-12 | Existing conflicting/unknown limits stay held. Unsupported counters and missing attachments retain their honest limitations. |
| INT-13 | C→A4 mapping uses exact version conventions; legacy fact digests are never treated as fact versions. Unsupported/omitted dependencies cannot produce a managed-current claim. |
| INT-14 | Managed plan and actual grant targets exist with the expected organization, active context, dependency union, projection digest and target revision. |
| INT-15 | Other-org pack/context/dependency/target references cannot register or return usable currentness. |
| INT-16 | Missing database/A4, failed registration or unavailable managed verifier prevents affected entry; no downgrade to demo/unmanaged mode. |
| INT-17 | Replacing A with B before old-plan registration is refused. No executable old-pack plan is published. |
| INT-18 | Replacement attempting the same lock during registration is observably blocked, then stales the registered target after release. |
| INT-19 | Removing/bypassing the registration protection makes the race test fail for the intended stale-registration reason. Restore exact source afterward. |
| INT-20 | GET/currentness/idempotent registration cannot reset a stale target or retarget the old plan. Same-hash replacement with a new version still invalidates. |
| INT-21 | Real A4 fact-only and policy-only replacements stop their dependent managed prefill. Test the documented conservative pack-root behavior. |
| INT-22 | A change in another organization's/context's unrelated pack does not stale this plan. Targets intentionally lacking a changed dependency remain current in the A4 service test. |
| INT-23 | Actual C save → approve → B prepare → Chromium entry verifies at least two eligible text fields and final reread. No `TestApprovals` override in this joined test. |
| INT-24 | One-character C edit after planning results in zero affected writes. Old approval is not relabelled or re-rendered. |
| INT-25 | Publish a newer B question definition after planning: old approval/plan cannot authorize entry. |
| INT-26 | Real A4 replacement after preparation and before entry yields zero writes. Include replacement after grant registration and before its first mutation. |
| INT-27 | Event-controlled change between two field actions stops the remaining action and records partial/stale entry accurately. |
| INT-28 | The full plan/grant dependency union works for different facts across multiple fields. Per-field checks cannot overlook a later field's dependency. |
| INT-29 | Expiry, producer restart and managed verifier failure are rechecked after actions and at completion; a late result is not marked fully verified. |
| INT-30 | Completed execution replay returns the same historical run after C/A4 changes and launches no new browser. Uncertain/incomplete claims never auto-execute again. |
| INT-31 | Existing thread/process single-use claim tests still observe real contention and one execution. Existing hostile-page/canary, truncation, overwrite and cleanup tests pass. |
| INT-32 | Normal runtime UI flow uses C-created approval IDs, plan preview, explicit action and receipt. Data/currentness labels and changed-source next action are visible. |
| INT-33 | Refresh and plan/run GETs perform no browser writes, registration or lease renewal. Late responses cannot overwrite newer selection state. |
| INT-34 | Old incomplete plan/grant records fail closed for execution with a fresh-plan action; historical receipt behavior is documented/tested. |
| INT-35 | Production configuration remains unavailable for fixture prefill and fixture approval; missing secrets/configuration do not invoke fallback data. |
| INT-36 | Errors/audit records have stable reasons and identifiers/hashes where appropriate, without leaking answer text, secrets or other-org content. |
| INT-37 | Python contracts, JSON Schema and TypeScript agree; all unrelated merged registrations remain. Strict client authority-field rejection is preserved. |
| INT-38 | Reproducible manual guide and final handoff distinguish C-connected demo, managed A4 integration, process-local storage and pending TigerData/real-evidence work. |

Use injected clocks for TTLs and explicit events/barriers for races. Avoid fixed sleeps as the deciding assertion. Bound all tests and release locks/processes in cleanup even on failure. Do not terminate unrelated browser processes.

## 12. Milestones and checkpoints

### M0 — Reconstruct and record ownership

Inspect current main, local work and PR #17 handoffs. Commit this spec, takeover decision and coordination updates. Record the precise baseline, real producers, fixture state and proposed contract additions. Provide a short UI integration handoff. Do not relabel old handoffs as fully completed.

### M1 — Publish C content reader

Implement consistent store reads, shared approval predicate, producer epoch and public factory. Prove hash/identity checks, concurrent read behavior and metadata-resolver parity. Wire normal runtime DI to the actual C store. Keep unsupported typed choices held.

### M2 — Publish guarded A4 facade

Implement typed mapping/binding, plan target kind and atomic active-context registration. Add real PostgreSQL tests for replacements, exact target revisions, tenant scope and race outcomes. Run and document the targeted mutation check. No browser work under the registration lock.

### M3 — Connect B and the functional UI

Bind currentness into plan/grant formats, wire the factories, preserve historical replay and add live GET status. Implement minimal approved-answer selection/handoff. Prove stale/unavailable paths and preserve #17's execution/network restrictions.

### M4 — Joined acceptance and handoff

Run both joined environments in §10, the real UI/API/Chromium path and required regression checks. Complete the acceptance matrix, capability/status notes, manual instructions and draft PR. Report remaining project gates explicitly.

Do not stop at an M1/M2 checkpoint as if the task were complete. If interrupted, leave a precise handoff and continue the next milestone when resumed. If a new upstream change creates a genuine incompatibility, document it and complete unaffected work; do not silently weaken the gate.

## 13. Verification commands and evidence

Discover actual repository commands first. At the final integrated checkpoint, run the applicable targeted tests plus:

```bash
make contracts
make check
make smoke
make browser-smoke
```

The managed-currentness integration needs actual migrated PostgreSQL, not SQLite or a mock. Extend the appropriate database smoke/CI suite so the new A4 seam is exercised remotely. The joined browser test needs the real API process and C save/decide/content producer.

Run targeted suites while developing; repeat full checks when contracts/runtime integration is complete. If source changes after the final checks, rerun the affected checks. Record exact commands, exit results, environment, commit and omissions; never present the baseline counts as a new run.

Do not read or copy secret values into handoffs. Use the existing local database/container without destructive resets. If database or Chromium prerequisites are missing, report that verification gap and finish other work; do not replace the test with a fake pass. No TigerData/live-provider verification is claimed in this task unless it actually runs against an explicitly configured environment.

## 14. Deliverables and completion report

Commit:

- This spec under its repo destination.
- A takeover/integration decision under `docs/decisions/`, with adopted public contracts, consistency/lock order, conservative dependency coverage and compatibility policy.
- Producer/consumer implementations and regenerated contracts.
- Required unit, API, database, concurrency/mutation and real-browser tests.
- `docs/handoffs/integration/int-001-approved-content-currentness-r1.md` (new directory permitted).
- `docs/handoffs/integration/int-001-manual-test-guide.md` with startup/settings names, preparation steps, UI path, expected receipts, C edit, question revision and real A4 replacement cases.
- `docs/handoffs/integration/int-001-ui-contract.md` for Sawaab, the UI/UX owner.
- Updated current coordination/feature-status pointers. Link old A/B/C handoffs to this adoption without erasing their historical limitations.

The final report and PR description must state:

1. Actual behavior and exact branch/head/PR.
2. Spec revision, engineering sections, relevant rule IDs and any deviations.
3. Acceptance evidence for INT-01…38, clearly separating mocked, joined C, real A4 DB and real Chromium paths.
4. Test commands/results and mutation evidence, including restored source status.
5. Production-disabled paths, process-local C state, unmanaged evidence limitations, unsupported choices/counters/attachments and any unrun tests.
6. Whether Sawaab's UI/UX branch has actually been integrated; no implied redesign completion.
7. The next concrete increment: **TigerData durability plus real A-evidence/workspace integration**, carrying forward the public reader/currentness contracts.

Only update catalog implementation/test status when the exact catalog predicate has supporting evidence; do not mark all 86 checks complete because these task tests pass. Do not describe this as full G2/G4 completion or deployment readiness.

## 15. Definition of done

INT-001 is complete when the actual C producer authorizes the exact selected B-published answer versions, the registered representative portal receives those exact rendered values with real read-back, real A4 replacement blocks managed pending work through the supported facade, all applicable acceptance cases and required checks pass, and the result is reviewable through a PR with accurate handoffs.

The next task can replace fixture/process-local producers with TigerData-backed durable implementations without changing B's trust model or making models responsible for correctness.

## 16. Agent start instruction

> Implement INT-001 revision 1.1 in the existing repository. Begin with M0 and preserve all current work. You own former A/B/C engineering for this task; use one coding agent and resolve their producer/consumer dependencies directly. Keep Sawaab's UI/UX presentation work isolated. Follow the engineering plan/check catalog, finish M0–M4, preserve fail-closed behavior and labelled demo data, publish a draft PR under repository policy, and do not merge or deploy. TigerData is the mandatory next persistence target; this task establishes the public contracts and integrated behavior it must preserve.

## Source links

- [Merged PR #17](https://github.com/thegeekyqazi/Start_Strong_Agent/pull/17)
- [Verified main baseline](https://github.com/thegeekyqazi/Start_Strong_Agent/commit/b543454255c45e9a079e3090337585b375fe34f0)
- [Successful post-merge CI](https://github.com/thegeekyqazi/Start_Strong_Agent/actions/runs/42474740195)
- [B2 partial-increment handoff at baseline](https://github.com/thegeekyqazi/Start_Strong_Agent/blob/b543454255c45e9a079e3090337585b375fe34f0/docs/handoffs/dev-b/b2-auto-002-approved-prefill-r1.md)
- [C approved-content request at baseline](https://github.com/thegeekyqazi/Start_Strong_Agent/blob/b543454255c45e9a079e3090337585b375fe34f0/docs/handoffs/dev-b/b2-auto-002-approved-content-request-r1.md)
- [A4 implementation handoff at baseline](https://github.com/thegeekyqazi/Start_Strong_Agent/blob/b543454255c45e9a079e3090337585b375fe34f0/docs/handoffs/dev-a/a4-pkg-004-pack-replacement-r1.md)
