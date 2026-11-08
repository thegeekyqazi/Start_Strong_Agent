# B1-DISC-001: Funding discovery and source-capture slice

**Revision:** 1.0  
**Assigned agent:** Dev B1, Funding Discovery and Research.  
**Reported base:** ad5b8dd; resolve/verify in the real checkout.  
**Branch:** dev-b/b1-disc-001.  
**Engineering references:** v1.1 sections 4-6, 9-10, 12-15, 18-20 and 22.  
**Related agreement:** B1-B2_Parallel_Launch.md.  
**Product outcome:** Staff can search for funding candidates, inspect why a result was found, capture a selected source and inspect stored evidence with honest availability/eligibility states.

## 1. Execute, inspect and preserve

Read AGENTS.md, this spec, the shared launch agreement, the complete INIT report, decisions 0002/0003, relevant engineering sections, check catalog and actual funding/contracts/configuration code. Resolve actual command names and core interfaces before editing. The reported clean foundation and deviations are inputs, not independent verification by this spec author.

Implement this bounded feature end to end, including the registered Funding page, API, adapters, tests and handoff. Preserve oxlint, the working TypeScript/Vite configuration, navigation, root Playwright dependency group, DB port/migration history and A/C ownership. Do not reinitialize or implement the entire Dev B plan. Use developer discretion for compatible internal details and record meaningful departures.

Copy this spec to docs/specs/B1-DISC-001_Funding_Discovery_and_Capture.md if it is not already there. Add the shared launch agreement under docs/coordination if absent. Map proposed endpoint/model names below to existing prefixes/schemas in the handoff; do not create a duplicate API tree merely to match a label.

## 2. Scope and exclusions

Required: a typed public search profile; actual Tavily adapter; deterministic provider fixtures; candidate normalization/deduplication; source authority/cycle uncertainty; Firecrawl single-page capture adapter; immutable stored representations through CaptureStore or an explicitly scoped local development adapter; authorized artifact reading; Funding UI; bounded failures/budgets; B2 handoff and test evidence.

Future work: recurring search/scheduling, broad crawling/pagination, PDF/OCR ingestion, automatic grant-rule interpretation, full deadline/eligibility evaluation, recommendations implying likelihood of award, CRM/history integration, arbitrary authenticated sites, background durable jobs, multi-provider benchmarking and deployment. Preserve extension points without implementing them speculatively.

No drafting/model API is required. Search-provider summaries/scores do not become verified organizational facts or proof of eligibility. A found page may be closed, historical, an announcement or not a grant. Staff-facing wording must reflect that.

## 3. Required user path

1. Staff opens the existing Find Funding page and sees auth/provider/mode availability.
2. They choose or enter public funding interests, geography and program context; no private knowledge-store content is automatically inserted into the search query.
3. They run a bounded search. The screen shows the query/time/provider, candidates, duplicates/omissions and failures.
4. Each candidate shows title, URL, provider excerpt, explicit origin/authority status and unassessed/unknown eligibility/cycle status. Explain relevance through visible matched public terms or provider metadata, not an invented success score.
5. Staff selects one allowed candidate or explicitly allowed public source and requests capture. No automatic crawling of every result.
6. The screen shows actual stored content, source/version/hash, representation, capture time, coverage and warnings. Content is inert text, not trusted executable HTML.
7. A serialized capture reference is available for B2, with a clear supported-content status. Failed/partial captures remain visible.

Loading, no results, missing credentials, denied destination, quota failure and partial/empty extraction each have distinct readable states. A capture date must not be labelled deadline, publication date or reporting period.

## 4. Search adapter and normalization

Implement a SearchProvider port and Tavily adapter in the funding module; use existing project HTTP facilities where practical. Verify current official request/response fields. Initial calls use general search with explicitly bounded results, include_answer=false and no images; disable automatic depth/parameter escalation. The starting limit is five results and one provider request per explicit search, configurable downward or through documented server limits. These are this feature's budgets, not claims about vendor limits. [R01]

Keep the query short and public. A server-configured allowlist of public profile fields is the only automatic query input; do not fetch and paste private facts, family stories, grant history or secrets. Reject malformed/oversized query payloads. Do not claim pattern filtering proves a query contains no sensitive information.

Record requested/effective parameters, query/time, response status, actual provider/model-independent result identity and usage when supplied. Missing key yields provider_unavailable without a network call; an explicitly selected fixture mode uses labelled synthetic results. Live mode never silently falls back to fixture results, another vendor or higher-cost features.

Normalize URLs conservatively: case-normalize scheme/host, remove fragment and configured known tracking parameters, preserve semantic query parameters and distinct cycles/streams. Deduplicate normalized identical result URLs and exact content identities while retaining origin/query metadata. Do not merge two rounds because their titles or funder names resemble one another. Preserve the displayed original URL.

Source authority is a separate field: unreviewed, confirmed official by explicit configured profile/staff review, or other. A domain suffix, search rank or .org name alone is insufficient. A small trusted-funder/source seed configuration can be provided, labelled as a discovery seed rather than an eligible shortlist. No live deadlines are hardcoded from the earlier planning research.

Use the existing Opportunity/RequirementSet types. Any missing cycle/stage/deadline/amount field stays unknown. Optional literal extracted metadata is a candidate with its supporting text, not a reviewed eligibility rule. Full DAT/ELG evaluation is reserved for B1-DISC-002.

## 5. Capture, artifacts and source lineage

Implement a CaptureProvider port with a single-page Firecrawl adapter. Verify supported formats/fields in current official docs; request stored readable markdown plus HTML/raw representation when supported. No provider action scripts, generated summaries, recursive crawl or automatic document-following in this task. [R02]

Preserve exact returned bytes for each chosen representation with its own SHA-256, media type/encoding, size and immutable artifact ID. Store requested/original/final URL separately; unknown final redirect chains remain unknown. Record provider, actual call time, extraction warnings and partial/empty coverage. Use HTML/markdown section or offset locations tied to the exact representation; never invent PDF pages.

A representation returned by a provider is labelled provider_markdown/provider_html/provider_raw_html as appropriate. It is not asserted to be the origin server's original file bytes. Retain provider metadata needed for provenance, but never persist credentials or authorization headers in artifacts. Empty content, blocked pages, paywalls and partially extracted data cannot become successful complete evidence.

Use the existing CaptureStore. If the default implementation is unavailable, implement an isolated LocalCaptureStore under funding for development/demo use behind that port, with UUID/content-derived identifiers, server-derived organization namespaces, confined paths, atomic writes and integrity verification. Persist artifacts/metadata across a local process restart; do not call an in-memory dictionary durable storage. Its deployment capability stays development-only until A supplies the supported store. Do not add a competing knowledge/fact database or fall back from PostgreSQL to SQLite.

Coordinate any truly necessary shared protocol/schema change through the launch agreement. Prefer a funding-owned wrapper and adapter. Expose authorized metadata/content operations so B2 can consume saved HTML without refetching. Client-supplied local paths or another organization's IDs must never cause file access. Source references created here represent captures, not reviewed organizational facts.

## 6. Destination, permission and resource boundaries

Authorization precedes search, capture and reads. Use existing server-owned identity/organization context and retain baseline 401 behaviour. Keep demo identity disabled in production. Provider keys remain server-side; never return or log key values.

Only supported HTTP(S) public URLs are eligible for public capture. Reject credentials in URLs, non-web schemes, loopback/private/link-local/metadata destinations, invalid ports/host encodings and other reserved addresses under a reviewed URL policy. Validate hostname/address results and returned final destinations; bound response sizes, redirects where controlled and request duration. Do not relax this policy to enable B2's local fixture. [R03]

When a third-party capture provider makes the target request, application validation cannot prove which internal addresses it contacted or enforce its redirect/DNS behaviour. Record that trust boundary. Validate supported provider controls, reject uninspectable/unsupported results and keep the feature scoped to approved public sources. Direct-fetch implementations must enforce address/redirect checks at connection time with appropriate egress protection; do not claim a one-time URL regex prevents DNS rebinding. Report residual controls as partial rather than declaring full SEC-03 production coverage.

Search and capture are separate bounded operations. Use hard timeouts, cancellation cleanup, byte/result limits and bounded attempts. Default to no automatic retry of quota/auth/validation errors or uncertain billable capture completion. A timeout is not evidence that the vendor canceled or charged nothing; record outcome uncertainty and do not trigger background retries. Reuse scoped same-request/idempotency handling where already available. Do not create fake queued jobs when JobStore is unavailable.

Inspect/render content only as escaped text or the repo's reviewed sanitizer. No remote images/scripts or automatic link fetching. Treat retrieved instructions as data; no tool execution, approvals, source-policy promotion or message sending based on page text.

## 7. API and UI implementation shape

Use the existing funding router and ErrorEnvelope. Suggested relative operations: POST search; POST captures; GET capture metadata; GET authorized capture content; GET availability. Exact prefixes follow the actual repo. A successful bounded operation returns its actual result, not a fabricated job state. Errors distinguish invalid_input, unauthenticated/forbidden, provider_unavailable, provider_error/rate_limited, timeout/outcome_unknown, unsafe_destination, unsupported_content, extraction_empty/partial and capture_not_found/integrity_failure.

Use typed requests/results and generated TypeScript types. Search response includes provider mode, query metadata, candidate list and warnings. Capture response follows the semantic v1 seam in the launch agreement and existing SourceReference. Do not accept org/authority/approval state from an untrusted client as authoritative.

Implement the already-registered Funding page rather than a second app/navigation package. It must show availability before a request, mode labels throughout, candidate provenance and distinct capture states. Include an inspectable evidence panel and a copy/export of the capture reference. Display the exact supported content type B2 can import. Accessibility includes labelled controls, keyboard access and clear error text.

Feature availability is granular: discovery adapter implemented does not imply live-verified; provider configured does not imply a capture succeeded; captured evidence does not imply eligibility established. A/C/automation features remain unchanged and unavailable as before until their owning tasks implement them.

## 8. Checks and acceptance test matrix

Use meaningful deterministic fixtures and injected HTTP/provider responses. Default tests make no paid calls. Retain baseline check/smoke/browser checks. Record applicable catalog coverage per predicate; do not mark whole rules or the whole catalog passed from a partial adapter test.

| Test ID | Scenario / expected result | Rule references |
| --- | --- | --- |
| DISC-01 | Missing identity returns existing 401 before provider/store calls. | SEC-01, APP-05 |
| DISC-02 | Missing Tavily/Firecrawl key yields explicit unavailable; no automatic fixture substitution. | SEC-02, SEC-06 |
| DISC-03 | Fixture mode is conspicuous; normal production configuration rejects demo identity/fixture serving. | SEC-01, SEC-13 |
| DISC-04 | Query/result/timeout limits enforced; malformed input rejected before request. | JOB-03, SEC-05 |
| DISC-05 | Query builder cannot automatically draw private material from A/C ports; provider payload contains selected public fields only. | SEC-02, SEC-06 |
| DISC-06 | Same URL plus fragment/tracking duplicate collapses; meaningful query/cycle differences remain distinct. | SRC-06, DAT-03 |
| DISC-07 | No-result and unrelated/award-announcement candidates do not become eligible grants. Provider relevance is labelled. | ELG-01, DAT-03 |
| DISC-08 | Incomplete deadline/cycle/timezone remains unknown; no current/closed assessment fabricated from search dates. | DAT-01, DAT-03 |
| DISC-09 | Stored hash matches exact representation; byte tampering prevents trusted content read. | SRC-01, SRC-02 |
| DISC-10 | Stored source/locator/artifact metadata exists; same hash retains separate capture origins. | SRC-03, SRC-06, SRC-08, SRC-10 |
| DISC-11 | Empty or partial extraction stays failed/partial, not completed evidence. | SRC-05, SRC-09 |
| DISC-12 | Unsafe schemes, URL credentials, loopback/private/metadata hosts and unsafe final destinations rejected in deterministic tests. | SEC-03 |
| DISC-13 | Cross-org and traversal artifact reads rejected; raw local paths not exposed. | SEC-01, SEC-04, APP-05 |
| DISC-14 | Quota/auth/timeout/vendor malformed responses become safe errors; no unbounded or hidden retries. | JOB-03, SEC-06, SEC-10 |
| DISC-15 | Captured scripts/HTML/instruction text renders inert; no provider keys or auth headers appear in client/log output. | SEC-06, SEC-07 |
| DISC-16 | Local development capture survives restart and reopens with integrity/provenance; deployment limitation is explicit. | SRC-02, SRC-08; store-boundary coverage only |
| DISC-17 | Serialize one captured HTML record, resolve exact content and feed the B2 adapter/fixture contract without dropping IDs/hash/representation. | SRC-01, SRC-08; B1-B2 seam |
| DISC-18 | Funding page drives real API with injected provider and shows results, errors, source details and mode changes correctly. | Feature acceptance, not a new numbered truth rule |

Full date comparison, funding-window rules, semantic temporal wording, explicit amount/geography eligibility, invitation/cooldown history, release scanners and durable job recovery remain future scope. Specifically DAT-02/04/05, ELG-02/03/04 and SEC-11 are not completed by this slice. The represented/partial coverage of DAT-01/03, ELG-01, JOB-03 and SEC-03 must be stated precisely.

If credentials and explicit live-smoke opt-in are available, verify one public search and one staff-selected allowed capture within the configured budget; record timestamp, sanitized metadata and actual outcome. Otherwise report code/fixture verification complete and live verification not run. Do not create accounts or request partner credentials. Do not fabricate a cached public capture and call it live.

## 9. Completion, commits and handoff

Run actual repo check/smoke commands and targeted tests. Do not introduce an ESLint migration, framework update, new router library or database-port change. Commit coherent changes with engineering/task/rule references. Shared config or generated contract changes include a specific consumer note. No remote currently exists: create local commits and a review-ready PR description; publish only when the owner supplies an authorized target. Do not merge to main.

Produce docs/handoffs/dev-b/b1-disc-001-r1.md plus a task check-evidence table. Include: full base/head commits; actual edited paths; commands/results; provider mode/live-smoke status; local-store capability limits; implemented/partial/planned rule coverage; deviations; endpoint/schema examples; capture artifact types; storage/read adapter usage; and exact B2 action. Publish one sanitized sample capture in a fixture namespace, with authority/provenance labels, never real secrets.

Done means the narrow search/capture UI/API path and negative cases work; source lineage persists; B2 has a concrete typed saved-HTML example; and every claim about live verification/storage/security is accurately limited. Real A-store integration and the combined B2 seam can remain named integration gates, not invented completed work. Stop after this ticket and report inputs for B1-DISC-002.

## 10. Official implementation references

- R01: Tavily Search request/response documentation: https://docs.tavily.com/documentation/api-reference/endpoint/search
- R02: Firecrawl single-page scrape: https://docs.firecrawl.dev/api-reference/endpoint/scrape
- R03: OWASP SSRF prevention: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html

These references support adapter interfaces and destination-control considerations. The scope, budgets, schemas, local-store restriction and acceptance tests are this project's requirements. Verify the actual installed/provider versions and do not extrapolate a vendor response into a guarantee of source truth or network isolation.
