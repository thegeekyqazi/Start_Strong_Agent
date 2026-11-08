import { type FormEvent, useEffect, useState } from 'react'
import type {
  ActivePackState,
  KnowledgeAvailability,
  KnowledgeRetrievalResult,
  KnowledgeSnapshot,
} from '@strongstart/contracts'
import { describeKnowledgeError, httpKnowledgeClient, type KnowledgeClient } from './client'

type State =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'done'; availability: KnowledgeAvailability; snapshot: KnowledgeSnapshot | null }

export function KnowledgePage({ client = httpKnowledgeClient }: { client?: KnowledgeClient }) {
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [action, setAction] = useState<string | null>(null)
  const [results, setResults] = useState<KnowledgeRetrievalResult | null>(null)
  const [activePack, setActivePack] = useState<ActivePackState | null>(null)
  const applicationContext = 'demo-application'
  useEffect(() => {
    let active = true
    const load = async () => {
      const availability = await client.availability()
      if (!active) return
      if (!availability.ok) {
        setState({ kind: 'error', message: describeKnowledgeError(availability) })
        return
      }
      if (!availability.data.authenticated || availability.data.status === 'unavailable') {
        setState({ kind: 'done', availability: availability.data, snapshot: null })
        return
      }
      const snapshot = await client.snapshot()
      if (!active) return
      setState(
        snapshot.ok
          ? { kind: 'done', availability: availability.data, snapshot: snapshot.data }
          : { kind: 'error', message: describeKnowledgeError(snapshot) },
      )
      const activePackResult = await client.activePack(applicationContext)
      if (active && activePackResult.ok) setActivePack(activePackResult.data)
    }
    void load()
    return () => {
      active = false
    }
  }, [client])

  if (state.kind === 'loading') return <p role="status">Loading knowledge availability…</p>
  if (state.kind === 'error') return <p role="alert">{state.message}</p>
  const { availability, snapshot } = state
  const facts = snapshot?.evidence_bundles.flatMap((bundle) => bundle.facts) ?? []
  const importText = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const result = await client.importText(String(form.get('title')), String(form.get('text')))
    setAction(
      result.ok
        ? `Imported source version ${result.data.source_version_id}.`
        : describeKnowledgeError(result),
    )
  }
  const importPdf = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const file = form.get('pdf')
    if (!(file instanceof File) || file.size === 0) return setAction('Choose a PDF file.')
    const encoded = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onerror = () => reject(new Error('read failed'))
      reader.onload = () => resolve(String(reader.result).split(',', 2)[1] ?? '')
      reader.readAsDataURL(file)
    }).catch(() => '')
    if (!encoded) return setAction('The PDF could not be read.')
    const result = await client.importPdf(String(form.get('title')), encoded)
    setAction(
      result.ok
        ? `Imported ${result.data.processed_pages} PDF page(s).`
        : describeKnowledgeError(result),
    )
  }
  const retrieve = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const query = String(new FormData(event.currentTarget).get('query'))
    const result = await client.retrieve(query)
    if (result.ok) {
      setResults(result.data)
      setAction(null)
    } else setAction(describeKnowledgeError(result))
  }
  const activate = async (packVersionId: string) => {
    const result = await client.activatePack(
      applicationContext,
      packVersionId,
      activePack?.pack_version_id ?? null,
    )
    if (result.ok) {
      setActivePack(result.data.active)
      setAction(
        result.data.idempotent
          ? `Pack ${packVersionId} is already active.`
          : `Activated ${packVersionId}; ${result.data.invalidated.length} dependent item(s) became stale.`,
      )
    } else setAction(describeKnowledgeError(result))
  }
  return (
    <section aria-labelledby="knowledge-heading">
      <h2 id="knowledge-heading">Knowledge and evidence</h2>
      <p>
        Storage: {availability.storage}. Status: {availability.status.replace('_', ' ')}.
      </p>
      {availability.identity_is_fixture && (
        <p className="badge badge-planned">FIXTURE: synthetic data, not partner evidence</p>
      )}
      {!availability.authenticated && <p>Not signed in: knowledge access is denied.</p>}
      {availability.status === 'unavailable' && <p>{availability.detail}</p>}
      {snapshot && (
        <div className="knowledge-tools">
          <section aria-labelledby="pack-heading">
            <h3 id="pack-heading">Evidence pack</h3>
            <p>
              Application context: <code>{applicationContext}</code>. Active version:{' '}
              <strong>{activePack?.pack_version_id ?? 'none'}</strong>.
            </p>
            {snapshot.evidence_bundles.map((bundle) => (
              <p key={bundle.pack_version_id}>
                {bundle.pack_version_id}{' '}
                <button
                  type="button"
                  disabled={activePack?.pack_version_id === bundle.pack_version_id}
                  onClick={() => void activate(bundle.pack_version_id)}
                >
                  {activePack?.pack_version_id === bundle.pack_version_id
                    ? 'Active'
                    : 'Activate version'}
                </button>
              </p>
            ))}
          </section>
          <section aria-labelledby="text-import-heading">
            <h3 id="text-import-heading">Import plain text</h3>
            <form onSubmit={(event) => void importText(event)}>
              <label>
                Title <input name="title" required maxLength={300} />
              </label>
              <label>
                Evidence text <textarea name="text" required />
              </label>
              <button type="submit">Import text</button>
            </form>
          </section>
          <section aria-labelledby="pdf-import-heading">
            <h3 id="pdf-import-heading">Import text PDF</h3>
            <p className="hint">Scanned or encrypted PDFs require review and are not accepted.</p>
            <form onSubmit={(event) => void importPdf(event)}>
              <label>
                Title <input name="title" required maxLength={300} />
              </label>
              <label>
                PDF <input name="pdf" type="file" accept="application/pdf,.pdf" required />
              </label>
              <button type="submit">Import PDF</button>
            </form>
          </section>
          <section aria-labelledby="retrieval-heading">
            <h3 id="retrieval-heading">Search evidence passages</h3>
            <form onSubmit={(event) => void retrieve(event)}>
              <label>
                Search terms <input name="query" required minLength={2} maxLength={200} />
              </label>
              <button type="submit">Search</button>
            </form>
            {results && results.hits.length === 0 && <p>No authorized passages matched.</p>}
            {results?.hits.map((hit) => (
              <article className="candidate" key={hit.passage.passage_id}>
                <h4>{hit.title}</h4>
                <p>{hit.passage.exact_text}</p>
                <p className="hint">
                  {hit.passage.locator} · lexical score {hit.score}
                </p>
              </article>
            ))}
          </section>
        </div>
      )}
      {action && <p role="status">{action}</p>}
      {snapshot && snapshot.source_versions.length === 0 && (
        <p role="status">No knowledge sources are available for this organization.</p>
      )}
      {snapshot && snapshot.source_versions.length > 0 && (
        <>
          <h3>Source versions</h3>
          <ul>
            {snapshot.source_versions.map((source) => (
              <li key={source.source_reference.source_version_id}>
                <strong>{source.title}</strong>, {source.media_type}, {source.size_bytes} bytes
                <br />
                Version: {source.source_reference.source_version_id}
                <br />
                SHA-256: <code>{source.source_reference.content_hash}</code>
              </li>
            ))}
          </ul>
          <h3>Typed facts</h3>
          {facts.map((fact) => (
            <article key={fact.fact_id} className="candidate">
              <h4>{fact.metric_id}</h4>
              <p>
                Exact value: <strong>{fact.value ?? 'unknown'}</strong>{' '}
                {fact.unit ?? '(unit unknown)'}
              </p>
              <p>Scope: {fact.scope}</p>
              <p>Population: {fact.population ?? 'unknown'}</p>
              <p>Reporting period: {fact.reporting_period ?? 'unknown'}</p>
              <p>Status: {fact.status.replace('_', ' ')}</p>
            </article>
          ))}
        </>
      )}
    </section>
  )
}
