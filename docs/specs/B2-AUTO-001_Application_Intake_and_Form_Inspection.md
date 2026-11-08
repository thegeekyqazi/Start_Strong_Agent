# B2-AUTO-001: Application intake and representative-form inspection

**Revision:** 1.0  
**Assigned agent:** Dev B2, Application Intake and Browser Automation.  
**Reported base:** ad5b8dd; resolve/verify in the real checkout.  
**Branch:** dev-b/b2-auto-001.  
**Engineering references:** v1.1 sections 4, 7, 9-10, 12-16, 18-20 and 22.  
**Related agreement:** B1-B2_Parallel_Launch.md.  
**Product outcome:** Staff can import a supported application definition/captured HTML, inspect original instructions and uncertainty, and compare a representative form's actual fields with a typed question map.

## 1. Execute, inspect and preserve

Read AGENTS.md, this spec, the shared launch agreement, the complete INIT report and decisions 0002/0003. Inspect the actual automation router/page, Pydantic contracts, schema-generation commands and root Playwright dependency group. Read relevant engineering/check entries before implementation. The spec author has only the owner's partially truncated report, not this actual code.

Preserve existing oxlint/TypeScript/Vite/navigation choices, DB setup and registered A/B1/C entry points. Extend only your automation lane and owned contract/test modules. Do not introduce a second frontend/router, replace root Playwright packaging or rebuild approval/drafting services. Copy this task spec to docs/specs if needed; use actual prefixes/imports and document the mapping.

Implement through tests and handoff rather than writing another plan. Use fixtures until B1's capture producer is available. Publish required shared changes early; do not edit common lockfiles/migration heads/export registries concurrently without the launch agreement.

## 2. Scope and exclusions

Required: typed application/question/attachment/limit/conflict records using existing DTOs; import of a bounded structured JSON definition and supported saved HTML form; immutable input representation/hash and locators in results; a clearly labelled representative portal; Playwright read-only inspection of that portal; unique field-map validation; Automation UI; JSON export; meaningful tests and the B1/C handoff.

This task does not fill answers, upload attachments, log into third-party sites, sign/submit, draft proposal text, approve content, implement full answer counters or parse arbitrary PDFs/scans/prose guides. The reported Chromium truncation smoke proves the browser installed; it does not constitute real approved prefill. B2-AUTO-002 will consume C's authoritative approved-answer resolver and implement that action path later.

No original partner/guide files were present in the reported setup. Use labelled engineering-derived fixtures now. If actual originals appear, inventory them; do not silently expand scope to broad PDF/OCR support or claim that the fixture was extracted from them.

## 3. Required user path

1. Staff opens the existing Automation page and sees supported import modes, browser/fixture availability and unfinished prefill state.
2. They choose a known fixture, paste/upload a supported structured JSON definition, or import captured HTML through an authorized capture port.
3. The system returns typed questions in original order with original wording, field type, limits/units, instructions, required/conditional status, choices, attachments and source location. Missing/ambiguous data is explicit.
4. Staff opens the representative local portal and requests read-only inspection. The result lists actual browser-observed fields and how they map to questions, including unsupported or ambiguous mappings.
5. The evidence panel shows exact imported text/metadata and source representation/hash/locator. Conflicting instructions show both alternatives and block action readiness for affected fields.
6. Staff exports a versioned JSON ApplicationDefinition/QuestionSet/FormMap handoff for C and later prefill work. Any nonpersistent state is labelled; an export is not an approved application.

Provide loading, empty, invalid JSON, unsupported content, oversized input, source-read failure, browser-unavailable and mapping-conflict states. Keep field inspection and answer approval separate. A valid map is not permission to fill it.

## 4. Supported import contract

Reuse existing QuestionSet/ApplicationDefinition, FormMap, SourceReference and ErrorEnvelope. If additional metadata is necessary, use an automation-owned compatible wrapper rather than weakening strict shared schemas. Preserve unknown fields only in a documented original-evidence blob, not as arbitrary executable attributes or silently accepted policy.

| Information | Required behaviour |
| --- | --- |
| Identity/order | Stable internal question ID plus original number/section/order. Duplicate incompatible IDs are errors, not silently renumbered. |
| Original wording | Preserve exact question/instruction text and source location; normalized display text is a separate derived value. |
| Scope/type | Organization/program/unknown scope; text/number/select/choice/group/file/unsupported type as observed. No inferred diagnosis/program claims. |
| Limits | Value, unit, counting convention when known, evidence and competing constraints. Distinguish words, characters, native DOM maxlength and unknown unit. |
| Required/conditional | Required, optional, conditional or unknown with a source predicate/reference. Unknown JS conditions remain unresolved. |
| Choices/fields | Preserve option values/labels and explicit radio/checkbox grouping. A group is not a duplicate merely because it contains multiple controls. |
| Attachments | Allowed types, size/count and required state only when supported by source; unknown otherwise. No attachment upload. |
| Evidence/version | Source/capture/hash/representation/parser version and precise locator. No made-up PDF page numbers. |
| Conflict/completeness | Preserve conflicting/absent requirements and processed/supported coverage. No conflict resolution by choosing the shortest convenient limit. |

Implement structured JSON input with strict size/depth/count limits, duplicate-key rejection where needed, safe decoding and schema errors. Implement HTML-form extraction with a bounded non-executing parser: labels/for, fieldset/legend, textarea, input/select attributes, choices and explicit nearby instructions. Do not execute uploaded HTML, follow links, interpret JavaScript or load its external resources to parse it.

An uploaded definition proposes instructions; its own claims of source authority or review are not trusted. The server creates the import identity/hash and records its origin as uploaded/unverified or an explicit fixture. Supplied source IDs must resolve through an authorized source adapter before being shown as verified. Exported limits remain imported/provisional until their actual authority has been reviewed; a well-formed JSON object cannot approve a funder rule.

Only supported form/structured patterns yield normalized fields. Unsupported content returns a specific status; a natural-language paragraph does not automatically become a validated question definition. Parsing confidence is not source truth. Original HTML scripts remain inert evidence if retained; do not render them in the app.

Maintain a version/hash of the exact imported bytes and parser/normalization version. For this first task, return the typed result with an explicit persisted/nonpersistent flag and downloadable JSON; no DB migration or global application store is required. Use an available CaptureStore port for original artifacts or a confined automation-owned fixture/input representation store marked development-only. Do not expose arbitrary server paths or create a second full knowledge store.

## 5. Representative fixture set

Build one local representative portal and variants under the automation fixture namespace. It is this team's fixture, not the real United Way portal. Label every page/result/export accordingly. Source the example constraints from engineering v1.1 section 7, with provenance engineering_derived_fixture and original_guide_present=false unless actual bytes were supplied/parsed by a separate supported task.

Minimum cases: mission field with 50-word instruction; services field with 250-word instruction; pending-applications field with 300-character instruction; a partnership field whose imported instructions disagree at 350 versus 500 words; a field saying Max 300 with no unit; a standard request numeric field; a choice group; a conditional section; and an attachment control with explicit fixture constraints. These are illustrative test fields, not verbatim extracted funder questions or a verified open grant cycle.

Preserve numeric request/stream distinctions as input metadata; B1 owns eligibility interpretation. Do not automatically apply a network limit to standard GOS. Native input maxlength is a browser property; a funder's word limit is a separate semantic constraint. When they conflict, surface both. Do not assume a generic characters label specifies UTF-16, code points or grapheme counting; record unknown convention pending confirmation. [R03]

Add malformed variants: duplicate field IDs/unexpected selector matches, missing label, unsupported widget, altered form fingerprint, unknown limit unit and dynamic/hidden conditional content. Fixture-specific data attributes may describe expected IDs/conditions, but label them as declared fixture metadata. Do not claim the same technique understands arbitrary third-party portal logic.

Fixtures include a submit/sign surface that is unavailable/denied to the automation principal, or no executable submission path at all. A visible disabled button alone is not proof that submission is prevented. Instrument tests to observe zero mutation/submission requests from the inspector.

## 6. Read-only Playwright inspector

Use the existing installed Playwright/Chromium and root dependency group. Create a fresh browser context with no user cookies, saved sessions or secrets. Inspect only the server-registered representative fixture origin/path; the client chooses an allowed fixture ID, not a free URL. Bind the ephemeral fixture-server origin into a scoped server-owned test/inspection context. Never permit arbitrary localhost targets to bypass B1's public URL policy.

Wait for a declared fixture-ready condition before enumerating controls. Read DOM labels/legends/types, IDs/names, group members/options, required/disabled/readonly/maxLength attributes, visible/hidden state, expected supported conditions and attachment accept/multiple values. Locators operate against actual observed fields; dynamically changing lists require an explicit wait rather than an immediate blind enumeration. [R01]

Construct a versioned FormMap and fingerprint from canonical field identity/type/group/options/constraint metadata, excluding volatile display data and secret values. A mapping is valid only when the expected field or declared group resolves with the expected cardinality/type. Missing/ambiguous/changed fields return findings. Do not fix them with .first() or a silent nth selector.

No answer value entry, selection changes, uploads, clicks, submission/signing or login in this task. Browser DOM evaluation must be trusted application code that reads an allowlisted structure, not JavaScript provided in imported content or generated by a model.

Block unexpected navigation, redirects, downloads, popups and external subresources in the controlled fixture context. Use service-worker restrictions and request logs appropriate to the installed Playwright version. Browser interception has limitations and does not establish arbitrary-site production isolation; the current capability remains registered-local-fixture read-only inspection. [R02]

Enforce finite page/field/byte/time limits and cancellation cleanup; close contexts/processes on all exit paths. Keep the browser test/process ports separate from other agent services and leave the unrelated port-7000 service alone. Do not introduce unbounded asynchronous jobs or fake durable job states.

## 7. B1 and C integration contracts

Implement an intake function/port accepting the shared captured-document semantic v1 record and exact supported content bytes, as defined in the launch agreement. Preserve B1 source/version/hash/organization/opportunity/cycle references. Verify hash/authorization at the available boundary; do not trust client-attested metadata. No automatic URL refetch when capture bytes exist.

Start with a fixture producer while B1 is building. When B1's sample is available, run it through this real importer. If a captured page is prose or markdown without supported structured/form content, return unsupported/needs_manual_definition with preserved evidence; do not invent questions to make the seam look successful.

Export the typed question set and field map to C. Identify unresolved limits, required fields, attachment instructions and incomplete scope. C's future writer/counter/approval APIs consume these records; do not implement those authorities locally. Preserve the existing ApprovedAnswerResolver as unavailable here. Tests/fixtures describing future approvals do not enable prefill endpoints.

Expose implementation availability granularly: intake supported; local browser inspection supported if actually tested; original PDF parsing not implemented; approved prefill not implemented; final submission unavailable. Avoid a single automation-ready flag that implies all of these work.

## 8. API/UI implementation shape

Use the existing automation router. Suggested relative operations: POST imports for structured/supported HTML input; POST inspect-fixture with a server-defined fixture ID and expected map version when comparing; POST export-definition or a typed client download; GET availability. The actual prefixes/signatures follow the initialized code. Use current auth dependencies before input storage or browser launch; retain 401 without identity and production fixture restrictions.

Use schema-generated TypeScript types. The Automation page shows source/mode, question/instruction list, limits/units, source locators, conditional/attachment states, conflicts and map-inspection findings. Include fixture selection, bounded input import, inspection and JSON export. Escape raw content. Preserve the existing shell/navigation rather than adding a new router/library.

Do not accept org_id/approved=true/action authorization from the client. Error responses distinguish malformed_definition, duplicate_id, unsupported_input, input_too_large, source_unavailable/hash_mismatch, browser_unavailable, fixture_not_allowed, timeout, mapping_missing/ambiguous/changed and unresolved_requirement. Reuse ErrorEnvelope and safe request IDs. Do not return internal filesystem paths, cookies or raw exceptions.

## 9. Deterministic checks and acceptance cases

Default tests are local, deterministic and require no paid provider or partner login. Use actual Chromium for browser behaviour, not a mocked browser claimed as real. Run baseline make check, make smoke and make browser-smoke, plus targeted tests from actual repo commands.

| Test ID | Scenario / expected observation | Rule references |
| --- | --- | --- |
| AUTO-01 | Unauthenticated import/inspection denied before artifact access/browser launch; client org/approval cannot grant rights. | SEC-01, SEC-14, APP-05 |
| AUTO-02 | Valid structured fixture preserves IDs/order/text/source/hash and unknowns; export roundtrip preserves semantics. | SRC-01, SRC-03, SRC-08 |
| AUTO-03 | Invalid JSON/type/depth/size and incompatible duplicate IDs fail clearly; no silent field repair. | SEC-04, SEC-05 |
| AUTO-04 | Static HTML parses without executing scripts, loading resources or following embedded instructions. Evidence renders inert in UI. | SEC-07; capture/parser boundary |
| AUTO-05 | Word limit, character limit, native maxlength and unknown unit stay distinct. The 350/500 conflict preserves both sources and holds the affected action state. | APP-01 prerequisite representation only |
| AUTO-06 | Required/conditional/unknown status and explicit attachment types/counts survive import; unsupported condition stays unknown. | APP-02 and AUT-04 prerequisite representation only |
| AUTO-07 | Real Chromium reads representative fields and options after fixture readiness; expected types and declared groups match. | AUT-01 inspection/mapping coverage |
| AUTO-08 | Duplicate/missing/changed field resolves to ambiguous/missing/changed, never first-match success. | AUT-01 |
| AUTO-09 | Altered fingerprint/version is detected; no stale map silently reused. | JOB-02; mapping snapshot boundary |
| AUTO-10 | Unregistered URL/fixture rejected; controlled local fixture exception cannot access another local/private service. | SEC-03 consumed boundary, SEC-08 inspection scope only |
| AUTO-11 | Inspector produces zero answer writes, uploads, clicks, navigation beyond its fixture and submit/sign calls; prohibited action path denies. | SEC-09; no prefill capability |
| AUTO-12 | Missing browser/timeout/unsupported widget yields truthful unavailable/partial result; browser closes on failure/cancel. | JOB-03 consumed budget/cleanup boundary |
| AUTO-13 | Production configuration cannot serve fixture identity/inspection mode; cross-org source reads denied. | SEC-01, SEC-13 |
| AUTO-14 | One B1 saved HTML record passes through importer without refetch or lost lineage; modified bytes fail integrity. | SRC-02, SRC-08; B1-B2 seam |
| AUTO-15 | Unsupported prose/PDF/markdown remains preserved but not falsely parsed as a complete question set. | SRC-05, SRC-09; partial coverage |
| AUTO-16 | API/UI show imported definition, findings, unknowns and fixture mode; JSON export is not labelled approved. | Feature acceptance |

AUT-02 and AUT-03 remain future approved-entry/read-back work; baseline browser-smoke is not their completion evidence. AUT-04's enforcement and full SEC-08 action authorization remain future scope. Record AUT-01's actual tested subset, source/permission boundary coverage and limitations. No catalog-wide status update. Put per-case commands/results and fixture evidence in a task-specific check-evidence note.

## 10. Completion, commits and handoff

Done means a supported imported definition and a real inspected representative form are visible through the actual UI/API; field-map failure/conflict cases are reliable; exported typed data can be consumed by C; and original/capture lineage is retained. The full B1/C production-adapter integration is a named later gate if unavailable, not an invented success.

Run actual check/smoke/browser commands, fix regressions and record omissions. Commit only this feature's coherent changes with engineering/task/rule citations. No remote is reported: prepare a local branch and review-ready PR body; do not invent a GitHub PR or merge to main. Coordinate shared contract/generated files through the launch agreement; after B1 integrates, rebase safely and regenerate combined types.

Produce docs/handoffs/dev-b/b2-auto-001-r1.md containing full base/head commits, actual paths and commands, screenshots only of the controlled fixture if useful, imported/export examples, map fingerprint algorithm, supported parser patterns, source availability, implemented/partial/planned rule coverage, no-write browser evidence, deviations, B1 adapter mapping and the exact C/B2-AUTO-002 dependencies. Do not write another developer's acknowledgment on their behalf.

Stop after this ticket. The next spec will use the actual intake/map implementation and C approval availability to define approved prefill, read-back, attachments and stale-action handling.

## 11. Official implementation references

- R01: Playwright Python locators and enumeration behaviour: https://playwright.dev/python/docs/api/class-locator
- R02: Playwright Python network interception: https://playwright.dev/python/docs/network
- R03: HTML form-control/maxlength semantics: https://html.spec.whatwg.org/multipage/form-control-infrastructure.html

References inform API/DOM handling; the fixture schemas, scope limits and acceptance tests are project requirements. Preserve the actual observed DOM attributes and unresolved funder conventions rather than assuming a general-purpose parser establishes them.
