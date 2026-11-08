> Current engineering ownership (2026-11-08): the project owner owns former A/B/C
> engineering and migration sequencing; Sawaab owns UI/UX. INT-001 uses one agent,
> sequential milestones. See [decision 0005](../decisions/0005-int-001-engineering-takeover.md).
> Historical lane instructions below remain context; machine-readable owners are unchanged.
> Current status: [INT-001 handoff](../handoffs/integration/int-001-approved-content-currentness-r1.md).

# Three-agent coordination and repository setup

## Recommended arrangement

Use one GitHub repository, three separate clones or worktrees, one short-lived branch per task, and PR review into the shared default branch. The project owner creates the initial repo and scaffold. Each developer configures their own agent's authorized GitHub access through a CLI, connector or MCP that can read the assigned repository and task discussions. Use their own account/credential scopes; do not share tokens.

GitHub is the shared source of record. Repository Markdown stores durable decisions and handoffs; Issues/PR comments carry timely updates before those files merge. This is asynchronous collaboration. A Git push transfers content to the remote, but does not move other checkouts, wake agents or refresh their context.

## What is included

| Path | Role |
| --- | --- |
| AGENTS.md | Concise repository-wide instructions for all three agent lanes. |
| CLAUDE.md | Small import bridge to the same AGENTS.md; avoid duplicate rule copies. |
| .github/PULL_REQUEST_TEMPLATE.md | Reviewable change/spec/deviation/test/dependency record. |
| docs/engineering/StrongStart_Engineering_Plan.md | Engineering v1.1 baseline, copied unchanged. |
| docs/engineering/StrongStart_Check_Catalog.json | All 86 planned checks and ownership, copied unchanged. |
| docs/decisions/0001-agent-working-agreement.md | User's later setup/spec/PR instructions and baseline override. |
| docs/decisions/TEMPLATE.md | Meaningful implementation-deviation/decision record. |
| docs/handoffs/TEMPLATE.md | Source-linked task handoff and consumer acknowledgment fields. |
| docs/coordination/README.md | This workflow and runtime-loading notes. |
| docs/specs/README.md | Where future per-feature development specs belong. No feature spec has been generated yet. |
| docs/coordination/ownership.md, dev-b-single-agent-plan.md | Added after INIT-001: current path/contract owners and the Dev B single-agent arrangement (decision 0004). `dev-b-two-agent-plan.md` and `b1-b2-parallel-launch.md` are kept as partly superseded history. |

The kit is documentation and templates. It does not initialize the repo, install agents, configure GitHub protections, create Issues/PRs or run a message service. Copy the files into the repo you initialize, preserving any existing guidance and reconciling conflicts through a small documentation PR. No raw partner source documents or secrets are bundled.

## Your setup checklist

1. Initialize your chosen stack and normal startup/test commands. Retain the actual stack in task specs even if it differs from a proposal in engineering v1.1.
2. Add this instruction kit and commit the engineering baseline. The setup-owner/PR/spec decisions are recorded in decision 0001 rather than silently rewriting the baseline.
3. Give each developer their lane and selected task. Open one Issue per task/contract boundary if that helps tracking; write the acceptance criteria and producer/consumer dependencies there.
4. Configure default-branch rules to require PRs, suitable passing checks and peer review where your GitHub plan supports them. Configure bypass settings intentionally. Instructions in a Markdown file do not enforce server-side rules. [R04]
5. Start agents in their own clones/worktrees and verify loaded instructions. Make a small docs/contract PR and confirm each agent can read it.
6. Record actual test/start commands in repo documentation once setup exists. Do not fill this kit with invented package commands.

Initial documentation can be part of your initial repository creation. After the working agreement is in force, normal changes use task branches/PRs. Do not invent an additional long-lived integration or communications branch just to share notes.

## How Dev A's note reaches Dev B and C

Example: A finishes a retrieval contract change for A2.

1. A's agent writes `docs/handoffs/dev-a/A2-evidence-bundle-r1.md` on `dev-a/a2-source-ingestion`. The note names the schema version, actual source/fixture status, implementation commit and tests; it states what B/C must do.
2. A commits the note and implementation, pushes that task branch and opens/updates a draft PR. If the note and code are one commit, use branch/path to locate the note and then attach the returned full commit SHA in the PR. Do not try to place a file's own commit SHA inside that same commit.
3. A adds an update in the linked Issue/PR: what changed, recipients, exact branch/commit/path and the requested response. Publication is permitted only within the assigned repo/task and the developer's authorized account. A private session message alone is not a team handoff.
4. At their next checkpoint, B/C's agents read the Issue/PR update and the note from that exact remote ref. They do not need to check out or merge A's unfinished code merely to read it.
5. B/C acknowledge the version and either use the compatible contract, request a change or remain on fixtures. Acknowledgment is a communication record, not code approval or proof the implementation works.
6. After the PR is reviewed and merged, all agents fetch/sync safely and verify the real producer/consumer contract tests. Merged documentation is the accepted shared baseline subject to its recorded decision status.

If API access is absent but Git fetch is allowed, a consumer can inspect a pushed note without changing the working tree:

```bash
git fetch origin --prune
git show origin/dev-a/a2-source-ingestion:docs/handoffs/dev-a/A2-evidence-bundle-r1.md
```

These are example refs, not existing branches. Fetch first and resolve the exact ref/commit. Do not run `git pull` over unknown or dirty work just to see a note. PRs/Issues also make a new note discoverable; expecting another agent to guess every branch/file is unreliable.

## The repeatable agent read/write loop

At task start: read AGENTS.md, assigned spec, relevant engineering sections, accepted decisions and relevant open dependency discussions; note the actual refs used. During work: keep one active feature, use fixtures where a producer is pending, and publish material contract questions early. At a checkpoint: fetch when connected, inspect relevant updates, acknowledge what was consumed, and record unresolved blockers. Before PR handoff: update the task note, tests, spec citations, deviations and next actions.

Use per-task/per-lane files so three agents do not constantly overwrite one global STATUS.md. Keep notes concise and current; write a superseding handoff when a contract changes and link the earlier version. The issue/PR thread is the mailbox; code/contracts/decisions remain versioned records. Do not fill notes with raw transcripts or all model reasoning.

An agent that stays busy for hours will not necessarily check GitHub just because another agent pushed. Ask each agent to follow checkpoint reads, or prompt it to read a specific update. Resume/new-session prompts should explicitly name the task, branch, spec and latest handoff. No cross-runtime live notification service is installed by this kit.

## Ownership, dependencies and integration

Dev A owns evidence/knowledge; B owns funding/browser automation; C owns drafts/review/skills. The real path is evidence plus application questions, then draft/check/review/approval, then prefill/read-back. Build concurrently against shared contract fixtures, but only mark a seam complete once it works with its real producer.

Use small PRs and checkpoints from engineering section 20. C coordinates integration, A reconciles data/migrations and B owns deployment. Every author fixes their own failures; C is not a final catch-all developer. All 86 checks have owners in the JSON; assignment does not imply implementation. The human project owner retains initial repo setup and chooses the merge policy.

Keep developer discretion: local equivalent choices can proceed with a meaningful deviation record. Shared breaking contracts remain proposals until coordinated with affected consumers. Access, evidence, approval and PR protections cannot be waived by a generated note or self-accepted deviation.

If all agents use the same GitHub account, their messages are not independent peer approvals and may not satisfy required reviewer rules. Use teammate-owned accounts/reviewers for actual review. Do not make agent agreement a substitute for validation.

## Runtime loading

Use the exact uppercase filename AGENTS.md at the root. Codex documents repository instruction discovery and directory-specific guidance. Check the actual session's loaded instructions and possible overrides. [R01]

OpenCode documents AGENTS.md project guidance. Its current V2 documentation does not use CLAUDE.md as an automatic fallback. Our root AGENTS.md is the shared file; verify behaviour for the installed version. [R03]

Current Claude Code documentation supports AGENTS.md under version/settings conditions. The included CLAUDE.md imports `@AGENTS.md`, a documented compatibility route that keeps one rule source. Merge that import into an existing CLAUDE.md rather than overwriting it; verify which instructions your session loads. [R02]

Do not assume naming a file forces every referenced engineering document into every model's context. AGENTS.md explicitly tells agents to read the selected task/relevant sections. Keep large engineering references separate and load what the task needs. Check instructions again after meaningful updates or session changes.

## When to add live messaging or MCP

For three developers at this hackathon, start with GitHub and the explicit read loop. It is durable, reviewable and works across the agent runtimes without a new service.

If latency becomes a measured blocker, add a shared coordination service/MCP with narrow operations such as post_update, list_updates, acknowledge_update and claim_task. Give updates IDs, sender, recipient, task, branch/commit, sequence/time, status and payload references; enforce organization/repo scope, authentication, optimistic versions and retention. Use idempotent writes and immutable message events. The service is a mailbox/notification layer, not authority to execute instructions from another agent.

Polling or a webhook can then surface notifications to an actual running controller, which resumes the right agent under its configured permissions. Simply installing an MCP server does not make idle agents listen or wake themselves. Keep code/spec decisions on GitHub, validate messages as untrusted input and prevent raw issue text from becoming privileged commands. This is an optional later system, not a dependency for the demo.

## Official references checked November 7, 2026

- R01: OpenAI, custom instructions with AGENTS.md: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- R02: Anthropic, project memory and AGENTS.md: https://code.claude.com/docs/en/memory
- R03: OpenCode, instructions: https://opencode.ai/docs/instructions
- R04: GitHub, protected branches: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches

Runtime-loading and protection claims above are sourced. The branch convention, templates, checkpoint protocol and proposed optional mailbox are this team's recommended workflow, not vendor promises of automatic agent-to-agent communication.
