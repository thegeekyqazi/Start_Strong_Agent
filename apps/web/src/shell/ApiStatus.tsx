import type { ApiState } from '../api'

export function ApiStatus({ state }: { state: ApiState }) {
  if (state.kind === 'loading') return <p role="status">Checking API...</p>
  if (state.kind === 'unreachable') {
    return (
      <p role="status" className="badge badge-unavailable">
        API unreachable ({state.detail})
      </p>
    )
  }
  const ready = state.ready.status === 'ready'
  return (
    <div role="status" className="status-row">
      <span className="badge badge-ok">API alive</span>
      <span className={`badge ${ready ? 'badge-ok' : 'badge-unavailable'}`}>
        {ready ? 'Database ready' : 'Not ready'}
      </span>
      {!ready && (
        <ul className="checks">
          {state.ready.checks.map((c) => (
            <li key={c.name}>
              {c.name}: {c.ok ? 'ok' : 'failed'} ({c.detail})
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
