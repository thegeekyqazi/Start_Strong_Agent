// Find Funding page. Owner: B1. B1-DISC-001 rev 1.0.
// Captured content is rendered only as escaped text (React text nodes); never as HTML.
import { useEffect, useState, type FormEvent } from 'react'
import type {
  CaptureContent,
  CapturedDocument,
  FundingAvailability,
  SearchCandidate,
  SearchRequest,
  SearchResult,
} from '@strongstart/contracts'
import { describeError, httpFundingClient, type FundingClient } from './client'
import { IntakeReferences, SavedCaptures } from './library'
import { FundingCases } from './cases'

type Phase<T> =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string; captureId?: string }
  | { kind: 'done'; data: T }

const AUTHORITY_LABEL: Record<string, string> = {
  unreviewed: 'Source authority: unreviewed',
  confirmed_official: 'Source authority: confirmed official (configured seed/review)',
  other: 'Source authority: other',
}

function ModeBadge({ mode }: { mode: string }) {
  const fixture = mode === 'fixture'
  return (
    <span className={`badge ${fixture ? 'badge-planned' : 'badge-ok'}`}>
      {fixture ? 'FIXTURE (synthetic)' : `Mode: ${mode}`}
    </span>
  )
}

function Availability({ data }: { data: FundingAvailability }) {
  return (
    <section aria-labelledby="funding-availability">
      <h3 id="funding-availability">Availability</h3>
      <p>
        {data.authenticated
          ? `Signed in${data.identity_is_fixture ? ' (LOCAL FIXTURE identity)' : ''}.`
          : 'Not signed in: search and capture will be denied.'}
      </p>
      <ul className="checks">
        {data.providers.map((p) => (
          <li key={p.operation}>
            <strong>{p.operation}</strong>: {p.provider} - {p.status.replace('_', ' ')}{' '}
            <ModeBadge mode={p.mode} /> {p.detail}
          </li>
        ))}
      </ul>
      <p className="hint">
        Limits: up to {data.limits.max_results} results, one provider request per operation, no
        automatic retries.
      </p>
    </section>
  )
}

function Candidate({
  c,
  onCapture,
  busy,
}: {
  c: SearchCandidate
  onCapture: (c: SearchCandidate) => void
  busy: boolean
}) {
  return (
    <li className="candidate">
      <h4>{c.title}</h4>
      <p className="url">{c.original_url}</p>
      <p>
        <em>Provider excerpt (unverified):</em> {c.provider_excerpt}
      </p>
      <ul className="facts">
        <li>{AUTHORITY_LABEL[c.authority]}</li>
        <li>Eligibility: unassessed</li>
        <li>Cycle status: unknown</li>
        <li>Deadline: unknown</li>
        <li>
          Matched public terms: {c.matched_terms.length ? c.matched_terms.join(', ') : 'none'}
        </li>
        {c.provider_relevance && (
          <li>Provider relevance score: {c.provider_relevance} (ranking signal only)</li>
        )}
        {c.provider_date_hint && (
          <li>Provider date estimate: {c.provider_date_hint} (not a deadline)</li>
        )}
        {c.duplicates && c.duplicates.length > 0 && (
          <li>Collapsed duplicates: {c.duplicates.map((d) => d.original_url).join(', ')}</li>
        )}
        {c.possible_duplicate_of && <li>Possible duplicate of {c.possible_duplicate_of}</li>}
      </ul>
      <button type="button" disabled={!c.capture_allowed || busy} onClick={() => onCapture(c)}>
        Capture this page
      </button>
      {!c.capture_allowed && <span className="hint"> {c.capture_block_reason}</span>}
    </li>
  )
}

function Results({
  result,
  onCapture,
  busy,
}: {
  result: SearchResult
  onCapture: (c: SearchCandidate) => void
  busy: boolean
}) {
  const q = result.query
  return (
    <section aria-labelledby="funding-results">
      <h3 id="funding-results">Search results</h3>
      <p>
        Query <code>{q.query_text}</code> via {q.provider} <ModeBadge mode={q.mode} /> at{' '}
        {q.completed_at}. Fields used: {q.public_fields_used.join(', ')}.
      </p>
      <ul className="warnings">
        {result.warnings.map((w) => (
          <li key={w}>{w}</li>
        ))}
      </ul>
      {result.candidates.length === 0 ? (
        <p role="status">No results.</p>
      ) : (
        <ol className="candidates">
          {result.candidates.map((c) => (
            <Candidate key={c.candidate_id} c={c} onCapture={onCapture} busy={busy} />
          ))}
        </ol>
      )}
      <p>Duplicates collapsed: {result.duplicates_collapsed}</p>
      {result.omitted.length > 0 && (
        <details>
          <summary>Omitted results ({result.omitted.length})</summary>
          <ul>
            {result.omitted.map((o) => (
              <li key={`${o.provider_rank}`}>
                #{o.provider_rank} {o.original_url ?? '(no URL)'}: {o.reason}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}

export function CapturePanel({ doc, client }: { doc: CapturedDocument; client: FundingClient }) {
  const [content, setContent] = useState<Phase<CaptureContent>>({ kind: 'idle' })
  const [copied, setCopied] = useState(false)
  const reference = JSON.stringify(doc, null, 2)
  const load = async (artifactId: string) => {
    setContent({ kind: 'loading' })
    const r = await client.content(doc.capture_id, artifactId)
    setContent(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
  }
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(reference)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }
  return (
    <section aria-labelledby="funding-capture">
      <h3 id="funding-capture">Captured source</h3>
      <p>
        <span className={`badge ${doc.coverage === 'complete' ? 'badge-ok' : 'badge-unavailable'}`}>
          Coverage: {doc.coverage}
        </span>{' '}
        <ModeBadge mode={doc.provider_mode} />
      </p>
      <dl className="meta">
        <dt>Capture ID</dt>
        <dd>{doc.capture_id}</dd>
        <dt>Source / version</dt>
        <dd>
          {doc.source_reference.source_id} / {doc.source_reference.source_version_id}
        </dd>
        <dt>Requested URL</dt>
        <dd>{doc.requested_url}</dd>
        <dt>Final URL</dt>
        <dd>{doc.final_url ?? 'unknown'}</dd>
        <dt>Captured at (capture time only; not a deadline or publication date)</dt>
        <dd>{doc.captured_at}</dd>
        <dt>Provider</dt>
        <dd>{doc.provider}</dd>
        <dt>Authority</dt>
        <dd>{AUTHORITY_LABEL[doc.authority_review]}</dd>
        <dt>B2 can import</dt>
        <dd>
          {doc.supported_import_representations.length
            ? doc.supported_import_representations.join(', ')
            : 'none (no HTML representation stored)'}
        </dd>
      </dl>
      <h4>Stored representations</h4>
      <table>
        <thead>
          <tr>
            <th scope="col">Representation</th>
            <th scope="col">Bytes</th>
            <th scope="col">SHA-256</th>
            <th scope="col">View</th>
          </tr>
        </thead>
        <tbody>
          {doc.artifacts.map((a) => (
            <tr key={a.artifact_id}>
              <td>{a.representation}</td>
              <td>{a.size_bytes}</td>
              <td>
                <code>{a.sha256}</code>
              </td>
              <td>
                <button type="button" onClick={() => load(a.artifact_id)}>
                  Show {a.representation} as text
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ul className="warnings">
        {doc.warnings.map((w) => (
          <li key={w}>{w}</li>
        ))}
      </ul>
      {content.kind === 'loading' && <p role="status">Loading content...</p>}
      {content.kind === 'error' && <p role="alert">{content.message}</p>}
      {content.kind === 'done' && (
        <figure>
          <figcaption>
            {content.data.artifact.representation} (integrity verified, shown as inert text)
          </figcaption>
          <pre className="evidence" data-testid="capture-content">
            {content.data.text}
          </pre>
        </figure>
      )}
      <IntakeReferences doc={doc} />
      <h4>Full capture reference (JSON)</h4>
      <button type="button" onClick={copy}>
        Copy full capture reference (JSON)
      </button>{' '}
      <a
        download={`${doc.capture_id}.json`}
        href={`data:application/json;charset=utf-8,${encodeURIComponent(reference)}`}
      >
        Download capture reference (JSON)
      </a>
      {copied && <span role="status"> Copied.</span>}
    </section>
  )
}

export function FundingPage({ client = httpFundingClient }: { client?: FundingClient }) {
  const [avail, setAvail] = useState<Phase<FundingAvailability>>({ kind: 'loading' })
  const [search, setSearch] = useState<Phase<SearchResult>>({ kind: 'idle' })
  const [capture, setCapture] = useState<Phase<CapturedDocument>>({ kind: 'idle' })
  const [interests, setInterests] = useState('early learning')
  const [geography, setGeography] = useState('')
  const [programContext, setProgramContext] = useState('')
  const [manualUrl, setManualUrl] = useState('')

  useEffect(() => {
    let active = true
    client.availability().then((r) => {
      if (!active) return
      setAvail(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
    })
    return () => {
      active = false
    }
  }, [client])

  const runSearch = async (e: FormEvent) => {
    e.preventDefault()
    setSearch({ kind: 'loading' })
    const terms = interests
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)
    const r = await client.search({
      profile: {
        interests: terms as SearchRequest['profile']['interests'],
        geography: geography.trim() || null,
        program_context: programContext.trim() || null,
      },
    })
    setSearch(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
  }

  const runCapture = async (url: string, c?: SearchCandidate) => {
    setCapture({ kind: 'loading' })
    const r = await client.capture({
      url,
      candidate_id: c?.candidate_id ?? null,
      search_id: search.kind === 'done' ? search.data.search_id : null,
    })
    if (r.ok) {
      setCapture({ kind: 'done', data: r.data })
      return
    }
    const details = r.error?.details as Record<string, unknown> | undefined
    const captureId = typeof details?.capture_id === 'string' ? details.capture_id : undefined
    setCapture({ kind: 'error', message: describeError(r), captureId })
  }

  return (
    <section aria-labelledby="feature-heading">
      <h2 id="feature-heading">Find Funding</h2>
      <p className="hint">
        Search public sources for funding leads and capture a selected page as evidence. Results are
        leads only: eligibility, cycle status and deadlines are not assessed here.
      </p>
      {avail.kind === 'loading' && <p role="status">Checking availability...</p>}
      {avail.kind === 'error' && <p role="alert">{avail.message}</p>}
      {avail.kind === 'done' && <Availability data={avail.data} />}

      <form onSubmit={runSearch} aria-labelledby="funding-search">
        <h3 id="funding-search">Search (public terms only)</h3>
        <label htmlFor="funding-interests">Funding interests (comma separated, up to 5)</label>
        <input
          id="funding-interests"
          value={interests}
          onChange={(e) => setInterests(e.target.value)}
        />
        <label htmlFor="funding-geography">Geography (optional)</label>
        <input
          id="funding-geography"
          value={geography}
          onChange={(e) => setGeography(e.target.value)}
        />
        <label htmlFor="funding-program">Program context (optional)</label>
        <input
          id="funding-program"
          value={programContext}
          onChange={(e) => setProgramContext(e.target.value)}
        />
        <button type="submit" disabled={search.kind === 'loading'}>
          Search
        </button>
      </form>
      {search.kind === 'loading' && <p role="status">Searching...</p>}
      {search.kind === 'error' && <p role="alert">{search.message}</p>}
      {search.kind === 'done' && (
        <Results
          result={search.data}
          busy={capture.kind === 'loading'}
          onCapture={(c) => runCapture(c.normalized_url, c)}
        />
      )}

      <form
        aria-labelledby="funding-manual"
        onSubmit={(e) => {
          e.preventDefault()
          if (manualUrl.trim()) runCapture(manualUrl.trim())
        }}
      >
        <h3 id="funding-manual">Capture a public page by URL</h3>
        <label htmlFor="funding-url">Public http(s) URL</label>
        <input
          id="funding-url"
          type="url"
          value={manualUrl}
          onChange={(e) => setManualUrl(e.target.value)}
        />
        <button type="submit" disabled={capture.kind === 'loading'}>
          Capture
        </button>
      </form>
      {capture.kind === 'loading' && <p role="status">Capturing...</p>}
      {capture.kind === 'error' && (
        <div role="alert">
          <p>{capture.message}</p>
          {capture.captureId && <p>Recorded capture ID: {capture.captureId}</p>}
        </div>
      )}
      {capture.kind === 'done' && <CapturePanel doc={capture.data} client={client} />}

      <SavedCaptures
        client={client}
        renderCapture={(doc) => <CapturePanel doc={doc} client={client} />}
      />

      <FundingCases client={client} />
    </section>
  )
}
