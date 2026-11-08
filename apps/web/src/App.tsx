import { useEffect, useState } from 'react'
import { loadApiState, type ApiState } from './api'
import { FEATURES } from './features/registry'
import { LandingPage } from './LandingPage'
import { ApiStatus } from './shell/ApiStatus'

const STATUS_LABEL: Record<string, string> = {
  available: 'Available',
  fixture_only: 'Fixture only',
  not_implemented: 'Coming later',
  unavailable: 'Unavailable',
}

const JOURNEY_IDS = ['funding', 'automation', 'knowledge', 'applications', 'review'] as const

const JOURNEY_OUTPUT: Record<(typeof JOURNEY_IDS)[number], string> = {
  funding: 'Captured opportunity',
  automation: 'Structured requirements',
  knowledge: 'Source-linked facts',
  applications: 'Checked draft',
  review: 'Approved version',
}

function currentFeatureId(): string {
  const id = window.location.hash.replace(/^#\/?/, '')
  if (!id || id === 'home') return 'home'
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
  const isLanding = featureId === 'home'
  const feature = FEATURES.find((f) => f.id === featureId) ?? FEATURES[0]
  const journey = JOURNEY_IDS.map((id) => FEATURES.find((item) => item.id === id)).filter(
    (item): item is (typeof FEATURES)[number] => Boolean(item),
  )
  const journeyIndex = Math.max(
    0,
    journey.findIndex((item) => item.id === feature.id),
  )
  const isJourneyFeature = journey.some((item) => item.id === feature.id)
  const navigationFeatures = [
    ...journey,
    ...FEATURES.filter((item) => !journey.some((journeyItem) => journeyItem.id === item.id)),
  ]
  const Page = feature.Component

  return (
    <div className={isLanding ? 'shell landing-shell' : 'shell'}>
      <a className="skip-link" href="#main-content">
        Skip to workspace
      </a>
      <header className="app-header">
        <div className="app-header-main">
          <h1 className="wordmark">
            <a href="#/home">Strong Start</a>
            <small>Grant workspace</small>
          </h1>
          {isLanding ? (
            <a className="header-workspace-link" href="#/funding">
              Open workspace
            </a>
          ) : (
            <ApiStatus state={api} />
          )}
        </div>
        {caps?.fixture_mode && (
          <p className="banner-fixture" role="alert">
            LOCAL FIXTURE MODE - synthetic demo identity, not authentication.
          </p>
        )}
      </header>
      {!isLanding && (
        <nav className="feature-nav" aria-label="Features">
          <p className="feature-nav-title">Workspace</p>
          <ul>
            {navigationFeatures.map((f) => {
              const status = statusOf(f.id)
              return (
                <li key={f.id}>
                  <a
                    href={`#/${f.id}`}
                    aria-label={f.label}
                    aria-current={f.id === feature.id ? 'page' : undefined}
                  >
                    <span className="feature-link-label">{f.label}</span>
                    <span className="feature-link-summary">{f.summary}</span>
                  </a>
                  <span className="feature-meta">
                    <span className="cap">{status ? STATUS_LABEL[status] : 'Status unknown'}</span>
                  </span>
                </li>
              )
            })}
          </ul>
        </nav>
      )}
      <main id="main-content" tabIndex={-1}>
        {isLanding ? (
          <LandingPage />
        ) : (
          <>
            {isJourneyFeature && (
              <section className="journey-console" aria-labelledby="journey-title">
                <div className="journey-overview">
                  <h2 id="journey-title" className="journey-title">
                    How to move through Strong Start
                  </h2>
                  <p className="journey-guide">
                    Work left to right, or open any step when you need it.
                  </p>
                  <p className="journey-count">
                    Step {journeyIndex + 1} of {journey.length}
                  </p>
                </div>
                <ol className="journey-steps" aria-label="Grant workflow stages">
                  {journey.map((item, index) => (
                    <li key={item.id} className={index === journeyIndex ? 'is-current' : ''}>
                      <a
                        href={`#/${item.id}`}
                        aria-label={`Go to ${item.label} in workflow`}
                        aria-current={index === journeyIndex ? 'step' : undefined}
                      >
                        <span className="journey-number">{index + 1}</span>
                        <span className="journey-step-copy">
                          <span>{item.label}</span>
                          <small>{JOURNEY_OUTPUT[item.id as (typeof JOURNEY_IDS)[number]]}</small>
                        </span>
                      </a>
                    </li>
                  ))}
                </ol>
              </section>
            )}
            <Page />
          </>
        )}
      </main>
    </div>
  )
}
