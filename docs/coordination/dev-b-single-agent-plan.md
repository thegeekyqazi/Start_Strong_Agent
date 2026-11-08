# Dev B: single-agent working plan

**Revision:** 1.0
**Authority:** decision `docs/decisions/0004-dev-b-single-agent.md` (owner instruction, 2026-11-07).
**Supersedes:** the session and coordination parts of `dev-b-two-agent-plan.md` rev 1.0 and `b1-b2-parallel-launch.md` rev 1.0. Their technical content stays in force as listed in s6.
**Baseline:** engineering v1.1, s6-7, s10, s12-17, s20, s22; AGENTS.md.
**Status:** working arrangement. It is not a feature spec and does not authorize the next feature.

## 1. Arrangement

- One Dev B agent owns both Dev B modules and works **sequentially**: one active task, one task branch, one PR at a time.
- Worktree: `strongstart-dev-b`, Dev B's only write location. It needs its own `.env`; it does not inherit the old worktrees' configuration. Names only are in `.env.example`; never copy credentials into notes.
- Each new task branch starts from current `origin/main`: `dev-b/<task-id-lowercase>` (for example `dev-b/b2-auto-002`).
- Each task still gets its own spec in `docs/specs/` before code, written from the merged code and latest handoffs. Do not write all future specs in advance.
- Integration goes only through reviewed PRs; never merge directly. `main` has **no server-side branch protection** (checked 2026-11-07, `gh api .../branches/main/protection` → 404). The PR rule is procedural until the owner configures protection. The agent uses the owner's GitHub identity, so its PR comments are not independent peer review.

## 2. Modules (unchanged)

| Module | Task series | Owns | Does not own |
| --- | --- | --- | --- |
| Funding (discovery/research), label `B1` | `B1-DISC-*`, `B1-OPS-*` | Search, candidates/dedup, official capture, funding profiles/requirements, eligibility/deadline predicates, monitoring, Find Funding UI; Dev B common CI/deploy | Field maps, browser entry, answer approval, organization facts, model-generated content |
| Automation (intake/browser), label `B2` | `B2-AUTO-*` | Guide/form intake, questions/limits/conditions/attachments, representative portal, field maps, approved prefill, read-back/failure handling, Automation UI | New-funder search, eligibility decisions, approval authority, final submission/signing |

Paths are in `ownership.md`. Funding owns funding eligibility and funder-wide rules; automation owns application questions, field instructions, limits and portal mappings (two-agent plan s2, still in force). Cross-module calls inside Dev B use the published contracts: `CapturedDocument` / `CapturedDocumentReader` from funding, and `CaptureSource` / `record_from_captured_document` in automation. They never use another module's private functions. One owner does not license merging the modules.

## 3. Dev B's 18 checks (catalog owner: Dev B; module assignment unchanged)

| Check IDs | Module | Status after B1-DISC-001 / B2-AUTO-001 |
| --- | --- | --- |
| DAT-01..DAT-05 | funding | DAT-01, DAT-03 partial (unknowns kept, no parsing); DAT-02, DAT-04, DAT-05 planned |
| ELG-01..ELG-04 | funding | ELG-01 partial (always `unassessed`); ELG-02..04 planned |
| SEC-03 | funding (automation enforces at its browser boundary) | partial: capture URL policy plus fixture-only browser routing; no connection-time egress control |
| SEC-11 | funding (automation supplies browser deps) | planned (no scanners or release policy) |
| JOB-03 | funding (automation contributes browser handling) | partial: timeouts, caps, no retries; no token budgets or cancellation |
| AUT-01..AUT-04 | automation | AUT-01 inspection/mapping subset; AUT-04 representation only; AUT-02/03 planned |
| SEC-08 | automation | inspection scope only; action grants planned |
| SEC-09 | automation | inspection subset: no submit capability; fixture endpoint denies |

The evidence is in `docs/handoffs/dev-b/b1-disc-001-r1.md` and `b2-auto-001-check-evidence.md`. All 86 catalog rules remain `planned` in the catalog JSON. A subset being tested does not mean the rule is implemented.

## 4. Dependencies on Dev A and Dev C

| Need | Producer | Current state (2026-11-07) | Dev B action |
| --- | --- | --- | --- |
| Supported artifact store for capture bytes (replaces funding's development-only `LocalCaptureStore`) | A (CaptureStore, s20.3) | Not available. A1 (PR #3, draft) stores knowledge source bytes in PostgreSQL `BYTEA` and says B should not couple to its tables. A2 is to add an A-owned artifact-store port. Production capture returns `store_unavailable`, and capture intake is 503 | Keep the `CapturedDocumentReader` semantics as the migration seam (org-scoped, unknown and other-org indistinguishable, hash verified on read). Propose or acknowledge the org-aware store port when A publishes it |
| Capture-to-knowledge import (captured guideline → evidence) | A (write port) | Not specified (A1 handoff) | Wait for A's import contract; preserve capture/artifact/source IDs and hashes |
| Database: Tiger Data / hosted PostgreSQL, migrations | **A** | Local PG 17 via Compose; A sequences migrations (`0002_source_fact_foundation` is on A's branch) | Funding/automation need no migration yet. Send bounded migration requests to A. Deployment consumes A's DB config and does not configure Tiger Data |
| Organization/history facts for eligibility (ELG-*, DAT-05) | A | Only the simulated demo fact (A1) | Missing inputs stay `unknown` |
| Validation runner (Dev B registers DAT/ELG/AUT rules) | A (A3) | Not available | Rule predicates stay in feature code with tests; register when A3 lands |
| ChangeSet / pack-change invalidation | A (A4) | Fixture only (`FixtureApprovedAnswerResolver` stales on applied ChangeSet) | B2-AUTO-003 consumes it |
| Identity/authorization (SEC-01) | A | INIT fixture identity only | No new identity paths; route shared-host changes to A for review |
| JobStore (durable jobs) | A with C | `UnconfiguredJobStore` | Request-bound operations remain a recorded deviation (both decision records) |
| Real `ApprovedAnswerResolver` and approval snapshots | C (C3) | Fixture only; C plans it for C3 | B2-AUTO-002 prefill uses only the server-resolved resolver; it rejects missing or stale approvals and never self-approves |
| Consumption of `AutomationHandoffExport` / `QuestionSet` (engineering G1 B+C) | C (C2) | C has read r1/r2 but not acknowledged; C1 still uses the fixture `demo-gos-questions-v1` | Answer C's questions. Keep `b2-automation-handoff/1` stable or version it |
| Counting conventions (APP-01) | C | Reported as `unknown` by automation | Do not invent conventions |
| Shared shell/components | C | C1 (PR #4, draft) adds reusable components and `.shell > nav` scoping | Acknowledge the C-requested items on PR #4 (s5) |

## 5. Open acknowledgments addressed to Dev B

| From | Request | Where |
| --- | --- | --- |
| A (A1 r1) | Acknowledge that funding capture stays on its development store until an import seam is specified | PR #3 |
| C (C1 r1) | Acknowledge the three new `.env.example` names (Dev B coordinates that file) | PR #4 |
| C (C1 r1) | Acknowledge the C line in `tests/unit/test_api.py` (`applications` now `unavailable` by default, new `applications.model`) and the `.shell > nav` CSS scoping | PR #4 |

Post these on the named PRs at the next checkpoint. They have not been posted by this consolidation task.

## 6. What remains in force from the superseded documents

- `dev-b-two-agent-plan.md`: s2 ownership meaning, s4 producer/consumer table, s5 check sub-ownership (as module ownership), s6 spec sequence and task IDs, s9 integration expectations.
- `b1-b2-parallel-launch.md`: s3 capture-to-intake seam semantics and s4 execution and safety defaults. That includes fixture origin vs public capture policy, no silent refetch, and request-bound operations as a recorded deviation.
- Superseded parts: two sessions and worktrees, the B1/B2 shared-file patch protocol, inter-agent acknowledgments, and "no remote exists" (`origin` is github.com/thegeekyqazi/Start_Strong_Agent).

## 7. Next tasks (IDs retained; one at a time; owner chooses order)

| Next spec | Engineering ticket (s20.4) | Hard dependencies |
| --- | --- | --- |
| B2-AUTO-002: server-resolved approved prefill, read-back, conditional fields, attachment checklist | B3 | C3 real resolver for completion (fixture resolver can start it); A/C current-version checks |
| B1-DISC-002: reviewed deadline/eligibility predicates, Opportunity/RequirementSet from reviewed captures, query profiles, repeat search/change detection | B1 remainder, part of B2 (RequirementSet) | A facts (unknowns otherwise), JobStore for repeat search |
| B1-OPS-001: deployment, capture/jobs/network controls, quotas, CI/release checks (SEC-11) | B4 | A database/Tiger Data config, JobStore |
| B2-AUTO-003: browser failure recovery, stale-snapshot rejection, pack-change response | B3/B4 | A4 ChangeSet, C3 approvals |

Engineering gate G1 (s20.7: "real B questions render with limits/conflicts" in C's editor) is **not** yet met. The Dev B "G1" in r2 is the internal funding→automation capture seam. The B+C seam is joined when C2 consumes `AutomationHandoffExport`.

## 8. Update 2026-11-08: DEV-B-BUNDLE-002 delivered (rev 1.1 of this plan)

Sections 1-7 above are kept as written (rev 1.0). This section records what DEV-B-BUNDLE-002 rev 1.0 delivered on draft PR #12. That PR is **not merged**; see `docs/handoffs/dev-b/dev-b-bundle-002-r1.md`.

| Area | Delivered (tested subsets) | Still open |
| --- | --- | --- |
| Automation (B2-AUTO-001A, superseded) | Immutable saved definitions, public `ApplicationDefinitionReader`, case-context binding for captured HTML forms | C2b consumption (B+C G1) |
| Funding (B1-DISC-002, bounded) | Capture library; funding cases with verified anchors and version-bound review; DAT-01..04 / ELG-01..04 predicates with scenario reports; saved searches, manual reruns, rechecks and change observations | Durable scheduled monitoring (needs a JobStore); evidence-backed inputs (needs an A fact mapping); A3 registration of B predicates (A-side extension point); DAT-05 |
| Portability (B1-OPS, scoped) | No-clobber writes, explicit durability policy, `.gitattributes` for hash-sensitive fixtures | Deployment/release hardening (B1-OPS-001); a real Windows run |
| B2-AUTO-002 | **Not started** | Needs C3's real `ApprovedAnswerResolver` and action gates |

Check-table update: DAT-01..04 and ELG-01..04 now have implemented and tested **subsets** behind B-owned rule functions. Catalog statuses are unchanged. AUT-01..04, SEC-03/08/09/11 and JOB-03 are as listed in s3, except that saved searches and rechecks reuse the existing JOB-03 budgets (one request, no retry).

Dependencies changed since rev 1.0:
- A3's runner merged (PR #13) with a closed source-rule registry;
- C3 (PR #10) is open but not merged, so the resolver is still unavailable.

## 9. Update 2026-11-08: B2-AUTO-002 takeover checkpoint

This section supersedes the stale B2-AUTO-002 "not started" and C3/C2b dependency entries above. One Dev B agent continues the existing `dev-b/b2-auto-002-approved-prefill` branch and draft PR #17, preserving `a2b8146` and merging inspected upstream `e6df77a` normally. No parallel Dev B sessions or feature task was started.

- **P0 complete; P1 fixture/harness complete:** exact approved plans, atomic single-use claims, restricted Chromium entry/live read-back/final reread, held requirements and attachment checklist, explicit Automation UI, concurrency mutation evidence and full verification. Runtime has no seeded approvals; integrated C3, real portals, upload and submission remain unavailable.
- **P2 pending:** C3 #10 is merged; C2b #18 now consumes B's exact saved question-set IDs. The remaining C blocker is a public approved-content reader returning the consistent exact template/rendered envelope with separate hashes, live dependencies and producer epoch. The requested contract remains a proposal; C's snapshot-only resolver cannot supply text.
- **A4:** merged at `0007_pack_replacement`; dependency/currentness HTTP contracts acknowledged as available, but the in-process B consumer factory remains requested, not integrated. No loopback HTTP/private-store bridge is added.
- **P3:** verification/publication of the partial P1 increment. Full B2-AUTO-002/G2 remains pending P2; the PR stays draft and is not merged.
- Applicable catalog subsets now have task evidence for AUT-02/03 and SEC-08, with AUT-01 mapping, AUT-04 checklist, SEC-03 registered-fixture routing, SEC-09 and JOB-03 bounded-action coverage. Catalog-wide statuses are not rewritten and no 86-check completion is claimed.

Exact implementation ref, public versions, AUTO2-01..32 evidence, failures, omissions, test results, decisions and consumer asks: `docs/handoffs/dev-b/b2-auto-002-approved-prefill-r1.md`. Next Dev B action is P2 when C publishes/acknowledges the reader. Keep funding work sequential and separately scoped.
