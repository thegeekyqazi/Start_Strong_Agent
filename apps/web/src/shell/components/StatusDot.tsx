// Answer status indicator (engineering s15; lane plan s6.2). Owner: C (shared shell).
// Text label + shape glyph, never colour alone. C3 extends this to the full s15 set.
export type AnswerStatus = 'draft' | 'needs_attention' | 'approved' | 'stale'

const LABEL: Record<AnswerStatus, string> = {
  draft: 'Draft – not reviewed',
  needs_attention: 'Needs attention',
  approved: 'Approved (this exact version)',
  stale: 'Out of date – approval no longer applies',
}
const GLYPH: Record<AnswerStatus, string> = {
  draft: '○',
  needs_attention: '△',
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
