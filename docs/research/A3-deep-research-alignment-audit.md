# A3 deep-research alignment audit

**Reviewer/lane:** Dev A

**Date:** 2026-11-08

**Research input:** `docs/research/A3-deep-research-report.md`

**Status:** design guidance; not an accepted feature specification

## Verdict

The report is strongly aligned with Strong Start's architecture. Its central recommendation should be adopted: build a small typed Python validation kernel using the initialized Pydantic/PostgreSQL stack, exact `Decimal` arithmetic, immutable validation receipts, server-derived authorization context and property-based tests. Borrow design patterns from OPA, Cedar and OpenFGA, but do not add those runtimes to A3.

The report is not sufficient by itself as the A3 contract. The researcher could not read this repository, its citation tokens are not usable repository links, and several proposed types do not match current Strong Start contracts. The A3 task specification must supersede those generic portions with the actual engineering plan, check catalog and accepted producer/consumer contracts.

## Binding project sources

Implementation decisions must trace to these sources, in this order:

1. `AGENTS.md` and current maintainer directions.
2. `docs/engineering/StrongStart_Engineering_Plan.md` v1.1, especially sections 4, 8.2, 9, 10.1-10.3, 13.2, 15 and 20.
3. `docs/engineering/StrongStart_Check_Catalog.json` for exact rule semantics, fixtures, ownership and failure behavior.
4. A1/A2 specs, migrations, decisions and handoffs for source/fact/artifact reality.
5. `docs/specs/C2-draft-claims.md` and Dev C's fact-version handoff for the consumer contract.
6. The deep-research report for external patterns and trade-off analysis only.

## Adopt from the report

- A pure-by-default `resolve -> authorize -> evaluate -> persist` flow.
- No hidden database, clock, network or model access inside evaluators.
- Exact rule ID, semantic version, definition hash, evaluator version and frozen evaluation time.
- Complete forward dependency references for A4 to invert later.
- Separate `planned`, `implemented` and `tested` registry states.
- Missing prerequisites produce `needs_review`; `not_applicable` requires a reason.
- Canonical decimal strings and explicit local `decimal.Context`; reject authoritative float ingress, NaN and infinity.
- Explicit rounding, tolerance, unit, currency, period, program, population and scope semantics.
- Immutable historical validation receipts; later changes stale/supersede rather than rewrite them.
- Hypothesis as a development dependency for numeric, serialization, authorization and metamorphic properties.
- Closed, allow-listed evaluator kinds and finite typed parameters; no `eval`, dynamic imports, SQL fragments or model-generated executable rules.
- Server-derived organization and permission context, anti-enumeration behavior and current-state reauthorization at action boundaries.
- Defer OPA, Cedar, OpenFGA and Pint as runtime dependencies.

## Required repository-specific corrections

### Identifiers and contracts

The report's UUID-centric sample is illustrative, not compatible with the repository. Strong Start uses `StableId` strings and existing `ContractModel` configuration. A3 must extend those conventions instead of introducing a parallel UUID identity system.

Do not replace the shared `DependencyRef` in `answers.py` without a coordinated proposal. Define an A3 validation dependency type with an unambiguous name, or add compatible fields through the shared-contract process.

Authoritative A3 request models should be strict and forbid extra fields. Response/receipt contracts should remain frozen. This does not justify globally changing every existing contract to strict mode in A3.

### Planned rules are not findings

A planned rule must never emit an authoritative `ValidationResult`. Registry/coverage APIs may report it as planned or not executable, but the four result outcomes remain reserved for an evaluator that actually ran. Missing prerequisites for an implemented rule produce `needs_review`; missing implementation produces capability/coverage status, not a fabricated finding.

### Actual A3 ownership

A3 owns the common runner, `SRC-01` through `SRC-10`, `NUM-01` through `NUM-12`, and shared primitives for `SEC-01`, `SEC-02`, `SEC-04` and `SEC-13`.

- Dev B still owns `DAT-*`, `ELG-*` and `AUT-*` evaluators.
- Dev C still owns `APP-*`, `POL-*` and `SKL-*` evaluators.
- A3 may execute registered B/C rules without changing their owner metadata or weakening their tests.
- A4, not A3, owns pack activation, reverse dependency traversal and invalidation publication.

`SEC-02` is provider/data-class routing and `SEC-04` is upload/parser containment. They are not all ordinary permission checks. A3 should expose typed server-owned decisions/primitives for these boundaries, while their feature adapters continue to enforce them at the real action boundary.

### Actual source-rule mappings

The repository already defines the rule bodies omitted by the research session:

| Rule | Required A3 predicate |
| --- | --- |
| SRC-01 | Referenced source/version exists in the authorized evidence set. |
| SRC-02 | Original artifact bytes match registered SHA-256 and size. |
| SRC-03 | Referenced page/section/locator exists in that exact version. |
| SRC-04 | Direct quote matches the stored passage under a versioned normalization policy. |
| SRC-05 | Capture/extraction succeeded and required content is nonempty. |
| SRC-06 | Detect identical hashes/repeated origins while preserving distinct capture metadata. |
| SRC-07 | Detect source-version changes and emit affected dependency information. |
| SRC-08 | Required extraction metadata and resolvable original-artifact reference exist. |
| SRC-09 | Page/extraction coverage is known and processed range is valid. |
| SRC-10 | Parser/OCR version, warnings and capture time are complete. |

A2 supplies real data for most of these predicates. A3 must turn that data into versioned findings without claiming OCR or authenticity verification.

### Actual numeric-rule mappings

| Rule | Required A3 predicate |
| --- | --- |
| NUM-01 | Parse sign, decimal, scale and percent markers without loss; ambiguity remains review. |
| NUM-02 | Apply metric-specific typed bounds without inventing bounds for unknown metrics. |
| NUM-03 | Bound claim value matches the verified fact/derivation under declared rounding. |
| NUM-04 | Unit, scale and currency match or have an explicit conversion record. |
| NUM-05 | Period, program, geography, population and scope match. |
| NUM-06 | Budget line items/subtotals/totals reconcile using exact decimal arithmetic. |
| NUM-07 | Registered ratio has an intended, approved, nonzero denominator. |
| NUM-08 | Expected metric ID distinguishes enrollment, completion, assessed participants and responses. |
| NUM-09 | Comparable fact keys with unequal values remain visible as conflicts. |
| NUM-10 | Percentage-point difference and relative percent change are distinct operations. |
| NUM-11 | Aggregation requires compatible units/periods and explicitly disjoint scopes. |
| NUM-12 | Future targets/requested costs require approved or explicitly simulated project inputs. |

Do not add weighted totals, exchange-rate discovery or broad unit conversion merely because the research toolbox mentioned them. Add only evaluators required by catalog rules and accepted fixtures.

### Fact versions

Address Dev C's request with an additive Strong Start-compatible fact version (`fact_version` or stable version ID) and database constraint for new real facts. Until all producers migrate, `pack_version_id + fact_id` remains the safe coarse binding. A3 records the exact binding; A4 later invalidates dependents.

### Persistence and replay

Persist validation reports, results and forward dependencies, but avoid a large speculative schema before one complete vertical rule path works. Build an internal replay service first; expose a replay API only when its authorization and sensitive-data behavior have an explicit consumer and tests.

Do not store raw private evidence redundantly in canonical receipt JSON. Store typed observed/expected values and authorized references, with sensitive-field exclusions. A dependency on the entire lockfile is excessive per result; bind runner build/version and relevant parser/rule/registry versions, while CI preserves the lockfile.

### Dependency choices

- Adopt Hypothesis as a dev/test dependency.
- Use Pydantic's generated JSON Schema and strict models before adding `python-jsonschema`; add it only if finite external rule manifests require features Pydantic cannot enforce cleanly.
- Defer Babel until an accepted rule/fixture requires locale-specific parsing. NUM-01 must still preserve ambiguity and explicit locale metadata.
- Use a small reviewed unit/currency vocabulary for A3. Do not add Pint in the first implementation.

## Improved implementation sequence

The report front-loads contracts, persistence, replay and permissions. A safer repository-native sequence is vertical and reviewable:

### A3a: runner and one real vertical rule

- Feature spec and decision record.
- Additive validation contracts and registry states.
- Canonical hashing and exact decimal primitives.
- Server-derived minimal permission/context snapshot.
- Pure runner with no network/model/database access inside evaluators.
- Implement `SRC-01` end-to-end against A2, persist its receipt and expose an authorized read path.
- Add Hypothesis and registry invariant tests.

Gate: one real source rule travels from authorized PostgreSQL evidence through the runner to a persisted, reproducible finding. Planned rules cannot execute.

### A3b: complete source validation and shared boundary primitives

- Implement/test `SRC-02` through `SRC-10` in catalog-sized commits.
- Add source/fact version and coverage dependencies.
- Complete authorization, routing, parser-boundary and access-aware-cache primitives for `SEC-01/02/04/13`.
- Add current-main A2 and C2 producer/consumer tests.

Gate: every SRC rule has positive, negative, boundary, missing-prerequisite, cross-org and tamper/replay coverage; no claim that document authenticity or OCR correctness was proved.

### A3c: numeric validation and C2 integration

- Implement/test `NUM-01` through `NUM-12` with exact decimal and typed scope semantics.
- Add C2 registry adapter without moving APP/POL ownership.
- Compare C2 legacy outputs with shared-runner outputs before switching the consumer.
- Export complete forward dependencies for A4.
- Add property, metamorphic, load and denial-of-service boundary tests.

Gate: C2 can consume real A2 evidence and A3 findings without changing drafting logic, every numeric rule is catalog-linked and tested, and A4 can consume dependency edges without A3 performing invalidation.

## Additional safeguards to add beyond the report

1. **Reason-code catalog:** stable machine reason codes separate from human messages, with ownership and version tests.
2. **Finding aggregation policy:** reports retain every finding; an action-specific gate computes blockers without turning mixed results into a misleading universal pass.
3. **Rule determinism harness:** execute each evaluator twice with a deep-copied context and assert identical canonical output; reject mutation of inputs.
4. **Forbidden-import test:** validation evaluator modules may not import HTTP/model/browser clients or repository/session objects.
5. **Complexity budgets:** per-rule maximum facts/passages/line items/digits/exponent and deterministic failure status.
6. **Quote-normalization corpus:** Unicode whitespace, NBSP, line wrapping, punctuation and changed-digit cases for SRC-04.
7. **Numeric ambiguity corpus:** parentheses, signs, percentages, localized separators, scale words, currency placement and Unicode minus characters.
8. **Consumer parity gate:** C2 APP/POL tests remain unchanged and pass both before and after shared-runner integration.
9. **Honest capability reporting:** API/UI report rule coverage by exact state and version; never display "A3 passed" or "all checks passed" when only a subset ran.
10. **Migration rollback safety:** no downgrade may silently delete validation receipts or fact versions; refuse downgrade or require an explicit verified export/migration path.

## Decision recommendation

Accept the report as the A3 research baseline with the corrections above. The task spec should adopt its deterministic kernel, immutable receipt, exact dependency, permission snapshot, Decimal and Hypothesis recommendations. It should reject its UUID examples, generic planned-rule tables, broad evaluator toolbox and premature dependency/service additions where they conflict with the initialized repository or actual catalog.

Before implementation, publish `docs/specs/A3-VAL-003_Deterministic_Validation_Runner.md` revision 1.0 and obtain acknowledgment from Dev C for the shared `ValidationResult`/fact-version changes. Dev B should review the registry extension seam and shared security primitives. Implementation should start only from the updated main branch after A2b/A2c integration is settled.
