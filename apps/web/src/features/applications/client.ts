// Applications API client (owner: C; C1 spec s6). Types are generated from Python contracts.
import type {
  AnswerPlan,
  ApplicationWorkspace,
  CheckReport,
  CheckRequest,
  DraftProposal,
  DraftRequest,
  ErrorEnvelope,
  PlanRequest,
} from '@strongstart/contracts'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export type ApiResult<T> =
  { ok: true; data: T } | { ok: false; status: number; error: ErrorEnvelope | null }

export async function call<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
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

export interface ApplicationsClient {
  workspace(questionSetId?: string | null): Promise<ApiResult<ApplicationWorkspace>>
  draft(questionId: string, body: DraftRequest): Promise<ApiResult<DraftProposal>>
  check(questionId: string, body: CheckRequest): Promise<ApiResult<CheckReport>>
  plan(body: PlanRequest): Promise<ApiResult<AnswerPlan>>
}

export const httpApplicationsClient: ApplicationsClient = {
  workspace: (questionSetId) =>
    call(
      questionSetId
        ? `/api/applications/workspace?question_set_id=${encodeURIComponent(questionSetId)}`
        : '/api/applications/workspace',
    ),
  draft: (questionId, body) =>
    call(`/api/applications/questions/${encodeURIComponent(questionId)}/draft`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  check: (questionId, body) =>
    call(`/api/applications/questions/${encodeURIComponent(questionId)}/check`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  plan: (body) => call('/api/applications/plan', { method: 'POST', body: JSON.stringify(body) }),
}

type Failure = { status: number; error: ErrorEnvelope | null }

const reasonOf = (f: Failure) =>
  (f.error?.details as Record<string, unknown> | undefined)?.reason as string | undefined

/** Plain-language copy for workspace loading failures (lane plan s6.3). */
export function describeWorkspaceError(f: Failure): string {
  if (f.status === 0) return 'The server could not be reached. Check your connection and reload.'
  if (f.status === 401)
    return "You're not signed in, so this application can't be shown. Ask your workspace administrator for access."
  const reason = reasonOf(f)
  if (reason === 'unknown_question_set')
    return "That saved question set wasn't found for your organization. We did not switch to other questions."
  if (reason === 'question_set_integrity_failure')
    return 'That saved question set failed its integrity check, so it was not used. We did not switch to other questions.'
  if (f.status === 503)
    return "The application workspace isn't set up on this server yet. Nothing is wrong with your work."
  if (f.status === 404) return "We couldn't find this application. Reload the page."
  return 'Something went wrong loading the application. Reload the page.'
}

/** Plain-language copy for draft failures. The editor is never changed on failure. */
export function describeDraftError(f: Failure): string {
  const unchanged = ' Your text is unchanged.'
  if (f.status === 0) return 'The server could not be reached.' + unchanged
  if (f.status === 401) return "You're not signed in, so a draft can't be requested." + unchanged
  if (f.status === 503)
    return (
      "Drafting isn't available: no writing assistant is set up. We don't switch to another assistant automatically." +
      unchanged
    )
  if (f.status === 409)
    return 'This question changed since you opened it. Reload to see the current wording, then request a draft again.'
  if (f.status === 404) return "We couldn't find this question or its evidence. Reload the page."
  if (f.status === 403)
    return "This evidence can't be sent to the configured assistant under the data-handling rules. Nothing was sent."
  if (f.status === 429) return 'The assistant is busy. Wait a minute and try again.' + unchanged
  if (f.status === 504)
    return 'The assistant took too long, so we stopped waiting.' + unchanged + ' Try again.'
  if (reasonOf(f) === 'model_output_rejected')
    return (
      "The assistant's reply didn't pass our safety and format checks, so we discarded it." +
      unchanged +
      ' You can try again or write the answer yourself.'
    )
  return 'The assistant service refused the request. Contact your administrator.' + unchanged
}
