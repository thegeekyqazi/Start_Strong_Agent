# C1: App shell components, application workspace and model adapter (r1)

- Author/lane: Dev C agent (Claude Code, claude-opus-5-5)
- Intended consumers: project owner (review), Dev A, Dev B1, Dev B2
- UTC timestamp: 2026-11-08T04:13Z
- Status: ready-for-review (**local only**: not pushed, no PR; awaiting owner authorization)
- Task spec path/revision: `docs/specs/C1-shell-and-adapter.md` rev 1.1. Lane plan: `docs/coordination/dev-c-lane-plan.md` rev 1.0, on branch `dev-c/c0-lane-plan` (commit `6bb5a19`, not pushed)
- Engineering version/sections and rule IDs: v1.1, s8.2, 8.3, 14, 15, 17, 18, 20. SEC-05, SEC-06, SEC-07, SEC-14 boundary coverage only (all 86 catalog rules remain `planned`)
- Branch: `dev-c/c1-shell-and-adapter`, base `origin/main` `45b4488` (INIT-001 + B1 PR #1 + B2 PR #2)
- Implementation commits (this note is the next commit; a file cannot contain its own SHA):
  - `02bb137` docs: spec rev 1.1 and decision record
  - `728d9c7` contracts
  - `73bc640` API adapters, validation, workspace and tests
  - `83fc859` web components, workspace page and tests
- PR / Issue links: not published. `gh` is installed but not authenticated on this machine
- Supersedes / superseded by: none

## What works

Staff open **Applications** in local fixture mode (`STRONGSTART_AUTH_MODE=fixture`) and see three panes.

- **Question list:** the 4 `demo-gos-questions-v1` questions, with tags "Required" / "Required: not stated" / "Limit conflict" / "Unit unknown".
- **Selected question:**
  - The original wording is shown read-only with its provenance ("Derived from the engineering plan, not the original guide").
  - The limit is shown exactly as the data states it:
    - partnership-q3 shows both 350 and 500 words, unresolved;
    - pending-q4 shows "Max 300", unit unknown, with both word and character counts.
  - The "Your answer" editor has a live counter labelled "placeholder count; counting convention unverified".
- **Evidence panel:** an EvidenceCard for `demo-fact-children-served`.
  - It shows 120 children, 2025-09/2026-06, the source, the locator and the publication date.
  - Separate lines cover staff review ("Not yet verified by staff"), source verification, time suitability (the bundle's coverage note, quoted) and provenance ("Simulated – synthetic demo data").

**Request a draft** calls the API. The default FakeAdapter returns a deterministic proposal whose figure is a `{{fact:demo-fact-children-served}}` slot, so the prose contains no raw number.
- The editor fills with the template.
- A preview renders the slot as a chip: "120 children · 2025-09/2026-06 · Simulated · Not yet verified by staff".
- Draft details show "demo writing assistant (fixed sample output, not an AI model)", "Draft – not reviewed", a version fingerprint and the uncertainties.

If the editor already has text, including text typed while the request is in flight, the draft becomes a separate "Suggested draft" with an explicit replace button (s15). Every failure has its own plain-language message, and the editor is untouched.

### Real vs fixture

| Capability | Status |
| --- | --- |
| Workspace questions/evidence | **fixture-only**: shared `demo-bundle@1`, active only in fixture mode; otherwise 503 `capability_unavailable` |
| Identity | INIT fixture identity (not authentication); 401 without it |
| FakeAdapter drafts | **fixture-only**: labelled, deterministic, unavailable in production |
| GeminiAdapter | **implemented, tested only with mocked HTTP**. Live call **NOT RUN** (no key, and no model ID confirmed, s23.1) |
| Model-output validation | **real**: runs on every response, including Gemini |
| Counter | **placeholder**, not APP-01 (the versioned counter is C2) |
| Draft persistence | **none**: proposals live in browser state only. No AnswerSnapshot is created (C2/C3) |
| Unbound-number scan of model prose | **not implemented** (APP-03, C2). The fake adapter never emits digits; Gemini is only instructed not to |

## Contracts and dependencies

New C-owned models (`strongstart_contracts.answers`, exported via `ANSWERS_PUBLIC_MODELS`, all `draft`, `x-owner: C`) are generated to TS through `make contracts`:
- `DraftRequest {question_version, evidence_bundle_id}` (extra fields are rejected);
- `DraftProposal` (`template_text` with `{{fact:ID}}`, `template_sha256`, `segments` of text/fact_slot, `fact_ids`, `uncertainties`, `provider: ModelRunInfo`, `provenance`). It has **no** approval/status/state field;
- `ApplicationWorkspace {application_definition_id, question_set, evidence_bundle, is_fixture, data_label}`.

Routes (identity is resolved before any source or model access):

| Route | Success | Errors (`ErrorEnvelope`, reason in `details.reason`) |
| --- | --- | --- |
| `GET /api/applications/workspace` | 200 `ApplicationWorkspace` | 401; 503 `capability_unavailable` (not fixture mode); 404 `unknown_workspace` |
| `POST /api/applications/questions/{question_id}/draft` | 200 `DraftProposal` (sync, D1) | 401; 404 `unknown_question` / `unknown_evidence_bundle`; 409 `version_conflict`; 403 `data_class_not_permitted`; 502 `model_output_rejected` (+ `issues`); 504 `model_timeout`; 429 `rate_limited`; 502 `auth_rejected` / `provider_error`; 503 adapter unconfigured; 422 bad body |
| `GET /api/applications/status` | runtime `Capability[]` | |
| `POST /api/applications/draft-jobs` | unchanged 501 | |

`/api/capabilities` reports:
- `applications`: `fixture_only` in fixture mode, otherwise `unavailable`.
- `applications.model`: `fixture_only` for fake; `available` or `unavailable` for gemini by key and model; `unavailable` for fake in production.
- `review` and `skills`: `not_implemented`.

The `ModelAdapter` interface lives in `services/api/src/strongstart_api/features/applications/models/`:
- `capabilities()` declares structured output, context/output limits, permitted data classes, `is_fixture`, and `tools/streaming/cancellation=False`;
- `async complete(task) -> str` returns raw text only.

Settings (names only):
- `STRONGSTART_MODEL_PROVIDER`: `fake` (default) or `gemini`;
- `STRONGSTART_GEMINI_MODEL`: empty means unset;
- `STRONGSTART_MODEL_TIMEOUT_SECONDS`: default 20;
- plus the existing `STRONGSTART_GEMINI_API_KEY`.

**Reusable by A and B** (`apps/web/src/shell/components`): `EvidenceCard` (`Fact`), `FindingRow` (presentational: `origin`, `outcome`, `message`, optional observed/expected, affected text, next action, in-app `href`), `StatusDot`, `HashChip`, and plain-language labels in `labels.ts`. All render inert text.

## Validation (2026-11-07, this checkout, macOS; Node 22.16.0 (below the declared 22.22.2, Vitest ran fine); Python 3.12.4)

| Command | Result |
| --- | --- |
| baseline `make check` before any change | exit 0: 261 pytest, 24 Vitest |
| `make check` on HEAD `83fc859` | exit 0: ruff clean; mypy strict no issues (100 files); oxlint/Prettier clean; **pytest 323 passed** (15 deselected db/browser); **Vitest 48 passed**; contracts drift clean; web + wheels built |
| `uv run pytest tests/applications` | **55 passed** |
| `make smoke` (local Postgres via `make db-up`) | exit 0: 53 import + 2 db tests; real API live 200, ready 200 (`0001_bootstrap`), capabilities 200 (16 entries) |
| `make browser-smoke` | exit 0, **13 passed** (B1 funding e2e and B2 inspector tests unchanged after the shell CSS scoping) |
| Manual headless Chromium, real API (fixture mode) + Vite, 1500px and 420px | 4 questions, evidence card, empty editor; after the draft request the editor holds the slot template and the chip text is correct; 0 page errors; 0 external requests; three columns wide, stacked narrow with no horizontal scroll |
| Gemini live call | **NOT RUN** (no key or confirmed model ID) |

Defects found and fixed during validation:
1. A recursive key scan crashed on 3000-deep nesting, which would have returned a 500. It is now an iterative scan with a depth cap of 16 and a typed `too_deeply_nested` rejection.
2. In-flight typing could be overwritten by a draft.
3. The global shell `nav` CSS broke feature-page layout.
4. A settings-level production guard broke B1/B2 production-mode tests (D4).

### Rule boundary evidence (catalog statuses unchanged: `planned`)

| Rule | Covered here | Not covered |
| --- | --- | --- |
| SEC-14 | `DraftProposal`/`DraftRequest` cannot carry approval/status. Model output with `approved`, `status`, `state`, `approval*` or `decision` (top-level or nested) → 502 `sec14_forbidden_field`. Client `approved` → 422 (`test_model_output_validation.py`, `test_applications_api.py`) | Approval workflow itself (C3) |
| SEC-05 | Adapters declare no tools. Only a 3-field schema is accepted: extra fields, wrong types, duplicate keys, non-finite numbers, malformed slots and unknown fact IDs are rejected before anything is built | Tool-call registry and action gateway (no tools exist yet) |
| SEC-06 | A canary key never appears in any applications/capabilities/session/OpenAPI response body or header, even when the mocked provider echoes it in error bodies. Key sent only in a header. Web src + built `dist` contain no canary (`dist` is scanned only when it exists). A scan is not proof | Secret scanning of generated skills (C4); production secret store |
| SEC-07 | C components render React text only. HTML in messages stays inert; `javascript:`, `//`, `https:` and `data:` hrefs are not rendered as links (`components.test.tsx`) | Rich evidence previews/sanitizer (none exist) |

## Decisions and deviations

`docs/decisions/C1-shell-and-adapter.md` (developer-decision) covers:
- D1: synchronous draft route;
- D2: C-local fixture workspace source;
- D3: Gemini over REST/httpx;
- D4: production fake guard at adapter selection.

Spec rev 1.1 s11 lists every change from rev 1.0.

## Consumer action / blockers

- **Owner:**
  - Review the four commits.
  - Authorize push and a draft PR for `dev-c/c1-shell-and-adapter`, and separately for `dev-c/c0-lane-plan`.
  - Run `gh auth login` on this machine so C can open PRs and post acknowledgments.
  - Optionally supply a Gemini key and model ID for one live smoke.
- **B1:** acknowledge the three additive `.env.example` names (you coordinate that file).
- **A, B1, B2:** acknowledge two changes:
  - the C line in `tests/unit/test_api.py`: `applications` is now `unavailable` by default, and there is a new `applications.model`;
  - the `.shell > nav` CSS scoping, which only affects pages that use `nav`; today that is only C's page.
  
  The shared components are available to reuse; no action is required.
- **B2:** C has read `AutomationHandoffExport` (b2-auto-001 r1/r2). C consumes it in **C2** at G1 and provides the real `ApprovedAnswerResolver` in **C3**. No integration was started in C1, per owner instruction.
- **A:** C has read A1-KNOW-001 r1 (PR #3, head `053eb92`, not merged). C2 will swap the fixture `EvidenceBundle` for `GET /api/knowledge/evidence/{pack_version_id}` after merge and seeding. Simulated `needs_review` facts are already displayed as unverified.
- **Blockers:** none for C1. Live Gemini needs credentials. C2's real seams need A2/A3 and B2's export (G1).

## Next step

Write the C2 spec (plan/draft with claim bindings and visible findings: APP-01/02/03, POL-01..04, SEC-12) against the then-current `main`, and get the owner's "go" before code.

## Acknowledgments

None yet.
