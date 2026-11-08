# C1-shell-and-adapter: Synchronous draft route, C-local fixture workspace, REST Gemini adapter, production fake guard

- Author/developer: Dev C agent (Claude Code, claude-opus-5-5)
- Date: 2026-11-07
- Status: developer-decision (D1-D4). The shared-file edits listed under Impact were approved by the project owner ("go", 2026-11-07) for `config.py`, `.env.example` and `export.py`. The `tests/unit/test_api.py` C-line update and the shell CSS scoping are flagged for consumer acknowledgment
- Decided/accepted by and evidence: Dev C agent within C1 spec discretion. The project owner approved the C1 proposal and its three shared-file edits in this session. Not yet reviewed in a PR
- Engineering path/version/sections: `docs/engineering/StrongStart_Engineering_Plan.md` v1.1, s14.1, s15, s17, s20.3, s23.1
- Feature spec path/revision: `docs/specs/C1-shell-and-adapter.md` rev 1.1 (s6, s10, s11)
- PR / Issue: not published (see handoff `docs/handoffs/dev-c/c1-shell-and-adapter.md`)
- Supersedes / superseded by: none

## Original requirements

- s14.1: `POST /answers/{id}/draft` returns a "Draft job; typed proposal only", and long operations return 202 plus a job ID.
- s20.3: consumers start from a reviewed fixture and replace it with the real producer at a named gate. Port fixtures belong in shared `fixture_adapters.py`.
- s17: one real adapter plus a deterministic fixture adapter. An unsupported function returns an explicit capability error, never a silent switch.
- s23.1: "Use Gemini first"; still "confirm actual model IDs/endpoints".

## Decisions

1. **D1: synchronous draft route.**
   - `POST /api/applications/questions/{question_id}/draft` returns 200 with a validated `DraftProposal`, or a typed error.
   - It has a hard deadline (`STRONGSTART_MODEL_TIMEOUT_SECONDS`), one adapter call and no retries.
   - `JobStore` is `UnconfiguredJobStore`, so a 202 with a process-local job map would falsely advertise durability. This follows the same reasoning as B1's recorded deviation.
   - `POST /api/applications/draft-jobs` stays an explicit 501.
   - *Tradeoff:* a slow model holds the request for up to the timeout (20 s default).
   - *Replacement:* C2/C3 move drafting to jobs once A/C provide a JobStore.
2. **D2: C-local fixture workspace source.**
   - `features/applications/workspace.py` reads the shared `demo-bundle@1` through `load_fixture_bundle`. It runs only in fixture mode and is org-scoped to the server identity.
   - It does not add a `FixtureEvidenceProvider` or a QuestionSet port to the shared `fixture_adapters.py`/`ports.py`.
   - *Why:* those are shared files, and C2 replaces this source with the real producers (B2 `AutomationHandoffExport`, A `GET /api/knowledge/evidence/{pack_version_id}`) at G1.
   - *Alternative:* promote it to `fixture_adapters.py` as a proposed-cross-module change, if A/B want it.
3. **D3: Gemini over REST with httpx.**
   - It uses `generateContent` through the existing `httpx` runtime dependency. There is no Google SDK and no new dependency or lockfile change.
   - The key goes in the `x-goog-api-key` header only.
   - The model name must be configured (`STRONGSTART_GEMINI_MODEL`). No model ID is assumed (s23.1).
   - Permitted data classes are `simulated`, `engineering_derived` and `public`. `supplied` partner data is denied before any network call until the owner approves that routing (AGENTS.md: "do not route private data to an unapproved backend").
   - **Live behaviour has not been verified** (no key used).
4. **D4: the production fake guard lives at adapter selection, not in `Settings`.**
   - Rev 1.0 said `fake` is rejected in production. Validating that in `Settings` broke the B1/B2 tests that construct `Settings(environment="production")` with defaults.
   - Instead, `get_model_adapter` returns an adapter that raises `CapabilityUnavailable` in production, and `applications.model` reports `unavailable`.
   - Production still cannot serve a fake draft, and other lanes' settings still load.

## Impact and coordination

Shared files touched:

| File | Owner | Change | Approval / acknowledgment |
| --- | --- | --- | --- |
| `services/api/src/strongstart_api/config.py` | shared host | Additive `model_provider`, `gemini_model` (empty means unset) and `model_timeout_seconds` | owner "go" |
| `.env.example` | B1 (infra) | Additive names `STRONGSTART_MODEL_PROVIDER`, `STRONGSTART_GEMINI_MODEL`, `STRONGSTART_MODEL_TIMEOUT_SECONDS` (empty or default values) | owner "go"; B1 please acknowledge |
| `packages/contracts/.../export.py` | shared | `*ANSWERS_PUBLIC_MODELS` appended, using B2's pattern | owner "go" |
| generated schema/TS | generated | `make contracts` | n/a |
| `tests/unit/test_api.py` | each owner extends | The C line now expects `applications: unavailable` and `applications.model: fixture_only` by default. No other lane's assertion changed | A/B please acknowledge |
| `apps/web/src/index.css` | C (shell) | Shell nav rules scoped to `.shell > nav`, so feature pages can use `nav` | C-owned; B1/B2 browser e2e pass unchanged (13 passed) |

- **Consumers:**
  - A and B can reuse `EvidenceCard`, `FindingRow`, `StatusDot` and `HashChip` from `apps/web/src/shell/components`.
  - The shared `ErrorCode` enum is unchanged. Model failures use `details.reason`, following B1's precedent.
- **Checks:** this is SEC-05/06/07/14 boundary coverage only. Catalog statuses remain `planned`.

## Validation and rollback

- **Validation:** `make check`, `make smoke` and `make browser-smoke` all exit 0 (see the handoff for counts), and `tests/applications/*` has 55 tests.
- **Rollback:**
  - Revert the C1 commits. All shared edits are additive.
  - Without the `config.py` fields, `get_model_adapter` cannot select Gemini, so the router change must be reverted with them.
- **Reversals:**
  - D1 is reversed by C2/C3 adopting a JobStore.
  - D2 is reversed by the real producers at G1.
  - D4 can move back into `Settings` once every lane's production tests set `model_provider` explicitly. That needs agreement across lanes.
