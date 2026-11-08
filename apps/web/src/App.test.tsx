import { render, screen } from '@testing-library/react'
import type { CapabilityReport } from '@strongstart/contracts'
import { afterEach, beforeEach, vi } from 'vitest'
import App from './App'
import type { ApiState } from './api'
import { FEATURES } from './features/registry'

function caps(fixture: boolean): CapabilityReport {
  return {
    schema_version: '1',
    environment: 'local',
    auth_mode: fixture ? 'fixture' : 'none',
    fixture_mode: fixture,
    capabilities: FEATURES.map((f) => ({
      feature: f.id,
      owner: f.owner,
      status: 'not_implemented',
      detail: 'planned',
    })),
  }
}

const reachable = (ready: boolean, fixture = false): ApiState => ({
  kind: 'reachable',
  live: { status: 'alive', service: 'strongstart-api' },
  ready: {
    status: ready ? 'ready' : 'not_ready',
    checks: [{ name: 'database', ok: ready, detail: ready ? 'connected' : 'OperationalError' }],
  },
  capabilities: caps(fixture),
})

describe('App shell', () => {
  beforeEach(() => {
    window.location.hash = '#/knowledge'
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              schema_version: '1',
              authenticated: false,
              identity_is_fixture: false,
              environment: 'test',
              storage: 'unconfigured',
              status: 'unavailable',
              detail: 'Database storage is not configured.',
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        ),
      ),
    )
  })

  afterEach(() => vi.unstubAllGlobals())

  it('registers every lane feature with its owner', async () => {
    render(<App load={async () => reachable(true)} />)
    for (const f of FEATURES) {
      expect(screen.getByRole('link', { name: f.label })).toBeInTheDocument()
    }
    expect(await screen.findByText('Database ready')).toBeInTheDocument()
    expect(screen.getAllByText('Coming later').length).toBeGreaterThanOrEqual(6)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows not-ready readiness truthfully', async () => {
    render(<App load={async () => reachable(false)} />)
    expect(await screen.findByText('Not ready')).toBeInTheDocument()
    expect(screen.getByText(/database: failed/)).toBeInTheDocument()
  })

  it('shows an unreachable API instead of pretending', async () => {
    render(<App load={async () => ({ kind: 'unreachable', detail: 'Failed to fetch' })} />)
    expect(await screen.findByText(/API unreachable/)).toBeInTheDocument()
    expect(screen.getAllByText('Status unknown')).toHaveLength(FEATURES.length)
  })

  it('labels fixture mode conspicuously', async () => {
    render(<App load={async () => reachable(true, true)} />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/LOCAL FIXTURE MODE/)
  })

  it('guides users through the existing grant workflow without replacing feature routes', async () => {
    window.location.hash = '#/knowledge'
    render(<App load={() => new Promise<ApiState>(() => undefined)} />)

    expect(
      screen.getByRole('region', { name: 'How to move through Strong Start' }),
    ).toHaveTextContent('Step 3 of 5')
    expect(
      screen.getByRole('link', { name: 'Go to Intake & Prefill in workflow' }),
    ).toHaveAttribute('href', '#/automation')
    expect(screen.getByRole('link', { name: 'Go to Applications in workflow' })).toHaveAttribute(
      'href',
      '#/applications',
    )
  })

  it('opens with a product landing page that links into the existing workspace', async () => {
    window.location.hash = ''
    render(<App load={() => new Promise<ApiState>(() => undefined)} />)

    expect(
      screen.getByRole('heading', { name: /Build stronger grants with evidence/ }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open the workspace' })).toHaveAttribute(
      'href',
      '#/funding',
    )
    expect(screen.queryByRole('navigation', { name: 'Features' })).not.toBeInTheDocument()
  })
})
