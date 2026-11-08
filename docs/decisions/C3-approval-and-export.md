# C3-approval-and-export: Fixture store until the C3 migration is sequenced, live staleness, export contract

- Author/developer: Dev C agent
- Date: 2026-11-08
- Status: developer-decision (working tree, **not committed**, per owner instruction)
- Decided/accepted by and evidence: owner approval of C3 and answers to spec s11 (2026-11-08); developer decisions below
- Engineering path/version/sections: v1.1, s8.1, s9.2, s13.2, s13.3, s15, s16, s18
- Feature spec path/revision: `docs/specs/C3-approval-and-export.md` rev 1.0 plus s12 notes
- PR / Issue: none (not committed)
- Supersedes / superseded by: none

## Decisions

1. **D1: Fixture-only persistence until A sequences the C3 answers/approvals migration.**
   - C3 runs on a labelled, process-local `InMemoryAnswerStore`, active only in fixture mode.
   - The draft migration is outside `migrations/`.
   - *Tradeoff:* data is lost on restart.
   - *Reversal:* a Postgres `AnswerStore` behind the same protocol once that migration exists.
2. **D2: Staleness is evaluated live, not stored.**
   - Every read and action recomputes the JOB-05 snapshot from current dependencies and checks for a newer version and applied ChangeSets.
   - Nothing is cached, so no change can be missed.
   - Stale events are still written to the audit log when an edit or ChangeSet causes them.
3. **D3: A fact digest stands in for the missing fact version.**
   - Bound facts enter the snapshot as `pack_version_id` plus a SHA-256 of the full fact record, so any value/unit/period/status/support change stales approvals.
   - Replace this when A ships the requested fact version.
4. **D4: Only the fixture identity approves.** In fixture mode only, it approves, labelled ("FIXTURE APPROVAL - NOT AUTHENTICATION"). All other identities get 403. Real reviewer roles depend on A's SEC-01 identity primitive.
5. **D5: Blocked exports return 200** with `blocked: true` and reasons, and produce no artifact. The event is audited as `export_blocked`.
6. **D6: Synchronous exports and reviewer calls**, as in C1 D1, because there is no JobStore.

## Impact and coordination

| Change | Owner | Status |
| --- | --- | --- |
| `services/api/pyproject.toml` adds `python-docx>=1.1` | shared | owner-approved |
| `uv.lock` regenerated (+`python-docx` 1.2.0, +`lxml` 6.1.3) | **Dev B** (lockfiles) | owner-approved; **B please acknowledge** |
| `tests/unit/test_api.py` | shared | C's `review` line only: `not_implemented` → `unavailable` |
| C3 answers/approvals migration (unnumbered draft `c3-migration-request/answers_and_approvals.py`; revision and down-revision assigned by Dev A) | **Dev A** | request only, not active |
| Real `ApprovedAnswerResolver` into shared `ports.py` | shared host | not wired; needs owner/B agreement |

## Validation and rollback

- **Validation:** `make check` exit 0 (454 pytest, 66 Vitest), `make smoke` exit 0, `make browser-smoke` 13 passed. Plus a Chromium run of save → approve → export → edit → stale.
- **Rollback:** discard the working-tree changes. Nothing is committed.
