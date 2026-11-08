// Automation API client (owner: B2). Typed with generated contract types; no hand-written DTOs.
import type {
  ApplicationIntakeResult,
  AutomationAvailability,
  AutomationHandoffExport,
  ErrorEnvelope,
  ExportDefinitionRequest,
  FormInspectionResult,
  ImportApplicationRequest,
  InspectFixtureRequest,
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
}

export function describeError(r: { status: number; error: ErrorEnvelope | null }): string {
  if (r.status === 0) return 'The API could not be reached.'
  if (r.status === 401) return 'Not signed in: no identity provider is configured.'
  const reason = r.error?.details?.reason
  const text = typeof reason === 'string' ? REASON_TEXT[reason] : undefined
  const base = text ?? r.error?.message ?? `Request failed (HTTP ${r.status}).`
  return typeof reason === 'string' ? `${base} [${reason}]` : base
}
