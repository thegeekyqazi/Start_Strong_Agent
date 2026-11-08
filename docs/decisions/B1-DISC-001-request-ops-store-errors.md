# B1-DISC-001: Request-bound operations, development-only capture store and funding error reasons

- Author/developer: B1 agent (Claude Code) for Dev B
- Date: 2026-11-07
- Status: developer-decision. Items 3, 5 and 6 touch shared files and are flagged for consumer acknowledgment.
- Decided/accepted by and evidence: B1 agent within B1-DISC-001 rev 1.0 s1 discretion and launch agreement s4. Not yet reviewed by the owner.
- Engineering path/version/sections: `docs/engineering/StrongStart_Engineering_Plan.md` v1.1, s2, s5, s14, s15, s22
- Feature spec path/revision: `docs/specs/B1-DISC-001_Funding_Discovery_and_Capture.md` rev 1.0 (s5, s6, s7)
- PR / Issue: see handoff `docs/handoffs/dev-b/b1-disc-001-r1.md`
- Supersedes / superseded by: none

## Original requirements

- Engineering s14: long operations (e.g. `POST /discovery/jobs`) return 202 and a durable job ID. Launch agreement s4 allows bounded request-based operations while JobStore is unavailable, as a recorded deviation.
- Spec s5: use the existing `CaptureStore`, or an isolated development `LocalCaptureStore` behind that port if the default is unavailable.
- Spec s7: errors distinguish invalid_input, provider_unavailable, rate_limited, timeout/outcome_unknown, unsafe_destination, unsupported_content, extraction_empty, capture_not_found/integrity_failure, and so on.

## Decisions

1. **Request-bound search and capture.** `POST /api/funding/search` and `POST /api/funding/captures` run synchronously with hard timeouts and byte caps. Each makes one provider request and no retries, then returns the actual result or a typed failure. There are no fake queued jobs, no background tasks and no process-local job map. `POST /api/funding/discovery-jobs` remains an explicit 501. *Tradeoff:* a slow capture holds a worker thread for up to `funding_capture_timeout_seconds` (45 s default, 120 s max). That is acceptable for staff-initiated single captures; durable jobs replace it later.
2. **Development-only `LocalCaptureStore`.** The default `CaptureStore` is `UnconfiguredCaptureStore`. The shared `CaptureStore.put/get` signature has no organization parameter, so implementing it directly would be organization-unscoped. Instead:
   - the funding-owned store exposes the B1-owned `CapturedDocumentReader` port (`strongstart_contracts.discovery`), scoped by the server-derived organization;
   - it persists to `funding_capture_store_dir` (`.local-data/funding-captures`, per worktree, git-ignored);
   - records are immutable, bytes are content-addressed, writes are atomic and every read is hash-verified;
   - it is disabled when `environment=production`.

   The shared `CaptureStore` protocol and `SourceReference` are unchanged. Dev A's real artifact store replaces this; the reader port is the migration seam.
3. **Funding error reasons ride in `ErrorEnvelope.details.reason`.** The shared `ErrorCode` enum is marked `frozen`, so I did not extend it. Each funding failure uses the closest existing code and HTTP status. The precise `FundingErrorReason` goes in `details.reason`, along with `outcome_uncertain`/`retried`/`capture_id` where relevant. `capture_not_found` deliberately returns 404 for both missing and other-organization captures. *Alternative:* add codes to the shared enum, which needs a proposed-cross-module change.
4. **Candidates are not `Opportunity` records yet.** `Opportunity` requires `funder_id`, `stream_id` and `cycle_id`, which a search result does not establish. Fabricating them would violate DAT-03. Candidates therefore remain `SearchCandidate` (unassessed). A capture can carry optional staff-supplied opportunity/stream/cycle IDs. Creating `Opportunity`/`RequirementSet` records from reviewed captures is B1-DISC-002 scope.
5. **Funding settings live in the shared `Settings`** (`funding_*` fields; B1 coordinates common config per launch agreement s2). This keeps one override path for tests and lets settings validation reject fixture providers in production, alongside the existing fixture-identity rule.
6. **`feature_capabilities(settings)` hook** in `strongstart_api/features/__init__.py`. A feature module may expose `capabilities_for(settings)` so `/api/capabilities` reports runtime status. Funding reports `unavailable`, `fixture_only` or `available`; it is never "available" without keys. Modules without the hook keep their static `CAPABILITIES`. This is backward compatible; `FEATURE_CAPABILITIES` is still exported.
7. **Firecrawl request choices.**
   - `formats=["markdown","html","rawHtml"]` with `onlyMainContent=true`.
   - `maxAge=0`, so the capture is fresh and `captured_at` is truthful.
   - `storeInCache=false` (data protection).
   - `proxy="basic"`, so there is no automatic escalation.
   - `parsers=[]`, so there is no per-page PDF/OCR billing. PDFs are rejected as unsupported.
   - No `actions`.
   - Tavily: `search_depth=basic`, `auto_parameters=false`, `include_answer=false` and no images or raw content.
8. **Authority** is `confirmed_official` only by exact host match in a configured discovery seed. In live mode the seed is empty unless `STRONGSTART_FUNDING_SOURCE_SEED_PATH` is set. A domain suffix, rank or page text never sets authority.
9. **Search dedup** collapses only identical normalized URLs. Identical title+excerpt at different URLs is flagged `possible_duplicate_of`, not merged, so distinct rounds are never combined. Identical capture bytes share one blob while each capture keeps its own origin record (SRC-06).

## Impact and coordination

- **B2:** consume `CapturedDocument` plus `CapturedDocumentReader.read_artifact()`. Only `provider_html`/`provider_raw_html` are listed in `supported_import_representations`. There is no URL refetch.
- **A:** the real store should implement `CapturedDocumentReader` (or an agreed successor), with organization scoping and verification. The reader port should be preserved when the dev store is replaced.
- **C:** `/api/capabilities` now includes runtime funding status. The shell needs no change.
- **All:** run `make contracts` after rebasing. Generated TS gains `Opportunity.title`, which was dropped by an INIT-001 generator bug fixed here.

## Validation and rollback

Validated by `tests/funding/*` (DISC-01..17), `tests/browser/test_funding_e2e.py` (DISC-18), `make check`, `make smoke` and `make browser-smoke`. To roll back, revert the B1-DISC-001 commits. The shared edits are additive: settings fields, the capability hook and the httpx runtime dependency.
