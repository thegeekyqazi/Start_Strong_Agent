// INT-001: ephemeral, tab-local IDs only. The server resolves all content and authority.
export type ApprovedSelection = {
  questionSetId: string
  approvals: Record<string, string>
}
let selection: ApprovedSelection | null = null

export function readApprovedSelection(): ApprovedSelection | null {
  return selection
    ? { questionSetId: selection.questionSetId, approvals: { ...selection.approvals } }
    : null
}

export function selectApprovedAnswer(
  questionSetId: string,
  questionId: string,
  approvalId: string,
) {
  selection = {
    questionSetId,
    approvals: {
      ...(selection?.questionSetId === questionSetId ? selection.approvals : {}),
      [questionId]: approvalId,
    },
  }
  window.location.hash = '#/automation'
}

export function clearApprovedSelection() {
  selection = null
}
