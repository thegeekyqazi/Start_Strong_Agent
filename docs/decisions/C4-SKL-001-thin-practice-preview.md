# C4-SKL-001-thin-practice-preview: preview-only practice slice, stacked base and lean verification

- Author/developer: coding agent for the project owner (former A/B/C engineering)
- Date: 2026-11-08
- Status: accepted-maintainer (scope reduction, lean verification); developer-decision (layout below)
- Decided/accepted by and evidence: project owner — C4-SKL-001 r1.0 §1 (thin, owner-authorized
  reduction) and the 2026-11-08 time-budget update (lean verification for this checkpoint)
- Engineering path/version/sections: docs/engineering/StrongStart_Engineering_Plan.md v1.1
  §§4–5, 8.2–8.3, 9, 11, 12.1–12.4, 13.1–13.3, 15–18, 20–21
- Feature spec path/revision: docs/specs/C4-SKL-001_Thin_Practice_Generator_and_Draft_Preview.md r1.0
- PR / Issue: draft PR #23. Opened stacked on PR #20; #20 merged to `main` at `12ac1b4`
  (content-identical to the stacked base `068f5aa`), so #23 was retargeted to `main`.
- Supersedes / superseded by: none

## Original requirement

C4-SKL-001 asks for a source-reviewed practice → strict proposal → deterministic compiler →
scans/model screening → exact-hash review/activation → real C draft preview, with revocation/
source-change invalidation, on the accepted DATA-001 PostgreSQL implementation. §13 lists
`make contracts/check/smoke/browser-smoke` and §11 an acceptance matrix C4-01…30.

## Decisions

1. **Stacked base.** DATA-001 (PR #20, migration head `0009_durable_applications`) is not yet on
   `main`. C4 needs its engine/configuration, so the branch starts from the DATA-001 task head
   `068f5aa`. Integration order: PR #20 first, then this PR (retargeted to `main`). C4 adds
   migration `0010_practice_skills`; no released migration is modified.
2. **Preview-only integration** (spec §1.2, owner-authorized). Practices affect only the Skills
   page draft preview through a narrow Applications public port. Saved answers, approvals,
   exports, B plans/grants and normal drafting are untouched; previews carry
   `working_preview_only=true` and `approval_permitted=false`.
3. **Two finite operators** (`preferred_term`, `protected_name`) compile into the existing C
   `WritingPolicy` records, so the deterministic POL-01/POL-02 engine is reused rather than
   copied. Protected names must be in a server-owned registry for the demo context.
4. **Storage shape.** Feature-owned `skl_scope_state` (one guarded row per organization/context:
   current source version, active release, revision; locked `FOR UPDATE`) plus append-only
   immutable `skl_records` (source, authority, candidate, gates, review, release, revocation,
   preview, audit). State mutation and its audit commit in one transaction. The engine is the
   DATA-001 PostgreSQL C store's engine; no memory fallback (503 when not configured).
5. **Fixture screening.** In local/test fixture mode the explicit fake adapter supplies a labelled
   FIXTURE proposal and FIXTURE screening signal (`is_fixture=true` on every record and in the
   UI). This mirrors existing fixture-mode approvals; production rejects the fake adapter, so
   screening there is unavailable/held unless a live adapter is configured. A fixture signal is
   never described as live model screening.

## Scope adjustment: lean verification for this checkpoint

Per the owner's 2026-11-08 time-budget update, which supersedes the spec's exhaustive test
execution requirements for this checkpoint:

- Run focused tests for changed code, reuse existing tests, and type/build checks at meaningful
  checkpoints. Do not implement every C4-01…30 permutation now; do not rerun full
  `make check/smoke/browser-smoke` after each change.
- Essential verification kept: (1) source → candidate → review/activate → draft-preview path;
  (2) tampered hash or incomplete screening cannot activate; (3) revocation/source change prevents
  later use; (4) missing identity or another organization's IDs cannot bypass access checks;
  plus one focused UI/API walkthrough.
- Broader regression (full suites, race/restart/rollback permutations, Chromium automation,
  live-provider rehearsal) is left for the integrated release check. The handoff records exactly
  what ran and what remains unverified. No runtime safeguard is disabled for the demo.

## Impact and coordination

New public contracts `strongstart_contracts.skills` (generated schema/TS). Applications gains an
optional practice-guidance parameter on the draft service plus a public preview port; when absent,
normal drafting instructions and checks are byte-identical. `StructuredTask.operation` adds
`propose_practice` and `screen_practice`. Sawaab: Skills page uses existing shell components and
tokens only; see docs/handoffs/dev-c/c4-skl-001-ui-contract.md.

## Validation and rollback

Validation: see docs/handoffs/dev-c/c4-skl-001-practice-preview-r1.md. Rollback: revert this PR;
migration 0010 downgrade drops only `skl_*` tables (tested only on disposable databases).
