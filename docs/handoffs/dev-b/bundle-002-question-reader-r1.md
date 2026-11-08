# DEV-B-BUNDLE-002 M1: saved definitions and the public question reader (r1)

- Author/lane: Dev B agent (Claude Code, claude-opus-5-5) for the project owner (Dev B)
- Intended consumers: **Dev C (C2b)**, owner; FYI Dev A
- UTC timestamp: 2026-11-08 (M1 checkpoint)
- Status: ready-for-review (producer side). C2b runtime integration is **pending**.
- Task spec: `docs/specs/DEV-B-BUNDLE-002_Saved_Grant_Workspace_and_Reviewed_Research.md` rev 1.0, s5 (M1), s10, s13. It supersedes B2-AUTO-001A rev 1.0, which had no prior code.
- Engineering: v1.1 s7, s14, s15, s20.3 (public producer interfaces), s20.7 (G1)
- Branch: `dev-b/dev-b-bundle-002`, base `origin/main` `2adcdeb0d8a3059caf0d8734bff054403a5c7ffb`. M1 commit: see the PR's commit list ("feat(automation): saved definitions ... (M1)"). A file cannot contain its own SHA.
- PR: draft PR from `dev-b/dev-b-bundle-002` (link posted on C2 PR #7)
- Answers: `docs/handoffs/dev-c/c2-question-read-port-request.md`

## What works (real persistence, not a dictionary)

- `POST /api/automation/definitions` saves an **immutable version**:
  - it re-runs the existing bounded intake on the exact source and requires the preview's input SHA-256;
  - it stores the exact input bytes in the Dev B local store;
  - it returns 201, or 200 on an identical idempotent replay.
- `GET /api/automation/definitions` (bounded list), `GET /api/automation/definitions/{definition_id}` (current) and `GET /api/automation/question-sets/{question_set_id}` (exact version).
- The Automation page has **Save definition for drafting**, a **Saved definitions** list, reopen with exact evidence, previous-version open, and **Copy question-set ID for Dev C**. It says "Saved; connection to Applications pending".
- The store is a development/test repository under `STRONGSTART_DEV_B_STORE_DIR` (default `.local-data/dev-b-store`). It persists across restarts and is **disabled in production** (503; the reader is unconfigured).

## Public imports (the only supported entry points)

```python
from strongstart_contracts.application_publication import (
    ApplicationDefinitionReader,           # Protocol: is_fixture, get_version, get_current
    ApplicationDefinitionNotFound,         # unknown AND other-org IDs (indistinguishable)
    ApplicationDefinitionIntegrityError,   # stored version failed verification; withhold
    PublishedApplicationVersion,           # the envelope (below)
    UnconfiguredApplicationDefinitionReader,
)
from strongstart_contracts.ports import CapabilityUnavailable   # production / no store
from strongstart_api.features.automation.public import (
    get_application_definition_reader,     # FastAPI dependency (override in tests)
    build_application_definition_reader,   # same, from Settings
)
```

Wiring example: the `public.py` module docstring and `tests/contracts/test_application_definition_reader_contract.py`. That test is a consumer route run against both a fixture double and the real repository.

```python
ReaderDep = Annotated[ApplicationDefinitionReader, Depends(get_application_definition_reader)]

def handler(identity: Identity, reader: ReaderDep, question_set_id: str):
    v = reader.get_version(identity.organization_id, question_set_id)   # server org only
    v.question_set.questions   # shared Question DTOs, published IDs, question_version == v.version
    v.unresolved               # UnresolvedItem keyed by PUBLISHED IDs
    v.intake.questions         # rich intake (exact text, locators, candidate/native limits,
                               #   conditions, attachments) with ORIGINAL IDs; join via v.id_mapping
```

## Envelope `PublishedApplicationVersion` (`b2-published-definition/1`)

| Group | Fields |
| --- | --- |
| Identity | `definition_id` (`def-<26 hex>`, server), `version` (1..20), `question_set_id = qs-<definition_id>-v<version>` (unique per revision), `saved_by`/`saved_at` (server identity/time), `organization_id` (server) |
| Integrity | `integrity.raw_input_sha256/raw_input_size`; `normalized_digest` over the canonical JSON of the content groups (`dev-b-canonical-json-sha256/1`) |
| Content | `question_set` (shared `QuestionSet`), `application_definition` (`form_id=null`; no FormMap is attached), `intake` (original rich result), `id_mapping`, `added_original_ids`, `removed_original_ids`, `unresolved` |
| Context | `context.opportunity_id` and `opportunity_basis`: `fixture_registry`, `source_declared_claim` or (M3) `funding_case`; `declared` (claims); `binding` (M3, exact case version) |
| Provenance | `provenance`, `is_fixture` (record), `mode_label`, parser/normalization metadata in `intake.input`, coverage in `intake.coverage` |
| Workflow | always `review_status=saved_not_reviewed`, `approval_status=not_approved`, `prefill_permitted=false` |

### Version behaviour

- Published question IDs are `<definition_id>:<original_id>`, so identical `rp-*` IDs in different lineages never collide. They stay stable within a lineage.
- `question_version` equals the definition version. **Every** question advances on a revision, conservatively.
- `get_version(org, qs_id)` returns exactly that immutable version, never a substituted latest. `get_current(org, definition_id)` returns the latest, for C3's later current-version checks.
- A revision needs the explicit lineage plus the expected current version. One of two concurrent writers wins and the other gets 409 (cross-process tested).
- Semantics are unchanged: 350/500 conflicts stay `unresolved` (`limit=None`); "Max 300" keeps unit `unknown`; `required: null` stays `null`; counting conventions stay unknown; stream-specific amounts and file constraints are preserved in `intake`.

### Sample

A sample from the real repository: `tests/fixtures/automation/published-definition-v1.sample.json`. It is a FIXTURE record (`is_fixture=true`, simulated provenance, 9 questions). Its contract is checked by the test above.

## Consumer requirements (C2b)

- Resolve the selected `question_set_id` with the **server** organization. Never accept browser-supplied question or provenance payloads.
- On `ApplicationDefinitionNotFound`/`IntegrityError`/`CapabilityUnavailable`, show the failure. **Do not silently fall back** to `demo-bundle@1`.
- Keep rich intake, conflicts and unknowns visible; do not resolve them on B's behalf.
- B+C G1 is claimed only after C's editor/check/draft path reads this producer. Full G1 also needs A evidence.

## Validation at M1

| Command | Result |
| --- | --- |
| `make check` | exit 0: ruff/format/oxlint/Prettier; mypy strict 131 files; pytest **453 passed**, 19 deselected; Vitest **58 passed**; contracts drift clean; build |
| `pytest tests/automation/test_saved_definitions.py` | 39 passed: BND-01..16, including the cross-process writers (BND-12), tamper cases (BND-13) and injected mid-commit failure (BND-14) |
| `pytest tests/contracts/test_application_definition_reader_contract.py` | 3 passed (fixture double and real producer) |

Baseline before M1 (`2adcdeb`): `make check` exit 0, 407 pytest and 54 Vitest. Not run at M1: `make smoke` and `make browser-smoke` (run at M6).

## Decisions / deviations

`docs/decisions/DEV-B-BUNDLE-002-local-repositories-versions-review.md`: local repository, ID scheme, review semantics and platform durability policy.

## Message for C2 PR #7

> Dev B M1 (DEV-B-BUNDLE-002): the question read port C requested in `c2-question-read-port-request.md` now exists on draft PR <B PR link>. Port `ApplicationDefinitionReader` (`strongstart_contracts.application_publication`) and factory `strongstart_api.features.automation.public.get_application_definition_reader`. Envelope `b2-published-definition/1`. Exact versions via `get_version(org, question_set_id)`; current via `get_current(org, definition_id)`. Semantics are unchanged (conflicts/unknowns stay unresolved). Handoff: `docs/handoffs/dev-b/bundle-002-question-reader-r1.md`. Sample: `tests/fixtures/automation/published-definition-v1.sample.json`. The development-only local repository is disabled in production. Please acknowledge the port name/version when C2b starts consuming it; B+C G1 stays pending until C's editor reads it.

## Acknowledgments

None yet.
