# INT-001 functional UI contract for Sawaab

UI/UX owner: Sawaab. Baseline b543454; INT-001 revision 1.1.

Before component edits: add an isolated client handoff adapter carrying only
question_set_id, published question_id and server-issued approval_id. Review offers
“Use in Automation” only for current approved versions on saved B question sets.
Automation consumes these IDs into its existing selection form, previews exact saved
rendered text/hashes and retains the explicit execution button. No answer text,
selectors or authority flags in URL/storage; all authority is resolved by the server.

Extend live availability to stale/dependency-unavailable with a prepare-new-plan next
action. Preserve existing request generations, double-click guard, same-key retries,
read-only refresh recovery, labels/accessibility and existing layout/styles.
No UI/UX branch is integrated by this task. Final paths/props/tests follow at M4.
