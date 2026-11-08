// Skills API client (owner: C; C4-SKL-001 s10.1). Types are generated from Python contracts.
import type {
  CompiledPracticePackage,
  PracticeActivateRequest,
  PracticeCandidate,
  PracticeOverview,
  PracticePreview,
  PracticePreviewRequest,
  PracticeRelease,
  PracticeReviewRequest,
  PracticeSourceVersion,
} from '@strongstart/contracts'
import { call, type ApiResult } from '../applications/client'

export type FixtureSourceKey = 'demo' | 'conflict' | 'hostile'

export interface SkillsClient {
  overview(): Promise<ApiResult<PracticeOverview>>
  loadFixtureSource(key: FixtureSourceKey): Promise<ApiResult<PracticeSourceVersion>>
  approveAuthority(sourceVersionId: string): Promise<ApiResult<PracticeSourceVersion>>
  generate(sourceVersionId: string): Promise<ApiResult<PracticeCandidate>>
  screen(candidateId: string): Promise<ApiResult<PracticeCandidate>>
  review(candidateId: string, body: PracticeReviewRequest): Promise<ApiResult<PracticeCandidate>>
  activate(candidateId: string, body: PracticeActivateRequest): Promise<ApiResult<PracticeRelease>>
  revoke(releaseId: string, reason: string): Promise<ApiResult<PracticeRelease>>
  preview(body: PracticePreviewRequest): Promise<ApiResult<PracticePreview>>
  exportPackage(candidateId: string): Promise<ApiResult<CompiledPracticePackage>>
}

const enc = encodeURIComponent
const post = (body?: unknown): RequestInit => ({
  method: 'POST',
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const httpSkillsClient: SkillsClient = {
  overview: () => call('/api/skills'),
  loadFixtureSource: (key) => call(`/api/skills/fixture-sources/${enc(key)}`, post()),
  approveAuthority: (id) => call(`/api/skills/sources/${enc(id)}/authority`, post()),
  generate: (id) => call('/api/skills/candidates', post({ source_version_id: id })),
  screen: (id) => call(`/api/skills/candidates/${enc(id)}/screening`, post()),
  review: (id, body) => call(`/api/skills/candidates/${enc(id)}/review`, post(body)),
  activate: (id, body) => call(`/api/skills/candidates/${enc(id)}/activate`, post(body)),
  revoke: (id, reason) => call('/api/skills/releases/revoke', post({ release_id: id, reason })),
  preview: (body) => call('/api/skills/preview', post(body)),
  exportPackage: (id) => call(`/api/skills/candidates/${enc(id)}/package`),
}

const REASON: Record<string, string> = {
  source_authority_missing: 'Review this source as practice authority first.',
  source_not_current: 'A newer source version was published. Use the current one.',
  source_changed_during_generation: 'The source changed while generating. Generate again.',
  package_hash_mismatch: 'The package changed. Review the exact current fingerprint.',
  gates_not_passed: 'Hard gates have not passed, so this cannot be approved or activated.',
  source_support_not_confirmed: 'Confirm that every rule follows from its source excerpt.',
  review_items_not_acknowledged: 'Acknowledge every "Needs your review" item first.',
  review_missing_or_stale: 'An exact-fingerprint staff review of the current gates is required.',
  idempotency_key_reused: 'This activation request conflicts with an earlier one. Reload.',
  package_quarantined: 'This package is quarantined (a secret-like value) and cannot be exported.',
  practice_store_unavailable: 'Practice skills need the durable PostgreSQL store on this server.',
  not_authorized: 'Only authorized staff can do this.',
}

/** Plain-language copy for skills failures. */
export function describeSkillsError(result: {
  status: number
  error: { details?: Record<string, unknown> } | null
}): string {
  if (result.status === 0) return 'The server could not be reached.'
  if (result.status === 401) return "You're not signed in."
  const reason = result.error?.details?.reason as string | undefined
  const holds = result.error?.details?.holds as string[] | undefined
  const base = (reason && REASON[reason]) ?? `Request failed (HTTP ${result.status}).`
  return holds?.length ? `${base} Open holds: ${holds.join(', ')}.` : base
}
