// Review API client (owner: C; C3 spec s7). Types are generated from Python contracts.
import type {
  AnswerHistory,
  AnswerVersion,
  AnswerVersionCreate,
  ApprovalDecisionRequest,
  ApprovalRecord,
  ExportRequest,
  ExportResult,
  ReviewerProposal,
  ReviewerProposalRequest,
  ReviewNote,
  ReviewNoteCreate,
} from '@strongstart/contracts'
import { call, type ApiResult } from '../applications/client'

export interface ReviewClient {
  history(questionId: string): Promise<ApiResult<AnswerHistory>>
  saveVersion(body: AnswerVersionCreate): Promise<ApiResult<AnswerVersion>>
  decide(body: ApprovalDecisionRequest): Promise<ApiResult<ApprovalRecord>>
  addNote(body: ReviewNoteCreate): Promise<ApiResult<ReviewNote>>
  propose(body: ReviewerProposalRequest): Promise<ApiResult<ReviewerProposal>>
  exportAnswers(body: ExportRequest): Promise<ApiResult<ExportResult>>
  downloadUrl(exportId: string, kind: 'docx' | 'audit'): string
}

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''
const enc = encodeURIComponent
const post = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

export const httpReviewClient: ReviewClient = {
  history: (id) => call(`/api/applications/answers/${enc(id)}`),
  saveVersion: (body) => call('/api/applications/answers/versions', post(body)),
  decide: (body) => call('/api/applications/answers/decisions', post(body)),
  addNote: (body) => call('/api/applications/answers/notes', post(body)),
  propose: (body) => call('/api/applications/answers/reviews', post(body)),
  exportAnswers: (body) => call('/api/applications/exports', post(body)),
  downloadUrl: (id, kind) => `${BASE}/api/applications/exports/${enc(id)}/${kind}`,
}

/** Plain-language copy for review/approval failures. */
export function describeReviewError(result: {
  status: number
  error: { details?: Record<string, unknown> } | null
}): string {
  const reason = result.error?.details?.reason as string | undefined
  if (result.status === 0) return 'The server could not be reached.'
  if (result.status === 401) return "You're not signed in."
  if (result.status === 403)
    return 'You can add notes, but you are not authorized to approve or reject.'
  if (result.status === 503)
    return "Saving and approval aren't set up on this server yet (no answer store)."
  if (result.status === 409)
    return reason === 'answer_version_conflict'
      ? 'Someone saved a newer version. Reload to see it before saving again.'
      : 'This version changed, was replaced or was already decided. Reload before deciding.'
  if (result.status === 422 && reason === 'review_items_not_acknowledged')
    return 'Read every "Needs your review" item and tick the confirmation before approving.'
  if (result.status === 422 && reason === 'blocking_findings')
    return 'This version has problems that block approval. Fix them and save a new version.'
  return 'The request was rejected. Reload and try again.'
}
