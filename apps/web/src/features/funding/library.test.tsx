import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { CaptureCatalogPage, CapturedDocument } from '@strongstart/contracts'
import { INTAKE_REFERENCE_KEY } from '../automation/handoff'
import type { FundingClient } from './client'
import { IntakeReferences, SavedCaptures } from './library'

const capId = 'cap-' + 'a'.repeat(32)
const doc = {
  capture_id: capId,
  artifacts: [
    { artifact_id: `${capId}-markdown`, representation: 'provider_markdown' },
    { artifact_id: `${capId}-html`, representation: 'provider_html' },
    { artifact_id: `${capId}-raw-html`, representation: 'provider_raw_html' },
  ],
  supported_import_representations: ['provider_html', 'provider_raw_html'],
} as unknown as CapturedDocument

const page = (over: Partial<CaptureCatalogPage> = {}): CaptureCatalogPage => ({
  items: [
    {
      capture_id: capId,
      status: 'ok',
      page_title: 'FIXTURE <script>window.pwned=1</script>',
      requested_url: 'https://demo-funder.example/programs/community-grants',
      captured_at: '2026-11-08T01:00:00Z',
      provider: 'fixture-capture',
      provider_mode: 'fixture',
      coverage: 'complete',
      representation_count: 3,
      authority_review: 'confirmed_official',
      is_simulated: true,
      content_integrity: 'not_checked_in_listing',
    },
    {
      capture_id: 'cap-' + 'b'.repeat(32),
      status: 'corrupt',
      content_integrity: 'not_checked_in_listing',
      detail: 'The stored record is missing or failed validation; no content shown.',
    },
  ],
  next_cursor: null,
  more: false,
  incomplete: false,
  backfill_status: 'complete',
  backfill_pending: 0,
  limit: 20,
  ...over,
})

function client(over: Partial<FundingClient> = {}): FundingClient {
  return {
    availability: vi.fn(),
    search: vi.fn(),
    capture: vi.fn(),
    content: vi.fn(),
    getCapture: async () => ({ ok: true, data: doc }),
    listCaptures: async () => ({ ok: true, data: page() }),
    ...over,
  } as FundingClient
}

afterEach(() => {
  vi.unstubAllGlobals()
  window.sessionStorage.clear()
  window.location.hash = ''
})

describe('SavedCaptures', () => {
  it('lists saved captures as inert text, marks corrupt entries and opens by row', async () => {
    const { container } = render(
      <SavedCaptures client={client()} renderCapture={(d) => <p>opened {d.capture_id}</p>} />,
    )
    expect(await screen.findByText(/no content shown/)).toBeInTheDocument()
    expect(screen.getByText('Corrupt')).toBeInTheDocument()
    expect(container.querySelector('script')).toBeNull()
    expect((window as unknown as { pwned?: number }).pwned).toBeUndefined()
    fireEvent.click(screen.getByRole('button', { name: `Open ${capId}` }))
    expect(await screen.findByText(`opened ${capId}`)).toBeInTheDocument()
  })

  it('shows pending backfill honestly and validates open-by-ID before calling the API', async () => {
    const getCapture = vi.fn()
    render(
      <SavedCaptures
        client={client({
          getCapture,
          listCaptures: async () => ({
            ok: true,
            data: page({ items: [], backfill_status: 'pending', backfill_pending: 3 }),
          }),
        })}
        renderCapture={() => null}
      />,
    )
    expect(await screen.findByText(/3 pending/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Open a capture by ID'), {
      target: { value: '../../etc' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Open capture' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/cap-<32 hex/)
    expect(getCapture).not.toHaveBeenCalled()
  })
})

describe('IntakeReferences', () => {
  it('offers exact colon references only for importable artifacts, separate from JSON', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    render(<IntakeReferences doc={doc} />)
    const refs = screen.getAllByTestId('intake-reference').map((n) => n.textContent)
    expect(refs).toEqual([`${capId}:${capId}-html`, `${capId}:${capId}-raw-html`])
    expect(screen.queryByText(/provider_markdown/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Copy intake reference (provider_html)' }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(`${capId}:${capId}-html`))
  })

  it('hands IDs to the Automation page through session storage', () => {
    render(<IntakeReferences doc={doc} />)
    fireEvent.click(
      screen.getByRole('button', { name: 'Use provider_raw_html in application intake' }),
    )
    expect(window.sessionStorage.getItem(INTAKE_REFERENCE_KEY)).toBe(`${capId}:${capId}-raw-html`)
    expect(window.location.hash).toBe('#/automation')
  })
})
