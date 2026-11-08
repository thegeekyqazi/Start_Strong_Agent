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

## Implemented M3 handoff

- `apps/web/src/features/automation/approvedHandoff.ts`: ephemeral module state,
  `selectApprovedAnswer(questionSetId, questionId, approvalId)`,
  `readApprovedSelection()`, `clearApprovedSelection()`. IDs only; per-question selections
  accumulate within one question set. No answer text, selectors or authority flags in URL
  or storage. Hash navigation remains `#/automation`.
- `features/review/Page.tsx`: adds one button for the matching current approved latest
  version on the loaded saved B question set. Existing review presentation is retained.
- `features/automation/prefill.tsx`: imports handoff IDs, loads exact server definition,
  verifies the IDs belong, fills existing approval inputs and retains explicit prepare/
  execute buttons. Request generation checks isolate late handoff/currentness responses.
  Adds accurate C/A4 labels and a read-only source check with stale next action.
- `features/automation/api.ts`: simple changed-pack/unavailable/old-format explanations.
- Shared shell heading/document title/README now say **Strong Start Agent**, at the
  owner's explicit request. Repository renamed to `thegeekyqazi/strong-start-agent`.
  Existing package namespaces remain compatible. No styles or layout redesign.

Evidence: 100 Vitest tests passed, including ID handoff, late selection response and stale
read-only refresh; normal runtime API/UI/Chromium joined test passed with two C-approved
text fields and refresh receipt recovery. Sawaab's separate UI/UX branch has **not** been
merged or represented as integrated. Adapt these functional hooks when merging his design;
preserve explicit authority checks and stable accessible controls.
