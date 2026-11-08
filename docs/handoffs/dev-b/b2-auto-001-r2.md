# B2-AUTO-001 r2: rebased on merged B1 and joined the B1-B2 capture seam (G1)

- Author/lane: Dev B2 agent (Claude Code, claude-opus-5-5) for the project owner (Dev B)
- Intended consumers: owner (review), B1 (seam acknowledgement), C (handoff consumer), A (store replacement)
- UTC timestamp: 2026-11-08T04:30Z
- Status: ready-for-review (draft PR)
- Task spec: `docs/specs/B2-AUTO-001_Application_Intake_and_Form_Inspection.md` rev 1.0; agreement `docs/coordination/b1-b2-parallel-launch.md` rev 1.0
- Base: `origin/main` = `8df9df89620955f79945f461169c2fc97913fa96` (merge of B1 PR #1). Previous base `ad5b8dd`. The pre-rebase branch is kept locally as `backup/b2-auto-001-pre-rebase`.
- Branch: `dev-b/b2-auto-001`; head = the commit containing this note (`git log -1`)
- Supersedes: extends `b2-auto-001-r1.md`, which remains valid except where noted here

## Rebase and shared files

- `export.py`: kept B1's explicit `discovery` model list **and** B2's `*AUTOMATION_INTAKE_PUBLIC_MODELS`. The combined schema has 84 `$defs` with no name collisions.
- `strongstart-contracts.schema.json` / `generated.ts`: **regenerated** with `make contracts` using B1's fixed generator, not hand-merged. `make contracts-check` passes.
- `tests/unit/test_api.py`: both lanes removed themselves from the "not implemented" loop. The merge keeps B1's funding `unavailable` assertions and B2's automation `fixture_only`/prefill/submission assertions.

## G1 seam (B1 consumer, schema "1", commit `1c58ad96796d4d6ec11fdfda73343f8c18837bf1`)

Acknowledged: B2 now consumes B1's `CapturedDocument` (schema "1") via `CapturedDocumentReader` (`LocalCaptureStore`).

- `features/automation/capture.py` maps `CapturedDocument` → B2 `capture-record/1` field for field (`record_from_captured_document`) and wraps the reader (`B1CaptureSource`):
  - `final_url_status` keeps B1's `provider_reported`;
  - every artifact's ID, representation and sha256 is preserved;
  - `source_reference.{source_id, source_version_id, content_hash}` is preserved (the content hash as `producer_source_reference_hash`);
  - `supported_import_representations` is enforced; markdown is read-only context;
  - B1 `CaptureIntegrityError` → B2 `hash_mismatch` (409); not-found and other-org → the same 404.
- Wiring (`router.get_capture_source`): B1's store from `funding.deps.get_capture_store` (development-only; `None` in production) is tried first, then the labelled B2 fixture producer in fixture mode only. With neither available, capture intake fails closed (503).
- A seam test found a gap, now fixed: B1's page states limits in the label text ("... (50 words)"). The normalizer now records limits stated in question wording, with that wording as exact evidence.
- UI: capture mode accepts a pasted `capture_id:artifact_id` reference from Find Funding (B1's reader has no listing).

## Validation (2026-11-07, this worktree)

| Command / test | Result |
| --- | --- |
| `make check` | exit 0: ruff/format/oxlint/Prettier clean; mypy 84 files clean; pytest **261 passed**, 15 deselected; vitest **24 passed**; contracts-check; build |
| `make smoke` | exit 0 (live 200, ready 200 at `0001_bootstrap`, 15 capabilities) |
| `make browser-smoke` (now builds web first) | exit 0, **13 passed** (B1 funding e2e + INIT smoke + 10 B2 inspector/seam tests) |
| `tests/automation/test_b1_integration.py` (7) | B1's committed sample `sample-capture-v1`, loaded via `LocalCaptureStore.save` and imported through the **unmodified** B2 router wiring with 0 network attempts. Results: capture_id, source_id, source_version_id, artifact sha256, provider-reported final URL, B1 provenance (simulated) and authority claim all survive into the result and every question `source_ref`. Raw HTML: script/tracker inert; hidden page text is not a question. Markdown: context only. A one-byte change to the stored blob → 409. Other-org gives the same 404 as unknown. Production → 503. A **fresh capture from B1's API** (fixture provider) imports with matching hash/IDs |
| Manual UI | Real API + Vite on ephemeral ports. B1 capture via `POST /api/funding/captures`, reference pasted into Automation, imported. Label shows `b1-capture-store; FIXTURE/SIMULATED`, sha256/capture ID shown, 2 questions, no script execution, 0 page errors |

Not run: live Tavily/Firecrawl capture (no credentials; B1's live status remains NOT RUN); GitHub CI result at handoff time (see PR checks).

## Remaining blockers / next actions

- **B1:** acknowledge this consumer mapping, or flag a field B2 should read differently. The `opportunity_id/stream_id/cycle_id` in B1 records are null until B1-DISC-002 staff review creates `Opportunity` records, so the shared `QuestionSet` projection is omitted (by design, nothing invented).
- **A:** a supported production artifact store implementing `CapturedDocumentReader` semantics. Until then capture intake is development-only. Consider the org-aware `CaptureStore` proposal B1 raised.
- **C:** consume `AutomationHandoffExport`; provide the real `ApprovedAnswerResolver` for B2-AUTO-002.
- **Owner:** review the draft PR. Merging follows your policy; the B1/B2 agents share your GitHub identity, so they are not independent reviewers.

## Acknowledgments

None yet.
