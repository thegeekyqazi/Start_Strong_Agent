# B1-DISC-001: Funding discovery and source-capture slice (r1)

- Author/lane: Dev B / B1 agent (Claude Code, claude-opus-5-5)
- Intended consumers: B2 (capture seam), Dev A (store replacement), Dev C (shell/capabilities), the project owner
- UTC timestamp: 2026-11-08T02:45Z
- Status: ready-for-review
- Task spec path/revision: `docs/specs/B1-DISC-001_Funding_Discovery_and_Capture.md` rev 1.0; agreement `docs/coordination/b1-b2-parallel-launch.md` rev 1.0
- Engineering version/sections and rule IDs: v1.1, s4-6, 10.1, 10.3-10.4, 12.4, 14-15, 18, 22. Rule coverage is in the evidence table below.
- Branch: `dev-b/b1-disc-001` (worktree `../strongstart-b1`)
- Base commit: `ad5b8dd10a4104ce3442c5788c3ed87f0c54a9da` (accepted INIT-001; identical to `origin/main` at task start)
- Implementation head: `8f834549a598c07580e352c7d8cfa8129576b61b`. This handoff is the next commit on the branch; a file cannot contain its own SHA.
  - `b5708de88a2743e347fe7be5839a2f902ff3b13d` docs: spec and launch agreement
  - `1c58ad96796d4d6ec11fdfda73343f8c18837bf1` contracts and TS generator fix
  - `1b2c5a2da18efb00e4e5b2a45ee95c7c1563624b` funding API, adapters, store, tests and fixtures
  - `8f834549a598c07580e352c7d8cfa8129576b61b` Funding page, browser e2e, Makefile/CI
- PR / Issue links: draft PR from `dev-b/b1-disc-001` into `main` on github.com/thegeekyqazi/Start_Strong_Agent (see "Publication")
- Supersedes / superseded by: none

## What works

Staff open **Find Funding** (the existing registered page) and see identity, provider and mode availability, with limits, before any request. They run a bounded public search built only from allowlisted public profile fields:
- interests (up to 5 terms);
- optional geography and program context;
- the fixed suffix "grant funding".

The page shows:
- the query text, provider, mode and completion time;
- candidates with original and normalized URL, the provider excerpt (labelled unverified) and source authority;
- matched public terms, and the provider relevance score labelled as a ranking signal only;
- the provider date estimate, labelled "not a deadline";
- collapsed duplicates and omitted results, each with a reason.

Eligibility is always **unassessed**; cycle status and deadline are always **unknown**.

Staff then capture one selected candidate or a manually entered public URL. The evidence panel shows:
- capture/source/version IDs and the requested and final URL;
- capture time (labelled as capture time only);
- provider and mode, coverage and warnings;
- each stored representation's bytes and SHA-256, with integrity-verified content shown as **inert text**.

The panel also offers a copy/download of the capture reference JSON for B2. Every failure reason has its own readable state.

**Provider mode / live status**
- Live adapters: Tavily search and Firecrawl v2 single-page scrape. Both are implemented and tested with injected HTTP only.
- **Live verification: NOT RUN.** No project credentials are configured, and the spec requires explicit opt-in.
- Fixture mode (`STRONGSTART_FUNDING_SEARCH_MODE=fixture`, `..._CAPTURE_MODE=fixture`) serves labelled synthetic `.example` data. It is rejected in production. Live mode never falls back to fixtures.

**Storage**
- `LocalCaptureStore` is **development-only**. It persists in this checkout at `.local-data/funding-captures` (configurable, git-ignored) and survives restarts.
- It is disabled in production, where capture returns `store_unavailable`.
- It is not Dev A's supported artifact store.

## Endpoint mapping (spec s7 → actual)

| Spec label | Route | Auth | Success | Notes |
| --- | --- | --- | --- | --- |
| availability | `GET /api/funding/availability` | none (reports auth state) | 200 `FundingAvailability` | No provider calls; booleans only, never key values |
| (status) | `GET /api/funding/status` | none | 200 `Capability[]` | Same runtime status as `/api/capabilities` |
| search | `POST /api/funding/search` | required | 200 `SearchResult` | Body `SearchRequest`; `max_results` ≤ min(5, server limit) |
| captures | `POST /api/funding/captures` | required | 201 `CapturedDocument` | Body `CaptureRequest` (`url`, optional candidate/search/opportunity/stream/cycle IDs) |
| capture metadata | `GET /api/funding/captures/{capture_id}` | required | 200 `CapturedDocument` | Org-scoped |
| capture content | `GET /api/funding/captures/{capture_id}/artifacts/{artifact_id}/content` | required | 200 `CaptureContent` (JSON string `text`) | Hash re-verified on every read |
| (durable jobs) | `POST /api/funding/discovery-jobs` | required | 501 `not_implemented` | Future (needs JobStore) |

Errors are always an `ErrorEnvelope`. The funding reason is in `details.reason`:

| Reason | HTTP | Code |
| --- | --- | --- |
| `invalid_input` | 422 | |
| `provider_unavailable`, `store_unavailable` | 503 | `capability_unavailable` |
| `provider_error`, `provider_auth_rejected` | 502 | |
| `rate_limited`, `quota_exceeded` | 429 | |
| `timeout`, `outcome_unknown` | 504 | |
| `unsafe_destination` | 422 | `forbidden` |
| `unsupported_content`, `source_http_error` | 422 | |
| `extraction_empty` | 422 | (`details.capture_id` of the recorded empty capture) |
| `capture_not_found` | 404 | (also returned for other-organization captures) |
| `integrity_failure` | 500 | |

Provider failures add `details.retried=false` and `details.outcome_uncertain`. Missing identity returns the existing 401 `unauthenticated`, resolved before any provider or store access.

## Contracts and dependencies

New B1-owned module `packages/contracts/python/src/strongstart_contracts/discovery.py` (exported to JSON Schema/TS; all `draft`, `x-owner: B1`):
- search types: `SearchProfile`, `SearchRequest`, `SearchQueryRecord`, `SearchCandidate`, `CandidateDuplicate`, `OmittedResult`, `SearchResult`;
- capture types: `CaptureRequest`, `CaptureArtifact`, `SectionLocator`, `CapturedDocument` (semantic v1 seam), `CaptureContent`;
- availability types: `ProviderAvailability`, `FundingAvailability`;
- `FundingErrorReason`;
- the in-process port `CapturedDocumentReader` (`get_record(org, capture_id)`, `read_artifact(org, capture_id, artifact_id) -> VerifiedArtifact`), with `CaptureNotFoundError` and `CaptureIntegrityError`.

Shared signatures (`SourceReference`, `CaptureStore`, `ErrorEnvelope`, `ErrorCode`) are **unchanged**.

**Capture artifact types**
- `provider_markdown` (`text/markdown`, heading char-offset locators): read-only context, not B2-importable.
- `provider_html` (`text/html`, main content): B2-importable.
- `provider_raw_html` (`text/html`, provider-returned full page): B2-importable.
- None of these is asserted to be the origin server's original bytes. There are no PDF page locators.

Trimmed example (from `tests/fixtures/funding/sample-capture-v1/record.json`, FIXTURE):

```json
{
  "schema_version": "1",
  "capture_id": "cap-7ee0a0bfa1e245f395cde11fb70c87d2",
  "organization_id": "demo-org",
  "requested_url": "https://demo-funder.example/programs/community-grants",
  "final_url": "https://demo-funder.example/programs/community-grants",
  "final_url_status": "provider_reported",
  "redirect_chain": "unknown",
  "provider": "fixture-capture", "provider_mode": "fixture",
  "captured_at": "2026-11-08T02:18:57.627856Z",
  "coverage": "complete",
  "authority_review": "confirmed_official",
  "artifacts": [
    {"artifact_id": "cap-7ee0...-markdown", "representation": "provider_markdown", "size_bytes": 419, "sha256": "20331fcd...", "b2_importable": false},
    {"artifact_id": "cap-7ee0...-html", "representation": "provider_html", "size_bytes": 725, "sha256": "093dd3d8...", "b2_importable": true},
    {"artifact_id": "cap-7ee0...-raw-html", "representation": "provider_raw_html", "size_bytes": 1300, "sha256": "e212379e...", "b2_importable": true}
  ],
  "source_reference": {"source_id": "web-4eac66401a73d11f3ce283a1", "source_version_id": "cap-7ee0a0bfa1e245f395cde11fb70c87d2",
                       "content_hash": "093dd3d8...", "publication_date": {"status": "unknown", "value": null}},
  "supported_import_representations": ["provider_html", "provider_raw_html"],
  "storage_capability": "development_local_store",
  "provenance": {"provenance_class": "simulated", "is_simulated": true}
}
```

The full sample (record plus exact artifact bytes) is in `tests/fixtures/funding/sample-capture-v1/` (see its README).

**Storage/read adapter usage (B2, in-process)**

```python
from strongstart_api.features.funding.deps import get_capture_store   # FastAPI dependency
store = get_capture_store(settings)            # LocalCaptureStore | None (None in production)
record = store.get_record(identity.organization_id, capture_id)      # CapturedDocument
art = next(a for a in record.artifacts if a.representation == "provider_html")
verified = store.read_artifact(identity.organization_id, capture_id, art.artifact_id)
html_bytes = verified.content   # sha256 already re-verified; raises CaptureIntegrityError otherwise
```

Always pass the **server-derived** organization. A client-attested record is only a pointer: re-read it through the port.

**Shared changes**, coordinated by B1 per launch agreement s2. Consumer action is noted where needed.
- `Settings`: new `funding_*` fields, documented in `.env.example`. Production rejects funding fixture modes.
- `services/api/pyproject.toml`: `httpx` promoted to an API runtime dependency. It was already locked at 0.28.1; `uv.lock` changed by 2 lines.
- `features/__init__.py` + `app.py`: `feature_capabilities(settings)` hook, which is backward compatible.
- `tests/unit/test_api.py`: the INIT baseline now expects funding `unavailable` without keys, instead of `not_implemented`.
- `Makefile` `browser-smoke` builds web first; the CI browser job adds Node and `npm ci`.
- `.gitignore`: `.local-data/`.
- **TS generator bug fix** (INIT-001): properties named `title` were dropped. Generated TS now includes `Opportunity.title`. **Everyone: run `make contracts` after rebasing.**

## Validation (2026-11-07, worktree `strongstart-b1`)

| Command | Result |
| --- | --- |
| `make check` | exit 0: ruff, ruff-format, oxlint, Prettier clean; mypy strict 0 issues/66 files; **pytest 204 passed** (6 deselected db/browser); **Vitest 19 passed**; contracts drift clean; web + wheels built (wheel includes `fixture_data/`) |
| `make smoke` | exit 0: 36 import tests + 2 db tests passed; real API live 200 / ready 200 (`0001_bootstrap`) |
| `make browser-smoke` | exit 0: **4 passed** (INIT fixture read-back + 3 Funding e2e: fixture flow, live-without-keys, no-identity); Chromium 156.0.8078.4 |
| Live provider smoke | **not run**: no project credentials and no opt-in. Not substituted |

No migrations were added; the shared DB was only migrated/seeded idempotently by `make smoke`.

### Task check evidence (DISC matrix → rule predicates)

Statuses: **implemented-tested** (predicate in code, with positive/negative tests); **partial** (part of the rule covered, gap named); **planned** (not covered).

| Test ID | Test location | Rule refs | Status / exact coverage |
| --- | --- | --- | --- |
| DISC-01 | `test_funding_api.py::test_disc01_*` | SEC-01, APP-05 | **partial**: 401 before provider/store calls on all 5 funding routes (including a malformed body). Identity is the INIT fixture/none mode, not real authentication |
| DISC-02 | `test_disc02_*`, `test_providers.py` | SEC-02, SEC-06 | **partial**: missing key → `provider_unavailable`, no request, no fixture fallback; key canary absent from availability, status, capabilities and OpenAPI. No data-class routing engine |
| DISC-03 | `test_disc03_*` | SEC-01, SEC-13 | **implemented-tested** for configuration: production rejects fixture identity and fixture providers and disables the dev store; fixture output is labelled |
| DISC-04 | `test_disc04_*`, `test_normalize.py` | JOB-03, SEC-05 | **partial** (JOB-03): result cap, single request, timeouts, byte caps, no retries, uncertain-outcome reporting. No token budgets or cancellation (no jobs) |
| DISC-05 | `test_disc05_*`, `test_query_builder_has_no_access_to_private_ports` | SEC-02, SEC-06 | **implemented-tested** for the query builder: only allowlisted profile fields; extra fields rejected; no port access |
| DISC-06 | `test_disc06_*`, `test_normalize.py` | SRC-06, DAT-03 | **partial**: URL dedup (fragment/tracking/case/port) keeps `?cycle=`/path differences and the displayed original URL. No funder/stream/cycle identity model yet (B1-DISC-002) |
| DISC-07 | `test_disc07_*` | ELG-01, DAT-03 | **partial** (ELG-01): every candidate is `unassessed`, and the announcement page is not promoted. No eligibility predicates exist yet |
| DISC-08 | `test_disc07_08_*`, `test_disc08_*` | DAT-01, DAT-03 | **partial** (DAT-01): deadline and publication date stay `unknown`; provider date and capture time are never labelled as a deadline. No deadline parsing/timezone logic (B1-DISC-002) |
| DISC-09 | `test_disc09_10_16_*`, `test_store.py` | SRC-01, SRC-02 | **implemented-tested** (store boundary): exact-byte SHA-256; a one-byte tamper → `integrity_failure`, content withheld; unknown IDs fail |
| DISC-10 | `test_disc09_10_16_*`, `test_disc10_*` | SRC-03, SRC-06, SRC-08, SRC-10 | **partial**: same bytes at two URLs → one blob, two origin records; pipeline version, provider, params, capture time and warnings recorded. SRC-03 covers markdown heading offsets only, not a page/section inventory resolver |
| DISC-11 | `test_disc11_*` | SRC-05, SRC-09 | **implemented-tested** for capture: empty → `extraction_empty` (recorded, not evidence); missing/oversize representation → `partial`; HTTP ≥400 / PDF never stored as evidence. SRC-09 page-count coverage is not applicable to HTML |
| DISC-12 | `test_url_policy.py`, `test_disc12_*` | SEC-03 | **partial**: schemes, credentials, ports, encoded IPs, private/loopback/link-local/metadata/CGNAT/IPv6 forms, DNS results and the provider-reported final URL are all checked. **Residual:** the provider performs the fetch, and there is no connection-time egress control or DNS-rebinding defence |
| DISC-13 | `test_disc13_*`, `test_store.py` | SEC-01, SEC-04, APP-05 | **implemented-tested** (store boundary): other-org reads → 404; traversal IDs → 404; hashed org dirs; confined paths; no local paths in responses |
| DISC-14 | `test_providers.py`, `test_disc14_*` | JOB-03, SEC-06, SEC-10 | **partial**: auth/rate/quota/5xx/malformed/timeout → typed safe errors, exactly 1 attempt, and no key in messages or logs. No audit-completeness store (SEC-10) |
| DISC-15 | `test_disc15_*`, Vitest, e2e | SEC-06, SEC-07 | **partial** (SEC-07): content served as JSON strings and rendered as React text; e2e confirms no script execution and no external requests (tracker). Page instructions don't change authority. No sanitizer/rich preview exists, by design |
| DISC-16 | `test_disc09_10_16_*`, `test_store.py` | SRC-02, SRC-08 | **implemented-tested** (store-boundary coverage only): a new app instance reopens records with integrity; atomic writes; immutable records. Development-only |
| DISC-17 | `test_disc17_*`, `tests/fixtures/funding/sample-capture-v1` | SRC-01, SRC-08 | **implemented-tested**, contract-level: serialized record → reader → exact verified HTML parsed by a stand-in consumer. The real B2 importer is a G1 integration gate (not done) |
| DISC-18 | `tests/browser/test_funding_e2e.py`, `Page.test.tsx` | feature acceptance | **implemented-tested** with fixture providers through the real API process |

Not covered in this slice (still **planned**): DAT-02, DAT-04, DAT-05, ELG-02, ELG-03, ELG-04, SEC-11 (no scanners/release policy), JOB-04/05 (durable jobs and validation caches). Catalog statuses are unchanged: all 86 rules remain `planned` in `StrongStart_Check_Catalog.json`.

## Decisions and deviations

`docs/decisions/B1-DISC-001-request-ops-store-errors.md` (developer-decision) covers:
- request-bound operations instead of engineering s14 job routes;
- the development-only local store and reader port in place of the org-less `CaptureStore` protocol;
- funding reasons carried in `details` (the frozen `ErrorCode` is unchanged);
- candidates not yet being `Opportunity` records;
- funding settings in the shared `Settings`, and the capability hook;
- the Firecrawl/Tavily parameter choices, the authority seed rule and the dedup policy.

## Consumer action / blockers

- **B2 (action):**
  1. Import `tests/fixtures/funding/sample-capture-v1` through your real importer via `CapturedDocumentReader` (load it with `LocalCaptureStore.save`, as in `tests/funding/test_store.py`).
  2. Preserve `capture_id`, `source_reference.{source_id,source_version_id,content_hash}`, `artifacts[].{artifact_id,sha256,representation}` and `organization_id`. Accept only `supported_import_representations`.
  3. Treat `provider_markdown` as read-only context.
  4. After B1 merges, rebase, run `make contracts`, and acknowledge the version read (`CapturedDocument` schema_version "1", commit `1c58ad96796d4d6ec11fdfda73343f8c18837bf1`).
- **A:** the replacement store must keep organization-scoped `CapturedDocumentReader` semantics (unknown and other-org IDs indistinguishable; verify the hash on read). Consider whether the shared `CaptureStore` protocol should gain an organization parameter (a cross-module proposal, not done here).
- **C:** no action required. `/api/capabilities` now reports runtime funding status.
- **Owner:** to run a live smoke, set `STRONGSTART_TAVILY_API_KEY`/`STRONGSTART_FIRECRAWL_API_KEY` in this worktree's `.env` and explicitly opt in. Budget: one search (≤5 results, basic depth) and one capture.
- **Blockers:** no real artifact store (A), no JobStore, and live verification is pending credentials. The G1 seam with B2's real importer is not yet joined.

## Inputs for B1-DISC-002

- Captured guideline records (this slice) as the evidence source for deadline/eligibility predicates (DAT-01..05, ELG-01..04) with a frozen clock and IANA timezones.
- A staff review step: candidate/capture → `Opportunity`/`RequirementSet` with confirmed funder/stream/cycle/stage IDs (the decision in item 4).
- A real query profile and watchlist store, plus repeat search and change detection (SRC-07), once a JobStore exists.
- A configured official-source seed file (`STRONGSTART_FUNDING_SOURCE_SEED_PATH`) reviewed by staff.
- A live-smoke result, if credentials are supplied.

## Publication

The branch `dev-b/b1-disc-001` is pushed to `origin` (github.com/thegeekyqazi/Start_Strong_Agent) as a **draft PR into `main`**, following AGENTS.md. It is not merged; merging follows the owner's review policy. The B1 and B2 agents share the owner's GitHub identity, so a review by the B2 agent is not an independent approval.

## Acknowledgments

None yet.
