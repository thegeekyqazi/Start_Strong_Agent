# Shared contracts (v1)

Canonical source: Pydantic models in `python/src/strongstart_contracts/`. The models are generated into:

- `schema/strongstart-contracts.schema.json` (JSON Schema 2020-12, `$defs` per model)
- `ts/src/generated.ts` (TypeScript declarations via `json-schema-to-typescript`; import from `@strongstart/contracts`)

Run `make contracts` to regenerate and `make contracts-check` to detect drift (CI runs the drift check). Do not hand-edit the generated files.

All models forbid extra fields and are immutable. IDs use `StableId` (`^[a-z0-9][a-z0-9._:-]{0,127}$`). Decimals are exact strings (`DecimalString`), never floats. Every `$def` carries `x-contract-status` (`frozen` = consumers may rely on it for v1; `draft` = owners may extend compatibly) and `x-owner`.

| Contract | Module | Owner | Status | Boundary |
| --- | --- | --- | --- | --- |
| SourceReference, Provenance, DateKnowledge | common | A / shared | draft | Unknown dates are explicit (`status: unknown`). `content_hash` is null unless actually computed |
| ErrorEnvelope, ErrorCode | common | shared | frozen | Safe message only, no raw exceptions |
| Fact, EvidenceBundle | evidence | A | draft | Null unit/period = unknown. Fixture facts are labelled simulated |
| Opportunity, RequirementSet, RequirementCondition | funding | B1 | draft | `evaluation: unknown` for missing inputs. A link is not eligibility proof |
| QuestionSet, Question, QuestionLimit, LimitConflict, ApplicationDefinition | automation | B2 | draft | Unknown units stay `unknown`. Conflicts are preserved unresolved |
| FormMap, FieldMapping, PrefillAction | automation | B2 | draft | Only `fill_field`/`attach_file`; submit/sign is unrepresentable. Approval is an ID resolved server-side |
| AnswerSnapshot, ApprovalSnapshot, DependencyRef | answers | C | draft | No `approved` Boolean. Content hash plus dependency snapshot |
| ValidationResult | validation | shared | draft | `pass/fail/needs_review/not_applicable`. No validator is implemented |
| JobContext, JobResult, JobBudget | jobs | shared | draft | Schema only. No durable worker exists |
| ChangeSet, ChangedVersion | jobs | A | draft | Consumers must stale their real state later |
| LivenessReport, ReadinessReport, CapabilityReport, SessionIdentity | platform | shared | frozen | Consumed by the web shell |
| FixtureBundle (+ cross-reference validation) | fixtures | shared | draft | Bundle must be simulated. Dangling links/hash mismatches are rejected |

Ports (`ports.py`): `CaptureStore`, `EvidenceProvider`, `ApprovedAnswerResolver`, `JobStore`. Each has an `Unconfigured*` default that raises `CapabilityUnavailable`. Fixture adapters (`fixture_adapters.py`) set `is_fixture = True` and must be injected deliberately.

To extend an owned schema compatibly, add optional fields or new models, run `make contracts`, and note the change in your handoff. Breaking changes to shared/frozen contracts need a `proposed-cross-module` decision record and consumer acknowledgment.
