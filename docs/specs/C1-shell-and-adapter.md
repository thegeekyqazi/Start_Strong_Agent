# C1: App shell, application workspace and model adapter

- Task ID: C1 (lane Dev C)
- Revision: 1.1 (rev 1.0 approved by the project owner on 2026-11-07 ("go"). Rev 1.1 records the implementation changes in s11; no requirement was weakened)
- Branch: `dev-c/c1-shell-and-adapter`, base `origin/main` at `45b4488` (INIT-001 + merged B1 PR #1 + B2 PR #2). C1 keeps the `demo-bundle@1` QuestionSet; B2 `AutomationHandoffExport` is consumed in C2 (G1)
- Engineering baseline: `docs/engineering/StrongStart_Engineering_Plan.md` v1.1, sections 2, 3, 8, 14, 17, 18, 20 (20.2-20.5, C1 row)
- Checks (boundary coverage only; catalog status stays `planned`): SEC-05, SEC-06, SEC-07, SEC-14
- Out of scope: C2 (planning/claim bindings/findings engine), C3 (approval/export), C4 (skills)

## 1. Goal

Staff open **Applications** and see a three-pane workspace for the fixture application:
question list, the original question (read-only) with an editor and a live word/character
counter placeholder, and an evidence panel. They can request a draft from the configured
model adapter. With the default configuration this is a deterministic **FakeAdapter** whose
draft uses `{{fact:ID}}` slots, rendered as labelled chips, never raw numbers.

Every piece of data on screen comes from the API. The API reads the shared synthetic
fixture `tests/fixtures/demo/demo-bundle-v1.json` (`demo-bundle@1`) and labels it as fixture data.

## 2. Repo context (actual, not proposed)

- Web: Vite + React 19 + TS 7, hash navigation, `features/registry.ts`, Vitest + Testing Library, oxlint, Prettier.
- API: FastAPI app factory; `features/__init__.py` already includes `applications.router` and
  calls an optional `capabilities_for(settings)` hook (added by B1).
- Identity: `Identity` dependency. 401 when `STRONGSTART_AUTH_MODE=none`. Fixture `demo-org` identity when `fixture`.
- Contracts: Pydantic `extra="forbid"`, frozen. TS generated through `export.py` `PUBLIC_MODELS` → `make contracts`.
- Ports: `EvidenceProvider` default is `Unconfigured*`. There is no QuestionSet port and no fixture `EvidenceProvider`.
- `httpx` is already a runtime dependency of `strongstart-api` (added by B1). No new dependency is needed.

## 3. Contracts (producer C, `answers.py`, additive)

- `DraftRequest`: `question_version: int`, `evidence_bundle_id: StableId`. Extra fields are rejected, so a client `approved` is 422.
- `DraftSegment`: discriminated union of `{kind: "text", text}` and `{kind: "fact_slot", fact_id}`.
- `ModelRunInfo`: `adapter: "fake" | "gemini"`, `model: str`, `is_fixture: bool`.
- `DraftProposal`: `schema_version`, `proposal_id` (deterministic), `question_id`, `question_version`,
  `evidence_bundle_id`, `pack_version_id`, `template_text` (with slot tokens), `template_sha256`,
  `segments`, `fact_ids`, `uncertainties`, `provider: ModelRunInfo`, `provenance`.
  It has **no** approval, status or state field (SEC-14). It is a proposal by type.
- `ApplicationWorkspace`: `application_definition_id`, `question_set: QuestionSet`,
  `evidence_bundle: EvidenceBundle`, `is_fixture: bool`, `data_label: str`.

The model-facing output schema (`ModelDraftOutput`: `text`, `fact_ids`, `uncertainties`) is
internal to the applications feature and is not a public contract.

## 4. ModelAdapter (section 17)

Structured tasks only. `AgentRuntimeAdapter` is out of scope.

- `ModelCapabilities`: `structured_output`, `max_context_tokens`, `max_output_tokens`,
  `permitted_data_classes` (set of `ProvenanceClass`), `tools=False`, `streaming=False`,
  `cancellation`, `is_fixture`.
- `StructuredTask`: `task_id`, `operation="draft_answer"`, instructions, typed input payload
  (question + allowed facts), output JSON schema, `timeout_seconds`.
- `async complete(task) -> str` returns raw text. It never returns a parsed or trusted object.
- Typed errors: `CapabilityUnavailable` (existing), `ModelTimeout`, `ModelOutputRejected(reason, issues)`,
  `ModelTransportError(reason)` (`auth_rejected`, `rate_limited`, `provider_error`),
  `DataClassNotPermitted`. No error carries a raw provider body or key.
- **FakeAdapter**: local, deterministic, `is_fixture=True`, all data classes. It returns canned
  JSON whose text references the first allowed fact via `{{fact:ID}}` and contains no digits.
- **GeminiAdapter**: REST `generateContent` via `httpx.AsyncClient` with an injectable transport,
  key in the `x-goog-api-key` header (never in the URL), and JSON response mode.
  It returns `CapabilityUnavailable` with no network call when `STRONGSTART_GEMINI_API_KEY`
  or `STRONGSTART_GEMINI_MODEL` is unset. Permitted data classes: `simulated`, `engineering_derived`,
  `public`. `supplied` partner data is denied until the maintainer approves it. **No fallback** to another adapter.
- Selection: `STRONGSTART_MODEL_PROVIDER=fake` (default) or `gemini`. `fake` is unavailable when `environment=production`. This is enforced where the adapter is selected, not in settings validation (D4, s11).

## 5. Validation of every model response (SEC-14, SEC-05 boundary)

The steps run in order, and any failure is a typed `ModelOutputRejected`:

1. Raw size cap (32 KiB).
2. Strict `json.loads` with duplicate-key rejection. The top level must be an object.
3. Iterative, depth-bounded (16 levels) forbidden-key scan. Deep nesting is a typed `too_deeply_nested` rejection, never a crash: `approved`, `approval*`, `status`, `state`, `decision`,
   `approved_by`, `is_approved`. Reason `sec14_forbidden_field`.
4. Pydantic `ModelDraftOutput` (`extra="forbid"`, strict types). Reason `schema`.
5. Slot parse. Malformed `{{...}}` is rejected. Every slot ID must be in the bundle's `allowed_fact_ids`
   (`unknown_fact_id`). The declared `fact_ids` must equal the slot set (`fact_ids_mismatch`).

Only then does the service build a `DraftProposal`. Schema-valid output is still not truth.
Numeric/source checks are C2/A3.

## 6. Service, routes and errors

- Workspace source: a C-local fixture source that loads the shared bundle. It is active only when
  `settings.fixture_mode` is set; otherwise it raises `CapabilityUnavailable`. Data is org-scoped to the server identity.
- `GET /api/applications/workspace`: requires identity. Returns 200 `ApplicationWorkspace`.
- `POST /api/applications/questions/{question_id}/draft`: requires identity. Body `DraftRequest`.
  Returns **200** `DraftProposal` synchronously. See deviation D1.
- `GET /api/applications/status` and `capabilities_for(settings)`: add the `applications.model` capability
  (`fixture_only` for fake, `available` or `unavailable` for gemini depending on key/model).
- The existing `POST /api/applications/draft-jobs` placeholder keeps returning 501. The shared `tests/unit/test_api.py` depends on it.
- Errors use `ErrorEnvelope` with `details.reason`:

| Condition | HTTP | Code | Reason |
| --- | --- | --- | --- |
| No identity | 401 | `unauthenticated` | |
| Adapter/key/model/source unconfigured | 503 | `capability_unavailable` | |
| Unknown question / bundle | 404 | `validation_failed` | `unknown_question` / `unknown_evidence_bundle` |
| Question version mismatch | 409 | `version_conflict` | |
| Data class not permitted | 403 | `forbidden` | `data_class_not_permitted` |
| Model output rejected | 502 | `validation_failed` | `model_output_rejected` plus issue codes |
| Timeout | 504 | `dependency_unavailable` | `model_timeout` |
| Provider transport | 502 / 429 | `dependency_unavailable` | `auth_rejected` / `rate_limited` / `provider_error` |

- Timeout: `asyncio.wait_for` around `complete()` at `STRONGSTART_MODEL_TIMEOUT_SECONDS` (default 20 s, range 0.01-60 s; sub-second values exist for tests),
  plus the httpx timeout inside Gemini.

## 7. Web

- Shared components in `apps/web/src/shell/components/` for reuse by A and B:
  - `EvidenceCard`: value, unit, period, source, locator/page, provenance (simulated) and fact status.
    Unknown values read "unknown".
  - `FindingRow`: badge, plain-language message and a "go to" link. Links are restricted to an allowlist of
    internal `#/` and relative hrefs; other schemes render as text (SEC-07 boundary). Content is escaped text only.
  - `StatusDot`: `draft`, `needs_attention`, `approved` and `stale`, each with a text label (not color alone).
  - `HashChip`: 12-character prefix with the full hash in the title. Non-hex input reads "invalid hash".
- `features/applications/`: `client.ts` (injectable, like B1's pattern) and `Page.tsx` (three panes).
  Also a fact-slot preview with chips (value/unit/period from the evidence bundle, labelled unverified/simulated),
  and a counter placeholder explicitly labelled "placeholder count; counting convention unverified".
  The counter shows the limit, an unknown unit or an unresolved conflict as the question data states it.
  Question-data notices (limit conflict, unknown unit, unknown required) use `FindingRow` and are labelled
  "from question data, not a validation check".
- No `approved` state is displayed in the workspace. `StatusDot` approved/stale are exercised only in component tests.

## 8. Tests

Vitest:
- `shell/components/components.test.tsx`: each component with a fact parsed from the real demo bundle
  (`?raw` import). Unknown fields. Safe vs `javascript:` link. HTML message stays inert. All four status
  labels. Hash prefix and invalid hash.
- `features/applications/Page.test.tsx`: the workspace shows 4 questions, the selected original question
  is read-only, the evidence card shows and the editor is empty. "Request draft" then puts the slot template
  in the editor, shows the chip with `120` / `children` / `2025-09/2026-06` labelled simulated, and shows a hash chip.
  Typing updates the counter. 401 and 503 show distinct messages and leave the editor untouched.

pytest (`tests/applications/`):
- FakeAdapter output is byte-identical across calls, instances and two API requests. It has no digits outside slots.
- Rejections for: malformed JSON (truncated, array, empty), duplicate keys, unknown fact ID, `fact_ids` mismatch,
  extra field, `approved: true` (top-level and nested), `status`, `state`, and oversize. A valid case passes.
- Gemini with no key: `CapabilityUnavailable` and zero HTTP calls. No model: also `CapabilityUnavailable`.
  The app starts (`/health/live` 200), capabilities reports it unavailable, and draft returns 503 with no fake fallback.
  Gemini with key + `MockTransport`: valid JSON is validated. The key is in the header, not the URL.
  401/429/500 map to typed errors. Supplied-class evidence is denied before any network call.
- Timeout: a hanging adapter with a 0.05 s limit gives `ModelTimeout` within 2 s, and the API returns a 504 envelope.
  httpx `ReadTimeout` gives `ModelTimeout`.
- SEC-06 canary: with a dummy key set and a mock provider echoing it in error bodies, no applications/capabilities/session
  response body or header contains it. Web `src` and any built `dist` contain neither the canary nor `GEMINI`.
- API: workspace 401 without identity, 200 with fixture identity. Draft 200. 409 on version mismatch.
  404 on unknown question. 422 on extra/`approved` body field. 503 for the workspace when not in fixture mode.

## 9. Acceptance gate

The app opens with `STRONGSTART_AUTH_MODE=fixture` and the workspace shows the fixture question and evidence.
The fake draft fills the editor and fact slots render as chips. Bad model output cannot pass validation.
`make check` and `make smoke` pass, with output shown.

## 10. Deviations (recorded in `docs/decisions/C1-shell-and-adapter.md`)

- D1: synchronous 200 draft instead of the section 14.1 202 job, because `JobStore` is `Unconfigured`. C2/C3 move it to jobs.
- D2: a C-local fixture workspace source instead of a shared `FixtureEvidenceProvider`/QuestionSet port, to avoid a shared-file edit.
  It is proposed for promotion to `fixture_adapters.py` with A/B.
- D3: Gemini via REST/httpx rather than the Google SDK (no new dependency). The model name must be configured, not assumed.

## 11. Changes in rev 1.1 (found during implementation; owner informed in the C1 handoff)

| # | Rev 1.0 text | Rev 1.1 behaviour | Why |
| --- | --- | --- | --- |
| 1 | "`fake` is rejected when `environment=production`", via settings validation | Settings still load. In production `get_model_adapter` returns an adapter that raises `CapabilityUnavailable`, and capabilities report `applications.model: unavailable` (D4) | Validating in `Settings` crashed B1/B2 production-mode tests that build `Settings(environment="production")` with defaults. The guarantee is unchanged: production never serves fake drafts |
| 2 | Timeout range 1-60 s | 0.01-60 s | The API-level timeout test uses a 0.05 s deadline. Short values fail closed (504) |
| 3 | Recursive forbidden-key scan | Iterative scan with a depth cap of 16. `RecursionError` from `json.loads` is a typed rejection | Probing showed that 3000-deep nesting inside an object passed `json.loads` and crashed the recursive scan, which would have returned a 500 |
| 4 | `applications` capability not specified | `fixture_only` in fixture mode, otherwise `unavailable`. The C line in the shared `tests/unit/test_api.py` was updated to match | The previous `not_implemented` status is no longer true |
| 5 | (not in rev 1.0) | Shell nav CSS scoped from `nav` to `.shell > nav` in `index.css` | The global rule placed any feature-page `nav` (the question list) into the shell's grid area. Only the shell and C pages use `nav`; B1/B2 browser e2e pass unchanged |
| 6 | (not in rev 1.0) | Text typed while a draft request is in flight is never overwritten; the draft becomes a separate suggestion | s15 "do not overwrite staff work"; found while reviewing the page |
| 7 | Web scan for `GEMINI` in the canary test | Dropped. The canary-value scan remains | A provider name in UI text is not a secret; the check would have broken A/B UI text |

