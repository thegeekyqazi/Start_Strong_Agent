> INT-001 adoption (2026-11-08): engineering ownership and current producer/consumer
> integration are recorded in the [integration handoff](../integration/int-001-approved-content-currentness-r1.md).
> This historical note retains its original status, evidence and limitations below.

# C2b: C reads Dev B's saved question sets (r1)

- Author/lane: Dev C
- Intended consumers: project owner; **Dev B** (producer acknowledgment below); Dev A (FYI: G1's evidence half)
- UTC timestamp: 2026-11-08
- Status: ready-for-review (local branch `dev-c/c2b-real-questions`, base `origin/main` `c490dba`; not pushed yet)
- Task spec: `docs/specs/C2-draft-claims.md` rev 1.3, **s13 (phase C2b)**
- Engineering: v1.1 s7, s14, s15, s20.3 (consumer tests against fixture and real producer), s20.7 (G1)
- Producer: Dev B `ApplicationDefinitionReader`, envelope `b2-published-definition/1` (PR #12; handoff `docs/handoffs/dev-b/bundle-002-question-reader-r1.md`), answering `c2-question-read-port-request.md`

## What works

- **Choosing the questions.** The Applications and Review pages have a "Questions from" picker:
  - "Demo fixture questions (synthetic)", which is an **explicit** choice;
  - each **verified** Dev B saved definition (`status: ok`), listed through B's public `GET /api/automation/definitions`. Integrity-failed entries are not offered.
  
  The selection is remembered per tab.
- **Only the ID crosses the wire.** The browser sends just `question_set_id`. C's server resolves it with `reader.get_version(identity.organization_id, question_set_id)`, so it gets the exact immutable version and never a substituted latest. No question or provenance payload from the browser is accepted.
- **No silent fallback.** A missing, other-org or failed-integrity set is shown as an error ("We did not switch to other questions"). The demo questions load only if staff click "Use the demo fixture questions instead".

  | Failure | HTTP | Reason |
  | --- | --- | --- |
  | Not found or other organization | 404 | `unknown_question_set` |
  | Integrity failure | 502 | `question_set_integrity_failure` |
  | No repository (e.g. production) | 503 | `capability_unavailable` |
- **Nothing resolved on B's behalf.**
  - Published IDs (`def-…:rp-*`), question versions, `limit=None` with 350/500 candidates, unit `unknown` and `required: null` are used as-is.
  - B's `unresolved` items are shown as "Saved definition: …" notices on each question.
  - B's `saved_not_reviewed` status and fixture label are shown.
- **The whole C path reads the producer.** Workspace, plan, draft, check (APP-01 uses B's limits; APP-03 is unchanged), save version, history, approve, reviewer roles and export all carry `question_set_id`. Saved answer versions record it.
- **Revision staleness.** If B saves a newer version of the definition, an approval made on the older question set becomes **stale** (`question_definition_revised`) and prefill readiness is revoked. The resolver also finds approvals on any question set.
- **Evidence is unchanged.** It is still the labelled fixture `EvidenceBundle`. Real A evidence is the remaining half of G1.

## Contracts (C-owned `answers.py`, additive; regenerated)

- Optional `question_set_id` on `DraftRequest`, `CheckRequest`, `PlanRequest`, `AnswerVersionCreate` and `ExportRequest` (strict).
- `ApplicationWorkspace`:
  - `question_source` (`fixture_bundle` | `dev_b_saved_definition`);
  - `question_set_ref` (new `QuestionSetRef`: question set ID, definition ID and version, fixture flag, mode label, review status, saved-at);
  - `unresolved` (B's `UnresolvedItem`).
- `AnswerVersion.question_set_id`.
- Routes: `GET /api/applications/workspace?question_set_id=…` and `GET /api/applications/answers/{id}?question_set_id=…`. The other routes take it in the body.
- C imports **only** B's public entry points: `strongstart_contracts.application_publication` and `strongstart_api.features.automation.public.get_application_definition_reader`. No B file is modified.

## Validation (2026-11-08)

| Command | Result |
| --- | --- |
| `uv run pytest tests/applications/test_c2b_real_questions.py` | **16 passed**. The real B repository (saved through B's public API into a temporary store) and a labelled double from B's committed sample; no-fallback 404/502/503; other-org; strict typing; plan/draft/check; save → approve → resolve → export; definition revision → stale |
| `make check` | exit 0: ruff, mypy strict (182 files), oxlint, Prettier; **698 pytest passed**; **87 Vitest passed** (3 new C2b UI tests); contracts drift clean; build ok |
| `uv run pytest tests/applications` | 170 passed |
| `make smoke` | exit 0: readiness 200 at `0007_pack_replacement` |
| `make browser-smoke` | exit 0, 16 passed |
| Chromium against the real API | Definition saved via B's `POST /api/automation/definitions`; picked in Applications; 9 B questions, unresolved notice and 350/500 conflict shown; draft, counter (B's 50-word limit) and Save version; Review on the same set. 0 page errors, 0 external requests |

## Acknowledgment to Dev B

C acknowledges `ApplicationDefinitionReader` / `b2-published-definition/1` as consumed in C2b:
- `get_version` for exact versions;
- `get_current` for revision staleness only;
- `UnresolvedItem` kept visible.

B+C G1 ("real B questions render with limits/conflicts in C's editor/check/draft") is now met on C's side. Full G1 still needs real A evidence.

## Limitations / next actions

- Evidence is still the fixture. Next: consume A's evidence route (A1–A4 are merged) to complete G1.
- Answer persistence is still C3's fixture store until Dev A sequences the C3 migration request.
- The definitions list shows up to 50 entries (B's bounded list). There is no pagination UI yet.
