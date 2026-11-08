# C4-SKL-001 demo guide (about three minutes)

All practice text is **SYNTHETIC** and invented for the demo; it is not Strong Start's brand policy.
Proposal and screening come from the labelled **FIXTURE** adapter unless a live model is
configured; never present them as live model output.

## Reset-safe preparation

Use a dedicated local database so other worktrees' databases are untouched (never reset a shared
or hosted database):

```sh
docker exec strongstart-postgres-1 psql -U strongstart -d postgres -c "CREATE DATABASE strongstart_c4_demo"
export STRONGSTART_DATABASE_URL=postgresql+psycopg://strongstart:<local-dev-password>@127.0.0.1:55432/strongstart_c4_demo
uv run alembic upgrade head          # to 0010_practice_skills
uv run strongstart-seed-demo         # synthetic demo-org
STRONGSTART_ANSWER_STORE_BACKEND=postgres STRONGSTART_AUTH_MODE=fixture \
  uv run uvicorn --factory strongstart_api.app:app_factory --host 127.0.0.1 --port 8000
npm run dev -w @strongstart/web      # http://127.0.0.1:5173/#/skills
```

State is append-only; each "Publish" creates a new source version. For a clean slate, drop and
recreate only `strongstart_c4_demo`.

Optional rehearsal: `uv run python scripts/c4_walkthrough.py /tmp/c4-shots http://127.0.0.1:5173`.

## Script

1. **Source.** Publish the synthetic demo source; point out the SYNTHETIC label and fingerprint.
   Approve it as practice authority for this scope (a source approval is not a rule approval).
   The real playbook would arrive through the same administrator-authored source path.
2. **Generate.** Generate a candidate; show each rule beside its exact excerpt and code points, and
   the compiled package files.
3. **Gates.** Show the scan (no findings), rule tests (real POL-01/POL-02), then run screening —
   explain it is a review signal (FIXTURE here), not a security classifier.
4. **Review/activate.** Confirm source support, approve the exact package, activate.
5. **Preview.** Preview a draft: show the applied-instruction trace that was sent to the draft
   model, and the same sample checked with base policy (passes) vs active practice (flags
   "kids" → "children" and the protected name). Working preview only — nothing to approve here.
6. **Revoke.** Revoke and preview again: "No practice applied". Or publish a new source version:
   the release becomes stale and the preview refuses it.
7. **Malicious candidate.** Publish the planted hostile source, approve authority, generate: the
   candidate is held (override, exfiltration, secret canary redacted, hidden character,
   unregistered name), screening never sends it to a model, and approve/activate stay disabled.
   Optionally publish the conflicting source to show a base-policy conflict hold.

Limits to say out loud: synthetic policy and fixture model; preview-only integration (not saved
answers, approvals, exports or prefill); a benign corpus is not exhaustive attack coverage.
