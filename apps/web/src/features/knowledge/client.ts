import type {
  ErrorEnvelope,
  EvidenceBundle,
  KnowledgeAvailability,
  KnowledgeSnapshot,
} from '@strongstart/contracts'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export type KnowledgeApiResult<T> =
  { ok: true; data: T } | { ok: false; status: number; error: ErrorEnvelope | null }

async function call<T>(path: string): Promise<KnowledgeApiResult<T>> {
  try {
    const response = await fetch(`${BASE}${path}`, { headers: { Accept: 'application/json' } })
    const body: unknown = await response.json().catch(() => null)
    if (response.ok) return { ok: true, data: body as T }
    return {
      ok: false,
      status: response.status,
      error: body && typeof body === 'object' && 'code' in body ? (body as ErrorEnvelope) : null,
    }
  } catch {
    return { ok: false, status: 0, error: null }
  }
}

export interface KnowledgeClient {
  availability(): Promise<KnowledgeApiResult<KnowledgeAvailability>>
  snapshot(): Promise<KnowledgeApiResult<KnowledgeSnapshot>>
  evidence(packVersionId: string): Promise<KnowledgeApiResult<EvidenceBundle>>
}

export const httpKnowledgeClient: KnowledgeClient = {
  availability: () => call('/api/knowledge/availability'),
  snapshot: () => call('/api/knowledge/snapshot'),
  evidence: (id) => call(`/api/knowledge/evidence/${encodeURIComponent(id)}`),
}

export function describeKnowledgeError(result: {
  status: number
  error: ErrorEnvelope | null
}): string {
  if (result.status === 0) return 'The Knowledge API could not be reached.'
  if (result.error?.code === 'unauthenticated') return 'Not signed in: knowledge access is denied.'
  if (result.error?.details?.reason === 'integrity_failure') {
    return 'Stored source integrity verification failed. Content and dependent facts were withheld.'
  }
  if (result.error?.code === 'capability_unavailable') {
    return 'Knowledge storage is not configured.'
  }
  return result.error?.message ?? `Knowledge request failed (HTTP ${result.status}).`
}
