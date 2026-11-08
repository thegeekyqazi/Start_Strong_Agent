# UI-001: Adopt a shared Hallmark visual system and guided grant journey

- Author/developer: Dev A / Codex
- Date: 2026-11-08
- Status: accepted-maintainer
- Decided/accepted by and evidence: Project owner explicitly requested a Hallmark full-project UI/UX redesign, a blue accent, a landing page and guided workflow in this task thread.
- Engineering path/version/sections: `docs/engineering/StrongStart_Engineering_Plan.md` v1.1, sections 2, 20.1 and 20.3
- Feature spec path/revision: No dedicated UI task spec exists; the maintainer's UI-only prompts are the task contract.
- PR / Issue: pending publication
- Supersedes / superseded by: none

## Original requirement

Redesign the existing frontend across all pages while preserving features, routes, integrations, data flows, authentication rules and business logic. The maintainer later requested a simple explanatory landing page, a blue secondary/accent system and stronger navigation through the grant workflow.

## Decision / deviation and reason

Use a shared Furrow-derived token system with a trust-blue accent, a dark operational workflow surface and one responsive shell. Add a root landing route and reorder the presentation of existing routes into the real working sequence: Find Funding, Intake & Prefill, Knowledge, Applications and Review. Skills remains reachable but is labelled `Coming later` and excluded from the active journey.

This is a cross-lane presentation change because the shared shell is owned by Dev C and route content includes Dev B surfaces. No public TypeScript/Python contract, API, backend behavior, database schema, authentication rule or feature capability is changed.

## Impact and coordination

Dev B and Dev C should review presentation and accessible labels for their existing routes. Existing route IDs, feature registrations, forms, links, handlers, provenance labels and test hooks remain compatible. The root hash now presents the landing page; each established `#/<feature>` route is unchanged.

## Validation and rollback

Validated with TypeScript, oxlint, the complete 89-test web suite, real API/database-backed browser captures at desktop and phone sizes, and Hallmark render checks with zero blocking findings. Rollback is the UI commit; no data or migration rollback is required.
