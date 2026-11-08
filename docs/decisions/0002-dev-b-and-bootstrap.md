# 0002: Dev B owns initial setup and runs two Dev B agents

- Author/developer: INIT-001 setup agent (Claude Code) on behalf of the project owner (Dev B)
- Date: 2026-11-07
- Status: accepted-maintainer (for the user decisions below); the stack choices are recorded separately as developer decisions in 0003
- Decided/accepted by and evidence: the project owner, via `docs/specs/INIT-001_Repo_Initialization.md` rev 1.0 (header "Confirmed assignment: Dev B", s1, s2, s9) and `docs/coordination/dev-b-two-agent-plan.md` rev 1.0 (s1, s2)
- Engineering path/version/sections: `docs/engineering/StrongStart_Engineering_Plan.md` v1.1, s3, s20, s23
- Feature spec path/revision: `docs/specs/INIT-001_Repo_Initialization.md`, revision 1.0
- PR / Issue: not published (no remote configured)
- Supersedes / superseded by: extends 0001; supersedes none. Item 3 (two Dev B agents) superseded by `0004-dev-b-single-agent.md` (2026-11-07)

## Original requirement

Engineering v1.1 s20 assigned parts of the initial bootstrap to several lanes and s3 proposes a module tree. Decision 0001 already records that the human project owner initializes the repository. INIT-001 s2 asks for a record of the specific owner decisions.

## Decision

These are **user decisions**, stated by the owner in INIT-001 and the Dev B plan:

1. The user (project owner) is **Dev B**. An earlier "my Dev C" phrase was clarified by the user to mean Dev B.
2. Dev B owns the **initial repository setup** (scaffold, tooling, CI baseline, first local commit).
3. Within the Dev B lane the user will run **two independent agents**: B1 (Funding Discovery and Research) and B2 (Application Intake and Browser Automation), each in its own clone/worktree from the same accepted base commit. Ownership boundaries are in `docs/coordination/dev-b-two-agent-plan.md` and `docs/coordination/ownership.md`.
4. INIT-001 **authorizes a setup agent** to execute the initialization on the owner's behalf, including `git init` and the initial local commit on the default branch (bootstrap exception noted in 0001; not ongoing permission for direct default-branch changes).
5. The engineering s3 module diagram remains a **baseline**, not a description of an existing file tree. The actual tree is in `docs/handoffs/setup/INIT-001-setup-report.md`.

Not user decisions: the concrete tools/versions/layout chosen during INIT-001 (npm workspaces, uv, oxlint, PostgreSQL 17, port numbers, etc.). Those are the spec's proposed defaults plus setup-agent developer decisions, listed in `0003-init-001-stack-and-layout.md`.

## Impact and coordination

- Dev A and Dev C receive registered feature entry points and shared contracts; their lane responsibilities in engineering s20 (after setup) are unchanged.
- B1 coordinates common CI/deploy and lockfile changes within Dev B; B2 requests changes to shared files through B1 or a reviewed PR.
- Both Dev B agents run under the same human authority; their mutual review is not independent peer approval.

## Validation and rollback

Documentation-only decision. It can be superseded by a later owner decision recorded as a new numbered file; do not rewrite this record.
