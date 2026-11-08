# A3 Technical Design Review: Deterministic Trust and Validation Layer for Strong Start

## Scope, evidence base, and repository-access constraint

The strongest A3 architecture is a **small, repository-native deterministic validation kernel** built on the existing Python/Pydantic/PostgreSQL stack, not a replacement rule-engine platform. A3 should own immutable validation receipts, exact-version dependency binding, deterministic source/numeric checks, and reusable permission-decision snapshots; A4 should consume those dependency edges for reverse invalidation and pack activation. Pydantic should remain the typed boundary, Python `Decimal` the authoritative numeric representation, PostgreSQL the durable audit store, Hypothesis the property-testing tool, and a deliberately narrow internal rule registry the execution mechanism. External policy engines such as OPA, Cedar, and OpenFGA contain useful design patterns but would introduce an additional policy language/runtime or networked authorization service before this repository appears to need one. Pydantic v2 already provides strict validation modes and is an actively maintained MIT-licensed dependency; its latest stable releases in November 2026 remain in the 2.x line. citeturn881998search0turn143614search2turn143614search5

One important limitation affects the repository-specific portion of this review: the authoritative Strong Start files named in the request were not available to the file-retrieval interface in this session, and exact-title web searches did not locate a public copy of the repository. I therefore **do not assign invented semantics to `SRC-01`…`SRC-10` or `NUM-01`…`NUM-12`**. Doing so would contradict the instruction to treat the repository check catalogue as authoritative and would create precisely the kind of model-invented authority A3 is intended to prevent. The design below specifies the execution model, contracts, persistence, security, numeric semantics, and per-ID implementation envelope, but the rule bodies for those 22 IDs must be populated from `StrongStart_Check_Catalog.json` and the cited engineering/spec/handoff files before any registry row is marked `implemented` or `tested`.

That distinction is material. A rule may be **registered as planned** without being implemented, and the database/API must expose that state. A planned rule must never produce an authoritative `pass`, `fail`, or `not_applicable`; attempts to execute it should result in a non-authoritative planning/coverage record, while a rule with missing factual prerequisites must return `needs_review`, according to the hard constraint in the request. This separation is also consistent with established validation-engine practice: rule-pack version, prerequisites, reasons for non-execution, and parameter provenance are treated as explicit report data rather than silently inferred. citeturn243584search0turn243584search1turn243584search3

## Technology review and adoption decisions

The following choices are based on maintained primary projects and their official documentation.

| Candidate | Evidence, licence, and useful patterns | Integration/security assessment | A3 decision |
|---|---|---|---|
| **Pydantic v2** | MIT; current 2.14.x releases in November 2026. Strict mode can reject coercions rather than silently converting input, and Pydantic emits JSON Schema. citeturn143614search2turn143614search5turn881998search0turn881998search1 | Already in the stack, so cost is negligible. Main risk is accidental lax coercion at trust boundaries. Pydantic also recently fixed Decimal constraint behaviour, reinforcing the need to pin versions and test exact numeric boundary semantics. citeturn143614search3 | **Adopt.** Use for contracts and boundary validation, with strict models on A3 authoritative inputs. Do not use Pydantic validation itself as the business-rule engine. |
| **Hypothesis** | MPL-2.0; released 6.170.15 on 6 Nov 2026 and has frequent releases. It generates edge cases and shrinks failures to simpler counterexamples. citeturn143614search1turn143614search4turn881998search6 | Pure test dependency; very low production risk. Test nondeterminism is controlled through recorded examples/seeds where CI reproducibility matters. | **Adopt.** Required for decimal, interval, unit, scope, permission, serialization, and metamorphic properties. |
| **python-jsonschema** | MIT; current project requires Python ≥3.12, matching the repository. It supports immutable referencing registries and structured `ValidationError` paths/context plus `ErrorTree`. Releases remain active in 2026. citeturn881998search4turn881998search5turn257022search0turn257022search6 | Low integration cost, but Pydantic already owns Python request contracts. Duplicating business contracts in JSON Schema would add drift risk. Its immutable registry and structured error-tree ideas are valuable for generated finite-data definitions. | **Borrow/adopt narrowly.** Use only where A3 must validate persisted/generated JSON rule data against a versioned schema; do not introduce a parallel domain-model layer. |
| **OPA** | Apache-2.0, actively maintained; release artefacts were published 5 Nov 2026. OPA supports versioned policy bundles and detailed decision logs containing query input, result, bundle revision and replay-related nondeterministic-builtin data. citeturn823722search5turn482764search1turn881998search9turn881998search10 | Powerful, but adds Rego, a second runtime/sidecar or WASM integration, deployment/version management and a new policy attack surface. Remote bundle loading is eventually consistent unless carefully pinned, which is a poor default for an A3 receipt intended to bind exact versions. citeturn881998search9 | **Defer. Borrow patterns.** Copy bundle revisioning, decision IDs, input snapshots and masking concepts. Do not use OPA for `SRC/NUM` execution. |
| **Cedar** | Apache-2.0 and active in 2026. Cedar has a schema describing principals, resources, actions and context, validates policies separately from runtime authorization, and treats schema changes as authorization-model changes requiring revalidation. citeturn823722search1turn482764search0turn482764search3 | Excellent authorization semantics, but the primary implementation is Rust and adds another policy language and binding boundary. Cedar documentation explicitly notes that policy correctness remains the application author's responsibility even after schema validation. citeturn482764search19 | **Borrow patterns; defer runtime adoption.** Particularly valuable: typed action/resource schemas, explicit policy/schema versions, deny-by-default construction, and revalidation on schema change. |
| **OpenFGA** | Apache-2.0, CNCF Incubating, active with releases through 2026. It models fine-grained authorization as relationships governed by versioned authorization models and supports stronger-consistency reads that bypass caches. citeturn823722search0turn143614search25turn482764search2turn355489search0 | Best candidate if Strong Start later needs a large shared ReBAC graph across many services. For A3 it means another service/database/API dependency and stale-read choices. Its newer dynamic CEL-expression conditions are explicitly experimental, and generated executable expressions would conflict with the requirement that generated rules be finite data/instructions rather than executable code. citeturn355489search4 | **Defer.** Borrow model-ID pinning, relationship-based vocabulary, consistency controls, and test fixtures; do not put A3 validation behind a network authorization call. |
| **Python `decimal`** | Standard-library implementation of decimal arithmetic. Python documents exact string construction, explicit contexts, quantization, rounding modes, traps such as `Inexact`, and warns that constructing from binary float preserves the float approximation exactly. citeturn192247search0turn192247search7 | Zero added dependency. Risks are implicit global contexts, accidental float construction, hidden rounding, NaN/Infinity and inconsistent quantization. | **Adopt as normative numeric kernel.** No authoritative float ingress. |
| **Babel** | BSD-licensed. `parse_decimal` parses locale-specific strings directly to `Decimal`, and strict mode rejects irregular localized formatting. citeturn192247search1turn192247search2 | Useful only at ingestion/UI normalization. Locale databases can change across Babel/CLDR versions, so normalization results must bind parser/version/locale. System locale defaults are unacceptable for deterministic A3 evaluation. | **Adopt narrowly or borrow.** Require explicit locale; never infer locale from process environment for authoritative values. |
| **Pint** | BSD-3-Clause; active release in Oct 2026. Pint supports dimensional quantities and can use `Decimal` or `Fraction`, though its default magnitude type is float. citeturn192247search3turn192247search4turn192247search5 | Good unit catalogue, but default float use violates A3 unless configured carefully, and a broad mutable unit registry can make semantics harder to freeze. | **Defer for A3a.** Prefer a small canonical unit table for the units actually present in the catalog; consider Pint later only with a frozen registry and `Decimal`/`Fraction` magnitude type. |

A useful additional pattern comes from `python-jsonschema`: its error representation separates **where the failure occurred**, **which validation keyword failed**, and **nested causal context**, instead of flattening all problems to strings. citeturn257022search6 A3 should borrow that shape while preserving Strong Start’s domain statuses. Conversely, generic validation systems that permit arbitrary generated code should be rejected: the rule catalogue should identify a finite evaluator kind plus typed parameters; it must not contain Python expressions, SQL fragments, Rego, CEL, Jinja, or dynamically imported callables.

## Recommended A3 contracts and deterministic runner

The core contract should distinguish immutable **definition identity**, **input identity**, **dependency identity**, and **evaluation outcome**. A successful evaluation is reproducible only when all four are bound.

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )


class ValidationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"
    NOT_APPLICABLE = "not_applicable"


class ImplementationState(StrEnum):
    PLANNED = "planned"
    IMPLEMENTED = "implemented"
    TESTED = "tested"


class DependencyKind(StrEnum):
    SOURCE = "source"
    SOURCE_VERSION = "source_version"
    PASSAGE = "passage"
    FACT_VERSION = "fact_version"
    ARTIFACT = "artifact"
    ARTIFACT_VERSION = "artifact_version"
    CLAIM = "claim"
    EVIDENCE_BINDING = "evidence_binding"
    PERMISSION_SNAPSHOT = "permission_snapshot"
    POLICY_VERSION = "policy_version"
    RULE_DEFINITION = "rule_definition"
    APP_POL_RESULT = "app_pol_result"


class DependencyRef(StrictModel):
    kind: DependencyKind
    object_id: UUID | str
    version_id: UUID | str
    org_id: UUID
    content_sha256: str | None = None


class ExactFactVersion(StrictModel):
    fact_id: UUID
    fact_version_id: UUID
    org_id: UUID
    fact_type: str
    canonical_value: str
    canonical_unit: str | None = None
    source_version_id: UUID
    evidence_refs: tuple[DependencyRef, ...]
    content_sha256: str


class PermissionDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class PermissionCheck(StrictModel):
    action: str
    resource_type: str
    resource_id: UUID | str
    decision: PermissionDecision
    reason_code: str
    policy_ref: DependencyRef


class PermissionSnapshot(StrictModel):
    snapshot_id: UUID
    org_id: UUID
    actor_id: UUID
    subject_type: str
    evaluated_at: datetime
    policy_version: str
    membership_version: str
    checks: tuple[PermissionCheck, ...]
    snapshot_sha256: str


class ValidationContext(StrictModel):
    org_id: UUID
    request_actor_id: UUID
    evaluation_time: datetime
    input_version: str
    claim_id: UUID | None = None
    answer_id: UUID | None = None
    exact_facts: tuple[ExactFactVersion, ...] = ()
    evidence: tuple[DependencyRef, ...] = ()
    permission_snapshot: PermissionSnapshot
    dependencies: tuple[DependencyRef, ...]
    locale: str | None = None


class RuleDefinition(StrictModel):
    rule_id: str
    semantic_version: str
    owner: str
    implementation_state: ImplementationState
    evaluator_kind: str
    prerequisite_kinds: tuple[str, ...]
    invalidation_kinds: tuple[str, ...]
    parameter_schema_version: str
    parameters: dict[str, str | int | bool | Decimal]
    spec_ref: str
    definition_sha256: str


class FindingLocation(StrictModel):
    object_type: str
    object_id: UUID | str
    field_path: tuple[str | int, ...] = ()
    start_char: int | None = None
    end_char: int | None = None


class ValidationResult(StrictModel):
    rule_id: str
    rule_version: str
    status: ValidationStatus
    reason_code: str
    message: str
    not_applicable_reason: str | None = None
    locations: tuple[FindingLocation, ...] = ()
    dependency_refs: tuple[DependencyRef, ...]
    permission_snapshot_id: UUID
    evaluated_at: datetime
    evaluator_version: str
    input_sha256: str
    result_sha256: str


class ValidationReport(StrictModel):
    report_id: UUID
    org_id: UUID
    subject_type: str
    subject_id: UUID | str
    runner_version: str
    registry_version: str
    created_at: datetime
    permission_snapshot: PermissionSnapshot
    results: tuple[ValidationResult, ...]
    dependencies: tuple[DependencyRef, ...]
    report_sha256: str
```

Two invariants should be enforced structurally. First, `not_applicable` is invalid without a non-empty reason. Second, any missing required prerequisite produces `needs_review`, never `pass`. Pydantic is appropriate for these cross-field invariants, but the authoritative decision still belongs to the rule evaluator rather than a caller-provided status. Strict validation matters because Pydantic otherwise deliberately performs coercions such as string-to-integer conversion. citeturn881998search0

`evaluation_time` deserves special handling. Time is an input, not a hidden dependency. The server creates it once, binds it into the `ValidationContext`, and every time-sensitive rule receives that value. A pure evaluator never calls `datetime.now()`. This mirrors deterministic validation designs that prohibit current-time and network calls inside check execution. citeturn243584search4

### Registry and execution architecture

The registry should be static Python plus generated **data**, not generated executable code:

```text
catalog JSON
   ↓ schema validation
RuleDefinition records
   ↓ startup verification
registry[(rule_id, semantic_version)]
   ↓
evaluator_kind → pre-reviewed Python function
```

A catalogue entry may select only an allow-listed evaluator kind such as `source_binding`, `exact_match`, `numeric_compare`, `numeric_sum`, `ratio`, `range`, `period_alignment`, or `scope_compatibility`. Parameters are finite typed values validated against a versioned schema. There is no `eval`, dynamic import path, Python source, SQL, Rego, CEL, template expression, or model call.

The registry metadata should include `owner`, `semantic_version`, `implementation_state`, `prerequisite_kinds`, `invalidation_kinds`, `parameter_schema_version`, `spec_ref`, and `definition_sha256`. A semantic change that can alter a result must create a new rule version rather than mutating the old definition. This follows the same useful principle seen in versioned deterministic rule packs: result-affecting semantic changes require a new pinned semantic identity. citeturn243584search3

Execution should occur in four stages: **resolve → authorize → evaluate → persist**. Resolution constructs all exact source/fact/evidence references. Authorization derives an immutable permission snapshot. Evaluation runs pure functions over that closed context. Persistence stores the complete receipt and dependency edges in one transaction. There must be no lazy database fetch from inside a rule because that creates hidden dependencies and makes replay ambiguous.

### Server-side authorization and anti-enumeration flow

The client should submit only the intended subject and requested operation. It must not submit `org_id`, permission outcomes, “verified” flags, or approval state as authoritative fields.

The endpoint flow should be:

1. Authenticate the server-side principal and derive its active organization.
2. Load the target through an organization-scoped query plus permission predicates.
3. Resolve source/fact/evidence IDs through the same organization scope.
4. For any missing **or unauthorized** requested ID, return the same externally visible response shape and status so an attacker cannot distinguish existence from lack of access.
5. Construct `PermissionSnapshot` from server-side membership/role/policy state.
6. Bind the snapshot and policy/membership versions into `ValidationContext`.
7. Run the deterministic registry.
8. Persist report, result rows, dependency edges and permission snapshot atomically.

This anti-enumeration pattern is used by other multi-tenant deterministic validation services, which deliberately return the same not-found response for absent and foreign-tenant reports. citeturn243584search7 For Strong Start, it should be applied to A1/A2 IDs as well as A3 reports.

The reusable primitives for `SEC-01`, `SEC-02`, `SEC-04` and `SEC-13` should therefore not be “policy rules” mixed into `SRC/NUM`; they should be small server-owned operations such as `authorize_read(resource)`, `authorize_validate(resource)`, `authorize_bind_evidence(resource)`, and `authorize_use_fact_version(fact_version)`, each producing `PermissionCheck` records. Whether those four SEC checks map one-to-one to these primitives must be confirmed against the unavailable catalogue before naming the mapping authoritative.

OPA and OpenFGA reinforce two useful design ideas here: authorization decisions should carry a stable decision identifier/version context, and cache consistency is a security choice rather than an implementation detail. OPA decision logs include bundle revision, input and result, while OpenFGA exposes a higher-consistency mode specifically to avoid stale cached permissions. citeturn881998search10turn355489search0 A3 should achieve the same property locally by snapshotting the exact membership/policy revision used for every result.

## Persistence, exact numeric semantics, and rule implementation envelope

### Persistence schema and migration sequence

I recommend six A3 tables plus one optional catalogue table:

```text
validation_reports
- id uuid pk
- org_id uuid not null
- subject_type text not null
- subject_id uuid/text not null
- runner_version text not null
- registry_version text not null
- permission_snapshot_id uuid not null
- created_at timestamptz not null
- canonical_payload jsonb not null
- report_sha256 char(64) not null
- unique(org_id, report_sha256) optional

validation_results
- id uuid pk
- report_id uuid fk
- ordinal integer
- rule_id text
- rule_version text
- status enum
- reason_code text
- message text
- not_applicable_reason text null
- evaluator_version text
- evaluated_at timestamptz
- input_sha256 char(64)
- result_sha256 char(64)
- canonical_payload jsonb
- unique(report_id, ordinal)

validation_dependencies
- report_id uuid fk
- result_id uuid null fk
- dependency_kind text
- object_id text
- version_id text
- org_id uuid
- content_sha256 char(64) null
- primary key(report_id, result_id, dependency_kind, object_id, version_id)

permission_snapshots
- id uuid pk
- org_id uuid
- actor_id uuid
- evaluated_at timestamptz
- policy_version text
- membership_version text
- canonical_payload jsonb
- snapshot_sha256 char(64)

permission_snapshot_checks
- snapshot_id uuid fk
- ordinal integer
- action text
- resource_type text
- resource_id text
- decision enum
- reason_code text
- policy_version text
- primary key(snapshot_id, ordinal)

rule_registry_manifest
- rule_id text
- semantic_version text
- owner text
- state enum(planned, implemented, tested)
- evaluator_kind text
- definition_sha256 char(64)
- spec_ref text
- primary key(rule_id, semantic_version)
```

Do **not** update historical rows when rule semantics change. New semantic versions get new registry entries. The manifest table may be generated from code at deploy time or written by a migration, but it is descriptive; executable functions remain reviewed Python.

The Alembic sequence should be reviewable: introduce enums/tables without callers; add write path; add replay/read path; then add indexes/constraints after representative production-sized tests. Cross-org foreign keys should include `org_id` where the existing A1/A2 schema permits composite references, or the service layer must prove organization equality before insertion. A database constraint on `status='not_applicable' ⇒ not_applicable_reason IS NOT NULL AND length(trim(...))>0` is worthwhile because it protects the invariant below the application layer.

A3 should store a normalized canonical JSON representation for hashing, but **database JSONB must not be the only representation of authoritative decimals**. PostgreSQL `NUMERIC` is appropriate for queryable numeric columns; canonical serialized decimals should be strings when placed in JSON to avoid downstream JSON number parsers converting them to binary float.

### Decimal, locale, units, currency, period, population and scope

Authoritative numeric input must begin as a string, integer, PostgreSQL `NUMERIC`/Python `Decimal`, or a typed exact fact value. A binary float should be rejected at A3's authoritative boundary. Python documents why: `Decimal(3.14)` preserves the exact binary floating-point approximation, producing a long decimal value rather than the text value `3.14`. citeturn192247search0turn192247search7

Each numeric evaluator should use an explicit local decimal context rather than the process-global context. Precision, rounding and enabled traps become part of `evaluator_version`. For checks requiring exactness, trap `Inexact`, `InvalidOperation`, `DivisionByZero`, `Overflow`, and reject NaN/Infinity. Quantization should occur only where the rule definition specifies a scale or rounding policy; Python's `quantize()` and `Inexact` trap are explicitly suited to fixed-scale validation. citeturn192247search0

Locale is a parsing concern, not a comparison concern. Canonical A3 numbers use ASCII decimal strings with `.` and no grouping. If raw user text must be parsed, the parser must receive an explicit locale. Babel can produce a `Decimal` and its strict mode rejects malformed locale-specific formatting, but its locale/CLDR version must then become a dependency snapshot. citeturn192247search1 Never use the host's `LC_NUMERIC`, `LANG`, or equivalent defaults for authoritative interpretation; Babel itself can derive defaults from environment variables when locale is omitted. citeturn192247search2

Units should be canonical identifiers, not free text: for example, exact unit dimensions plus a canonical conversion factor represented as `Decimal` or rational numerator/denominator. Pint demonstrates that Decimal-based quantity conversion is feasible, but Pint defaults to float unless explicitly configured. citeturn192247search4 For the initial A3 implementation, a small frozen unit table covering only catalogued units is easier to audit than a general-purpose unit registry.

Currencies should never be treated as dimensionally convertible units without an explicit exchange-rate fact. `CAD 100` and `USD 100` are different typed quantities. Currency conversion requires an exact rate fact carrying source, rate version, effective date/time, quote/base currencies, and rounding policy; absent any of those prerequisites, the rule returns `needs_review`.

Periods must be structured values, not display strings: `{start_date, end_date, inclusivity, granularity, fiscal_calendar_id?}`. Comparisons require a declared alignment rule. “2026” must not silently mean calendar year if the relevant grant uses a fiscal year.

Population and scope should also be typed. A numeric equality is not a semantic equality when denominators differ. A value should bind `population_id` or a structured scope such as organization/program/site/cohort/geography; period; measurement definition; inclusion/exclusion criteria; and, where relevant, aggregation method. A numeric rule may compare values only when the catalogue declares scopes compatible or supplies an explicit transform. Otherwise it returns `needs_review`.

### `SRC-*` implementation strategy

Because the authoritative `StrongStart_Check_Catalog.json` was unavailable, these IDs should initially be registered exactly as follows until their definitions are copied and reviewed:

| Rule | Initial A3 registry state | Required implementation action |
|---|---|---|
| `SRC-01` | `planned` | Bind the exact catalogue definition, prerequisites, evaluator kind, reason codes and positive/negative fixtures before enabling. |
| `SRC-02` | `planned` | Same. |
| `SRC-03` | `planned` | Same. |
| `SRC-04` | `planned` | Same. |
| `SRC-05` | `planned` | Same. |
| `SRC-06` | `planned` | Same. |
| `SRC-07` | `planned` | Same. |
| `SRC-08` | `planned` | Same. |
| `SRC-09` | `planned` | Same. |
| `SRC-10` | `planned` | Same. |

The source-rule evaluator toolbox should nevertheless be implemented in A3a so the catalog rules become thin mappings rather than bespoke infrastructure: exact source-version existence; org-scope consistency; evidence locator validity; passage-to-source-version binding; artifact/extraction-version binding; exact fact-version provenance; evidence coverage; claim-span containment; permission-to-use-source; and source/fact temporal applicability. Which evaluator maps to which `SRC-*` ID must come from the repository, not from this report.

Every source evaluator should compare immutable/versioned identifiers, never “latest source” or “current fact” implicitly. A1/A2 may resolve a current version for a user workflow, but A3 receipts must record the exact version used. Evidence-binding validation should fail closed to `needs_review` if a referenced version is missing, inaccessible or ambiguous.

### `NUM-*` implementation strategy

The same constraint applies to `NUM-01` through `NUM-12`:

| Rule | Initial A3 registry state | Required implementation action |
|---|---|---|
| `NUM-01` | `planned` | Copy authoritative definition; map to an allow-listed exact-decimal evaluator; add catalogue fixtures. |
| `NUM-02` | `planned` | Same. |
| `NUM-03` | `planned` | Same. |
| `NUM-04` | `planned` | Same. |
| `NUM-05` | `planned` | Same. |
| `NUM-06` | `planned` | Same. |
| `NUM-07` | `planned` | Same. |
| `NUM-08` | `planned` | Same. |
| `NUM-09` | `planned` | Same. |
| `NUM-10` | `planned` | Same. |
| `NUM-11` | `planned` | Same. |
| `NUM-12` | `planned` | Same. |

The numeric evaluator library should be capable of exact equality; ordered comparisons; bounded ranges with explicit inclusive/exclusive endpoints; additive totals; differences; ratios and percentages; percentage-point differences; weighted totals; unit conversion; period alignment; currency compatibility/conversion; and population/scope compatibility. That set is an architectural recommendation, not a claim that these are the catalog semantics.

For ratio/percentage operations, division-by-zero produces `needs_review` unless the rule definition explicitly defines another outcome. Tolerance must always be explicit and typed; no universal epsilon should exist. A tolerance itself is part of the rule version and therefore of the result's dependencies. Exact-decimal arithmetic avoids binary-representation error, but it does not remove the need to specify rounding and tolerance semantics. Python's decimal context explicitly controls precision, rounding and exceptional signals. citeturn192247search0

## C2 integration, A3/A4 boundary, threat model, and test strategy

### C2 APP/POL integration

A3 should not absorb C2's APP/POL ownership. The integration should be a **read-only adapter** over C2's existing deterministic registry:

```text
C2 claim
 ├─ exact claim span
 ├─ evidence bindings
 ├─ C2 APP results
 └─ C2 POL results
          ↓ immutable dependency refs
A3 validation report
```

A3 may validate that a C2 APP/POL result exists, came from the expected registry/rule version, applies to the same exact claim span/input version, and is authorized for the current organization. A3 must not reinterpret the policy, silently rerun a different semantic version, or downgrade C2 tests. The dependency should look like `DependencyRef(kind=APP_POL_RESULT, object_id=..., version_id=<C2 rule/result version>, content_sha256=...)`.

If A3 later needs to run C2-owned evaluators as part of one combined report, call them through their existing public pure-function interface and keep their owner metadata as `C2`. A3's registry can expose them as external owned rules but cannot mark them as A3-owned. This is analogous to treating external schemas/policies as versioned dependencies rather than copying them into a new authority domain.

### A3/A4 boundary

A3 should write a complete **forward dependency set**:

```text
validation result
→ rule version
→ input version
→ exact fact versions
→ source/source versions
→ passages/artifacts
→ C2 APP/POL results
→ permission snapshot
→ policy/membership version
→ evaluation time
```

A3 is responsible for making this dependency set complete enough that a historical result can be explained and deterministically replayed.

A4 owns the inverse operation: “given that dependency X changed, which results/packs are stale?” A4 therefore builds or materializes the reverse graph, schedules invalidation/revalidation, and controls validation-pack activation. A3 should not mark historical receipts “wrong”; a historical receipt remains a record of what was evaluated against exact inputs at that time. A4 may mark it superseded/stale for current workflow purposes.

This split closely resembles versioned policy systems in which the evaluated bundle/model revision is recorded with the decision; later model changes do not rewrite the old decision. OPA's decision-log design, for example, records bundle metadata alongside each decision. citeturn881998search10

### Threat model

The principal threats and controls are:

| Threat | Control |
|---|---|
| **Client/model-forged `pass`, approval, permission, verified fact** | Do not accept authoritative outcome fields from request DTOs. Server constructs context and writes results. Models may supply proposals only. |
| **Cross-org source/fact/report probing** | Every load is scoped from authenticated server-derived org. Missing and unauthorized IDs have indistinguishable external behaviour. |
| **Stale permission decision** | Bind membership/policy revision and evaluation time into `PermissionSnapshot`; privileged state-changing operations re-authorize rather than trusting an old snapshot. |
| **Approval replay** | Approval is a separately versioned authorization artefact bound to exact subject/input hash, actor, scope, permission revision and expiry/consumption semantics; A3 never converts prose saying “approved” into approval state. |
| **Untrusted generated rule definition** | Validate against closed schema; allow-listed evaluator kinds only; no executable expression/string; signed/reviewed catalogue manifest in deployment. |
| **Cache leakage across orgs** | Cache keys begin with org identity and exact version/hash; prefer process-local immutable caches for rule definitions only. Never cache permission results without actor/org/policy revision in the key. |
| **TOCTOU between authorization and result persistence** | Resolve and authorize from a transactionally consistent snapshot where practical; persist snapshot versions. For state-changing operations, re-check immediately at commit boundary. |
| **Hidden network/model call** | Rule package has no network/model dependency; lint/import rules plus tests monkeypatch sockets/HTTP clients/model clients to raise. |
| **Rule-version confusion** | Registry key is `(rule_id, semantic_version)`; report binds definition hash and evaluator version. |
| **Locale or environment drift** | Explicit locale/decimal context/unit registry version; no environment-derived locale. |
| **Hash ambiguity** | Canonical serialization with explicit schema version, sorted map keys and stable decimal/string representations before SHA-256. |
| **Denial-of-service numeric inputs** | Bound digit count, exponent, collection size and evaluator complexity before arithmetic. Pydantic/request-size constraints are necessary but not sufficient. |

Cedar's policy model is instructive here: changing the authorization schema changes the authorization model and may require policy revalidation. citeturn482764search0 Strong Start should similarly treat a permission-schema or policy-semantic change as a new version, not an invisible implementation change.

### Positive, negative, boundary, metamorphic and property tests

A3 should require five test classes for every implemented rule. **Positive fixtures** demonstrate the smallest authoritative pass cases. **Negative fixtures** demonstrate each documented failure reason. **Boundary fixtures** hit equality, one smallest representable step either side of thresholds, zero, sign changes, date boundaries, inclusive/exclusive ends, quantization boundaries and maximum accepted digit/exponent lengths. **Metamorphic tests** apply transformations that should preserve or predictably change the outcome. **Property-based tests** search broader spaces and shrink counterexamples.

Hypothesis is particularly valuable here because it generates edge cases automatically and shrinks failures to simpler counterexamples. citeturn881998search6turn881998search7 Recommended properties include:

- no authoritative evaluator ever receives `float`;
- serialization → deserialization preserves every `Decimal`, rule version and dependency identity;
- reordering irrelevant input maps/lists does not change canonical report hashes where ordering is semantically irrelevant;
- adding an unused source/fact does not change a result;
- removing any declared required prerequisite can only move to `needs_review`, never `pass`;
- changing org IDs while retaining object IDs can never yield a cross-org `pass`;
- a denied permission can never be transformed into allow by any model/client field;
- `not_applicable` is impossible without a reason;
- exact unit round-trips preserve values for rational conversion factors;
- changing currency with no rate can never preserve a definitive numeric comparison;
- scaling both numerator and denominator by the same non-zero exact factor preserves a ratio rule;
- adding zero to an exact sum does not change the result/hash except where the input dependency set itself is intentionally hash-visible;
- replaying the same canonical context and rule version yields byte-identical rule result payload/hash;
- any semantic rule change must cause either a semantic-version or definition-hash change.

For generated rule data, run JSON-schema validation in CI and startup verification against an immutable local schema registry. `python-jsonschema`'s immutable `referencing.Registry` is a good model because it avoids uncontrolled remote reference retrieval and makes the set of schema resources explicit. citeturn881998search5

Dependency snapshots should include the Python lockfile/commit, A3 runner version, Pydantic version, Babel/CLDR version if locale parsing is used, unit-registry version if units are externally sourced, and rule-definition hashes. Historical replay should **not** require recreating the entire production environment when the result payload already stores its exact dependencies, but golden replay tests should run against pinned lockfiles in CI.

## Delivery sequence, non-goals, and A3a/A3b/A3c acceptance gates

The implementation should be split into narrow pull requests rather than landing rule logic, authorization and persistence together.

A practical PR sequence is: contract additions first; registry manifest and state machine second; exact decimal/canonical serialization primitives third; permission snapshot/context builder fourth; report/result/dependency persistence fifth; runner/replay sixth; one vertical source rule seventh; one vertical numeric rule eighth; then remaining `SRC-*` and `NUM-*` rules in catalogue-sized batches; C2 APP/POL adapter after the runner semantics are stable; and finally security/property/replay hardening. Each rule PR should change its registry state only from `planned → implemented` when executable and `implemented → tested` only when the required fixture/property suite passes. Registration alone never counts as implementation.

Explicit non-goals for A3 should be model-based fact verification, web retrieval, source ingestion, approval issuance, organization selection, permission creation, “latest fact” inference, reverse invalidation traversal, pack activation, arbitrary user-authored code, general workflow orchestration, exchange-rate discovery, or replacing FastAPI/Pydantic/SQLAlchemy/PostgreSQL with a policy platform. OPA, Cedar and OpenFGA are therefore rejected **as A3 runtime dependencies for now**, not rejected as technologies. OPA is an actively maintained general-purpose policy engine with strong decision logging and bundle mechanics; Cedar has excellent typed authorization schemas and validation; OpenFGA is an active CNCF authorization system with explicit consistency controls. Their capabilities are real, but the cost and semantic surface are disproportionate to a repository whose stated architecture already puts deterministic validation inside the Python service. citeturn482764search1turn482764search0turn143614search25

### A3a

**Build:** contracts; canonical serialization/hashing; exact `Decimal` kernel; dependency references and exact fact-version types; rule registry with `planned/implemented/tested`; server-derived `ValidationContext`; permission snapshot primitives; persistence tables; deterministic runner skeleton; replay API/service; catalogue JSON schema validation.

**Acceptance gates:** no authoritative float path; no network/model calls from evaluator package; `not_applicable` requires a reason at contract and DB levels; missing prerequisites mechanically map to `needs_review`; server rejects/ignores client-provided org/permission/outcome authority; cross-org and unknown IDs are externally indistinguishable; every persisted result binds rule version/hash, input hash, exact dependencies, permission snapshot and evaluation time; planned rules cannot yield authoritative outcomes; replay of a fixed context/rule version is byte-stable.

A3a should be mergeable before any claim that the 22 source/numeric checks are implemented.

### A3b

**Build:** all catalogue-defined `SRC-01`…`SRC-10`, after reading the authoritative catalogue/specs; exact A1/A2 fact/source/passage/artifact version binding; evidence/provenance checks; C2 exact claim-span/evidence-binding adapter; C2 APP/POL registry integration without ownership transfer.

**Acceptance gates:** every SRC rule has its authoritative catalogue definition linked via `spec_ref`; each is marked `tested` only with positive, negative, missing-prerequisite, cross-org, stale-version, boundary and replay fixtures; each result enumerates exact evidence/version dependencies; no rule resolves “latest” during evaluation; C2 APP/POL regression tests run unchanged, and A3 adds adapter tests rather than weakening C2 assertions.

### A3c

**Build:** all catalogue-defined `NUM-01`…`NUM-12`; locale normalization boundary; canonical units/currencies/period/population/scope types; property/metamorphic test suite; dependency snapshot manifest; security and load hardening; A4-facing dependency export.

**Acceptance gates:** every NUM rule is catalogue-linked and `tested`; zero binary-float use in authoritative calculations is enforced by tests/lint/type boundaries; all rounding/tolerance rules are explicit and versioned; locale is explicit; currencies never convert without an exact rate fact; incompatible units/periods/populations/scopes produce the catalogue-prescribed non-pass outcome and missing prerequisites always produce `needs_review`; property tests cover arithmetic identities and pathological magnitudes; mutation/replay tests prove a semantic change requires a new rule version/hash; A4 can consume dependency edges without A3 implementing reverse invalidation or pack activation.

The central design recommendation is therefore: **build A3 as a closed, typed, pure-by-default Python validation kernel with immutable PostgreSQL receipts and exact dependency/permission snapshots; use Pydantic, `Decimal`, Hypothesis and narrowly scoped JSON Schema support; borrow versioning/audit ideas from OPA, schema discipline from Cedar and relationship/consistency ideas from OpenFGA, but defer all three as runtime dependencies.** The unresolved repository-specific task is not architectural but authoritative: populate and test the exact `SRC-*` and `NUM-*` semantics from `StrongStart_Check_Catalog.json` and the A1/A2/C2 specifications before changing any of those rules from `planned` to `implemented` or `tested`.
