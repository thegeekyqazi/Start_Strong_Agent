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
