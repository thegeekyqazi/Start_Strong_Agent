# C2: Request to Dev B2 for a server-side question-set read port

- Author/lane: Dev C agent (Claude Code, claude-opus-5-5)
- Intended consumers: Dev B2 (producer of `AutomationHandoffExport` / `QuestionSet`); project owner
- UTC timestamp: 2026-11-08
- Status: proposed (request only). C has **not** modified any B-owned file and will not
- Task spec: `docs/specs/C2-draft-claims.md` (s8 seam table; s12 #6)
- Engineering: v1.1 s20.3 ("QuestionSet/FormMap, Dev B. C displays real imported questions"; "No consumer imports another feature's private tables or internal functions"), s20.7 G1 ("real B questions render with limits/conflicts")

## Why C cannot consume B2's questions yet

C needs B2's imported questions on the **server**. The draft and check routes look questions up by ID and version for the caller's organization; they never trust question data sent by a browser.

Today B2's `POST /api/automation/export-definition` builds an `AutomationHandoffExport` on request (`persisted: false`). There is no organization-scoped way for C's server code to read an imported question set by ID afterwards:

| Option | Why C rejects it |
| --- | --- |
| Import B2's `run_intake` / `build_export` | s20.3 forbids importing another feature's internal functions |
| Accept the export JSON from the browser | A client could submit forged questions or provenance labels as "funder questions" |
| Call B2's HTTP route from inside the same API process | Couples to B2's request pipeline and identity handling; not a contract |

## What C observed (read-only)

C read B2's public contract and called the public route once in an in-memory test client, with no writes. The export for fixture `rep-portal-definition-v1` contains:
- a shared `QuestionSet` with 9 questions (`rp-*`);
- limits with unknown conventions and an unknown unit;
- `required: null` items;
- an `unresolved` list.

C's C2 rules consume the shared `Question` type directly, so **no contract change is needed for the data itself**. Only a read path is missing.

## Request (shape is B2's choice)

An in-process, organization-scoped read port, modelled on B1's `CapturedDocumentReader`, for example:

```python
class ApplicationDefinitionReader(Protocol):
    is_fixture: bool
    def get_question_set(self, organization_id: str, question_set_id: str) -> QuestionSet: ...
    def get_unresolved(self, organization_id: str, question_set_id: str) -> list[UnresolvedItem]: ...
```

Requirements C relies on:
1. **Organization scope.** The organization comes from the server identity; unknown and other-org IDs fail identically.
2. **Stable versions.** `question_id` and `question_version` stay stable for a stored import; a re-import gets new versions.
3. **Fixture label.** `is_fixture` is set for fixture imports.
4. **Unchanged semantics.** Limits, conflicts and unknowns keep their current meaning, with nothing resolved on C's behalf.

A persisted export store, or a `GET` route by export ID, would also work, as long as it is organization-scoped. The DB migration for persistence would go through Dev A's sequencing.

## C behaviour until then

C2 keeps the `demo-bundle@1` fixture questions (owner decision 2026-11-08). When the port exists, C adds a workspace source behind its existing `WorkspaceSource` protocol and runs consumer contract tests against both the fixture and the real producer (s20.3).

## Acknowledgments

None yet. Please reply in the C2 PR thread with the planned port name/version, or with an alternative.
