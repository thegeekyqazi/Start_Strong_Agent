# E2E-DEMO r1: one end-to-end Strong Start demonstration

- Branch `integration/e2e-demo`, stacked on `data/data-001-tigerdata-application-state`
  `068f5aa` (DATA-001, PR #20, unmerged). Integration order: merge #20 first, then this PR.
- Scope: orchestration only (`scripts/demo/`, `docs/demo/`, this handoff). No application,
  C4, shared contract, migration, model adapter, shell or styling change. No new API.
- Recipients: project owner (cross-module blockers), Sawaab (two UI observations), C4 agent
  (insertion point and migration note).

## Delivered

- `scripts/demo/start_stack.sh`: demo-owned API on `:18120` and Vite on `:15190`. It uses
  the fixture identity, the fake model and FIXTURE funding providers, with durable C in the
  existing local PostgreSQL. B state is per-worktree (`E2E_DEMO_FRESH=1` gives a new empty
  dir). It refuses to start unless readiness is 200. It never migrates, seeds or resets.
- `scripts/demo/e2e_demo.py`:
  - `prepare` runs steps 1–3 and prints the selections.
  - `rehearse [--execute-portal] [--source prefill|capture]` runs steps 1–8 over real HTTP.
  - `status --manifest` reads a run back.
- `docs/demo/e2e-demo-guide.md`: step-by-step UI walkthrough with expected results, the C4
  insertion point, the labelled fallback/recovery table, blockers, limitations and evidence.

## Verification (2026-11-08, local; one focused rehearsal)

Fresh stack (`E2E_DEMO_FRESH=1`), readiness 200 at `0009_durable_applications`, existing
local PostgreSQL 17, Playwright Chromium.

1. `prepare`: FIXTURE search `srch-dc760b3b…` returned 3 candidates and omitted 1 unsafe
   result. Saved `def-01a1bb88a5780776e24df9fb31` v1 (input sha256 `6001379969e9…`). The
   workspace opened that exact question set with 9 questions and synthetic
   `demo-evidence-a-v1`.
2. Operator-path UI walk in real Chromium (scratch automation using only visible controls,
   not committed): Funding FIXTURE banner → Applications banner names the definition → save
   org name (201) → **Request a draft** + save summary (201) → Review approve both (200 each,
   *Ready for prefill*). **Export reviewed** was blocked by 7 unanswered questions; the
   working DOCX downloaded. Then **Use approved answer in Automation** ×2 → plan preview
   (*C producer connected*, *A4 not integrated for this evidence*) → **Fill these approved
   fields** → *Selected fields verified*, `Final reread: all_match`, 2 × `entered_verified
   (match)`, intended = actual SHA-256 → reload + **Check stored receipt** OK.
   - The approve click was the automation's, standing in for the human click.
   - Two scratch probe limits: the picker option-count probe printed 1, and the findings
     regex found no rule IDs in the page text after saving. Neither was a product failure:
     the banner ID was asserted, and findings are shown in the earlier capture and the API
     rehearsal.
3. `rehearse --execute-portal` (exit 0, manifest `20261108T142135Z-52a49d`):
   - APP-01 needs_review; APP-02/03, POL-01–03 as listed in the guide.
   - Approvals `apr-efbc660a…` and `apr-b6d88be7…`.
   - Reviewed export `exp-178876cf…`: 37691 B, downloaded SHA-256 equals the record.
   - Plan `pfp-01a1bb893cb72dc57ed7f19638`: executable, `approval_reader=c_reader`.
   - Run `pfr-01a1bb893cb72dc57ed7f19638`: `selected_fields_verified` / `all_match`;
     operations `fill:org-name-field`, `fill:summary-field`; stored receipt equal.
     `status` re-read it.
4. `rehearse --source capture --execute-portal` (exit 0): reviewed export
   `exp-d999c316…`. Plan `pfp-01a1bb8943be1f62bed68807e1` had `executable=false`, every
   selection held, and no browser entry.
5. `ruff check`, `ruff format --check`, `mypy` (strict) on `scripts/demo` pass;
   `bash -n start_stack.sh` passes. Full suites were deliberately not rerun (no product code
   changed).

## Blockers (exact requests)

- `POST /api/automation/prefill-plans` `{"question_set_id": <capture-derived set>,
  "portal_fixture_id": "rep-portal-v1", "selections": [rp-mission, rp-services,
  rp-other-funding approvals]}` returned 201 with `executable:false` and
  `no_eligible_selected_fields`. The held reasons are `held_counter_unavailable` (C
  exposes no public APP-01 counter to B) and `held_unresolved_requirement`
  (`unknown_limit_unit`). Other fields are held for a maxlength conflict, a limit conflict
  and `held_choice_value_unavailable`.
- `POST /api/applications/answers/decisions` for `rp-request-amount` text `25000` returned
  422 `approval gate blocked` / `blocking_findings`.
- Therefore no *captured funding opportunity* currently reaches an executable portal. B1
  fixture funding pages are not registered prefill targets. The executable journey uses
  the labelled saved definition bound to `rep-prefill-v1`. Owner decision needed for the
  next increment: a C→B public word counter and a reviewed requirement resolution.

## Coordination and environment

- The C4 worktree `strongstart-c4` holds an uncommitted `migrations/versions/0010_practice_skills.py`.
  Applying it to the shared DB would make this branch report not-ready. That is the
  intended fail-closed behaviour; recovery is documented. This branch does not touch it.
- No other service was stopped. Default ports `8000`/`5173` were left free. Demo-owned
  writes:
  - B files under `.local-data/e2e-demo/state*` (Git-ignored).
  - C rows in the shared local DB under the fixture org, with `e2e-demo-*` idempotency keys
    and `[E2E-DEMO SYNTHETIC]` text, plus a few earlier probe rows from the same session in
    `.local-data/e2e-demo/` (old flat state dir).
  - There is no C deletion path, and none was attempted.
- No credentials in commits or logs. The local Compose placeholder URL comes from
  `.env.example`.

## UI observations for Sawaab (not changed here)

1. The "Questions from" picker shows identical labels for several saved definitions of the
   same fixture. Consider adding the definition ID or saved time.
2. Review's reviewed export covers the whole question set, so a partial application can
   only export a working draft from the UI. Consider a subset or reviewed-only option.
