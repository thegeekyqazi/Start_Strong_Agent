# C4-SKL-001 — Thin practice generator and draft preview

**Revision:** 1.0  
**Date:** 2026-11-08, America/Toronto  
**Status:** Ready for the next implementation assignment; prepare now, execute after the DATA-001 checkpoint.  
**Engineering owner:** Project owner, former A/B/C engineering; one coding agent, sequential milestones.  
**UI/UX owner:** Sawaab. Preserve the current redesign and shared presentation.  
**Repository:** `thegeekyqazi/strong-start-agent`  
**Observed main:** `41a80efc477044203cf94cc44a289c56a50003f3`. DATA-001 PR #20 is open at `ba7eed4434a262ea4895f43f1dd4e5401ac79db5`; do not assume it is merged or hosted-verified.  
**Suggested branch:** `dev-c/c4-skl-001-practice-preview`  
**Repo destination:** `docs/specs/C4-SKL-001_Thin_Practice_Generator_and_Draft_Preview.md`

## 1. Goal and scope decision

Deliver a small, working skill-generation feature for the hackathon: a reviewed policy source produces a source-linked practice proposal, deterministic compilation and screening records; staff review and activate an exact version; the active practice changes the instructions/checks used by a real draft preview. Revocation or a source-policy change prevents subsequent use. A malicious candidate visibly fails the gate.

**This is the next feature priority after DATA-001's usable checkpoint.** Do not require DATA-002, a general JobStore, broad real-evidence integration or a new provider platform before starting it.

The owner explicitly authorized reducing breadth and presenting some features as prototypes because time is limited. This task implements a **thin C4 slice**, not full completion of C4/G3/G4 or all 16 SKL rules.

### 1.1 Required working path

1. Select a short immutable writing-policy source, or add a bounded plain-text source.
2. Review it explicitly as an organizational practice source for one defined scope.
3. Generate a structured candidate using the existing configured model adapter.
4. Show exact source passages, proposed rules and a deterministic compiled package.
5. Run bounded scans, a recorded model-screening signal and deterministic rule tests.
6. Let authorized staff approve the exact hash and activate it for that scope.
7. Generate/check an answer preview with the active practice, showing what was used and its source.
8. Revoke it or publish a new policy version; a subsequent preview must refuse the old release.

### 1.2 Deliberately narrow integration

The functional integration is on the **Skills page's draft-preview workflow**, reusing C's real draft/render/check services through a public boundary. It does not automatically inject practices into all normal Applications requests.

**Deferred:** connecting skill versions into saved answer/approval snapshots, reviewed exports, B plans/grants and all normal drafting. That wider integration would require coordinated dependency/version changes across C and A4. Do not sidestep it by applying an unrecorded practice to an already approved answer.

Preview outputs carry `working_preview_only`, exact release/dependency identities and explicit `approval_permitted=false`. They cannot create an approval or authorize prefill. Do not add an automatic “approve/export/prefill this preview” shortcut. Existing normal Applications/Review functionality remains governed by its current contracts.

This boundary is a deliberate time-saving scope decision, not a claim that practice dependencies are irrelevant to future approvals.

## 2. Minimum deliverable and deferred breadth

| Area | Required now | Deferred / prototype only |
| --- | --- | --- |
| Source input | Existing reviewed text source or bounded `text/plain`; exact versions, quotes and authority record. | PDF/OCR/ZIP ingestion, connectors, bulk extraction. |
| Practice language | Two finite types: preferred terminology and protected program/name wording. | Arbitrary workflow instructions, broad semantic style compiler, dynamic rule language. |
| Proposal model | Existing ModelAdapter with strict output validation, no tools. | Additional providers, coding-agent backends, multi-agent consensus. |
| Screening | Deterministic scans plus one bounded existing-model screening adapter with honest coverage. | Training/hosting a dedicated attack classifier. |
| Staff review | Source-to-rule confirmation, flags, test evidence, exact-hash approval/activation. | Enterprise roles/admin console; do not invent production authentication. |
| Draft effect | Real C draft preview with resolved practice and deterministic findings. | All Applications/approval/export/browser dependency propagation. |
| Storage | PostgreSQL/TigerData-compatible durable source/candidate/release/audit state. | A new distributed queue, lease system or general workflow engine. |
| Export | Deterministic restricted text/JSON package from the compiler. | Third-party skill import, automatic installation, auto-update, arbitrary archive extraction. |
| Invalidation | Source revision/revocation at dispatch and after model work; optional managed A4 identity check when supplied. | Complete reverse invalidation across every product consumer. |
| UX | One usable Skills page matching Sawaab's current tokens/components. | Another navigation/theme redesign. |

Do not reduce correctness controls for an enabled action to save time. If screening/currentness is unavailable, preserve the proposal and show the missing prerequisite; activation stays disabled.

## 3. Baseline reconciliation and prerequisites

Observed repository facts:

- The Skills page is still a placeholder under `apps/web/src/features/skills/`.
- C's `WritingPolicy` supports terminology rules and protected names; reuse those semantics where appropriate.
- `StructuredTask.operation` currently allows drafting/planning/reviewer tasks, not skill proposal/screening. A compatible extension is required.
- The current Gemini adapter permits simulated, engineering-derived and public inputs; it excludes supplied material by default. Do not silently broaden routing permissions.
- A4 has an in-process public currentness facade, but its existing guarded registration is browser-specific. Do not pretend it already registers C4 releases.
- DATA-001 PR #20 adds `0009_durable_applications`, a PostgreSQL AnswerStore, state/audit unit of work and stable durable epochs. Its observed PR still says hosted verification pending; local evidence is not cloud verification.
- Main's observed CI is failing after UI changes; PR #21 removes a Google Fonts import and has green PR CI. Neither its merge nor final resolution is assumed here.

Before coding, inspect actual upstream and the DATA-001 local handoff. Use the accepted DATA-001 implementation after it is integrated, or an owner-selected clean dependency base. Do not merge PR #20/#21 automatically, discard the in-progress worktree or rewrite Sawaab's redesign. Record any known baseline failure separately from new failures and coordinate a narrow fix rather than weakening tests.

A pending hosted operational test does not require rebuilding persistence. Continue against the accepted PostgreSQL implementation while keeping the hosted verification gap visible. No new TigerData account, service or paid resources are needed for C4.

## 4. Read first and working agreement

Read current `AGENTS.md`, directory guidance, accepted DATA-001 handoff/decision, INT-001 public contracts and:

- Engineering Plan v1.1 §§4–5, 8.2–8.3, 9, 11, 12.1–12.4, 13.1–13.3, 15–18, 20–21.
- `StrongStart_Check_Catalog.json`: SKL-01…16; applicable SEC-01/02/05/06/07/10/13/14 and JOB-02/03/05.
- Existing C service/model/coordinator/policy/check implementations and actual persistence abstractions.
- `knowledge.public`, current source/version types, and the Skills feature registration/shell.

Create a dedicated task branch, preserve all existing work and use one coding agent. Implement sequential checkpoints and publish through a draft PR. No default-branch push, automatic merge, deployment or parallel replacement implementation.

Keep C4 code in a feature-owned module, for example `features/skills/`, with one router registration. Shared adapters should be public/typed; do not import a router's private helper or read another feature's tables to avoid publishing a seam.

Document this preview-only scope as an explicit owner-authorized reduction from the full C4 plan. Keep the original engineering document and historical handoffs intact. Commit task-specific decisions and current feature-status updates.

## 5. Approved practice source: one bounded authority bridge

The original brand playbook may still be unavailable. A family story, financial statement or funder page does not automatically establish organizational writing policy.

Provide a narrow policy-source adapter with these distinctions:

- **Existing supplied/public material:** retain its real source ID/version/hash/locator and provider data classification. Staff must explicitly approve its use for the selected organizational practice scope.
- **Administrator-authored practice:** store the exact staff-entered text and approval identity/version as the authority basis; do not pretend it came from an ingested document.
- **Synthetic demo policy:** clearly label it simulated, including its approval as a local fixture action. This is sufficient for the hackathon demonstration when private material is missing.

Use a fixed server-owned demo context/program mapping when real scope metadata is absent. Do not infer an authoritative program from model prose or let a request assign itself organization/role permissions.

### 5.1 Immutable text and exact evidence

Store source ID/version, exact UTF-8 text/hash, title, provenance, program/context scope, effective/current revision, authority status and actor/time. Text upload is bounded, for example 16 KiB; make actual limits explicit engineering budgets.

Every proposed rule needs at least one resolvable source span: source version/hash, Unicode code-point start/end and exact quote. Server verifies quote equality and bounds against the stored text. No fetching a URL to fill missing evidence. These checks establish identity, not semantic entailment; staff must confirm that each rule follows from its source.

Approving source use does not approve every generated rule. Publishing another source version makes the prior source noncurrent for this scope. Keep historical text/approvals available. Reapproval is explicit, not a silent overwrite.

### 5.2 Small, honest demonstration source

Add a new versioned synthetic source containing two simple instructions for a registered demo program, such as:

- Prefer “reading volunteer” over “tutor” in this demo program's narrative.
- Preserve the registered demo program name exactly.

Label these as invented demonstration practices, not Strong Start's actual brand policy. Keep existing fixture files/hashes untouched. Add one deliberately conflicting source version and one planted hostile candidate fixture for negative tests.

## 6. Strict candidate, compiler and package

### 6.1 Finite candidate schema

Introduce Pydantic contracts in a feature-owned shared module, following existing StableId, provenance and strict request conventions. Suggested logical entities:

- `PracticeSourceVersion` and `PracticeAuthorityRecord`.
- `PracticeCandidateVersion` with source snapshot, task/program/context scope and rule proposals.
- `CompiledPracticePackage` with compiler/template/mapping versions, fixed file map and canonical hash.
- `PracticeScreeningReport`, deterministic test report, exact-hash review and release state.
- `ResolvedPractice` and `PracticeDraftPreview` with immutable input/output identities.

Unknown fields are rejected. The model cannot supply organization, approvals, status, screening completion, capabilities, tests-passed or activation records.

Mandatory operators:

| Operator | Typed operands / effect |
| --- | --- |
| `preferred_term` | Forbidden/preferred literal phrase, bounded application/program scope and explicit matching convention. Maps to reviewed terminology code. |
| `protected_name` | Exact registered name and optional acronym/first-use behavior supported by existing policy code. No free-form rewrite expression. |

Do not add arbitrary regex, Python, shell, SQL, template execution, network URLs, tool names, install hooks, dynamic imports or executable resources. Protected core evidence/approval/submission behavior is never an operand.

No current impact figures, budgets, targets or other mutable facts may become generated instruction constants. Existing fact-slot rendering stays authoritative. Source excerpts may contain dated information, but quoting it does not turn it into a reusable current-number rule.

Keep budgets small: one selected policy source, one context, up to three rules, bounded strings and one preview question. Broaden only after the complete path passes.

### 6.2 Deterministic compiler

Compile only the validated structured proposal. Derive readable instructions from fixed templates and typed operands, not a model-generated executable body. Copy exact source citations and provenance into a reviewable source map.

The compiler produces a fixed allowlisted file map, for example:

- `SKILL.md`: readable scope and compiled practices.
- `rules.json`: typed finite policy records.
- `references/policy-excerpts.md`: authorized exact excerpts and labels.

No model-selected paths, external includes, symlinks or arbitrary files. Hash canonical manifests/file bytes with explicit compiler/template/source versions. Exclude wall-clock timestamps from reproducible build identity or bind them as fixed inputs. Identical approved inputs compile identically.

Export a bounded JSON/text representation of these exact files; ZIP import/export is unnecessary. This is a restricted application package, not a claim of compatibility with every coding-agent skill runtime. Never install it into Claude/Codex/OpenCode automatically.

If a candidate changes, create a new immutable version/package hash. Old screening, tests and approvals cannot authorize the edited version.

## 7. Proposal and screening adapters

### 7.1 Proposal generation

Extend or wrap the existing ModelAdapter with a typed `propose_practice` operation and strict JSON schema. Reuse coordinator timeouts, data-class checks, tool-less requests and safe errors. One bounded call per click, no retry loop or new provider framework.

Pass only the authorized text/scope required for this candidate. Documents and examples remain untrusted model input. Parse bounded JSON, reject duplicate keys/deep nesting/unknown fields, and independently verify every returned source reference/quote.

The proposal is non-deterministic. Store the actual response-derived candidate and provider metadata; do not claim a fresh regeneration is the same reviewed version.

Missing configuration or provider rejection is visible and never falls back to a fake live success. Explicit fake adapters remain useful in tests and a separately labelled fixture preview; they do not establish live generation/screening.

### 7.2 Deterministic screening

Inspect metadata, structured operands, compiled files, examples and referenced excerpts. Record inspected artifact hashes and scanner version. Scan raw text plus bounded normalized views for instruction-override/exfiltration patterns, hidden controls/zero-width characters, executable requests, disallowed paths and synthetic-secret canaries.

Use only reviewed static patterns/finite checks in application code. Do not run candidate-provided regex. Bound normalization/decoding; never recursively expand arbitrary encoded blobs or follow includes. Record normalized/raw locations clearly.

Flag suspicious phrases with context; do not ban ordinary words such as “system” globally. A benign quoted attack example may need review without establishing malicious intent. Structural capability/code violations are rejected independently of the language model.

Known secret matches are quarantined and redacted in previews/errors; do not export or send detected credentials to the screening model. Real local credential files are not test fixtures and must never enter this workflow.

### 7.3 Bounded model-screening signal

Implement a `ScreeningAdapter` using the existing configured model if needed. Identify it honestly as a **model-based screening signal**, not a dedicated, calibrated security classifier. Generation and screening may use the same backend; agreement is not independent truth.

Return versioned structured findings such as `no_flags`, `review`, `block` or `unknown`, with bounded spans/reasons and inspected input identity. Server records which parts/chunks it actually sent; the model cannot self-certify complete coverage. Screen source-to-rule meaning separately through explicit staff confirmation.

For the thin package, one bounded request covering all parts is preferred. If the package exceeds the budget, reject/hold it or implement complete bounded chunk coverage. Never silently truncate a trailing rule, metadata field or reference.

Timeout, malformed output, unsupported content, blocked provider routing, missing chunks or inconclusive result means screening incomplete. A new generated release cannot activate. No keyword-only or canned “safe” fallback. Test-only screening doubles must be explicit dependency overrides and labelled; they cannot be configured as the normal live runtime.

The result is a review signal. Even `no_flags` requires deterministic checks, tests, provenance confirmation and authorized exact-hash approval.

## 8. Review, activation and live validity

Use explicit states from the engineering plan where applicable: proposed, screened/testing, needs_review, approved, active, suspended, revoked and superseded. Persist the reason for any hold/rejection; no “safe” badge based only on a classifier label.

### 8.1 Review gate

The review panel shows scope, package hash, exact source-to-rule map, deterministic findings, screening completeness/provider, test report, conflicts and simulated labels. Require staff to confirm source support and acknowledge each reviewable finding with a rationale. Hard violations, incomplete screening, failed tests or unresolved conflicts cannot be acknowledged into a pass.

Only a server-derived authorized identity can create review/activation records. Local fixture mode may use the existing fixture-staff identity, with explicit fixture labels and production denial. Do not build or imply new production authentication.

### 8.2 Activation

Activation requires the exact expected candidate/package hash, source/current scope revision, current screening/test hashes and review identity. Store one active release per bounded context. A repeat of the same request may be idempotent; changed payload with a reused key conflicts.

Serialize source revision, activation, supersession and revocation through actual PostgreSQL locks/CAS, using the accepted DATA-001 engine/configuration. The source-currentness check and activation write must share the guarded commit boundary. Do not implement a check-then-write race in separate transactions.

No DB lock is held during model/screening calls or draft generation. Capture expected state, do external work, then guard persistence against changed state. State mutation and required audit commit together.

### 8.3 Resolve at use time

A public resolver returns only a currently active, authorized release for the exact server-resolved context/task/program. It verifies hashes, source authority/revision, screening/test identity and revocation/supersession state. Unknown/out-of-scope/stale data never silently substitutes another release.

Check again after long model work and before publishing the preview. If the release/source changes during the call, refuse to present the result as a current applied practice. Preserve it only as a clearly stale working result if the contract supports that; do not silently relabel it.

Source changes/revocation must stop the next use even if a cached release was previously active. Public GETs may compute effective suspended/stale state without rewriting immutable history. They must not activate or refresh approval.

If the source includes an actual managed A4 binding, use the supported knowledge facade to compare the exact active identity before/after use. Missing verification blocks that managed path. Do not claim a browser-only registration method already supports skills or mark all A4 consumer integration complete. An unmanaged synthetic policy is valid for the labelled thin demo and uses real C4 policy revision checks.

## 9. Draft-preview integration and visible effect

Publish a narrow Applications-owned preview interface that reuses the real workspace/model/render/check pipeline. C4 supplies a resolved immutable practice through that boundary; it does not copy C's renderer or import route-private helpers.

The preview request selects a real question-set/question/evidence identity plus the server-resolved practice context. The server resolves all content and current releases. Do not accept client-provided compiled instructions, active flags, organization IDs or model permissions.

Compose with the existing writing policy; never replace core controls. Conflicting practices/base policy produce a visible hold, not last-writer-wins. The practice may add narrow terminology/protected-name guidance and deterministic findings, not suppress source/number/word-limit checks.

The result contains:

- Exact question/evidence/pack identities and current data labels.
- Applied practice release ID/version/package hash, source versions and instruction snapshot hash.
- Model/provider/fixture information and the actual generated template/rendered answer.
- Existing C check report plus practice-specific findings and plain-language next actions.
- `working_preview_only=true` and `approval_permitted=false`.

Provide a baseline-versus-active comparison using the same selected question/evidence/model configuration. The baseline disables only this generated practice; it must not disable the organization's existing policy or evidence checks.

Show an inspectable applied-instruction trace and a deterministic example check: a text containing the old term is flagged with the preferred term after activation, while protected wording is checked. This proves the compiled practice is consumed. Do not guarantee an LLM will always follow it or present two canned drafts as live model evidence.

If useful, let staff check a bounded working-text sample through the same preview checker. Client text remains untrusted draft content and grants no authority. No reviewed export/prefill or persisted approval can be created from the preview route.

## 10. Minimal API, storage and UI

### 10.1 Public API responsibilities

Use a feature-owned prefix such as `/api/skills`; finalize names at M0. Minimum operations:

- List/create/read immutable policy sources and explicitly review their practice authority.
- Generate/read a candidate version and compiled package.
- Run/read screening and deterministic tests.
- Review/approve, activate, revoke and read effective release state.
- Resolve current scoped release through a public in-process port.
- Create/read a working draft preview; download only supported exact compiled artifacts.

Separate typed commands and read responses. Identity resolves before reads/provider calls; other-org and unknown resources are indistinguishable. Every long operation has bounded input/time/call budgets and safe errors. Double clicks cannot create duplicate activations or uncontrolled paid calls.

### 10.2 Durable storage

Use the accepted DATA-001 PostgreSQL/TigerData configuration. Add only the C4 tables needed for policy versions/authority, immutable candidate/package, screening/test reports, reviews/releases/active pointer, preview provenance and audit. Reuse existing typed audit/redaction logic and transaction infrastructure where appropriate; do not claim independent transactions are atomic together.

Sequence migrations from the actual current head. PR #20 proposes 0009, but do not assume the next number or modify its released migration. Preserve exact schema/storage versions and hashes. Restart must retain active/revoked state and evidence; no automatic activation on seed/restart.

### 10.3 Skills page

Replace the Skills placeholder, using Sawaab's existing components/styles. One page or compact set of panels is enough:

1. Source and scope, with provenance and explicit authority review.
2. Proposed practices and side-by-side supporting excerpts.
3. Scans/screening/tests with understandable findings and incomplete states.
4. Exact-hash review, activate/revoke and current release state.
5. Draft preview, applied-instruction trace and before/after example check.

Show loading/error/conflict/stale states and preserve selection when a provider fails. Render all content inertly; no raw HTML/remote images. Missing screening shows a held proposal, not a disabled page with no explanation.

No theme, router, font or global layout overhaul. Publish a short component/API handoff for Sawaab before modifying shared frontend interfaces.

## 11. Deterministic fixtures and release-gate coverage

Support the enabled subset of SKL checks; preserve catalog status honesty. Do not mark all SKL-01…16 tested because this preview works.

| ID | Required executable acceptance |
| --- | --- |
| C4-01 | Strict schemas/budgets reject unknown fields, extra authority flags, unsupported versions, duplicate keys and excessive nesting/bytes before dispatch. |
| C4-02 | Every rule quote/span/hash matches the exact authorized source version. Wrong quote/version/other-org source is refused. |
| C4-03 | Unreviewed webpage/story cannot become practice authority; explicit source review is distinct from candidate review. Synthetic/admin-authored sources retain correct labels. |
| C4-04 | Unknown operators, code, arbitrary regex, dynamic includes, tool permissions and unregistered paths are rejected. Ordinary text mentioning a benign keyword is not globally banned. |
| C4-05 | Same validated input/compiler/source snapshot yields byte-identical file map/hash. A metadata character change produces a new hash and invalidates prior review/screening. |
| C4-06 | Only fixed text/JSON files export. No scripts, symlinks, network fetches or automatic local skill installation. Unsafe/quarantined packages cannot export. |
| C4-07 | Raw/normalized/hidden-content scans record coverage/locations. A planted override/secret/exfiltration candidate is held/rejected with inert/redacted output. |
| C4-08 | Screening covers metadata, rules, compiled text and references for the exact hash. Timeout/unknown/malformed/truncated/missing-last-part prevents activation. |
| C4-09 | Provider/data-class routing runs before calls. Supplied/restricted content is not sent to a disallowed provider; missing live keys do not invoke fake success. |
| C4-10 | The model cannot assert source approval, tests-passed, screened-complete or active state. A `no_flags` signal alone cannot activate. |
| C4-11 | Deterministic positive/negative rule cases prove terminology/protected-name behavior, matching conventions, context exclusions and conflicts with base policy. |
| C4-12 | The staff review binds exact package/source/screening/test snapshots. Incomplete/failed hard gates cannot be overridden by an acknowledgment checkbox. |
| C4-13 | Repeated activation is idempotent for the same command; changed request key payload and concurrent incompatible activation conflict. One active release per context. |
| C4-14 | Event-controlled source revision racing activation either wins and blocks stale activation, or follows activation and makes the release unusable. Actual lock/commit evidence, no sleep-based proof. |
| C4-15 | Another program/context cannot use this release. Unknown context does not fall back to a global practice. |
| C4-16 | Real C preview resolves an active release, passes compiled guidance to the configured adapter and returns the applied hashes, actual C rendering and checks. No canned draft called live. |
| C4-17 | Baseline comparison preserves core policy/evidence/number checks. The same sample's old term is flagged by the activated practice with the source-linked preferred term. |
| C4-18 | Preview response cannot approve/export/prefill; forged client instructions/approval flags/selectors cannot bypass the preview-only boundary. Existing normal approval/prefill paths remain unchanged. |
| C4-19 | Revoke/source revision after activation blocks the next preview, including cached resolutions and after API restart. Historical packages/reviews remain readable. |
| C4-20 | Revoke/source change during a model call prevents publishing a current successful preview; no long DB lock spans the call. |
| C4-21 | Managed A4 identity, when present, is rechecked; actual replacement blocks managed use. Unmanaged synthetic demo is not labelled A4-integrated. |
| C4-22 | Durable source/candidate/release/audit round-trip preserves exact hashes and state across independent app instances; no memory fallback on DB outage. |
| C4-23 | State/audit failure rolls back the associated mutation; unknown write outcome does not trigger automatic activation replay. |
| C4-24 | Normal UI/API path supports source review → generate → screen/test → exact review/activate → preview → revoke, with labels and useful errors. |
| C4-25 | Missing classifier/key/routing permission produces a saved held proposal and explicit next action. There is no new generated-skill activation fallback. |
| C4-26 | Non-synthetic fixture adapters are never implied: test-only generation/screening overrides stay test-only; live/fixture evidence is separated in reports. |
| C4-27 | Production fixture identity/activation remains forbidden; cross-org IDs are hidden; secret/HTML payloads do not leak or execute. |
| C4-28 | Existing DATA-001/INT-001 contracts, source/number/approval/export and browser safeguards pass regression checks; normal drafting is not silently modified. |
| C4-29 | A real API/PostgreSQL/Chromium test drives the thin flow with explicit model test doubles. A separate bounded live-provider rehearsal, when configured, records actual model generation/screening without claiming a safety benchmark. |
| C4-30 | Final feature matrix/hand-off explicitly distinguishes this working preview slice, deferred full Applications integration, synthetic source authority and any missing live verification. |

Keep a small adversarial corpus: forged approval field; unsupported executable operator; hidden instruction; quoted benign attack example; canary secret; wrong-source quote; incomplete classifier trailing chunk; source-edit activation race; revoked-during-draft case. Report rule/model signals separately from staff judgments.

No multi-agent agreement test establishes truth. No classifier label is a deterministic security proof. Use fixture doubles for reproducibility and a separately labelled live rehearsal for integration evidence.

## 12. Implementation milestones and time guardrails

### M0 — Ready base and scope contract

Inspect DATA-001/current main/UI handoffs, record actual dependency commit and CI state, commit this spec and its preview-only scope decision. Freeze the two operators, source authority/quote semantics, screen adapter, storage contract and Sawaab interface boundary.

### M1 — Source, compiler and persistence

Implement bounded policy input/review, strict candidate/package contracts, deterministic compiler, DB migration/repository and exact source map. Add the synthetic policy and hostile fixtures. Core authority is server-derived; no fake auto-approved seed.

### M2 — Screening, tests and release gate

Implement bounded proposer/screening adapters, raw/normalized scans, finite rule tests, exact-hash staff review, transactional activation/revocation and source-currentness resolver. Prove incomplete-screening and activation/source-race cases.

### M3 — Draft preview and usable Skills page

Connect real C draft/render/check code through a public preview boundary. Build the thin UI, instruction trace, baseline example check and meaningful held/error/stale states. Verify actual model payload receives the selected compiled guidance.

### M4 — Rehearsal and publication

Run required checks, the real API/DB/browser path, malicious/changed-source demos and a bounded live rehearsal if configured. Publish handoffs and draft PR. Reserve the remaining project time for integration/rehearsal; do not start optional provider, archive, scheduler or all-app propagation work.

If a prerequisite is unavailable, finish the source/compiler/review UI and expose the hold honestly. Do not remove activation gates to manufacture a successful demonstration. A review-only proposal prototype is a valid reported partial result; it is not full completion of the working path above.

## 13. Verification and reproducible demo

Discover current commands first. Run targeted compiler/screening/release/concurrency tests, then the appropriate final checks:

```bash
make contracts
make check
make smoke
make browser-smoke
```

Extend real PostgreSQL smoke/CI for the new persistence/release tests. Default pytest excludes DB/browser markers and is not enough. Do not run destructive smoke/reset commands against a hosted/shared target; use DATA-001's selected environment and owned synthetic records.

Keep the live demo small: one source, two finite rules, one question and one configured model. A bounded live rehearsal may use one proposal call, one package-screen call and preview calls within an explicit recorded budget. If unavailable, show clearly labelled fixture/prototype evidence and keep live activation prerequisites intact.

Suggested demonstration, about three minutes:

1. Open the synthetic approved policy and explain that the real playbook can replace it through the same adapter.
2. Generate a candidate; inspect its exact source-to-rule map.
3. Run screening/tests and show their limits.
4. Review/activate exact hash; preview an answer and inspect applied guidance/checks.
5. Revoke or update the policy; show that reuse is blocked.
6. Open the planted bad candidate; show the failed gate without executing anything.

Do not call a fixed before/after sample a live model comparison. Do not describe synthetic policy wording as partner guidance, a benign corpus as exhaustive attack coverage, or this preview slice as full grant approval integration.

## 14. Deliverables and completion report

Commit:

- This spec and a dated preview-only C4 scope/contract decision.
- Feature-owned Python contracts, deterministic compiler, policy source/release repository, screening/test adapters and public APIs.
- Bounded Applications preview integration and the Skills UI using current presentation.
- Forward migration(s), regenerated schema/types and targeted DB/unit/API/browser tests.
- `docs/handoffs/dev-c/c4-skl-001-practice-preview-r1.md` with C4-01…30 evidence.
- `docs/handoffs/dev-c/c4-skl-001-demo-guide.md` with reset-safe preparation, live/fixture modes, changed-source and malicious-candidate steps.
- `docs/handoffs/dev-c/c4-skl-001-ui-contract.md` for Sawaab.
- Updated feature/capability matrix, explicitly marking full Applications/approval/export/browser skill integration deferred.

Final report/PR: exact branch/head/PR, dependency commits, migrations, spec/engineering/check references, actual model versus fixture evidence, commands/results, scope deviations, remaining holds and a short demo script. Name any baseline CI failure and whether it is actually resolved. No blanket all-SKL/all-86/G3/G4/production-ready claim.

The feature is complete for this thin scope when its source-reviewed candidate can pass actual enabled checks, be staff-activated, affect the real draft preview, and become unusable after revoke/source change, with persistent state and reviewable evidence. Export and activation remain separate; no personal coding-agent skill is installed.

## 15. Ready-to-paste Claude Code prompt

```text
After reaching the agreed DATA-001 checkpoint, implement C4-SKL-001 revision 1.0.
Read docs/specs/C4-SKL-001_Thin_Practice_Generator_and_Draft_Preview.md in full.
If supplied outside the repository, copy it there first.

Inspect current Git status/upstream, DATA-001 handoffs and Sawaab's UI work. Preserve
unfinished work. Start a dedicated feature branch from the accepted dependency base;
do not assume PR #20 or the CI fix is merged, and do not merge them automatically.

I own former A/B/C engineering. Use one coding agent and sequential M0–M4.
Time is limited: deliver the thin path rather than broad infrastructure.

Build one source-reviewed practice → strict proposal → deterministic compiler →
complete scans/model screening → staff exact-hash review/activation → real C draft
preview. Include revocation/source-change invalidation and a malicious candidate.
Use only two finite rule types, existing model adapters and durable PostgreSQL/TigerData
configuration. Preserve synthetic labels and all core evidence/approval/browser controls.

The working integration is the Skills-page preview, not all Applications/approvals/
exports/prefill. Preview cannot authorize those actions. Do not silently apply an
unrecorded skill to saved answers. Incomplete screening holds activation; no fake-safe
fallback. Do not install generated skills or add executable resources/providers.

Preserve Sawaab's presentation. Run applicable C4-01…30 cases and required checks,
write handoffs/demo instructions, push the task branch and publish a draft PR under
repo policy. Do not merge/deploy or expand into DATA-002 or full C4 breadth.
Report actual live/fixture evidence, remaining limits, exact head/PR and demo steps.
```

## 16. Pinned references

- [Observed main](https://github.com/thegeekyqazi/strong-start-agent/commit/41a80efc477044203cf94cc44a289c56a50003f3)
- [DATA-001 PR #20 — observed open](https://github.com/thegeekyqazi/strong-start-agent/pull/20)
- [CI font-import fix PR #21 — observed open](https://github.com/thegeekyqazi/strong-start-agent/pull/21)
- [Existing Skills placeholder](https://github.com/thegeekyqazi/strong-start-agent/blob/41a80efc477044203cf94cc44a289c56a50003f3/apps/web/src/features/skills/Page.tsx)
- [Engineering plan: full C4 requirements](https://github.com/thegeekyqazi/strong-start-agent/blob/41a80efc477044203cf94cc44a289c56a50003f3/docs/engineering/StrongStart_Engineering_Plan.md)
- [Current check catalog](https://github.com/thegeekyqazi/strong-start-agent/blob/41a80efc477044203cf94cc44a289c56a50003f3/docs/engineering/StrongStart_Check_Catalog.json)
- [Existing finite WritingPolicy](https://github.com/thegeekyqazi/strong-start-agent/blob/41a80efc477044203cf94cc44a289c56a50003f3/services/api/src/strongstart_api/features/applications/rules/policy.py)
- [Existing model task interface](https://github.com/thegeekyqazi/strong-start-agent/blob/41a80efc477044203cf94cc44a289c56a50003f3/services/api/src/strongstart_api/features/applications/models/base.py)
- [Existing C draft/render/check service](https://github.com/thegeekyqazi/strong-start-agent/blob/41a80efc477044203cf94cc44a289c56a50003f3/services/api/src/strongstart_api/features/applications/service.py)
- [Existing A4 public facade](https://github.com/thegeekyqazi/strong-start-agent/blob/41a80efc477044203cf94cc44a289c56a50003f3/services/api/src/strongstart_api/features/knowledge/public.py)
- [Observed DATA-001 unit-of-work implementation](https://github.com/thegeekyqazi/strong-start-agent/blob/ba7eed4434a262ea4895f43f1dd4e5401ac79db5/services/api/src/strongstart_api/features/applications/postgres_store.py)
