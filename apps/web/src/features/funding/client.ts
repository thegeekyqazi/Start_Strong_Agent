// Find Funding API client (owner: B1). Types are generated from the Python contracts.
import type {
  CaptureCatalogPage,
  EvaluateCommand,
  EvaluationList,
  EvaluationReport,
  FundingCaseCommand,
  FundingCaseEnvelope,
  FundingCaseList,
  ReviewCommand,
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
  listCaptures(cursor?: string | null): Promise<ApiResult<CaptureCatalogPage>>
  listCases(): Promise<ApiResult<FundingCaseList>>
  getCase(caseId: string, version?: number): Promise<ApiResult<FundingCaseEnvelope>>
  saveCase(body: FundingCaseCommand, caseId?: string): Promise<ApiResult<FundingCaseEnvelope>>
  reviewCase(
    caseId: string,
    version: number,
    body: ReviewCommand,
  ): Promise<ApiResult<FundingCaseEnvelope>>
  evaluateCase(caseId: string, body: EvaluateCommand): Promise<ApiResult<EvaluationReport>>
  listEvaluations(caseId: string): Promise<ApiResult<EvaluationList>>
}

const enc = encodeURIComponent

export const httpFundingClient: FundingClient = {
  availability: () => call('/api/funding/availability'),
  search: (body) => call('/api/funding/search', { method: 'POST', body: JSON.stringify(body) }),
  capture: (body) => call('/api/funding/captures', { method: 'POST', body: JSON.stringify(body) }),
  getCapture: (id) => call(`/api/funding/captures/${enc(id)}`),
  content: (id, artifactId) =>
    call(`/api/funding/captures/${enc(id)}/artifacts/${enc(artifactId)}/content`),
  listCases: () => call('/api/funding/cases'),
  getCase: (id, version) =>
    call(`/api/funding/cases/${enc(id)}${version ? `/versions/${version}` : ''}`),
  saveCase: (body, caseId) =>
    call(caseId ? `/api/funding/cases/${enc(caseId)}/revisions` : '/api/funding/cases', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  reviewCase: (id, version, body) =>
    call(`/api/funding/cases/${enc(id)}/versions/${version}/review`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  evaluateCase: (id, body) =>
    call(`/api/funding/cases/${enc(id)}/evaluations`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  listEvaluations: (id) => call(`/api/funding/cases/${enc(id)}/evaluations`),
  listCaptures: (cursor) => call(`/api/funding/captures${cursor ? `?cursor=${enc(cursor)}` : ''}`),
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
    case 'case_not_found':
      return 'Funding case not found or not accessible.'
    case 'anchor_mismatch':
      return 'The quoted passage does not exactly match the stored text at that position. Nothing was saved.'
    case 'anchor_source_changed':
      return 'The stored source differs from the one you quoted from. Reload it and select again.'
    case 'anchor_too_large':
      return 'Select a narrower passage (the quote is too long).'
    case 'version_conflict':
      return 'Someone saved a newer version first. Reload the case and revise that version.'
    case 'stale_snapshot':
      return 'The case changed since you opened it; reload before reviewing.'
    case 'review_scope_mismatch':
      return 'A review must name exactly every requirement in this version.'
    case 'already_reviewed':
      return 'This exact version is already reviewed.'
    case 'not_current_version':
      return 'Only the current case version can be reviewed.'
    case 'idempotency_key_reused':
      return 'This request was already used for different content.'
    case 'too_large':
      return `Too large: ${result.error?.message ?? ''}`
    case 'history_limit':
      return 'This item reached its version-history limit (20).'
    case 'integrity_failure':
      return 'Stored content failed its integrity check and was withheld.'
    case 'provider_error':
      return `Provider error: ${result.error?.message ?? ''}`
    default:
      if (result.status === 422) return 'The request was rejected as invalid.'
      return result.error?.message ?? `Request failed (HTTP ${result.status}).`
  }
}
