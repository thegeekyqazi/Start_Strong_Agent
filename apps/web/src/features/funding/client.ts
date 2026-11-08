// Find Funding API client (owner: B1). Types are generated from the Python contracts.
import type {
  CaptureContent,
  CapturedDocument,
  CaptureRequest,
  ErrorEnvelope,
  FundingAvailability,
  SearchRequest,
  SearchResult,
} from '@strongstart/contracts'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export type ApiResult<T> =
  { ok: true; data: T } | { ok: false; status: number; error: ErrorEnvelope | null }

async function call<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    })
  } catch {
    return { ok: false, status: 0, error: null }
  }
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    body = null
  }
  if (res.ok) return { ok: true, data: body as T }
  const error = body && typeof body === 'object' && 'code' in body ? (body as ErrorEnvelope) : null
  return { ok: false, status: res.status, error }
}

export interface FundingClient {
  availability(): Promise<ApiResult<FundingAvailability>>
  search(body: SearchRequest): Promise<ApiResult<SearchResult>>
  capture(body: CaptureRequest): Promise<ApiResult<CapturedDocument>>
  getCapture(captureId: string): Promise<ApiResult<CapturedDocument>>
  content(captureId: string, artifactId: string): Promise<ApiResult<CaptureContent>>
}

const enc = encodeURIComponent

export const httpFundingClient: FundingClient = {
  availability: () => call('/api/funding/availability'),
  search: (body) => call('/api/funding/search', { method: 'POST', body: JSON.stringify(body) }),
  capture: (body) => call('/api/funding/captures', { method: 'POST', body: JSON.stringify(body) }),
  getCapture: (id) => call(`/api/funding/captures/${enc(id)}`),
  content: (id, artifactId) =>
    call(`/api/funding/captures/${enc(id)}/artifacts/${enc(artifactId)}/content`),
}

/** Plain-language explanation for each failure; distinct states per B1-DISC-001 s3. */
export function describeError(result: { status: number; error: ErrorEnvelope | null }): string {
  if (result.status === 0) return 'The API could not be reached.'
  const reason = (result.error?.details as Record<string, unknown> | undefined)?.reason
  const code = result.error?.code
  if (code === 'unauthenticated') return 'Not signed in: search and capture are denied.'
  switch (reason) {
    case 'invalid_input':
      return `Invalid input: ${result.error?.message ?? ''}`
    case 'provider_unavailable':
      return `Provider unavailable (missing credentials). ${result.error?.message ?? ''}`
    case 'store_unavailable':
      return 'No capture store is available in this environment.'
    case 'provider_auth_rejected':
      return 'The provider rejected the configured credentials.'
    case 'rate_limited':
      return 'Provider rate limit reached. Nothing was retried automatically.'
    case 'quota_exceeded':
      return 'Provider quota or plan limit reached. Nothing was retried automatically.'
    case 'timeout':
    case 'outcome_unknown':
      return 'The provider timed out. The outcome (and any charge) is unknown; nothing was retried.'
    case 'unsafe_destination':
      return `Destination denied: ${result.error?.message ?? ''}`
    case 'unsupported_content':
      return `Unsupported content: ${result.error?.message ?? ''}`
    case 'source_http_error':
      return `The source page returned an error: ${result.error?.message ?? ''}`
    case 'extraction_empty':
      return 'Empty extraction: the provider returned no usable content. It was recorded for inspection but is not evidence.'
    case 'capture_not_found':
      return 'Capture not found or not accessible.'
    case 'integrity_failure':
      return 'Stored content failed its integrity check and was withheld.'
    case 'provider_error':
      return `Provider error: ${result.error?.message ?? ''}`
    default:
      if (result.status === 422) return 'The request was rejected as invalid.'
      return result.error?.message ?? `Request failed (HTTP ${result.status}).`
  }
}
