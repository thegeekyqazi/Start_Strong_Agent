import { fireEvent, render, screen } from '@testing-library/react'
import type { KnowledgeAvailability, KnowledgeSnapshot } from '@strongstart/contracts'
import { KnowledgePage } from './Page'
import type { KnowledgeClient } from './client'

const availability: KnowledgeAvailability = {
  schema_version: '1',
  authenticated: true,
  identity_is_fixture: true,
  environment: 'local',
  storage: 'postgresql',
  status: 'fixture_only',
  detail: 'configured',
}
const ref = {
  source_id: 'source-1',
  source_version_id: 'source-1-v1',
  provenance: { provenance_class: 'simulated' as const, is_simulated: true },
  publication_date: { status: 'known' as const, value: '2026-07-01' },
  content_hash: 'a'.repeat(64),
  verification_status: 'verified' as const,
}
const snapshot: KnowledgeSnapshot = {
  schema_version: '1',
  organization_id: 'demo-org',
  generated_at: '2026-11-07T00:00:00Z',
  is_fixture: true,
  passages: [],
  source_versions: [
    {
      title: 'Synthetic metrics',
      media_type: 'text/plain',
      size_bytes: 120,
      source_reference: ref,
    },
  ],
  evidence_bundles: [
    {
      schema_version: '1',
      bundle_id: 'bundle-1',
      organization_id: 'demo-org',
      pack_id: 'pack-1',
      pack_version_id: 'pack-1-v1',
      access_context: 'fixture:demo-org',
      facts: [
        {
          fact_id: 'fact-1',
          metric_id: 'children-served',
          value: '120',
          raw_value: '120',
          unit: 'children',
          scope: 'all programs',
          population: 'children enrolled',
          reporting_period: '2025-09/2026-06',
          status: 'needs_review',
          supporting_refs: [ref],
          provenance: { provenance_class: 'simulated', is_simulated: true },
        },
      ],
      allowed_fact_ids: ['fact-1'],
      coverage_notes: [],
    },
  ],
}

function client(overrides: Partial<KnowledgeClient> = {}): KnowledgeClient {
  return {
    availability: async () => ({ ok: true, data: availability }),
    snapshot: async () => ({ ok: true, data: snapshot }),
    evidence: async () => ({ ok: true, data: snapshot.evidence_bundles[0] }),
    importText: async () => {
      throw new Error('not expected')
    },
    importPdf: async () => {
      throw new Error('not expected')
    },
    retrieve: async () => ({
      ok: true,
      data: {
        schema_version: '1',
        organization_id: 'demo-org',
        query: 'evidence',
        hits: [],
        retrieval_method: 'lexical-v1',
        truncated: false,
      },
    }),
    ...overrides,
  }
}

describe('KnowledgePage', () => {
  it('shows fixture lineage and exact typed fact fields', async () => {
    render(<KnowledgePage client={client()} />)
    expect(await screen.findByText(/FIXTURE: synthetic data/)).toBeInTheDocument()
    expect(screen.getByText(/source-1-v1/)).toBeInTheDocument()
    expect(screen.getByText('a'.repeat(64))).toBeInTheDocument()
    expect(screen.getByText(/Exact value:/)).toHaveTextContent('120 children')
    expect(screen.getByText(/Reporting period:/)).toHaveTextContent('2025-09/2026-06')
  })

  it('shows a distinct empty state', async () => {
    render(
      <KnowledgePage
        client={client({
          snapshot: async () => ({
            ok: true,
            data: { ...snapshot, source_versions: [], evidence_bundles: [] },
          }),
        })}
      />,
    )
    expect(await screen.findByText(/No knowledge sources/)).toBeInTheDocument()
  })

  it('withholds content after an integrity failure', async () => {
    render(
      <KnowledgePage
        client={client({
          snapshot: async () => ({
            ok: false,
            status: 500,
            error: {
              code: 'internal_error',
              message: 'withheld',
              details: { reason: 'integrity_failure' },
            },
          }),
        })}
      />,
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Content and dependent facts were withheld',
    )
    expect(screen.queryByText('children-served')).not.toBeInTheDocument()
  })

  it('renders an authorized retrieval result with its locator', async () => {
    render(
      <KnowledgePage
        client={client({
          retrieve: async (query) => ({
            ok: true,
            data: {
              schema_version: '1',
              organization_id: 'demo-org',
              query,
              retrieval_method: 'lexical-v1',
              truncated: false,
              hits: [
                {
                  passage: {
                    passage_id: 'pass-1',
                    source_id: 'source-1',
                    source_version_id: 'source-1-v1',
                    locator: 'page:2',
                    exact_text: 'Exact grant evidence',
                  },
                  title: 'Guide',
                  source_reference: { ...ref, locator: 'page:2' },
                  score: 2,
                },
              ],
            },
          }),
        })}
      />,
    )
    const input = await screen.findByLabelText('Search terms')
    fireEvent.change(input, { target: { value: 'grant evidence' } })
    fireEvent.submit(input.closest('form')!)
    expect(await screen.findByText('Exact grant evidence')).toBeInTheDocument()
    expect(screen.getByText(/page:2/)).toBeInTheDocument()
  })
})
