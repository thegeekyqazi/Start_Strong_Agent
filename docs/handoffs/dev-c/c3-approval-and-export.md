# C3: Exact-version approval, invalidation, reviewer roles and DOCX/audit export (r1)

- Author/lane: Dev C agent
- Intended consumers: project owner; Dev B (resolver consumer, lockfile owner); Dev A (migration sequencing)
- UTC timestamp: 2026-11-08
- Status: ready-for-review in PR #10 (open; not merged). Commits authored as Aryan Dayani (GitHub noreply)
- Task spec: `docs/specs/C3-approval-and-export.md` rev 1.0 plus s12 notes
- Engineering: v1.1 s8.1, s9.2, s15, s16, s18. Rules: APP-04, APP-06, APP-07, APP-08, POL-05, JOB-02, JOB-05, SEC-10, plus SEC-14 boundaries (catalog stays `planned`)
- Branch base: rebased onto `origin/main` `2adcdeb`, then **merged** with `origin/main` `b1f9ddf` (A3 PRs #11, #13, #14) and again with `51f19f4` (Dev B PR #12). See "Merge resolution r2"

## What works (fixture mode)

1. **Save version.** Applications → "Save version" freezes the exact text as version N, with:
   - a content hash;
   - a JOB-05 snapshot hash covering question, pack, a fact digest, policy, rules, counters, organization and the time policy;
   - a reviewed-mode check.
   
   Saves are optimistic: a stale `expected_answer_version` gets 409.
2. **Review page.** It shows:
   - versions with all s15 states (text plus shape);
   - a word diff between versions;
   - the stale banner and prefill readiness;
   - reviewed-mode findings with text labels;
   - numbers/meaning reviewer suggestions ("cannot approve anything");
   - notes;
   - approve/reject bound to the exact fingerprint.
3. **The approve gate (s9.2) requires:**
   - the latest version, with matching expected content and snapshot hashes;
   - no stale reason;
   - no `fail` findings;
   - acknowledgment of every `needs_review` item;
   - the fixture identity in fixture mode (otherwise 403).
   
   Only one decision is allowed per version: concurrent approvals give one 200 and the rest 409.
4. **Staleness (live).** Any edit (a newer version), any fact, policy or question change, or an applied fixture ChangeSet makes the approval `stale`. Prefill readiness is revoked and an old approval can never be replayed.
5. **Resolver for B.** `StoreApprovedAnswerResolver` implements the `ApprovedAnswerResolver` port. It is org-scoped and refuses unknown, rejected and stale approvals with `ApprovalNotUsable`. It returns an `ApprovalSnapshot` labelled simulated.
6. **Export:**
   - **Working DOCX:** always allowed, labelled "WORKING DRAFT - NOT REVIEWED" with `[NEEDS REVIEW]`/`[PROBLEM]` text labels.
   - **Reviewed DOCX:** blocked unless every question's latest version is approved and current, with no `fail`, no unsupported claim and no unacknowledged warning.
   - "SYNTHETIC DEMO DATA" appears in the header of every page. "FIXTURE APPROVAL - NOT AUTHENTICATION" is added only when a fixture approval is included.
   - **JSON audit:** hashes, dependencies, fact IDs, sources, approvals and check records with `counts_as_current` (APP-08).
7. **SEC-10 audit.** Every save, decision, stale event, note, proposal, export and ChangeSet is audited with actor/action/object/version/decision/time. Configured keys and known key shapes are redacted. The route requires identity and is org-scoped.

## Interfaces

| Route (`/api/applications`) | Result |
| --- | --- |
| `POST /answers/versions` | 201 `AnswerVersion` |
| `GET /answers/{question_id}` | `AnswerHistory` |
| `POST /answers/decisions` | `ApprovalRecord`; 403, 409 or 422 (gate) |
| `POST /answers/notes` | 201 `ReviewNote` |
| `POST /answers/reviews` | 201 `ReviewerProposal` |
| `POST /exports` | `ExportResult` |
| `GET /exports/{id}/docx`, `GET /exports/{id}/audit` | File downloads |
| `GET /audit-events` | Audit events |
| `POST /fixture/change-sets/{id}/apply` | Fixture mode only |

Contracts are C-owned, added to `answers.py` and regenerated.

## Validation (2026-11-08)

| Command | Result |
| --- | --- |
| `make check` | exit 0: ruff, mypy (130 files), oxlint, Prettier; **454 pytest**; **66 Vitest**; contracts drift clean; build ok |
| `uv run pytest tests/applications` | 154 passed (46 new C3 cases across the s8 rule table) |
| `make smoke` | exit 0: readiness 200 (see PR for the post-rebase run at `0004_pdf_extraction_coverage`) |
| `make browser-smoke` | exit 0, 13 passed |
| Chromium against the real API | Draft → save v1 → approve (with ack) → prefill ready → numbers reviewer → reviewed export blocked (3 unanswered questions) → working DOCX downloaded (labels in the header) → edit → v2 → "Out of date" banner and "Not ready for prefill". 0 page errors, 0 external requests |

Defects found during C3 validation and fixed:
1. The migration FK pointed at a non-existent column.
2. The working export showed `[PROBLEM]` for allowed placeholders.
3. The "fixture approval" label appeared with no approvals.
4. ChangeSet staling was not audited.
5. The prefill line disappeared after an edit.

## Merge resolution r2 (2026-11-08): `origin/main` `b1f9ddf` merged into C3

The owner asked to resolve PR #10 "after PRs #12 and #15 have landed". **They had not landed:** #12 (Dev B bundle-002) and #15 (Dev A A4 pack replacement) are still open. This merge resolves PR #10 against the **current** `main`, which gained Dev A's A3 validation work (#11 spec, #13 A3a/A3b source validation, #14 A3c numeric validation). Another merge is needed when #12/#15 land.

- **Method:** `git merge origin/main` (no rebase, no force-push).
- **Conflicts:** only the generated `packages/contracts/schema/strongstart-contracts.schema.json` and `packages/contracts/ts/src/generated.ts`. These were **regenerated with `make contracts`** from the combined Python models, not resolved by picking a side. All Python sources merged cleanly.
- **What the regenerated outputs contain:**
  - C3's models (`AnswerVersion`, `ApprovalRecord`, `AuditEvent`, `ExportResult`, `ReviewerProposal`, ...);
  - A3's `SourceValidationRequest`/`SourceValidationReport`/`RuleCapability`;
  - every A, B1, B2 and shared model;
  - Dev A's additive `ClaimBinding.fact_version` (default 1). That is A's response to C's fact-version request (`c2-fact-version-request.md`). C3 builds bindings without it and gets the default, so it is compatible.
- **Dependencies:** `services/api/pyproject.toml` keeps A's `pypdf>=6.1,<7` and C3's `python-docx>=1.1`. The merged `uv.lock` passes `uv lock --check` and `uv sync --locked` with no drift, so it was not regenerated. Upstream root `pyproject.toml`/`uv.lock` changes merged cleanly.
- **Migration coordination:** C's request was drafted as `0005_answers_and_approvals`, but `main` now has A's `0005_validation_receipts` and `0006_numeric_validation`, and A4's PR #15 adds `0007_pack_replacement`.
  - The request is now **unnumbered**: `c3-migration-request/answers_and_approvals.py`, with revision `assign_by_dev_a_answers_and_approvals`.
  - Its `down_revision` is the deliberately invalid placeholder `SET_BY_DEV_A_TO_CURRENT_HEAD`, so applying it unchanged fails loudly instead of creating a second head.
  - C added **no** migration head and applied nothing.
  - Code, spec s12, the decision record and this handoff no longer cite a number.

### Validation after the merge

| Command | Result |
| --- | --- |
| `uv sync --locked` / `uv lock --check` | exit 0 / no drift |
| `make contracts-check` | schema and TS match the combined models |
| `make check` | exit 0: ruff, ruff-format, mypy strict (150 files), oxlint, Prettier; **510 pytest passed** (24 deselected); **67 Vitest passed**; build ok |
| `uv run pytest tests/applications` | 154 passed |
| `tests/unit/test_validation_runner_adapter.py` (A3's C2 runner parity fixture) | 1 passed |
| `make smoke` | exit 0: 82 + 11 db tests; readiness 200 at `0006_numeric_validation`; capabilities 200 (17 entries) |
| `make browser-smoke` | exit 0, 13 passed |

### Second merge: `origin/main` `51f19f4` (Dev B PR #12, merged 09:27 UTC during the first merge)

PR #12 (DEV-B-BUNDLE-002) landed while the first merge was being validated, which made PR #10 conflict again. It was handled the same way.

- **Conflicts:** only the two generated contract files again, regenerated with `make contracts`. The combined schema carries every lane: C 33 models, B1 70, B2 50, A-series, shared.
- **No new migrations** (head stays `0006_numeric_validation`) and no dependency changes. `uv lock --check` shows no drift.
- PR #15 (A4) was still open at this point. It landed shortly after; see "Third merge".
- **C2b is unblocked.** PR #12 delivered `ApplicationDefinitionReader` in answer to C's `c2-question-read-port-request.md` (see `docs/handoffs/dev-b/bundle-002-question-reader-r1.md`). Consuming it is follow-up C2b work, not part of this PR.

| Command (tree after second merge) | Result |
| --- | --- |
| `uv sync --locked` / `uv lock --check` | exit 0 / no drift |
| `make check` | exit 0: mypy strict (176 files) clean; **675 pytest passed** (27 deselected); **83 Vitest passed**; contracts drift clean; build ok |
| `uv run pytest tests/applications` | 154 passed |
| `make smoke` | exit 0: 97 + 11 db tests; readiness 200 at `0006_numeric_validation`; capabilities 200 (22 entries) |
| `make browser-smoke` | exit 0, **16 passed** (PR #12 added B's e2e) |

### Third merge: `origin/main` `5f1c5a0` (Dev A PR #15, A4 pack replacement)

PR #15 merged after the second merge was pushed. With it, **both PRs named in the owner's request (#12 and #15) have landed**, and this branch now contains them.

- **No conflicts.** Git auto-merged everything, including the generated contract files. `make contracts-check` confirms the committed schema and TypeScript match the combined models (A4's `packs.py` contracts included), so nothing needed regenerating.
- **Dependencies:** `uv sync --locked` and `uv lock --check` are clean.
- **Migration head** is now A's `0007_pack_replacement` (`REQUIRED_MIGRATION_REVISION`). C's request stays unnumbered and inactive. C added no head.

| Command (tree after third merge) | Result |
| --- | --- |
| `make check` | exit 0: mypy strict (181 files) clean; **682 pytest passed** (28 deselected); **84 Vitest passed**; contracts drift clean; build ok |
| `uv run pytest tests/applications` | 154 passed |
| `make smoke` | exit 0: 99 + 12 db tests; readiness 200 at `0007_pack_replacement`; capabilities 200 (22 entries) |
| `make browser-smoke` | exit 0, **16 passed** |

## Consumer action / blockers

- **Dev A (please acknowledge in PR #10):** sequence the **unnumbered** request `docs/handoffs/dev-c/c3-migration-request/answers_and_approvals.py` (it targets `organizations.id`). Assign its revision and down-revision after your current head (`0007_pack_replacement`, current head on main). Its placeholder down-revision fails loudly if applied unchanged. C will not add a migration head. Persistence stays fixture-only until then.
- **Dev B:**
  - acknowledge the `uv.lock` change (`python-docx`, `lxml`);
  - consume `get_c_approved_answer_resolver` / `StoreApprovedAnswerResolver` for B2-AUTO-002;
  - agree whether C should wire it into the shared `ports.get_approved_answer_resolver`.
- **Dev B:** thanks for `ApplicationDefinitionReader`; C will consume it in a C2b follow-up (not in this PR).
- **Owner:** review PR #10. It is open and not merged, and it is now resolved against `main` including both #12 and #15.
