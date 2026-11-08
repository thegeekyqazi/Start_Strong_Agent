# A3-VAL-003: Deterministic source and numeric validation runner

**Revision:** 1.0

**Owner:** Dev A

**Status:** accepted implementation baseline

**Branch:** `dev-a/a3-val-003-spec` for this documentation increment; implementation uses short-lived A3 task branches

**Engineering baseline:** Strong Start Engineering Plan v1.1 sections 4, 5, 8.2, 9, 10.1-10.2, 13.2, 14-15, 19-21 and 23.2 (`ENG-004`)

**Catalog rules:** SRC-01 through SRC-10 and NUM-01 through NUM-12. Boundary integration: SEC-01, SEC-02, SEC-04 and SEC-13; A3 does not take ownership of other lanes' security rules.

**Research input:** `docs/research/A3-deep-research-report.md`, interpreted by `docs/research/A3-deep-research-alignment-audit.md`

## 1. Goal

Build the repository-native validation kernel that evaluates exact, authorized, versioned inputs and produces reproducible findings for source and numeric claims. A result proves only its named predicate. Missing or ambiguous prerequisites never pass, and no model, network request, hidden database read or ambient clock participates inside an evaluator.

A3 is the forward validation layer. It records the exact dependencies used by a result. A4 will consume those dependencies for reverse lookup, staleness propagation and pack activation/replacement.

## 2. Product outcomes

A3 must let the application answer these questions without inventing certainty:

1. Does a referenced source version exist in the actor's authorized evidence snapshot?
2. Do the original stored bytes still match the registered hash?
3. Does the locator resolve, and does a claimed direct quote match under a versioned normalization rule?
4. Is ingestion/capture metadata complete enough for the rule being evaluated?
5. Was a number parsed without losing sign, scale, decimal or percent meaning?
6. Does a bound claim match its verified fact's value, unit, currency, metric, period, program, geography and population?
7. Are calculations reproducible with exact decimal arithmetic and explicit rounding?
8. When inputs conflict, overlap or remain unknown, does the finding preserve the uncertainty instead of selecting a winner?

The UI/API may use these findings later, but this task's core is the shared contracts, deterministic runner, persistence, rule implementations, integration seams and tests. A3 does not approve applications, activate packs, submit forms or make model judgments.

## 3. Authority and interpretation

When sources disagree, use this order:

1. `AGENTS.md` and current maintainer decisions.
2. This task spec.
3. Engineering plan v1.1 and the exact catalog requirement/failure behavior.
4. Merged A1/A2 contracts and migrations.
5. Coordinated consumer contracts, especially C2 claim bindings.
6. The deep-research report for architecture patterns only.

The research report did not have repository access and contains unusable embedded citation markers. It is retained as design research, not as proof of project requirements or third-party code provenance.

## 4. Scope and ownership

### 4.1 In scope

- A small validation package using the initialized Python/Pydantic/PostgreSQL stack.
- Shared request, context, dependency, result, receipt and capability contracts.
- A versioned, allow-listed rule registry and deterministic runner.
- Immutable persisted evaluation receipts and result rows.
- SRC-01 through SRC-10 evaluators and fixtures.
- NUM-01 through NUM-12 evaluators and fixtures.
- Exact decimal parsing/calculation primitives and explicit rounding policies.
- Source/locator/quote normalization primitives with version identifiers.
- Server-side resolution of authorized inputs before evaluation.
- Integration with merged A2 source/version/artifact/passage data.
- Compatible consumption of C2 fact bindings and application check contracts.
- Forward dependency records suitable for A4 invalidation.
- Capability reporting that distinguishes planned, implemented, tested and unavailable rules.
- Unit, property, persistence, authorization, replay and consumer-compatibility tests.

### 4.2 Out of scope

- Reverse dependency traversal, pack activation and automatic staleness transitions (A4).
- APP, POL, DAT, ELG, AUT, SKL or other lanes' rule semantics.
- Semantic support, causal-claim truth, document authenticity or meaning-preserving-edit judgments.
- New model calls, semantic retrieval, OCR, discovery crawling or browser automation.
- A universal score, universal pass/fail aggregate or claim that all catalog rules pass.
- OPA, Cedar, OpenFGA, Great Expectations or another external rule-engine runtime.
- A public replay API in the first slice; replay begins as an internal service/test capability.

### 4.3 Boundary rules

A3 may supply reusable data/access primitives for SEC-01, SEC-02, SEC-04 and SEC-13, but each rule remains enforced at its real action boundary. In particular:

- SEC-01 requires server-derived identity and per-action authorization; a stored permission snapshot does not replace a fresh action check.
- SEC-02 is provider/data-class routing, not a generic evidence permission check.
- SEC-04 is upload/parser containment, not an ordinary validation result.
- SEC-13 requires access-aware caching and reauthorization, not merely tenant-keyed cache names.

## 5. Architecture decision

A3 uses a repository-native kernel and mature supporting libraries. It does not fork or embed another validation repository. The core is project-specific because it must understand Strong Start source versions, facts, provenance, human-review states and invalidation dependencies.

Initial dependencies:

- Pydantic and existing Strong Start contracts for typed boundaries.
- SQLAlchemy/Alembic and PostgreSQL/Tiger Data for persisted receipts.
- Python `Decimal` for all numeric values and calculations.
- pytest for deterministic and integration tests.
- Hypothesis for numeric, ordering and replay properties.

External policy engines may be reconsidered only when there is a measured authorization-policy need, a named owner, a versioned adapter contract, outage/deny behavior and an operational benefit that exceeds the new deployment burden. This deferral must not prevent a future adapter.

## 6. Core contracts

All public identifiers use the existing `StableId`; A3 must not introduce a parallel UUID-only identity system. Public request models use `extra="forbid"`, are frozen, and serialize decimals as canonical strings.

### 6.1 RuleDefinition

Registry metadata must include:

- `rule_id` and immutable `rule_version`;
- owner, priority and supported scopes;
- implementation state: `planned`, `implemented`, `verified` or `unavailable`;
- prerequisite kinds and evaluator identifier;
- dependency kinds the evaluator may emit;
- reason codes and supported outcomes;
- fixture/test references.

Only server-registered evaluators are executable. A request cannot supply a Python path, expression, SQL, policy text or arbitrary callable.

### 6.2 ValidationRequest

The boundary request identifies the requested rule IDs, subject/action, exact subject version/hash, evaluation mode and expected input snapshot identifiers. Organization, actor, roles and grants are derived from authenticated server context rather than accepted from request JSON.

Unknown, planned or unavailable rule IDs return typed capability information. They do not produce decorative `pass` results.

### 6.3 ResolvedValidationContext

The orchestration layer resolves and freezes all evaluator inputs before evaluation:

- actor/organization and authorization decision identifier;
- exact subject bytes/hash or claim text/hash where relevant;
- source, artifact, passage, fact and pack/version identifiers;
- provenance and simulation labels;
- locators, extraction coverage, parser metadata and warnings;
- fact status, raw value, decimal value, unit, currency, scale, metric and scope dimensions;
- explicit locale, numeric convention and rounding policy;
- explicit evaluation time;
- relevant policy/counter/formula versions.

Evaluators receive typed values only. They may not import an API database session, perform network I/O, call a model or read the ambient clock.

### 6.4 ValidationResult

The existing shared `ValidationResult` is extended compatibly rather than replaced secretly. The final contract must support:

- `pass`, `fail`, `needs_review` and `not_applicable`;
- stable `reason_code` values, with human-facing explanations kept separate;
- observed and expected typed values;
- evidence references and affected spans where applicable;
- exact rule/evaluator version;
- input and dependency fingerprints;
- next action;
- explicit reason for every `not_applicable` result.

An evaluator may emit more than one finding when the rule contract calls for distinct affected inputs. Ordering must be canonical.

### 6.5 DependencyRef

Use one coordinated dependency vocabulary shared with C and A4. Each dependency reference must identify a kind, stable object ID, exact version/hash where applicable and organization/access scope without embedding private document content.

Required initial kinds include subject, source version, artifact hash, passage/locator, fact, pack version, formula, rounding policy, normalization policy and permission snapshot. If a C-owned dependency contract already exists when implementation starts, A3 must adapt compatibly or publish a cross-module proposal before changing it.

Until an additive per-fact version is available, a fact dependency is `pack_version_id + fact_id`. Adding `fact_version` must be backward compatible and coordinated with C; it must not make existing bindings silently mean something different.

### 6.6 EvaluationReceipt

Persist an immutable receipt containing:

- evaluation ID, organization, actor reference and server action;
- requested and executed rule versions;
- exact subject/input fingerprint;
- dependency fingerprints;
- frozen evaluation time and evaluator build identity;
- ordered results and capability omissions;
- creation timestamp and correlation/request ID.

Receipts store identifiers, hashes and minimal audit metadata. They must not duplicate private passages, credentials, cookies or entire source documents. Re-evaluation creates a new receipt; prior receipts are never overwritten into a new truth.

## 7. Runner semantics

The runner follows one explicit pipeline:

1. **Resolve:** load the exact requested objects and versions.
2. **Authorize:** enforce server-derived object/action access before private data enters the context.
3. **Freeze:** validate strict contracts, canonicalize ordering and calculate input/dependency fingerprints.
4. **Evaluate:** invoke only allow-listed pure evaluators.
5. **Persist:** atomically store the receipt and results.
6. **Return:** expose only authorized, sensitivity-safe findings and capability status.

Rules execute in canonical `(rule_id, rule_version)` order. Result serialization, evidence ordering and dependency ordering are stable. Repeating an evaluation with the same frozen context and evaluator build must yield byte-equivalent semantic results, excluding the new receipt identity and persistence timestamp.

Failure rules:

- A missing prerequisite is `needs_review`, unless the catalog explicitly requires rejection/failure for that predicate.
- `not_applicable` requires a stable reason code and evidence that the rule's scope does not apply.
- An evaluator exception is never converted to `pass`; persist/return a typed internal failure without raw exception or sensitive data.
- Unknown authorization is deny or `needs_review` at a non-disclosing boundary, according to the action contract.
- A rule pass cannot satisfy another rule implicitly.
- Aggregation is action-specific. Saving a draft, approving, exporting and prefilling have different gates; A3 does not publish a universal `overall_pass`.

## 8. Reason-code policy

Reason codes are stable machine contracts. They use lowercase snake case, are declared by the owning rule, and are tested. Human text may improve without changing the code.

Initial cross-rule codes include:

- `prerequisite_missing`
- `prerequisite_ambiguous`
- `rule_not_applicable`
- `rule_unavailable`
- `unauthorized_or_missing`
- `dependency_version_mismatch`
- `integrity_mismatch`
- `locator_unresolved`
- `normalization_mismatch`
- `numeric_format_ambiguous`
- `value_mismatch`
- `unit_mismatch`
- `scope_mismatch`
- `calculation_mismatch`
- `conflicting_facts`
- `overlap_unknown`
- `approved_input_missing`

Rule-specific additions belong in the registry/spec tests. Codes must not reveal whether another organization's private object exists.

## 9. Source-rule acceptance mapping

The check catalog remains authoritative. At minimum:

| Rule | Required behavior and acceptance evidence |
| --- | --- |
| SRC-01 | Authorized known version passes; unknown or unauthorized version is non-disclosing and never passes. |
| SRC-02 | Recompute SHA-256 from authoritative bytes; one-byte mutation fails and holds dependent claims. |
| SRC-03 | Resolve the locator against the exact version inventory; page 31 of 30 fails. |
| SRC-04 | Versioned whitespace normalization may pass; a changed digit fails. Matching is not semantic support. |
| SRC-05 | Successful capture with empty required content returns review/failure per capture state, never invented content. |
| SRC-06 | Identical hashes/canonical URLs are detected while distinct provenance records remain visible. |
| SRC-07 | Changed source content/version emits changed dependencies for A4; A3 does not itself perform all reverse invalidation. |
| SRC-08 | Required extraction metadata and resolvable original-artifact reference are verified. |
| SRC-09 | Processed coverage is compared with actual page inventory; partial extraction stays explicitly partial. |
| SRC-10 | Parser/OCR version, capture time and explicit warning list are present; absent parser version fails completeness. |

SRC-06 and SRC-07 may require orchestration over more than one resolved record but the comparison function remains pure.

## 10. Numeric-rule acceptance mapping

| Rule | Required behavior and acceptance evidence |
| --- | --- |
| NUM-01 | Preserve raw string, sign, decimal, scale and percent marker. Parenthesized loss and `1.2 million` retain meaning; ambiguous `1,234` needs review under an unknown locale. |
| NUM-02 | Apply only metric-specific bounds. `101%` fails a bounded share but is not automatically invalid as relative growth. |
| NUM-03 | Compare a claim slot with its exact verified fact/derivation and declared rounding; changing 94 to 95 fails. |
| NUM-04 | Unit, scale and currency must match or cite an explicit conversion; CAD/USD and families/children mismatches fail. |
| NUM-05 | Metric, period, program, geography and population must match; cross-program substitution fails. |
| NUM-06 | Reconcile line items/subtotals/totals using Decimal and explicit tolerance; expose the exact delta. |
| NUM-07 | Require the intended approved nonzero denominator and registered formula; absent/zero denominator prevents output. |
| NUM-08 | Require the expected metric ID; enrollment cannot satisfy a completion claim. |
| NUM-09 | Surface same-key inconsistent values without selecting a winner. |
| NUM-10 | Keep percentage-point and relative-percent operations separate and label the selected operation. |
| NUM-11 | Aggregate only explicitly disjoint, compatible scopes; unknown overlap needs review rather than summing. |
| NUM-12 | Future targets/costs require approved or explicitly simulated project input IDs; history cannot silently become a commitment. |

All calculations use `Decimal`. Floats are rejected at public numeric boundaries. Locale, currency, unit, scale, rounding mode and period/population semantics are explicit inputs rather than guessed defaults.

## 11. Persistence and migration

Implement the smallest vertical schema required for immutable evaluations before adding breadth. Expected records are an evaluation receipt, ordered result rows and ordered dependency rows, using existing organization/identity conventions and foreign keys where the referenced object is in the same database boundary.

Requirements:

- append-only evaluation identity;
- transactionally complete receipt/results/dependencies;
- canonical JSON or typed columns that preserve decimal strings and hashes;
- organization-scoped lookup and non-disclosing missing behavior;
- uniqueness/idempotency constraints only where their semantics are explicit;
- indexes for subject/rule/dependency/version lookups needed by A4;
- forward-only Alembic migration with tested downgrade/rollback behavior consistent with repository policy;
- no stored private excerpt unless already required by the authoritative evidence record.

Tiger Data/PostgreSQL remains the database. A3 does not introduce a second database or external policy datastore.

## 12. C2 and A4 integration

### 12.1 C2 parity gate

C2 currently owns a local rule runner for APP/POL behavior and wraps the shared `ValidationResult`. A3 must not change its outcomes while extracting/generalizing the shared runner seam. Before any C2 runner migration:

- replay the existing C2 fixtures through the integrated seam;
- compare ordered rule IDs, outcomes, reason codes, observed/expected values and relevant spans;
- document intentional differences and obtain Dev C acknowledgment;
- preserve C's ownership of APP/POL semantics.

A3 may initially expose an internal Python service used by C2. A public HTTP replay endpoint is unnecessary until a consumer requires it.

### 12.2 A4 dependency export

Every persisted result exposes exact forward dependencies. A4 will own changed-dependency lookup, stale marking, pack activation and concurrency behavior. A3 must provide indexed, versioned dependency data but must not pre-empt A4 by implementing hidden activation transitions.

## 13. Security and privacy requirements

- Authorization precedes resolution/disclosure of private evidence.
- Request-supplied organization/role/permission fields are ignored or rejected, never trusted.
- Unknown and unauthorized object IDs are indistinguishable at external read boundaries.
- Evaluator modules have no DB, network, model, filesystem or ambient-clock access.
- Stored receipts exclude secrets and minimize private evidence duplication.
- Logs contain correlation IDs and safe reason codes, not raw document bodies.
- Simulation/provenance labels survive context, result and receipt serialization.
- A stale permission snapshot cannot authorize a later action; action gates reauthorize.
- Registry metadata cannot grant tools, permissions or workflow transitions.

## 14. Delivery sequence

### A3a: kernel and one persisted vertical slice

- Add/finalize contracts, reason codes, registry and capability reporting.
- Implement resolve-authorize-freeze-evaluate-persist orchestration.
- Add immutable receipt/result/dependency migration and repository.
- Implement SRC-01 end-to-end against real A2 source-version data.
- Add deterministic replay, authorization-negative and persistence tests.
- Publish the shared seam to B/C for review.

Natural checkpoint: one real source version can be evaluated, persisted, replayed and inspected without leaking another organization or claiming unsupported rules are implemented.

### A3b: source rules and boundary primitives

- Implement SRC-02 through SRC-10.
- Add versioned quote normalization and locator/coverage fixtures.
- Complete source capability matrix and security-boundary tests.
- Export forward dependencies required by A4.

### A3c: numeric rules and consumer integration

- Implement NUM-01 through NUM-12 with Decimal and typed scopes.
- Add fact-version support compatibly or retain safe `pack_version_id + fact_id` dependency identity.
- Integrate C2 claim bindings and run the parity gate.
- Complete property, ambiguity-corpus, calculation and producer/consumer tests.
- Publish the A3-to-A4 handoff.

Each phase may use a separate short-lived branch/PR. A later phase must not falsely mark earlier catalog rules verified merely because the registry lists them.

## 15. Test strategy

### 15.1 Deterministic and unit tests

- Positive, negative and boundary fixture for every implemented rule.
- Exact reason-code and dependency assertions.
- Canonical result/dependency ordering.
- `not_applicable` reason invariant.
- Missing prerequisite never passes.
- Evaluator exception never passes or leaks raw exceptions.

### 15.2 Property tests

Use Hypothesis where it adds coverage:

- Decimal serialization/round-trip and no-float boundaries.
- Equivalent allowed whitespace yields the same SRC-04 decision.
- Changed quote digits never normalize to equality.
- Reordering semantically unordered inputs does not change results.
- Same frozen context produces the same semantic receipt payload.
- Budget delta equals declared total minus exact item sum.
- Percent-change and percentage-point operations remain distinct.
- Overlapping/unknown scopes are never silently aggregated.

### 15.3 Integration tests

- Real PostgreSQL migrations and transaction rollback.
- A2 artifact bytes/source versions/passages, not fixture-only substitutes.
- Cross-organization and forged-organization denial.
- Hash mismatch after byte mutation.
- Concurrent duplicate evaluations produce valid immutable receipts.
- C2 contract/parity tests and A4 dependency-query shape.
- Contract generation and TypeScript drift if public contracts change.

### 15.4 Architecture tests

- A forbidden-import test prevents evaluator modules importing DB sessions, HTTP/network clients, model adapters or clock helpers.
- Registry allow-list rejects unknown evaluator names/parameters.
- Dependency and result payloads remain within documented count/size limits.
- Receipt serialization excludes configured sensitive fields.

### 15.5 Corpora

Maintain small reviewable fixture corpora for:

- quote whitespace, Unicode punctuation, line-break and changed-digit cases;
- numeric separators, parentheses, scale words, currency, percentages and locale ambiguity;
- period/program/population/geography mismatches;
- overlapping, disjoint and unknown aggregation scopes.

Corpus entries must state expected outcomes and why; they are test data, not partner facts.

## 16. Operational limits

The first implementation defines bounded maximums for requested rules, findings per rule, evidence references, dependencies, input text size and calculation graph depth. Exceeding a limit returns a typed failure/review state; it never silently truncates decisive evidence or reports pass.

No evaluator may recursively dispatch rules. Formula execution is allow-listed and bounded. The runner records elapsed operational metrics outside the semantic result so runtime variability cannot change validation meaning.

## 17. Acceptance criteria

A3 is complete only when:

1. SRC-01 through SRC-10 and NUM-01 through NUM-12 have separate, honest registry states.
2. Every claimed implemented rule has catalog-aligned positive, negative and boundary tests.
3. The real A2 producer path is exercised for source rules.
4. Numeric rules use exact Decimal and explicit metric/scope semantics.
5. Results and immutable receipts bind exact versions/hashes and expose forward dependencies.
6. Same frozen inputs replay to the same semantic results.
7. Missing/ambiguous prerequisites never pass.
8. Cross-organization access and forged identity fields are denied without disclosure.
9. C2 compatibility is tested with real merged contracts; fixture-only integration is labelled.
10. Migrations, lint, type checking, contract generation and relevant tests pass.
11. Documentation, capability matrix, decision record and Dev A handoff are current.
12. Remaining A4 work and external-engine deferral are reported accurately.

## 18. Major decisions and permitted discretion

The maintainer has accepted the repository-native kernel, the A3a/A3b/A3c sequence and the safeguards in this spec. Internal file organization, equivalent small helper libraries and optimization choices remain Dev A discretion if they preserve the contracts and test evidence.

The following require a recorded cross-module proposal before implementation:

- breaking `ValidationResult`, `Fact`, claim-binding or dependency contract changes;
- moving APP/POL semantics out of C ownership;
- changing A4 activation/invalidation ownership;
- introducing an external policy/rule engine or second datastore;
- weakening exact-version, authorization, simulation or human-review gates.

## 19. Known dependencies and open coordination

- A2 is merged and supplies real source/version/artifact/passage storage.
- C2 supplies claim-binding and local rule-runner behavior that A3 must preserve at the shared seam.
- Dev C requested an additive fact version; A3c should answer with a compatible contract and migration plan.
- A4 will consume dependency rows; its reverse-invalidation contract must be reviewed before A3c closes.
- Dev B verifies Dev A fixtures and should review shared security/capability behavior without taking ownership of A3 implementation.

None of these dependencies authorizes bypassing PR review or silently changing another lane's public contract.

## 20. A3a/A3b implementation record

Implementation branch `dev-a/a3ab-val-003-source-validation` combines A3a and A3b in one source-validation increment while retaining the internal SRC-01 checkpoint. It adds strict source-validation contracts, the closed SRC registry, pure evaluators, migration `0005_validation_receipts`, authorized resolution, immutable receipt replay, canonical-URL/hash duplicate detection and API routes under `/api/validation`.

Catalog status is `implemented` for SRC-01 through SRC-10. It is not changed to `verified`: Dev B remains the independent verification owner and must review the fixtures/results. A3c remains separate and owns NUM-01 through NUM-12, C2 parity/property testing and the final A4 handoff.
