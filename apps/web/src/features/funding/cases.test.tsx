import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type {
  CaptureContent,
  CapturedDocument,
  EvaluationReport,
  FundingCaseEnvelope,
} from '@strongstart/contracts'
import type { ApiResult, FundingClient } from './client'
import { FundingCases, ReportView } from './cases'
import { locateQuote } from './quote'

const capId = 'cap-' + 'a'.repeat(32)
const sha = 'd'.repeat(64)
const text = '# FIXTURE 🙂\n\nStandard stream requests: 20,000 to 100,000 CAD per award.\n'
const doc = {
  capture_id: capId,
  artifacts: [
    { artifact_id: `${capId}-markdown`, representation: 'provider_markdown', sha256: sha },
  ],
  supported_import_representations: [],
} as unknown as CapturedDocument
const content = {
  capture_id: capId,
  artifact: doc.artifacts[0],
  text,
  integrity_verified: true,
} as unknown as CaptureContent

const caseId = 'case-' + '1'.repeat(26)
const envelope = {
  version: {
    case_id: caseId,
    version: 1,
    context: {
      funder_label: 'FIXTURE Funder',
      stream_label: 'standard',
      cycle_label: '2026',
      stage: 'full_application',
    },
    capture_links: [],
    anchors: [
      {
        anchor_key: 'amount',
        capture_id: capId,
        quote: 'Standard stream requests: 20,000 to 100,000 CAD per award.',
        start: 14,
        end: 73,
        coverage: 'complete',
        is_simulated: true,
      },
    ],
    requirements: [
      {
        requirement_key: 'standard-amount',
        spec: { kind: 'amount_range', limit_kind: 'per_award', maximum: '100000', currency: 'CAD' },
        anchor_keys: ['amount'],
        scope: {},
        interpretation: 'Per-award maximum.',
        rule_ids: ['ELG-02', 'ELG-03'],
      },
    ],
  },
  version_digest: 'e'.repeat(64),
  current_version: 1,
  is_current: true,
  review_status: 'unreviewed',
  source_status: 'current',
  readiness: 'not_reviewed',
  opportunity: null,
  opportunity_missing: ['source link'],
} as unknown as FundingCaseEnvelope

const ok = <T,>(data: T) => Promise.resolve({ ok: true, data } as ApiResult<T>)

function client(over: Partial<FundingClient> = {}): FundingClient {
  return {
    availability: vi.fn(),
    search: vi.fn(),
    capture: vi.fn(),
    listCaptures: vi.fn(),
    getCapture: () => ok(doc),
    content: () => ok(content),
    listCases: () =>
      ok({ items: [], next_cursor: null, more: false, incomplete: false, limit: 20 }),
    getCase: () => ok(envelope),
    saveCase: vi.fn(() => ok(envelope)),
    reviewCase: vi.fn(() => ok({ ...envelope, review_status: 'reviewed' } as FundingCaseEnvelope)),
    evaluateCase: vi.fn(),
    listEvaluations: vi.fn(),
    ...over,
  } as FundingClient
}

describe('locateQuote', () => {
  it('counts Unicode code points like the server and reports duplicates', () => {
    const found = locateQuote(text, 'Standard stream')
    expect(found).toEqual({ start: 13, count: 1 }) // the emoji is one code point (UTF-16 would say 14)
    expect(locateQuote('ab ab', 'ab')).toEqual({ start: 0, count: 2 })
    expect(locateQuote('abc', 'zz')).toBeNull()
  })
})

describe('FundingCases', () => {
  it('builds a case from an exact verified quote and a typed rule, without authority flags', async () => {
    const c = client()
    render(<FundingCases client={c} />)
    await screen.findByText('No funding cases yet.')
    fireEvent.change(screen.getByLabelText('Funder'), { target: { value: 'FIXTURE Funder' } })
    fireEvent.change(screen.getByLabelText('Capture ID'), { target: { value: capId } })
    fireEvent.click(screen.getByRole('button', { name: 'Load capture' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Show provider_markdown' }))
    expect(await screen.findByTestId('anchor-source')).toHaveTextContent('Standard stream')
    fireEvent.change(screen.getByLabelText('Exact quote'), {
      target: { value: 'Standard stream requests: 20,000 to 100,000 CAD per award.' },
    })
    fireEvent.change(screen.getByLabelText('Anchor key'), { target: { value: 'amount' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add anchor' }))
    fireEvent.change(screen.getByLabelText('Requirement key'), { target: { value: 'cap' } })
    fireEvent.change(screen.getByLabelText('Anchor keys'), { target: { value: 'amount' } })
    fireEvent.change(screen.getByLabelText('Maximum (exact decimal)'), {
      target: { value: '100000' },
    })
    fireEvent.change(screen.getByLabelText('Interpretation'), { target: { value: 'Per award.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add requirement' }))
    fireEvent.click(screen.getByRole('button', { name: 'Create funding case' }))
    await waitFor(() => expect(c.saveCase).toHaveBeenCalled())
    const body = vi.mocked(c.saveCase).mock.calls[0][0]
    expect(body.anchors?.[0]).toMatchObject({ start: 13, end: 71, expected_artifact_sha256: sha })
    expect(body.requirements?.[0].spec).toMatchObject({ kind: 'amount_range', maximum: '100000' })
    expect(JSON.stringify(body)).not.toMatch(/reviewed|approved|organization|eligible/)
  })

  it('rejects a quote that does not occur exactly', async () => {
    render(<FundingCases client={client()} />)
    fireEvent.change(await screen.findByLabelText('Capture ID'), { target: { value: capId } })
    fireEvent.click(screen.getByRole('button', { name: 'Load capture' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Show provider_markdown' }))
    fireEvent.change(await screen.findByLabelText('Exact quote'), {
      target: { value: 'Standard stream requests: 20,000 to 100,001' },
    })
    fireEvent.change(screen.getByLabelText('Anchor key'), { target: { value: 'amount' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add anchor' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('does not occur')
  })

  it('reviews the exact version digest and every requirement key', async () => {
    const c = client({
      listCases: () =>
        ok({
          items: [
            {
              case_id: caseId,
              status: 'ok',
              current_version: 1,
              review_status: 'unreviewed',
              source_status: 'current',
              requirement_count: 1,
            },
          ],
          next_cursor: null,
          more: false,
          incomplete: false,
          limit: 20,
        }),
    })
    render(<FundingCases client={c} />)
    fireEvent.click(await screen.findByRole('button', { name: `Open case ${caseId}` }))
    expect(
      await screen.findByText(/Staff-selected context, not a certified opportunity/),
    ).toBeInTheDocument()
    expect(screen.getByText(/Not established: missing source link/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Review these requirements' }))
    await waitFor(() => expect(c.reviewCase).toHaveBeenCalled())
    const [id, version, cmd] = vi.mocked(c.reviewCase).mock.calls[0]
    expect([id, version]).toEqual([caseId, 1])
    expect(cmd).toMatchObject({
      version_digest: 'e'.repeat(64),
      requirement_keys: ['standard-amount'],
    })
  })
})

describe('ReportView', () => {
  it('shows the four answers and never an eligibility badge', () => {
    const report = {
      scenario_summary:
        'These encoded rules are met using these inputs; funder eligibility is not confirmed.',
      reliance_explanation: 'Reliance: not confirmed. Inputs are staff_asserted scenario values.',
      clock: '2026-02-01T12:00:00-05:00',
      clock_source: 'request',
      case_version: 1,
      inputs_digest: 'f'.repeat(64),
      evaluator_version: 'b1-rules/1',
      results: [
        {
          requirement_key: 'standard-amount',
          kind: 'amount_range',
          rule_ids: ['ELG-02', 'ELG-03'],
          outcome: 'not_met',
          compared: 'the requested amount against the reviewed per-award range',
          support: [
            { anchor_key: 'amount', quote: 'Standard stream requests: 20,000 to 100,000 CAD' },
          ],
          inputs_used: ['request_amount=120000 CAD units (staff_asserted)'],
          found: 'Request 120,000 exceeds the maximum 100,000 by 20,000 (exact Decimal).',
          uncertainty: 'The request is a staff scenario; confirm the actual budget.',
          next_action: 'Reduce the request or confirm a different stream.',
        },
      ],
      excluded: [{ requirement_key: 'pool', reason: 'a total pool is not a per-award cap' }],
    } as unknown as EvaluationReport
    render(<ReportView report={report} />)
    expect(screen.getByText(/funder eligibility is not confirmed/)).toBeInTheDocument()
    expect(screen.getByText(/exceeds the maximum 100,000 by 20,000/)).toBeInTheDocument()
    expect(screen.getByText(/Uncertain: The request is a staff scenario/)).toBeInTheDocument()
    expect(screen.getByText(/not a per-award cap/)).toBeInTheDocument()
    expect(screen.queryByText(/^Eligible$/i)).toBeNull()
  })
})
