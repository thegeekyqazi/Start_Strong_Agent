# DEV-B-BUNDLE-002 r1: saved grant workspace and reviewed research

- Author/lane: Dev B agent (Claude Code, claude-opus-5-5) for the project owner (Dev B)
- Intended consumers: owner (review), Dev C (C2b reader, future requirement dependencies), Dev A (A3 registration, A4 dependency refs), future Dev B sessions
- UTC timestamp: 2026-11-08
- Status: ready-for-review (draft PR; **not merged**)
- Task spec: `docs/specs/DEV-B-BUNDLE-002_Saved_Grant_Workspace_and_Reviewed_Research.md` rev 1.0. It supersedes the unimplemented B2-AUTO-001A rev 1.0; no prior B2-AUTO-001A code existed.
- Engineering: v1.1 s3-7, s9, s10.1, s10.3-10.5, s12.4, s13.2-13.3, s14-16, s18-20, s22
- Decision: `docs/decisions/DEV-B-BUNDLE-002-local-repositories-versions-review.md` (developer-decision)
- Branch: `dev-b/dev-b-bundle-002`.
  - Base: `2adcdeb0d8a3059caf0d8734bff054403a5c7ffb`.
  - `origin/main` advanced to `5f52813` (A3, PRs #11/#13) and was merged into the branch at the M6 checkpoint. Only the generated files conflicted; they were regenerated, not hand-merged.
  - Head = the commit containing this note.
- PR: https://github.com/thegeekyqazi/Start_Strong_Agent/pull/12 (draft)
- Earlier notes: `bundle-002-question-reader-r1.md` (M1, posted to C2 PR #7) and `bundle-002-funding-case-reader-r1.md` (M3/M4)

## Milestones

| Milestone | Commit (subject) | Delivered |
| --- | --- | --- |
| M0 | `docs(dev-b): DEV-B-BUNDLE-002 spec and local-repository decision (M0)` | Spec committed; decision record; baseline `make check` on `2adcdeb`: 407 pytest / 54 Vitest |
| M1 | `feat(automation): saved definitions and public question reader (M1)` | Immutable saved definitions; `ApplicationDefinitionReader`; Saved definitions UI; consumer handoff + real-repository sample |
| M2 | `feat(funding): saved capture library and storage portability fixes (M2)` | Capture catalog + bounded backfill; open-by-ID; exact intake references and "Use in application intake"; no-clobber writes, durability policy, `.gitattributes` |
| M3+M4 | `feat(funding): reviewed funding cases and deterministic evaluations (M3, M4)` | Funding cases, verified anchors, version-bound review, case-context binding for saved definitions; DAT/ELG rules and saved reports. **One commit**, because evaluation is a method of the case repository. The split is by module (`cases.py` vs `rules.py`) |
| M5 | `feat(funding): saved public searches, manual reruns and source rechecks (M5)` | Saved profiles, run-now, comparisons; "Capture again and compare"; change observations; case re-review |
| M6 | regression fix, upstream merge, e2e/production tests and docs | Real-Chromium BND-50..52, BND-49, this handoff, plan update |

## Public interfaces (B-owned; shared DTOs unchanged)

| Interface | Import | Notes |
| --- | --- | --- |
| `ApplicationDefinitionReader` | `strongstart_contracts.application_publication`; factory `strongstart_api.features.automation.public` | `get_version(org, question_set_id)`, `get_current(org, definition_id)`. Envelope `b2-published-definition/1` |
| `FundingCaseReader` | `strongstart_contracts.funding_review`; factory `strongstart_api.features.funding.public` | `get_version(org, case_id, v)`, `get_current`. Envelope with digest, review, source status and projections |
| `CaptureCatalogReader` | `strongstart_contracts.discovery` (additive) | `list_captures(org, cursor, limit)`, implemented by `LocalCaptureStore` |
| `CapturedDocumentReader` | unchanged | Used for anchors and recheck |

New routes:

| Prefix | Route | Purpose |
| --- | --- | --- |
| `/api/automation` | `POST /definitions`, `GET /definitions` | Save; bounded list |
| `/api/automation` | `GET /definitions/{id}` | Current version |
| `/api/automation` | `GET /question-sets/{id}` | Exact version |
| `/api/funding` | `GET /captures` | Capture library |
| `/api/funding` | `POST/GET /cases`, `POST /cases/{id}/revisions` | Create, list, revise |
| `/api/funding` | `GET /cases/{id}`, `GET /cases/{id}/versions/{v}` | Current / exact case |
| `/api/funding` | `POST /cases/{id}/versions/{v}/review` | "Review these requirements" |
| `/api/funding` | `POST/GET /cases/{id}/evaluations` | Run / list evaluations |
| `/api/funding` | `POST/GET /searches`, `POST /searches/{id}/revisions` | Saved profiles |
| `/api/funding` | `GET /searches/{id}` | Current profile |
| `/api/funding` | `POST/GET /searches/{id}/runs`, `GET /searches/{id}/runs/{run}/compare?base=` | Run-now; history; compare |
| `/api/funding` | `POST /captures/{id}/recheck`, `GET /captures/{id}/observations` | Recheck; observation history |

New capabilities (production → `unavailable`): `automation.saved_definitions`, `funding.capture_library`, `funding.reviewed_requirements`, `funding.evaluations`, `funding.saved_searches`.

New settings: `STRONGSTART_DEV_B_STORE_DIR` and `STRONGSTART_DEV_B_STORE_ALLOW_REDUCED_DURABILITY`, both in `.env.example`.

Schema/TS were regenerated with `make contracts`. No migrations; A's head is `0005` after the merge. Zero model calls.

## Acceptance matrix (54 task-local cases; not catalog rules)

Status words:
- **tested**: positive and negative cases pass in the named tests;
- **tested (subset)**: a named limit applies;
- **pending**: needs another lane.

| IDs | Status | Tests |
| --- | --- | --- |
| BND-01 | tested | `tests/automation/test_saved_definitions.py::test_bnd01_*`; `tests/funding/test_cases.py::test_bnd01_*` (all new routes 401 before store/body access) |
| BND-02 | tested | `test_saved_definitions::test_bnd02_*`; `test_cases::test_bnd02_*`; `test_monitoring::test_bnd44_other_org_*`; `test_capture_library::test_bnd18_*` |
| BND-03 | tested | `test_saved_definitions::test_bnd03_*` (10 cases: string/float/bool versions, org/approval/actor/provenance/path extras); `test_cases::test_bnd03_*` |
| BND-04 | tested | `test_saved_definitions::test_bnd04_*` (7 paths + symlink escape); `test_cases::test_bnd04_*` |
| BND-05 | tested | 100/101 questions; 40/41 anchors; 21 rules; >2 MiB, deep, duplicate-key and NaN bodies, with no commit |
| BND-06..BND-11 | tested | `test_saved_definitions` (order/wording/locators; conflicts/unknowns; hash 409; restart; idempotency incl. lost-response replay; revisions/namespacing) |
| BND-12 | tested | Two **spawned processes**, one expected version: one commit, one conflict. Plus an API thread race |
| BND-13 | tested | Altered limit (with and without a recomputed envelope digest), raw blob, hash, mapping and redirected idempotency index: content withheld, 409 |
| BND-14 | tested | Injected failure at the version commit: 503 `store_write_failed`, nothing visible, the retry completes the same target |
| BND-15 | tested | Prose HTML / context-less form → 422 `publication_blocked` |
| BND-16 | tested | Public reader with fixture/non-fixture labels; `tests/contracts/test_application_definition_reader_contract.py` (fixture double + real producer) |
| BND-17..BND-20 | tested | `tests/funding/test_capture_library.py` (restart; bounded backfill pending→complete; pagination/scan cap; corrupt entry; exact colon reference; inert content). Web: `library.test.tsx`. Browser: BND-50 |
| BND-21 | tested (subset) | `tests/funding/test_portability.py`: `.gitattributes` `text: unset` for every protected fixture; CRLF would change hashes; per-platform durability (POSIX full; Windows refused unless opted in; others refused); cross-process no-clobber captures. **Not run on real Windows**: the Windows path is exercised by injecting `os_name` |
| BND-22..BND-27 | tested | `tests/funding/test_cases.py` (unknown context; quote/digit/range/hash/cross-org anchor failures; review only via exact digest + full key list; edit/relink stales the review and history stays; HTML-form QuestionSet via case; unlinked/declared-mismatch/stale/incomplete context held; reopen after the producer blob is deleted) |
| BND-26a..e (review follow-up) | tested | `tests/automation/test_case_binding_atomicity.py`. **26a:** publication paused (event) after context resolution, then a case revision commits → 409 `context_changed`, no definition stored. **26b:** while publication holds the pin, a revision thread is observed (through the store's `set_lock_observer` hook) to attempt the case lock and be refused (`blocked`); it has neither acquired nor finished while the pin is held; after release it records `acquired_after_wait` and commits v2, and the publication is bound to v1. **26c:** the same with a spawned process, using `multiprocessing.Event`s set by the child's observer and a blocking `Queue.get` for the result. **26d:** a committed idempotent publication replays (200, same version) after the case changed. **26e:** stale digest under the pin → conflict. Mutation checks: guard disabled → 26a/b fail; pin lock disabled (`VersionCollection.locked` → no-op) → 26b and 26c fail with "never contended for the lock" |
| BND-28..BND-38 | tested | `tests/funding/test_rules.py`, 30 tests (before/at/after with inclusive/exclusive/unstated; date-only/rolling; DST fall-back with/without fold, spring-forward gap, inconsistent offset; EOI vs full and cycle vs stream exclusion; window endpoints; Decimal N±1 and 0.01; currency/scale; pool/matching never a cap; exact membership; any/all; invitation evidence; all-of and reviewed n/a) |
| BND-39, BND-40 | tested | `test_cases::test_bnd39_*`, `test_bnd40_*` (scenario "met" leaves RequirementSet `unknown`, reliance not confirmed, nothing written to A's store; reports reproduce digest/results; four answers present) |
| BND-41..BND-48 | tested | `tests/funding/test_monitoring.py` (public-only query preview equals the sent query; one call, no retry, free replay; unavailable/failed kept; normalized-URL comparison; version/failure not comparable; new capture leaves old bytes, private destination refused before the provider call; match/changed/partial/not-comparable; linked re-review + stale history; no rule/approval rewrite) |
| BND-49 | tested | `tests/funding/test_production_boundary.py`: every new route 503, nothing written, capabilities `unavailable` |
| BND-50..BND-52 | tested | `tests/browser/test_dev_b_bundle_e2e.py`: real Chromium against the real API process, 0 external requests, 0 page errors, no script execution |
| BND-53 | tested | Full suites green on the merged tree: B1/B2 e2e, INIT, C2 and A3 tests, and smoke with migrations through `0005` |
| BND-54 | tested (producer) / **pending (consumer)** | Consumer-shaped contract test runs against the fixture double and the real repository. **C's editor integration is not claimed**; C2b has not consumed the reader |

Catalog statuses in `StrongStart_Check_Catalog.json` are **unchanged** by this bundle. The tested subsets are DAT-01..04 and ELG-01..04. DAT-05, AUT-02/03, SEC-08 action grants, SEC-11 and global JOB guarantees stay outside the bundle.

## Validation (final, merged tree)

| Command | Result |
| --- | --- |
| `make check` | exit 0: ruff/format/oxlint/Prettier; mypy strict 160 files; pytest **602 passed**, 26 deselected (597 before the atomic-binding follow-up); Vitest **70 passed**; contracts drift clean; build |
| `make smoke` (local PG 17 on 127.0.0.1:55432; `STRONGSTART_DATABASE_URL` from `.env.example` for that command only) | exit 0: 87 + 10 passed; live 200; ready 200 at `0005_validation_receipts` |
| `make browser-smoke` | exit 0, **16 passed** (13 existing + 3 new) |
| Live Tavily/Firecrawl | **not run**: this worktree has no `.env` with provider keys. All provider evidence is fixtures or HTTP-free doubles |

### Failures retained (not erased by later green runs)

1. **PR CI run `42459206191`** (after M1): `ruff format --check` failed on Python code blocks inside the M1 Markdown handoff. It was fixed in the M2 commit.
2. **PR CI run `42460894616`** (commit `ca3edc6`), browser readiness: `test_funding_page_without_identity` found two "Not signed in" alerts because each new saved-data section raised its own. The fix (`fix(funding): one sign-in notice ...`) mounts those sections only for a signed-in identity. It also makes two pre-existing substring locators (`Search` button, `Geography (optional)` label) `exact=True`, because the spec-named "Run search now" button and the saved-search geography label also matched them. The locators became more precise, not weaker.
3. **PR CI run `42461376244`** (commit `3bb3b37`, M5), browser readiness: the existing fixture-flow e2e hit strict-mode violations on `get_by_label("Geography (optional)")` and `get_by_role("button", name="Search")`. The fix is the same commit as item 2.
4. Final head CI run `42462167243`: all five jobs passed.
5. Found by tests during M4 and fixed: same-zone `datetime` comparison ignores `fold`, which made a DST-ambiguous cutoff compare wrongly. Deadline instants are now compared in UTC (BND-30 covers both folds).

### Correction to an earlier claim

The first version of BND-26b/c (commit `e007a7d`) used `time.sleep(0.5)`/`time.sleep(1.5)`, `Future.done()` and `Queue.empty()` to infer that the competing writer was blocked. My report then said sleeps did not decide those outcomes, and **that was wrong**: a slow worker could have passed without ever contending for the lock. Both tests now synchronize on real lock-contention events emitted by the store's lock loop (`blocked`, then `acquired_after_wait`), with no sleeps and no `Queue.empty()`. They are shown to fail when the pin's lock is disabled.

### Local side effects

- `make smoke` upgraded the shared local development database (`strongstart-postgres-1`) from `0002` to `0005` using Dev A's merged migrations. Nothing was reset, and the bundle adds no migrations.
- This worktree has `node_modules`/`.venv` and per-test temporary stores only.

## Manual rehearsal (spec s12)

The rehearsal was executed by **automated Chromium scripts and API tests** driving the real UI/API with fixture providers, not by a human.

| Step | Where | Result |
| --- | --- | --- |
| 1-2 | API process with fixture identity/providers; migrate/seed in `make smoke` | done |
| 3 | BND-50: capture, navigate away + reload, found in Saved captures, inert text, exact `capture_id:artifact_id` copied/handed off | done |
| 4 | BND-50: nine-question fixture saved, reloaded, reopened with conflict/evidence; question-set ID shown and copyable | done |
| 5 | BND-50 (form capture without context → `publication_blocked`); BND-26 API (complete case → versioned definition) | done (context completion via API test, not browser) |
| 6 | BND-51 (anchored amount rule reviewed; missing input unknown; 120,000 vs 100,000; "funder eligibility is not confirmed"). Geography, invitation and DST via API/unit BND-30/36/37 | done (DST not in browser) |
| 7 | BND-52: saved profile run twice, compared, absence not treated as closure | done |
| 8 | BND-52 (unchanged then changed observation in the browser); BND-47 API (linked case re-review, history stale and unchanged) | done (case re-review via API) |
| 9 | Not exercised in the browser. C2b is not merged, so Applications still uses its own fixture. Automation capabilities still show approved prefill `not_implemented` and final submission `unavailable` | honest status only |

## Deviations, limitations and platform/storage notes

- Local repositories follow decision s2. They are POSIX-durable, Windows only with an explicit reduced-durability opt-in, and disabled in production. A digest is an integrity identity, not a signature.
- **Concurrent same-key provider calls.** Search runs and rechecks check for a completed replay before the provider call. Two simultaneous requests with the *same new* key could both call the provider once; only one record commits. A JobStore lease would remove this.
- **Context binding is atomic** (review follow-up). The case current-version/digest check runs under the funding-case store's cross-process lock, and the definition commits inside it (decision update 2026-11-08). The earlier check-then-commit window is closed. Committed idempotent replays are returned before any context check.
- **Lock order** is cases → definitions; a case writer may wait briefly (bounded) while a definition commit holds the pin.
- **Review is not required for binding.** Binding a case version into a definition needs an established opportunity identity, not a review. `binding.case_review_status` records which applies.
- **Fixture rotation.** The "updates" fixture rotates per API process: unchanged → changed → partial. It is labelled FIXTURE and never used live.
- **A3 registration (pending).** A3 merged with a closed, A-owned SRC registry and no extension point for other lanes. B's DAT/ELG predicates (`features/funding/rules.py`) return compatible `ValidationResult`s. Registering them needs an A-side registry change and is proposed below; no A file was edited.
- **Unaffected work.** B2-AUTO-002 (approved prefill/read-back) was **not started**. DAT-05 is not addressed.

## Consumer action / blockers

- **Dev C (C2b):** consume `ApplicationDefinitionReader` per the M1 handoff. Acknowledge the port name and format on PR #12 or #7. B+C G1 is pending until C's editor reads the producer, and full G1 also needs A evidence. Later, bind requirement versions via `FundingCaseReader` (digest + version) as answer dependencies.
- **Dev A (A3/A4):**
  - decide whether A3's registry accepts B rule modules (DAT-01..04, ELG-01..04), or publish an extension point;
  - A4 can key on case version digests, change-observation IDs and saved-definition question-set IDs.
  - Still owed by Dev B, not done here: A's request for an independent review of A3's SRC fixtures.
- **Owner:**
  - review PR #12 (draft; do not merge without your policy);
  - set `STRONGSTART_DEV_B_STORE_DIR` if a different location is wanted;
  - add a `.env` with provider keys for a live smoke if desired.
- **Next Dev B tasks:**
  - B2-AUTO-002 (needs C3's real resolver);
  - B1-DISC-002 remainder (durable scheduled monitoring after a JobStore exists; evidence-backed inputs after A's fact mapping);
  - B1-OPS-001 (deployment/release).

## Acknowledgments

- M1 notice posted on C2 PR #7: https://github.com/thegeekyqazi/Start_Strong_Agent/pull/7#issuecomment-6718774577.
- A3 registration ask posted on PR #13: https://github.com/thegeekyqazi/Start_Strong_Agent/pull/13#issuecomment-6719153735.
- No consumer acknowledgment yet.
