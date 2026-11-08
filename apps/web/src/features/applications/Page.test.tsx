import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type {
  AnswerFinding,
  AnswerPlan,
  CheckReport,
  CheckRequest,
  DraftProposal,
  ErrorEnvelope,
} from '@strongstart/contracts'
import { demoWorkspace } from '../../shell/components/demoBundle.testdata'
import type { ApiResult, ApplicationsClient } from './client'
import { ApplicationsPage } from './Page'

const FACT = 'demo-fact-children-served'
const TEMPLATE = `SYNTHETIC FIXTURE DRAFT: Demo Org supports early learning. Linked evidence: {{fact:${FACT}}}.`
const RENDERED_FACT = '120 children (2025-09/2026-06)'
const HASH = 'c'.repeat(64)

const proposal: DraftProposal = {
  schema_version: '1',
  proposal_id: 'draft-abc',
  question_id: 'mission-q1',
  question_version: 1,
  evidence_bundle_id: 'demo-evidence-a-v1',
  pack_version_id: 'demo-a-v1',
  template_text: TEMPLATE,
  template_sha256: HASH,
  segments: [],
  fact_ids: [FACT],
  uncertainties: ['Linked facts must be checked by staff before this text is used.'],
  provider: { adapter: 'fake', model: 'fake-deterministic-v1', is_fixture: true },
  provenance: { provenance_class: 'simulated', is_simulated: true },
}

function finding(
  rule: string,
  outcome: AnswerFinding['result']['outcome'],
  message: string,
  affected?: string,
): AnswerFinding {
  return {
    result: { rule_id: rule, rule_version: 'c2-1', outcome, inputs: {}, reasons: [] },
    message,
    affected_text: affected ?? null,
    next_action: outcome === 'pass' ? null : 'Fix it.',
  }
}

/** Mirrors the API contract shape; rule logic itself is tested in pytest against the real API. */
function report(questionId: string, body: CheckRequest): CheckReport {
  const token = `{{fact:${FACT}}}`
  const at = Array.from(body.text.split(token)[0]).length
  const text = body.text.replace(token, RENDERED_FACT)
  const words = text.trim() === '' ? 0 : text.trim().split(/\s+/).length
  const findings = [
    finding(
      'APP-01',
      'needs_review',
      `${words} of 50 words (words-v1). Counting method not confirmed.`,
    ),
  ]
  if (/\b500\b/.test(body.text)) {
    findings.push(
      finding(
        'APP-03',
        body.mode === 'reviewed' ? 'fail' : 'needs_review',
        '"500" is a number that is not linked to evidence.',
        '500',
      ),
    )
  }
  return {
    schema_version: '1',
    question_id: questionId,
    question_version: 1,
    evidence_bundle_id: body.evidence_bundle_id,
    mode: body.mode ?? 'working',
    submitted_text_sha256: HASH,
    rendered: {
      text,
      text_sha256: HASH,
      bindings: body.text.includes(token)
        ? [
            {
              fact_id: FACT,
              pack_version_id: 'demo-a-v1',
              span_start: at,
              span_end: at + Array.from(RENDERED_FACT).length,
              rendered_text: RENDERED_FACT,
            },
          ]
        : [],
      unsupported_markers: [],
    },
    findings,
  }
}

const plan: AnswerPlan = {
  schema_version: '1',
  plan_id: 'plan-1',
  question_set_id: 'demo-gos-questions-v1',
  evidence_bundle_id: 'demo-evidence-a-v1',
  items: [
    {
      question_id: 'mission-q1',
      question_version: 1,
      evidence_fact_ids: [FACT],
      missing_inputs: [],
      repeated_with: [],
    },
    {
      question_id: 'services-q2',
      question_version: 1,
      evidence_fact_ids: [],
      missing_inputs: ['Program descriptions'],
      repeated_with: [],
    },
  ],
  planner: { adapter: 'fake', model: 'fake-deterministic-v1', is_fixture: true },
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
  const checks: CheckRequest[] = []
  const c: ApplicationsClient = {
    workspace: async () => ({ ok: true, data: demoWorkspace }),
    draft: async (id, body) => {
      calls.push([id, body])
      return draft
    },
    check: async (id, body) => {
      checks.push(body)
      return { ok: true, data: report(id, body) }
    },
    plan: async () => ({ ok: true, data: plan }),
  }
  return { c, calls, checks }
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
    expect(editor().value).toBe('')
    expect(screen.getByText('120 children')).toBeInTheDocument()
    expect(
      screen.getByText(/Limit: 50 words\. Counting method not confirmed\./),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(document.querySelector('.counter')).toHaveTextContent(/0 of 50 words \(words-v1\)/),
    )
    expect(screen.queryByText(/Approved/)).not.toBeInTheDocument()
  })

  it('fills the editor with the draft and renders server-rendered fact chips', async () => {
    const { c, calls } = client()
    render(<ApplicationsPage client={c} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Request a draft' }))
    await waitFor(() => expect(editor().value).toBe(TEMPLATE))
    expect(calls).toEqual([
      [
        'mission-q1',
        { question_version: 1, evidence_bundle_id: 'demo-evidence-a-v1', question_set_id: null },
      ],
    ])
    const chip = await screen.findByLabelText(/Linked fact children-served/)
    expect(chip).toHaveTextContent(`${RENDERED_FACT} · Simulated · Not yet verified by staff`)
    expect(screen.getByText(/fixed sample output, not an AI model/)).toBeInTheDocument()
    expect(screen.getByText('Draft – not reviewed')).toBeInTheDocument()
  })

  it('flags a raw number from the checks and marks findings out of date after an edit', async () => {
    const { c, checks } = client()
    render(<ApplicationsPage client={c} />)
    fireEvent.change(await screen.findByLabelText('Your answer'), {
      target: { value: 'We served 500 children.' },
    })
    expect(
      await screen.findByText(/"500" is a number that is not linked to evidence/),
    ).toBeInTheDocument()
    const checksPanel = screen.getByRole('region', { name: 'Checks on this text' })
    expect(within(checksPanel).getAllByText('Needs your review').length).toBeGreaterThanOrEqual(2)
    fireEvent.change(editor(), { target: { value: 'We served many children.' } })
    expect(screen.getByText(/Out of date – the text or check mode changed/)).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText(/"500" is a number/)).not.toBeInTheDocument())
    expect(checks.at(-1)?.text).toBe('We served many children.')
  })

  it('review mode re-checks and shows blocking findings', async () => {
    const { c, checks } = client()
    render(<ApplicationsPage client={c} />)
    fireEvent.change(await screen.findByLabelText('Your answer'), {
      target: { value: 'We served 500 children.' },
    })
    await screen.findByText(/"500" is a number/)
    fireEvent.click(screen.getByLabelText(/Review check/))
    expect(await screen.findByText('Problem found')).toBeInTheDocument()
    expect(checks.at(-1)?.mode).toBe('reviewed')
  })

  it('shows the plan with missing inputs and never-invented wording', async () => {
    render(<ApplicationsPage client={client().c} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Plan this application' }))
    expect(await screen.findByText('Answer plan')).toBeInTheDocument()
    expect(screen.getByText(/Missing: Program descriptions \(not invented\)/)).toBeInTheDocument()
    expect(screen.getByText(/Evidence: demo-fact-children-served/)).toBeInTheDocument()
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
    const base = client().c
    const c: ApplicationsClient = { ...base, draft: () => new Promise((r) => (resolve = r)) }
    render(<ApplicationsPage client={c} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Request a draft' }))
    fireEvent.change(editor(), { target: { value: 'typed meanwhile' } })
    await act(async () => resolve({ ok: true, data: proposal }))
    expect(await screen.findByText('Suggested draft')).toBeInTheDocument()
    expect(editor().value).toBe('typed meanwhile')
  })

  it('shows both limits for a conflict and the unknown-unit notice', async () => {
    render(<ApplicationsPage client={client().c} />)
    fireEvent.click(await screen.findByRole('button', { name: /Describe your partnerships/ }))
    expect(
      screen.getByText(/350 words and 500 words\. We have not chosen one\./),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /List pending applications/ }))
    expect(screen.getByText(/does not say words or characters/)).toBeInTheDocument()
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
      ...client().c,
      workspace: async () => fail(status),
    }
    render(<ApplicationsPage client={c} />)
    expect(await screen.findByRole('alert')).toHaveTextContent(text)
    expect(screen.queryByLabelText('Your answer')).not.toBeInTheDocument()
  })
})
