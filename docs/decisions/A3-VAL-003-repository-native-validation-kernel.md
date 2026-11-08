# A3-VAL-003: Use a repository-native validation kernel and defer external rule engines

- Author/developer: Dev A
- Date: 2026-11-08
- Status: accepted-maintainer
- Decided/accepted by and evidence: project owner accepted the normal A3 plan plus the documented safeguards in the active Codex session on 2026-11-08
- Engineering path/version/sections: `docs/engineering/StrongStart_Engineering_Plan.md` v1.1 sections 3-5, 8.2, 9, 10.1-10.2, 13.2, 14-15, 19-21 and 23.2
- Feature spec path/revision: `docs/specs/A3-VAL-003_Deterministic_Validation_Runner.md` rev 1.0
- PR / Issue: pending publication
- Supersedes / superseded by: none

## Original requirement

Engineering v1.1 specifies a validation package, rule registry, `ValidationContext`, `ValidationResult`, pure evaluators where possible, exact dependency versions and reproducible findings. It does not require OPA, Cedar, OpenFGA, Great Expectations or another external rule-engine runtime.

The A3 research report recommended a small deterministic Python kernel and described external systems as useful architectural references. The project owner asked whether adopting them would improve A3 and then chose the original plan unless a major issue required a change.

## Decision / deviation and reason

Implement A3 in the initialized Python/Pydantic/PostgreSQL stack. Use mature libraries for typed boundaries, persistence and testing, but implement Strong Start's source/numeric evaluators, receipts, reason codes and dependency records in the repository.

Do not add an external rule or policy runtime during A3. Preserve a narrow adapter boundary so a later measured authorization need can introduce one without replacing domain evaluators.

This is a clarification, not a departure from the engineering plan. External engines do not supply Strong Start's evidence semantics and would add a policy language/data model, deployment, version mapping, outage behavior and cross-lane testing while leaving the main evaluators to build.

Alternatives considered:

- OPA or Cedar: potentially valuable for future authorization policy, but not the domain validation core.
- OpenFGA: useful if relationship-based access becomes complex; premature for current permissions.
- Great Expectations: useful for batch data-quality monitoring; a poor primary fit for source-linked grant claims.
- Forking a validation repository: rejected because its contracts, provenance and invalidation semantics would still require substantial replacement.

## Impact and coordination

- A owns SRC/NUM evaluators, shared runner primitives and migration sequencing.
- C retains APP/POL semantics and must acknowledge any shared-contract migration.
- B retains DAT/ELG/AUT/network/deployment responsibilities and verifies A's rule fixtures.
- A4 remains responsible for reverse invalidation and pack activation.
- No additional service, datastore or policy language is introduced.
- Tiger Data/PostgreSQL remains the persistence layer.

Reconsider an external engine only with a concrete use case, owner, adapter contract, policy-version receipt, deny-on-outage behavior, privacy analysis, deployment plan and measured benefit.

## Validation and rollback

This documentation decision was checked against the current engineering plan, rule catalog, merged A2 contracts and C2 handoffs. No runtime code or schema changes are made by this record.

Rollback is documentation-only: a later maintainer decision may supersede this file and add an external adapter. Existing domain evaluators and receipts should remain valid because the deferred adapter boundary is intentionally replaceable.
