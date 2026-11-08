import { useEffect, useState } from 'react'
import type { KnowledgeAvailability, KnowledgeSnapshot } from '@strongstart/contracts'
import { describeKnowledgeError, httpKnowledgeClient, type KnowledgeClient } from './client'

type State =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'done'; availability: KnowledgeAvailability; snapshot: KnowledgeSnapshot | null }

export function KnowledgePage({ client = httpKnowledgeClient }: { client?: KnowledgeClient }) {
  const [state, setState] = useState<State>({ kind: 'loading' })
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
      {snapshot && snapshot.source_versions.length === 0 && (
        <p role="status">No knowledge sources are available for this organization.</p>
      )}
      {snapshot && snapshot.source_versions.length > 0 && (
        <>
          <h3>Source versions</h3>
          <ul>
            {snapshot.source_versions.map((source) => (
              <li key={source.source_reference.source_version_id}>
                <strong>{source.title}</strong> — {source.media_type}, {source.size_bytes} bytes
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
