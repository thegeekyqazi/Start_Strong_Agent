# Dev B: Two-agent execution and integration plan

**Revision:** 1.0  
**Confirmed developer:** Project owner is Dev B.  
**Scope:** Two implementation agents inside the Dev B lane, alongside the team's separate Dev A and Dev C work.  
**Baseline:** Engineering v1.1, especially sections 6-7, 10, 13-17 and 20; AGENTS.md; INIT-001.  
**Status:** Work allocation and spec sequence. No feature implementation, agent sessions or GitHub messages have been started by this document.

## 1. Sequence

Run INIT-001 with one setup agent first. Accept a working foundation and record its actual commands/tree/contracts/base commit. Then run two agents concurrently in separate clones or worktrees from that same accepted base.

Their first feature specs will be written individually from that actual setup report, as requested by the owner. The task names below are planned work, not substitute approved feature specs. Do not ask both agents to implement this entire plan, the engineering PDF or the entire Dev B lane.

## 2. Independent feature ownership

| Agent | Owns end to end | Does not own |
| --- | --- | --- |
| B1: Funding Discovery and Research | Search, candidate discovery/deduplication, official funder capture, funding profiles/requirements, eligibility/deadline evaluation, monitoring, Find Funding UI, common Dev B CI/deploy coordination. | Application field maps, browser entry, answer approval, organization facts or model-generated proposal content. |
| B2: Application Intake and Browser Automation | Guide/form intake, questions/limits/conditions/attachments, representative portal, field maps, planned prefill, exact approved transfer, read-back/failure handling and automation UI. | New-funder search, granting eligibility decisions, actual organizational approval authority or final submission/signing. |

Both agents implement their own UI, backend/API, tests, documentation and handoffs. Neither becomes the other's frontend helper. Split further only when an actual bottleneck warrants it.

B1 owns the meaning of funding eligibility and funder-wide rules. B2 owns application questions, field-specific instructions, word/character limits and portal mappings. A guideline can contain both: preserve original support and produce distinct typed records rather than two incompatible versions of one giant RequirementSet.

## 3. File and shared-resource boundaries

Use the actual INIT-001 tree. If paths differ, document equivalents before writing code.

| Area | B1 primary paths | B2 primary paths |
| --- | --- | --- |
| Backend feature | services/api/.../features/funding | services/api/.../features/automation |
| UI feature | apps/web/src/features/funding | apps/web/src/features/automation |
| Contracts | funding/opportunity/eligibility schema files | application-definition/question/form-map schema files |
| Tests/fixtures | discovery, funder, eligibility and date fixtures | guide/form, browser, attachment and read-back fixtures |
| Infrastructure | Common CI/deploy configuration after bootstrap | Browser-specific image/config/Compose fragment |
| Handoffs | docs/handoffs/dev-b/b1-* | docs/handoffs/dev-b/b2-* |

The shared app entry point, common contract primitives, lockfiles, root environment example, main Compose file and migration head are coordination points. B1 coordinates common infra/lockfile changes within Dev B; B2 supplies a small requested patch/dependency list rather than both editing the same shared file independently. Dev A sequences shared DB migrations. Dev C owns the shared application shell and answer/approval interfaces after setup.

Individual owners can still contribute shared-file patches in a reviewed PR. Ownership means coordinate changes; it does not mean silently working around a required fix or waiting for hours when a compatible patch can be agreed.

## 4. Producer/consumer dependencies

| Consumer need | Producer | How work starts independently | Real completion gate |
| --- | --- | --- | --- |
| Original capture bytes/version/locator storage | A / shared CaptureStore port | B1 uses the setup's labelled fixture adapter. | Stored capture and evidence locations resolve through the actual store. |
| Organization/history facts for eligibility | A | B1 encodes unknown inputs and uses synthetic history fixtures. | Actual selected facts are source-linked; missing inputs remain unknown. |
| Selected opportunity/cycle and official guideline refs | B1 | B2 uses demo-gos and the supplied-guide/engineering fixture. | The selected opportunity and intake use consistent stream/cycle/source versions. |
| A downloaded guide/artifact from discovery | B1 via CaptureStore | B2 can accept an explicit file/capture fixture without waiting for broad search. | Intake consumes captured bytes plus original reference, not a citation-free summary. |
| QuestionSet/ApplicationDefinition | B2 | C and B1 can consume the shared fixture. | Imported questions/limits/conflicts preserve IDs and support. |
| Exact approved answer and dependency snapshot | C | B2 injects a seeded test resolver, clearly labelled fixture-only. | Real prefill resolves approval server-side and rejects stale/unapproved content. |
| Pack/requirements changes | A plus B1/B2 | Consumers receive a fixture ChangeSet in their tests. | Pending actions/answers use current versions and fail on relevant changes. |
| Browser service availability and constraints | B2 | B1 uses the documented service contract for deployment work. | Deployed network/auth/isolation configuration is tested, not inferred from local success. |

Do not make B2 wait for search: it starts from selected questions and a representative portal. Do not make B1 wait for C's writer: it can prove useful official discovery and eligibility unknowns independently. Do not let fixture approvals become a live authorization bypass.

## 5. Dev B's 18 deterministic checks

The engineering catalog's primary owner remains Dev B. This table assigns the implementation sub-owner; preserve the original IDs/priorities/meaning. Each future feature spec selects the applicable subset and exact acceptance cases.

| Check IDs | Sub-owner | What must be verified |
| --- | --- | --- |
| DAT-01 through DAT-05 | B1 | Date completeness, timezone/cutoff, cycle/stage, project window and historical/current suitability. |
| ELG-01 through ELG-04 | B1 | Missing inputs stay unknown; explicit eligibility, limit kinds and prior/invitation stages. |
| SEC-03 | B1 | URL/redirect/address and egress controls for capture; B2 must consume/enforce the same policy for its browser destination boundary. |
| SEC-11 | B1 | Common dependency/artifact release checks and CI policy; B2 supplies browser dependencies/images. |
| JOB-03 | B1 | Common budgets/timeouts/cancellation/retry policy; B2 contributes safe browser-write handling and enforcement. |
| AUT-01 through AUT-04 | B2 | Unique mappings, exact approved versions, read-back equality and attachment constraints. |
| SEC-08 | B2 | Exact origin/form/field/answer/attachment action authorization. |
| SEC-09 | B2 | No automated final-submit/sign operation; representative endpoints deny automation-principal submission. |

B1 has 12 primary check assignments and B2 has 6. Counts are not estimates of equal effort: browser and portal handling can consume more time than several simple predicates. Both agents consume A/C-owned checks such as authorization, source validity, content-version approval, counter conventions, pack invalidation and job idempotency. Do not duplicate a weaker local version merely because the real producer is not ready.

Record per-rule implementation/test evidence. Planned checks do not become passing checks through ownership assignment, a schema or a UI badge. Model-derived interpretation is distinct from deterministic predicate evaluation.

## 6. Feature-spec sequence

| Round | B1's next spec | B2's next spec | Shared checkpoint |
| --- | --- | --- | --- |
| Foundation | INIT-001 handled once by the setup agent. | Same accepted foundation; no independent second setup. | G0: actual tree/commands/contracts are recorded. |
| First parallel increment | B1-DISC-001: typed opportunity/search/capture slice with official support, clear failures and a Funding screen. | B2-AUTO-001: typed question/limit intake and representative-form inspection with an Automation screen. | G1: B1 opportunity/capture refs can be consumed by B2 without schema rewriting. |
| Second parallel increment | B1-DISC-002: reviewed deadline/eligibility predicates, query profiles, repeat search/change detection. | B2-AUTO-002: server-resolved approved prefill, read-back, conditional fields and attachment checklist. | G2: requirements/draft/approval/prefill join real A/C adapters where available. |
| Stabilization | B1-OPS-001: deployed capture/jobs/network controls, quotas and CI/release checks. | B2-AUTO-003: browser failure recovery, stale-snapshot rejection and pack-change response. | G3: deployed behaviour matches claimed capabilities and failures remain visible. |

Do not write all these specs in advance. After each completed ticket, use its code, handoff, test results, current contracts and blockers to write the next one. The first two specs can be created after INIT-001 and executed in parallel; later specs adapt to what the team actually built.

The first B1 increment should include an actual public provider when configured, with recorded fixtures for tests and explicit missing-key status. The first B2 increment can use the original guide only when its bytes are available; otherwise demonstrate a labelled engineering-derived question fixture. Never call that fixture a successful document extraction.

## 7. Grunt work allocation

| Work | Primary owner | Handoff |
| --- | --- | --- |
| Initial repo, scaffold, commands and CI baseline | Project owner/setup agent | INIT-001 setup report to A/C/B1/B2. |
| Public official-source seed list and cached capture | B1 | Query/capture provenance and source versions. |
| Funding profile/date/eligibility fixtures | B1 | Conditions, known/unknown inputs and expected deterministic results. |
| Guide question transcription/limit conflict inventory | B2 | IDs, locators when available, count units and unresolved conflicts. |
| Local representative portal and dummy attachment | B2 | Explicit fixture label, origin/form versions and expected values. |
| Provider-key names, quotas and deployed common service settings | B1 | Names/config requirements only, never credentials in notes. |
| Browser installation/image/isolation prerequisites | B2 | Exact versions, smoke results and service contract for B1. |
| Shared DB migration sequencing | A | B1/B2 provide bounded migration requests. |
| Real approved-answer resolver | C | B2 supplies exact required interface, not its own approval authority. |

## 8. Branches, messages and review

Start one task branch per agent from the accepted foundation commit. Publish small draft PRs with engineering/task/rule citations and exact validation. Use separate notes such as docs/handoffs/dev-b/b1-disc-001-r1.md and b2-auto-001-r1.md. Never have both agents overwrite one Dev B status file.

At task start and dependency boundaries, read relevant upstream PR/Issue/handoff updates. For a new schema, name version, source commit, consumer action and actual producer/fixture status. Consumers acknowledge which version they read. GitHub does not automatically update another checkout or wake another agent.

The human Dev B coordinates these two sessions. Agents may review each other's technical work, but both run under the same human's authority and may use the same GitHub identity. Such feedback is not an independent GitHub peer approval and never evidence of factual truth. Use Dev A/C's real teammate review where repository rules require it. All merges follow the owner-approved PR policy.

## 9. Integration and completion

At G1, connect B1's real captured guideline/artifact to B2 intake and verify opportunity/cycle/source IDs and error cases. At G2, connect actual A evidence/version/access and C approved-answer resolution. B2's prefill must reject missing/stale approvals; B1's eligibility must preserve missing history as unknown. Fixture-only seams remain marked until replaced and tested.

Before release, B1 deploys common services; B2 verifies actual browser constraints. Exercise a changed funder requirement, ambiguous limit, closed/unknown deadline, partial capture, unapproved answer, altered form, truncation and pack-change invalidation. Tests must observe outcomes and real read-back values, not just final model text.

Each agent fixes its own module and publishes a final handoff. Dev B reports the joined outcome to C, the team integration coordinator. Preserve final staff submission/signing control. Reserve the stabilization capacity from engineering section 20; do not defer the first real B1/B2 seam until the final merge window.

## 10. Inputs for the next specs

After INIT-001, provide its setup report, actual repo tree, accepted base commit, available commands and any blockers. That is sufficient to draft B1-DISC-001 and B2-AUTO-001 against the real foundation. If the repo is connected, use exact refs to inspect it; otherwise the report and relevant files are adequate. No paid API key or partner portal login is needed to write these first scoped specs.
