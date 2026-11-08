// Evidence fact card (engineering s4.1, s8.3, s18; lane plan s6.2). Owner: C (shared shell).
// Separate labelled signals: staff review, source verification, time suitability (quoted
// coverage notes only - nothing computed), provenance. Unknown values read "unknown".
// Everything is a React text node; locators are never rendered as links (SEC-07).
import type { Fact } from '@strongstart/contracts'
import { FACT_STATUS, PROVENANCE_LABEL, SOURCE_STATUS } from './labels'

const orUnknown = (v: string | null | undefined) =>
  v === null || v === undefined || v === '' ? 'unknown' : v

export function EvidenceCard({
  fact,
  coverageNotes = [],
}: {
  fact: Fact
  coverageNotes?: string[]
}) {
  const ref = fact.supporting_refs[0]
  const pub = ref.publication_date
  const headingId = `fact-${fact.fact_id}`
  return (
    <article className="evidence-card" aria-labelledby={headingId}>
      <h4 id={headingId}>{fact.metric_id}</h4>
      <p className="fact-value">
        {fact.value === null ? 'Value: unknown' : fact.value}{' '}
        {fact.unit === null ? '(Unit: unknown)' : fact.unit}
      </p>
      <dl>
        <dt>Scope</dt>
        <dd>{fact.scope}</dd>
        <dt>Population</dt>
        <dd>{orUnknown(fact.population)}</dd>
        <dt>Reporting period</dt>
        <dd>{orUnknown(fact.reporting_period)}</dd>
        <dt>Source</dt>
        <dd>
          {ref.source_id} (version {ref.source_version_id})
        </dd>
        <dt>Location</dt>
        <dd>{orUnknown(ref.locator)}</dd>
        <dt>Published</dt>
        <dd>
          {pub.status === 'known'
            ? orUnknown(pub.value)
            : pub.status === 'unknown'
              ? 'unknown'
              : 'not applicable'}
        </dd>
      </dl>
      <ul className="signals">
        <li>
          <span className="signal-name">Staff review:</span> {FACT_STATUS[fact.status]}
        </li>
        <li>
          <span className="signal-name">Evidence support:</span>{' '}
          {SOURCE_STATUS[ref.verification_status ?? 'unverified']}
        </li>
        {coverageNotes.length > 0 && (
          <li>
            <span className="signal-name">Time suitability:</span>{' '}
            {coverageNotes.map((n) => `“${n}”`).join(' ')}
          </li>
        )}
        <li className={fact.provenance.is_simulated ? 'signal-simulated' : undefined}>
          <span className="signal-name">Provenance:</span>{' '}
          {PROVENANCE_LABEL[fact.provenance.provenance_class] ?? fact.provenance.provenance_class}
        </li>
      </ul>
      {fact.provenance.note && (
        <details>
          <summary>About this data</summary>
          <p>{fact.provenance.note}</p>
        </details>
      )}
    </article>
  )
}
