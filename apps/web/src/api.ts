import type { CapabilityReport, LivenessReport, ReadinessReport } from '@strongstart/contracts'

// Public, non-secret base URL. Empty means same origin (the Vite dev proxy forwards /api, /health).
const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export type ApiState =
  | { kind: 'loading' }
  | { kind: 'unreachable'; detail: string }
  | {
      kind: 'reachable'
      live: LivenessReport
      ready: ReadinessReport
      capabilities: CapabilityReport | null
    }

async function getJson<T>(path: string): Promise<{ status: number; body: T }> {
  const res = await fetch(`${BASE}${path}`, { headers: { Accept: 'application/json' } })
  return { status: res.status, body: (await res.json()) as T }
}

export async function loadApiState(): Promise<ApiState> {
  try {
    const live = await getJson<LivenessReport>('/health/live')
    if (live.status !== 200) return { kind: 'unreachable', detail: `liveness HTTP ${live.status}` }
    const ready = await getJson<ReadinessReport>('/health/ready')
    const caps = await getJson<CapabilityReport>('/api/capabilities')
    return {
      kind: 'reachable',
      live: live.body,
      ready: ready.body,
      capabilities: caps.status === 200 ? caps.body : null,
    }
  } catch (err) {
    return { kind: 'unreachable', detail: err instanceof Error ? err.message : 'request failed' }
  }
}
