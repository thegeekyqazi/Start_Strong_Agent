# dev-b-b2-auto-001-intake-slice: B2-AUTO-001 implementation deviations and choices

- Author/developer: Dev B2 agent (Claude Code) for the project owner (Dev B)
- Date: 2026-11-07
- Status: developer-decision (items 1-6); proposed-cross-module (items 7-8, need B1/A/C acknowledgement)
- Decided/accepted by and evidence: B2 agent within B2-AUTO-001 rev 1.0 s1/s4/s8 discretion and launch agreement rev 1.0 s2-s4; not yet reviewed by the owner
- Engineering path/version/sections: `docs/engineering/StrongStart_Engineering_Plan.md` v1.1 s4.1, s7, s12.4, s14.1, s15, s16
- Feature spec path/revision: `docs/specs/B2-AUTO-001_Application_Intake_and_Form_Inspection.md` rev 1.0
- PR / Issue: not published (local branch `dev-b/b2-auto-001` only)
- Supersedes / superseded by: none

## Original requirement

B2-AUTO-001 s4 asks to reuse QuestionSet/ApplicationDefinition/FormMap/SourceReference/ErrorEnvelope and use a compatible automation-owned wrapper when more metadata is needed. Engineering s14 describes long operations as 202 + durable job. s8 lists specific error names. The launch agreement s2 asks feature contracts to be imported from their modules rather than both B lanes rewriting shared export files.

## Decisions / deviations and reasons

| # | Requirement | Actual | Reason / tradeoff |
| --- | --- | --- | --- |
| 1 | Long jobs return 202 + job (eng s14) | Intake, inspection and export are **bounded synchronous requests** returning the actual result or a typed failure | No JobStore exists (`UnconfiguredJobStore`). Launch agreement s4 directs this deviation. Inspection is capped (default 15 s budget, 300 fields); no background work survives the request. A later task moves inspection behind real persisted jobs. |
| 2 | Reuse shared DTOs | New B2 module `strongstart_contracts/automation_intake.py` (`ApplicationIntakeResult`, `FormInspectionResult`, `AutomationHandoffExport`, ...). It *embeds* the unchanged shared `QuestionSet`/`ApplicationDefinition`/`FormMap` as projections | The shared `Question` cannot express native maxlength vs semantic limits, `conditional`/`unknown` required states, exact text + locators, or held action state without weakening it. `automation.py` is untouched. |
| 3 | Error names (malformed_definition, duplicate_id, ...) | Shared `ErrorCode` unchanged; the specific name is in `ErrorEnvelope.details.reason` | `common.py` is a shared, frozen-envelope contract. Mapping findings (missing/ambiguous/changed/unresolved) are typed findings in a 200 result, not errors. |
| 4 | Nonpersistent result + JSON export | `persisted=false` everywhere. Export is **re-derived server-side** from the same source request (`POST /export-definition`), not uploaded back by the client | No store is required by the spec. The client never supplies the exported content, so it cannot inject approvals or edits. Import IDs are content-derived, so re-derivation is deterministic. |
| 5 | Fixtures "under the automation fixture namespace" | Runtime fixtures live in `services/api/src/strongstart_api/features/automation/fixtures/` (shipped in the wheel). Tests live in `tests/automation/` and `tests/browser/test_automation_inspector.py` | The API serves/inspects them in local fixture mode, so they must be package data. `tests/fixtures/browser/demo-form.html` (INIT smoke) is unchanged. |
| 6 | Browser worker | Inspector lives in the B2 feature package and uses the root `browser` dependency group lazily. `services/browser` stays a README extension point | No new workspace member or dependency. Missing Playwright/Chromium → `browser_unavailable`. |
| 7 | Shared export registry | `export.py` gains one line: `*AUTOMATION_INTAKE_PUBLIC_MODELS` imported from the B2 module | Launch agreement s2 pattern. B1 adds an equivalent line. Conflicts resolve by regenerating schema/TS, never by hand-editing generated files. **Needs B1 acknowledgement.** |
| 8 | B1-B2 capture seam | B2 consumer port `CaptureSource` + `CaptureRecord` (`capture-record/1`) in `features/automation/capture.py`. B2 ships a labelled fixture producer | B1's real record is not published yet. The field mapping is in the handoff. **Needs B1 to confirm or publish its actual record so `parse_capture_record` can be adapted.** |

Additional technical choices (developer discretion):

- Readiness is polled with a fixed trusted `querySelector` check instead of `wait_for_selector`. Playwright's wait otherwise blocks on a page-initiated navigation that the inspector deliberately never commits.
- Blocked navigations are answered with HTTP 204, which Chromium does not commit, so the inspected document stays in place. Other blocked requests are aborted.
- Allowed fixture requests are fetched with `route.fetch(max_redirects=0)` and fulfilled by the inspector. A test showed that `route.continue_()` let a fixture-origin 302 reach another local service, because Playwright does not run route handlers on redirect hops.
- The fingerprint excludes label text, so the missing-label variant keeps a valid map with a `missing_label` warning. Structural changes (IDs, types, options, constraints, conditions) change the fingerprint.

## Impact and coordination

- C consumes `AutomationHandoffExport` (`b2-automation-handoff/1`) and its embedded shared `QuestionSet`/`FormMap`. C still owns counting (APP-01), approval and `ApprovedAnswerResolver`.
- B1: items 7-8 above. A: no migration and no store change. `CaptureStore` is unchanged and unused by this slice.
- `tests/unit/test_api.py` (shared) now expects `automation` to be `fixture_only` instead of `not_implemented`, and excludes automation from the 501-placeholder loop. The 401 check still covers `/api/automation/intake`.

## Validation and rollback

Validated by `make check`, `make smoke`, `make browser-smoke` and the per-case evidence in `docs/handoffs/dev-b/b2-auto-001-check-evidence.md`. Rollback: revert the branch commits. Shared files touched are `export.py` (one line), the regenerated schema/TS (regenerate) and `tests/unit/test_api.py`.

## Update 2026-11-07 (after B1 merge, rebase onto `8df9df8`)

- Item 7: both lanes' registrations were kept in `export.py`. B1 used an explicit list and B2 a module tuple; both are compatible. Schema/TS were regenerated, not hand-merged.
- Item 8: B1 published `CapturedDocument` schema "1" and `CapturedDocumentReader`. B2 now adapts it (`record_from_captured_document`, `B1CaptureSource`) and uses B1's development-only store ahead of the B2 fixture producer. The B2 contract `CaptureLineage` gained additive fields: `final_url_status` now also allows `provider_reported`, plus `producer`, `producer_source_reference_hash` and `producer_supported_representations`. Status: implemented-tested against B1's sample and B1's API; awaiting B1 acknowledgement. See `docs/handoffs/dev-b/b2-auto-001-r2.md`.
