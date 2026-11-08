import { useEffect, useState } from 'react'
import { loadApiState, type ApiState } from './api'
import { FEATURES } from './features/registry'
import { ApiStatus } from './shell/ApiStatus'

const STATUS_LABEL: Record<string, string> = {
  available: 'Available',
  fixture_only: 'Fixture only',
  not_implemented: 'Planned - not implemented',
  unavailable: 'Unavailable',
}

function currentFeatureId(): string {
  const id = window.location.hash.replace(/^#\/?/, '')
  return FEATURES.some((f) => f.id === id) ? id : FEATURES[0].id
}

export default function App({ load = loadApiState }: { load?: () => Promise<ApiState> }) {
  const [api, setApi] = useState<ApiState>({ kind: 'loading' })
  const [featureId, setFeatureId] = useState(currentFeatureId)

  useEffect(() => {
    let active = true
    load().then((s) => active && setApi(s))
    const onHash = () => setFeatureId(currentFeatureId())
    window.addEventListener('hashchange', onHash)
    return () => {
      active = false
      window.removeEventListener('hashchange', onHash)
    }
  }, [load])

  const caps = api.kind === 'reachable' ? api.capabilities : null
  const statusOf = (id: string) => caps?.capabilities.find((c) => c.feature === id)?.status
  const feature = FEATURES.find((f) => f.id === featureId) ?? FEATURES[0]
  const Page = feature.Component

  return (
    <div className="shell">
      <header>
        <h1>Strong Start Agent</h1>
        <ApiStatus state={api} />
        {caps?.fixture_mode && (
          <p className="banner-fixture" role="alert">
            LOCAL FIXTURE MODE - synthetic demo identity, not authentication.
          </p>
        )}
      </header>
      <nav aria-label="Features">
        <ul>
          {FEATURES.map((f) => {
            const status = statusOf(f.id)
            return (
              <li key={f.id}>
                <a href={`#/${f.id}`} aria-current={f.id === feature.id ? 'page' : undefined}>
                  {f.label}
                </a>
                <span className="owner"> ({f.owner})</span>
                <span className="cap">{status ? STATUS_LABEL[status] : 'Status unknown'}</span>
              </li>
            )
          })}
        </ul>
      </nav>
      <main>
        <Page />
      </main>
    </div>
  )
}
