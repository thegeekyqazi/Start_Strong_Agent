# DEV-B-BUNDLE-002: Local B repositories, version identity and review semantics

- Author/developer: Dev B agent (Claude Code, claude-opus-5-5) for the project owner (Dev B)
- Date: 2026-11-08
- Status: developer-decision (within DEV-B-BUNDLE-002 rev 1.0 s4.1, s10 and s13 discretion)
- Decided/accepted by and evidence: the Dev B agent; the persistence approach itself is prescribed by spec s4.1. Not yet reviewed by the owner.
- Engineering path/version/sections: `docs/engineering/StrongStart_Engineering_Plan.md` v1.1, s4, s9, s10.1, s10.3-10.4, s14-15, s20.3, s22
- Feature spec path/revision: `docs/specs/DEV-B-BUNDLE-002_Saved_Grant_Workspace_and_Reviewed_Research.md` rev 1.0
- PR / Issue: draft PR from `dev-b/dev-b-bundle-002` (see the bundle handoff)
- Supersedes / superseded by: supersedes the unimplemented B2-AUTO-001A rev 1.0 assignment (spec s1). No B2-AUTO-001A code existed when this bundle started; nothing was merged into M1.

## Original requirement

Spec s4.1 asks for swappable, bounded **local/test repository adapters** for the bundle's new B metadata. They must persist across API restarts and be disabled in production. Migrations, Tiger Data, SQLite and A's private artifact classes stay untouched. Spec s10 lists the storage guarantees: organization namespaces, path confinement, exact bytes, canonical JSON hashing, atomic immutable writes with cross-process coordination, compare-and-swap, idempotency replay and no visible half-commits.

## Decisions

### 1. One low-level helper, separate business modules

- `services/api/src/strongstart_api/features/dev_b_store/` is a Dev B-owned **storage helper**. It provides org namespaces, ID validation, path confinement, a cross-process lock, no-clobber atomic create, canonical JSON digests, immutable versioned objects and idempotency records. It contains no funding or automation logic.
- Funding (cases, profiles, runs, observations, capture catalog) and automation (saved definitions) each build their own repository on top of it. Each module reaches the other's data only through public readers and factories: `strongstart_api.features.funding.public` and `strongstart_api.features.automation.public`.

### 2. Storage layout and guarantees

The root is `STRONGSTART_DEV_B_STORE_DIR` (default `.local-data/dev-b-store`, git-ignored, per worktree). Under it:

```text
org-<sha256(org)[:32]>/<collection>/<object-id>/v000001.json   immutable version envelopes
org-<...>/blobs/<sha256>                                          exact input bytes (content-addressed)
org-<...>/idempotency/<collection>/<sha256(key)>.json             intent records
org-<...>/locks/<collection>.lock                                 cross-process lock file
```

- **IDs.** Object IDs are server-generated and time-ordered: `<prefix>-<12 hex ms><14 hex random>`. Every path segment is validated against a fixed pattern *before* any filesystem call. Resolved paths must stay inside the root, which rejects symlink escapes.
- **Commit point.** A version file is created with `os.link(tmp, final)`, which fails if the target exists, so it is a no-clobber, atomic create. Writing `vN+1` is therefore a genuine compare-and-swap even without the lock: of two writers expecting version N, exactly one link succeeds.
- **Locking.** An exclusive `fcntl.flock` (POSIX) or `msvcrt.locking` (Windows) is taken with a bounded wait (default 5 s, then 503 `store_busy`). It serializes the idempotency check and version commit for a collection.
- **Idempotency.** Under the lock, the server writes an *intent* `{key-hash, command-hash, target object/version}` first, then the version. Reads only look at version files, so an intent without its version is invisible. A retry with the same key and command completes the same target. The same key with a different command → 409 `idempotency_key_reused`. A completed replay is checked **before** expected-version validation (spec s5.2).
- **Integrity.** Each envelope stores `digest = sha256(canonical_json(record))`. Canonical JSON is UTF-8, sorted keys, `(",", ":")` separators, no ASCII escaping (`dev-b-canonical-json-sha256/1`). Reads recompute it and validate the model plus cross-field relationships (IDs, mapping and blob hash/size). On mismatch they withhold all dependent content (409 `integrity_failure`). A digest is an integrity identity, **not** a signature: someone who can rewrite both the record and its digest is outside this local adapter's threat model.
- **Durability.** POSIX: file `fsync`, link, then directory `fsync`. Windows: there is no directory-fsync equivalent, so the store **refuses writes** (503 `store_unavailable`, reason `platform_durability_unsupported`) unless `STRONGSTART_DEV_B_STORE_ALLOW_REDUCED_DURABILITY=true` is set. With that flag the reduced guarantee (file flush + no-clobber create, no directory flush) is reported in availability. Other platforms are rejected. The same policy now applies to the existing funding `LocalCaptureStore` (portability fix, spec s6).
- **Production.** Every new repository factory returns an **unconfigured** adapter when `environment=production`. There is no memory or fixture fallback.
- **Bounds** (spec s10):
  - 20 versions per definition, case or profile, then 413 `history_limit`; nothing is pruned;
  - list pages default 20, max 100;
  - directory scans capped at 2,000 entries, with `incomplete=true` beyond that;
  - envelopes ≤ 4 MiB; ≤ 100 questions; ≤ 20 predicates and ≤ 40 anchors per case version.

### 3. Saved definition identity

- A save **re-runs** the existing bounded intake on the exact source, compares the input SHA-256 with the preview hash (409 `input_changed`) and stores the exact input bytes as its own blob. Saved versions never depend on a B1 blob still existing (BND-27).
- `definition_id` is server-generated. `question_set_id = qs-<definition_id>-v<N>`, unique per revision and parsed strictly on read. Published question IDs are `<definition_id>:<original_id>`, or `<definition_id>:h<sha256(original)[:24]>` when that would exceed 128 characters. Within a lineage, the same unique original ID keeps its published ID. Every question's `question_version` equals the definition version, which advances all questions conservatively on any revision. Added and removed original IDs are listed explicitly; nothing is matched by text or position.
- Publication requires a shared `QuestionSet` projection. Without an opportunity identity (from the source's own declaration or a selected funding case), save returns 422 `publication_blocked`. A declared-vs-selected context disagreement returns 409 `context_conflict` and nothing is stored. Staff must resolve it; it is never overwritten.

### 4. Funding cases and review

- Case versions are immutable. **Review** is a separate create-once record bound to `(case_id, version, digest)`. A version is *reviewed* only if such a record exists. Any edit creates a new, unreviewed version, and old versions and reviews remain readable. There is no client `reviewed` Boolean.
- Funder, stream, cycle and stage are staff-entered labels. Their IDs are derived by the server, e.g. `cyc-<sha256(case_id, label)[:16]>`: a different label gives a different identity, and IDs are never the title itself.
- Evidence anchors are resolved server-side through `CapturedDocumentReader`: hash-verified bytes, an exact code-point quote match and the source/version IDs from the stored record.
- Rule kinds come from a fixed server registry (deadline, project window, amount range, geography, organization type, activity, invitation). There are no expressions, regex or code.
- Change observations linked to a case put the case into `requires_re_review` when the outcome is changed, partial, failed or not comparable for any capture it anchors. Readiness is computed at read time from immutable records, so nothing is rewritten.

### 5. Evaluations

Rules are pure functions in `features/funding/rules.py`. Each returns a B evaluation and a shared `ValidationResult` (`met→pass`, `not_met→fail`, `unknown`/at-cutoff`→needs_review`, `not_applicable→not_applicable`), ready for A3's runner when it exists.

Staff scenario inputs are labelled `staff_asserted` or `simulated`. The report separates `scenario_outcome` from `reliance_status`, which is always `not_confirmed` in this bundle because no A `EvidenceProvider` fact mapping exists. The shared `RequirementSet` projection keeps every condition `unknown`.

## Impact and coordination

- **New B-owned contract modules:**
  - `strongstart_contracts.application_publication` (automation);
  - `strongstart_contracts.funding_review` (funding cases, evaluations, profiles, runs, observations);
  - an additive capture-catalog section in `discovery.py`.
- Shared `QuestionSet`, `Opportunity`, `RequirementSet`, `DateKnowledge`, `ValidationResult` and `ErrorEnvelope` are unchanged.
- **C** consumes `ApplicationDefinitionReader` via `strongstart_api.features.automation.public.get_application_definition_reader`. **A** can register the pure rules later. There are no migrations and no A/C file edits.
- New settings: `STRONGSTART_DEV_B_STORE_DIR` and `STRONGSTART_DEV_B_STORE_ALLOW_REDUCED_DURABILITY` (Dev B coordinates `.env.example`).

## Validation and rollback

Validated by the BND-* tests listed in the bundle handoff. To roll back, revert the bundle commits and delete `.local-data/dev-b-store`; there are no migrations. A later shared repository can replace the local adapters behind the readers without changing feature logic.

## Update 2026-11-08: atomic funding-case binding at publication (PR #12 review follow-up)

The owner asked that the bound funding case's current-version check be atomic with definition publication, not an unprotected check immediately before the write. That supersedes the earlier "small window" limitation recorded in the bundle handoff.

- **Boundary.** `FundingCaseVersionPin` (`strongstart_contracts.funding_review`), implemented by the funding case repository and exposed only through `strongstart_api.features.funding.public.build_funding_case_version_pin`.
  - `pinned(org, case_id, version, digest)` takes the **same cross-process lock that case commits take** (`VersionCollection.locked()`, `fcntl`/`msvcrt`, bounded wait).
  - It re-checks that `version` is current with exactly `digest`, and raises `FundingCaseVersionChanged` otherwise.
  - Automation commits the definition **inside** that block (`automation/context.py::publication_guard`), so no case revision can commit between the check and the write, from any thread or process.
  - The earlier check in `resolve_publication_context` remains only as a fast, friendly failure.
- **Lock order.** Always cases → definitions. Case writers take only the cases lock, and definitions without a case take only the definitions lock, so there is no reverse ordering. Code holding a collection's lock must not commit to that same collection.
- **Idempotent replay first.** `DefinitionRepository.replay()` runs before intake, the hash check and context validation. A command whose publication already committed returns that exact version (200, `replayed: true`), even after the bound case changed. A *new* command against the stale version gets 409 `context_changed`.
- **Failure outcome.** A changed or deleted case, or a digest mismatch, under the pin gives 409 `context_changed` / 404 `context_not_found` / 409 `integrity_failure`, and nothing is published. If the wait times out, the result is 503 `store_busy`.
- **Tradeoff.** A case writer may wait while a definition commit holds the pin; the commit is short and local. Unreferenced content-addressed input blobs are never written on a rejected pin, because the save runs inside the block.
- **Validation.** `tests/automation/test_case_binding_atomicity.py` (BND-26a..e):
  - **26a:** publication is paused after context resolution, a revision commits, then publication resumes → 409 and no definition.
  - **26b/26c:** a competing revision (thread / spawned process) is observed attempting the case lock and being refused, via a lock-observer hook. It has not acquired the lock while the pin is held; after release it acquires the lock and commits.
  - **26d:** replay after a case change returns 200 with the same version.
  - **26e:** stale digest → conflict.
  - **Mutation checks:** guard disabled → 26a/b fail; pin lock disabled → 26b/c fail.
- **Test instrumentation.** `dev_b_store.core.set_lock_observer(observer)` reports `blocked` (first failed non-blocking attempt) and `acquired_after_wait` per process. It is a no-op unless set, and it never changes locking. It replaced an earlier sleep- and `Queue.empty()`-based version of 26b/c, which could not prove contention.
