import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { AnswerVersion, AnswerVersionCreate } from '@strongstart/contracts'
import { demoWorkspace } from '../../shell/components/demoBundle.testdata'
import type { ReviewClient } from '../review/client'
import type { ApplicationsClient } from './client'
import { ApplicationsPage } from './Page'

const appClient: ApplicationsClient = {
  workspace: async () => ({ ok: true, data: demoWorkspace }),
  draft: async () => ({ ok: false, status: 500, error: null }),
  check: async () => ({ ok: false, status: 500, error: null }),
  plan: async () => ({ ok: false, status: 500, error: null }),
}

function saved(n: number): AnswerVersion {
  return {
    schema_version: '1',
    answer_version_id: `av-${n}`,
    answer_id: 'ans-mission-q1',
    question_id: 'mission-q1',
    question_version: 1,
    answer_version: n,
    is_latest: true,
    text: 't',
    content_sha256: 'a'.repeat(64),
    rendered: { text: 't', text_sha256: 'a'.repeat(64), bindings: [], unsupported_markers: [] },
    dependencies: [],
    snapshot_sha256: 'b'.repeat(64),
    check: {
      schema_version: '1',
      question_id: 'mission-q1',
      question_version: 1,
      evidence_bundle_id: 'demo-evidence-a-v1',
      mode: 'reviewed',
      submitted_text_sha256: 'a'.repeat(64),
      rendered: { text: 't', text_sha256: 'a'.repeat(64), bindings: [], unsupported_markers: [] },
      findings: [],
    },
    checked_at: '2026-11-08T00:00:00Z',
    state: 'ready_for_review',
    created_by: 'demo-staff',
    created_at: '2026-11-08T00:00:00Z',
  }
}

it('saves a version with the optimistic expected version and shows its server state', async () => {
  const bodies: AnswerVersionCreate[] = []
  let latest = 1
  const reviewClient: ReviewClient = {
    history: async () => ({
      ok: true,
      data: {
        schema_version: '1',
        question_id: 'mission-q1',
        answer_id: 'ans-mission-q1',
        versions: [saved(1)],
        approvals: [],
        notes: [],
        proposals: [],
        prefill_ready: false,
        store_is_fixture: true,
      },
    }),
    saveVersion: async (body) => {
      bodies.push(body)
      latest += 1
      return { ok: true, data: saved(latest) }
    },
    decide: async () => ({ ok: false, status: 500, error: null }),
    addNote: async () => ({ ok: false, status: 500, error: null }),
    propose: async () => ({ ok: false, status: 500, error: null }),
    exportAnswers: async () => ({ ok: false, status: 500, error: null }),
    downloadUrl: () => '',
  }
  render(<ApplicationsPage client={appClient} reviewClient={reviewClient} />)
  expect(await screen.findByText(/Latest saved: version 1/)).toBeInTheDocument()
  const save = screen.getByRole('button', { name: 'Save version' })
  expect(save).toBeDisabled() // nothing typed yet
  fireEvent.change(screen.getByLabelText('Your answer'), { target: { value: 'Our mission.' } })
  fireEvent.click(save)
  expect(await screen.findByText('Saved as version 2.')).toBeInTheDocument()
  expect(bodies[0]).toMatchObject({
    question_id: 'mission-q1',
    text: 'Our mission.',
    expected_answer_version: 1,
  })
  await waitFor(() => expect(screen.getByText(/Latest saved: version 2/)).toBeInTheDocument())
  expect(screen.getByRole('link', { name: 'Open in Review' })).toHaveAttribute('href', '#/review')
})

it('reports a concurrent save in plain language', async () => {
  const reviewClient: ReviewClient = {
    history: async () => ({
      ok: true,
      data: {
        schema_version: '1',
        question_id: 'mission-q1',
        answer_id: null,
        versions: [],
        approvals: [],
        notes: [],
        proposals: [],
        prefill_ready: false,
        store_is_fixture: true,
      },
    }),
    saveVersion: async () => ({
      ok: false,
      status: 409,
      error: {
        code: 'version_conflict',
        message: 'x',
        details: { reason: 'answer_version_conflict' },
      },
    }),
    decide: async () => ({ ok: false, status: 500, error: null }),
    addNote: async () => ({ ok: false, status: 500, error: null }),
    propose: async () => ({ ok: false, status: 500, error: null }),
    exportAnswers: async () => ({ ok: false, status: 500, error: null }),
    downloadUrl: () => '',
  }
  render(<ApplicationsPage client={appClient} reviewClient={reviewClient} />)
  fireEvent.change(await screen.findByLabelText('Your answer'), { target: { value: 'x' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  expect(await screen.findByText(/Someone saved a newer version/)).toBeInTheDocument()
})
