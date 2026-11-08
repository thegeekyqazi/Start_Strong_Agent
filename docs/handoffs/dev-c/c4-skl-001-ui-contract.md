# C4-SKL-001 Skills page — UI contract for Sawaab

Recipient: Sawaab (UI/UX owner). Ack requested before restyling; no shared interface changed.

- Files: `apps/web/src/features/skills/{Page.tsx,client.ts}` only. No theme, router, font, token,
  global CSS or layout change; no new CSS classes. Uses `FindingRow`, `HashChip` and existing
  classes (`banner-fixture`, `badge badge-*`, `hint`, `meta`, `draft-actions`, `button-primary`,
  `button-secondary`, `stale-banner`, `findings`, `plain`).
- Data: `GET /api/skills` (`PracticeOverview`) plus the commands in `client.ts`; types are
  generated from `strongstart_contracts.skills`. The server decides every status, hold and
  gate; the page only renders them and enables buttons from server state.
- Must keep (behavioural, not stylistic): SYNTHETIC/FIXTURE labels; "working preview only —
  approval is not permitted"; hold reasons visible and activation disabled while held; exact
  fingerprints near approve/activate; all content rendered as text (no HTML/markdown rendering,
  no remote images); no approve/export/prefill shortcut from a preview.
- Free to change: layout of the five panels, headings, copy tone, ordering, table vs list,
  collapsing the package files and audit trail.
- Screenshots of the current state come from `scripts/c4_walkthrough.py`.
