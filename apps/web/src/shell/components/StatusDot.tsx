// Answer status indicator (engineering s15; lane plan s6.2). Owner: C (shared shell).
// Text label + shape glyph, never colour alone. Full s15 answer-state set (C3).
export type AnswerStatus =
  'draft' | 'checking' | 'needs_attention' | 'ready_for_review' | 'approved' | 'stale' | 'rejected'

const LABEL: Record<AnswerStatus, string> = {
  draft: 'Draft – not reviewed',
  checking: 'Checking…',
  needs_attention: 'Needs attention',
  ready_for_review: 'Ready for review – not approved',
  rejected: 'Rejected by reviewer',
  approved: 'Approved (this exact version)',
  stale: 'Out of date – approval no longer applies',
}
const GLYPH: Record<AnswerStatus, string> = {
  draft: '○',
  checking: '◌',
  needs_attention: '△',
  ready_for_review: '◇',
  rejected: '✕',
  approved: '✓',
  stale: '⊘',
}

export function StatusDot({ status }: { status: AnswerStatus }) {
  return (
    <span className={`status status-${status}`}>
      <span aria-hidden="true">{GLYPH[status]} </span>
      {LABEL[status]}
    </span>
  )
}
