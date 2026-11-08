# 0005: INT-001 engineering takeover and supported integration

- Status: accepted-maintainer (ownership/scope); developer-decision (implementation details below).
- Authority: project owner, 2026-11-08; INT-001 revision 1.1.
- Baseline: origin/main b543454255c45e9a079e3090337585b375fe34f0, merged #17.
- Branch: integration/int-001-approved-content-currentness, isolated worktree.
- Engineering v1.1 §§4, 5.3, 8.2–8.3, 9.2, 10.5, 10.7–10.8, 12.4,
  13.2–13.3, 14–16, 18–21; APP-04/06, AUT-01/02/03, PKG-01/02/03,
  JOB-02/03/05, SEC-01/08/09/10/13/14. AUT-04 remains checklist-only.

## Adopted ownership and baseline

The project owner now owns engineering across former A/B/C lanes, migration sequencing
and producer/consumer integration. One coding agent completes M0–M4 sequentially;
no separate lane acknowledgment is needed. A/B/C remain contract/module labels.
Sawaab owns UI/UX. Former lane restrictions are superseded only for this assigned scope.

C save/approve is real code over an app-local fixture store; B publication and Chromium
prefill are real code over the local development repository/representative portal.
The requested content reader is currently unconfigured. A4 is real PostgreSQL,
with generic registrations but no guarded browser registration. No durable C migration
is installed. Preserve all prior historical handoff caveats.

## Adopted contracts and ordering

C publishes its reader/factory using the existing ApprovedPrefillContent envelope;
metadata and content share one usable-approval predicate. Capture deep copies and an
org revision under the C lock, release before workspace/SQL, then recheck revision.
Epoch belongs to the store, not the dependency-provider instance.

A4 publishes a supported in-process facade and exact server-built binding. Use a
conservative pack-root projection plus verifiable policy/source dependencies. Original
C dependencies remain hash-bound. Unknown coverage refuses managed authority.
Lock order for guarded registration: organization row (same as activation), context,
target. No C/B locks or browser operations under SQL locks. Register plan before
publication, actual grant after single-use claim and before mutation. Orphan SQL
registrations cannot authorize execution. Reads never register or reset stale targets.

New hash-bound fields use a new plan/grant format. Old pending records require a new
plan; historical receipts remain readable/replayable without renewed execution.
The exact field layout and validation evidence will be recorded at later milestones.

## Scope and next increment

TigerData is mandatory: retain SQLAlchemy/PostgreSQL/Alembic interfaces. This task does
not install C3 draft migrations or claim process-local state is durable or multiworker.
Next: TigerData durability plus real A-evidence/workspace integration. Production
fixture identity/prefill remains disabled. No redesign, upload, submit, sign or deployment.

Project display name becomes Strong Start Agent. Owner also authorized GitHub repository
rename to strong-start-agent; publication will use the returned canonical repository URL.
Rollback is by reverting this task branch through review; never reset shared history.

## M2 adopted layout and migration

`knowledge.public.KnowledgeCurrentness` exposes active evidence, explicit projection,
guarded register and read-only registration checks. `ApprovedKnowledgeBinding` carries
organization/context, exact pack version/active revision, original C dependency digest,
canonical A4 projection and its digest. `KnowledgeRegistration` adds actual target kind,
ID and revision. C freezes this optional server-built binding when saving; unmanaged
evidence never receives one. Legacy fact digests are compared to authoritative bundle
facts and projected using their actual integer fact versions, never parsed as versions.
Unknown requirement-set coverage is held because C currently has no independent live
requirement-set verifier. Question/rule checks remain with C/B.

Migration `0008_browser_bindings` follows `0007_pack_replacement`, adding four nullable
binding columns to existing targets. No migration is needed merely for the new
`browser_plan` string kind; columns persist exact context/revision/projection metadata
for guarded consumers. Generic registrations remain compatible except that they cannot
reset a guarded target. This prevents bypassing the new stale-target lifecycle.
C3's draft migration remains uninstalled. Rollback: stop consumers, revert task code,
then Alembic downgrade 0008 to 0007 only after preserving any guarded-target metadata.

Registration uses organization, context and target row locks in that order. The mutation
audit removes only the three registration `FOR UPDATE` locks, preserving activation and
all assertions, then restores exact bytes in `finally`. The expected failure is
`stale_registration: replacement missed the new target`; a removed guard must not be
reported as covered merely because a Future remained unfinished.

M2 evidence: 25 PostgreSQL smoke tests passed (13 new A4 facade cases plus 12
existing DB tests). The lock-removal mutation failed at the stale-registration assertion;
restored test passed. Restored PackService SHA-256:
`ac9aceaa5d5e415082097545479df91bdd6f63f86db39d69a29c2ed06a0b586a`.
The script is reproducible with the configured local PostgreSQL URL; it does not reset DB
state. Only task-owned synthetic rows are cleaned. Migration advanced the existing local
PostgreSQL from 0007 to 0008, no data reset. No TigerData environment was contacted.

## M3 format/currentness compatibility

Plans now use `b2-approved-prefill/2`; grants explicitly use `b2-prefill-grant/2`.
Response decoders retain v1 historical reads with bounded defaults; execution refuses
old pending plans/grants with a prepare-new-plan action. No stored grant is rehashed or
upgraded. Immutable plan actions retain their saved C bindings, and the plan stores the
full original dependency union plus aggregate A4 registration. Grant data/hash predicts
its own exact target revision; that target must actually register after the claim before
entry. Both targets are checked at every action boundary and completion. Legacy explicit
test currentness remains a harness only; an object implementing a protocol does not earn
an A4 label. Managed plans require the real supported facade and successful registration.

GETs compute usability separately without changing plan bytes, registration or expiry.
Completed receipt replay precedes new currentness decisions and never launches a browser.
The harness now constructs valid C-format dependency snapshot hashes to meet B's stricter
independent checks. Missing-reader coverage explicitly injects an unconfigured producer;
the normal runtime now uses C's real empty store and refuses unknown approvals as held.

## M4 verification refinements

The public C factory also detects replacement of its app-scoped store during an existing
request. Keeping a reference to the old store must not allow hooks to continue after the
active store is replaced. Both the captured org revision and active-store identity are
checked at the final reader boundary. Live reviewed gates are recomputed as well as
snapshot/render hashes, including deliberately inconsistent unknown-fact fixtures.
Unavailable dependency checks now retain `unavailable` receipt labels separately from stale.

Browser-specific A4 registration rejects noncanonical fact/policy version strings;
generic historical APIs retain their established conventions. The final lock mutation
again produced the exact stale-registration failure, restored the source and passed:
`e0574503c6d2e4698c9c51cacf1202e70f62308ad12575d52764bc34815f44ea`.
The earlier M2 source hash remains historical evidence, not the final source hash.

Two opt-in rehearsal scripts use a bounded test workspace over actual A4 evidence and
normal C save/approve/content implementations; they are never wired into the runtime.
The real HTTP/SQL/Chromium rehearsal passed locally, including actual plan/grant rows,
pack activation, zero-write refusal and unchanged completed replay. Its owned API was
stopped and synthetic SQL rows/temporary B files cleaned. No TigerData/live provider
verification, production enablement or Sawaab UI/UX branch merge is claimed.
