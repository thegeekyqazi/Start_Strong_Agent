import { act, fireEvent, render, screen } from '@testing-library/react'
import type {
  PrefillPlan,
  PrefillRunView,
  PublishedApplicationVersion,
} from '@strongstart/contracts'
import * as api from './api'
import { PrefillPanel, PREFILL_PENDING_KEY } from './prefill'

const id = `pfp-${'a'.repeat(26)}`
const qs = `qs-def-${'b'.repeat(26)}-v1`
const question = `def-${'b'.repeat(26)}:pf-org-name`
const exact = '  Approved <img src=x onerror="alert(1)"> 🦎  '
const pub = {
  question_set_id: qs,
  version: 1,
  id_mapping: [
    {
      original_question_id: 'pf-org-name',
      published_question_id: question,
      question_version: 1,
      order: 0,
    },
  ],
} as PublishedApplicationVersion
const plan = {
  plan_id: id,
  plan_sha256: 'c'.repeat(64),
  expires_at: '2026-11-08T12:02:00Z',
  executable: true,
  mode_label: 'FIXTURE test provider only',
  scope_note: 'Selected fields only.',
  actions: [
    {
      action_index: 0,
      published_question_id: question,
      field_id: 'org-name-field',
      operation: 'fill',
      intended_value: exact,
      intended_choices: [],
      approval_snapshot_id: 'approved-1',
      answer_version_id: 'answer-v3',
      template_sha256: 'd'.repeat(64),
      rendered_sha256: 'e'.repeat(64),
      constraints: ['120 UTF-16 units'],
      comparison: 'b2-readback-exact/1',
    },
  ],
  held: [
    {
      published_question_id: 'held-q',
      reason: 'held_unresolved_requirement',
      detail: '350/500 conflict',
    },
  ],
  unselected_requirements: [{ published_question_id: 'other-q', required_status: 'required' }],
  attachments: [
    {
      published_question_id: 'budget-q',
      status: 'needs_review_unavailable',
      accepted_types: ['.pdf'],
      max_size_bytes: 1000,
      max_count: 1,
      findings: ['Required file unavailable'],
      evidence_basis: 'unavailable',
    },
  ],
} as unknown as PrefillPlan

function receipt(outcome = 'selected_fields_verified'): PrefillRunView {
  return {
    effective_outcome: outcome,
    interrupted: false,
    history_note: 'Historical receipt.',
    run: {
      run_id: `pfr-${'a'.repeat(26)}`,
      plan_id: id,
      outcome,
      final_reread: 'all_match',
      receipt_note: 'Ephemeral fixture page closed; test approval provider.',
      fields: [
        {
          action_index: 0,
          field_id: 'org-name-field',
          state: 'entered_verified',
          result: 'match',
          actual_value: exact,
          intended_sha256: 'e'.repeat(64),
          actual_sha256: 'e'.repeat(64),
          comparison: 'b2-readback-exact/1',
          next_action: 'Review selected fields.',
        },
      ],
    },
  } as PrefillRunView
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => {
    resolve = r
  })
  return { promise, resolve }
}

async function prepared() {
  fireEvent.change(screen.getByLabelText('Exact saved question-set ID'), { target: { value: qs } })
  fireEvent.click(screen.getByText('Load prefill questions'))
  await screen.findByText(/Exact selection/)
  fireEvent.change(screen.getByLabelText(/Approval ID for pf-org-name/), {
    target: { value: 'approved-1' },
  })
  fireEvent.click(screen.getByText('Prepare selected-field plan (no entry)'))
  await screen.findByText('Exact approved plan preview')
}

beforeEach(() => {
  sessionStorage.clear()
  vi.spyOn(api, 'getQuestionSet').mockResolvedValue({ ok: true, data: pub })
  vi.spyOn(api, 'preparePrefill').mockResolvedValue({ ok: true, data: plan })
  vi.spyOn(api, 'executePrefill').mockResolvedValue({
    ok: true,
    data: { replayed: false, run: receipt() },
  })
  vi.spyOn(api, 'getPrefillPlan').mockResolvedValue({
    ok: true,
    data: { plan, availability: 'claimed', run_id: `pfr-${'a'.repeat(26)}` },
  })
  vi.spyOn(api, 'getPrefillRun').mockResolvedValue({ ok: true, data: receipt() })
})
afterEach(() => vi.restoreAllMocks())

it('previews exact server text, holds, requirements and checklist; sends IDs only', async () => {
  const { container } = render(<PrefillPanel />)
  await prepared()
  expect(api.preparePrefill).toHaveBeenCalledWith({
    question_set_id: qs,
    portal_fixture_id: 'rep-prefill-v1',
    selections: [{ published_question_id: question, approval_snapshot_id: 'approved-1' }],
  })
  expect(container.querySelector('pre')?.textContent).toBe(exact)
  expect(container.querySelector('img')).toBeNull()
  expect(screen.getByText(/350\/500 conflict/)).toBeInTheDocument()
  expect(screen.getByText(/Required file unavailable/)).toBeInTheDocument()
  expect(screen.getByText(/other-q: required, unselected/)).toBeInTheDocument()
  expect(api.executePrefill).not.toHaveBeenCalled()
})

it('guards a double click and shows running then a live read-back receipt', async () => {
  const gate = deferred<Awaited<ReturnType<typeof api.executePrefill>>>()
  vi.mocked(api.executePrefill).mockReturnValue(gate.promise)
  render(<PrefillPanel />)
  await prepared()
  const button = screen.getByText('Fill these approved fields')
  fireEvent.click(button)
  fireEvent.click(button)
  expect(api.executePrefill).toHaveBeenCalledTimes(1)
  expect(button).toBeDisabled()
  expect(screen.getByRole('status')).toHaveTextContent('Running approved entry')
  await act(async () => gate.resolve({ ok: true, data: { replayed: false, run: receipt() } }))
  expect(await screen.findByText('Selected fields verified')).toBeInTheDocument()
  expect(screen.getByLabelText('Read-back receipt')).toHaveTextContent('Final reread: all_match')
  expect(button).toBeDisabled()
})

it('retains one request key across lost response, retry and refresh; refresh only reads', async () => {
  vi.mocked(api.executePrefill).mockResolvedValueOnce({ ok: false, status: 0, error: null })
  const view = render(<PrefillPanel />)
  await prepared()
  fireEvent.click(screen.getByText('Fill these approved fields'))
  await screen.findByRole('alert')
  const first = vi.mocked(api.executePrefill).mock.calls[0]
  fireEvent.click(screen.getByText('Fill these approved fields'))
  await screen.findByText('Selected fields verified')
  expect(vi.mocked(api.executePrefill).mock.calls[1]).toEqual(first)
  expect(JSON.parse(sessionStorage.getItem(PREFILL_PENDING_KEY)!)).toMatchObject({
    planId: id,
    hash: plan.plan_sha256,
  })
  view.unmount()
  render(<PrefillPanel />)
  expect(api.executePrefill).toHaveBeenCalledTimes(2)
  fireEvent.click(screen.getByText('Check stored receipt'))
  await screen.findByText('Selected fields verified')
  expect(api.getPrefillRun).toHaveBeenCalledTimes(1)
  expect(api.executePrefill).toHaveBeenCalledTimes(2)
})

it.each([
  ['stopped_with_partial_entry', 'Stopped with partial entry'],
  ['blocked_before_entry', 'Blocked before entry'],
  ['outcome_unknown', 'Outcome unknown — do not assume entry succeeded'],
  ['in_progress', 'Running — this plan has already been claimed'],
])('shows %s without enabling another execution', async (outcome, label) => {
  vi.mocked(api.executePrefill).mockResolvedValue({
    ok: true,
    data: { replayed: false, run: receipt(outcome) },
  })
  render(<PrefillPanel />)
  await prepared()
  fireEvent.click(screen.getByText('Fill these approved fields'))
  expect(await screen.findByText(label)).toBeInTheDocument()
  expect(screen.getByText('Fill these approved fields')).toBeDisabled()
})

it('does not let a late preparation overwrite a newer selection', async () => {
  const gate = deferred<Awaited<ReturnType<typeof api.preparePrefill>>>()
  vi.mocked(api.preparePrefill).mockReturnValue(gate.promise)
  render(<PrefillPanel />)
  fireEvent.change(screen.getByLabelText('Exact saved question-set ID'), { target: { value: qs } })
  fireEvent.click(screen.getByText('Load prefill questions'))
  await screen.findByText(/Exact selection/)
  fireEvent.change(screen.getByLabelText(/Approval ID for pf-org-name/), {
    target: { value: 'approved-1' },
  })
  fireEvent.click(screen.getByText('Prepare selected-field plan (no entry)'))
  fireEvent.change(screen.getByLabelText('Exact saved question-set ID'), {
    target: { value: 'new-selection' },
  })
  await act(async () => gate.resolve({ ok: true, data: plan }))
  expect(screen.queryByText('Exact approved plan preview')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Exact saved question-set ID')).toHaveValue('new-selection')
  expect(api.executePrefill).not.toHaveBeenCalled()
})

it('does not let a late execution response relabel a newer selection', async () => {
  const gate = deferred<Awaited<ReturnType<typeof api.executePrefill>>>()
  vi.mocked(api.executePrefill).mockReturnValue(gate.promise)
  render(<PrefillPanel />)
  await prepared()
  fireEvent.click(screen.getByText('Fill these approved fields'))
  fireEvent.change(screen.getByLabelText('Registered prefill portal'), {
    target: { value: 'rep-portal-v1' },
  })
  await act(async () => gate.resolve({ ok: true, data: { replayed: false, run: receipt() } }))
  expect(screen.queryByLabelText('Read-back receipt')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Registered prefill portal')).toHaveValue('rep-portal-v1')
})

it('holds an empty plan and exposes an unavailable reader without fallback', async () => {
  vi.mocked(api.preparePrefill).mockResolvedValueOnce({
    ok: false,
    status: 503,
    error: {
      code: 'capability_unavailable',
      message: 'No approved-content reader',
      details: { reason: 'approval_reader_unavailable' },
    },
  })
  render(<PrefillPanel />)
  fireEvent.change(screen.getByLabelText('Exact saved question-set ID'), { target: { value: qs } })
  fireEvent.click(screen.getByText('Load prefill questions'))
  await screen.findByText(/Exact selection/)
  fireEvent.change(screen.getByLabelText(/Approval ID for pf-org-name/), {
    target: { value: 'approved-1' },
  })
  fireEvent.click(screen.getByText('Prepare selected-field plan (no entry)'))
  expect(await screen.findByRole('alert')).toHaveTextContent('approval_reader_unavailable')
  vi.mocked(api.preparePrefill).mockResolvedValueOnce({
    ok: true,
    data: {
      ...plan,
      actions: [],
      executable: false,
      not_executable_reasons: ['no_eligible_selected_fields'],
    },
  })
  fireEvent.click(screen.getByText('Prepare selected-field plan (no entry)'))
  await screen.findByText('Entry blocked: no_eligible_selected_fields')
  expect(screen.getByText('Fill these approved fields')).toBeDisabled()
  expect(api.executePrefill).not.toHaveBeenCalled()
})
