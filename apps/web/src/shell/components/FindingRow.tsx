// Finding / notice row (engineering s8.3, s9.1, s18; lane plan s6.2, s6.6 #1). Owner: C.
// Presentational shape until ValidationResult carries message/span/next-action fields.
// Text only; links are allowlisted to in-app paths, anything else is shown inert (SEC-07).
import type { ValidationResult } from '@strongstart/contracts'
import { isSafeHref } from './labels'

export type FindingOutcome = ValidationResult['outcome'] | 'notice'

export interface FindingRowProps {
  origin: 'check' | 'question_data'
  outcome: FindingOutcome
  message: string
  observedExpected?: string
  affectedText?: string
  nextAction?: string
  href?: string
  linkLabel?: string
}

const BADGE: Record<FindingOutcome, string> = {
  fail: 'Problem found',
  needs_review: 'Needs your review',
  pass: 'Passed this check only',
  not_applicable: 'Not applicable',
  notice: 'Note',
}

export function FindingRow(props: FindingRowProps) {
  const { origin, outcome, message, observedExpected, affectedText, nextAction, href } = props
  const linkLabel = props.linkLabel ?? 'Go to'
  return (
    <div className={`finding finding-${outcome}`} role="group" aria-label={BADGE[outcome]}>
      <span className={`badge finding-badge-${outcome}`}>{BADGE[outcome]}</span>{' '}
      <span>{message}</span>
      {origin === 'question_data' && (
        <span className="finding-origin"> From question data, not a validation check.</span>
      )}
      {observedExpected && <p className="finding-detail">{observedExpected}</p>}
      {affectedText && <blockquote className="finding-detail">{affectedText}</blockquote>}
      {nextAction && <p className="finding-detail">Next: {nextAction}</p>}
      {href &&
        (isSafeHref(href) ? (
          <a href={href}>{linkLabel}</a>
        ) : (
          <span className="finding-detail">
            {linkLabel}: {href} (link not opened)
          </span>
        ))}
    </div>
  )
}
