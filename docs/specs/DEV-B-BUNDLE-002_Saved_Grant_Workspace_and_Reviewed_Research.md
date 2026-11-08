# DEV-B-BUNDLE-002: Saved grant workspace and reviewed research

**Revision:** 1.0 · **Owner:** Dev B, one agent · **Prepared:** November 8, 2026, America/Toronto

**Repository:** `thegeekyqazi/Start_Strong_Agent`  
**Inspected main:** `2adcdeb0d8a3059caf0d8734bff054403a5c7ffb`  
**Suggested branch:** `dev-b/dev-b-bundle-002`  
**Commit this spec as:** `docs/specs/DEV-B-BUNDLE-002_Saved_Grant_Workspace_and_Reviewed_Research.md`

**Engineering baseline:** `docs/engineering/StrongStart_Engineering_Plan.md` v1.1, sections 3–7, 9, 10.1, 10.3–10.5, 12.4, 13.2–13.3, 14–16, 18–20 and 22. In particular: 20.3 public producer interfaces, 20.6 rule ownership and 20.7 integration gates.

## 1. Outcome, authorization and supersession

Deliver a coherent saved grant workspace: staff can find and reopen captured sources, preserve imported application questions as immutable versions, review evidence-linked funding requirements, evaluate explicitly encoded deadline/eligibility rules, and rerun public searches or selected source captures with visible change observations. Dev C receives a stable server-side question reader, so its application editor can stop depending exclusively on canned questions.

The owner explicitly requested a **larger bundled spec this time**. This is one planned Dev B work package, implemented sequentially by one agent with milestone commits. It does not authorize parallel Dev B agents, unrelated rewrites, direct merges, relaxed source checks or work in another lane's feature internals.

This document **supersedes the unimplemented standalone B2-AUTO-001A spec revision 1.0** as the implementation assignment. Its saved-definition/read-port requirements are integrated here. Do not implement both documents separately. If the earlier spec has already produced local changes, inspect and preserve them, map them into M1 and record the starting state; do not reset or duplicate them.

Existing task series retain their meaning:

| Existing task | Coverage in this bundle |
| --- | --- |
| B2-AUTO-001A | Saved definitions and the public question reader, M1; later capture-context integration in M3. |
| B1-DISC-002 | Bounded first implementation: reviewed funding contexts, finite requirement rules, deadline/eligibility evaluations, saved profiles and manual change observations, M3–M5. Durable recurring scheduling remains deferred. |
| B1-OPS-* | Only the capture library and directly relevant storage/fixture portability fixes here. Deployment and release hardening remain separate. |
| B2-AUTO-002 | **Not started by this bundle:** approved prefill/read-back still needs C3's real resolver and action gates. |

Saving or reviewing an interpretation never submits to a funder, verifies an organizational fact, approves an answer or grants browser permissions. Staff remain responsible for those separate decisions.

## 2. GitHub changes verified for this revision

| Item | Actual state at the inspected main |
| --- | --- |
| B1/B2 first slices and B consolidation | Merged. B exports remain nonpersistent and lack a server-side read port. |
| A1 and A2a | Merged. Source/fact reads, local artifacts and text ingestion exist. |
| **A2b/A2c, PR #8** | **Now merged.** Text-PDF ingestion, page/coverage provenance, organization-scoped lexical retrieval, and Knowledge UI are available. |
| Migration head | `0004_pdf_extraction_coverage` in the inspected tree. |
| C1/C2 | Merged. C's workspace still reads `demo-bundle@1`; the question read-port request remains open work. |
| **C0 lane plan, PR #9** | **Now merged.** Contains historical status statements; its PR explains newer state. |
| C3 | No merged approval implementation or published resolver found on main. The C0 PR describes local work in progress; that is not a released dependency. |
| Main CI | Run `42456450038`, all five jobs successful: Python, web, contracts, database smoke and browser readiness. |

A2 does **not** replace B's capture store, expose a shared capture-to-knowledge import port, create reviewed facts from every imported passage, provide a validation runner, or make local filesystem storage production-ready. Do not infer any of those from the merged PDF/retrieval routes.

The spec author inspected GitHub code and handoffs. No implementation or live provider/model verification was performed while writing this document.

## 3. Start and execution order

Work in the existing `strongstart-dev-b` worktree. Read `AGENTS.md`, decision `0004-dev-b-single-agent.md`, current ownership/coordination documents, the engineering sections above, the relevant catalog entries, and these handoffs:

- B1-DISC-001 and B2-AUTO-001 r1/r2, plus the consolidated Dev B handoff.
- `docs/handoffs/dev-c/c2-question-read-port-request.md` and `c2-plan-and-draft.md`.
- `docs/handoffs/dev-a/a2a-know-002-ingestion-r1.md`, which now documents the full A2 increment.
- A2a/b/c specs and parser-boundary decision; C2's seam/implementation sections; the current C lane plan.

Inspect actual Git status, upstream, applicable directory instructions, models, settings, API/UI and test commands. Preserve local changes and existing `.env` values. Start a task branch from current agreed `origin/main`; record the real starting SHA if upstream advanced. Never work directly on shared main or revive concurrent B1/B2 sessions.

| Milestone | Deliverable | Dependency and completion evidence |
| --- | --- | --- |
| **M0** | Baseline, spec commit, architecture/contract decisions and bounded fixtures | Current upstream and existing tests understood; no fabricated implemented status. |
| **M1 — first** | Versioned saved definitions and public question read port | Existing B2 importer; prove real persistence and publish a C handoff immediately at this checkpoint. |
| **M2** | Saved capture library and reliable reopen/copy/import flow | Existing B1 capture records; M1 reference format. |
| **M3** | Evidence-anchored funding cases/requirements and capture-to-application context | M2 sources, M1 publications; only reviewed finite interpretations become executable requirements. |
| **M4** | Deterministic deadline/project-window and eligibility evaluations | Exact M3 versions and typed inputs; missing facts remain unknown. |
| **M5** | Saved public profiles, staff-triggered reruns and change observations | Existing search/capture operations; M2/M3 version references. |
| **M6** | Joined B workflow, regression/browser evidence and durable consumer handoffs | M1–M5; C runtime integration is proved separately when C2b consumes the reader. |

Default to one task branch and an early draft PR with coherent milestone commits. Do not keep the read-port contract private until the rest of the bundle is complete: publish its exact import paths and sample at M1. If C needs the producer merged sooner, split a clean **producer-only PR** at M1, explicitly identify the remaining bundle PR/base, and continue sequentially. Splitting review is allowed; running two active Dev B implementations is not. No agent merges its own PR without the owner's existing merge authorization.

This bundle's extra scope does not justify blocking all work on a missing A/C dependency. Implement the contracted B paths, mark a missing integration unavailable, and continue independent milestones. Do not fabricate C3, A3, JobStore or a production store.

## 4. Architecture, ownership and shared invariants

Keep funding and automation as separate modules, with B-owned typed public contracts and explicit adapters between them. Use one reusable low-level local storage helper if useful; do not merge business logic into a single feature service.

| Interface | Producer | Consumer |
| --- | --- | --- |
| Existing `CapturedDocumentReader` | Funding | Automation, capture library, evidence-anchor validation |
| New `CaptureCatalogReader` or compatible public extension | Funding | Funding UI and explicit source selection |
| New `ApplicationDefinitionReader` | Automation | C2b and automation reopen UI |
| New `FundingCaseReader` | Funding | Automation publication/context selection; future C requirement consumer |
| Existing `EvidenceProvider` | A | Optional evidence-backed rule inputs when a real authorized implementation exists; otherwise unavailable |
| Existing `ApprovedAnswerResolver` | C | Future B2-AUTO-002; not implemented here |

Expose protocols/models/exceptions in B-owned contracts modules and documented composition factories. Consumers may import those supported entry points, never another feature's private parsers, database tables or functions. No HTTP loopback route calls inside the API process. Publish interfaces before depending on them.

Global invariants:

1. Identity and organization come from the server. Every lookup, list, source read and write enforces that scope; missing and other-org objects fail identically.
2. Exact input bytes, source/version IDs, representation type, hashes, parser versions, locators, warnings, scope and simulated labels survive every handoff.
3. Search ranking, schema validity, source citations, staff review and deterministic predicate execution are separate signals. None alone establishes truth.
4. Original inputs and committed versions are immutable. Changes create versions; expected-version checks protect writes. Historical successful checks are not relabelled current after dependencies change.
5. Models do not decide identity, permissions, rule activation, pass/fail, verification, approvals or actions. This bundle requires **zero new model calls**.
6. UI explanations say what was checked, what source/input was used, what remains unknown and what staff can do next. No hidden model reasoning is needed or stored.
7. Use the existing request-bound pattern for these bounded operations. Scheduling, workers and durable jobs remain unavailable until an actual JobStore exists.

### 4.1 Persistence decision

Use swappable, bounded **local/test repository adapters** for this bundle's new B metadata. They persist across API restarts but are disabled in production. Keep A-owned migrations and TigerData untouched; C3 is also coordinating its upcoming migration sequence with A.

Do not create SQLite, ad hoc new tables, an unreviewed migration head, or a dependency on A's private knowledge artifact class. A2's source artifact storage has a different lifecycle from funding-case/application state. A later shared repository adapter can replace the local implementation through the ports without rewriting feature logic.

Document this choice and supported filesystem/platform assumptions in a task decision. It is authorized implementation scope, not a reason to stop and ask the owner again. If upstream now supplies a compatible public repository, prefer it after proving compatibility and recording the change; do not quietly replace the contract.

## 5. M1: Save application definitions and expose the reader

### 5.1 Save command and immutable data

Add explicit staff save/reopen behavior to the Automation page. Existing intake and `export-definition` remain previews/exports with their current `persisted: false` literals. Add a new saved envelope; never change those existing literal meanings.

`POST /api/automation/definitions` accepts a **strict** request with:

- Existing `IntakeSource`, exact preview input SHA-256 and an organization-scoped idempotency key.
- Optional stored definition ID plus expected current version as a pair for a revision.
- Optional exact funding-case ID/version for the M3 context integration.

It does not trust a client-built QuestionSet, export payload, actor, organization, path, verification flag or approval/provenance labels. The source's original JSON remains untrusted input, even when it names sources or calls itself official.

The server re-runs the bounded B2 intake on the exact source, obtains the actual parsed bytes, compares them with the preview hash and builds the saved record. A changed input returns 409 with no commit. Capture sources use stored bytes through the real capture reader; no network request or browser launch occurs during save/read.

Reject no-question/unsupported imports. Until M3 supplies a valid context, a missing shared QuestionSet/ApplicationDefinition projection also prevents publication. Do not invent an opportunity/funder/cycle to satisfy a required schema field. With M3, a version-pinned authorized funding context supplies only its known, explicit identity; all unknown factual fields remain unknown. Source content and the selected context must not silently contradict each other.

Required saved envelope, for example `PublishedApplicationVersion` in a new B-owned `application_publication.py`:

| Field group | Required semantics |
| --- | --- |
| Identity | Format `b2-published-definition/1`, stored definition ID/version, immutable question-set ID, actor/time. |
| Integrity | Raw input hash/size, canonical normalized-record digest and named algorithm. |
| Content | Published shared QuestionSet/ApplicationDefinition, original rich intake, original-to-published ID mapping, unresolved items. |
| Context | Optional exact funding-case/version/hash; original client-declared IDs preserved as claims, not authority. |
| Provenance | Original source labels, parser/normalization metadata, coverage, fixture indicator and warnings. |
| Workflow | Always `approval_status=not_approved`, `prefill_permitted=false`; saved does not mean reviewed. |

Keep rich instructions, choices, scope, native browser limits, candidate limits, conditions and attachments. The common Question projection is not lossless. Store the original intake separately from published normalized IDs. Do not attach an existing FormMap whose IDs/fingerprint describe a different question set; inspection stays separate until correctly version-bound prefill work.

### 5.2 IDs, revisions, retry behavior

- Server-created definition identity is independent of titles and source-declared IDs.
- Each saved revision gets a unique question-set ID. Published question IDs are namespaced by stored definition so identical `rp-*` IDs in unrelated applications cannot collide.
- Within one lineage, retain published IDs for matching unique original question IDs. Set each question version to the definition revision, conservatively advancing all question versions when the definition changes. Preserve exact original numbering/order and source predicates.
- Added/removed questions and ID mappings are explicit. Do not guess identity from text similarity, array position or a model. Ambiguous/duplicate identities fail.
- Revision writes atomically compare expected current version. One of two concurrent writers can commit; the other receives 409. A stale write never replaces another staff member's version.
- Same idempotency key plus the same command returns the committed IDs/version, including after a lost response. Same key plus different source/context/lineage is 409. Check completed replay before rejecting its old expected version.
- Reads by question-set ID return that exact version, not a substituted latest version. A separate current-version read supports C3's later checks.

### 5.3 Public reader

Publish supported models, typed errors, an unconfigured implementation and a public factory for wiring:

```python
class ApplicationDefinitionReader(Protocol):
    is_fixture: bool

    def get_version(
        self, organization_id: str, question_set_id: str
    ) -> PublishedApplicationVersion: ...

    def get_current(
        self, organization_id: str, definition_id: str
    ) -> PublishedApplicationVersion: ...
```

One envelope gives C both shared questions and rich unresolved requirements consistently. Optional convenience methods must delegate to the same immutable version. Adapter `is_fixture` does not replace record/source provenance: a real local repository can hold simulated records.

C2b owns its workspace selector and consumer adapter. Do not edit C's Applications feature to claim the seam is complete. Supply C a minimal public-port example and real-producer contract tests. The B+C gate closes only after C's actual editor/check/draft path reads this data; full G1 also requires A evidence integration.

### 5.4 UI and routes

| Route | Meaning |
| --- | --- |
| POST `/api/automation/definitions` | 201 first save; 200 identical replay. |
| GET `/api/automation/definitions` | Bounded authorized summary list, with cursor/more indicator. |
| GET `/api/automation/definitions/{id}` | Current saved version. |
| GET `/api/automation/question-sets/{id}` | Exact immutable version. |

Show **Save definition for drafting**, saved ID/version/hash/time, unresolved counts and a reloadable **Saved definitions** list. Explicitly select a lineage for revision; never match by title. Preserve previews and unsaved staff input on errors. A changed source invalidates the preview/save intent. Until C2b ships, say **Saved; connection to Applications pending**, rather than linking to C's fixture editor as if it contained these questions.

## 6. M2: Capture library and portability fixes

Staff must be able to find a completed capture after navigation or reload. Add a Funding-page **Saved captures** section with bounded list, open-by-ID and source detail. Expose an authorized capture catalog route/public port; extend contracts additively. Keep the existing capture-by-ID/content endpoints compatible.

Each summary shows capture ID, title/URL, capture time, provider/mode, coverage, representation count and review label. Opening loads the existing record and hash-verified artifact content. Preserve the distinction between provider-rendered HTML/markdown and original origin-server bytes; Firecrawl `rawHtml` is not automatically the latter.

Provide both:

- The existing complete capture-reference JSON download.
- **Copy intake reference** for a selected importable artifact, returning the exact `capture_id:artifact_id` string B2 expects. Label it separately from full JSON copy.

Offer **Use in application intake** within B-owned UI. Pass IDs only, resolve/authorize server-side and preserve the selected representation. If no supported form controls are present, show context-only/unsupported status; never invent questions from a prose grant page. A capture with missing funding context can be linked through M3 before saving its questions.

Listing is bounded and has a stable pagination contract, scan limits and an explicit incomplete/truncated state. Do not load every blob or traverse an unlimited directory tree to populate one response. If a catalog/index is needed, update it atomically on new captures and support a bounded backfill for pre-existing captures. Do not silently hide all older work, or claim backfill is complete after reaching its cap.

Corrupt/missing records must produce safe findings rather than crash the entire list or expose unverified source text. Verify artifact content before displaying it or deriving a requirement. Metadata-only summaries must state when content integrity has not yet been checked.

Fix the known directly relevant portability defects:

- Hash-sensitive fixture bytes must survive checkout. Add targeted `.gitattributes` rules for registered raw/markdown/HTML artifacts; use byte reads and do not normalize saved source newlines. Do not simply recompute expected hashes to match a transformed checkout.
- Directory fsync currently uses a Unix-specific path in B's store. Implement tested platform-specific durability behavior or explicitly reject unsupported storage/platform combinations before success. Do not silently skip a critical protection or claim equal crash durability without evidence.
- Preserve immutable-create semantics under concurrent captures; an existence check followed by overwrite-capable rename is not by itself a no-clobber guarantee. Fix relevant write paths and test two writers. Avoid an unrelated storage rewrite.

## 7. M3: Reviewed funding contexts and evidence-bound requirements

### 7.1 Funding case lifecycle

Introduce B-owned `FundingCase` / `FundingCaseVersion` models and a `FundingCaseReader`. A case groups a staff-selected funding opportunity context; it is not an AI-certified funding opportunity. Start as **draft/unreviewed**, create immutable revisions and record explicit staff review decisions with server actor/time and exact input hashes.

| Context | Treatment |
| --- | --- |
| Funder, stream, cycle and stage labels | Entered/selected by staff; source-linked when known; unknown stays explicit. Do not treat a search title/date as reviewed identity. |
| Internal IDs | Server-generated stable IDs for real records; not titles and not fabricated evidence about a funding year. |
| Capture links | Authorized capture/artifact/version IDs and hashes, with source quality/coverage. |
| Interpretation review | A specific staff decision about an exact requirement version; separate from source authenticity and organizational-fact verification. |
| Shared Opportunity projection | Emit only when mandatory funder/stream/cycle identities are actually established. Otherwise keep a draft case and explain the missing inputs. |
| Shared RequirementSet | Versioned projection of the reviewed finite conditions, keeping unknowns and uncertainty notes. Never publish scenario success as confirmed eligibility. |

Do not create a universal current-cycle flag or current deadline from a provider's published-date estimate. EOI and full-application stages, annual cycles and standard/network streams remain distinct identities.

### 7.2 Evidence anchors and review commands

Every executable requirement needs an evidence anchor to an authorized, immutable stored representation:

- Capture ID, artifact ID, source/version ID and artifact hash.
- Exact quote plus code-point start/end in the stored UTF-8-decoded representation, or an equivalent resolvable source section/locator with an exact quoted passage.
- Parser/representation label and explicit warnings/coverage.

The server resolves the anchor and verifies bytes/hash, locator range and quote before recording the interpretation. It must not accept a citation string as proof or pull a fresh URL. Quote comparison is exact for this slice; preserve any documented display normalization separately. Partial content remains partial; an unavailable omitted section prevents conclusions that require that section.

A staff member may provide a **typed interpretation** of the anchored passage: for example, a per-award range for a named stream or an exact deadline. Store the raw passage and the interpretation/rationale separately. Code establishes that the cited text exists and the input is structurally sound; it does not prove the staff interpretation is semantically correct. UI must make that distinction visible.

Only a separate explicit **Review these requirements** command activates that exact finite interpretation for evaluations. Server identity supplies reviewer/time; no client/model `reviewed=true` Boolean is accepted as an authority shortcut. A later edit, source relink or rule change creates an unreviewed revision and invalidates the current review for the changed snapshot. Retain old review history.

No free-form policy code, expressions, SQL, regex supplied by users/models, arbitrary imports or `eval`. Rule kinds and input fields come from a small server-defined registry, with unknown kinds rejected.

### 7.3 Capture-to-question context integration

After a case has a valid opportunity identity, its exact version can be selected in Automation. Resolve that context through the public reader and bind it into the new saved definition, retaining capture/source lineage. This removes the previous unknown-opportunity projection blocker for legitimate captured HTML forms.

Do not mutate the original `CapturedDocument` or make a new capture appear reviewed. Store the linkage in a versioned wrapper. Compare source-declared context with selected context; a disagreement is held for review, not overwritten. For a changed current case during a save, fail 409 rather than bind to a different version than staff selected. Coordinate local atomicity/version checks through supported B composition; no private cross-module repository calls.

Capture input without an established opportunity identity still cannot be promoted into a shared QuestionSet by inventing a cycle. It can be saved as evidence/context, and a staff-labelled structured definition remains a supported alternative.

### 7.4 Public contract and routes

Suggested B-owned `funding_review.py` contracts: `FundingCaseVersion`, `RequirementDraft`, `EvidenceAnchor`, `RequirementReviewCommand`, `DeadlineSpec`, finite predicate union, `RequirementEvaluation` and `FundingCaseSummary`.

The reader must support authorized exact-version and current-version reads, returning requirements, unresolved items, context, hashes and review metadata in one consistent envelope. Expose an unconfigured implementation. Add API commands for create, explicit revision/review, bounded list, current/exact read and evaluation under `/api/funding/cases`. Use existing API naming conventions; document final schemas and route names before consumers rely on them.

Shared `Opportunity`, `RequirementSet`, `QuestionSet` and `DateKnowledge` stay compatible. New wrappers hold richer information. A known deadline date in `DateKnowledge` must not imply its time/zone is known; C consumers need the richer deadline envelope when evaluating cutoffs.

## 8. M4: Deterministic deadline and eligibility checks

### 8.1 Reproducible evaluation records

Each report records exact case/rule/source versions and hashes; typed input values and their provenance; evaluation clock; evaluator/rule version; result; plain-language explanation; missing/conflicting inputs; and what the staff member should do next. Hash the canonical inputs for reproducibility. Do not log private values in generic errors or send them to search providers.

Use explicit outcomes such as `met`, `not_met`, `unknown`, `not_applicable`; distinguish rule outcome from source/input quality. There is no generic **eligible** green badge or probability score. At most say **These encoded rules are met using these inputs; funder eligibility is not confirmed**. A missing/unreviewed rule or missing required input never becomes a pass.

Use the shared `ValidationResult` shape where applicable, wrapped with plain-language fields like C's presentational findings. A3's shared runner is not present: keep pure B rule functions behind an adapter now and register them when A publishes the runner. Do not create a competing shared engine or rename C-owned APP rules.

### 8.2 Date/time rules — DAT-01 to DAT-04

`DeadlineSpec` retains original wording, date, optional local time, optional IANA zone/explicit offset, cycle/stream/stage, precision, cutoff-boundary interpretation and its review/source anchors. Unknown components are nullable/typed unknown, not guessed.

- Exact deadlines compare an injected aware evaluation clock with the reviewed instant. Test before, at and after the boundary. Whether the exact boundary is inclusive is an explicit reviewed convention; if unstated, report `at_cutoff/needs_review` at that instant rather than guessing.
- Date-only deadlines remain date-only. Do not fabricate 23:59, noon or the server's timezone. Show a calendar-date observation when defensible; exact-time readiness stays unknown. Rolling opportunities remain rolling, not assigned a made-up date.
- IANA-zone DST rules must handle ambiguous fall-back and nonexistent spring-forward times. Missing disambiguation stays unknown; never silently choose fold zero or normalize an impossible local time. Validate an explicit offset against its zone when both are supplied.
- A search provider's date estimate, capture time, last-modified hint or application period is not automatically a submission deadline.
- Select and evaluate only the exact funder/stream/cycle/stage in the report. An EOI deadline cannot validate a full application. Historical closed-cycle captures cannot stand in for the current round.
- Project start/end checks run only against explicitly reviewed funding-window constraints, using typed dates and a declared inclusive/exclusive convention. Inverted ranges fail; missing dates or unclear funding windows stay unknown.
- A report is time-stamped evidence, not a permanently current pass. Re-evaluate time at the next explicit action/check. No background timer, approval or prefill gate is implied here.

DAT-05 claim-time suitability remains a separate A/C-dependent integration. Do not claim that this bundle fixes every historical figure appearing current in prose.

### 8.3 Finite eligibility predicates — ELG-01 to ELG-04

Support a small typed registry, initially:

| Predicate | Inputs and strict behavior |
| --- | --- |
| Request amount range | Exact Decimal strings; explicit currency, unit, range boundaries, award-limit kind, stream/application type. No float conversion, inferred FX or comparison against a whole funding pool. |
| Geography membership | Explicit reviewed region identifiers and exact membership; no substring/geocoding guess. Unknown mapping stays unknown. |
| Organization type | Reviewed finite set versus typed selected type; absent status does not default to charity. |
| Eligible activity | Explicit allowlist and declared any/all semantics, not keyword similarity or embeddings. |
| Invitation/prior-stage requirement | Applicable Boolean/status plus source-backed evidence when required; Apply-button presence is not an invitation. Missing invitation/history returns unknown. |

Use flat bounded rules or a fixed, bounded all-of grouping, not an arbitrary expression language. For a required all-of group, all met is met; any known not-met is not-met; otherwise any unknown makes the group unknown. Not-applicable is allowed only with a reviewed applicability condition, never as a substitute for absent data.

**Input provenance matters:** this bundle may accept typed per-evaluation staff scenario inputs to exercise the rules, but they are not a new organizational knowledge base and do not write facts into A's store. Record them as `staff_asserted` or `simulated`. Show scenario outcomes separately from reliance readiness. Unverified staff values cannot turn the shared authoritative RequirementSet evaluation into a confirmed pass; keep it unknown pending adequate evidence. A test harness may use explicitly simulated evidence-confirmed fixtures, keeping the simulation label.

When a real A `EvidenceProvider` is available, consume only authorized typed facts through that public port, retaining metric/unit/scope/period/version and verification status. Do not infer a metric mapping or promote arbitrary retrieved prose to verified facts. Until that interface/mapping is available, evidence-backed inputs remain missing/unknown; scenario evaluation still works honestly.

Preserve separate standard and network maximums. A 250,000 network maximum cannot validate a standard 120,000 request against a 100,000 cap. A total fund pool or matching ratio is not a per-award cap. Currency/scale/scope mismatch is a finding, never a hidden conversion.

### 8.4 Plain-language output

Each finding must answer four things with concrete data:

1. What code compared: e.g. the standard-stream request against its reviewed per-award range.
2. What source/input it used: exact saved version, excerpt and value with provenance.
3. What it found: e.g. request 120,000 exceeds maximum 100,000 by 20,000, calculated with Decimal.
4. What remains uncertain/next action: e.g. request is a staff scenario; confirm the actual project budget and currency.

Keep explanations deterministic templates over checked data. Do not ask another model to invent a rationale or treat agent agreement as evidence.

## 9. M5: Saved public searches and explicit change observations

### 9.1 Saved profiles and run history

Persist only the existing bounded public `SearchProfile` fields plus an inert user label, server-generated ID/version and timestamps. Internal facts, private program documents, scenario inputs and saved case evidence do not automatically flow into search terms. The UI previews exactly the public query before a run.

Add create/revise/list/read profile commands and **Run search now**. Each staff-triggered run uses the existing authorized B1 search provider once, with existing size/time/result limits and no automatic retries. Save the exact profile version, query/provider metadata, result/omission/duplicate information and outcome. Failed or unavailable runs remain failed/unavailable; do not fill them with fixture results or hide the failure in history.

Allow comparison of successful runs of the same profile version using normalized URLs. Report **newly seen**, **seen again** and **not seen in this result set**. A missing result is not a removed opportunity or closed grant; a result set is bounded/provider-ranked. Different profile versions are not automatically comparable.

No cron, recurring task, email, calendar entry, notifications to others or durable job is created in this bundle. Scheduled monitoring remains unavailable pending JobStore and a separate authorized scheduling task.

### 9.2 Staff-selected source recheck

Provide **Capture again and compare** for one explicitly selected saved public source. This is a new authorized capture operation with the existing destination policy and exactly one provider request. It never overwrites the old capture or automatically opens other URLs.

Compare like representations and recorded extraction options. Hash equality means the stored representation bytes match; hash difference means the representation changed. It does not by itself establish that funder policy changed, that the origin page is malicious, or that extraction is complete. Different provider options or missing representations are **not comparable**, rather than a false semantic diff.

Save a versioned `ChangeObservation` referencing old/new capture IDs, compared artifact hashes/representation/options, time, outcome and explanation. A bounded textual diff may assist staff but is not authoritative semantic interpretation.

Where that recheck is explicitly linked to a funding case, changed/partial/failed content makes its current source review **requires re-review** and prevents current rule readiness until staff resolves it. Retain old evaluations as historical, visibly stale relative to the new observation. Do not automatically replace rules or declare newly captured terms accepted.

This is local B dependency handling. It does not implement A4's pack-change graph or C3's invalidation across answers/approvals. Expose version/hash/change references so those consumers can integrate later, and report the missing downstream behavior honestly.

## 10. Storage, concurrency, budgets and API failures

All new B repositories must provide:

- Organization-derived namespaces, strict ID validation and path confinement, including symlinks. No user/model-controlled filesystem paths.
- Exact byte storage and versioned canonical JSON hashing. Preserve Unicode and newlines; reject NaN, duplicate keys and coercion in new strict commands. A hash is an integrity identity, not a signature or proof of authenticity.
- Verify input and normalized records before disclosing dependent content. Validate ID/parent/source relationships and mappings; a rewritten limit must not bypass integrity checks.
- Atomic immutable writes with genuine cross-process coordination, bounded lock waits, current-version compare-and-swap and idempotency replay. A process-local lock is insufficient.
- No success before a consistent commit; no half-written version/index visible. Test injected write failures and crash leftovers. A safe unavailable response is preferable to guessed success.
- Saved versions read their own preserved bytes/metadata, without refetch or reinterpretation by the latest parser. They do not depend on B1 temporary blobs staying forever. Preserve lineage, and separately enforce any later source-revocation policy.
- Production uses unconfigured adapters; unavailable stores never silently fall back to fixtures or memory.

Explicit project budgets, adjustable only through documented compatible settings:

| Resource | Initial bound |
| --- | --- |
| Publication request | At most 2 MiB, and the tighter existing per-mode input limit still applies. |
| Application questions / canonical saved envelope | 100 / 4 MiB. |
| Case predicates / source anchors | 20 / 40 per case version. |
| Version history | 20 per definition/case/profile; reaching the cap returns a clear limit error, no destructive pruning. |
| List page | Default 20, maximum 100 summaries; stable cursor and explicit more/incomplete status; no unbounded filesystem or blob scan. |
| Source excerpt / explanation | Bounded; do not silently truncate decisive source support. Too-large support must be selected more narrowly or held. |
| Profile/provider operation | Existing five-result maximum, one request, no automatic retry; existing time/byte caps. |

Retain the existing `ErrorEnvelope`, with typed reasons in `details.reason`. Authentication is 401; unknown/other-org object is the same 404; malformed/coerced/extra-field input is 422; stale versions/input/hash expectations or key reuse are 409; size/history budgets are 413; unavailable stores/adapters are 503. Integrity failures use a documented 409 or existing integrity convention with all dependent content withheld. Do not leak source snippets, keys, raw exceptions or filesystem paths in errors.

Check identity before parsing source bodies, touching stores or calling providers; malformed path IDs must not cause filesystem access. Add truthful capability entries for saved definitions, capture catalog, reviewed requirements, evaluations and manual reruns. Existing search candidates stay unassessed, regardless of a separate case evaluation. Existing routes and C2 fixture behavior remain compatible.

## 11. Deterministic acceptance matrix

These **54 task-local cases** cover named predicates and integration boundaries. They are not 54 new catalog rules and do not establish that all 86 catalog rules are complete. Keep the catalog's global statuses unchanged unless a separate agreed evidence update justifies a specific status. Record implemented/tested subsets and omissions in the handoff.

| ID | Required case and result | Main mapping |
| --- | --- | --- |
| BND-01 | Missing identity prevents source/store/provider access on every new route. | SEC-01 subset |
| BND-02 | Unknown/other-org IDs give identical read/update failures; lists do not leak other tenants. | SEC-01/13 subsets |
| BND-03 | Strict versions reject strings, floats and bools; forbidden org/approval/path/provenance extras rejected. | SEC-14 command boundary |
| BND-04 | Traversal, encoded paths, malicious names and symlink escapes fail before outside I/O. | SEC-01/13 subsets |
| BND-05 | Bounds tested at N/N+1; huge/deep/duplicate-key JSON rejected without crash or partial commit. | SEC-04 bounded parsing subset |
| BND-06 | Fixture nine-question definition saves and reloads in original order with exact wording/locators. | SRC-01/03/10 subsets |
| BND-07 | 350/500 conflict, Max 300 unit unknown, required null, condition, separate stream amounts and file constraints survive. | APP-01/02 producer compatibility |
| BND-08 | Changed preview input hash returns 409 with no committed side effects. | SRC-02 / version boundary |
| BND-09 | Restart/fresh repository reads same saved IDs/hashes; not an in-memory dictionary. | Persistence |
| BND-10 | Same idempotent command returns original version; different command/key reuse is 409. | Retry boundary |
| BND-11 | Revision preserves old version; IDs are namespaced and stable within lineage; additions/removals explicit. | Snapshot identity |
| BND-12 | Two cross-process writers with one expected version yield one commit and one conflict. | JOB-02 publication subset |
| BND-13 | Alter raw input/normalized limit/index target/hash/mapping: dependent content withheld. | SRC-02 subset |
| BND-14 | Inject mid-commit failure; no partial version visible, retry consistent. | Atomicity |
| BND-15 | Unsupported/no-question imports remain unsupported; missing context is held before M3. | SRC-05/08/09 subsets |
| BND-16 | Public reader supplies real stored questions plus unresolved/rich data; fixture and nonfixture source labels preserved. | Engineering 20.3 |
| BND-17 | Capture list/open works after navigation/restart; old captures bounded-backfilled or explicitly pending. | Capture library |
| BND-18 | Pagination/scan limits and corrupt-entry handling are visible and tenant-safe. | SEC-13 / bounded operation |
| BND-19 | Copy intake reference gives exact colon IDs; full JSON copy remains separate; correct artifact selected. | B1→B2 seam |
| BND-20 | Captured scripts/trackers remain inert in library/intake; no remote loads. | SEC-07 subset |
| BND-21 | Hash-sensitive fixtures survive declared checkout policy; write durability/no-clobber tested on supported platforms. | SRC-02/06 storage subset |
| BND-22 | Create draft funding case with missing context: unknowns remain, no fabricated Opportunity projection. | DAT-03 / ELG-01 boundary |
| BND-23 | Valid exact evidence quote resolves; wrong quote/digit/range/hash/cross-org source fails. | SRC-01/02/03 subsets |
| BND-24 | Typed requirement stays inactive until explicit version-bound review; client/model review Boolean cannot activate it. | SEC-14 boundary |
| BND-25 | Requirement edit/source relink stales current interpretation review; old history remains. | Version/dependency boundary |
| BND-26 | Reviewed context enables stored HTML-form QuestionSet; source and selected context mismatch is held. | B1→B2 publication seam |
| BND-27 | Reopen saved publication after original producer blob removed uses its own verified bytes and retains lineage. | Immutable input |
| BND-28 | Exact deadline before/at/after reviewed boundary uses aware clock and declared inclusive/exclusive policy. | DAT-01/02 |
| BND-29 | Date-only, missing time/zone and rolling cutoff never become fabricated exact timestamps. | DAT-01/02 |
| BND-30 | Ambiguous/nonexistent DST local times and inconsistent zone/offset are unknown/rejected, not silently normalized. | DAT-02 |
| BND-31 | EOI/full application, old/new cycle and standard/network scopes cannot substitute for each other. | DAT-03 |
| BND-32 | Project window endpoints, inverted range, outside window and missing dates tested under declared convention. | DAT-04 |
| BND-33 | Missing history/invitation/geography/type/request input yields unknown, not a pass. | ELG-01/04 |
| BND-34 | Exact Decimal amount N−1/N/N+1; currency/scale mismatch; pool-vs-award mismatch. | ELG-02/03 |
| BND-35 | Standard request cannot borrow network maximum; funding pool/matching requirement cannot become award cap. | ELG-03 |
| BND-36 | Geography/type/activity registry executes exact reviewed membership and explicit any/all semantics. | ELG-02 |
| BND-37 | Apply button does not prove invitation; missing prior-stage evidence stays unknown. | ELG-04 |
| BND-38 | All-of results distinguish fail/unknown/not-applicable without default eligibility. | ELG-01 |
| BND-39 | Staff scenario can show a computed outcome but cannot create a confirmed RequirementSet pass or verified A fact. | Evidence/decision boundary |
| BND-40 | Evaluation records reproduce result from exact versions/clock/inputs; explanations show concrete support and uncertainty. | APP-08 input contract subset |
| BND-41 | Saved profile contains public allowlisted fields only; no auto-read of private KB/scenario data for query. | SEC-02 routing boundary |
| BND-42 | Search rerun calls one provider, retains limits/errors; missing keys never fall back to fake results. | JOB-03 / existing search boundary |
| BND-43 | Same-profile comparisons use normalized URLs; unseen result is not labelled closed/removed grant. | Search interpretation |
| BND-44 | Different profile versions are not silently compared; failed runs stay failures. | Snapshot/availability |
| BND-45 | Explicit single-source recheck creates new capture, leaves old bytes unchanged and obeys existing URL policy. | SEC-03 / SRC-02 |
| BND-46 | Equal/different/missing/different-options representations produce match/change/not-comparable observations correctly. | SRC-06/07 subset |
| BND-47 | Changed/partial/failed source recheck linked to case requires re-review; historical evaluation visibly stale. | Local requirement invalidation |
| BND-48 | Change observation does not rewrite rules, approve answers or claim A4/C3 invalidation. | Ownership/authority boundary |
| BND-49 | Production/unconfigured repositories unavailable, no fixture/memory/local fallback. | Capability boundary |
| BND-50 | Real Chromium: capture → saved library → intake → save/reload/reopen → exact conflict/evidence; zero scripts. | B end-to-end path |
| BND-51 | Real Chromium: case/evidence selection → reviewed finite rule → scenario check → visible support/unknowns. | M3/M4 integration |
| BND-52 | Real Chromium: saved profile rerun and selected capture comparison show history/change labels; no scheduler needed. | M5 integration |
| BND-53 | Existing B1/B2 and C2 fixture paths remain compatible after generation; A2 migration/readiness unchanged. | Regression/contracts |
| BND-54 | Consumer handoff imports only public ports; producer tests run with fixture and actual repository. Actual C editor integration is labelled pending until C proves it. | Engineering 20.3 / G1 |

SRC-07 coverage here is limited to B capture/requirement changes, not a full global dependency graph. APP-08 coverage is reproducible B report inputs, not C's approval records. SEC-03 remains partial because Firecrawl performs fetching; application URL checks do not prove provider egress isolation. SEC-04 remains a bounded local parser boundary, not production sandboxing. AUT-02/03, DAT-05, SEC-08 action grants, SEC-11 release scanning and global JOB guarantees remain outside this bundle.

## 12. Staff UI, manual rehearsal and real-vs-simulated fixtures

Use existing feature pages and shared presentational components where appropriate. Do not redesign C's shell or Applications workspace. Keep separate signals for availability, source coverage, interpretation review, input quality, deterministic findings and workflow approval. Never collapse them into a single green badge.

Check in small clearly synthetic fixtures for each new rule; no copied partner files, credentials or alleged real open grants. Use a frozen clock and exact values, including the existing 350/500, Max 300 and separate 100,000/250,000 examples, explicitly engineering-derived. New scenario data must not appear to be Strong Start's actual budget, registration status, invitation or current impact.

Required manual rehearsal in the handoff:

1. Start current API/web, migrate/seed and select local demo identity.
2. Use fixture providers for reproducible no-cost capture/search; live providers may be exercised separately if the owner's existing opt-in applies. Report live status independently.
3. Capture a page, navigate away/reload, find it in Saved captures, open inert text and copy an importable artifact reference.
4. Import the nine-question structured fixture, save, reload and reopen exact conflict/source evidence. Copy its saved question-set ID for C.
5. Select a form capture and establish a draft funding context; show missing identity fields preventing premature publication, then complete source-linked context and save a versioned definition.
6. Add/review a finite requirement with an exact anchor. Run amount/geography/invitation and deadline scenarios, including a missing input and a DST ambiguity. Explain why a scenario outcome is not confirmed eligibility.
7. Save a public search profile, run twice and compare bounded results without treating absence as closure.
8. Recheck a fixture source with changed/partial content, show the change observation and the funding case's re-review state. Old publication/evaluation remains historical and unchanged.
9. Show C's current fixture editor honestly unless C2b has actually merged and consumed the saved ID. Show approval/prefill still unavailable.

UI failures preserve current input/preview; loading, empty, unavailable, stale and corrupt states are distinct. Tests must include a late save response arriving after the user changes imports, so it cannot relabel a newer preview as saved.

## 13. Shared files, integration and delivery

Expected changes: B-owned funding/automation modules and pages, B-owned contract modules, focused tests, task docs, local repository helpers, narrow settings/capability additions and targeted `.gitattributes`. Regenerate schemas/TypeScript using `make contracts` and preserve A/C registrations. Do not hand-merge generated files.

Do not change C-owned request schemas/workspace selection, A knowledge internals, TigerData or migration sequencing to make this bundle appear integrated. If a public contract change affects a consumer, publish an additive/versioned proposal and a compatibility example. Developer discretion covers names/layout/equivalent libraries and reversible details; record meaningful departures with rationale, affected checks/consumers, validation and rollback.

At M1, publish `docs/handoffs/dev-b/bundle-002-question-reader-r1.md` with exact public imports, factory wiring, version behavior and a sample from the real repository. C2b must preserve rich intake/conflicts and resolve selected IDs using server organization. It must not accept browser-supplied question/provenance payloads or silently fall back to the old fixture on a failed read.

At M3/M4, publish the funding-case/requirement reader and report contract for C/A. C can later bind requirement versions into answer dependencies; A3 can register the pure B predicates. No callback/message from another agent is an authorization bypass.

At completion, provide:

- This spec committed in `docs/specs/` and a task decision on local adapters/version/review semantics.
- Coherent milestone commits, generated contracts and all required source/tests.
- `docs/handoffs/dev-b/dev-b-bundle-002-r1.md`: real base/head/branch/PR; milestone matrix; exact port/API/schema changes; all 54 acceptance results; regressions; omissions/deviations; live-vs-fixture status; platform/storage limits; and manual rehearsal.
- Updated current Dev B plan with delivered subsets and remaining B1-DISC-002/B2-AUTO-002 work, preserving historical notes.
- Reviewable PR(s) using the repository template, citing engineering sections, this spec and applicable predicate coverage. No direct-main writes or self-approved merge.

AGENTS.md permits technical task updates in this assigned repo. If connected/authorized, post the M1 response on C2 PR #7 with the B PR link; otherwise include exact unposted text in the handoff. Do not send unrelated email/Slack or claim a notification happened without a returned record.

## 14. Verification and completion gates

Discover current commands first. At this baseline:

```bash
make contracts
make check
make smoke
make browser-smoke
```

Run focused tests while implementing, then complete checks against the final combined changes. `make smoke` uses the current A migration/seed/readiness path. Do not pin migration 0003 when current head is 0004 or a later reviewed upstream revision. Migrations and A's parser boundaries remain unchanged by this work.

Use isolated temporary stores, actual API wiring and real Chromium for milestone integration. Provider HTTP mocks are appropriate for deterministic response/error cases; they are not live Tavily/Firecrawl evidence. The bundle needs no paid provider/model call to pass its required acceptance.

Retain first failures and investigate them. C previously reported a B browser timeout under load; a later green run does not erase it. Do not merely increase timeouts, recompute fixture hashes or weaken predicates to obtain a pass.

Completion gates:

| Gate | Required claim |
| --- | --- |
| M1 producer ready | Real saved-definition reader works with immutable versions; C2b runtime integration may still be pending. |
| B workflow ready | M2–M5 paths work through B UI/API with correct labels, deterministic reports and exact source/version links. |
| B+C G1 | Claim only after C reads this producer and shows the actual imported questions/limits/conflicts in its editor. |
| Full G1 | Also requires real A evidence in C; A2 passage retrieval alone is not proof of that join. |
| G2 approval/read-back | **Not delivered here.** C3 real approvals/action-time checks and B2-AUTO-002 remain dependencies. |

Do all independent authorized work through M6. If a consumer or infrastructure piece is missing, finish the B producer, prove its boundary and state exactly what remains unavailable. Do not stop at a plan, fabricate a successful seam, or expand into C3/A3 internals.

## 15. Pinned review references

- [Inspected main](https://github.com/thegeekyqazi/Start_Strong_Agent/tree/2adcdeb0d8a3059caf0d8734bff054403a5c7ffb)
- [Successful main CI](https://github.com/thegeekyqazi/Start_Strong_Agent/actions/runs/42456450038)
- [A2b/A2c merged PR #8](https://github.com/thegeekyqazi/Start_Strong_Agent/pull/8)
- [A2 ingestion/retrieval handoff](https://github.com/thegeekyqazi/Start_Strong_Agent/blob/2adcdeb0d8a3059caf0d8734bff054403a5c7ffb/docs/handoffs/dev-a/a2a-know-002-ingestion-r1.md)
- [C0 merged PR #9 and current-state notes](https://github.com/thegeekyqazi/Start_Strong_Agent/pull/9)
- [C2 merged PR #7](https://github.com/thegeekyqazi/Start_Strong_Agent/pull/7)
- [C question-reader request](https://github.com/thegeekyqazi/Start_Strong_Agent/blob/2adcdeb0d8a3059caf0d8734bff054403a5c7ffb/docs/handoffs/dev-c/c2-question-read-port-request.md)
- [Existing B capture reader and contracts](https://github.com/thegeekyqazi/Start_Strong_Agent/blob/2adcdeb0d8a3059caf0d8734bff054403a5c7ffb/packages/contracts/python/src/strongstart_contracts/discovery.py)
- [Current A knowledge routes](https://github.com/thegeekyqazi/Start_Strong_Agent/blob/2adcdeb0d8a3059caf0d8734bff054403a5c7ffb/services/api/src/strongstart_api/features/knowledge/router.py)
- [Engineering baseline](https://github.com/thegeekyqazi/Start_Strong_Agent/blob/2adcdeb0d8a3059caf0d8734bff054403a5c7ffb/docs/engineering/StrongStart_Engineering_Plan.md)

These references establish the inspected starting point. The implementing agent must fetch current upstream and reconcile actual newer public contracts without silently changing the bundle's acceptance boundaries.
