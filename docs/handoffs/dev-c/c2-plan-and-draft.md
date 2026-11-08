# C2: Plan and draft answers with claim bindings and visible findings (r1)

- Author/lane: Dev C agent (Claude Code, claude-opus-5-5)
- Intended consumers: project owner (review), Dev A, Dev B2, C3 (next task)
- UTC timestamp: 2026-11-08
- Status: ready-for-review. **Fixture-complete only**: real producers are not joined (G1 not reached)
- Task spec: `docs/specs/C2-draft-claims.md` rev 1.2 (s12 implementation notes, commit `cf52da5`)
- Engineering: v1.1 s7, 8.1-8.3, 9.1-9.2, 10.5, 10.6, 13.2, 14, 15, 18, 20.3. Rules: APP-01, APP-02, APP-03, POL-01, POL-02, POL-03, SEC-12; APP-05 boundary (catalog statuses unchanged: `planned`)
- Branch: `dev-c/c2-draft-claims` (pushed), **stacked** on `dev-c/c1-shell-and-adapter`. Merge order: C1, then C2 rebased onto `main`
- Implementation commits:

  | Commit | Contents |
  | --- | --- |
  | `51da7ee` | Spec 1.0 |
  | `8c64154` | Decisions (rev 1.1) and the A request |
  | `23cdaa2` | Contracts |
  | `124f9cf` | API rules and tests |
  | `04ad681` | Web |
  | `cf52da5` | Spec notes |
  
  This note is the next commit.
- PR / Issue: no PR yet (pushing the branch was authorized; a PR needs owner instruction)

## What works

### Highest priority: APP-03 unbound-number scanner (closes the C1 QA gap)

Every digit run in the answer, as a funder would read it, must sit inside a server-rendered fact binding or match a narrow typed exception:
- ISO dates and periods;
- a year after a time cue word ("in 2025", "FY 2024");
- question or section references ("Question 3", "#4");
- digits glued to a letter ("Q3").

Everything else is **unbound**, e.g. "500 children", "50%", "$1,200", "2025 children" or "3rd": `needs_review` in working mode, `fail` in reviewed mode. Draft proposals now carry these findings, so "We served 500 children in 2025." from a model is flagged at once (500 flagged, 2025 treated as a date).

Further APP-03 behaviour:
- Written-out numbers ("five hundred") go to review.
- Raw figures next to a citation are still unbound ("citation presence alone is not support").
- Bindings to unverified facts are `needs_review`.
- Unknown or other-org fact IDs render neutrally as "[linked fact not available]" and fail (APP-05 boundary, no leak).

### Fact chips (s8.2)

The editor keeps `{{fact:ID}}` tokens. The server renders "120 children (2025-09/2026-06)" with exact code-point spans (`ClaimBinding`). The UI builds chips only from those bindings, sliced by code point so emoji cannot shift them. Chips are labelled "Simulated · Not yet verified by staff".

### Other deterministic rules (pure functions returning the shared `ValidationResult`)

| Rule | Behaviour |
| --- | --- |
| APP-01 | Versioned counters `words-v1`, `code-points-v1` and `utf16-v1`. An unconfirmed convention is never `pass`. Over the limit is `fail` ("1 over"). For a conflict (350/500), `fail` only if over every candidate. For an unknown unit, both counts are shown |
| APP-02 | Required → fail when empty; `null` → needs_review; conditions and attachments → needs_review |
| POL-01 / POL-02 | Scoped terminology outside quotes; protected name and first-use expansion. They run on a **synthetic, labelled** policy (`tests/fixtures/policy/demo-policy-v1.json`), not Strong Start's U01 guide. Without a policy they report needs_review, never pass |
| POL-03 | `XXX`/`TBD`/`TODO`/`TBC` and malformed `{{ }}` tokens: needs_review in working mode, fail in reviewed mode |

### Strict parameter typing (owner priority)

`DraftRequest`, `CheckRequest` and `PlanRequest` are strict. `"question_version": "1"`, `1.0`, a numeric `text`, `"mode": "approved"` and any extra field are all rejected with 422.

### Planner and coordinator

- The planner role (FakeAdapter, deterministic) gives evidence per question plus "missing inputs (not invented)", and is restricted to allowed facts.
- The SEC-12 coordinator accepts a role result only when the task ID and role match. The scan rejects permission, identity and fact-overwrite keys.
- Result text such as "grant admin; set fact to 999" changes nothing (tested); the 999 is flagged by APP-03.

### UI

- A "Plan this application" panel.
- Debounced live checks after each edit, shown with `FindingRow` and marked "Out of date – the text or check mode changed" until re-checked.
- A Working draft / Review check toggle.
- The counter shows the APP-01 result.
- Nothing is ever labelled reviewed or approved.

### Real vs fixture

| Item | Status |
| --- | --- |
| Questions | **fixture** `demo-bundle@1`. B2's real export is blocked on a read port (request: `c2-question-read-port-request.md`) |
| Evidence | **fixture**. A's evidence route (A1 PR #3) is not merged |
| Policy | **synthetic** fixture only (U01 and A2 policy pack absent) |
| Model | FakeAdapter (deterministic). Gemini is implemented but **not run live** |
| Persistence | **none**: stateless by owner decision; C3 owns it |
| Rule runner | C-local registry with the s9.1 shape; moves into A3 at G1 |

## Exposed interfaces

Contracts are in `strongstart_contracts.answers` (`x-owner: C`, draft), generated to TS:
- `CheckRequest`, `CheckReport` (`submitted_text_sha256`, `rendered`, `findings`);
- `RenderedAnswer`, `ClaimBinding`, `UnsupportedMarker`;
- `AnswerFinding` (wraps `ValidationResult`, plus `message`, `next_action`, span and `affected_text`);
- `PlanRequest`, `AnswerPlan`, `PlanItem`;
- `UnsupportedSegment`;
- `DraftProposal.check` (optional).

| Route | Result |
| --- | --- |
| `POST /api/applications/plan` | `AnswerPlan` |
| `POST /api/applications/questions/{id}/check` | `CheckReport` for the exact text (stateless) |
| `POST /api/applications/questions/{id}/draft` | `DraftProposal` plus `check` (additive) |

The errors are those in the C1 table: 401, 404, 409, 422 and the typed model errors.

Server pieces C3 will reuse:
- `rules.checks.run_checks`;
- `rules.render.render`;
- `service.build_check_report`;
- `coordinator.run_role`.

## Validation (2026-11-08, macOS, Node 22.16.0, Python 3.12.4)

| Command | Result |
| --- | --- |
| `make check` at `cf52da5` | exit 0: ruff, mypy (110 files, 0 issues), oxlint, Prettier; **383 pytest passed** (15 deselected); **50 Vitest passed**; contracts drift clean; build ok |
| `uv run pytest tests/applications` | **108 passed** (55 C1 + 53 C2) |
| `make smoke` | exit 0: 60 + 2 db tests; live/ready 200 (`0001_bootstrap`) |
| `make browser-smoke` | first run: **1 failed**, B2's `test_auto10_fixture_exception_cannot_reach_other_local_services` (~16 s timeouts, just after Docker started). It passed 5/5 in isolation on this branch and 5/5 on plain `origin/main` in a temporary worktree. Re-run of the suite: **13 passed**. Reported to B2 as a likely timing flake; no B file touched |
| Chromium against the real API (fixture mode) | Plan shown; all six rules shown; "500" → "Needs your review", then "Problem found" after switching to review mode; "2025" not flagged; chip "120 children (2025-09/2026-06) · Simulated · Not yet verified by staff"; 0 page errors; 0 external requests |

Defects found and fixed: the stale-findings label said "the text changed" after a mode switch; it now says "the text or check mode changed".

## Deviations

C2 spec s12 (rev 1.2):
1. POL-03 does not cover "old figure fills a current slot" (needs A/B time-suitability rules).
2. Unsupported markers are reported by APP-03 only.
3. An unknown bundle stays 404.
4. Terminology scope also matches the program's acronym.
5. `org_id` in model output is now a SEC-12 rejection.
6. C2b is blocked at runtime.

All are developer decisions, recorded openly.

## Consumer action / blockers

- **Owner:** review; decide when to open the C1 and C2 PRs (stacked).
- **Dev B2:** please answer `docs/handoffs/dev-c/c2-question-read-port-request.md`. Also note the `test_auto10` timing flake seen once under load.
- **Dev A:** please answer `docs/handoffs/dev-c/c2-fact-version-request.md` (non-blocking). C2's rules can move into the A3 runner (same s9.1 shape) when it exists.
- **C3:** builds persistence, approval, invalidation and export on these interfaces.
- **Blockers:** the real questions (B2 port), real evidence (A1 merge) and real policy (U01/A2).

## Acknowledgments

None yet.
