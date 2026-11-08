# DEV-B consolidation: one Dev B agent, merged state, open work and dependencies (r1)

- Author/lane: Dev B consolidated agent (Claude Code, claude-opus-5-5) for the project owner (Dev B)
- Intended consumers: project owner; Dev A; Dev C; future Dev B sessions
- UTC timestamp: 2026-11-08T05:30Z (local 2026-11-07)
- Status: ready-for-review (documentation only)
- Task spec path/revision: none; this is the owner's coordination-consolidation instruction. Arrangement in `docs/decisions/0004-dev-b-single-agent.md` and `docs/coordination/dev-b-single-agent-plan.md` rev 1.0
- Engineering version/sections and rule IDs: v1.1 s3, s20.2-20.7, s22; Dev B rules AUT-01..04, DAT-01..05, ELG-01..04, JOB-03, SEC-03, SEC-08, SEC-09, SEC-11 (statuses unchanged)
- Branch: `dev-b/coordination-consolidation`, base `origin/main` `45b4488` (merge of PR #2)
- PR / Issue links: see the PR for this branch
- Supersedes / superseded by: consolidates `b1-disc-001-r1.md`, `b2-auto-001-r1.md`, `b2-auto-001-r2.md` and `b2-auto-001-check-evidence.md`. Those stay valid as the per-task records.

## What is merged on `main` (`45b4488`)

| Task | PR | Merge | Summary |
| --- | --- | --- | --- |
| INIT-001 | (bootstrap commit) | `ad5b8dd` | Monorepo foundation |
| B1-DISC-001 | #1 | `8df9df8` | Find Funding: bounded Tavily search and Firecrawl single-page capture adapters, both **live-unverified**; labelled fixture providers; development-only `LocalCaptureStore` with hash-verified, org-scoped `CapturedDocumentReader`; `CapturedDocument` schema "1"; Funding UI |
| B2-AUTO-001 | #2 | `45b4488` | Automation intake (fixture/structured JSON/HTML/capture); engineering-derived representative portal; read-only Chromium inspection with fingerprint `b2-form-fp/1`; `AutomationHandoffExport` `b2-automation-handoff/1`; Automation UI; funding→automation capture seam joined (development store, fixture provider) |

CI on `main` passed for both merges (runs `42441490661`, `42443188804`). PR review consisted of owner comments from the same GitHub identity the agents used. That is not independent peer review.

## Validation in this worktree

| Command | Result |
| --- | --- |
| `make check` on unchanged `main` (after a locked `npm ci`; the new worktree had no `node_modules`) | exit 0: ruff/format/oxlint/Prettier clean; mypy 84 files clean; pytest **261 passed**, 15 deselected; Vitest **24 passed**; contracts-check; build. Matches `b2-auto-001-r2.md` |
| `make smoke`, `make browser-smoke` | not run: this change is documentation-only and touches no runtime code, migration or browser path |
| Live Tavily/Firecrawl | **not run**. This worktree has no `.env`. Credentials are configured only in the old worktrees, and the values were not read |

## Old worktrees (inspected read-only; nothing deleted or changed)

| Worktree | Branch / state | Unpublished work | Recommendation |
| --- | --- | --- | --- |
| `../strongstart-b1` | `dev-b/b1-disc-001` @ `b8c067e`, equals `origin/dev-b/b1-disc-001`, fully in `main`; clean | None tracked. Ignored: `.env` (**holds the Tavily/Firecrawl/Gemini keys**; names checked, values not read), `.venv`, `node_modules`, caches, `dist`, possibly `.local-data/` captures | Retire after the owner copies the needed `.env` entries into `strongstart-dev-b/.env` |
| `../strongstart-b2` | `dev-b/b2-auto-001` @ `068e39e`, equals remote, fully in `main` | Untracked `B1-B2_Parallel_Launch.md` and `B2-AUTO-001_...md` are **byte-identical** to the tracked `docs/` copies. Ignored `.env` has the same key names | Retire. The untracked copies are redundant |
| `../Start_Strong_Agent` (primary checkout) | `main` @ `ad5b8dd`, **14 commits behind** `origin/main` | Three untracked spec/agreement copies, all byte-identical to tracked files. Ignored `.env` (no provider keys), `.bootstrap-input/` | Keep (primary checkout). Fast-forward when convenient; the untracked copies can be removed by the owner |
| local branch `backup/b2-auto-001-pre-rebase` @ `782fe78` | never pushed | Pre-rebase B2 commits. Every file differs from `main` only by the later G1/B1-merge additions; nothing unique was found | Delete after review, or keep as a local backup. Owner choice |

Retirement commands are owner actions and were not run, e.g. `git worktree remove ../strongstart-b2` (refuses if dirty; ignored files are removed with the directory).

## What remains incomplete

Funding module:
- **Live provider verification: NOT RUN.**
- No production artifact store; production capture returns `store_unavailable`.
- Candidates are not `Opportunity`/`RequirementSet` records yet, so their opportunity/stream/cycle IDs are null. Automation therefore omits the shared `QuestionSet` projection for real captures.
- No deadline/eligibility predicates: DAT-02/04/05 and ELG-02..04 planned; DAT-01/03 and ELG-01 partial.
- No durable jobs, repeat search or change detection; SEC-11 scanners/release policy planned.
- SEC-03 residual: the provider does the fetch, and there is no connection-time egress or DNS-rebinding control.

Automation module:
- No prefill, read-back or attachment enforcement (AUT-02/03 planned; AUT-04 representation only).
- No SEC-08 action grants.
- No PDF/prose guide parsing; no original partner guide present (fixtures are engineering-derived).
- Counting conventions `unknown`.
- Inspection is fixture-origin only and not production network isolation.

Shared:
- All 86 catalog rules remain `planned`.
- Request-bound operations remain recorded deviations, pending a JobStore.

## Discrepancies found (code vs engineering plan vs earlier handoffs)

1. **Engineering G1 is not met.** Engineering s20.7 defines G1 as "real B questions render with limits/conflicts" in C's editor (B+C). `b2-auto-001-r2.md` uses "G1" for the internal funding→automation capture seam, which *is* joined. C1 still renders the fixture `demo-gos-questions-v1`. The B+C seam closes when C2 consumes `AutomationHandoffExport`.
2. **Ticket label collision.** Engineering s20.4 tickets B1-B4 (search; GOS intake/RequirementSet; prefill/read-back; repeat discovery/deploy) differ from the Dev B task series. B2-AUTO-001 covered engineering B2 intake plus B3's inspection part. No `RequirementSet` is produced yet (engineering B2), and B1-DISC-002 is the planned owner of it. Mapping: `dev-b-single-agent-plan.md` s7.
3. **Tiger Data owner.** Decision 0003 row 7 assigned Tiger Data confirmation to B1 at deploy time. The owner now assigns Tiger Data to Dev A; a pointer was added to 0003 and decision 0004 records the change.
4. **No branch protection.** `main` is unprotected (`gh api` 404). AGENTS.md and the coordination README assume required PR checks/reviews. The PR rule is currently procedural only.
5. **Windows portability (reported by Dev A, A1 r1).** 12 Dev B tests fail on Windows:
   - `LocalCaptureStore` fsyncs a directory via `os.open(dir)`, which Windows denies (`features/funding/store.py:86`);
   - the repo has no `.gitattributes`, so CRLF checkout changes fixture bytes, and B1's stored hashes no longer match.
   
   Linux CI passes. This is not fixed here (runtime/test change); it is a candidate for the next funding task or a small fix PR.
6. **Stale publication statements in historical handoffs.** `b1-disc-001-r1.md` says "draft PR, not merged" and `b2-auto-001-r1.md` says "not published". Both PRs are merged; the records were left as written.
7. **Ownership table vs code.** `ownership.md` listed `services/browser/` as B2's browser location. The inspector actually lives in `features/automation/` (B2 decision item 6). The table now notes this.
8. **Module labels in code.** `Capability.owner` and contract `x-owner` still say `B1`/`B2`. This is intentional; they are now module labels (decision 0004 item 5).

## Internal Dev B acknowledgments now closed (self-review, not independent)

- The funding module accepts automation's consumer mapping of `CapturedDocument` schema "1" (`record_from_captured_document`, `B1CaptureSource`). It also accepts the additive `CaptureLineage` fields (`provider_reported`, `producer`, `producer_source_reference_hash`, `producer_supported_representations`) and the dual `export.py` registration pattern. Decision `dev-b-b2-auto-001-intake-slice.md` items 7-8 are therefore accepted within Dev B, by the same agent and identity.

## Consumer action / blockers

- **Owner:**
  1. Review this PR.
  2. Copy the needed `.env` entries into `strongstart-dev-b/.env`, then retire `strongstart-b1`/`strongstart-b2`.
  3. Decide on `backup/b2-auto-001-pre-rebase`.
  4. Consider enabling branch protection.
  5. Choose the next Dev B task (`dev-b-single-agent-plan.md` s7). For the main path, B2-AUTO-002 is the engineering-critical one.
- **Dev A:**
  - Provide the supported artifact-store port preserving `CapturedDocumentReader` semantics (A2).
  - Own Tiger Data/DB configuration that Dev B's deployment will consume.
  - Specify the capture-to-knowledge import contract.
  - Provide the A3 runner, A4 ChangeSet and JobStore when available.
  - Dev B owes A the acknowledgment on PR #3 (dev store remains until the import seam).
- **Dev C:**
  - Consume `AutomationHandoffExport` in C2 to close engineering G1.
  - Provide the real `ApprovedAnswerResolver` (C3) for B2-AUTO-002 completion.
  - Dev B owes C the acknowledgments requested on PR #4 (`.env.example` names, `test_api.py` line, `.shell > nav` scoping) after reading that PR's diff.
- **Blockers:** none for the consolidation. The real G2 path is blocked on A2/A3 and C3.

## Acknowledgments

None yet from A or C.
