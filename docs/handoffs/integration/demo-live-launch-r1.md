# Live demo launch r1 (2026-11-08)

- Branch `demo/live-launch-001` from `main` `e1c3f57` (PR #23 merged). Recipients: project
  owner; C owner (citation decision); Sawaab (none, no UI changes).
- Scope: restore the PR #22 demo files that merged into the DATA-001 branch rather than
  `main` (from `fea5e8a`: `scripts/demo/`, `docs/demo/`, `docs/handoffs/integration/e2e-demo-r1.md`);
  live launcher; one C4 validation fix found by the first live model run. No migration,
  contract, UI or provider changes.

## Changes

- `scripts/demo/start_live.sh` / `stop_live.sh`: one API (:18220) and one Vite (:15290),
  detached, PIDs and logs in `.local-data/demo-live/` (ignored). Preflight refuses to start
  without Gemini key/model, Tavily/Firecrawl keys, live modes, fixture auth and the postgres
  store (verified: exit 4, names only). TigerData runtime profile from a private file; the
  migration URL is unset before the API starts. `--web-only` with `DEMO_ALLOWED_HOST` passes
  one exact host via `__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS`. `start_stack.sh` is unchanged
  and remains the fake/fixture rehearsal.
- `scripts/demo/e2e_demo.py`: `--no-search`, `--draft-only`, `--use-draft-text`,
  `--stop-before-approval`, and an `approve` subcommand. Model labels now come from
  `provider.is_fixture` instead of a hard-coded "fixture model".
- `skills/model_tasks.verify_span`: server-derived offsets for an exact, unique quote
  (`docs/decisions/C4-SKL-001-citation-offset-resolution.md`) plus a test.
- `docs/demo/e2e-demo-guide.md`: live launch section; head `0010`; C4 merged.

## Hosted TigerData (TEST service `strongstart-data001-test`, not the restore service)

- Applied `0009 -> 0010_practice_skills` as `data001_migrator` (verify-full, TLS 1.3).
- Bounded runtime grants to `data001_app`: `SELECT, INSERT` on `skl_scope_state`,
  `skl_records`; `UPDATE(revision, current_source_version_id, active_release_id)` on
  `skl_scope_state`; `USAGE` on `skl_records_ordinal_seq`. No UPDATE/DELETE on records.
- `strongstart-seed-demo` (as migrator) added synthetic `demo-org` + demo-bundle metadata
  (simulated-labelled) for the fixture identity.
- Not done: backup/restore re-verification, role/plan changes, TLS changes.

## Live walkthrough evidence (one run each; through the web origin /api proxy)

| Step | Result |
| --- | --- |
| Readiness | 200, `revision=0010_practice_skills`; session `LOCAL FIXTURE IDENTITY` |
| Tavily search | `srch-b9cecb77…`, live, HTTP 200, 5 candidates, 1 credit |
| Firecrawl capture | `cap-4b4b5a9d…` of the canada.ca ESDC news release (March 2025, historical, not a current call); public, unreviewed, unverified |
| Gemini draft | `gemini-3.5-flash-lite`, `draft-c427a8d8…`, schema-valid; reviewer **rejected** v1 (present-tense claim from a historical figure; "this project" vs all-programs scope) |
| Review | edited v2 approved (`apr-631f3cb1…`); `pf-org-name` fixed synthetic text approved by the fixture reviewer |
| Export | reviewed DOCX `exp-71d48d88…`, SHA-256 verified on download |
| Prefill | `rep-prefill-v1`, plan `pfp-01a1bbbb…`, run `selected_fields_verified` / `all_match` in real Chromium |
| C4 | source `psrc-0df29a7f…` -> authority -> Gemini proposal (first rejected `citation_not_exact_source_text`; after the fix `pcand-5eb94918…`) -> live screening `no_flags`, complete 6/6 parts -> 5/5 rule tests -> exact-hash review -> release `prel-c1c7c9ab…` -> preview (POL-01/POL-02 flag the sample) -> revoked |

Gemini notes: the first key's project returned HTTP 402 (prepaid credits depleted);
`gemini-2.5-flash-lite` returned 404 ("no longer available to new users") for the second
key. Model chosen from the account's ListModels plus official thinking docs: the adapter caps
output at 1024 tokens, and thinking tokens count toward that cap. Gemini preview-draft quality
note: the practice draft misattributed the claim to the program name; preview is working-only.

## Validation

`ruff check`/`format --check`, `mypy` (scripts/demo, skills, new test); `pytest
tests/skills/test_citation_spans.py` 5 passed; `pytest -m db tests/skills` 4 passed. Full
`make check/smoke/browser-smoke` not rerun (focused change).

## Limitations

B state (definitions, plans, captures) is still in the development-only local file store
(DATA-002 pending). The runtime role has no grants on A knowledge tables (the A routes show
not implemented). The Quick Tunnel is temporary, needs this machine awake, and gets a new
hostname on every restart.
