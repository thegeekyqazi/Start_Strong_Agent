# A3c VAL-003: numeric validation and A4 dependency handoff

- Author/lane: Dev A
- Intended consumers: Dev C (C2 claim bindings), Dev A (A4 pack invalidation)
- UTC timestamp: 2026-11-08
- Status: ready-for-review
- Task spec path/revision: `docs/specs/A3-VAL-003_Deterministic_Validation_Runner.md` revision 1.0
- Engineering version/sections and rule IDs: Engineering Plan v1.1 sections 4, 5, 8.2, 9, 10.1-10.2, 13.2, 14-15, 19-21, 23.2; NUM-01 through NUM-12
- Branch and exact implementation commit: `dev-a/a3c-val-003-numeric`; `63de972`
- PR / Issue links, or not published: not published yet
- Supersedes / superseded by: completes the A3 implementation after `a3ab-val-003-source-validation-r1.md`

## What works

The allow-listed pure numeric registry implements NUM-01 through NUM-12 with `Decimal` arithmetic. It preserves sign, scale and percent syntax; applies only registered metric bounds; binds claims to exact fact versions; checks unit/scope metadata; reconciles budgets; validates ratios; exposes conflicts without choosing a winner; distinguishes change operations; requires explicit disjointness for aggregation; and resolves commitment inputs from organization-scoped PostgreSQL state.

`POST /api/validation/numeric` resolves the fact through an allowed evidence-pack version, evaluates selected rules, and stores an immutable receipt. Missing and cross-organization facts share the same non-disclosing response. No evaluator performs I/O, reads an ambient clock, invokes a model, or executes request-supplied code.

## Contract and dependencies

`Fact` now carries additive `fact_version`, `currency`, `scale`, `program`, and `geography` fields. C2 `ClaimBinding` additively carries `fact_version`; the renderer copies it from the server-resolved fact. C retains APP/POL definitions and ordering, while its registry now runs through A3's generic deterministic adapter. The compatibility test proves the adapter output equals the prior list-comprehension behavior.

Migration `0006_numeric_validation` versions facts, adds their numeric metadata, permits `fact` receipt subjects, and creates organization-scoped `project_numeric_inputs`. A3 numeric receipts emit forward dependencies with these meanings:

- `fact_version`: exact fact identity and integer version; A4 must stale dependants when a newer version replaces it.
- `pack_version`: exact authorization/evidence snapshot; A4 must stale dependants when pack activation changes.
- `rounding_policy`: `decimal-half-up` plus decimal places; changing it invalidates calculated output.
- `formula`: registered formula identity/version (currently ratio v1).
- `project_input`: exact approved or explicitly simulated input version; revocation or replacement invalidates commitments.
- `permission_snapshot`: audit dependency only; it must not be interpreted as durable authorization.

A4 reverse traversal remains out of scope for A3c. It should index `validation_dependencies(kind, ref_id, version)`, locate impacted evaluation IDs, and create a new stale transition rather than mutate these receipts.

## Validation

- `ruff check`: passed for changed Python files.
- `mypy packages/contracts/python/src services/api/src`: passed (75 source files).
- Targeted validation/C2/unit/contract suite: 87 passed, 11 DB-marked tests intentionally deselected in that command.
- PostgreSQL migration `0005 -> 0006`: passed against local Docker PostgreSQL.
- PostgreSQL DB suite, including numeric persistence/replay and cross-organization isolation: 11 passed.
- Hypothesis properties cover exact unscaled decimal parsing and budget summation.

The repository-wide run completed with 427 passed, 24 deselected and 27 failures. One A3 compatibility failure and contract drift were fixed and their focused reruns pass. The remaining failures are pre-existing/unrelated Windows funding-fixture integrity and directory-fsync behavior, plus one environment-sensitive knowledge test caused by setting the DB URL for the combined run; they are not claimed as passing here.

## Decisions and deviations

No external policy/rules engine was added. Metric bounds are a closed server registry; unknown metrics return not-applicable rather than receiving invented bounds. Aggregate requests return needs-review unless disjointness is explicitly declared, and conflicts preserve every comparable value. This follows the accepted A3 spec and catalog rather than weakening uncertain cases to pass.

## Consumer action / blockers

Dev C should consume additive `ClaimBinding.fact_version` and may select NUM rules through the numeric endpoint without changing APP/POL ownership. A4 should consume the dependency semantics above and must keep receipts immutable. Neither consumer should infer overall truth from one passing predicate.

## Acknowledgments

Pending consumer review.
