// Automation API client (owner: B2). Typed with generated contract types; no hand-written DTOs.
import type {
  ApplicationIntakeResult,
  AutomationAvailability,
  AutomationHandoffExport,
  DefinitionList,
  ErrorEnvelope,
  ExportDefinitionRequest,
  FormInspectionResult,
  ImportApplicationRequest,
  InspectFixtureRequest,
  PublishedApplicationVersion,
  SaveDefinitionRequest,
  SaveDefinitionResult,
} from '@strongstart/contracts'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''
const PREFIX = `${BASE}/api/automation`

export type ApiResult<T> =
  { ok: true; data: T } | { ok: false; status: number; error: ErrorEnvelope | null }

export type IntakeSource = ImportApplicationRequest['source']

async function call<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  let res: Response
  try {
    res = await fetch(`${PREFIX}${path}`, {
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
  return { ok: false, status: res.status, error: (body as ErrorEnvelope | null) ?? null }
}

export function getAvailability(): Promise<ApiResult<AutomationAvailability>> {
  return call('/availability')
}

export function importDefinition(
  source: IntakeSource,
): Promise<ApiResult<ApplicationIntakeResult>> {
  const body: ImportApplicationRequest = { source }
  return call('/intake', { method: 'POST', body: JSON.stringify(body) })
}

export function inspectFixture(
  req: InspectFixtureRequest,
): Promise<ApiResult<FormInspectionResult>> {
  return call('/inspect-fixture', { method: 'POST', body: JSON.stringify(req) })
}

export function exportDefinition(
  req: ExportDefinitionRequest,
): Promise<ApiResult<AutomationHandoffExport>> {
  return call('/export-definition', { method: 'POST', body: JSON.stringify(req) })
}

export function saveDefinition(
  req: SaveDefinitionRequest,
): Promise<ApiResult<SaveDefinitionResult>> {
  return call('/definitions', { method: 'POST', body: JSON.stringify(req) })
}

export function listDefinitions(cursor?: string | null): Promise<ApiResult<DefinitionList>> {
  const q = cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''
  return call(`/definitions${q}`)
}

export function getDefinition(
  definitionId: string,
): Promise<ApiResult<PublishedApplicationVersion>> {
  return call(`/definitions/${encodeURIComponent(definitionId)}`)
}

export function getQuestionSet(
  questionSetId: string,
): Promise<ApiResult<PublishedApplicationVersion>> {
  return call(`/question-sets/${encodeURIComponent(questionSetId)}`)
}

export function newIdempotencyKey(): string {
  const random =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `ui-${random}`
}

export function portalUrl(fixtureId: string): string {
  return `${PREFIX}/fixtures/portal/${encodeURIComponent(fixtureId)}`
}

const REASON_TEXT: Record<string, string> = {
  malformed_request: 'The request was not in the expected shape.',
  malformed_definition: 'The definition is not valid JSON or does not match the supported format.',
  duplicate_id: 'Two items share an ID. Nothing was renumbered; fix the source and re-import.',
  unsupported_input: 'This input type is not supported.',
  input_too_large: 'The input is larger than the allowed limit.',
  source_unavailable: 'The captured source could not be read (missing, not yours, or no producer).',
  hash_mismatch: 'The stored capture bytes do not match their recorded hash. Nothing was imported.',
  browser_unavailable: 'The browser is not available, so no inspection ran.',
  fixture_not_allowed: 'That fixture is not registered or fixture mode is off.',
  timeout: 'The inspection ran out of time; no result was produced.',
  unknown_form_version: 'No stored form map exists for that version.',
  input_changed:
    'The source changed since this preview. Re-import before saving; nothing was saved.',
  publication_blocked:
    'This import cannot be published yet (no questions, or the opportunity is unknown). Nothing was saved.',
  version_conflict:
    'Someone saved a newer version first. Reload the saved definition and revise that version.',
  idempotency_key_reused: 'This save request was already used for different content.',
  too_many_questions: 'Saved definitions are limited to 100 questions.',
  history_limit: 'This definition reached its version-history limit (20).',
  integrity_failure: 'The stored definition failed its integrity check; content was withheld.',
  definition_not_found: 'Saved definition not found.',
  store_unavailable: 'No saved-definition store is available in this environment.',
  store_busy: 'The store is busy. Try again.',
  store_write_failed: 'The store could not finish writing. Nothing was committed.',
  context_unavailable: 'Funding-case context is not available.',
  context_incomplete:
    'The selected funding case does not establish funder, stream and cycle yet. Complete it first.',
  context_conflict:
    'The source declares a different opportunity/stream/cycle than the selected funding case. Held for review; nothing was saved.',
  context_changed:
    'The selected funding case has a newer version. Select the current version explicitly.',
  context_not_found: 'The selected funding case was not found.',
  ambiguous_question_identity: 'Question identities are ambiguous; nothing was saved.',
}

export function describeError(r: { status: number; error: ErrorEnvelope | null }): string {
  if (r.status === 0) return 'The API could not be reached.'
  if (r.status === 401) return 'Not signed in: no identity provider is configured.'
  const reason = r.error?.details?.reason
  const text = typeof reason === 'string' ? REASON_TEXT[reason] : undefined
  const base = text ?? r.error?.message ?? `Request failed (HTTP ${r.status}).`
  return typeof reason === 'string' ? `${base} [${reason}]` : base
}

// A lost/aborted response has uncertain effects; callers retain the same request key.
async function prefillCall<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  const abort = new AbortController()
  const timer = setTimeout(() => abort.abort(), 45_000)
  try {
    return await call<T>(path, { ...init, signal: abort.signal })
  } finally {
    clearTimeout(timer)
  }
}

export function preparePrefill(req: import('@strongstart/contracts').PreparePrefillPlanRequest) {
  return prefillCall<import('@strongstart/contracts').PrefillPlan>('/prefill-plans', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export function executePrefill(
  planId: string,
  req: import('@strongstart/contracts').ExecutePrefillRequest,
) {
  return prefillCall<import('@strongstart/contracts').ExecutePrefillResult>(
    `/prefill-plans/${encodeURIComponent(planId)}/execute`,
    { method: 'POST', body: JSON.stringify(req) },
  )
}

export function getPrefillPlan(planId: string) {
  return prefillCall<import('@strongstart/contracts').PrefillPlanView>(
    `/prefill-plans/${encodeURIComponent(planId)}`,
  )
}

export function getPrefillRun(runId: string) {
  return prefillCall<import('@strongstart/contracts').PrefillRunView>(
    `/prefill-runs/${encodeURIComponent(runId)}`,
  )
}
