import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type {
  AnswerHistory,
  AnswerVersion,
  ApprovalDecisionRequest,
  ApprovalRecord,
  CheckReport,
  ExportResult,
} from '@strongstart/contracts'
import { demoWorkspace } from '../../shell/components/demoBundle.testdata'
import type { ApiResult, ApplicationsClient } from '../applications/client'
import type { ReviewClient } from './client'
import { ReviewPage } from './Page'

const H = (c: string) => c.repeat(64)

function check(outcome: 'needs_review' | 'fail'): CheckReport {
  return {
    schema_version: '1',
    question_id: 'mission-q1',
    question_version: 1,
    evidence_bundle_id: 'demo-evidence-a-v1',
    mode: 'reviewed',
    submitted_text_sha256: H('a'),
    rendered: { text: 'x', text_sha256: H('a'), bindings: [], unsupported_markers: [] },
    findings: [
      {
        result: { rule_id: 'APP-01', rule_version: 'c2-1', outcome, inputs: {}, reasons: [] },
        message: '18 of 50 words (words-v1).',
        next_action: 'Confirm the counting method.',
      },
    ],
  }
}

function version(
  n: number,
  text: string,
  state: AnswerVersion['state'],
  latest: boolean,
): AnswerVersion {
  return {
    schema_version: '1',
    answer_version_id: `av-${n}`,
    answer_id: 'ans-mission-q1',
    question_id: 'mission-q1',
    question_version: 1,
    answer_version: n,
    is_latest: latest,
    text,
    content_sha256: H(String(n)),
    rendered: { text, text_sha256: H(String(n)), bindings: [], unsupported_markers: [] },
    dependencies: [],
    snapshot_sha256: H('s'),
    check: check('needs_review'),
    checked_at: '2026-11-08T00:00:00Z',
    state,
    created_by: 'demo-staff',
    created_at: '2026-11-08T00:00:00Z',
  }
}

function approval(avid: string, stale: string | null): ApprovalRecord {
  return {
    approval_id: 'apr-1',
    answer_version_id: avid,
    answer_id: 'ans-mission-q1',
    question_id: 'mission-q1',
    decision: 'approve',
    content_sha256: H('1'),
    snapshot_sha256: H('s'),
    reviewer_id: 'demo-staff',
    reviewer_is_fixture_identity: true,
    note: '',
    decided_at: '2026-11-08T00:00:00Z',
    is_stale: stale !== null,
    stale_reason: stale,
  }
}

function hist(over: Partial<AnswerHistory>): AnswerHistory {
  return {
    schema_version: '1',
    question_id: 'mission-q1',
    answer_id: 'ans-mission-q1',
    versions: [],
    approvals: [],
    notes: [],
    proposals: [],
    prefill_ready: false,
    store_is_fixture: true,
    ...over,
  }
}

const appClient: ApplicationsClient = {
  workspace: async () => ({ ok: true, data: demoWorkspace }),
  draft: async () => ({ ok: false, status: 500, error: null }),
  check: async () => ({ ok: false, status: 500, error: null }),
  plan: async () => ({ ok: false, status: 500, error: null }),
}

function fake(h: AnswerHistory, overrides: Partial<ReviewClient> = {}) {
  const decisions: ApprovalDecisionRequest[] = []
  const client: ReviewClient = {
    history: async () => ({ ok: true, data: h }),
    saveVersion: async () => ({ ok: false, status: 500, error: null }),
    decide: async (body) => {
      decisions.push(body)
      return { ok: true, data: approval(body.answer_version_id, null) }
    },
    addNote: async (body) => ({
      ok: true,
      data: {
        note_id: 'n1',
        answer_version_id: body.answer_version_id,
        author_id: 'demo-staff',
        text: body.text,
        created_at: '2026-11-08T00:00:00Z',
      },
    }),
    propose: async () => ({ ok: false, status: 500, error: null }),
    exportAnswers: async () => ({ ok: false, status: 500, error: null }),
    downloadUrl: (id, kind) => `/dl/${id}/${kind}`,
    ...overrides,
  }
  return { client, decisions }
}

describe('Review page', () => {
  it('separates durable storage from synthetic evidence and fixture review', async () => {
    const h = hist({ store_is_fixture: false, store: { backend: 'postgres', durable: true } })
    render(<ReviewPage appClient={appClient} client={fake(h).client} />)
    expect(await screen.findByText(/Durable PostgreSQL store/)).toHaveTextContent(
      /Synthetic data and fixture reviewer labels still apply/,
    )
    expect(screen.queryByText(/lost on restart/)).not.toBeInTheDocument()
  })

  it('shows versions with states, the diff and fixture labelling', async () => {
    const h = hist({
      versions: [
        version(1, 'We help many families.', 'stale', false),
        version(2, 'We help some families.', 'ready_for_review', true),
      ],
      approvals: [approval('av-1', 'newer_version_saved')],
    })
    render(<ReviewPage appClient={appClient} client={fake(h).client} />)
    const versions = await screen.findByRole('navigation', { name: 'Versions' })
    expect(
      within(versions).getByText(/Out of date – approval no longer applies/),
    ).toBeInTheDocument()
    expect(within(versions).getByText(/Ready for review – not approved/)).toBeInTheDocument()
    expect(screen.getByLabelText('removed: many')).toBeInTheDocument()
    expect(screen.getByLabelText('added: some')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(
      /approval of version 1 no longer applies because a newer version was saved/,
    )
    expect(
      screen.getByText('Not ready for prefill: the latest version is not approved.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/FIXTURE store/)).toBeInTheDocument()
  })

  it('approves the exact hash only after acknowledging review items', async () => {
    const { client, decisions } = fake(
      hist({ versions: [version(1, 'Text.', 'ready_for_review', true)] }),
    )
    render(<ReviewPage appClient={appClient} client={client} />)
    const approveButton = await screen.findByRole('button', {
      name: /Approve this exact version \(111111111111…\)/,
    })
    fireEvent.click(screen.getByLabelText(/I have read all 1 "Needs your review" items/))
    fireEvent.click(approveButton)
    await waitFor(() => expect(decisions).toHaveLength(1))
    expect(decisions[0]).toMatchObject({
      answer_version_id: 'av-1',
      expected_content_sha256: H('1'),
      expected_snapshot_sha256: H('s'),
      decision: 'approve',
      acknowledge_review_items: true,
    })
  })

  it('explains a refused approval in plain language', async () => {
    const refused: ApiResult<ApprovalRecord> = {
      ok: false,
      status: 403,
      error: { code: 'forbidden', message: 'x', details: { reason: 'not_an_approver' } },
    }
    const { client } = fake(hist({ versions: [version(1, 'Text.', 'ready_for_review', true)] }), {
      decide: async () => refused,
    })
    render(<ReviewPage appClient={appClient} client={client} />)
    fireEvent.click(await screen.findByRole('button', { name: /Approve this exact version/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/not authorized to approve/)
  })

  it('hides decision controls for an older or decided version', async () => {
    const h = hist({
      versions: [version(1, 'A.', 'approved', true)],
      approvals: [approval('av-1', null)],
      prefill_ready: true,
    })
    render(<ReviewPage appClient={appClient} client={fake(h).client} />)
    expect(await screen.findByText(/Ready for prefill/)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Approve this exact version/ }),
    ).not.toBeInTheDocument()
  })

  it('shows blocked reviewed-export reasons and download links for a working export', async () => {
    const blocked: ExportResult = {
      schema_version: '1',
      export_id: null,
      mode: 'reviewed',
      blocked: true,
      blocked_by: [
        {
          question_id: 'mission-q1',
          reason: 'not_approved',
          message: 'The latest version is not approved.',
        },
      ],
      labels: ['REVIEWED - EXACT APPROVED VERSIONS', 'SYNTHETIC DEMO DATA'],
      docx_sha256: null,
      audit_sha256: null,
      created_at: '2026-11-08T00:00:00Z',
    }
    const ok: ExportResult = {
      ...blocked,
      export_id: 'exp-1',
      mode: 'working',
      blocked: false,
      blocked_by: [],
      labels: ['WORKING DRAFT - NOT REVIEWED'],
      docx_sha256: H('d'),
      audit_sha256: H('e'),
    }
    const { client } = fake(hist({}), {
      exportAnswers: async (b) => ({ ok: true, data: b.mode === 'reviewed' ? blocked : ok }),
    })
    render(<ReviewPage appClient={appClient} client={client} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Export reviewed (DOCX)' }))
    expect(await screen.findByText(/Reviewed export blocked/)).toBeInTheDocument()
    expect(screen.getByText(/The latest version is not approved/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Export working draft (DOCX)' }))
    expect(await screen.findByRole('link', { name: 'Download DOCX' })).toHaveAttribute(
      'href',
      '/dl/exp-1/docx',
    )
    expect(screen.getByRole('link', { name: 'Download audit JSON' })).toHaveAttribute(
      'href',
      '/dl/exp-1/audit',
    )
  })

  it('shows reviewer suggestions as suggestions only', async () => {
    const h = hist({
      versions: [version(1, 'A.', 'ready_for_review', true)],
      proposals: [
        {
          proposal_id: 'rp-1',
          answer_version_id: 'av-1',
          role: 'numerical_reviewer',
          findings: [{ concern: 'Confirm the period suits this question.', fact_ids: [] }],
          reviewer: { adapter: 'fake', model: 'fake-deterministic-v1', is_fixture: true },
          provenance: { provenance_class: 'simulated', is_simulated: true },
          created_at: '2026-11-08T00:00:00Z',
        },
      ],
    })
    render(<ReviewPage appClient={appClient} client={fake(h).client} />)
    expect(
      await screen.findByText(/Numbers reviewer \(demo, not an AI model\): Confirm the period/),
    ).toBeInTheDocument()
    expect(screen.getByText(/Suggestions only – they cannot approve anything/)).toBeInTheDocument()
  })
})
