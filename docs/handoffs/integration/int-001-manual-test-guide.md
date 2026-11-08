# INT-001 revision 1.1: manual rehearsal

Use this branch with Python 3.12, the locked uv/npm dependencies, Node from `.nvmrc`,
PostgreSQL 17 and installed Playwright Chromium. All data below is synthetic. No model,
search or capture credentials are needed. Nothing submits, uploads or signs.

## Normal C-connected demo

1. Run `uv sync --locked`, `npm ci`, and `uv run playwright install chromium` if needed.
   Keep existing local database data; never reset its volume. Set
   `STRONGSTART_DATABASE_URL` to your local PostgreSQL URL (or an explicitly configured
   TigerData test URL), then run `make migrate`. The required head is
   `0008_browser_bindings`; this task did not install C3's draft migration.
2. Start the normal API (one worker, no reload during the rehearsal):

   ```sh
   STRONGSTART_AUTH_MODE=fixture uv run uvicorn --factory strongstart_api.app:app_factory --host 127.0.0.1 --port 8000
   ```

   In another terminal run `npm run dev -w @strongstart/web`. Open
   `http://127.0.0.1:5173/#/automation`. `STRONGSTART_DEV_B_STORE_DIR` controls the
   development-only saved-definition/plan/run directory (default `.local-data/dev-b-store`).
   The normal runtime does **not** use `tests/browser/prefill_app.py` or seeded approvals.
3. In Automation select **Known fixture**, choose `rep-prefill-definition-v1`, import,
   then **Save definition for drafting** as a new definition. Saved is not reviewed.
   This positive fixture has two eligible text fields; the original representative
   portal's 350/500 conflict and unknown `Max 300` unit are deliberately unchanged.
4. In Applications select that saved definition under **Questions from**. Save a version
   for the organization name (`Riverside Youth Collective`) and summary
   (`Historical synthetic metric: {{fact:demo-fact-children-served}}.`). Inspect the
   rendering and synthetic provenance. No draft/model invocation is required.
5. In Review choose the same definition and first question. Inspect the exact version,
   acknowledge all review items, and **Approve this exact version**. Click
   **Use approved answer in Automation**. Return to Review, approve the summary, and use
   the same button again. The tab accumulates only server-issued approval/question IDs
   for this question set. No answer text or selectors are passed in URLs/storage.
6. Automation loads those IDs. Select `rep-prefill-v1` and click
   **Prepare selected-field plan (no entry)**. Verify exact rendered values, separate
   template/rendered hashes, versions, holds, attachments and expiry. Expect
   **C producer connected** and **A4 not integrated for this evidence (unmanaged demo)**.
   A configured database alone does not turn fixture evidence into managed evidence.
7. Click **Fill these approved fields** once. Expect `Selected fields verified`, two
   `entered_verified` fields, matching live hashes and `Final reread: all_match`.
   The representative page closes. This is not saved funder state or application readiness.
   Refresh, then **Check stored receipt**: the original receipt returns without execution.

## C edits, definition revisions and historical replay

- Prepare another plan, then save a one-character C edit before executing it. In the plan
  use **Check current sources (no entry)**. Expect stale usability, disabled entry and
  a review/prepare-new-plan action. An API execution attempt yields a zero-write blocked
  receipt. The old approval never receives the new text or a new rendering.
- Rehearse again with a fresh approval/plan, then save a newer version of B's definition.
  The old question set/approval/plan is unusable; choose current questions and review again.
- Completed receipts remain historical after either change. Same-key execution replay
  returns the original run, without renewed authority. An incomplete/uncertain claim
  never automatically executes again. Do not delete the pending identity to retry a write.
- Choice prose has no typed authority. Select/radio/checkbox and their dependent fields
  remain held. Word-counter integration and attachments remain limited as shown.
- Restarting the API loses C approvals and changes its store epoch. B's local files may
  survive, but old pending plans cannot execute. Multiple workers are unsupported here.

## Managed A4 rehearsal (real PostgreSQL and Chromium)

This opt-in harness replaces **only the evidence workspace** with a bounded test adapter
that reads real A4 records through `knowledge.public`. C's save/decide/store/content reader,
B publication/planner/runner and Chromium are the real implementations. It does not make
this workspace the normal runtime or production integration. Policy rules without a C
writing-policy adapter stay `needs_review`; no synthetic fixture policy is relabelled.

Stop the normal API on port 8000 first, or use `--port` and the API verifier on a free port.
With `STRONGSTART_DATABASE_URL` set, run:

```sh
uv run python -m scripts.int001_managed_rehearsal
```

The process creates uniquely named synthetic manifests/facts/policies, prints its context,
exact fact tokens, replacement path/body, and serves the real application. It migrates
forward without resetting data. C approvals are process-local; B files are temporary.
Ctrl+C stops the owned server and removes only this rehearsal's SQL rows/files.

For an automated real HTTP/Chromium rehearsal, copy the printed replacement version ID:

```sh
uv run python -m scripts.verify_int001_managed_api --replacement <printed-pack-version-id>
```

Expected: actual C save/approve → two-field managed plan → actual plan/grant SQL targets →
Chromium final reread; a second pending plan → real activation → stale GET → zero-write
blocked receipt; the first completed run replays identically. Both PASS lines are required.
This was run locally on port 18008; it was not run against TigerData.

For the UI variant, run the web server, publish the positive fixture and follow the normal
Review handoff above using the printed **managed** fact tokens. Expect
**Managed A4 currentness registered**. Before entry, POST the printed replacement URL/body
(for example with a local HTTP client). Check current sources: the source-pack next action
appears and entry is disabled. Never paste answer text or authority fields into an execute
request. To repeat, stop/restart the rehearsal for new isolated IDs and approvals.

Use the deterministic DB tests for replacement after grant registration and between fields,
fact-only/policy-only/same-content replacements, tenant/context isolation and both lock
orderings. These avoid trying to time a manual race:

```sh
uv run pytest -m db tests/smoke/test_int001_a4.py tests/smoke/test_int001_joined.py
uv run python scripts/verify_int001_registration_mutation.py
```

The mutation script temporarily removes only registration locks, requires the specific
stale-registration test failure, restores source bytes in `finally`, and reruns the protected
test. Do not run it concurrently with source edits. An outage/failed registration blocks;
there is no fallback from managed to unmanaged authority.

## Required checks and limits

```sh
make contracts
make check
make smoke
make browser-smoke
```

`make smoke` requires the configured migrated PostgreSQL; `make browser-smoke` requires
installed Chromium. The DB CI job includes the actual A4 seam with a controlled browser
actuator; the browser CI job exercises the normal C-connected UI/API/Chromium path. The
managed API script above additionally joins all four real components locally.

Production fixture identity/prefill remains disabled; real authentication, durable C/B
storage/jobs, real funder portals, uploads, signing and submission are not enabled. The
mandatory next increment is **TigerData durability plus real A-evidence/workspace integration**,
including approved writing-policy retrieval and the remaining real-check/G2/G4 consumers.
