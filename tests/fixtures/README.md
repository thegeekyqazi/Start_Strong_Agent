# Shared fixtures

Everything here is **synthetic**. No partner document, source excerpt, quote or current figure is included. The original partner documents (e.g. the United Way guide referenced as U09) were **not** in the owner's folder at INIT-001. The question limits below come from the engineering plan v1.1 s7 summary, labelled `engineering_derived`. They are **not** a PDF extraction result.

## `demo/demo-bundle-v1.json` (`demo-bundle@1`)

Validated by `strongstart_contracts.FixtureBundle`, which checks types and cross-references (IDs, versions, content hashes, simulation labels).

| ID | Kind | Owner | Purpose |
| --- | --- | --- | --- |
| `demo-org` | organization | A | Synthetic organization (seeded into the DB) |
| `demo-a-v1`, `demo-b-v1` | pack versions | A | Two packs for later replacement tests |
| `demo-evidence-a-v1` / `demo-fact-children-served` | evidence bundle / fact | A | **Dated simulated metric**: value "120", period 2025-09/2026-06, publication date 2026-07-01 (synthetic) |
| `demo-gos` | opportunity | B1 | Synthetic GOS-style opportunity. Deadline unknown |
| `demo-gos-req-v1` / `demo-cond-charity-status` | requirement set / condition | B1 | **Unknown eligibility condition** (`evaluation: unknown`, with missing input) |
| `demo-gos-questions-v1` | question set | B2 | `mission-q1` (50 words), `services-q2` (250 words), `partnership-q3` (**conflicting limit** 350 vs 500 words, unresolved), `pending-q4` (Max 300, **unit unknown**) |
| `demo-gos-app-v1` | application definition | B2 | Links opportunity, question set and form |
| `demo-gos-v1` | form map | B2 | `fixture://demo-gos.local`, fields `mission-field`, `services-field` |
| `demo-answer-mission-v1` | answer snapshot | C | Synthetic text with exact sha256 and dependencies |
| `demo-approval-mission-v1` | approval snapshot | C | Fixture approval record ref. **Not a real approval** |
| `demo-change-fact-v2` | change set | A | **Future stale snapshot case**: fact v1 → v2 must stale `demo-approval-mission-v1` |
| `demo-job-capture-failed` | job result | shared | **Typed failure** (`capability_unavailable`) |

`expectations` records the outcomes later feature tests should assert. These are expected values, not results from any engine.

## `browser/demo-form.html`

A local static representative form for browser readiness only (`#mission` has a preset value, `#pending` has `maxlength=10`). It is not a funder portal and has no submit endpoint.
