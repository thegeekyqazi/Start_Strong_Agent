import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ApplicationWorkspace, DefinitionList, ErrorEnvelope } from '@strongstart/contracts'
import { demoWorkspace } from '../../shell/components/demoBundle.testdata'
import type { ApiResult, ApplicationsClient } from './client'
import { ApplicationsPage } from './Page'
import { QuestionSetPicker } from './QuestionSetPicker'
import type { QuestionSetClient } from './questionSets'

const QS = 'qs-def-01a1ba112583f8bb87a6c9b125-v1'
const DEF = 'def-01a1ba112583f8bb87a6c9b125'

const list: DefinitionList = {
  items: [
    {
      definition_id: DEF,
      status: 'ok',
      current_version: 1,
      question_set_id: QS,
      title: 'Representative portal',
      is_fixture: true,
    },
    { definition_id: 'def-' + 'b'.repeat(26), status: 'integrity_failure' },
  ],
  more: false,
  incomplete: false,
  limit: 50,
}
const sets: QuestionSetClient = { list: async () => ({ ok: true, data: list }) }

// Dev B's saved questions use published IDs `<definition_id>:<original_id>`.
const mission = { ...demoWorkspace.question_set.questions[0], question_id: `${DEF}:rp-mission` }
const savedWorkspace: ApplicationWorkspace = {
  ...demoWorkspace,
  question_set: { ...demoWorkspace.question_set, question_set_id: QS, questions: [mission] },
  question_source: 'dev_b_saved_definition',
  question_set_ref: {
    question_set_id: QS,
    definition_id: DEF,
    definition_version: 1,
    is_fixture: true,
    mode_label: 'FIXTURE - engineering-derived representative material',
    review_status: 'saved_not_reviewed',
    saved_at: '2026-11-08T00:00:00Z',
  },
  unresolved: [
    { question_id: `${DEF}:rp-mission`, kind: 'unknown_counting_convention', detail: 'x' },
  ],
}

function notFound(): ApiResult<never> {
  const error: ErrorEnvelope = {
    code: 'validation_failed',
    message: 'x',
    details: { reason: 'unknown_question_set' },
  }
  return { ok: false, status: 404, error }
}

function client(workspaceFor: (qs: string | null | undefined) => ApiResult<ApplicationWorkspace>) {
  const asked: (string | null | undefined)[] = []
  const drafts: unknown[] = []
  const c: ApplicationsClient = {
    workspace: async (qs) => {
      asked.push(qs)
      return workspaceFor(qs)
    },
    draft: async (_id, body) => {
      drafts.push(body)
      return { ok: false, status: 503, error: null }
    },
    check: async () => ({ ok: false, status: 500, error: null }),
    plan: async () => ({ ok: false, status: 500, error: null }),
  }
  return { c, asked, drafts }
}

beforeEach(() => window.sessionStorage.clear())

describe('QuestionSetPicker', () => {
  it('offers the demo explicitly plus only verified saved definitions', async () => {
    const chosen: (string | null)[] = []
    render(<QuestionSetPicker value={null} onChange={(id) => chosen.push(id)} client={sets} />)
    const select = screen.getByLabelText('Questions from')
    await screen.findByText(/Representative portal \(saved definition v1, fixture material\)/)
    expect(screen.getAllByRole('option')).toHaveLength(2) // demo + 1 ok definition
    fireEvent.change(select, { target: { value: QS } })
    fireEvent.change(select, { target: { value: '' } })
    expect(chosen).toEqual([QS, null])
  })
})

describe('Applications with a Dev B saved question set', () => {
  it('loads the selected set by ID and shows its status and unresolved items', async () => {
    const { c, asked, drafts } = client((qs) =>
      qs === QS ? { ok: true, data: savedWorkspace } : { ok: true, data: demoWorkspace },
    )
    render(<ApplicationsPage client={c} questionSets={sets} />)
    await screen.findByText('Draft answers', { exact: false })
    await screen.findByRole('option', { name: /Representative portal/ }) // picker loaded
    fireEvent.change(screen.getByLabelText('Questions from'), { target: { value: QS } })
    expect(await screen.findByText(/saved, not reviewed or approved by Dev B/)).toBeInTheDocument()
    expect(asked).toEqual([null, QS])
    expect(
      screen.getByText(/Saved definition: The funder's counting method is not stated\./),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Request a draft' }))
    await waitFor(() => expect(drafts).toHaveLength(1))
    expect(drafts[0]).toMatchObject({ question_set_id: QS })
    expect(window.sessionStorage.getItem('strongstart.c.questionSetId')).toBe(QS)
  })

  it('shows a missing set as an error and never falls back on its own', async () => {
    window.sessionStorage.setItem('strongstart.c.questionSetId', QS)
    const { c, asked } = client((qs) =>
      qs === QS ? notFound() : { ok: true, data: demoWorkspace },
    )
    render(<ApplicationsPage client={c} questionSets={sets} />)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /saved question set wasn't found.*did not switch to other questions/,
    )
    expect(asked).toEqual([QS]) // no automatic second request for the demo questions
    expect(screen.queryByLabelText('Your answer')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Use the demo fixture questions instead' }))
    expect(await screen.findByLabelText('Your answer')).toBeInTheDocument()
    expect(asked).toEqual([QS, null])
  })
})
