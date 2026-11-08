# Dev B first parallel increment: launch and shared agreement

**Revision:** 1.0  
**Tasks:** B1-DISC-001 and B2-AUTO-001.  
**Reported foundation:** local main commit ad5b8dd, subject to verification in the actual checkout.  
**Authority:** User requested the next two specs after reporting successful INIT-001. This document and the two task specs authorize feature implementation within their bounds, not remote publication to an unspecified repository.

## 1. Foundation facts and limits

The owner relayed a setup-agent report: FastAPI and Pydantic contracts, React/TypeScript/Vite, generated TS types, registered lane routers/pages, working PostgreSQL/migrations, a local demo identity rejected in production, and passing check/smoke/browser-smoke commands. All 86 catalog checks remain planned. No feature implementation, remote, partner source documents or scanners were reported.

Some pasted lines are truncated. The spec author has not inspected this source checkout or independently rerun its tests. Each executing agent must read docs/handoffs/setup/INIT-001-setup-report.md, docs/decisions/0002-dev-b-and-bootstrap.md and docs/decisions/0003-init-001-stack-and-layout.md and inspect actual code before choosing filenames/imports/commands. The garbled absolute machine-note path is not a usable authoritative reference; use the complete relative report in the repo.

Preserve the recorded setup choices: oxlint rather than replacing it with ESLint; the actual TypeScript/Vite versions and lockfiles; PostgreSQL 17 on the actual configured non-default host port; existing navigation without introducing a new routing package; and Playwright in the root Python dependency group. Do not repair a working setup simply to match an earlier proposal. Do not touch the unrelated service reported on port 7000.

Resolve ad5b8dd to its full commit. Use that accepted commit or an explicitly accepted descendant containing documentation updates as the common base. If the local tree differs materially, record the actual base and adapt compatible details; do not reset work to force a match. Missing evidence of a previously passing command means rerun/inspect, not claim verification.

## 2. Two sessions and ownership

Run B1 and B2 in separate clones/worktrees. Example commands, executed by the owner from the real repo after checking paths/branches do not already exist:

```bash
git status --short
git rev-parse --verify 'ad5b8dd^{commit}'
git worktree add -b dev-b/b1-disc-001 ../strongstart-b1 ad5b8dd
git worktree add -b dev-b/b2-auto-001 ../strongstart-b2 ad5b8dd
```

Do not execute these against an unrelated checkout or delete existing directories to make them succeed. These commands create local branches, not PRs or a remote. Use the full accepted base instead if it has advanced. If the specs were only copied as untracked files into the original checkout, the worktrees will not contain them: copy each task spec and this agreement into its worktree, or give the agent their actual external paths. Each agent commits only its own task spec; B1 owns adding this shared agreement if it is not already tracked.

| Resource | B1 owner | B2 owner |
| --- | --- | --- |
| Product code/UI | Existing funding lane | Existing automation lane |
| New contracts | Funding/search/capture module | Intake/question/form-map module |
| Tests and fixtures | funding/discovery/capture namespaces | automation/intake/form namespaces |
| New configuration/dependencies | Coordinates common config, env examples and lockfile updates | Uses installed packages first; sends a bounded change request if new dependencies are essential |
| Common schema exports/generated TS | Owns first shared update | Regenerates on its branch, then regenerates again after rebasing on the integrated B1 update |
| Database migrations | None required in these initial slices; coordinate any necessary proposal with A | None; read-only intake/inspection returns a versioned result and JSON export |

Existing core DTOs/protocols and router registration stay intact. Inspect installed packages before adding dependencies; use existing HTTP and parser facilities where sufficient. Import feature contracts from their modules rather than both rewriting a shared export file. Generated-code conflicts are resolved by regeneration from combined canonical schemas, not manual line editing. Keep global catalog/engineering files unchanged; record feature check evidence separately.

## 3. Shared capture-to-intake seam

B1 produces an authorized captured-document record; B2 consumes the same record through a small port/adapter. Preserve existing SourceReference and CaptureStore signatures. If more metadata is needed, put a compatible wrapper in B1's owned contract module rather than changing shared methods without coordination.

The semantic v1 record includes: schema version; capture/source-version ID; organization scope supplied by server; opportunity/stream/cycle IDs where known; original/requested/final URL with unknowns explicit; provider/capture time; artifacts with representation type, media type, size and SHA-256; extraction coverage/warnings; provenance; authority-review status; and a means to retrieve supported content through authorized application code. No API keys, raw local filesystem paths or browser sessions are handed to B2.

Artifact types distinguish provider-returned markdown/HTML from original HTTP/file bytes. A hash covers the exact stored representation, not an imagined original. A vendor-rendered capture is not automatically a fully preserved original document. Do not fabricate PDF page locators for HTML or a provider summary.

B2 must accept a captured HTML record and preserve its source/version/hash/locator lineage. Markdown may be shown as read-only context; unconstrained question extraction from prose/markdown/PDF is not a required first-slice feature. No consumer silently refetches a URL when saved bytes are available. An absent live CaptureStore adapter keeps the relevant integration fixture-only/unavailable; it does not justify a fake successful lookup.

B2 starts from a fixture implementing this seam while B1 works. B1 publishes an actual example and contract mapping early. An integration test then sends B1's serialized record and saved HTML through B2's real importer. The two feature specs refer to this semantic contract, not invented constructor arguments that may differ from the actual repo.

## 4. Execution and safety defaults

The API auth dependency must run before provider calls, file access or browser launch. Preserve baseline 401 responses without identity, and production rejection of local demo identity. Demo mode stays conspicuous; no new identity header or approved=true bypass.

B1 public capture rejects private/local destinations. B2's registered local representative fixture is a separate capability: allow only its server-controlled origin/path, not arbitrary localhost URLs supplied by a client. Never solve the distinction by globally enabling private-network access. Browser request routing is only one layer; these tasks do not establish production isolation for arbitrary hostile websites.

Use bounded request-based operations for this first slice if the real JobStore/worker is still unavailable. Record this as a scoped implementation deviation from engineering section 14's long-running job architecture; return actual completion/failure rather than fake queued jobs. Search and capture are separate operations, and browser inspection is limited to the local fixture. No scheduled/repeated work, background side effects after a timeout, or process-local job map advertised as durable. A later task supplies real persisted coordination.

Use per-worktree temporary artifact paths and distinct configured/ephemeral ports in tests. Do not stop another agent's API, overwrite a shared demo data directory, reset the shared database, or change global environment variables. Current DB readiness and startup commands remain intact.

## 5. Integration and review

Each agent creates a small local commit series and a handoff containing actual paths, full base/head commits, contract example, tests, limitations and next action. No remote exists in the reported setup: do not invent one, claim a PR was opened or push to an unspecified repo. If the owner later supplies an authorized remote, publish task branches/PRs following AGENTS.md. Until then, inspect the sibling local branch/ref with git show or exchange the exact handoff; private session text is not a durable shared record.

Suggested merge order: B1's capture contract and implementation first, then B2 rebase/update against that accepted change and regenerate types. B2 can build and test almost all its slice before this happens. Do not merge to main merely because this order is suggested; follow the owner's authorized review/merge policy. A separate integration worktree/branch may compare both changes without changing main.

G1 is complete only when both screens work with their actual services, B1 saved HTML is parsed by B2, source lineage survives, auth/failure cases work, and combined check/smoke/browser tests pass. Live-provider verification is a separate reported status; missing credentials are not a reason to invent a live result. Planned and future rules remain planned.
