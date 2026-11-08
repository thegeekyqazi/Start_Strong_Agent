// Dev B saved question sets for C2b (owner: C). The browser only ever sends an ID; C's
// server resolves the exact version with the server organization (C2 spec rev 1.3 s13).
import type { DefinitionList } from '@strongstart/contracts'
import { call, type ApiResult } from './client'

export interface QuestionSetClient {
  /** Dev B's public list route (organization-scoped on the server). */
  list(): Promise<ApiResult<DefinitionList>>
}

export const httpQuestionSetClient: QuestionSetClient = {
  list: () => call('/api/automation/definitions?limit=50'),
}

const KEY = 'strongstart.c.questionSetId'

/** Remembered selection for this tab; storage may be blocked, so never throw. */
export function loadSelectedQuestionSet(): string | null {
  try {
    return window.sessionStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function saveSelectedQuestionSet(id: string | null): void {
  try {
    if (id) window.sessionStorage.setItem(KEY, id)
    else window.sessionStorage.removeItem(KEY)
  } catch {
    // per-tab convenience only
  }
}

/** Plain-language text for Dev B's unresolved item kinds. */
export const UNRESOLVED_TEXT: Record<string, string> = {
  unknown_counting_convention: "The funder's counting method is not stated.",
  limit_conflict: 'The guide gives conflicting limits; none has been chosen.',
  unknown_limit_unit: 'The limit has no unit (words or characters); none has been chosen.',
  required_status_unknown: 'The guide does not say whether this is required.',
  scope_unknown: 'The organization or program scope is not stated.',
}
