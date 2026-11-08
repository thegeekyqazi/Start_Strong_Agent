import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { DraftProposal, ErrorEnvelope } from '@strongstart/contracts'
import { demoWorkspace } from '../../shell/components/demoBundle.testdata'
import type { ApiResult, ApplicationsClient } from './client'
import { ApplicationsPage } from './Page'

const TEMPLATE =
  'SYNTHETIC FIXTURE DRAFT: Demo Org supports early learning. Linked evidence: {{fact:demo-fact-children-served}}.'

const proposal: DraftProposal = {
  schema_version: '1',
  proposal_id: 'draft-abc',
  question_id: 'mission-q1',
  question_version: 1,
  evidence_bundle_id: 'demo-evidence-a-v1',
  pack_version_id: 'demo-a-v1',
  template_text: TEMPLATE,
  template_sha256: 'c'.repeat(64),
  segments: [],
  fact_ids: ['demo-fact-children-served'],
  uncertainties: ['Linked facts must be checked by staff before this text is used.'],
  provider: { adapter: 'fake', model: 'fake-deterministic-v1', is_fixture: true },
  provenance: { provenance_class: 'simulated', is_simulated: true },
}

function fail(status: number, reason?: string): ApiResult<never> {
  const error: ErrorEnvelope = {
    code: 'validation_failed',
    message: 'x',
    details: reason ? { reason } : {},
  }
  return { ok: false, status, error }
}

function client(draft: ApiResult<DraftProposal> = { ok: true, data: proposal }) {
  const calls: unknown[] = []
  const c: ApplicationsClient = {
    workspace: async () => ({ ok: true, data: demoWorkspace }),
    draft: async (id, body) => {
      calls.push([id, body])
      return draft
    },
  }
  return { c, calls }
}

const editor = () => screen.getByLabelText('Your answer') as HTMLTextAreaElement

describe('Applications workspace', () => {
  it('shows questions, the read-only original question, evidence and an empty editor', async () => {
    render(<ApplicationsPage client={client().c} />)
    const list = await screen.findByRole('navigation', { name: 'Questions' })
    expect(within(list).getAllByRole('button')).toHaveLength(4)
    expect(
      screen.getByText("FIXTURE: Describe your organization's mission.", {
        selector: 'blockquote',
      }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: /question/i })).not.toBeInTheDocument()
    expect(editor().value).toBe('')
    expect(screen.getByText('120 children')).toBeInTheDocument()
    expect(
      screen.getByText(/Limit: 50 words\. Counting method not confirmed\./),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/0 of 50 words \(placeholder count; counting convention unverified\)/),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Approved/)).not.toBeInTheDocument()
  })

  it('fills the editor with the fake draft and renders fact slots as chips', async () => {
    const { c, calls } = client()
    render(<ApplicationsPage client={c} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Request a draft' }))
    await waitFor(() => expect(editor().value).toBe(TEMPLATE))
    expect(calls).toEqual([
      ['mission-q1', { question_version: 1, evidence_bundle_id: 'demo-evidence-a-v1' }],
    ])
    const chip = screen.getByLabelText(/Linked fact children-served/)
    expect(chip).toHaveTextContent(
      '120 children · 2025-09/2026-06 · Simulated · Not yet verified by staff',
    )
    expect(screen.getByText(/fixed sample output, not an AI model/)).toBeInTheDocument()
    expect(screen.getByText('Draft – not reviewed')).toBeInTheDocument()
    expect(screen.getByTitle('c'.repeat(64))).toBeInTheDocument()
  })

  it('never overwrites staff text with a draft (engineering s15)', async () => {
    render(<ApplicationsPage client={client().c} />)
    fireEvent.change(await screen.findByLabelText('Your answer'), {
      target: { value: 'My own words' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Request a draft' }))
    expect(await screen.findByText('Suggested draft')).toBeInTheDocument()
    expect(editor().value).toBe('My own words')
    fireEvent.click(screen.getByRole('button', { name: 'Replace my text with this suggestion' }))
    expect(editor().value).toBe(TEMPLATE)
  })

  it('keeps text typed while a draft request is in flight', async () => {
    let resolve: (r: ApiResult<DraftProposal>) => void = () => {}
    const c: ApplicationsClient = {
      workspace: async () => ({ ok: true, data: demoWorkspace }),
      draft: () => new Promise((r) => (resolve = r)),
    }
    render(<ApplicationsPage client={c} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Request a draft' }))
    fireEvent.change(editor(), { target: { value: 'typed meanwhile' } })
    resolve({ ok: true, data: proposal })
    expect(await screen.findByText('Suggested draft')).toBeInTheDocument()
    expect(editor().value).toBe('typed meanwhile')
  })

  it('updates the placeholder counter while typing', async () => {
    render(<ApplicationsPage client={client().c} />)
    fireEvent.change(await screen.findByLabelText('Your answer'), {
      target: { value: 'one two three' },
    })
    expect(screen.getByText(/3 of 50 words/)).toBeInTheDocument()
  })

  it('shows both limits for a conflict and both counts for an unknown unit', async () => {
    render(<ApplicationsPage client={client().c} />)
    fireEvent.click(await screen.findByRole('button', { name: /Describe your partnerships/ }))
    expect(
      screen.getByText(/350 words and 500 words\. We have not chosen one\./),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /List pending applications/ }))
    expect(screen.getByText(/does not say words or characters/)).toBeInTheDocument()
    expect(screen.getByText(/0 words, 0 characters/)).toBeInTheDocument()
  })

  it.each([
    [fail(503), /no writing assistant is set up/],
    [fail(502, 'model_output_rejected'), /didn't pass our safety and format checks/],
    [fail(504, 'model_timeout'), /took too long/],
    [fail(409), /question changed since you opened it/],
  ])(
    'draft failure shows a distinct message and leaves the editor untouched',
    async (result, text) => {
      render(<ApplicationsPage client={client(result).c} />)
      fireEvent.change(await screen.findByLabelText('Your answer'), { target: { value: 'kept' } })
      fireEvent.click(screen.getByRole('button', { name: 'Request a draft' }))
      expect(await screen.findByRole('alert')).toHaveTextContent(text)
      expect(editor().value).toBe('kept')
    },
  )

  it.each([
    [401, /not signed in/],
    [503, /isn't set up on this server yet/],
  ])('workspace %s shows a distinct message', async (status, text) => {
    const c: ApplicationsClient = {
      workspace: async () => fail(status),
      draft: async () => fail(500),
    }
    render(<ApplicationsPage client={c} />)
    expect(await screen.findByRole('alert')).toHaveTextContent(text)
    expect(screen.queryByLabelText('Your answer')).not.toBeInTheDocument()
  })
})
