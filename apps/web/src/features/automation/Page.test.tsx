import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type {
  ApplicationIntakeResult,
  AutomationAvailability,
  FormInspectionResult,
} from '@strongstart/contracts'
import { AutomationPage } from './Page'

const loc = { kind: 'json_pointer' as const, value: '/questions/0/text' }
const ref = {
  source_id: 'fixture-x',
  source_version_id: 'fixture-x-1',
  locator: '/questions/0',
  provenance: { provenance_class: 'engineering_derived' as const, is_simulated: true },
  publication_date: { status: 'unknown' as const },
  content_hash: 'a'.repeat(64),
  verification_status: 'unverified' as const,
}

function availability(browser: AutomationAvailability['browser_status']): AutomationAvailability {
  return {
    capabilities: [
      { feature: 'automation.intake', owner: 'B2', status: 'available', detail: 'intake' },
      {
        feature: 'automation.approved_prefill',
        owner: 'B2',
        status: 'not_implemented',
        detail: 'later',
      },
      {
        feature: 'automation.final_submission',
        owner: 'B2',
        status: 'unavailable',
        detail: 'staff only',
      },
    ],
    import_modes: [
      { mode: 'fixture', status: 'fixture_only', max_bytes: 1000, detail: '' },
      { mode: 'structured_json', status: 'available', max_bytes: 50, detail: '' },
      { mode: 'html', status: 'available', max_bytes: 1000, detail: '' },
      { mode: 'capture', status: 'fixture_only', max_bytes: 1000, detail: '' },
    ],
    browser_status: browser,
    browser_detail: 'detail',
    fixture_mode: true,
    fixtures: [
      {
        fixture_id: 'rep-portal-definition-v1',
        kind: 'structured_definition',
        variant: 'representative',
        label: 'FIXTURE',
        description: 'def',
      },
      {
        fixture_id: 'rep-portal-v1-duplicate',
        kind: 'portal',
        variant: 'malformed',
        label: 'FIXTURE',
        description: 'dup',
      },
    ],
  }
}

const intakeResult: ApplicationIntakeResult = {
  import_id: 'imp-1',
  is_fixture: true,
  mode_label: 'FIXTURE - engineering-derived representative material',
  approval_status: 'not_approved',
  persisted: false,
  input: {
    representation_id: 'rep-1',
    origin: 'fixture',
    representation_type: 'structured_json',
    media_type: 'application/json',
    byte_size: 10,
    sha256: 'b'.repeat(64),
    integrity: 'computed_on_receipt',
    parser_id: 'b2-structured-json',
    parser_version: '1',
    normalization_version: 'b2-norm/1',
    storage: 'nonpersistent_response',
  },
  provenance: ref.provenance,
  coverage: {
    status: 'supported_complete',
    questions_extracted: 1,
    controls_seen: 0,
    unsupported_elements: 0,
  },
  questions: [
    {
      question_id: 'rp-partnership',
      order: 0,
      original_number: '7',
      text: {
        text: 'Describe <img src=x onerror="window.pwned=1"> partners',
        display_text: 'Describe <img src=x onerror="window.pwned=1"> partners',
        locator: loc,
      },
      scope: 'organization',
      answer_kind: 'text',
      required_status: 'conditional',
      limits: [
        {
          limit_id: 'l1',
          kind: 'structured_definition',
          maximum: '350',
          unit: 'words',
          convention_status: 'unknown_pending_confirmation',
          authority_status: 'imported_provisional',
          evidence: {
            text: 'Maximum 350 words.',
            display_text: 'Maximum 350 words.',
            locator: loc,
          },
        },
        {
          limit_id: 'l2',
          kind: 'structured_definition',
          maximum: '500',
          unit: 'words',
          convention_status: 'unknown_pending_confirmation',
          authority_status: 'imported_provisional',
          evidence: { text: 'up to 500 words', display_text: 'up to 500 words', locator: loc },
        },
      ],
      limit_conflicts: [
        {
          conflict_id: 'c1',
          kind: 'competing_instruction_limits',
          limit_ids: ['l1', 'l2'],
          description: 'Competing limits: 350 vs 500',
          resolution: 'unresolved',
        },
      ],
      source_ref: ref,
      action_state: 'held_unresolved_requirement',
      hold_reasons: ['limit_conflict:c1'],
    },
  ],
  findings: [
    {
      code: 'limit_conflict',
      severity: 'blocker',
      message: 'Imported instructions disagree',
      question_id: 'rp-partnership',
    },
  ],
}

const inspection: Partial<FormInspectionResult> = {
  fixture_id: 'rep-portal-v1-duplicate',
  mode_label: 'FIXTURE read-only inspection',
  map_status: 'invalid',
  fingerprint_status: 'changed',
  fingerprint: 'c'.repeat(64),
  expected_form_version: 1,
  browser_name: 'chromium',
  browser_version: '1',
  activity: {
    requests_allowed: 1,
    requests_blocked: 0,
    mutation_requests_blocked: 0,
    fixture_server_mutation_hits: 0,
    popups_blocked: 0,
    downloads_blocked: 0,
    navigations_blocked: 0,
    inspector_actions: [],
  },
  mappings: [
    {
      question_id: 'rp-services',
      expected_field_id: 'services-field',
      expected_selector: '#services',
      expected_kind: 'single',
      expected_type: 'textarea',
      status: 'ambiguous',
      observed_count: 2,
      requirement_hold: false,
      message: '2 controls match #services; none chosen.',
    },
  ],
  fields: [],
  findings: [{ code: 'mapping_ambiguous', severity: 'blocker', message: 'two matches' }],
}

type Handler = (url: string, init?: RequestInit) => { status: number; body: unknown }

const EMPTY_DEFINITIONS = {
  items: [],
  next_cursor: null,
  more: false,
  incomplete: false,
  limit: 20,
}

// Routes the saved-definitions panel (DEV-B-BUNDLE-002 M1) calls on mount get a contract-shaped
// empty list unless a test handles them itself (handleDefinitions: true).
function mockFetch(handler: Handler, opts: { handleDefinitions?: boolean } = {}) {
  const calls: { url: string; body: unknown }[] = []
  vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : null })
    const { status, body } =
      !opts.handleDefinitions && url.endsWith('/api/automation/definitions')
        ? { status: 200, body: EMPTY_DEFINITIONS }
        : handler(url, init)
    return new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  return calls
}

afterEach(() => vi.unstubAllGlobals())

describe('AutomationPage', () => {
  it('shows granular availability and fixture mode', async () => {
    mockFetch(() => ({ status: 200, body: availability('installed_not_launched') }))
    render(<AutomationPage />)
    expect(await screen.findByText('automation.final_submission')).toBeInTheDocument()
    expect(screen.getByText('Not implemented')).toBeInTheDocument()
    expect(screen.getByText(/FIXTURE MODE/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Inspect fields' })).toBeEnabled()
  })

  it('renders imported content as inert text with conflicts held and not approved', async () => {
    const calls = mockFetch((url) =>
      url.endsWith('/intake')
        ? { status: 200, body: intakeResult }
        : { status: 200, body: availability('installed_not_launched') },
    )
    const { container } = render(<AutomationPage />)
    await screen.findByText('automation.intake')
    fireEvent.click(screen.getByRole('button', { name: 'Import' }))
    expect(await screen.findByText(/Competing limits: 350 vs 500/)).toBeInTheDocument()
    expect(calls.find((c) => c.url.endsWith('/intake'))?.body).toEqual({
      source: { mode: 'fixture', fixture_id: 'rep-portal-definition-v1' },
    })
    expect(container.querySelector('img')).toBeNull()
    expect((window as unknown as { pwned?: number }).pwned).toBeUndefined()
    expect(screen.getAllByText(/<img src=x onerror=/).length).toBeGreaterThan(0)
    expect(screen.getByText('Held')).toBeInTheDocument()
    expect(screen.getByText('not_approved')).toBeInTheDocument()
    expect(screen.getByText(/exists only in this response/)).toBeInTheDocument()
    const evidence = screen.getByRole('complementary')
    expect(within(evidence).getByText('Maximum 350 words.')).toBeInTheDocument()
    expect(within(evidence).getByText('up to 500 words')).toBeInTheDocument()
  })

  it('explains invalid JSON and oversized input distinctly', async () => {
    mockFetch((url) =>
      url.endsWith('/intake')
        ? {
            status: 422,
            body: {
              code: 'validation_failed',
              message: 'invalid JSON',
              details: { reason: 'malformed_definition' },
            },
          }
        : { status: 200, body: availability('installed_not_launched') },
    )
    render(<AutomationPage />)
    await screen.findByText('automation.intake')
    fireEvent.click(screen.getByLabelText(/Structured JSON definition/))
    fireEvent.change(screen.getByLabelText('Definition JSON'), { target: { value: '{bad' } })
    fireEvent.click(screen.getByRole('button', { name: 'Import' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('[malformed_definition]')
    fireEvent.change(screen.getByLabelText('Definition JSON'), {
      target: { value: 'x'.repeat(60) },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Import' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('[input_too_large]'))
  })

  it('disables inspection when the browser is unavailable', async () => {
    mockFetch(() => ({ status: 200, body: availability('unavailable') }))
    render(<AutomationPage />)
    await screen.findByText('automation.intake')
    expect(screen.getByRole('button', { name: 'Inspect fields' })).toBeDisabled()
  })

  it('shows mapping conflicts from inspection and exports without approval', async () => {
    const calls = mockFetch((url) => {
      if (url.endsWith('/inspect-fixture')) return { status: 200, body: inspection }
      if (url.endsWith('/intake')) return { status: 200, body: intakeResult }
      if (url.endsWith('/export-definition'))
        return {
          status: 200,
          body: { export_id: 'exp-1', label: 'B2 handoff - NOT APPROVED - FIXTURE' },
        }
      return { status: 200, body: availability('installed_not_launched') }
    })
    render(<AutomationPage />)
    await screen.findByText('automation.intake')
    fireEvent.change(screen.getByLabelText('Portal fixture'), {
      target: { value: 'rep-portal-v1-duplicate' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Inspect fields' }))
    expect(await screen.findByText('ambiguous')).toBeInTheDocument()
    expect(screen.getByText('invalid')).toBeInTheDocument()
    expect(calls.find((c) => c.url.endsWith('/inspect-fixture'))?.body).toEqual({
      fixture_id: 'rep-portal-v1-duplicate',
    })
    fireEvent.click(screen.getByRole('button', { name: 'Import' }))
    fireEvent.click(await screen.findByRole('button', { name: /Export JSON handoff/ }))
    expect(await screen.findByText(/NOT APPROVED/)).toBeInTheDocument()
    expect(calls.find((c) => c.url.endsWith('/export-definition'))?.body).toEqual({
      source: { mode: 'fixture', fixture_id: 'rep-portal-definition-v1' },
      inspect_fixture_id: 'rep-portal-v1-duplicate',
    })
  })
})
