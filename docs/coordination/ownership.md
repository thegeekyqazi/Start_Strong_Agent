# Folder and contract ownership after INIT-001

Source: INIT-001 rev 1.0 s5, `dev-b-two-agent-plan.md` rev 1.0 s2-s3, AGENTS.md. "Owner" means the lane coordinates changes; it is not permission to rewrite others' modules. Shared coordination points need a reviewed PR that names affected consumers.

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
| `services/browser/` | B2 | Docs only. Browser-specific Compose fragment goes in a separate file. |
| `infra/compose.yaml`, `.github/workflows/`, root `package.json`/lockfiles, `.env.example` | B1 (Dev B common infra/CI) | B2 sends requested patches. Shared with all lanes through PR. |
| `migrations/` | A sequences after `0001_bootstrap` | Other lanes submit bounded migration requests. |
| `tests/fixtures/demo/demo-bundle-v1.json` | Per record owner (see `tests/fixtures/README.md`) | Keep IDs and simulation labels. Add a new versioned bundle instead of silently editing records others consume. |
| `tests/fixtures/browser/` | B2 | |
| `tests/contracts/`, `tests/unit/`, `tests/smoke/`, `tests/browser/` | Each owner extends relevant tests | |
| `docs/handoffs/dev-a/`, `dev-b/`, `dev-c/` | Respective lane | B1 uses `b1-*`, B2 uses `b2-*`. |

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
