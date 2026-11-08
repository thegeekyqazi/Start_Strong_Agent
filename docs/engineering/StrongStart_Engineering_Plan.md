# Strong Start Engineering Plan

## Implementation blueprint and secure practice-skill generator

**CommuniHacks 2026 | Engineering version 1.1 | November 7, 2026 | America/Toronto**

**Status:** Proposed engineering baseline, revised for three developers working in parallel. Builds on the updated team brief and supplied partner material. This document specifies interfaces, checks, tests and delivery gates; it does not claim the application or security controls have been implemented.

**Main decision:** Build one modular application with a code-controlled workflow, source-linked knowledge, interchangeable model adapters and a deterministic validation engine. Add a constrained generator that proposes reusable skills from approved organizational practices.

### What this plan includes

- Architecture, repository layout, data contracts, API routes, state machines and deployment boundaries.
- All 51 existing checks, retained by ID, with implementation guidance and an acceptance fixture each.
- 35 additional skill, security and reliability checks: 86 total planned checks.
- A skill-generation pipeline, permission model, classifier integration and adversarial test plan.
- Three full-stack feature lanes, dependency contracts, grunt-work owners, continuous integration and final release responsibilities.

### Reading guide

The product scope and permission to use all supplied materials are agreed. Technical choices below are recommendations for the team to adopt or adjust. P0 means a required control for an enabled capability; P1 means hardening or broader coverage. A capability cannot be advertised as complete merely because its P0 rules are listed here. No personal skill is being installed by this plan.

## Contents

1. Engineering objective and release scope
2. Architecture and default stack
3. Repository and module ownership
4. Data model and evidence contracts
5. Ingestion, retrieval and knowledge packs
6. Discovery and research pipeline
7. Application intake and answer planning
8. Drafting, claims and specialist review
9. Deterministic validation engine
10. Existing 51 checks with implementation fixtures
11. Practice-skill generator
12. Threat model and security design
13. Additional 35 engineering checks
14. API and tool contracts
15. Workflow states, concurrency and invalidation
16. Browser automation and exports
17. Model and agent-runtime adapters
18. Staff interface and understandable explanations
19. Testing and evaluation
20. Agile delivery for three developers
21. End-to-end demo and acceptance gates
22. Operations, deployment and observability
23. Immediate decisions and first backlog
24. Sources and interpretation limits

---

## 1. Engineering objective and release scope

Ship one complete path: discover a funder, capture official requirements, import selected application questions, retrieve Strong Start evidence, draft and check an answer, let staff review, transfer approved content into a representative form, and replace the knowledge pack without application-code changes.

The skill generator strengthens the same path. It turns approved practices into reusable instructions and typed policy rules. It must not become a second open-ended agent platform that delays discovery, automation or evidence checking.

| Demo capability | Required proof | Scope limit |
| --- | --- | --- |
| Discovery | Actual public search, official-source capture, fit evidence and eligibility unknowns. | A small useful candidate set; no claim of exhaustive coverage. |
| Application intake | Questions, instructions, word/character limits and source conflicts extracted. | Selected supplied GOS questions and one representative form. |
| Draft and review | Evidence panel, claim bindings, checks, edits and exact-version approval. | A small complete application slice. |
| Automation | Enter approved content and compare the values read back. | One tested form adapter; staff performs final submission. |
| Pack replacement | Change policy and facts; invalidate and regenerate affected content. | Two complete conforming packs A/B. |
| Skill generation | Generate, inspect, screen, test and approve one practice skill; reject a planted bad candidate. | Instructions and finite policy data; no generated executable scripts. |

Use all supplied documents under the user's confirmed permission. Preserve public, supplied and simulated provenance. Missing current figures, complete brand rules, budgets and history receive labelled synthetic fixtures and a documented replacement path. The early Copilot proposal remains background intent, not a stack mandate. [P01]

## 2. Architecture and default stack

Use a modular monolith: one API owns business state and contracts, separate worker processes run long tasks, and one browser worker has a narrower execution environment. Avoid independent microservices and a general autonomous supervisor for the hackathon.

| Component | Proposed default | Engineering reason |
| --- | --- | --- |
| Staff UI | React with TypeScript; use the team's existing Next.js or Vite setup. | Typed forms and evidence/review views; framework choice should not delay work. |
| Backend | Python with FastAPI and Pydantic contracts. | Shared extraction, validation and model-adapter code. |
| Database | PostgreSQL, preferably Tiger Data for the sponsor fit. | Transactions, foreign keys, versioned facts and approvals. |
| Retrieval | SQL filters and full-text search first; optional vector reranking. | Structured numeric queries must not depend on embedding similarity. |
| Original files | Private object storage behind an artifact interface; local directory in development. | Immutable capture bytes and source locations. |
| Jobs | Durable PostgreSQL jobs table and one worker initially. | One operational store; add a queue service when justified. |
| Browser | Playwright in a separate restricted worker. | Repeatable form maps, assertions and read-back tests. |
| Search/capture | Tavily search plus Firecrawl capture initially, behind adapters. | Clear starting split; benchmark overlap before adding Exa. |
| Models | One real API adapter first; Gemini is the sponsor candidate. | Prove contracts before adding provider breadth. |
| Exports | DOCX working application and JSON audit bundle. | Supports the Word collaboration flow described in the meeting. |
| Skill system | Structured practice proposals plus deterministic compiler. | Restricts what generated instructions can change. |

FastAPI documents a distinction between small in-process background tasks and heavier work. Our proposal uses persisted jobs for capture, OCR, model calls and browser work, so request completion is not mistaken for job durability. [E05]

Connection map: the UI calls the API; the API reads/writes PostgreSQL and schedules jobs; workers use scoped adapters and artifact storage. Models return proposals to the coordinator. They never directly approve answers or update authoritative facts. Browser work is requested through the same action gateway and a job-specific grant.

Cloudinary source previews and an event domain are optional integrations after this path works. Previews reference original artifact versions; private document previews require the same authorization checks as text.

## 3. Repository and module ownership

| Proposed path | Responsibility | Interface it owns |
| --- | --- | --- |
| apps/web | Knowledge, Funding, Application and Review screens. | Generated API client and UI state. |
| services/api | Authentication context, routes and command handling. | HTTP contracts and action authorization. |
| services/worker | Ingestion, discovery, model and export jobs. | Job handlers, leases and checkpoints. |
| services/browser | Form inspection and approved prefill. | Versioned FormAdapter and ActionResult. |
| packages/contracts | Pydantic schemas and generated TypeScript definitions. | Canonical request/result versions. |
| packages/domain | Applications, evidence, requirements and approval logic. | Pure state transitions. |
| packages/validation | Rule registry, counters, calculations and findings. | ValidationContext and ValidationResult. |
| packages/knowledge | Pack adapters, indexing and authorized retrieval. | EvidenceBundle and PackManifest. |
| packages/providers | Model, search, capture and storage adapters. | Capability declarations and normalized errors. |
| packages/skills | Proposal schema, compiler, scans and skill registry. | SkillProposal and SkillRelease. |
| packages/security | Permission checks, egress policy and screening adapters. | PolicyDecision and ActionGrant. |
| knowledge-packs/demo-a and demo-b | Reviewed supplied/public references and synthetic fixtures. | Versioned manifests with provenance labels. |
| tests/fixtures | GOS fields, benign/attack samples and browser pages. | Known-answer fixtures with source locators. |
| tests/unit, integration and e2e | Rules, database transitions and full user path. | Repeatable acceptance evidence. |
| infra and docs | Local compose, deployment configuration and decisions. | Reproducible development setup. |

Begin with skeletons only for modules used in the first complete slice. Put shared contracts in place before parallel implementation. Agent-runtime adapters may reuse ideas from Gecko's Helper, with its code/license reviewed before actual reuse. [P01, section 12]

## 4. Data model and evidence contracts

### 4.1 Canonical entities

| Entity group | Required information | Integrity rule |
| --- | --- | --- |
| Organization and access | Organization, user, role, membership, document grants. | Authenticated organization context; never trust a model-supplied tenant ID. |
| Document and version | Source class, original artifact, hash, title, URL, publication/capture/effective dates. | Original bytes/version never overwritten in place. |
| Passage and table cell | Source-version ID, page/section, offsets or cell coordinates, exact extracted content. | Locators resolve to the selected immutable version. |
| Fact and derivation | Metric ID, Decimal value, raw value, unit, currency, scale, population, program, geography, period, support. | Candidate/verified/conflicting status remains separate from numeric storage. |
| Approved writing and policy | Text, scope, protected phrases, authority, source locator, approval and version. | A story or funder page is not organizational policy by default. |
| Pack and membership | Pack/version, item mappings, simulated labels, active status. | One active organization pack per selected application context. |
| Funder, stream and cycle | Official identity, guidelines, deadlines, eligibility and capture versions. | Each requirement belongs to a stream/cycle/stage. |
| Application and question | Original instructions, type, count convention, conditions, attachments, order. | Preserve source question numbers and unresolved ambiguity. |
| Answer, claim and evidence link | Exact answer version, spans, fact/passage bindings, transformations. | A citation ID alone never means support was established. |
| Check and review | Rule/input versions, result, severity, explanation, staff decision. | Reviewed version and dependencies are explicit. |
| Skill and release | Proposal, source mappings, compiled content, scans, tests, approval and revocation. | Activation references one immutable package hash. |
| Job and action | Actor, snapshot, attempt, lease, tool arguments, results and artifacts. | Every side effect has an authorized action record. |

Use UUID-like IDs rather than titles as keys. Store money/measurements as exact decimal values and serialize decimals as strings through JSON. Preserve raw strings and explicit rounding. PostgreSQL documents numeric as exact and floating-point types as inexact; our budget arithmetic uses Python Decimal and NUMERIC columns. [E06]

### 4.2 Evidence bundle

Each bundle contains organization/access scope, active pack/version, requirement snapshot, ordered evidence items, allowed fact IDs, policy versions, source locators, uncertainty and coverage. Each item includes its exact excerpt or table values, period/program metadata and provenance. Authorize before ranking and again before returning previews.

Model output contains answer text, claim spans, proposed evidence bindings, transformations, missing inputs and short explanations. The server resolves IDs and recalculates values; it does not accept the model's pass/fail assertions as code results.

### 4.3 Database constraints and migrations

Create foreign keys for evidence/version relations; unique version numbers within each object; nonnegative counts where the metric definition requires them; enumerated states; and ownership-consistent references. Do not use a universal percent bound for every metric: relative growth can exceed 100%.

Row-level security is additional isolation when configured and tested with a non-owner application role. PostgreSQL notes that owners and privileged roles can bypass it; a table policy alone is not evidence of isolation. API authorization remains required. [E07]

## 5. Ingestion, retrieval and knowledge packs

### 5.1 Ingestion pipeline

1. Record upload or official public URL with actor, organization, source class and intended use.
2. Check type/signature, size and destination; quarantine unsupported material.
3. Store original bytes and hash before parsing.
4. Parse in a bounded worker: PDF text/tables, DOCX paragraphs/tables, HTML and text; OCR only where needed.
5. Store page/section/cell locators, extraction coverage and warnings.
6. Propose typed facts, writing blocks and policy candidates; distinguish extraction from verification.
7. Screen untrusted content before model use and review authority before policy promotion.
8. Index authorized passages and registered facts; produce ingestion report.

OCR-derived decisive numbers need original-image inspection or explicit unverified status. A successful parser does not certify correctness. Preserve separate timestamps for capture, publication, reporting period and effective policy date.

### 5.2 Retrieval strategy

Route quantitative questions to typed facts first. Filter by metric, program, period, population and unit before selecting. Use full-text or semantic retrieval for narratives and explanations. Return competing evidence when comparable values conflict; do not let similarity ranking settle the conflict.

An answer may use a dated historical figure when the question and wording allow it. A missing current figure stays missing or uses explicitly synthetic demo data. Keep excerpts sufficient to inspect qualifications and table headings.

### 5.3 Pack contract and replacement

A PackManifest records schema version, organization, item IDs/versions, policy inputs, mapping/parser versions, locale, access labels and source provenance. A supported pack can come from uploads or an adapter to an existing store. The adapter must return original support, not just untraceable summaries.

Activation is transactional: validate pack B; create immutable mappings; compute changed dependencies; update active pointer; mark affected outputs stale. In-flight tasks may finish as historical results, but cannot approve, prefill or export against an outdated snapshot. Revoke changed policy-derived skill releases and regenerate/review them when necessary.

Same-source evidence that remains a valid member of pack B may be retained. Do not reject an unchanged real source simply because it first appeared in A. Reject obsolete bindings and policies by dependency identity, rather than blindly banning every number that appeared in A.

## 6. Discovery and research pipeline

Build a query plan from approved geography, beneficiaries, activities, funding needs and exclusions. Public search queries must not expose internal financial figures or private family stories. The discovery adapter returns query/time/provider and candidate URLs; it does not declare eligibility.

Deduplicate by canonical URL, funder/stream/cycle and document hash without collapsing distinct rounds. Capture official guidelines and relevant files. Separate grant pages from past award announcements, participation forms, donation pages and news.

An opportunity record contains official-source links, cycle status, stage/deadline with uncertainty, award range and limit type, exclusions, priorities, reporting duties, relationship/history inputs, and field-by-field eligibility results. Unknown history stays unknown. The fit explanation quotes relevant priorities and names the matching organizational evidence; it does not produce a falsely precise success probability.

Run manual discovery plus one configurable persisted monitoring job. The scheduler records next-run time, query/watchlist version and last successful capture. Limit requests, crawl depth, pages, file size and retries. Handle API quotas and respect source access conditions; do not design around bypassing login or anti-bot controls.

Record status and content changes separately. Re-capture changed requirements and invalidate affected applications. Maintain an explicitly labelled cached fixture for the demo if live capture fails. A search timestamp is not a publication date or deadline.

## 7. Application intake and answer planning

Create a Question schema with original wording, normalized ID, section/order, organization/program scope, type, limit/unit, counting convention, required state, conditional predicates, choice values, attachments, source locations and conflicts. A model may propose this schema; code validates it and staff can correct interpretation.

Use the supplied United Way guide as the real template and a representative form as the browser fixture. Preserve its conflicting 350/500-word partnership limits, differing Tomorrow Fund amounts, mixed cycle/date labels, financial cutoffs and missing Max 300 unit. Do not silently choose a convenient rule. [P01, section 13; U09]

The answer planner maps all selected questions before drafting: organizational overview, need, services, impact, finances and supporting material. It selects reusable blocks, assigns evidence, identifies repeated questions, and lists missing data. It cannot invent the actual request, spending plan or operational consequences of reduced funding.

For the sample: mission 50 words; services 250 words; pending applications 300 characters; standard request 20,000-100,000 without currency symbols/decimals; network maximum separately 250,000. Compute 80/50/25% scenario amounts from the selected request in code. These are sample-guide rules, not a verified current open opportunity. [U09, pp.9,25,27-29]

## 8. Drafting, claims and specialist review

### 8.1 Bounded roles

| Role | Input | Output and restriction |
| --- | --- | --- |
| Evidence researcher | Question, scope and authorized source bundle. | Candidate passages/facts and gaps; no approval writes. |
| Planner | Full question set and approved organizational material. | Content allocation, evidence needs and overlap handling. |
| Writer | Question, selected evidence and active practice rules. | Answer proposal, claim bindings and uncertainties. |
| Numerical reviewer | Original values/tables, claim slots and calculations. | Independent proposed findings; arithmetic executed by code. |
| Meaning/policy reviewer | Approved wording, proposed answer and scoped rules. | Meaning changes, unsupported statements and terminology findings. |
| Coordinator | Typed outputs and workflow snapshot. | Runs code checks, persists versions and selects next allowed transition. |

Reviewers inspect original evidence before seeing another reviewer's verdict. Use extra review passes on consequential numeric, financial, eligibility and disputed claims. Agreement is never the truth criterion. Agents share typed results and authorized references, not hidden commands or permissions.

### 8.2 Numeric rendering and claim coverage

Prefer bound fact slots for quantitative sentences: the writer proposes a metric/template, the server renders the approved value/period/unit and records its text span. Derived values require registered formulas and input IDs. After every edit, run a deterministic scan for unbound numerical strings and broken protected spans.

That scan will also find dates, question numbers and addresses; classify typed exceptions instead of treating every digit as an impact statistic. Written-out numbers, implicit comparative claims and causal wording still need semantic review. A compliant-looking fact slot can represent the wrong metric if its binding was wrongly approved.

### 8.3 Evidence explanation

Display: what the system proposes; the short reason; supporting passage/rule/calculation; what remains uncertain; and the staff action. Do not expose or promise access to private model reasoning. Generate a concise decision record from actual evidence and execution logs, then check that explanation for unsupported claims.

Example: This is the 2016 figure. It can be used in a sentence about 2016, but we do not have evidence for the current year. Add the current figure or keep the statement historical. This explanation is derived from the selected source date and temporal policy, not an agent confidence score.

## 9. Deterministic validation engine

### 9.1 Contract

Each rule has ID/version, scope, prerequisites, implementation, priority/severity, invalidation dependencies and fixtures. ValidationContext includes exact answer bytes/hash, question/requirements, pack/policy/skill versions, authorized evidence, verified facts, counter version and frozen evaluation time.

A ValidationResult records pass, fail, needs_review or not_applicable; reason code; observed and expected values; evidence locators; affected span; input hashes; rule version; next action; and evaluator identity/time. A missing prerequisite is needs_review. Not_applicable requires a recorded reason.

The engine is pure where possible: pass typed inputs, return findings, no model call and no hidden network fetch. Rules requiring database authorization receive a resolved permission snapshot and enforce a fresh check at action time. Time-based checks receive explicit now; never silently reuse yesterday's result.

### 9.2 Gates and limits

| Action | Gate |
| --- | --- |
| Save/edit working draft | Allow incomplete work with visible markers; never label reviewed. |
| Approve answer | Current exact version, adequate evidence review, completed applicable blockers and authorized reviewer. |
| Reviewed export | Revalidate dependencies, unresolved blockers and simulation mode; include evidence audit bundle. |
| Browser prefill | Exact approved content plus form/origin/field/action grant; recheck immediately before action. |
| Activate skill | Current content hash, approved practice sources, complete screening/tests and authorized review. |

A pass proves only its exact predicate. A matching number with the wrong population remains wrong; a valid citation may not support a paraphrase. Semantic support, causal language, authenticity of a document and meaning-preserving edits require separate judgment. Model-extracted metadata must not be silently treated as verified input.

P0 entries are capability gates, not a promise to implement every broad feature before the demo. Disable an unsupported feature rather than displaying a decorative passing badge. P1 rules remain in the backlog and registry. There is no universal accuracy percentage claimed here.

## 10. Existing 51 checks with implementation fixtures

The IDs and P0/P1 priorities from the team brief are retained. The machine-readable companion also retains each original requirement and failure behaviour. Below, every row adds an implementation approach and minimum negative/boundary fixture. These are specifications, not executed tests.

### 10.1 Sources and captures

| ID | Priority | Requirement and implementation | Minimum acceptance fixture |
| --- | --- | --- | --- |
| SRC-01 | P0 | A citation's source/version ID exists. Foreign-key/lookup of source version within authorized evidence set. | Unknown version ID fails; known authorized ID passes. |
| SRC-02 | P0 | Stored artifact hash matches its registered version. SHA-256 of stored original bytes against immutable artifact record. | Alter one byte after capture; integrity check fails. |
| SRC-03 | P0 | Referenced page or section exists. Resolve locator against page/section/table inventory of that version. | Page 31 in a 30-page document fails. |
| SRC-04 | P0 | A claimed direct quote matches the stored passage under a documented normalization rule. Compare quote to recorded passage using versioned whitespace policy. | Changed digit fails; allowed whitespace difference passes. |
| SRC-05 | P0 | Capture succeeded and required content is nonempty. Check capture status and nonempty expected extraction fields. | HTTP success with empty document returns needs review. |
| SRC-06 | P1 | Detect identical artifact hashes and repeated candidate URLs. Canonical-URL keys plus artifact hashes; preserve distinct capture metadata. | Same bytes at two URLs share artifact, retain both origins. |
| SRC-07 | P1 | Detect source-version changes. Compare captured content hashes and semantic record versions. | Changed guideline invalidates dependent requirement snapshot. |
| SRC-08 | P1 | Required extraction fields and original-artifact reference are present. Validate required capture metadata and resolvable original-artifact key. | Missing original file reference fails ingestion readiness. |
| SRC-09 | P1 | Page count or extraction coverage is known and within the processed range. Compare processed pages to actual page inventory; flag omissions. | Two pages extracted from thirty stays partial. |
| SRC-10 | P1 | Record parser/OCR version, warnings, and capture time. Require parser version, timestamps and explicit warning list, even empty. | Missing parser version fails provenance completeness. |

### 10.2 Numbers and financial calculations

| ID | Priority | Requirement and implementation | Minimum acceptance fixture |
| --- | --- | --- | --- |
| NUM-01 | P0 | Parse numeric values without losing sign, decimal, scale, or percent markers. Locale-aware decimal parser; retain raw value and ambiguity status. | Parenthesized loss and 1.2 million retain sign/scale; ambiguous 1,234 is reviewed. |
| NUM-02 | P0 | Values fall within the defined metric's range, such as a proportion from 0 to 100%. Metric-specific typed bounds; unknown metric has no invented bounds. | 101 percent fails a bounded share; 101 percent growth is not automatically invalid. |
| NUM-03 | P0 | Claim value matches the cited structured fact. Compare bound claim slot with verified fact/derivation using declared rounding. | 94 changed to 95 fails even when both appear elsewhere. |
| NUM-04 | P0 | Claim unit/currency matches source and task. Match typed unit, scale and currency; require explicit conversion record. | CAD treated as USD or families as children fails. |
| NUM-05 | P0 | Period, program, and population match the selected fact. Compare metric key plus period, program, geography and population. | LSW enrollment cannot satisfy an organization-wide completion slot. |
| NUM-06 | P0 | Budgets reconcile line items, subtotals, and totals using decimal arithmetic and documented rounding. Decimal line-item sum, subtotal graph and documented rounding tolerance. | Items sum to 10,001 but budget says 10,000; show delta 1. |
| NUM-07 | P1 | Computed ratios have the intended nonzero denominator. Validate nonzero approved denominator and execute registered formula. | Zero or absent denominator prevents ratio output. |
| NUM-08 | P1 | Enrollment, completion, assessed participants, and responses use distinct metric IDs. Require the expected metric ID in typed evidence binding. | Enrollment ID bound to completion claim fails. |
| NUM-09 | P1 | Compare matching fact keys for inconsistent values. Group comparable fact keys; flag unequal values without choosing a winner. | Two same-scope, same-period totals differ; both remain visible. |
| NUM-10 | P1 | Distinguish percent change from percentage-point change. Calculate relative change and point difference in separate typed operations. | 40 to 50 percent is 10 points or 25 percent relative change. |
| NUM-11 | P1 | Aggregate only nonoverlapping, compatible scopes. Require explicit disjoint-scope declaration and compatible units/periods. | Overlapping regional totals return needs review instead of summing. |
| NUM-12 | P1 | Future targets and requested costs have approved project inputs. Require approved or explicitly simulated input IDs for commitments. | Old financial expense total cannot become a new funding target. |

### 10.3 Dates and time suitability

| ID | Priority | Requirement and implementation | Minimum acceptance fixture |
| --- | --- | --- | --- |
| DAT-01 | P0 | Required deadline components are present or explicitly unknown. Validate date/time/zone fields; distinguish date-only from exact cutoff. | Deadline with no timezone remains unknown when time matters. |
| DAT-02 | P0 | Compare current time and deadline in the stated timezone. Use frozen evaluation time and IANA-zone conversion with DST handling. | Before/after exact cutoff tested; a date-only cutoff is not fabricated. |
| DAT-03 | P0 | Select the correct cycle and application stage. Bind requirement to funder, stream, cycle and application stage IDs. | EOI deadline cannot stand in for full-application deadline. |
| DAT-04 | P1 | Project dates satisfy explicitly encoded funding-period conditions. Compare project start/end to approved funding-window constraints. | Project ending outside supported funding window fails. |
| DAT-05 | P1 | A claim's wording and reporting period match the selected time policy. Match declared temporal claim type to period and explicit freshness policy. | 2016 fact labelled current fails; explicitly historical use may pass. |

### 10.4 Eligibility

| ID | Priority | Requirement and implementation | Minimum acceptance fixture |
| --- | --- | --- | --- |
| ELG-01 | P0 | Every required input for an encoded eligibility rule is present. Three-valued predicate inputs: satisfied, not satisfied, unknown. | Absent prior-grant history returns unknown, never eligible by default. |
| ELG-02 | P1 | Apply explicit amount, geography, organization-type, and activity rules. Execute reviewed finite predicates over typed organization/request fields. | Boundary amounts and exact geographic memberships tested. |
| ELG-03 | P1 | Distinguish per-award limits from total funding pool and matching requirements. Check limit_kind and application_type before comparing request. | Network 250,000 maximum cannot validate standard GOS request. |
| ELG-04 | P1 | Explicit invitation or prior-stage requirements are met. Require evidence-bound invitation/prior-stage status for applicable rules. | A public Apply button does not satisfy invitation requirement. |

### 10.5 Applications, access and approval

| ID | Priority | Requirement and implementation | Minimum acceptance fixture |
| --- | --- | --- | --- |
| APP-01 | P0 | Answers satisfy the funder's specified word/character counting convention. Versioned counter selected per field: words, code points, UTF-16 or portal count. | Boundary N/N+1, emoji, apostrophes, line breaks and pasted text tested. |
| APP-02 | P0 | Required questions, fields, and attachments have a recorded status. Evaluate required and conditional fields against explicit status map. | Missing required attachment stays incomplete; unknown dependency stays review. |
| APP-03 | P0 | Generated factual claims carry valid evidence references or an explicit unsupported marker. Require claim spans, evidence IDs or explicit unsupported markers; scan uncovered numbers. | Unbound numeric span blocks reviewed output; citation presence alone is not support. |
| APP-04 | P0 | Approvals reference the exact answer/content version. Match approval to content hash and complete dependency snapshot. | One character edit or applicable policy change stales approval. |
| APP-05 | P0 | Retrieval and preview requests satisfy document access rules. Authorize before retrieval, ranking, snippets, previews, caches and export. | User without document permission cannot obtain its snippet or page image. |
| APP-06 | P1 | Evidence changes invalidate dependent checks. Traverse dependency edges on source/fact/requirement version changes. | Changed fact stales every dependent answer check, including aggregate status. |
| APP-07 | P1 | Reviewed-export policy is satisfied. Apply mode-specific export gate to exact versions and unresolved blockers. | Working draft exports labelled; reviewed export blocked with unsupported claim. |
| APP-08 | P1 | Validation records include rule version and reproducible inputs. Require rule version, input snapshot hashes, evaluation time and result payload. | Missing rule version prevents a validation record from counting as current. |

### 10.6 Writing policy

| ID | Priority | Requirement and implementation | Minimum acceptance fixture |
| --- | --- | --- | --- |
| POL-01 | P0 | Apply terminology rules only to their specified program/context. Apply scoped phrase/token rules to generated prose, respecting quote spans. | Tutor in LSW narrative is flagged; same word in a preserved quote is not rewritten. |
| POL-02 | P0 | Verify designated protected wording and first-use naming rules. Compare protected text and first-use expansions over configured application scope. | First program mention missing required name/mark fails; later acronym allowed. |
| POL-03 | P0 | Reject missing-data placeholders disguised as historical/current values. Scan explicit placeholder tokens and missing-input bindings before reviewed export. | XXX allowed in working draft; old figure cannot fill missing current slot. |
| POL-04 | P1 | Check a declared program assessment type against a structured program fact. Check registered program-to-assessment mapping against declared claim scope. | All-program pre/post claim conflicts with Baby Connections post-only record. |
| POL-05 | P1 | Enforce source-use exclusions and provenance labels. Enforce evidence-use exclusions and propagate synthetic-data labels. | EQAO support or lost simulated label prevents reviewed-real readiness. |

### 10.7 Browser transfer

| ID | Priority | Requirement and implementation | Minimum acceptance fixture |
| --- | --- | --- | --- |
| AUT-01 | P0 | Every required question maps to a unique expected form field. Validate field-map IDs, cardinality and form fingerprint; allow declared groups. | Missing input or two unexpected matches stops prefill. |
| AUT-02 | P0 | Prefill uses the exact approved answer version. Fetch exact approved snapshot server-side immediately before entry. | Browser job cannot prefill cached answer after staff edits it. |
| AUT-03 | P0 | Read-back value equals intended entered value. Read final DOM value and compare under declared, narrow normalization. | Maxlength truncation is detected; no silent trimming accepted. |
| AUT-04 | P1 | Validate required attachment count/type/size against confirmed rules. Compare attachment manifest and target constraints before upload. | Wrong type, excessive size or missing required file stops that transfer. |

### 10.8 Knowledge-pack replacement

| ID | Priority | Requirement and implementation | Minimum acceptance fixture |
| --- | --- | --- | --- |
| PKG-01 | P0 | Validate pack IDs, versions, required fields, and evidence references. Strict manifest schema and resolvable same-organization evidence links. | Duplicate IDs, missing source version or unsupported mapping rejected. |
| PKG-02 | P0 | Invalidate dependent outputs when pack facts/policies change. Diff structured facts/policies and walk reverse dependency graph. | Changed policy invalidates affected answer; unrelated answer remains valid. |
| PKG-03 | P0 | Verify regenerated output references the active replacement pack. Require active-pack provenance for new bindings; inspect removed/replaced values. | New answer cannot cite inactive replaced fact, even if numeric value happens to match. |


## 11. Practice-skill generator

### 11.1 Purpose and examples

Generate reusable organizational practices from approved material: Strong Start grant terminology; funder-focused answer-first structure; meaning-preserving shortening; historical-data handling; evidence explanations; and question triage. Start with one skill combining terminology and evidence explanation from the supplied writing approach. [U01]

| Input | Candidate output | What remains outside the skill |
| --- | --- | --- |
| Approved writing guide | Scoped practice instructions and terminology rules. | New tool permissions and final approvals. |
| Brand playbook | Protected phrases, tone guidance and first-use rules. | Unsupported current impact figures. |
| Past successful applications | Proposed reusable structure and examples, reviewed for context. | Assumption that old commitments or facts remain valid. |
| Verified metric table | Fact selectors and retrieval requirements. | Hardcoded current-year numbers in instruction text. |
| Unreviewed webpage/story | Evidence candidate or example only. | Automatic organizational policy promotion. |

The open Agent Skills format uses SKILL.md with metadata/instructions and optional resources; executable resources are possible in that format. Our v1 deliberately exports a restricted subset and keeps application permission enforcement separate. The format's experimental allowed-tools metadata is not the enforcement mechanism. [E01]

### 11.2 Generation pipeline

1. Staff select approved practice sources, intended task/program scope and examples.
2. A tool-less proposer extracts candidate practices into a strict structured schema with source spans.
3. A reviewer compares each proposed practice to its source, checking exceptions and conflicts.
4. Code validates schema, scope, references, finite operators and file/content limits.
5. Run phrase/hidden-content scans and a classifier over metadata, body, examples and references; record coverage and uncertainty.
6. Compile the reviewed structured proposal into predictable instruction sections and typed policy records.
7. Run deterministic fixtures and model-behaviour evaluations with instrumented dummy tools.
8. Show staff the source-to-rule map, diff, test evidence, flagged spans and requested scope.
9. Authorized staff activate the exact reviewed hash; save the previous release for rollback.
10. At use time resolve active facts and permissions again; source/policy changes trigger dependency review.

The compiler is deterministic; the proposal model is not. Generated skills never automatically install themselves into Codex, Claude Code or another user's environment. Export and activation are different actions. No current personal skill is being created by this document.

### 11.3 Restricted v1 schema

| Field | Meaning and limit |
| --- | --- |
| identity | Skill ID/version, name/description, organization and schema/compiler versions. |
| applies_to | Enumerated task types, program scope, locale and explicit exclusions. |
| practice_rules | Structured action, scope, source passage IDs, rationale and exceptions. |
| policy_rules | Enumerated operator and typed operands; no executable expression strings. |
| fact_selectors | Metric/scope/period selectors resolved against active authorized pack. |
| examples | Labelled benign examples with source mappings or synthetic status. |
| authority | Source-policy approvals and reviewer identity; never self-asserted by model. |
| screening | Scanner/classifier versions, chunk coverage, flags and review outcome. |
| release | Exact content hash, tests, dependency snapshot, activation and revocation state. |

Permit finite operators such as exact_phrase, forbidden_phrase, first_use_expansion, required_fact_binding, source_exclusion, scope_match and require_detail_id. Their implementation lives in reviewed application code. Restrict lengths, item counts and matching complexity. Do not accept generated Python, shell, arbitrary regex, SQL, package installs or dynamically fetched instructions.

Keep semantic advice such as preserve meaningful partnership detail as prose guidance plus model/staff evaluation. A required_detail_id can test presence of a registered detail; it cannot prove the entire paraphrase preserved meaning. Current statistics remain referenced data, not long-lived instruction constants.

### 11.4 Skill states and precedence

States: proposed, screened, testing, needs_review, approved, active, suspended, revoked, superseded. Approval does not automatically activate in another context. A dependency change suspends affected releases or marks them for explicit revalidation before use.

Core authorization, evidence and submission controls cannot be changed by a generated rule. Reviewed funder requirements govern the specific application; organizational writing practices govern their applicable scope. If official wording exceeds a funder limit, preserve the conflict and request a reviewed variant. Do not silently rewrite the official mission to satisfy a counter.

## 12. Threat model and security design

### 12.1 Why words alone cannot establish safety

OWASP describes keyword screening and guardrail models as partial defenses with false positives and bypasses. It recommends controls outside the model. This plan therefore treats suspicious wording as triage evidence and enforces capabilities at execution time. A classifier pass never authorizes a tool action. [E02]

Flag phrases associated with overriding instructions, extracting credentials, suppressing checks, changing approval state or sending data elsewhere. Record exact spans and context. An approved security example quoting such a phrase can be benign; an instruction reworded without any flagged phrase can still be malicious. Do not block ordinary words such as system or delete globally.

### 12.2 Threat boundaries

| Entry point or threat | Proposed control | Residual limit |
| --- | --- | --- |
| Web/PDF text tries to become an instruction | Separate untrusted evidence from approved practices; source-to-policy review. | The model may still write a misleading summary, requiring evidence review. |
| Poisoned private practice document | Approved authority role, source mapping, diff review and behavioural tests. | An authorized reviewer can approve a bad rule; approval is accountable, not infallible. |
| Skill asks for new tools or a secret | No executable resources; server-owned capability intersection and credential separation. | Permissions must also hold in the actual runtime adapter. |
| Hidden or encoded content | Bounded inspection of raw/normalized/decoded views, suspicious-span flags and classifier. | Screening will not identify every attack; do not call the package proven safe. |
| Skill metadata triggers too broadly | Screen metadata and require enumerated task/program scope. | Behavioural triggering in an external runtime must be tested separately. |
| Private evidence leaks through search, model or preview | Data-class routing, query restrictions, object authorization and egress controls. | A keyword secret scanner cannot detect all sensitive data. |
| Model changes approval or final submit | Typed state transitions; no model approval writes; no submit/sign capability. | Live portals may autosave or submit implicitly; adapter support must verify effects. |
| Parser/browser accesses internal network | Restricted process environment and network destination policy. | A browser request interceptor alone is not network isolation. |
| Package updated after approval | Immutable hashes, action-time version check, revocation and rollback. | Already completed external effects cannot be undone by revocation. |

OWASP's agent guidance supports scoped tools, action integrity and tested authorization. Our design binds approvals to actual targets, arguments and versions rather than trusting a prompt that says approved. [E03]

### 12.3 Classifier design

Introduce a ScreeningAdapter returning model/version, policy version, inspected chunk IDs, label/score when available, flagged spans, processing failures and coverage. Scores and labels differ across models; do not assume they are calibrated or interchangeable. Treat timeout, unsupported language, truncated input and inconclusive output as incomplete screening.

Prompt Guard 2 is a candidate dedicated attack classifier described by Meta's model card. Its suitability, license, hardware needs, input limits, languages and behaviour on Strong Start material must be evaluated before selection. Do not assume it is available through Featherless or the user's GLM endpoint. A general content-moderation model is not automatically an instruction-attack detector. [E04]

Use source chunks with overlap plus separate metadata screening and cross-reference inspection. Capture a package-level review for interactions spanning chunks. A dedicated classifier is one signal; a separate evidence reviewer evaluates whether instructions match approved practice. Avoid multiplying chat-agent votes into a claim of security.

Policy: deterministic invalid structure or forbidden capability is rejected. Suspicious semantic findings are quarantined for review. Eligible candidates with completed screening still need their test and authorized activation records. When the classifier is unavailable, do not activate a new generated skill through an automatic fallback. Existing approved releases follow their configured validity policy; show service degradation.

### 12.4 Network and runtime isolation

OWASP's SSRF guidance supports validating destinations and network-layer restrictions. Our proposed gateway blocks non-HTTP(S) schemes, local/private/link-local/metadata destinations, unsafe redirects and unsupported ports, with resolution checked at connection time. Add an egress proxy/firewall so DNS rebinding cannot be solved only by a one-time string check. [E08]

The parser and skill proposer have no tool credentials. The public discovery worker receives only public query inputs. The browser worker has a fresh context for one application, minimal artifact access and a short-lived grant. Disable unsupported service-worker paths in the fixture; Playwright documents interception limitations around service workers. Browser routing complements network controls. [E09]

Codex/Claude Code adapters must run in isolated per-job directories with sanitized configuration, controlled MCP tools, minimal environment and enforceable network/filesystem restrictions. If an adapter cannot meet the declared security profile, do not route private material or enable its tools. A common output schema does not imply equal isolation across providers.

## 13. Additional 35 engineering checks

These extend the existing 51 rules to 86 planned checks. Their pass conditions are explicit predicates over schemas, permissions, versions, coverage or execution results. They do not claim that text classification or malicious-intent detection is deterministic. Pattern matches and scanner reports are findings with a limited meaning.

### 13.1 Generated skills

| ID | Priority | Requirement and implementation | Minimum acceptance fixture |
| --- | --- | --- | --- |
| SKL-01 | P0 | Strict skill schema and format bounds. Validate name, description, type, scope, trigger fields and schema version; reject unknown fields. | Missing description or unsupported version cannot become a candidate. |
| SKL-02 | P0 | Positive file and content-type allowlist. V1 accepts compiler-produced text/JSON references only; reject scripts, executables, dependencies and install hooks. | A generated shell file or embedded executable artifact is rejected. |
| SKL-03 | P0 | Confined references and paths. Resolve approved relative paths and IDs; reject traversal, absolute paths, symlinks and external include directives. | A reference escaping the package root is rejected. |
| SKL-04 | P0 | Safe bounded parsing. Bound bytes, depth, item count and parse time; reject duplicate keys, YAML object tags/aliases and recursive includes. | Duplicate capability key or excessive nesting fails before model use. |
| SKL-05 | P0 | Authority-linked instruction provenance. Each proposed organizational rule references an approved policy source or explicit administrator-authored practice. | A grant webpage cannot promote its instructions into organization policy. |
| SKL-06 | P0 | Fact references remain live and scoped. Resolve fact selectors through active pack; prohibit generated current-number constants in policy payload. | Pack swap changes the selected fact without rewriting skill prose. |
| SKL-07 | P0 | Explicit task and program scope. Require bounded task types, program IDs and locale; dispatch only inside that scope. | LSW-only practice rule does not apply to Baby Connections. |
| SKL-08 | P0 | Suspicious-pattern and hidden-text screening coverage. Versioned scan over raw metadata/body/references and bounded normalized views; record spans and review flags. | Known phrase or hidden tag is flagged; flag alone is not a maliciousness verdict. |
| SKL-09 | P0 | Complete screening records for exact content. Require current scanner/classifier coverage of all candidate parts, including overlap chunks; errors or truncation mean incomplete. | Classifier timeout or unread trailing chunk prevents activation. |
| SKL-10 | P0 | No capability expansion from generated text. Intersect requested scopes with server-owned role/task grants; skill text cannot add tools, network, file or credential access. | Candidate asking for a new network destination gets no such permission. |
| SKL-11 | P0 | Finite rule language only. Accept enumerated operators/typed operands with limits; disallow code, eval, dynamic imports and arbitrary regex. | An expression requiring arbitrary execution is rejected. |
| SKL-12 | P0 | Protected control-policy integrity. Reject attempts to alter core evidence, authorization, approval or submission controls; preserve conflict records. | A generated rule disabling claim checks cannot be activated. |
| SKL-13 | P0 | Activation binds exact reviewed package. Require authorized reviewer, package hash, source/pack versions, current screening, test report and dependency snapshot. | Editing one metadata character after approval returns package to review. |
| SKL-14 | P0 | Revocation and change invalidation. Check active/revoked status at dispatch and tool boundary; stale source/policy versions invalidate affected skills and outputs. | Revoked skill cannot start another action; in-flight jobs cancel before next action. |
| SKL-15 | P1 | Reproducible skill build identity. Store canonical input manifest, compiler/template versions, package bytes/hash and test corpus version; deterministic compiler output is repeatable. | Same approved structured input compiles identically; model proposal is not claimed repeatable. |
| SKL-16 | P1 | Import/export is not automatic trust. Export sanitized supported format only; imported package enters quarantine and revalidation; no auto-install/auto-update. | Re-imported edited package does not inherit original activation. |

### 13.2 Security boundaries

| ID | Priority | Requirement and implementation | Minimum acceptance fixture |
| --- | --- | --- | --- |
| SEC-01 | P0 | Identity and object authorization. Derive organization/user/role from authenticated context; check ownership and grants on every object/action. | Replacing org_id in a request cannot access another organization. |
| SEC-02 | P0 | Provider and data-class routing. Compare content labels and user policy to approved provider/region/task capability before dispatch. | Restricted document cannot be sent to a disallowed provider by fallback routing. |
| SEC-03 | P0 | URL and network destination controls. Validate schemes and destinations, resolved addresses and every redirect; enforce egress policy outside model/browser. | Loopback, cloud metadata and redirect to private IP are blocked. |
| SEC-04 | P0 | Upload and parser containment. Check file signature/type/size; parse in resource-limited worker with no credentials or outbound network. | Renamed executable or oversize compressed document is rejected/quarantined. |
| SEC-05 | P0 | Executable tool-call schema. Only server-registered tools and typed parameters; no shell/raw SQL/path execution supplied by model. | Unknown tool name or unexpected argument fails before execution. |
| SEC-06 | P0 | Credential boundary. Keep service keys outside prompts/generated skills/browser content; apply configured secret-pattern and synthetic-canary scans. | Known dummy key in generated payload is caught; scan pass is not proof of no secrets. |
| SEC-07 | P0 | Safe content rendering. Escape text and use sanitization/link-scheme allowlists; disable embedded scripts and remote auto-loaded images in evidence views. | Malicious HTML displayed as inert evidence cannot run or beacon. |
| SEC-08 | P0 | Exact browser action authorization. Bind staff-approved prefill action to origin, form fingerprint, fields, answer/attachment hashes and short-lived job grant. | Origin or field change requires remapping/reapproval; generated text cannot grant it. |
| SEC-09 | P0 | Final-submit and signing boundary. Do not expose submit/sign tools in demo; deny those operations in action gateway and fixture endpoints for automation principal. | Attempted submit call fails even if skill says it is approved. |
| SEC-10 | P0 | Audit completeness with sensitive-field exclusions. Require actor/action/object/version/decision/time; redact configured credentials/cookies and restrict trace access. | Missing action decision fails audit completeness; known dummy secret is excluded. |
| SEC-11 | P1 | Dependency and artifact release policy. Pin builds and run maintained dependency/secret/container scanners under an explicit release policy. | Disallowed known finding blocks release; clean scan is not a security guarantee. |
| SEC-12 | P0 | Scoped agent communication. Validate sender/task ID, result schema and evidence permissions before coordinator accepts a message. | Reviewer cannot grant permissions or overwrite approved facts through result text. |
| SEC-13 | P0 | Access-aware caches and temporary artifacts. Key authorization scope and dependency versions; reauthorize reads; expire job grants and clean per-session temporary data. | Different user cannot reuse a private retrieval or preview cache entry. |
| SEC-14 | P0 | Model output remains a proposal. Allow writes only through typed workflow commands and authorized state transitions; never accept model-created approval/status fields. | A draft response claiming approved=true cannot approve itself. |

### 13.3 Workflow reliability

| ID | Priority | Requirement and implementation | Minimum acceptance fixture |
| --- | --- | --- | --- |
| JOB-01 | P0 | Idempotent commands and job deduplication. Bind idempotency key to actor, operation and request hash; reuse result for same request and reject changed payload. | Double click creates one job; same key with different answer returns conflict. |
| JOB-02 | P0 | Optimistic version and action-time checks. Compare expected snapshot before committing or acting; refuse stale input and recheck after long jobs. | Concurrent edit or pack change prevents stale approval/prefill/export. |
| JOB-03 | P0 | Bounded retries, time and token/tool budgets. Enforce attempt/time/cost limits in coordinator; retry only classified safe stages; cancel via worker grant. | Repeated timeouts stop visibly; uncertain browser writes are inspected before retry. |
| JOB-04 | P1 | Durable job lease and checkpoint ownership. Record lease/heartbeat/checkpoints; reclaim expired read jobs safely and quarantine uncertain write outcomes. | Worker death does not silently drop job or duplicate a browser write. |
| JOB-05 | P0 | Frozen validation and cache dependencies. Hash answer, evidence, pack, requirements, skill, rules, counter, permissions and evaluation time policy. | Old passing check cannot authorize output after its dependency changes. |


## 14. API and tool contracts

### 14.1 Core routes

| Route or command | Input | Result or restriction |
| --- | --- | --- |
| POST /packs/import | Uploaded item IDs, mappings and manifest version. | Ingestion job and per-item report. |
| POST /packs/{id}/activate | Expected active version and validated replacement. | Transactional activation/invalidation summary. |
| POST /discovery/jobs | Public search profile, provider limits and mode. | Durable job ID; no private corpus pasted into query. |
| GET /opportunities/{id} | Authorized opportunity ID. | Captured requirements, source versions and unknowns. |
| POST /applications/import | Guide/capture ID and selected stream/cycle. | Questions and unresolved extraction conflicts. |
| POST /applications/{id}/plan | Question and pack snapshots. | Answer plan with evidence and missing inputs. |
| POST /answers/{id}/draft | Expected version and selected evidence. | Draft job; typed proposal only. |
| POST /answers/{id}/validate | Exact answer/dependency versions. | Rule findings and semantic-review status. |
| POST /answers/{id}/approve | Content hash, snapshot and reviewer decision. | Approval record only when gate passes. |
| POST /applications/{id}/prefill | Form-map version and approved snapshot IDs. | Scoped browser action job and read-back evidence. |
| POST /applications/{id}/export | Working/reviewed mode and expected snapshot. | DOCX plus audit manifest or blocked result. |
| POST /skills/propose | Approved practice source IDs and scope. | Quarantined structured candidate. |
| POST /skills/{id}/screen-and-test | Immutable candidate hash. | Scan/test job with coverage and failures. |
| POST /skills/{id}/activate or revoke | Expected version, role and decision. | Version-bound activation or revocation. |
| GET /jobs/{id}/events | Authorized job ID and cursor. | Progress/events; not raw credentials or private reasoning. |

Long operations return 202 and a job ID. Use 409 for version conflicts and meaningful error codes for missing evidence, unsupported adapter capability and incomplete screening. Polling is adequate initially; add event streaming when the full path works.

### 14.2 Agent tools

Expose narrow tools: search_public_grants, capture_public_source, retrieve_authorized_evidence, get_application_questions, propose_answer, run_validation and request_approved_prefill. A request tool creates a proposal/job; the backend still evaluates its action gate. Skills cannot add tools by naming an MCP server.

The typed request contains task ID, operation, input object IDs, expected snapshot, budgets and requested output schema. Actor/organization identity and effective permissions are supplied by the server. The result contains proposed content, evidence references, completeness, warnings, provider metadata and structured failure. Permission assertions in tool text are ignored.

## 15. Workflow states, concurrency and invalidation

| Object | Main states | Important transition |
| --- | --- | --- |
| Capture | queued, fetching, parsed, partial, failed, quarantined. | Partial capture never silently becomes complete. |
| Fact | extracted, needs_review, verified, conflicting, superseded. | Verification records actor and original support. |
| Answer | draft, checking, needs_attention, ready_for_review, approved, stale, rejected. | Edits or applicable dependency changes stale approval. |
| Job | queued, running, paused, succeeded, failed, canceled, outcome_unknown. | Interrupted browser write may be outcome_unknown. |
| Skill | proposed, screened, testing, needs_review, active, suspended, revoked. | Revocation checked before another action. |
| Application | researching, planning, drafting, reviewing, export_ready, prefilling, staff_handoff. | No automated final-submitted state in demo. |

At-least-once job delivery is sufficient with idempotent read operations and guarded writes. Claim a job using a database lease; persist attempts and checkpoints. Do not hold a database transaction open during a model call. Commit results only if expected versions still match.

Approval snapshot: answer hash plus selected source/fact versions, requirements, active pack mappings, policy/skill versions, rule set, counter convention and review decisions. Permission changes are enforced live even when snapshot content is unchanged. Time-sensitive eligibility/deadlines are re-evaluated at action time.

Persist reverse dependency edges. A changed fact, requirement or policy invalidates derived claims, affected answers, validation aggregates, approvals, exports and pending browser grants. Job caches include all relevant versions and authorization scope. An old passing result remains an auditable historical record, never a current green status.

If staff edit while a model drafts, save the model result as a separate proposal or return conflict; do not overwrite staff work. If a browser action times out, inspect actual state before retry. Do not promise exactly-once external writes from an idempotency key alone.

## 16. Browser automation and exports

Start with a FormAdapter supporting inspect, validate_mapping, plan_prefill, execute_approved_prefill and read_back. Store origin, form fingerprint, unique selectors/group definitions, types, limits, option values, expected conditions and mapping version.

Staff authenticate. Inspect the selected form, compare it to the stored schema, and display intended field changes. Authorize the exact prefill snapshot. Enter only mapped approved fields and permitted attachments. Read values back and compare with approved strings under a documented normalization policy. Surface truncation, disabled fields, multiple matches, redirects and unexpected required fields.

A representative portal can enforce a stronger demonstration boundary: the automation principal has no permission on submit/sign endpoints. A real portal adapter is enabled only after understanding autosave and submission effects; never claim it is safe merely because a button was not clicked. Keep final submission and authorization signatures under staff control.

Export DOCX with original questions, answers, counts, highlighted missing/review items and source notes; export JSON with versions, checks and source locators. Use yellow/green/blue according to the supplied guide, preserving separate source approval and answer approval. Working exports may contain XXX; reviewed-real exports cannot hide unresolved/simulated factual inputs. A reviewed demo export remains prominently labelled synthetic where applicable. [U01]

## 17. Model and agent-runtime adapters

Define one ModelAdapter for structured tasks and a separate AgentRuntimeAdapter for session/tool-capable runtimes. Capability declarations include structured output, context/token accounting, attachments, tools, streaming, cancellation, sessions, isolation, permitted data classes and transport errors.

Implement one real adapter plus a deterministic fixture adapter for tests. Then add Featherless for bounded reviewer/extraction tasks if the actual model supports the contract. The user's reported 32K window is a planning input, not a verified capability of every available model. Reserve context for system instructions, tool schemas, evidence and output; do not truncate decisive source qualifiers.

The GLM endpoint/model and Codex/Claude Code modes remain adapter slots until confirmed. Do not assume API-key billing, local runtime availability or session semantics are interchangeable. An unsupported function returns an explicit capability error rather than silently switching to another provider with different data permissions.

Fallback rules are explicit per task: permitted providers, data classes, budget, completeness requirements and whether retries are safe. Record every actual provider/model/version and task input snapshot. Schema-valid output still needs source and value checks.

## 18. Staff interface and understandable explanations

| View | Core components | Decision it supports |
| --- | --- | --- |
| Knowledge | Pack switcher, source inventory, fact table, conflicts and policy/skill releases. | Which material and practices apply? |
| Find Funding | Candidate list, official source, eligibility conditions, changes and proceed rationale. | Is this worth pursuing and what is unknown? |
| Application | Original question, limits, answer plan, editable draft and attachment checklist. | What should we answer and what is missing? |
| Review | Source excerpt/image, exact answer changes, checks, review controls and export/prefill readiness. | Can this version be used? |
| Skill review panel | Source-to-rule map, scopes, flags, tests, version diff and activation/revoke. | Does the proposed practice match approved policy? |

Show distinct indicators for evidence support, time suitability, staff review, simulation provenance and security-screening status. Avoid one green badge implying everything is true and safe. A deterministic pass reads, for example, 248 of 250 words; a judgment finding reads, This sentence says all programs, but the cited assessment covers LSW only.

Each finding includes a plain-language explanation, original support, exact relevant value/rule, affected text and next action. Preserve source context and uncertainty. Readability scores can flag long sentences; they do not establish understandability, correctness or preserved meaning. Test explanations with the team's own nontechnical reading pass and, when available, partner staff.

## 19. Testing and evaluation

### 19.1 Test layers

| Layer | Cases | Evidence to retain |
| --- | --- | --- |
| Unit and property tests | Decimal parsing/calculations, counters, scope matching, limits and finite operators. | Inputs, expected predicates, boundary examples and failure messages. |
| Integration | Ingestion locators, permission filters, version changes, dependency invalidation and concurrent edits. | Database state before/after and exact snapshot IDs. |
| Browser | Extraction, mapping, prefill, truncation, conditional fields, attachments and staff handoff. | Fixture DOM values, action logs and read-back comparisons. |
| Model behaviour | Evidence support, terminology, shortening, numeric slot choices and insufficient-context abstention. | Provider/settings, prompts by access policy, source IDs and reviewed outputs. |
| Skill security | Direct/indirect injection, metadata poisoning, scope expansion, hidden/encoded content and benign quoted examples. | Attack entry point, intended violation, instrumented tool traces and outcome. |
| End to end | Public discovery through approved prefill, then pack swap. | Recorded run, dependency invalidation and final source bindings. |

Start with one positive and one negative/boundary case per implemented deterministic rule. Each catalog row supplies a minimum fixture, not an exhaustive suite. Add property tests where they test a meaningful invariant, such as no stale approval after any relevant dependency mutation. Run actual rule code and compare expected findings; a test that only checks the rule exists is insufficient.

### 19.2 Partner-specific fixtures

Use the June 2016 testimonials as historical evidence; LSW versus organization scope; children/Volunteer Coach terminology; Baby Connections post-only assessment; GOS mixed word/character limits; standard/network request separation; and the guide's explicit conflicts. Use frozen clock/timezone cases and clearly synthetic budgets/history. [P01; U01; U05; U09]

For pack A/B, change one numeric fact, one approved wording block and one policy; leave another source unchanged. Verify affected answers and skills are invalidated, unaffected evidence is retained correctly, approvals cannot be replayed and new bindings use the intended active versions.

### 19.3 Security evaluation corpus

Use harmless synthetic records and instrumented substitute tools. Include attacks inside web captures, PDF/OCR text, skill name/description, references, examples and agent results. Include reworded instructions with no flagged words, supported-language variants, bounded encoded inputs and malicious instructions spread across chunks. Include benign policy instructions, quotations about attacks and normal grant text containing trigger words.

Observe actual attempted tool calls, permission decisions, outgoing dummy requests and dummy-state changes. A refusal in the final answer does not undo an earlier disclosure or write. Missing telemetry, timeouts and unsupported cases are inconclusive rather than successful blocks. Keep grader checks separate from the model being evaluated.

Report per-case outcomes and counts, false-positive blocks on benign controls, legitimate-task completion, review burden and latency. Repeat non-deterministic cases with recorded settings. This is a scoped evaluation; do not advertise universal attack resistance, zero hallucinations or perfect knowledge-pack compatibility.

## 20. Agile delivery for three developers

### 20.1 Working model

Use a small feature-based Kanban workflow with short build-and-review cycles. The previous milestones are integration gates, not a sequence where one developer waits for another to finish. Each developer owns a usable feature from its UI and API through implementation, checks and tests. All three can implement immediately against agreed fixtures.

This is an agile execution proposal, not a claim that a document alone makes the team agile. Maintain one ranked backlog; deliver small working increments; review them together; and change the next tickets based on what the integrated product reveals. No full Scrum ceremony is required for this hackathon.

Board columns: Ready, Doing, Review, Integrated, Done. Keep one main active feature ticket per developer. Blocked tickets record exactly which contract/result is missing; switch to the next independent task rather than waiting silently. A fixture-backed screen is Integrated with fixtures, not Done as a live feature.

### 20.2 Three full-stack feature owners

Dev A, B and C are placeholders for the three team members. Assign names at kickoff. Ownership includes the feature UI, API/routes, persistence changes, rule implementations, error handling and tests. Avoid a split where one person builds every screen and another builds every endpoint.

| Owner | Independent feature area | Main deliverables |
| --- | --- | --- |
| Dev A | Knowledge and evidence | Upload/ingestion, immutable source previews, typed facts, authorized retrieval, pack A/B, provenance, numerical/source validation and dependency storage. Own Knowledge UI. |
| Dev B | Find Funding and application automation | Public discovery, funder profiles/requirements, guide intake, representative portal, field mapping, approved prefill/read-back, deadline/eligibility checks and deployment/CI setup. Own Funding and automation UI. |
| Dev C | Draft, review and practice skills | Model adapters, answer planning/drafting, claim bindings, application editor, staff approval, DOCX/audit export, practice-skill generator/screening/release and writing checks. Own Application, Review and skill UI. |

Dev A owns the common validation runner, source/access primitives and database baseline. Each feature owner adds their own rule modules through its registry. Dev C owns the application shell, navigation and shared UI components; A and B add their feature routes instead of queuing screen work behind C. Dev B owns CI/deployment configuration, with A providing migrations/seed commands and C providing API/web build commands.

Each owner controls their feature folder, API router and schema submodule. Keep contracts split into knowledge, funding/forms, and answers/skills files with the same ownership. Avoid all three editing a single routes file or models file. Dev A sequences schema migrations to prevent duplicate migration heads; other authors supply their changes in small reviewed patches.

### 20.3 Dependency contracts and replacement fixtures

Independently implementable does not mean the features have no runtime dependencies. Build against the same contract now; replace the fixture with the actual producer at a named integration gate. No consumer imports another feature's private tables or internal functions.

| Contract and producer | Consumer and real dependency | How the consumer starts now |
| --- | --- | --- |
| EvidenceBundle, Dev A | C needs original passages/facts for real sourced drafts and skills. | Use one reviewed fixture with exact source IDs, locators, periods and simulated labels. |
| CaptureStore interface, Dev A | B needs immutable artifacts/locators for production source capture. | Use a local fixture implementation with the identical result shape. |
| Opportunity and RequirementSet, Dev B | C needs questions, limits and eligibility unknowns for actual application planning. | Use a selected GOS question set with preserved conflicts. |
| QuestionSet/FormMap, Dev B | C displays real imported questions; B needs a stable question-to-field mapping. | Use shared question IDs and the representative form fixture. |
| AnswerSnapshot and ApprovalSnapshot, Dev C | B needs exact approved text/dependencies before real prefill. | Use a seeded approval from the test harness, never a model-created approval. |
| ValidationResult runner, Dev A | B and C register feature rules and show findings. | Call the pure contract/fixture adapter; later use the same real runner. |
| ChangeSet and dependency store, Dev A | C stales drafts/skills/approvals; B invalidates pending browser grants. | Inject a fixture pack-change event and assert consumer state transitions. |
| Job/AuthContext primitives, A with C | All routes/jobs need identity, versions, budgets and event states. | Shared fixed demo identity and recorded job fixtures; no independently invented actor fields. |

Freeze shared IDs and fixture semantics at kickoff: organization demo-org, pack demo-a-v1, source writing-guide-v1, source dated-metric-v1, opportunity demo-gos, question mission-q1 and form demo-gos-v1. Synthetic metric values must be explicitly labelled. These names are proposed fixtures, not records already created.

Contract changes require a small schema patch, fixture update and notification to consumers. Prefer additive fields; version breaking changes and update producers/consumers together. Consumer contract tests must run against both the fixture and the real producer. A passing mock is not evidence that the real integration works.

### 20.4 Parallel feature backlog and hard dependencies

The order within each owner's lane expresses dependencies. A1, B1 and C1 start together after agreeing minimum schemas; preparation in section 20.5 can start immediately. All tickets are proposed and unassigned to named people.

| Ticket and owner | Feature increment | Dependencies and completion gate |
| --- | --- | --- |
| A1, Dev A | Source/fact contracts, artifact store, database baseline and Knowledge fixture UI. | Starts immediately. Done when one source and typed fact persist and return exact provenance through the API. |
| A2, Dev A | Ingest selected supplied/public material and implement retrieval. | Needs A1; C can already use the EvidenceBundle fixture. Done when C can replace fixture retrieval without changing its draft logic. |
| A3, Dev A | Common validation runner plus source/numeric rules and permission primitives. | Runner schema starts with A1; actual artifact/fact checks need A2. B/C add their rules independently. |
| A4, Dev A | Pack B activation, change/dependency graph and invalidation publisher. | Needs A2 and agreed C/B dependency registration. Done only when C approvals and B pending actions actually become stale. |
| B1, Dev B | Public search, candidate cards, deduplication and source capture adapter. | Starts with CaptureStore fixture; actual persisted capture connects to A1. No need to wait for drafting. |
| B2, Dev B | GOS guide intake, RequirementSet/QuestionSet, field fixture and representative portal. | Starts from supplied guide independently of B1. Preserves ambiguous limits; provides real question contract to C. |
| B3, Dev B | Form inspection, mapped prefill/read-back and browser failure cases. | Starts using seeded approved test snapshots. Real prefill completion needs B2 plus C3 approval API and A/C current-version checks. |
| B4, Dev B | Repeated-discovery job, deployment, browser restrictions and network controls. | Job shell depends on common primitives; search/browser code can be developed locally first. Re-run and failure state must be visible. |
| C1, Dev C | App shell, editor/review fixture UI and first model adapter. | Starts with EvidenceBundle/QuestionSet fixtures. Adapter test is independent of live search or ingestion. |
| C2, Dev C | Plan/draft answer with claim bindings and visible findings. | Fixture implementation starts after C1; real completion needs A2 retrieval, A3 runner and B2 questions. |
| C3, Dev C | Exact-version staff approval, invalidation handler and DOCX/audit export. | Needs C2 state contract; use fixture check results initially. Done after A3 real checks and edit-after-approval test. Unblocks B3 real prefill. |
| C4, Dev C | Practice proposal/compiler, scans/classifier, test/review/activate/revoke. | Schema can start early with U01 fixtures. Real activation needs A2 approved policy provenance and A/C permission/version gates. |
| I1, all; coordinator C | Replace mock seams and join one full application path. | Needs A2/A3, B1/B2/B3 and C2/C3. Each producer/consumer pair fixes its seam. |
| I2, all; coordinator C | Pack swap, skill invalidation, deployment and final release rehearsal. | Needs A4, C4, B4 and I1. Verify stale actions fail across all modules. |

The main real-data path is A2 retrieval plus B2 questions, then C2 drafting, C3 approval, and B3 prefill. B1 discovery runs in parallel and joins through the selected opportunity/requirements. C4 skill generation is a second increment, so it does not hold the initial answer path hostage.

### 20.5 Grunt work and shared foundations

This work is necessary and gets explicit owners. It should not quietly accumulate with the last person integrating. A minimum shared setup can be timeboxed to roughly 45-60 minutes as a planning target, with parallel data/fixture work continuing if setup takes longer. This is not an event deadline or an estimate backed by implementation measurements.

| Setup/preparation task | Owner | Result and who needs it |
| --- | --- | --- |
| Confirm framework, repo conventions and contract naming | All, C records decisions | One short shared contract baseline; no three incompatible app skeletons. |
| API/bootstrap, database connectivity and initial migrations | A | A clean startup path used by all. |
| Common identity/access context and scoped test identities | A | Authorization helpers consumed by B/C; no fake production authentication. |
| Artifact naming, hashing, source inventory and page/date metadata | A | Trusted fixture references and source locations for C/B. |
| Demo pack A/B metric/policy mapping and synthetic labels | A; C reviews wording | Replacement fixtures for drafting, skill and invalidation tests. |
| Approved-practice extraction from U01 and protected-language examples | C; A checks source locators | Practice inputs and writing-rule fixtures. |
| Curate official search URLs and one cached capture | B | Actual discovery baseline and labelled failure fallback. |
| Transcribe selected GOS fields, limits, conditions and conflicts | B; C checks display | Shared question fixture and portal schema. |
| Representative portal, sample attachment and seeded approval fixture | B with C approval schema | Automation can start before real drafts exist. |
| UI shell, common finding/evidence components and fixture adapters | C | A/B can build their own pages without visual/API drift. |
| Environment template, provider-key names, CI and deployment smoke script | B; each owner supplies required settings | Reproducible setup; keys stay out of the repo and frontend. |
| Seed/reset command and deterministic test clock | A; B/C contribute feature seeds | Repeatable integration runs with shared IDs and versions. |
| Test rule registration and evidence/error fixtures | Each feature owner; A owns runner | No unimplemented rule can appear as passing. |
| Demo script and implemented/fixture-only/planned feature matrix | C coordinates; all verify | Accurate presentation and final rehearsal scope. |

### 20.6 Ownership of all 86 checks

The companion JSON assigns primary_owner, verification_owner and integration_dependencies to every check. The owner implements and tests the predicate. Consumers must call it at their action boundary. A shared check owner does not absolve a feature from enforcing it.

| Check IDs | Primary owner | Integration responsibility |
| --- | --- | --- |
| SRC-01 through SRC-10; NUM-01 through NUM-12; PKG-01 through PKG-03 | A | C binds claims and consumes findings; B uses immutable captures and current pack/action state. |
| DAT-01 through DAT-05; ELG-01 through ELG-04; AUT-01 through AUT-04 | B | C supplies request/answer/review snapshots; A supplies source/fact history and clock context. |
| APP-01 through APP-08; POL-01 through POL-05; SKL-01 through SKL-16 | C | A supplies authorized evidence/policy references; B supplies funder limits/form effects. APP-05 uses A's shared authorization primitive. |
| SEC-01, SEC-02, SEC-04, SEC-13 | A | Every feature must enforce these shared identity, routing, parser and cache boundaries. C provides provider/skill destinations; B provides capture/browser routes. |
| SEC-03, SEC-08, SEC-09, SEC-11 | B | A supplies access policy; C supplies approvals. B owns egress/browser boundaries and CI scanner configuration. |
| SEC-05, SEC-06, SEC-07, SEC-10, SEC-12, SEC-14 | C | Shared action/result/rendering/audit primitives consumed by A/B; credentials remain server-side. |
| JOB-01, JOB-04 | A | Job persistence/idempotency/lease primitives used by both feature lanes. |
| JOB-03 | B | Budget/cancel contract enforced in coordinator and workers; C supplies model token/tool usage. |
| JOB-02, JOB-05 | C | Snapshot checks join A dependency versions, B requirements and C answer/skill state. |

Ownership totals are A 31, B 18, C 37. Rule counts do not measure effort: crawling/browser edge cases can outweigh several simple schema checks. Cross-review cycle: B verifies A's rule fixtures, C verifies B's, and A verifies C's. All 86 remain planned; no owner assignment implies implementation is complete.

If C's skill work becomes the bottleneck after A's retrieval/pack slice is integrated, A can take a bounded skill-compiler or provenance subtask against C's SkillProposal contract. C retains release-state ownership; record any ticket transfer explicitly. Do not have two people independently implement the same classifier/policy gate.

### 20.7 Continuous integration checkpoints

Use short feature branches or separate worktrees, small pull requests and one stable main branch. Feature flags can keep incomplete features accessible in development without advertising them as ready. After every contract change, run contract checks. After every merge, run the enabled rule/unit and integrated smoke tests.

Reconnect roughly every 60-90 minutes of active building, or sooner when a ticket reaches a seam. Each developer shows a working result, exact blocker and next deliverable; adjust the ranked backlog. These are suggested team checkpoints, not automations created by this assistant.

| Gate | What joins | Who proves it |
| --- | --- | --- |
| G0 Shared skeleton | One app starts; same IDs/schema/fixtures, health routes and seed command. | All; A proves backend/data, C UI, B CI/startup. |
| G1 First real seam | Real A evidence reaches C editor/draft; real B questions render with limits/conflicts. | A+C and B+C; no interface rewrite. |
| G2 First complete usable path | Discovery/requirements, sourced draft, real checks, staff approval and B form read-back. | All; B+C prove exact approved transfer. |
| G3 Safe practice increment | Real policy provenance reaches skill proposal; scan/test/review/activation and denied-capability case. | A+C; B verifies external-action restriction. |
| G4 Change propagation | Pack B stales affected drafts, skills, approvals, exports and pending prefill grants. | A publishes change; C/B prove consequences. |
| G5 Release rehearsal | Clean deployed run with failures, simulation labels, exports and staff handoff. | All; C coordinates, B deploys, A resets/verifies evidence. |

Do not postpone G1/G2 until the final integration window. If a seam breaks, agree whether producer or consumer violates the contract, open a bounded fix and pair briefly. Do not solve the mismatch by silently weakening evidence or approval requirements.

### 20.8 Final integration and release plan

Reserve roughly the final 20-25% of available team capacity for stabilization and rehearsal, after continuous integration has already produced a complete path. Set the actual freeze point from the remaining event time; this document does not assume a particular start time or create a schedule.

1. C coordinates a feature freeze: list which paths are real, fixture-only, unavailable or deferred. All owners finish or disable incomplete advertised features.
2. A reconciles migrations and seeds pack A/B on a clean environment; verify artifact locators, permissions and schema versions.
3. B deploys the integrated web/API/worker/browser setup and checks configured provider/network restrictions. Each owner verifies their feature routes and settings.
4. A+C run real retrieval, numeric/claim checks and approval; B+C then run approved prefill/read-back and DOCX/audit export.
5. A switches to B; C and B prove that stale answers, skills, approvals and action grants cannot be reused. Regenerate affected content and verify new evidence bindings.
6. Run enabled P0 fixtures plus contract, authorization, concurrent-edit and browser failure tests. Each rule owner fixes its own failures; its verification owner reviews evidence.
7. Run classifier unavailable, capture failure, source conflict, unsupported current figure and truncated-field scenarios. Incomplete work must stay visible and never turn into a passing result.
8. Rehearse the exact end-to-end demo twice from a reset state, including one controlled failure; check source links, synthetic labels and downloads. All approve the release state; staff retain final submission.

C is the integration coordinator, not the person expected to rewrite everyone else's module. A owns database/evidence faults, B owns capture/form/deployment faults and C owns answer/review/skill faults. The developer changing a shared contract pairs with every affected consumer and supplies the compatibility fix.

### 20.9 Definition of Done

A feature is Done when its UI/API work with the real contracted producer; applicable implemented checks and meaningful negative/boundary tests pass; source/provenance/error states are visible; access and version gates are enforced; migrations/seed/reset instructions work; and another developer has reviewed the integration evidence. Update the feature matrix and rule implementation statuses only from actual results.

For an integration ticket, a successful module test or a mocked screenshot is insufficient: the specified cross-module path must run with the recorded versions. Preserve separate status for semantic/model evaluation and deterministic test results. Do not use all 86 listed checks as a claim that 86 checks have passed.

### 20.10 Scope and workload balancing

Keep a thin complete path before adding breadth: one source pack, one real model, actual discovery of a small candidate set, selected GOS questions, one form and one practice skill. Follow G2 before adding more providers or general portals. If behind, reduce candidates, formats, question count and adapter breadth while retaining applicable P0 boundaries.

Defer arbitrary third-party skill imports, executable generated scripts, fine-tuning classifiers, enterprise connectors and voice. An unavailable classifier prevents new automatically screened skill activation; hand-authored reviewed practices can support the initial answer slice with an accurate feature label. Move the next ticket between developers according to actual blockers rather than preserving a fixed role split at the cost of the demo.

## 21. End-to-end demo and acceptance gates

1. Show supplied/public/synthetic inputs and an older fact in pack A.
2. Run public discovery and inspect one candidate with official sources and unknown eligibility inputs.
3. Import selected GOS questions and surface a real instruction conflict.
4. Generate a draft with source-linked facts and visible language/count checks.
5. Generate a practice skill from approved writing guidance; inspect rule-to-source links and scope.
6. Screen a planted candidate asking to bypass review or send data elsewhere; show flags and a denied action in instrumented tests.
7. Review the valid candidate's tests and activate its exact version; use it to improve terminology/explanations.
8. Staff edit/review/approve an answer; demonstrate that a further edit invalidates approval.
9. Prefill the representative form, read back values and show an intentionally truncated case failing.
10. Activate pack B; show affected drafts/checks/skills/approvals invalidated and regenerate with B evidence.
11. Export the working document/audit bundle with simulation labels; hand final submission to staff.

Release gates: all enabled P0 rules have implementation and passing fixtures; no known cross-organization access path in tested routes; required source locators resolve; simulation labels survive export; stale approval cannot authorize prefill; invalid skill cannot expand server permissions; incomplete screening prevents new skill activation; and the advertised full path runs. Maintain a feature matrix of implemented, fixture-only, unavailable and planned capabilities.

## 22. Operations, deployment and observability

Use a reproducible local setup containing web, API, worker, PostgreSQL and the restricted browser service. Store keys in server configuration, never the frontend bundle or generated skill. Deployment can use Vultr if selected; it does not require GPUs for hosted model APIs.

| Concern | Initial engineering behaviour |
| --- | --- |
| Job failures | Durable status, bounded retry, clear staff action and preserved failure reason. |
| Provider outage | Approved fallback only; otherwise keep draft/job resumable and show degraded service. |
| Storage failure | Do not mark capture complete without original bytes and metadata. |
| Cancellation | Stop before next tool call, revoke job grant and preserve uncertain external state. |
| Traceability | Correlate application, task, source, model, rule, skill and browser action IDs. |
| Sensitive logs | Store minimal operational metadata; restrict prompt/artifact traces and redact known secrets. |
| Reproducibility | Pin dependencies, retain migrations, rule/compiler versions and test fixture hashes. |
| Cost controls | Per-job token/tool/request/time budgets with visible usage and configured ceilings. |
| Recovery | Backup original artifacts and database; exercise one restore path before real handoff. |
| Retention/deletion | Configurable policy; derived artifacts and caches linked to source access/deletion state. |

Measure capture completeness, useful unique opportunities, claim-review findings, numerical correctness on known cases, browser equality checks, stale-result blocks, skill-review burden, classifier false positives, task completion, latency and cost. Do not compress these into an unexplained overall trust score.

## 23. Immediate decisions and first backlog

### 23.1 Defaults to start with

Adopt Python/FastAPI, PostgreSQL, React/TypeScript, one durable worker and Playwright unless existing team code makes another choice faster. Use Gemini first for sponsor fit, with provider interfaces in place. Use a representative GOS-based form; no dependency on obtaining live portal credentials. Start practice generation from U01, not arbitrary scraped instructions.

Still confirm actual model IDs/endpoints, available API quotas, hosting owner, team assignments, exact export needs and which counter convention the representative form implements. Confirm a real portal's behaviour before adding its adapter. These choices do not prevent building the fixtures and contracts now. The A/B/C ticket lanes in section 20 are the authoritative execution split; the original ENG tickets below remain a high-level outcome checklist, not a separate sequential work queue.

### 23.2 First engineering tickets

| Ticket | Concrete result | Done when |
| --- | --- | --- |
| ENG-001 | Shared schemas and versioned fixtures. | Frontend and backend validate the same source/question/answer structures. |
| ENG-002 | Database ownership/version constraints and artifact storage. | One supplied source is immutable and permission-scoped. |
| ENG-003 | Pack A ingestion and evidence retrieval. | A fact and passage return original support and time/scope labels. |
| ENG-004 | Rule engine plus initial numeric/count/source fixtures. | Findings are reproducible and missing inputs do not pass. |
| ENG-005 | One model adapter and draft contract. | Unsupported IDs and malformed output are rejected. |
| ENG-006 | Review UI and exact-version approval. | Editing content stales approval and blocks prefill. |
| ENG-007 | Actual discovery/capture slice. | Query, official page and eligibility unknowns are visible. |
| ENG-008 | GOS question fixture and Playwright form adapter. | Approved text enters and is verified; truncation test fails. |
| ENG-009 | Practice compiler and scanner/classifier adapter. | Source-linked rule proposal can be screened/tested without granting tools. |
| ENG-010 | Pack B, skill invalidation, export and rehearsal. | Full demo and gates have retained test evidence. |

No application feature or rule is implemented by this planning deliverable. The JSON catalog is a machine-readable specification for implementation, not an executable validator or passing test report. A future skill exporter is also distinct from installing skills in a user's runtime.

## 24. Sources and interpretation limits

### 24.1 Project evidence

- **P01 - StrongStart_Team_Brief.md, version 2.0.** Current planning baseline created in this conversation. Contains the 11-file inventory, full meeting account and public-source register. A derived planning document, not organizational primary evidence.
- **U01 - Strong Start Approach to Grant Writing.docx.** Primary organizational writing/workflow practices; use its original passages when building policy rules.
- **U05 - Testimonials_Strong_Start_Programs.pdf.** Historical June 2016 material for source-age and attribution tests.
- **U09 - Q3_2026_GOS_Application_Guide(1).pdf.** Thirty-page sample application source. Page locators and unresolved conflicts retained; current open-cycle eligibility is not established.
- **Other supplied materials.** The full supplied set remains in the pack inventory from P01. Their use is authorized by the user. This plan does not reclassify stories, frameworks or event slides as current numerical or policy authority.

### 24.2 Engineering references checked November 7, 2026

- **E01 - Agent Skills specification.** Format and optional resource/metadata conventions. https://agentskills.io/specification
- **E02 - OWASP LLM Prompt Injection Prevention.** Screening limitations and defense principles. https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html
- **E03 - OWASP AI Agent Security.** Tool permissions, action integrity and validation practices. https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html
- **E04 - Meta Prompt Guard 2 model card.** Candidate classifier reference; not an implemented or benchmarked integration. https://github.com/meta-llama/PurpleLlama/blob/main/Llama-Prompt-Guard-2/86M/MODEL_CARD.md
- **E05 - FastAPI Background Tasks.** In-process task caveat and heavier-work distinction. https://fastapi.tiangolo.com/tutorial/background-tasks/
- **E06 - PostgreSQL numeric types.** Exact decimal versus inexact floating-point representation. https://www.postgresql.org/docs/current/datatype-numeric.html
- **E07 - PostgreSQL row security.** Policy behaviour and privileged-role/owner bypass. https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- **E08 - OWASP SSRF Prevention.** Destination validation and network restrictions. https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- **E09 - Playwright network documentation.** Routing/service-worker considerations. https://playwright.dev/docs/network

### 24.3 Interpretation limits

Architecture, schema design, gates, the restricted skill language and the 35 new checks are project recommendations informed by these references, not vendor guarantees. All 86 checks are planned. Phrase scans, classifiers and human review can fail; the design reduces privileges and makes failures observable rather than promising complete prevention. Real runtime isolation and supported portal behaviour must be verified in implementation.
