import type {
  ActivePackState,
  ErrorEnvelope,
  EvidenceBundle,
  KnowledgeAvailability,
  KnowledgeRetrievalResult,
  KnowledgeSnapshot,
  PackActivationReport,
  PdfSourceImportResult,
  TextSourceImportResult,
} from '@strongstart/contracts'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export type KnowledgeApiResult<T> =
  { ok: true; data: T } | { ok: false; status: number; error: ErrorEnvelope | null }

async function call<T>(path: string, init?: RequestInit): Promise<KnowledgeApiResult<T>> {
  try {
    const response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...init?.headers },
    })
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
  importText(title: string, text: string): Promise<KnowledgeApiResult<TextSourceImportResult>>
  importPdf(
    title: string,
    contentBase64: string,
  ): Promise<KnowledgeApiResult<PdfSourceImportResult>>
  retrieve(query: string): Promise<KnowledgeApiResult<KnowledgeRetrievalResult>>
  activePack(applicationContext: string): Promise<KnowledgeApiResult<ActivePackState>>
  activatePack(
    applicationContext: string,
    packVersionId: string,
    expectedActivePackVersionId: string | null,
  ): Promise<KnowledgeApiResult<PackActivationReport>>
}

export const httpKnowledgeClient: KnowledgeClient = {
  availability: () => call('/api/knowledge/availability'),
  snapshot: () => call('/api/knowledge/snapshot'),
  evidence: (id) => call(`/api/knowledge/evidence/${encodeURIComponent(id)}`),
  importText: (title, text) =>
    call('/api/knowledge/sources/import-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, text }),
    }),
  importPdf: (title, contentBase64) =>
    call('/api/knowledge/sources/import-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content_base64: contentBase64 }),
    }),
  retrieve: (query) => call(`/api/knowledge/retrieve?query=${encodeURIComponent(query)}`),
  activePack: (context) =>
    call(`/api/knowledge/packs/contexts/${encodeURIComponent(context)}/active`),
  activatePack: (context, packVersionId, expectedActivePackVersionId) =>
    call(
      `/api/knowledge/packs/contexts/${encodeURIComponent(context)}/activate/${encodeURIComponent(packVersionId)}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          expected_active_pack_version_id: expectedActivePackVersionId,
        }),
      },
    ),
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
