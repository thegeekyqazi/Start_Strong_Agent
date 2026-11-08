# B2-AUTO-001: application intake and representative-form inspection (r1)

- Author/lane: Dev B2 agent (Claude Code, claude-opus-5-5) for the project owner (Dev B)
- Intended consumers: B1 (capture seam, shared export line), C (question set / form map handoff), A (no action; FYI SRC-* subsets), owner (review)
- UTC timestamp: 2026-11-08T03:00Z (local 2026-11-07)
- Status: ready-for-review (local only, not published)
- Task spec path/revision: `docs/specs/B2-AUTO-001_Application_Intake_and_Form_Inspection.md` rev 1.0; launch agreement `B1-B2_Parallel_Launch.md` rev 1.0 (untracked copy in this worktree; B1 owns committing it)
- Engineering version/sections and rule IDs: v1.1 s4, s7, s9-10, s12-16, s18-20, s22. Tested subsets: SEC-01/03/04/05/07/08/09/13/14, SRC-01/02/03/05/08/09, APP-01/02/05 (representation only), AUT-01, AUT-04 (representation only), JOB-02/03. See the check-evidence note. Catalog unchanged.
- Branch and exact implementation commit: `dev-b/b2-auto-001`; base `ad5b8dd10a4104ce3442c5788c3ed87f0c54a9da`; head = the commit containing this note (run `git log -1 dev-b/b2-auto-001`)
- PR / Issue links: not published. `origin` exists in the checkout, but publication was not authorized for this task.
- Supersedes / superseded by: none

## What works

- **Intake** `POST /api/automation/intake` with `{"source": {...}}`, modes:
  - `fixture`: `rep-portal-definition-v1` (structured) or `rep-portal-v1-html` (static HTML of the portal).
  - `structured_json`: uploaded, labelled `uploaded_unverified`.
  - `html`: saved HTML, uploaded, parsed statically.
  - `capture`: `capture_id` + `artifact_id` through the capture port.
  
  Results contain typed questions in original order, exact wording + derived display text, JSON-pointer/HTML-element locators (with line/column for HTML), the input sha256/size/parser/normalization versions, scope, type, required/conditional/unknown, choices, attachment constraints, competing limits, and a held action state for unresolved items. `persisted=false`, `approval_status=not_approved`, `authority_status=imported_provisional_unreviewed`. Shared `QuestionSet` + `ApplicationDefinition` projections are produced when the opportunity is known.
- **Representative portal** (team fixture, engineering-derived, `original_guide_present=false`; not the United Way portal). Variants: `rep-portal-v1` plus duplicate, missing-label, unsupported-widget, altered, dynamic, hostile, never-ready. Staff can view it at `GET /api/automation/fixtures/portal/{id}`, served sandboxed with no forms or network.
- **Read-only inspection** `POST /api/automation/inspect-fixture {fixture_id, expected_form_version?, expected_fingerprint?}`:
  - real Chromium in a fresh context against an ephemeral loopback fixture server;
  - only registered GETs on that origin are allowed, and redirects are never followed;
  - everything else is blocked and logged: other origins, private/metadata addresses, non-GET, WebSockets, popups, downloads, navigation;
  - the server waits for the declared ready condition, then reads the DOM with fixed trusted JS;
  - per-field mapping status: matched/missing/ambiguous/type_mismatch/unsupported, with no first-match fallback;
  - fingerprint vs stored v1, typed findings, and a `FormMap` only when valid;
  - no fill/click/upload/submit; `prefill_permitted=false`.
- **Export** `POST /api/automation/export-definition {source, inspect_fixture_id?}` re-derives everything server-side. It returns `AutomationHandoffExport` (`b2-automation-handoff/1`): intake, optional inspection, shared projections, form map, an `unresolved` list and consumer notes. The UI downloads it verbatim.
- **Availability** `GET /api/automation/availability`: granular capabilities, import modes with byte limits, browser status (checked without launching) and the fixture catalogue (fixture mode only).
- **UI**: the existing Automation page (`apps/web/src/features/automation/`) covers availability, import (fixture/JSON/HTML/capture, paste or file), questions table, evidence panel, document findings, inspection view, and export. It has loading/empty/invalid/too-large/source/browser-unavailable/conflict states. All imported content renders as React text.

## Contract and dependencies

- Contracts: `packages/contracts/python/src/strongstart_contracts/automation_intake.py` (owner B2, draft), registered via one line in `export.py`. Schema/TS regenerated (`make contracts`). Generated TS names: `ApplicationIntakeResult`, `FormInspectionResult`, `AutomationHandoffExport`, `AutomationAvailability`, `ImportApplicationRequest`, `InspectFixtureRequest`, `ExportDefinitionRequest`. `automation.py`, `common.py`, `ports.py` and the demo bundle are unchanged.
- Errors: shared `ErrorEnvelope`. The specific reason is in `details.reason`: `malformed_request`, `malformed_definition`, `duplicate_id`, `unsupported_input`, `input_too_large` (413), `source_unavailable` (404/503), `hash_mismatch` (409), `browser_unavailable` (503), `fixture_not_allowed` (403), `timeout` (504), `unknown_form_version` (422). Mapping problems are findings in a 200 result.
- **Structured input format** `strongstart-application-definition` v1. Top level: `format`, `format_version`, `definition_id`, `opportunity_id?`, `stream_id?`, `cycle_id?`, `title?`, `provenance_note?`, `source? {capture_id, artifact_id}`, `questions[1..200]`. Each question has: `question_id`, `number?`, `section?`, `text`, `instructions[]`, `scope`, `type` (text/number/select/choice/group/file/unsupported), `required` (required/optional/conditional/unknown), `condition? {text, depends_on, equals}`, `limits[] {maximum|minimum (int or decimal string), unit (words/characters/amount/unknown), counting_convention?, stream?, text}`, `choices[] {value, label?}`, `multiple?`, `attachment? {accepted_types?, max_size_bytes?, max_count?}`. Unknown keys are preserved as original evidence; types are strict. Limits: 256 KiB, depth 12. Example: `services/api/src/strongstart_api/features/automation/fixtures/definitions/rep-portal-definition-v1.json`.
- **Supported HTML patterns** (parser `b2-html-form/1`, stdlib tokenizer, nothing executed or fetched):
  - question wording from `label[for]`, wrapping labels (with a leading "N." recorded as the number), or `fieldset/legend` for radio/checkbox groups; non-group legends and `h1-h4` inside the form become sections;
  - `aria-describedby` text becomes exact instructions;
  - supported controls: textarea; input text/email/url/tel/search/number/radio/checkbox/file; select/option;
  - attributes: required, aria-required, maxlength, min/max/step, accept, multiple, hidden;
  - `data-fixture-*` is declared fixture metadata.
  
  Everything else becomes `unsupported_widget` with partial coverage. Duplicate DOM IDs among controls → `duplicate_id`. Limits: 512 KiB, 5000 elements, 300 controls.
- **Limit text patterns** (`b2-norm/1`): "Maximum/Max/up to/no more than/at most N [words|characters]", "N words/characters", and for number fields "A to B" ranges. A missing unit is `unknown`. Counting convention is `unknown` unless declared. Native maxlength is `utf16_code_units` (`defined_by_html_spec`), stored separately and never merged into semantic limits.
- **Fingerprint `b2-form-fp/1`**: SHA-256 of the canonical JSON of the sorted per-control identity records `{tag, input_type, dom_id, name, role, contenteditable, required, disabled, readonly, max_length, min, max, step, accept, multiple, option_value, options[values], condition}`. Labels, descriptions, visibility, order, values and other `data-fixture-*` attributes are excluded. Stored v1: `41ccba87c5f2a8be646e8883a8eed85920d71b8d3179cc4688fa57b0874716ac` (recorded from real Chromium; main, dynamic-after-wait and hostile all match).
- **B1 adapter mapping** (B2 consumer view `capture-record/1`, `features/automation/capture.py::parse_capture_record`): `capture_id`, `source_id`, `source_version_id`, `organization_id` (server-scoped, compared to identity), `opportunity_id/stream_id/cycle_id?`, `urls {original, requested, final, final_status known|unknown}`, `provider`, `captured_at`, `artifacts[] {artifact_id, representation_type (provider_html|provider_raw_html|original_http_bytes|provider_markdown|...), media_type, byte_size, sha256}`, `extraction {coverage complete|partial|empty|unknown, warnings[]}`, `provenance`, `authority_review_status`. Bytes come from the port's `read_artifact(org, capture_id, artifact_id)`; B2 recomputes sha256 and never refetches URLs. HTML representations are parsed; markdown/PDF are preserved as unsupported.
- Source availability: **no original partner/guide files were present**. All fixture constraints are engineering-derived (s7). The B2 fixture capture producer (`fixtures/captures/records.json`) is synthetic, uses `.invalid` URLs, and includes markdown, PDF-placeholder, tampered and other-org records.

## Validation

`make check` exit 0 (ruff, ruff-format, oxlint, Prettier, mypy strict 67 files, pytest 135 passed / 12 deselected, vitest 9 passed, contracts-check, build) · `make smoke` exit 0 (15 capabilities) · `make browser-smoke` exit 0 (10 passed). The real UI was driven against the real API (see evidence). Per-case table: `docs/handoffs/dev-b/b2-auto-001-check-evidence.md`. Not run: GitHub CI, live B1 producer, any third-party site.

## Decisions and deviations

`docs/decisions/dev-b-b2-auto-001-intake-slice.md`:
- bounded synchronous operations instead of jobs;
- automation-owned wrapper contracts;
- error reason in details;
- server-re-derived export;
- runtime fixtures as package data;
- items 7-8 are `proposed-cross-module`: the `export.py` line, and the capture-record shape for B1.

## Consumer action / blockers

- **B1**: confirm or publish the actual serialized capture record and authorized read operation. B2 will then adapt `parse_capture_record`/add a `CaptureSource` adapter and rerun `test_auto14_b1_saved_html_passes_through_importer_with_lineage` with B1's sample. Acknowledge the one-line `export.py` registration pattern. After B1 merges, B2 rebases and regenerates schema/TS.
- **C**: consume `AutomationHandoffExport` and the embedded shared `QuestionSet`/`FormMap`. Use the `unresolved` list and `limit_conflicts` (never pick one). Counting conventions are `unknown` pending confirmation (APP-01 is C's). Provide the real `ApprovedAnswerResolver` for B2-AUTO-002.
- **B2-AUTO-002** depends on C's resolver/approval snapshots and on the form map + fingerprint here. Prefill, read-back (AUT-02/03), attachments (AUT-04) and SEC-08 action grants stay future work.
- **Owner**: review; decide on publication/PR.

## Acknowledgments

None yet.
