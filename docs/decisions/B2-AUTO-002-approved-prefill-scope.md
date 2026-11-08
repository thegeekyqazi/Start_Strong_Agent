# B2-AUTO-002: Approved prefill scope, exact-content semantics and unavailable producers

- Author/developer: Dev B agent (Claude Code, claude-opus-5-5) for the project owner (Dev B)
- Date: 2026-11-08
- Status: developer-decision (within B2-AUTO-002 rev 1.0 discretion). The proposed C reader in s3 is `proposed-cross-module` until Dev C acknowledges it.
- Decided/accepted by and evidence: the Dev B agent. Not yet reviewed by the owner or Dev C.
- Engineering path/version/sections: `docs/engineering/StrongStart_Engineering_Plan.md` v1.1, s4, s7, s9.2, s10.5, s10.7, s12.4, s13.2-13.3, s14-16, s18-21
- Feature spec path/revision: `docs/specs/B2-AUTO-002_Approved_Prefill_and_Read_Back.md` rev 1.0
- PR / Issue: draft PR from `dev-b/b2-auto-002-approved-prefill` (see the task handoff)
- Supersedes / superseded by: none

## Original requirement

Spec s1 and s3: staff prefill selected fields of a **registered local fixture portal** with server-resolved approved content, read the live values back, and never submit. P1 uses an explicitly injected test approval provider; P2 joins C3's real producer. Spec s5.1 notes that C3's `ApprovedAnswerResolver.resolve()` returns an `ApprovalSnapshot` without answer text, so B cannot fill a field from it.

## Baseline at task start

- `origin/main` = `c490dbae07bea5543468ba9495c58be08132e6b7`. It includes C3 (PR #10, merged), A4 (PR #15, merged), A3 (PRs #11, #13, #14) and DEV-B-BUNDLE-002 (PR #12).
- Open: PR #16 (C3 handoff notes, docs only).
- C3 on main exposes `StoreApprovedAnswerResolver` through `features/applications/review_router.get_c_approved_answer_resolver`. It is not wired into `strongstart_api.ports.get_approved_answer_resolver`, which still defaults to unconfigured. C's workspace is the fixture `demo-bundle@1` source (C2b pending), so C approvals name `mission-q1`-style IDs, not B's `def-…:rp-*` IDs.
- A4 on main exposes dependency registration and currentness **only as HTTP routes** under `/api/knowledge`. It has no in-process consumer factory.

## Decisions

### 1. Phase status is reported honestly

P0 and P1 are implemented here. P2 (C3 joined) is **blocked** on a C-owned content reader (s3) and on matching question identities (C2b or a C-owned test workspace adapter). The PR stays a clearly partial draft until then. Capabilities say `fixture_only` / `unavailable` accordingly.

### 2. Exact content and hashes

- B fills only content returned by a server-side reader for an approval ID. A request carries plan ID, plan hash and idempotency key, never text, selectors, URLs, organization or `approved`.
- Two hashes are checked independently: `template_sha256 == sha256(template_text) == ApprovalSnapshot.content_sha256`, and `rendered_sha256 == sha256(rendered_text)`. The rendered text is what gets entered. Rendered text containing `{{fact:` or `{{unsupported:` is refused.
- Comparison is exact Unicode string equality (`b2-readback-exact/1`). The only declared exception is `b2-readback-textarea-crlf/1`: a textarea's live value may report CRLF as LF, so the comparison maps `\r\n` → `\n` on **both** sides and records raw and compared hashes. No trim, case fold, Unicode normalization, currency stripping or truncation acceptance.
- Number controls take the approved string unchanged, and only when it matches `^[0-9]+$` and lies within the registry's confirmed min/max. Otherwise the field is held (`held_value_format`).
- Choice controls need a C-authorized typed value (`typed_value.kind="choice"`) equal to a registered option. Prose is never mapped to a choice.

### 3. Proposed C reader (proposed-cross-module)

B declares the **consumer port** it needs in the B-owned contract module `strongstart_contracts.automation_prefill`:

- `ApprovedPrefillReader.resolve_for_prefill(organization_id, approval_snapshot_id) -> ApprovedPrefillContent`;
- the default `UnconfiguredApprovedPrefillReader` fails closed.

C owns the implementation and may rename the port on adoption; B will adapt. The existing `ApprovedAnswerResolver.resolve()` is unchanged. The request is in `docs/handoffs/dev-b/b2-auto-002-approved-content-request-r1.md`.

### 4. Where the test provider lives

The P1 approval provider is a test double in `tests/automation/prefill_support.py`, injected with `app.dependency_overrides`. No runtime module contains seeded approvals. Unconfigured means 503 `capability_unavailable`.

### 5. Requirements gate

Approval does not resolve B's holds.

- Intake's `held_unresolved_requirement` stays held.
- **Word** limits are held (`held_counter_unavailable`): C's APP-01 counter has no public consumer contract, and B does not invent one.
- **Character** limits are enforced only with a declared UTF-16 code-unit convention (`html-maxlength-utf16-code-units`) or the registry's native maxlength.
- A conditional child is allowed only when its structured predicate names a parent selected earlier in the same plan, with an approved typed choice equal to the expected value. Otherwise it is held.

A dedicated positive fixture (`rep-prefill-v1`) is added. The existing `rep-portal-v1` 350/500, Max 300 and malformed fixtures are unchanged and remain negative cases.

### 6. Plans, grants, runs and claims

- Plans, grants and runs are stored in the Dev B local store (collections `prefill-plans` and `prefill-runs`). Production is disabled.
- A run's object ID is derived from the plan ID. The claim is a `commit(expected_version=0)`, so of two racing requests, threads or processes, exactly one creates v1 (the no-clobber link under the collection lock).
- Progress is committed as later versions before each DOM mutation and after each read-back. No lock is held while C is called or Chromium runs.
- A same-key retry replays the stored run. A different key on a claimed plan is 409 `plan_already_executed`.
- An incomplete run with no live executor past its deadline is reported `outcome_unknown` at read time and is never re-executed.

### 7. Runtime epoch and clock

- Each API process has a random runtime epoch, and plans and grants bind to it. After a restart (C3's store is process-local), execution fails with 409 `runtime_epoch_changed` before the browser starts.
- The clock is an injected dependency.
- Budgets:
  - plan/grant lifetime 120 s;
  - at most 20 actions;
  - one Chromium execution per grant;
  - a 30 s overall execution cap;
  - 5 s per operation;
  - no automatic write retries.

### 8. Browser boundary reuse

The inspector's restricted session (fixture server, routing, WebSocket/popup/download blocks, `finally` cleanup) is factored into a shared context manager. Read-only inspection behaviour, `FormInspectionResult.prefill_permitted=false` and the `b2-form-fp/1` fingerprint are unchanged.

The executor's operations are `fill`, `select_option` and `check` only, on server-resolved selectors. It has no click, Enter, submit, upload or arbitrary script.

### 9. A4 currentness

A4 is merged, but it offers no in-process consumer interface, and B does not call its HTTP routes through loopback. B therefore publishes a request instead. An optional `PrefillDependencyCurrentness` port is checked before each action when it is configured. It is injected only in tests, and the handoff labels that as fixture currentness, not A4 integration.

## Impact and coordination

- New B contract module: `automation_prefill.py` (additive), registered for JSON Schema/TypeScript generation.
- No change to `automation.py`, `automation_intake.py` or `application_publication.py`, and no change to C or A source.
- Consumers: C (asked to implement the reader), A (asked for an in-process currentness factory).

## Validation and rollback

The AUTO2-* evidence is in the task handoff. To roll back, revert the task commits and delete `.local-data/dev-b-store/**/prefill-*`. There are no migrations.
