# Strong Start end-to-end demonstration (E2E-DEMO)

Restored from `integration/e2e-demo` (`fea5e8a`, PR #22, which merged into the DATA-001
branch rather than `main`) onto current `main` (C4 merged, migration head
`0010_practice_skills`). Two launch modes exist:

- **Live launch** (`scripts/demo/start_live.sh`, section L below): live Gemini, Tavily and
  Firecrawl; hosted TigerData TEST service. Fixture identity, synthetic evidence and
  representative portals stay labelled.
- **Fixture rehearsal** (`scripts/demo/start_stack.sh`, the original sections 0-8): fake
  model and FIXTURE funding providers on local PostgreSQL. That database must be at `0010`.

## L. Live launch (current)

Private settings live outside Git: provider keys, `STRONGSTART_MODEL_PROVIDER=gemini`,
`STRONGSTART_GEMINI_MODEL` and live funding modes in this worktree's ignored `.env`. The
TigerData runtime profile is in `~/.local/share/strongstart-data001-private/hosted.env`
(verify-full, pinned trust root, budget 20). The script refuses to start when any live
setting is missing. It never substitutes fake output, and it drops the migration URL before
starting the API.

```sh
scripts/demo/start_live.sh                     # API :18220, web :15290 (detached, PIDs + logs in .local-data/demo-live)
uv run python -m scripts.demo.e2e_demo rehearse --api http://127.0.0.1:15290 \
  --no-search --draft-only pf-summary --use-draft-text --stop-before-approval
# inspect the exact draft text/findings in the manifest; review (reject/edit) as needed, then:
uv run python -m scripts.demo.e2e_demo approve --api http://127.0.0.1:15290 \
  --manifest .local-data/e2e-demo/manifests/<run>.json --execute-portal
DEMO_ALLOWED_HOST=<exact>.trycloudflare.com scripts/demo/start_live.sh --web-only   # after the tunnel exists
scripts/demo/stop_live.sh                      # tunnel, web, API (recorded PIDs only)
```

Bound paid calls: run search and capture once each from the Funding page, or once via the
API. `--no-search` stops the driver from searching again. `--draft-only` limits drafting to
one question. A C4 preview makes two model calls: a baseline draft and a practice draft.
`approve` approves the remaining answers as the LOCAL fixture reviewer. That is a rehearsal
action, so inspect each exact text first. Live run evidence is in
`docs/handoffs/integration/demo-live-launch-r1.md`.

## Original fixture rehearsal

**Everything shown is LOCAL, SYNTHETIC and FIXTURE-labelled.** Identity is the local fixture
identity, and its approvals are fixture actions, not authentication. Funding search and
capture use the FIXTURE providers. The question source is an explicitly selected, labelled
saved definition. Evidence is synthetic `demo-bundle@1`, not partner records. The model is
the deterministic fake adapter. The portal is the registered **representative** portal
`rep-prefill-v1`, not a funder site. The normal Applications workspace does **not** consume
real organizational evidence yet. Nothing is submitted, signed or uploaded.

## 0. Prepare (about 1 minute)

Prerequisites: locked dependencies installed in this worktree (`uv sync --locked`,
`npm ci`), Playwright Chromium (`uv run playwright install chromium`), and the existing local
PostgreSQL (`127.0.0.1:55432`) **already** at migration head `0010_practice_skills`.
The demo never migrates, seeds, resets or stops anything.

```sh
E2E_DEMO_FRESH=1 scripts/demo/start_stack.sh          # terminal 1: API :18120, web :15190
uv run python -m scripts.demo.e2e_demo prepare        # terminal 2: steps 1-3 + selections
```

`prepare` runs a FIXTURE funding search and saves the labelled definition
`rep-prefill-definition-v1` as a new saved definition. It confirms that this exact question
set opens in Applications with the synthetic bundle, then prints the IDs you will see in each
page. It writes `.local-data/e2e-demo/manifests/<run>.json` (IDs and hashes only; ignored by
Git). Drafting, review, approval, export and portal entry stay manual.

Ports are separate from the defaults (`8000`/`5173`), which the C4 agent or a teammate may
use. Override them with `E2E_DEMO_API_PORT` / `E2E_DEMO_WEB_PORT`, and pass the same values to
`--api` / `--web`.

## Walkthrough (open http://127.0.0.1:15190)

| # | Page and action | Expected result |
| --- | --- | --- |
| 1 | **Find Funding** (`#/funding`): interests `early learning`, click **Search**. | Availability shows `fixture-search - fixture only FIXTURE (synthetic)`. Results banner says **FIXTURE MODE: synthetic results, not a live search**. Candidates include *FIXTURE Demo Funder - Community Grants Program*. The unsafe `127.0.0.1` result is omitted. Say aloud: *live search is unavailable here, so we explicitly select a labelled saved source.* |
| 2 | **Intake & Prefill** (`#/automation`): the saved definition printed by `prepare` is listed under **Saved definitions** (or import **Known fixture** `rep-prefill-definition-v1` and **Save definition for drafting** yourself). | 9 questions, `FIXTURE - engineering-derived representative material; not a funder source`. Status *saved, not reviewed*. |
| 3 | **Applications** (`#/applications`): under **Questions from**, choose *FIXTURE: Prefill demonstration form (rep-prefill v1)*. It is the only one in a fresh state dir. The banner names the printed `def-…` ID. | **Questions (9)**. Banner: `Questions: Dev B saved definition def-… v1 (…saved_not_reviewed). Evidence: FIXTURE: synthetic demo-bundle@1 data, not partner records`. |
| 4 | Select **0. Legal name of the organization.**, type `Riverside Youth Collective`, click **Save version**. Select **1. Summarize the project in plain language.**, click **Request a draft**, then **Save version**. | The draft reads `SYNTHETIC FIXTURE DRAFT: …` with `{{fact:demo-fact-children-served}}` rendered as *120 children (2025-09/2026-06) · Simulated · Not yet verified by staff*. Drafted by *demo writing assistant (fixed sample output, not an AI model)*. |
| 5 | Same page: read **Checks on this text**, **What the draft is unsure about** and **Evidence for this application**. | Deterministic findings: APP-01 *needs review* (counting method unconfirmed), APP-02 pass, APP-03 *needs review* (fact not verified by staff), POL-01/02 not applicable, POL-03 pass. Two uncertainties. Fact source `demo-synthetic-metrics` v1, locator `tests/fixtures/demo/demo-bundle-v1.json#facts`, provenance *Simulated*. |
| ↳ | **C4 insertion point:** see the section below. Optional; owned by the other agent. | — |
| 6 | **Review** (`#/review`): same **Questions from**. For each of the two questions: pick it under **Question**, read the exact text and checks, tick **I have read all N "Needs your review" items**, click **Approve this exact version (…)**. | *Approved this exact version.* Then *Ready for prefill: the latest version is approved and current.* Fixture/synthetic labels stay visible. |
| 7 | Review, **Export**: click **Export reviewed (DOCX)**. | **Gate shown:** *Reviewed export blocked:* lists the 7 unanswered questions. The UI exports the whole question set, and only 2 of its 9 questions are answered. Click **Export working draft (DOCX)**, then **Download DOCX** (and optionally the audit JSON). The labels read *WORKING DRAFT - NOT REVIEWED · SYNTHETIC DEMO DATA · FIXTURE APPROVAL - NOT AUTHENTICATION*. |
| 8a | Review: pick question 0, click **Use approved answer in Automation**. Click **Review**, pick question 1, click it again. | Automation says *Selected from Review: 2 approved answer(s)…*. Only server-issued IDs are passed; no answer text travels through the URL or storage. |
| 8b | Automation, portal `rep-prefill-v1`: click **Prepare selected-field plan (no entry)**. | **Exact approved plan preview** with both rendered values, hashes, expiry, **C producer connected** and **A4 not integrated for this evidence (unmanaged demo)**. No browser entry has happened yet. |
| 8c | Click **Fill these approved fields** once. This is the explicit execution. | **Selected fields verified**, **Final reread: all_match. No application was submitted.** `org-name-field` and `summary-field`: `entered_verified (match)`, with identical intended and actual SHA-256. |
| 8d | Refresh, then click **Check stored receipt**. | The same historical receipt comes back without a new execution. |

Verified on 2026-11-08 (below): every row was driven in real Chromium against the real API
and real C/B/Chromium. The only difference is that the browser automation clicked the
approve button that you click by hand.

## C4 Skills insertion point

C4-SKL-001 is merged into `main` (PR #23) and served by the same stack (**Skills**,
`#/skills`; see `docs/handoffs/dev-c/c4-skl-001-demo-guide.md`). Insert it between steps 5
and 6. It is a **separate** demonstration:

- Its previews are `working_preview_only` with `approval_permitted=false`. They do not feed
  this journey's saved versions, approvals, export or plan. Present it as *how an approved
  practice would change a draft preview*, then return to step 6 with the answers saved in
  step 4.
- The required head is `0010_practice_skills`. Hosted runtime roles also need the bounded
  C4 grants (`docs/handoffs/integration/demo-live-launch-r1.md`).

## Rehearsal command (verification, not the human demo)

```sh
uv run python -m scripts.demo.e2e_demo rehearse --execute-portal   # executable journey
uv run python -m scripts.demo.e2e_demo rehearse --source capture   # labelled capture variant
uv run python -m scripts.demo.e2e_demo status --manifest .local-data/e2e-demo/manifests/<run>.json
```

`rehearse` performs steps 1–8 over real HTTP. It approves as the fixture reviewer, which is
a rehearsal and not meaningful review. Its reviewed export uses the **selected** question
IDs, which the API gate permits once those exact versions are approved. Without
`--execute-portal` it stops after preparing the plan. Any non-2xx response stops it and
prints the exact method, URL, request and response. Nothing is faked.

## Fallback and recovery (labelled)

| Situation | Action |
| --- | --- |
| `start_stack.sh` prints `E2E-DEMO BLOCKER: GET …/health/ready returned 503` | Do not migrate. The DB is not at head `0010_practice_skills`, or the container is stopped. Ask the DB owner to migrate it with the migration role. |
| Port in use | Use `E2E_DEMO_API_PORT` / `E2E_DEMO_WEB_PORT`. Never stop another agent's process. |
| Picker shows several identical *FIXTURE: Prefill demonstration form* entries | Restart with `E2E_DEMO_FRESH=1` (new empty B state dir) and run `prepare` again. The definition ID in the Applications banner must match the printed one. |
| Approval refused / stale (edited after approval) | Expected gate. Save the intended text again, re-review, approve the new exact version, and prepare a **new** plan. |
| Plan shows *runtime epoch changed* or **Check current sources** disables entry | Expected currentness gate (API restart or edit). Prepare a new plan; never replay the old one. |
| Live UI fails mid-demo | Labelled fallback: run `rehearse --execute-portal` in a terminal and show its output and manifest. It uses the same real APIs; say that approvals were made by the fixture reviewer identity. |
| Want to show a captured page instead of a registered definition | Labelled variant `--source capture` (B2 FIXTURE capture `cap-fixture-portal-html` of portal `rep-portal-v1`). It reaches a prepared plan with **every field held** and no entry. See the limitations. |
| Clean up demo B state | Stop the stack and remove only `.local-data/e2e-demo/state*`. C rows in the shared DB are demo-labelled (`[E2E-DEMO SYNTHETIC]`, `e2e-demo-*` idempotency keys) under the fixture org. There is no deletion path for them, and none is attempted. |

## Blockers and limitations (exact)

1. **No funding opportunity → executable portal path.** B1 FIXTURE funding captures are not
   registered prefill targets. The labelled B2 capture of `rep-portal-v1` is importable,
   saveable and draftable, but `POST /api/automation/prefill-plans` with
   `{"portal_fixture_id": "rep-portal-v1", …}` returns 201 with `executable: false` and
   `not_executable_reasons: ["no_eligible_selected_fields"]`. The held reasons are:
   - `rp-mission`, `rp-services`: `held_counter_unavailable` (*C owns word counting (APP-01)
     and exposes no public counter*).
   - `rp-other-funding`: `held_unresolved_requirement` (`unknown_limit_unit`).
   - `rp-pending-applications`: native maxlength conflict.
   - `rp-partnership`: limit conflict.
   - `rp-service-area`: `held_choice_value_unavailable`.

   `POST /api/applications/answers/decisions` for `rp-request-amount` (`"25000"`) returns
   422 `approval gate blocked` (`blocking_findings`). These are deliberate B/C gates on the
   *representative negative* portal. They are not demo bugs, and the demo does not bypass
   them. The executable journey therefore uses the labelled saved definition bound to
   `rep-prefill-v1`. Cross-module asks: a public C word counter for B (C→B), and a reviewed
   requirement-resolution path (B).
2. **Reviewed export in the UI** covers the whole question set and stays blocked until all
   9 questions are approved. The UI therefore shows the gate and downloads the working
   export. The API permits a reviewed export of the selected, approved subset (rehearsal).
   UI consideration for Sawaab: offer a subset or reviewed-only export, if desired.
3. **Picker labels**: identical fixture titles for several saved definitions are hard to
   tell apart. Mitigated with `E2E_DEMO_FRESH=1`. UI consideration for Sawaab: show the
   definition ID or saved time in the option label.
4. Evidence is the unmanaged synthetic bundle: *A4 not integrated for this evidence*. The
   managed A4 path is the separate INT-001 rehearsal. B files, plans and grants are
   development-only files (DATA-002). C state is durable in local PostgreSQL. The demo was
   not run against TigerData.
5. Approvals are fixture identity actions; real authentication is not implemented.

## Verification evidence (2026-11-08, local)

Stack: `scripts/demo/start_stack.sh`, API `127.0.0.1:18120` (readiness 200 at `0009`), Vite
`127.0.0.1:15190`, existing local PostgreSQL 17, Playwright Chromium. Results are recorded
in the [task handoff](../handoffs/integration/e2e-demo-r1.md).
