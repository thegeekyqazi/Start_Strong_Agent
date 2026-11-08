# 0004: One Dev B agent owns both Dev B modules

- Author/developer: Dev B consolidated agent (Claude Code, claude-opus-5-5) on behalf of the project owner (Dev B)
- Date: 2026-11-07 (America/Toronto)
- Status: accepted-maintainer (items 1-4 are the owner's instruction); items 5-7 are developer-decision
- Decided/accepted by and evidence: the project owner, in the consolidation task instruction for this session ("The B1/B2 arrangement has ended. You now own both modules, working sequentially in one dedicated worktree and one task branch at a time." and "TigerData integration belongs to Dev A.")
- Engineering path/version/sections: `docs/engineering/StrongStart_Engineering_Plan.md` v1.1, s3, s20.2-20.7, s22
- Feature spec path/revision: none (coordination task; no feature spec)
- PR / Issue: branch `dev-b/coordination-consolidation` (see its PR)
- Supersedes / superseded by: supersedes item 3 of `0002-dev-b-and-bootstrap.md` (two Dev B agents); supersedes the B1 deployment assignment for Tiger Data in `0003-init-001-stack-and-layout.md` row 7. Supersedes the session/coordination parts of `docs/coordination/dev-b-two-agent-plan.md` rev 1.0 and `docs/coordination/b1-b2-parallel-launch.md` rev 1.0.

## Original requirement

Decision 0002 item 3 and the two-agent plan split Dev B between two concurrent agents: B1 (funding discovery/research) and B2 (application intake/browser automation), in separate worktrees. They coordinated shared files through B1 and exchanged acknowledgments. Decision 0003 row 7 asked B1 to confirm Tiger Data compatibility at deploy time.

## Decision

Owner decisions:

1. **One agent.** A single Dev B agent owns both Dev B modules. It works sequentially, one task branch at a time, in the dedicated worktree `strongstart-dev-b`. There are no concurrent Dev B sessions.
2. **IDs and boundaries stay.** Task IDs (`B1-DISC-*`, `B1-OPS-*`, `B2-AUTO-*`), module boundaries (funding vs automation), contract modules and Dev B's 18 catalog checks are unchanged. "B1" and "B2" now name **modules/task series**, not agents.
3. **History is preserved.** Specs, decisions and handoffs from the two-agent period stay as written. The parallel-agent instructions are marked superseded where they no longer apply; nothing is deleted.
4. **Tiger Data belongs to Dev A.** Tiger Data (hosted PostgreSQL) integration is Dev A's work, with Dev A's database baseline and migrations. Dev B's deployment work consumes A's database configuration and does not choose or configure the database service.

Developer decisions for applying this:

5. **Module labels in code stay.** Runtime labels such as `Capability.owner="B1"/"B2"` (`features/funding/router.py`, `features/automation/router.py`) and the JSON Schema `x-owner: B1/B2` stay as module identifiers. Renaming them would change API output and generated contracts, which this documentation-only task must not do. A later feature task may rename them deliberately, with consumer notice.
6. **Shared-file coordination.** The B1-to-B2 "send a patch request" rule no longer applies inside Dev B. Shared files Dev B coordinates (`infra/compose.yaml`, `.github/workflows/`, root `package.json`/lockfiles, `.env.example`) still change only through a reviewed PR that names affected A/C consumers.
7. **Handoff names.** Module task handoffs keep the `b1-*` / `b2-*` prefixes. Cross-module Dev B notes use `dev-b-*`.

## Impact and coordination

- Dev A and Dev C: no contract, route or runtime change. Dev B's producer/consumer obligations are unchanged; one agent now answers for both modules. Dev A now owns Tiger Data; see `docs/coordination/dev-b-single-agent-plan.md` s4.
- B1/B2 internal acknowledgments that were still open, mainly B1 acknowledging B2's `CapturedDocument` consumer mapping, are closed as a **self-review by the same agent and identity**. That is not independent review (see the consolidated handoff).
- Old worktrees `strongstart-b1` and `strongstart-b2` are no longer working locations. Retirement is an owner action; the findings are in `docs/handoffs/dev-b/dev-b-consolidation-r1.md`.

## Validation and rollback

Documentation-only. `make check` was run on the unchanged `main` baseline as the starting point. To return to two agents, append a new numbered decision; do not rewrite this record or 0002.
