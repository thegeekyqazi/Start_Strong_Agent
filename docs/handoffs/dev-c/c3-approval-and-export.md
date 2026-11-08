# C3: Exact-version approval, invalidation, reviewer roles and DOCX/audit export (r1)

- Author/lane: Dev C agent
- Intended consumers: project owner; Dev B (resolver consumer, lockfile owner); Dev A (migration sequencing)
- UTC timestamp: 2026-11-08
- Status: implemented as **uncommitted working-tree changes** on `dev-c/c3-approval-export` (owner rule: no add, commit or push)
- Task spec: `docs/specs/C3-approval-and-export.md` rev 1.0 plus s12 notes
- Engineering: v1.1 s8.1, s9.2, s15, s16, s18. Rules: APP-04, APP-06, APP-07, APP-08, POL-05, JOB-02, JOB-05, SEC-10, plus SEC-14 boundaries (catalog stays `planned`)
- Branch base: `origin/main` `c69d610` (after the owner-authorized attribution rewrite)

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
| `make smoke` | exit 0: readiness 200 at `0003_artifact_text_ingestion` |
| `make browser-smoke` | exit 0, 13 passed |
| Chromium against the real API | Draft → save v1 → approve (with ack) → prefill ready → numbers reviewer → reviewed export blocked (3 unanswered questions) → working DOCX downloaded (labels in the header) → edit → v2 → "Out of date" banner and "Not ready for prefill". 0 page errors, 0 external requests |

Defects found during C3 validation and fixed:
1. The migration FK pointed at a non-existent column.
2. The working export showed `[PROBLEM]` for allowed placeholders.
3. The "fixture approval" label appeared with no approvals.
4. ChangeSet staling was not audited.
5. The prefill line disappeared after an edit.

## Consumer action / blockers

- **Dev A:** sequence `docs/handoffs/dev-c/c3-migration-request/0004_answers_and_approvals.py` (it targets `organizations.id`, down-revision `0003_artifact_text_ingestion`). Persistence stays fixture-only until then.
- **Dev B:**
  - acknowledge the `uv.lock` change (`python-docx`, `lxml`);
  - consume `get_c_approved_answer_resolver` / `StoreApprovedAnswerResolver` for B2-AUTO-002;
  - agree whether C should wire it into the shared `ports.get_approved_answer_resolver`.
- **Owner:** review the working tree and decide on commit/PR (nothing is committed).
