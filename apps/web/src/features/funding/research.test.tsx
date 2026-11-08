import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type {
  CapturedDocument,
  ChangeObservation,
  SearchProfileVersion,
  SearchRunRecord,
} from '@strongstart/contracts'
import type { ApiResult, FundingClient } from './client'
import { Recheck, SavedSearches } from './research'

const ok = <T,>(data: T) => Promise.resolve({ ok: true, data } as ApiResult<T>)
const page = <T,>(items: T[]) => ({
  items,
  next_cursor: null,
  more: false,
  incomplete: false,
  limit: 20,
})
const pid = 'prof-' + '1'.repeat(26)
const profile = {
  profile_id: pid,
  version: 1,
  label: 'FIXTURE early learning',
  query_preview: 'early learning grant funding',
  public_fields_used: ['interests'],
} as unknown as SearchProfileVersion
const run = (id: string, outcome: string, urls: string[] = []) =>
  ({
    run_id: id,
    profile_version: 1,
    outcome,
    error_reason: outcome === 'success' ? null : 'provider_unavailable',
    error_message: outcome === 'success' ? null : 'search unavailable',
    completed_at: '2026-11-08T01:00:00Z',
    normalized_urls: urls,
  }) as unknown as SearchRunRecord

function client(over: Partial<FundingClient> = {}): FundingClient {
  return {
    listProfiles: () => ok(page([profile])),
    saveProfile: vi.fn(() => ok(profile)),
    runProfile: vi.fn(() => ok(run('run-' + 'a'.repeat(26), 'unavailable'))),
    listRuns: () =>
      ok(
        page([
          run('run-' + 'b'.repeat(26), 'success', ['https://a.example/']),
          run('run-' + 'c'.repeat(26), 'success'),
        ]),
      ),
    compareRuns: () =>
      ok({
        newly_seen: [],
        seen_again: [],
        not_seen_in_this_result_set: ['https://a.example/'],
        note: 'Result sets are bounded and provider-ranked.',
      }),
    recheck: vi.fn(),
    listObservations: vi.fn(),
    ...over,
  } as unknown as FundingClient
}

describe('SavedSearches', () => {
  it('shows the exact public query, keeps failed runs and never calls absence closure', async () => {
    const c = client()
    render(<SavedSearches client={c} />)
    expect(await screen.findByText('early learning grant funding')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Run search now (FIXTURE early learning)' }))
    expect(
      await screen.findByText(/unavailable: search unavailable \(kept in history/),
    ).toBeInTheDocument()
    expect(vi.mocked(c.runProfile).mock.calls[0][1]).toMatchObject({ profile_version: 1 })
    fireEvent.change(await screen.findByLabelText('Earlier run'), {
      target: { value: 'run-' + 'b'.repeat(26) },
    })
    fireEvent.change(screen.getByLabelText('Later run'), {
      target: { value: 'run-' + 'c'.repeat(26) },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Compare runs' }))
    expect(
      await screen.findByText(/Not seen in this result set \(not removed or closed\)/),
    ).toBeInTheDocument()
  })
})

describe('Recheck', () => {
  it('rechecks one selected capture and shows a change as needing re-review', async () => {
    const observation = {
      observation_id: 'obs-' + 'd'.repeat(26),
      overall: 'changed',
      observed_at: '2026-11-08T02:00:00Z',
      new_capture_id: 'cap-' + 'e'.repeat(32),
      explanation: 'At least one representation changed; not by itself a policy change.',
      comparisons: [{ representation: 'provider_markdown', outcome: 'changed' }],
      text_diff: '-100,000\n+90,000',
      downstream_effects: ['Local Dev B handling only: A4 and C3 are not implemented here.'],
    } as unknown as ChangeObservation
    const c = client({ recheck: vi.fn(() => ok(observation)) })
    const doc = {
      capture_id: 'cap-' + 'f'.repeat(32),
      requested_url: 'https://demo-funder.example/u',
    }
    render(<Recheck doc={doc as unknown as CapturedDocument} client={c} />)
    fireEvent.click(screen.getByRole('button', { name: 'Capture again and compare' }))
    expect(
      await screen.findByText(/Changed \(stored bytes differ; re-review needed\)/),
    ).toBeInTheDocument()
    expect(screen.getByText(/A4 and C3 are not implemented/)).toBeInTheDocument()
    await waitFor(() => expect(c.recheck).toHaveBeenCalled())
    expect(vi.mocked(c.recheck).mock.calls[0][1]).toMatchObject({
      funding_case_id: null,
      funding_case_version: null,
    })
  })
})
