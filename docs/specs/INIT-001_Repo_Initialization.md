# INIT-001: Initial repository initialization and shared development foundation

**Revision:** 1.0  
**Owner:** Project owner, who is Dev B; a setup agent may execute this task on their behalf.  
**Status:** Ready-to-run development specification. No initialization has been performed by this document.  
**Baseline:** Engineering v1.1, sections 2-5, 9, 14-20, 22-23; root AGENTS.md; working-agreement decision 0001.  
**Scope:** Shared foundation for Dev A, Dev B and Dev C, followed by two independent Dev B agent sessions.  
**Confirmed assignment:** Dev B. The earlier “my Dev C” phrase was clarified by the user.

## 1. Agent execution instruction

Execute this specification in the owner's selected folder. Inspect existing files and Git state first. Implement and verify the shared initialization only; leave product features for their later feature specs. Use reasonable implementation judgment, document meaningful deviations, and continue through verification and a handoff report. Ask only for missing information that materially prevents authorized work; an absent GitHub remote or provider API key does not prevent local setup.

This is a coding-agent implementation spec, not a request to write another plan. It authorizes local initialization when the folder is not already a repository. The project owner retains responsibility for the setup; execution is delegated by giving an agent this spec. Do not initialize or modify some other repository.

## 2. Starting inputs and document import

The owner plans to put these three earlier deliverables in one folder, then add this spec and the Dev B work plan:

| Input | Purpose |
| --- | --- |
| AGENTS.md | Working instructions; preserve the exact uppercase filename. |
| Agent_Coordination_Guide.md | Explanation of branches, handoffs, PRs and agent communication. |
| StrongStart_Agent_Repo_Kit.zip | Ten documentation/template files, including the engineering Markdown and 86-check catalog. |

Read the top-level AGENTS.md first. The referenced docs may not exist until the ZIP is imported; importing them is an explicit bootstrap prerequisite, not a missing-spec blocker. Inspect the archive listing before extraction. Reject absolute paths, traversal, symlinks, unexpected executable resources and excessive expanded sizes. Stage extraction, compare existing files, and preserve existing user edits. Do not run scripts from the archive.

The original kit SHA-256 is `d57ed77dfc0aa3a1979fe390d834af7c26b4ff54815e5d9832308c59c1d5bcee`. A mismatch means inspect/report the difference rather than asserting the archive is unchanged; the hash is an integrity reference, not proof of trust. The expected ten paths are:

- AGENTS.md
- CLAUDE.md
- .github/PULL_REQUEST_TEMPLATE.md
- docs/coordination/README.md
- docs/decisions/0001-agent-working-agreement.md
- docs/decisions/TEMPLATE.md
- docs/handoffs/TEMPLATE.md
- docs/specs/README.md
- docs/engineering/StrongStart_Engineering_Plan.md
- docs/engineering/StrongStart_Check_Catalog.json

Identical duplicate AGENTS.md files can be retained once. If they differ, reconcile the actual owner instructions explicitly; do not overwrite them blindly. Preserve an existing CLAUDE.md and add the shared import without duplicating rules. Do not overwrite existing GitHub templates or an initialized app.

Copy this specification to `docs/specs/INIT-001_Repo_Initialization.md`. Copy `DevB_Two_Agent_Plan.md` to `docs/coordination/dev-b-two-agent-plan.md`. Preserve the engineering baseline and check catalog unchanged. Record later lane/sub-agent ownership separately. Keep original input archives/duplicate downloads outside tracked source, or in an ignored `.bootstrap-input/` folder; do not delete originals without instruction.

Add decision `docs/decisions/0002-dev-b-and-bootstrap.md` recording: the user is Dev B; they own initial setup; they will run two agents within Dev B; this spec authorizes that setup agent; the engineering diagram remains a baseline rather than an existing file tree. Distinguish these user decisions from the stack choices proposed below.

## 3. Intended outcome and scope limits

Deliver one reproducible monorepo that starts a minimal web shell and API, connects to a local PostgreSQL service, imports shared typed contracts/fixtures, exposes clearly labelled feature extension points, and runs meaningful baseline checks. Dev A and C must receive usable entry points too; this is not a Dev-B-only repository.

Do not build grant search, a crawler, proposal generation, a complete knowledge store, approvals, skill generation, portal automation or the 86-rule engine in this task. Do not configure paid accounts, publish a site, send partner messages, create a GitHub repository with an invented name, or fill absent credentials with fake working values.

Fixtures and placeholders must be visible as such. A missing adapter returns an explicit unavailable/not-implemented result; it never fabricates a successful product operation. All 86 catalog entries remain planned unless a later implementation has real supporting tests.

## 4. Stack and dependency choices

Use these defaults when the folder has no existing implementation. If the owner has already selected or scaffolded a different compatible stack, preserve it and record the mapping/deviation instead of replacing it.

| Area | Default | Required setup behaviour |
| --- | --- | --- |
| Web | React, TypeScript and Vite | Minimal shell, navigation and API connectivity state; no full visual redesign. |
| JavaScript tooling | npm workspaces | One committed package-lock.json; consistent package manager and supported Node runtime. |
| API | Python 3.12+, FastAPI, Pydantic | Separate feature routers and dependency injection; strict shared DTOs. |
| Python tooling | uv workspace | One committed uv.lock and compatible package metadata; root commands resolve local workspace packages. |
| Database | PostgreSQL; local development service through Docker Compose | Choose/pin a supported major compatible with the intended hosted DB; record actual tested version. |
| DB access/migrations | SQLAlchemy and Alembic | One migration history, minimal shared bootstrap tables, no production domain schema invented prematurely. |
| Tests/checks | pytest, Ruff, a Python type checker; TypeScript, ESLint and Vitest | Real runnable commands and deterministic fixtures. Choose one formatter per language. |
| Browser foundation | Playwright Python with Chromium | Isolated smoke test against a local fixture only; browser automation remains B2 work. |
| CI | GitHub Actions, if this is the chosen Git hosting service | No-secret checks using actual commands; no automatic deployment or PR merging. |

Check current official compatibility requirements during execution, choose stable compatible versions and lock the versions actually installed. Do not claim a specific version is latest without verification. Record Node, Python, uv, npm, PostgreSQL and browser versions in the setup handoff. Runtime installation limits are reported accurately; do not change global machine configuration or use administrator privileges without existing authorization.

Vite's official guide documents React/TypeScript scaffolding and runtime prerequisites; uv documents shared-lock workspaces; FastAPI documents independent APIRouter modules. These support the default choices, not a vendor guarantee of this project layout. [R01-R03]

## 5. Repository shape and ownership seams

Keep the engineering plan's logical modules, but initialize only working packages and extension points. This proposed concrete layout may be adjusted to existing conventions with documented compatibility:

| Path | Initial contents | Owner after setup |
| --- | --- | --- |
| apps/web | React/TypeScript app and common navigation/layout. | C owns shared shell; each lane owns its feature pages. |
| apps/web/src/features/knowledge | Labelled entry point for Knowledge. | A |
| apps/web/src/features/funding | Labelled entry point for Find Funding. | B1 |
| apps/web/src/features/automation | Labelled entry point for intake/prefill. | B2 |
| apps/web/src/features/applications, review, skills | Labelled C feature entry points. | C |
| services/api | FastAPI entry point, configuration, common dependencies and feature routers. | Shared host; feature owners edit their own routers. |
| services/api/src/strongstart_api/features/knowledge | Empty/explicitly unavailable feature router. | A |
| services/api/src/strongstart_api/features/funding | Empty/explicitly unavailable feature router. | B1 |
| services/api/src/strongstart_api/features/automation | Empty/explicitly unavailable feature router. | B2 |
| services/api/src/strongstart_api/features/applications | Empty/explicitly unavailable feature router. | C |
| packages/contracts/python/strongstart_contracts | Shared Pydantic schemas, errors and protocol boundaries. | Common/A/C agreements; funding B1 and automation B2 files are separate. |
| packages/contracts/ts | Generated TypeScript contract types and generation instructions. | Generated; update from canonical schemas. |
| services/worker and services/browser | Extension documentation/package markers only unless needed for the smoke test. | Feature worker owners; no unused service pretending to run. |
| infra | Local PostgreSQL Compose file and development configuration. | B1 coordinates common CI/deploy; B2 owns later browser-specific files. |
| migrations | One minimal initial revision and migration instructions. | A sequences later shared migrations. |
| tests/fixtures | Versioned shared JSON and local browser-page fixture. | Per-fixture owners; preserve IDs and simulation labels. |
| tests/contracts and tests/smoke | Real schema, import, API, DB and browser readiness tests. | Each owner extends relevant tests. |
| docs/setup and docs/handoffs | Actual commands, environment notes and setup handoff. | Setup owner initially; lane owners maintain feature instructions. |

Use two or three real Python workspace members if sufficient: API, contracts and an actually used browser-test package. Do not create ten empty installable packages or multiple competing lockfiles. Generate TypeScript declarations from canonical Python-exported JSON Schema/OpenAPI using a small documented tool; do not hand-maintain a second incompatible schema. Record the chosen generator and check drift in CI.

Register the basic UI routes and feature routers during setup so B1/B2/A/C do not all need to edit one main registration file for their first ticket. Leave future feature functions unavailable rather than adding speculative business logic.

## 6. Minimum shared contracts and fixture bundle

Define structural version-1 envelopes sufficient for typed fixtures and first feature implementation. Record draft versus frozen fields. Do not implement the full domain model. Each future task can extend its owned schemas compatibly.

| Contract | Minimum information | Important boundary |
| --- | --- | --- |
| SourceReference | Source/version ID, locator, provenance, capture/publication/reporting dates when known, hash reference. | Missing dates are explicit; no fake verification. |
| Fact / EvidenceBundle | Metric/value as decimal string, unit/scope/period, supporting refs, organization/pack/access context. | Fixture facts are labelled simulated; no real approval asserted. |
| Opportunity / RequirementSet | Funder/stream/cycle/stage IDs, source refs, conditions, uncertainty and requirement versions. | B1 owns funding requirements; a discovered link is not eligibility proof. |
| QuestionSet / ApplicationDefinition | Original text/ID/order/type, limit/unit/convention, conditions, attachments, source refs and conflicts. | B2 owns questions/field definitions; unknown units stay unknown. |
| AnswerSnapshot / ApprovalSnapshot | Exact content hash, answer/question version, dependency snapshot and authoritative approval reference. | Shape only; browser approval resolves through a server-side port, never a client approval Boolean. |
| FormMap / PrefillAction | Origin, form version/fingerprint, question/field IDs, selected answer/attachment references. | B2 has no submit/sign capability. |
| ValidationResult | Rule/version, pass/fail/needs_review/not_applicable, inputs/expected/observed, reasons and evidence. | No fabricated passing validators. |
| JobContext / JobResult | Job/task/actor ID, state, attempts/budgets, version snapshot, error and completeness. | Schema/protocol only; no claim of durable worker execution. |
| ChangeSet | Changed source/fact/pack/policy/requirement versions and affected dependency references. | Consumers must later stale their real state. |
| ErrorEnvelope | Stable error code, safe message, request/correlation ID and structured details. | Do not leak secrets or raw internal exceptions. |

Declare interfaces for CaptureStore, EvidenceProvider, ApprovedAnswerResolver and JobStore. Default unconfigured implementations fail explicitly. Test/fixture implementations must be injected deliberately and identified as fixtures. Do not implement A/C's full systems for their convenience or directly couple B features to their private database tables.

Create small consistent fixtures for organization demo-org; packs demo-a-v1/demo-b-v1; opportunity demo-gos; mission-q1; and form demo-gos-v1. Include one dated/simulated metric, one unknown eligibility condition, one conflicting limit, one future stale snapshot case and one typed failure. Generated sample data must have synthetic provenance. A fixture describing a 50-word mission field can be derived from the engineering baseline, but it is not proof that the original PDF has been parsed.

Validate fixture IDs and cross-references where this task uses them. When original partner documents are absent from the owner's folder, list that fact; do not invent source excerpts, quotes, current figures or a successful PDF extraction. The source material can be added through a later authorized input task.

## 7. Minimum running system

Implement a real web shell showing feature navigation and API connection/availability state. Use plain, accessible UI and distinct planned/fixture/unavailable states. B1/B2 pages can be entry points until their feature specs are executed.

Implement real liveness and readiness endpoints. Liveness reports process health without requiring the DB. Readiness returns ready only when the configured database connection and required migration revision work; database failure returns an explicit non-ready HTTP status. Expose a capability endpoint identifying which features are actually available, fixture-only or not implemented.

Use one local PostgreSQL configuration. Create only minimal organization/bootstrap metadata tables required to prove migration/seed/connectivity; leave full facts/applications/history to their owning specs. Provide an idempotent demo seed. Never silently switch a failed DB connection to SQLite or an in-memory production substitute.

Application keys remain server-side. Empty provider credentials must not prevent this no-provider bootstrap. Use an environment example containing names and dummy placeholders, not working secrets. Keep API/UI configuration separate so private keys cannot enter the browser build. Document local ports, CORS origins, DB URL and mode settings.

Default protected feature operations deny access or remain unavailable when no real identity/authorization provider is configured. A local-only, explicitly enabled fixture mode may use a fixed server-controlled demo identity with conspicuous labelling. It must be off by default for deployment, rejected in production configuration, and must not trust org_id/approved flags or arbitrary headers from a client. Test that condition. This is not production authentication.

## 8. Developer commands and CI

Provide documented root entry points for these operations. A Makefile is acceptable; also document underlying commands for systems without make. These names are commands the agent must implement, not claims that they already exist:

| Entry point | Required result |
| --- | --- |
| make bootstrap | Install/sync locked project dependencies without creating paid services or changing global settings. |
| make db-up | Start only the configured local development PostgreSQL service. |
| make migrate | Apply the actual shared migration history. |
| make seed-demo | Create/update fixture demo metadata idempotently; no production targets. |
| make dev-api / make dev-web | Run each service independently with documented ports. |
| make lint / make typecheck / make test | Real appropriate checks, with nonzero exit on failure. |
| make contracts / make contracts-check | Generate schema/types and detect drift; CI must not silently accept regenerated differences. |
| make build | Build actual frontend and applicable backend packages. |
| make smoke | Verify imports, API health/readiness and local DB migration/seed path. |
| make browser-smoke | Launch installed Chromium against a local static fixture and read a field value back. |

Browser installation may require a separate documented step. Playwright ties its package to compatible browser binaries; verify the actual installed pair. [R04] If OS/browser installation is unavailable, record the exact limitation and mark B2 browser readiness blocked; do not pretend the browser smoke passed. Preserve the remaining working setup.

CI should use lockfiles and separate clearly named Python, web, contract and DB/smoke checks. A browser readiness check can be separate, but must pass before claiming the B2 environment is ready. Keep external provider/network tests out of the no-secret default test run. Pin appropriate workflow dependencies and minimize CI permissions. GitHub protection/deployment configuration is reported as done only if actually configured under existing owner authorization.

Ignore secrets, .venv, node_modules, local DB volumes, logs, caches, downloaded inputs and local browser session artifacts. Keep lockfiles and deliberate schema-generated files tracked. Do not create fabricated GitHub usernames in CODEOWNERS; leave an explicit setup note if real reviewer handles have not been supplied.

## 9. Git and collaboration setup

Inspect existing Git state. If the folder already contains a repo, preserve its history/remotes and use a setup task branch/PR. Do not reinitialize, reset or change its remote because a sample name differs.

For a genuinely new repo, initialize locally. The first foundation commit is part of the owner's initial setup; this task permits that initial local commit on the chosen default branch. This is the bootstrap exception recorded in decision 0001, not ongoing permission for direct default-branch changes. If identity is absent, do not invent the human's name/email; finish files/tests and report the commit blocker. Do not modify global Git identity.

No remote URL or GitHub repository name has been supplied in this spec. Do local setup without inventing one. Configure/push a remote only if the owner supplies the target and authorizes the initial publication. Protect secrets and check the diff first. Record remote publication/PR status accurately. Lack of a remote does not block completion of local implementation, but it does block cross-machine PR integration until resolved.

After the foundation is accepted, B1 and B2 each start from the same accepted base commit in separate clones/worktrees and use task branches such as dev-b/b1-disc-001-foundation and dev-b/b2-auto-001-foundation. Do not start both write-capable agents in this same setup checkout. Specs for those tasks will be supplied after the setup report; do not create placeholder specs and call them approved.

## 10. Applicable deterministic checks and setup acceptance cases

The 86-check catalog is a product backlog. Bootstrap verifies only its actual setup boundaries. Do not change planned catalog statuses simply because a stub or test fixture exists. Cite these rule IDs where relevant and state the narrower coverage achieved:

| Case | Relevant rules | Required observation |
| --- | --- | --- |
| Archive extraction stays inside target | SEC-04; analogous SKL-03 confinement principle | Traversal/absolute/symlink/unexpected content is rejected; ordinary kit files import without overwriting edits. This is bootstrap input handling, not full skill-package security. |
| Shared DTOs reject malformed data | PKG-01, SEC-05 | Bad IDs/types and invalid fixture links fail; unknown/unimplemented capabilities are explicit. No claim that arbitrary skills/tools are validated. |
| Identity is server-controlled | SEC-01, SEC-14 | Client org/approval fields cannot grant rights; protected unconfigured operations deny. |
| Fixture mode cannot become production auth | SEC-01, SEC-13 | Production+fixture configuration fails; no cross-identity fixture data leaks. |
| Keys remain outside frontend/config artifacts | SEC-06 | No real keys committed or embedded in generated client output. Scanning alone is not proof of no secrets. |
| Fresh dependency install is reproducible | SEC-11 | Locked installs, import/type/build checks and recorded runtime versions. |
| DB readiness is truthful | JOB-04 boundary only | Healthy configured DB is ready; absent DB is non-ready; this does not establish durable job recovery. |
| Browser is actually usable | AUT-03 boundary only | Chromium opens the local fixture, reads its intended value, closes cleanly; this is not approved application prefill. |
| Contract generation is consistent | JOB-05 boundary only | Regeneration produces no unexplained drift; full validation cache invalidation is later work. |

Add direct bootstrap tests for repeat seed idempotency, clean imports, liveness/readiness distinction, unset API keys, clear unavailable-feature behaviour and exact fixture provenance. Prefer meaningful tests to tests that only assert a file exists. Do not write a broad fake implementation merely to make a check return pass.

## 11. Definition of Done and handoff

INIT-001 is complete locally when the actual scaffold runs; dependencies/versions are locked; documentation and templates are imported without silent loss; common contracts/fixtures validate; the DB migration/seed/readiness path works; the web shell renders actual API state; implemented checks pass; and limitations are recorded. Browser readiness and remote publication are separate explicit statuses. Missing required local prerequisites produce partial completion, not a fictitious green gate.

Produce `docs/handoffs/setup/INIT-001-setup-report.md` containing:

1. Actual repository tree, runtime/dependency versions and deviations from this default layout.
2. Exact successful commands, test results and omitted/failed commands with reasons.
3. Local services/ports, environment variable names, migration/seed revision and contract/type-generation commands; no secrets.
4. Which capabilities are real, fixture-only, unavailable and planned.
5. Git/default/setup branch, base commit, remote/PR URLs only if they exist, and protection status.
6. B1/B2/A/C folder ownership and shared-contract interfaces ready to consume.
7. Browser readiness, original-source availability, remaining prerequisites and blockers.
8. Instructions for a clean checkout and separate B1/B2 working directories.

Summarize that report to the owner. The report, actual tree and commit are the inputs for writing the next two feature specs. Do not start Dev B feature implementation in this initialization task.

## 12. Official references and limits

- R01: Vite getting started and templates: https://vite.dev/guide/
- R02: uv workspaces and shared lockfile: https://docs.astral.sh/uv/concepts/projects/workspaces/
- R03: FastAPI multiple files/APIRouter: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- R04: Playwright Python browsers and installation: https://playwright.dev/python/docs/browsers

These references were checked for this specification. The chosen project layout, scope limits, acceptance cases and initialization commands are project requirements; they are not vendor-provided guarantees. The execution agent verifies compatibility and actual results in the owner's environment.
