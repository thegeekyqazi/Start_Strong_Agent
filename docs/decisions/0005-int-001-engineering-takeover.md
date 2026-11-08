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
