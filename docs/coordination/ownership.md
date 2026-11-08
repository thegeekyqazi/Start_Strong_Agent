> Current engineering ownership (2026-11-08): the project owner owns former A/B/C
> engineering and migration sequencing; Sawaab owns UI/UX. INT-001 uses one agent,
> sequential milestones. See [decision 0005](../decisions/0005-int-001-engineering-takeover.md).
> Historical lane instructions below remain context; machine-readable owners are unchanged.

# Folder and contract ownership after INIT-001

Source: INIT-001 rev 1.0 s5, `dev-b-two-agent-plan.md` rev 1.0 s2-s3, AGENTS.md, decision 0004. "Owner" means the lane coordinates changes; it is not permission to rewrite others' modules. Shared coordination points need a reviewed PR that names affected consumers.

**Dev B labels (2026-11-07, decision 0004):** one Dev B agent owns both Dev B modules. In this table **B1** means the Dev B *funding* module (task series `B1-DISC-*`, `B1-OPS-*`) and **B2** means the Dev B *automation* module (`B2-AUTO-*`). They are module labels, not separate agents. The same labels appear in runtime `Capability.owner` and contract `x-owner` values and are intentionally unchanged. See `dev-b-single-agent-plan.md`.

## Paths

| Path | Owner | Notes |
| --- | --- | --- |
| `apps/web/src/App.tsx`, `src/shell/`, `src/api.ts`, `src/index.css` | C (shared shell) | Feature lanes do not edit these for routine feature work. |
| `apps/web/src/features/registry.ts`, `features/types.ts`, `features/Placeholder.tsx` | C | Registration already done for all six features. |
| `apps/web/src/features/knowledge/` | A | |
| `apps/web/src/features/funding/` | B1 | |
| `apps/web/src/features/automation/` | B2 | |
| `apps/web/src/features/{applications,review,skills}/` | C | |
| `services/api/src/strongstart_api/{app,config,errors,identity,db,ports,seed}.py` | Shared host | Changes are coordination points. Identity/authorization changes need A (SEC-01) review. |
| `services/api/src/strongstart_api/features/knowledge/` | A | |
| `services/api/src/strongstart_api/features/funding/` | B1 | |
| `services/api/src/strongstart_api/features/automation/` | B2 | |
| `services/api/src/strongstart_api/features/applications/` | C | Also declares the review and skills capabilities. |
| `packages/contracts/python/src/strongstart_contracts/common.py`, `platform.py`, `validation.py`, `jobs.py` | Shared (A/C agreements) | `ChangeSet` producer: A. |
| `.../evidence.py` | A | |
| `.../funding.py` | B1 | |
| `.../automation.py` | B2 | |
| `.../answers.py` | C | |
| `.../ports.py`, `fixture_adapters.py`, `fixtures.py` | Shared | Port producers are listed in the `ports.py` docstring. |
| `packages/contracts/schema/`, `packages/contracts/ts/src/generated.ts` | Generated | Regenerate with `make contracts`; never hand-edit. |
| `services/worker/` | Feature worker owners | Docs only. |
| `services/browser/` | B2 | Docs only. The B2-AUTO-001 inspector lives in `features/automation/` (decision `dev-b-b2-auto-001-intake-slice.md` item 6). Browser-specific Compose fragment goes in a separate file. |
| `infra/compose.yaml`, `.github/workflows/`, root `package.json`/lockfiles, `.env.example` | Dev B (common infra/CI, funding-module task series) | Shared with all lanes through PR. The B1→B2 patch-request rule is superseded (one Dev B agent). |
| `migrations/` | A sequences after `0001_bootstrap` | Other lanes submit bounded migration requests. Database service selection/Tiger Data integration is A's (decision 0004). |
| `tests/fixtures/demo/demo-bundle-v1.json` | Per record owner (see `tests/fixtures/README.md`) | Keep IDs and simulation labels. Add a new versioned bundle instead of silently editing records others consume. |
| `tests/fixtures/browser/` | B2 | |
| `tests/contracts/`, `tests/unit/`, `tests/smoke/`, `tests/browser/` | Each owner extends relevant tests | |
| `docs/handoffs/dev-a/`, `dev-b/`, `dev-c/` | Respective lane | Dev B module tasks use `b1-*` / `b2-*`; cross-module Dev B notes use `dev-b-*`. |

## Ports ready to consume

| Port | Real producer | Default | Fixture (inject deliberately) |
| --- | --- | --- | --- |
| `CaptureStore` | A | `UnconfiguredCaptureStore` raises `CapabilityUnavailable` | `FixtureCaptureStore` (in-memory, immutable versions) |
| `EvidenceProvider` | A | `UnconfiguredEvidenceProvider` | none yet |
| `ApprovedAnswerResolver` | C | `UnconfiguredApprovedAnswerResolver` | `FixtureApprovedAnswerResolver` (bundle-backed, stales on applied ChangeSet, org-scoped) |
| `JobStore` | A (with C) | `UnconfiguredJobStore` | none yet |

API dependency providers live in `strongstart_api/ports.py` (`get_capture_store`, ...). Override them with `app.dependency_overrides` in tests.

## CODEOWNERS

Not created: real GitHub reviewer handles have not been supplied. Add `.github/CODEOWNERS` from this table once the team's handles are known.


## INT-001 current public producer/consumer paths

- C: `applications.public.get_approved_prefill_reader` resolves the app-scoped save/approve
  store, exact saved rendering and store epoch with consistent snapshots. It also supports
  metadata resolution through the same usable-approval predicate. Process-local only.
- A4: `knowledge.public.KnowledgeCurrentness` / `get_prefill_currentness` resolve authorized
  active evidence, project dependencies, register exact browser targets and check existing
  registrations. PostgreSQL/Alembic, compatible with the next TigerData increment.
- B: plan/grant v2 binds C content, full dependency union and actual A4 registrations;
  default demo evidence remains unmanaged. The Review handoff carries IDs only.
- Sawaab: owns UI/UX; this task adds functional state/props only. See the
  [UI contract](../handoffs/integration/int-001-ui-contract.md).

See [the current integration handoff](../handoffs/integration/int-001-approved-content-currentness-r1.md)
for evidence, migration, limitations, acceptance mapping and next consumer work.
