# A3-VAL-003: deterministic validation specification handoff

- Author/lane: Dev A
- Intended consumers: project owner, Dev B, Dev C and future A4 work
- UTC timestamp: 2026-11-08
- Status: ready-for-review
- Task spec path/revision: `docs/specs/A3-VAL-003_Deterministic_Validation_Runner.md` rev 1.0
- Engineering version/sections and rule IDs: v1.1 sections 4, 5, 8.2, 9, 10.1-10.2, 13.2, 14-15, 19-21 and 23.2; SRC-01-10, NUM-01-12; SEC-01/02/04/13 boundaries
- Branch and exact implementation commit: `dev-a/a3-val-003-spec`; this handoff ships in the documentation commit, whose exact SHA is attached to the PR
- PR / Issue links, or not published: [PR #11](https://github.com/thegeekyqazi/Start_Strong_Agent/pull/11)
- Supersedes / superseded by: none

## What works

This increment defines the A3 implementation contract; it does not claim runtime implementation. It adds the accepted repository-native architecture, exact rule mapping, result/dependency/receipt semantics, A3a/A3b/A3c delivery checkpoints and required deterministic/security/integration tests.

The deep-research report is retained under `docs/research/` with a repository-specific audit. The report is advisory and its embedded citation markers are not usable source references.

## Contract and dependencies

- Use existing `StableId`, Pydantic, PostgreSQL/Tiger Data, SQLAlchemy/Alembic and Decimal conventions.
- Extend the shared `ValidationResult` compatibly; do not replace it without coordination.
- Use `pack_version_id + fact_id` until an additive fact version is coordinated with Dev C.
- Persist immutable minimal receipts and forward dependency records for A4.
- Preserve C ownership of APP/POL semantics and verify parity before moving C2 onto the shared runner seam.
- External rule engines are deferred by accepted decision `A3-VAL-003-repository-native-validation-kernel.md`.

## Validation

Documentation-only checks to be recorded on the final commit/PR. Runtime tests are not applicable to this increment and no A3 rule is marked implemented.

## Decisions and deviations

- Accepted decision: `docs/decisions/A3-VAL-003-repository-native-validation-kernel.md`.
- No engineering-plan requirement is weakened. The spec adds reason codes, deterministic replay, forbidden-import tests, bounded complexity, ambiguity corpora and a C2 parity gate.

## Consumer action / blockers

- Project owner: review and merge this documentation baseline before A3 implementation branches depend on it.
- Dev C: confirm the shared result/dependency seam and the safe `pack_version_id + fact_id` fallback; acknowledge the additive fact-version path.
- Dev B: review capability reporting and security-boundary fixtures as Dev A's verification owner.
- A3 implementation can begin with A3a after this baseline is merged. A4 must review the forward dependency shape before A3c closes.

## Acknowledgments

None recorded yet. Consumer agreement must be linked from the PR/Issue; this handoff does not claim peer approval.
