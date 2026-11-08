# C2: Plan and draft answers with claim bindings and visible findings

- Task ID: C2 (lane Dev C)
- Revision: 1.0 (proposal, awaiting the project owner's "go")
- Branch: `dev-c/c2-draft-claims`, **stacked** on `dev-c/c1-shell-and-adapter` (`94dffc2`; C1 is not yet merged). Integration order: C1 PR first, then rebase C2 onto `main`
- Engineering baseline: v1.1, s4.2, s7, s8.1-8.3, s9.1-9.2, s10.5 (APP), s10.6 (POL), s13.2 (SEC-12), s14.1, s15, s18, s20.3-20.4 (C2 row)
- Lane plan: `docs/coordination/dev-c-lane-plan.md` rev 1.0, s3 "C2"
- Checks (catalog stays `planned` until tests prove each predicate): APP-01, APP-02, APP-03, POL-01, POL-02, POL-03, SEC-12. APP-05 is enforced at C's retrieval boundary. POL-04 (P1) is deferred (s10)

## 1. Goal (s20.4 C2 row)

The s20.4 row reads: "Plan/draft answer with claim bindings and visible findings. Fixture implementation starts after C1; real completion needs A2 retrieval, A3 runner and B2 questions."

The staff-facing result:
1. A **plan** for all selected questions shows the evidence assigned to each question and the missing inputs. It never invents a request, a spend or consequences (s7).
2. A draft's figures are **bound claims**. The server renders each fact's value, unit and period into the answer and records the exact text span (s8.2).
3. After every edit, deterministic checks run and appear as **findings** in the editor (s8.3, s18):
   - an exact versioned count;
   - required-question status;
   - unbound numbers;
   - placeholder tokens;
   - scoped terminology and protected wording.

C2 is **fixture-complete** only. "Done" (s20.9) needs the real producers (G1, s7 below).

## 2. QA carried in from C1 (2026-11-07)

- C1 tests were re-run: pytest 68 (applications + api) passed and Vitest 48 passed. The pushed refs equal the local commits.
- **Gap, now P0 here:** model text with raw numbers ("We served 500 children in 2025.") passes C1 validation. APP-03's unbound-number scan closes this gap in C2.
- **Minor:** `question_version: "1"` is coerced, because contracts use lax parsing. C2 request models use `strict=True`.
- HTML in model text is stored as text and rendered inert, which is correct and kept.

## 3. Contracts (producer C, `answers.py`, additive)

Each model is listed with its source in the plan:

- `AnswerPlan`:
  - `plan_id`, `question_set_id`, `evidence_bundle_id`;
  - `items[]`, each with `question_id`, `question_version`, `evidence_fact_ids`, `missing_inputs[]` and `repeated_with[]` (questions asking for the same content);
  - `planner: ModelRunInfo`.
  
  The planner may only assign fact IDs that are in `allowed_fact_ids` (s7).
- `ClaimBinding`:
  - `fact_id`;
  - `span_start`/`span_end` (code-point offsets in the rendered text);
  - `rendered_text` (value, unit and period as the server rendered them);
  - `fact_version_ref` (`pack_version_id` plus `fact_id`, since `Fact` has no version field yet; see open question 3).
- `RenderedAnswer`:
  - `text`, `text_sha256`, `bindings[]`;
  - `unsupported_markers[]`: spans where the writer used `{{unsupported:short-reason}}`, the explicit APP-03 marker.
- `AnswerFinding`: a C-owned wrapper around the shared `ValidationResult`, so the shared file needs no edit (C1 decision s6.6 #1). Fields:
  - `result: ValidationResult`;
  - `message` (plain language);
  - `affected_span`;
  - `next_action`;
  - `evaluated_text_sha256`.
- `CheckRequest`: strict, with `question_id`, `question_version`, `text`, `evidence_bundle_id`, `mode: working|reviewed`.
- `CheckReport`: `text_sha256`, `findings[]` and `counter_version`.

  A report binds to the exact text hash, so results for an older hash are shown as out of date (s9.1, s15). It still carries no approval or status field (SEC-14).

## 4. Roles and coordinator (s8.1, SEC-12, SEC-05)

- **Planner** and **Writer** are the only roles in C2. Each is a `StructuredTask` through the C1 `ModelAdapter`, and FakeAdapter has deterministic outputs for both.
- The writer's output schema adds `{{unsupported:...}}` markers next to `{{fact:ID}}` slots.
- **Coordinator acceptance (SEC-12):** before a role result is used, code checks four things:
  1. The `task_id` and role match the task issued.
  2. The schema is strict, and the C1 validation pipeline is reused.
  3. Every referenced fact is in the evidence the identity may access.
  4. There are no permission, approval, status or fact-overwrite fields.
  
  Result text can never change facts, permissions or workflow state.
- The numerical and meaning reviewer roles are **not** in C2 (open question 1).

## 5. Deterministic rules (pure functions returning `ValidationResult`, s9.1)

There is a C-local registry with the s9.1 shape (ID, version, inputs, outcome). It moves into A3's runner at G1 with no logic change. A missing prerequisite yields `needs_review`, never `pass`.

| Rule | Implementation in C2 | Positive / negative / boundary tests (from the catalog fixture) |
| --- | --- | --- |
| APP-01 | Versioned counters `words-v1`, `code-points-v1` and `utf16-v1`, selected from the question's limit unit and convention. An unknown convention gives `needs_review` with all counts. A conflict gives `needs_review` and lists every candidate. Never `pass` on an unconfirmed convention | N and N+1 at the limit; emoji (code points vs UTF-16); apostrophes/hyphens; line breaks; pasted NBSP/zero-width characters |
| APP-02 | A status map over `required` (true/false/null), conditions and attachments. Missing required text is `fail`; `required: null` is `needs_review`; an unknown condition dependency is `needs_review` | Required empty → fail; optional empty → not_applicable; null → needs_review; missing required attachment stays incomplete |
| APP-03 | Every numeric span must be inside a claim binding or a typed exception. Exceptions are only: dates, question/section numbers and numbers quoted in the question text. Anything else is an unbound numeric. Written-out numbers ("five hundred") are `needs_review`. In reviewed mode, unbound numerics or unsupported markers are `fail`; in working mode they are `needs_review` | "500 children" unbound → fail (the C1 gap); bound slot → pass; "2025" as a year → exception; citation present but value differs from the span → fail ("citation presence alone is not support") |
| POL-01 | Scoped phrase rules (program scope, forbidden term → preferred term) applied outside quote spans | "tutor" in an LSW-scoped answer → flagged; the same word inside a quotation → not flagged |
| POL-02 | Protected text and first-use expansion within the application scope | First program mention without the required full name → fail; a later acronym → pass |
| POL-03 | Placeholder tokens (`XXX`, `TBD`, `{{unsupported:...}}`) and missing-input bindings | `XXX` in working mode → needs_review, in reviewed mode → fail; an old-period fact bound to a "current" missing input → fail |
| APP-05 | Evidence is resolved only through the identity-scoped source. A fact ID outside the caller's bundle cannot be bound, rendered or previewed | Other-org or unknown fact ID → indistinguishable 404/rejection, with no value leaked |

**POL-01/02 inputs:** approved policy sources (U01, A's policy pack) are not in the repo. C2 ships a **labelled synthetic policy fixture** (`tests/fixtures/policy/demo-policy-v1.json`, `provenance: simulated`). It contains one terminology rule and one protected-name rule, exercising the engine only. They are not Strong Start's real rules. Real rules arrive with A2 and U01 (s20.5).

## 6. Routes (s14.1, mapped to the actual `/api/applications` prefix)

| Route | Result |
| --- | --- |
| `POST /api/applications/plan` | `AnswerPlan` for the workspace's questions (sync, as C1 D1) |
| `POST /api/applications/questions/{id}/draft` | Extended: response adds `RenderedAnswer`; C1 fields unchanged (additive) |
| `POST /api/applications/questions/{id}/check` | `CheckReport` for the exact submitted text. **Stateless**: no answer persistence in C2 (open question 2) |

The errors follow the C1 table, plus 409 when the `question_version` or `evidence_bundle_id` is stale.

## 7. Web (lane plan s6.3; s18)

- **Plan panel:** each question shows its assigned evidence, missing inputs and repeated questions. Missing inputs read "Missing: … (not invented)".
- **Editor:**
  - Bound claims render as chips from `bindings`, using server-rendered text and not client formatting.
  - The counter becomes the real APP-01 result, e.g. "248 of 250 words (words-v1)"; `needs_review` text is shown when the convention is unknown.
  - Checks re-run after edits (debounced) and are shown with `FindingRow`, each with what, why, the exact value/rule, the affected text and the next action.
  - Findings for an older text hash are labelled out of date.
- A "Working draft" or "Review check" toggle selects `mode`. Nothing is labelled reviewed or approved; that is C3.

## 8. Real-producer seams (G1)

Each phase is gated: owner instruction "do not start integration" applies until each producer merges.

| Seam | Producer state now | C2 action |
| --- | --- | --- |
| Questions: B2 `AutomationHandoffExport` (merged, PR #2) | Real. Limits are `IntakeLimit` with `convention_status: unknown_pending_confirmation`; conflicts are `LimitConflictRecord` | **Phase C2b**, with owner "go": a source adapter maps the export into the workspace. APP-01 consumes `IntakeLimit` and keeps conflicts unresolved |
| Evidence: A `GET /api/knowledge/evidence/{pack_version_id}` | PR #3 open, not merged | **Phase C2b**, after the merge: swap the fixture source. Contract tests run against both fixture and real (s20.3) |
| Rule runner: A3 | Not started | The C registry has the same shape; it moves at G1 |

## 9. Tests (each runs real code)

- pytest:
  - every rule row in s5, positive, negative and boundary;
  - coordinator rejections (wrong task ID or role, permission/approval/fact-overwrite fields, inaccessible fact);
  - planner restricted to allowed facts;
  - server rendering spans exact (offsets round-trip);
  - stale hash or version → 409 or out-of-date;
  - the C1 gap case "500 children" → APP-03 finding;
  - strict request typing (`"1"` rejected);
  - all C1 tests still passing.
- Vitest:
  - plan panel with missing inputs;
  - chips from bindings;
  - counter labels (versioned / needs_review);
  - findings show and go out of date after an edit;
  - working vs reviewed mode wording.
- Gate commands: `make check`, `make smoke` and `make browser-smoke` (the shell is shared).

## 10. Scope limits and deferrals

- **Deferred:**
  - POL-04 (P1: program-assessment mapping needs A's structured program facts);
  - reviewer roles;
  - persistence, answer versions and approval (C3);
  - DOCX export (C3);
  - skills (C4);
  - durable jobs (no JobStore);
  - semantic support and paraphrase judgement (s8.2 says these need review, not code).
- No new dependency is expected, and no migration is in C2.

## 11. Open questions for the owner (please answer with "go")

1. **Reviewer roles:** s8.1 lists numerical and meaning reviewers. Should they be added in C2, or kept for a later increment? Recommendation: later. C2 already has deterministic numeric checks, and s8.1 requires reviewers to see original evidence first.
2. **Persistence:** should C2 stay stateless (check by exact text hash), or request a migration from A for answer versions? Recommendation: stay stateless. C3 owns the state machine and approval and will make one migration request.
3. **Fact versioning:** `Fact` has no version field. Bindings use `pack_version_id` plus `fact_id` until A adds one. Should this be raised as a cross-module proposal to A now? Recommendation: yes, as a note only.
4. **Phase C2b:** should C2b (consume B2's merged export) start once C2 fixture work is done, or wait until A1 also merges? Recommendation: do B2 first, since it is already in `main`.
