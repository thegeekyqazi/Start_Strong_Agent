# A4-PKG-004: Pack replacement and dependency invalidation

**Revision:** 1.0

**Owner:** Dev A

**Status:** developer implementation baseline derived from Engineering Plan v1.1

**Engineering baseline:** sections 4.1-4.3, 5.3, 9, 10.5, 10.8, 13.3, 14, 15, 19, 20.3-20.4, 21 and 23.2

**Catalog rules:** PKG-01, PKG-02 and PKG-03. Integration boundaries: APP-04, APP-06, AUT-02, JOB-02 and JOB-05 remain owned by their catalog owners.

## 1. Goal

Replace an organization's active evidence pack transactionally. Validate an immutable proposed manifest, compare it with the currently active manifest, publish exact changed dependencies, stale registered dependent state, and ensure new active-pack reads cannot bind an inactive pack. Historical receipts and results remain immutable and inspectable.

## 2. Scope

- Strict manifest/API contracts with immutable pack-version identity.
- Same-organization resolution of every fact, fact version, source version and policy record.
- One active pack per organization and application context.
- Optimistic activation using the caller's expected active pack version.
- Transactional active-pointer change, structured diff, reverse dependency traversal, invalidation events and an immutable change set.
- Explicit registration/currentness seam for C approvals/exports/skills and B browser grants/jobs.
- A3 validation receipts participate in reverse lookup without being mutated.
- Active-pack retrieval endpoint and a gate proving inactive packs cannot create new bindings.
- Positive, negative, boundary, cross-organization, concurrency, replay and rollback tests.

## 3. Out of scope and current dependency gap

C3 durable approvals/exports and B3 pending browser grants do not yet exist on merged `main`. A4 therefore implements and tests the real persistence/invalidation seam with typed registered consumer records, but cannot truthfully claim those absent feature tables are integrated. C and B must register their real objects before action and recheck currentness at action time. This limitation is a dependency status, not permission to add C/B private workflow tables in Dev A's feature.

## 4. Manifest contract

A manifest is server-scoped to the authenticated organization and contains:

- pack ID, immutable pack-version ID, bundle ID and application context;
- schema, mapping and parser versions, locale and access labels;
- unique fact bindings `(fact_id, fact_version)`;
- unique source-version IDs;
- unique policy bindings `(policy_id, policy_version, content_sha256)`;
- provenance/simulation label and coverage notes.

Request-supplied organization, active state, actor, approval or invalidation targets are forbidden. Duplicate IDs, missing references, version/hash mismatches and cross-organization references fail before persistence.

## 5. Activation and concurrency

Activation locks the context's active pointer, compares it with `expected_active_pack_version_id`, and returns conflict on mismatch. In one database transaction it:

1. validates the proposed immutable manifest;
2. loads the prior active manifest;
3. computes canonical changed dependency identities;
4. creates an immutable change set;
5. walks A3 dependency rows and registered consumer dependency rows;
6. appends invalidation events and marks mutable consumer currentness stale;
7. changes the active pointer.

Any failure rolls back all seven effects. Repeating activation of the already active version is idempotent and emits no second change set.

## 6. Diff and invalidation semantics

- Pack version always changes when A becomes B.
- Removed or version-changed fact, source or policy identities are changed dependencies.
- Unchanged members are retained and do not stale consumers bound only to those members.
- A target becomes stale when any exact registered dependency matches a changed old dependency.
- Historical validations, result payloads, approvals and action records are not rewritten. Currentness is a separate record/event.
- Permission is reauthorized live; a historical permission snapshot is never an activation credential.

## 7. Rule acceptance

| Rule | Acceptance |
| --- | --- |
| PKG-01 | Duplicate items and missing/cross-org/version-mismatched evidence are rejected with structured reasons; the manifest is not persisted. |
| PKG-02 | Pack A/B changes one fact and one policy while retaining one member; only exact dependent targets stale, A3 receipts remain immutable, and rollback leaves no partial activation. |
| PKG-03 | Active retrieval returns B after activation; new binding against inactive A is rejected even when a value happens to match. |

## 8. Definition of done

Migration, contracts/schema/TS, repository/service/routes, Knowledge capability text, pack A/B fixture, property/integration/API tests and A-to-B/C handoff are present. Lint, type checking, contract drift, unit tests and real PostgreSQL migration/activation tests pass. Actual C/B consumer integration remains explicitly pending until those durable producers exist.
