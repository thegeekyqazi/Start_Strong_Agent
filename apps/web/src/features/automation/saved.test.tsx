import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type {
  ApplicationIntakeResult,
  DefinitionList,
  PublishedApplicationVersion,
} from '@strongstart/contracts'
import { SavedDefinitions, type Preview } from './saved'

const sha = 'b'.repeat(64)
const intake = {
  import_id: 'imp-1',
  is_fixture: true,
  mode_label: 'FIXTURE - engineering-derived',
  approval_status: 'not_approved',
  persisted: false,
  input: { sha256: sha, byte_size: 10 },
  provenance: { provenance_class: 'engineering_derived', is_simulated: true },
  coverage: { status: 'supported_complete', questions_extracted: 1 },
  questions: [
    {
      question_id: 'rp-mission',
      order: 0,
      text: {
        text: 'Mission <script>window.pwned=1</script>',
        display_text: 'Mission <script>window.pwned=1</script>',
        locator: { kind: 'json_pointer', value: '/questions/0/text' },
      },
      scope: 'organization',
      answer_kind: 'text',
      required_status: 'required',
      limits: [],
      limit_conflicts: [],
      source_ref: {
        source_id: 'fixture-x',
        source_version_id: 'fixture-x-1',
        locator: '/questions/0',
        provenance: { provenance_class: 'engineering_derived', is_simulated: true },
        publication_date: { status: 'unknown' },
        content_hash: 'b'.repeat(64),
        verification_status: 'unverified',
      },
      action_state: 'no_blocker_detected_not_approved',
    },
  ],
  findings: [],
} as unknown as ApplicationIntakeResult

const defId = 'def-' + '1'.repeat(26)
const pub = {
  definition_id: defId,
  version: 1,
  question_set_id: `qs-${defId}-v1`,
  saved_by: 'demo-staff',
  saved_at: '2026-11-08T12:00:00Z',
  integrity: { raw_input_sha256: sha, raw_input_size: 10, normalized_digest: 'c'.repeat(64) },
  question_set: { questions: [{ question_id: `${defId}:rp-mission` }] },
  intake,
  unresolved: [{ question_id: `${defId}:rp-mission`, kind: 'scope_unknown', detail: 'not stated' }],
  context: { opportunity_id: 'demo-gos', opportunity_basis: 'fixture_registry' },
  is_fixture: true,
  mode_label: 'FIXTURE - engineering-derived',
  review_status: 'saved_not_reviewed',
  approval_status: 'not_approved',
  prefill_permitted: false,
} as unknown as PublishedApplicationVersion

const list = (items: DefinitionList['items']): DefinitionList => ({
  items,
  next_cursor: null,
  more: false,
  incomplete: false,
  limit: 20,
})

type Route = (url: string, init?: RequestInit) => Promise<{ status: number; body: unknown }>

function mockFetch(route: Route) {
  const calls: { url: string; body: unknown }[] = []
  vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : null })
    const { status, body } = await route(url, init)
    return new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  return calls
}

const preview = (token: number): Preview => ({
  token,
  result: intake,
  source: { mode: 'fixture', fixture_id: 'rep-portal-definition-v1' },
})

afterEach(() => vi.unstubAllGlobals())

describe('SavedDefinitions', () => {
  it('saves the exact preview hash with one idempotency key and shows the pending connection', async () => {
    const calls = mockFetch(async (_url, init) =>
      init?.method === 'POST'
        ? { status: 201, body: { replayed: false, publication: pub } }
        : { status: 200, body: list([]) },
    )
    render(<SavedDefinitions preview={preview(1)} />)
    await screen.findByText('No saved definitions yet.')
    fireEvent.click(screen.getByRole('button', { name: 'Save definition for drafting' }))
    expect(await screen.findByText(/connection to Applications pending/)).toBeInTheDocument()
    const post = calls.find((c) => c.url.endsWith('/definitions') && c.body)
    expect(post?.body).toMatchObject({
      expected_input_sha256: sha,
      definition_id: null,
      expected_version: null,
      funding_case_id: null,
    })
    expect(JSON.stringify(post?.body)).not.toMatch(/organization|approved|actor/)
    expect(screen.getByText(`qs-${defId}-v1`)).toBeInTheDocument()
  })

  it('never relabels a newer preview with a late save response', async () => {
    let release: (v: { status: number; body: unknown }) => void = () => undefined
    mockFetch((_url, init) =>
      init?.method === 'POST'
        ? new Promise((resolve) => {
            release = resolve
          })
        : Promise.resolve({ status: 200, body: list([]) }),
    )
    const { rerender } = render(<SavedDefinitions preview={preview(1)} />)
    await screen.findByText('No saved definitions yet.')
    fireEvent.click(screen.getByRole('button', { name: 'Save definition for drafting' }))
    rerender(<SavedDefinitions preview={preview(2)} />) // staff imported something else
    await act(async () => release({ status: 201, body: { replayed: false, publication: pub } }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Save definition for drafting' })).toBeEnabled(),
    )
    expect(screen.queryByText(/connection to Applications pending/)).toBeNull()
  })

  it('keeps the preview on a conflict and explains it', async () => {
    mockFetch(async (_url, init) =>
      init?.method === 'POST'
        ? {
            status: 409,
            body: {
              code: 'version_conflict',
              message: 'x',
              details: { reason: 'input_changed' },
            },
          }
        : { status: 200, body: list([]) },
    )
    render(<SavedDefinitions preview={preview(1)} />)
    await screen.findByText('No saved definitions yet.')
    fireEvent.click(screen.getByRole('button', { name: 'Save definition for drafting' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('[input_changed]')
    expect(screen.getByText(new RegExp(sha))).toBeInTheDocument()
  })

  it('reopens a saved definition as inert text, copies its ID and shows integrity failures', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    mockFetch(async (url) =>
      url.endsWith(`/definitions/${defId}`)
        ? { status: 200, body: pub }
        : {
            status: 200,
            body: list([
              {
                definition_id: defId,
                status: 'ok',
                current_version: 1,
                question_count: 1,
                unresolved_count: 1,
                title: 'FIXTURE definition',
              },
              {
                definition_id: 'def-' + '2'.repeat(26),
                status: 'integrity_failure',
                detail: 'This saved definition failed verification; content withheld.',
              },
            ]),
          },
    )
    const { container } = render(<SavedDefinitions preview={null} />)
    expect(await screen.findByText(/failed verification; content withheld/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: `Reopen def-${'2'.repeat(26)}` })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: `Reopen ${defId}` }))
    expect(await screen.findByTestId('saved-qs-id')).toHaveTextContent(`qs-${defId}-v1`)
    expect(container.querySelector('script')).toBeNull()
    expect((window as unknown as { pwned?: number }).pwned).toBeUndefined()
    fireEvent.click(screen.getByRole('button', { name: 'Copy question-set ID for Dev C' }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(`qs-${defId}-v1`))
    expect(screen.getByText(/saved not reviewed/)).toBeInTheDocument()
  })
})
