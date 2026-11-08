import { render, screen } from '@testing-library/react'
import type { Fact } from '@strongstart/contracts'
import { EvidenceCard, FindingRow, HashChip, isSafeHref, StatusDot } from '.'
import { demoEvidence, demoFact } from './demoBundle.testdata'

describe('EvidenceCard', () => {
  it('renders value, unit, period, source, locator and labelled signals from the fixture', () => {
    render(<EvidenceCard fact={demoFact} coverageNotes={demoEvidence.coverage_notes} />)
    expect(screen.getByText('120 children')).toBeInTheDocument()
    expect(screen.getByText('2025-09/2026-06')).toBeInTheDocument()
    expect(
      screen.getByText(/demo-synthetic-metrics \(version demo-synthetic-metrics-v1\)/),
    ).toBeInTheDocument()
    expect(screen.getByText('tests/fixtures/demo/demo-bundle-v1.json#facts')).toBeInTheDocument()
    expect(screen.getByText(/Not yet verified by staff/)).toBeInTheDocument()
    expect(screen.getByText(/Simulated – synthetic demo data/)).toBeInTheDocument()
    expect(screen.getByText(/historical period, not a current figure/)).toBeInTheDocument()
    expect(screen.queryByText(/Verified by staff/)).not.toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('says unknown instead of guessing missing values', () => {
    const unknown: Fact = {
      ...demoFact,
      value: null,
      unit: null,
      reporting_period: null,
      population: null,
    }
    render(<EvidenceCard fact={unknown} />)
    expect(screen.getByText(/Value: unknown/)).toBeInTheDocument()
    expect(screen.getByText(/Unit: unknown/)).toBeInTheDocument()
    expect(screen.getAllByText('unknown').length).toBeGreaterThanOrEqual(2)
  })
})

describe('FindingRow', () => {
  it('shows badge, message, origin and an in-app go-to link', () => {
    render(
      <FindingRow
        origin="question_data"
        outcome="notice"
        message="Two limits."
        href="#/applications"
      />,
    )
    expect(screen.getByText('Note')).toBeInTheDocument()
    expect(screen.getByText('Two limits.')).toBeInTheDocument()
    expect(screen.getByText(/not a validation check/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go to' })).toHaveAttribute('href', '#/applications')
  })

  it('never renders unsafe schemes as links (SEC-07)', () => {
    for (const href of [
      'javascript:alert(1)',
      'https://evil.example',
      '//evil.example',
      'data:text/html,x',
    ]) {
      expect(isSafeHref(href)).toBe(false)
    }
    render(<FindingRow origin="check" outcome="fail" message="x" href="javascript:alert(1)" />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText(/link not opened/)).toBeInTheDocument()
    expect(screen.getByText('Problem found')).toBeInTheDocument()
  })

  it('renders HTML in messages as inert text', () => {
    const { container } = render(
      <FindingRow
        origin="check"
        outcome="needs_review"
        message={'<img src=x onerror="alert(1)"><b>bold</b>'}
      />,
    )
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('b')).toBeNull()
    expect(screen.getByText(/<img src=x/)).toBeInTheDocument()
  })

  it('labels a pass as covering only its own check', () => {
    render(<FindingRow origin="check" outcome="pass" message="248 of 250 words" />)
    expect(screen.getByText('Passed this check only')).toBeInTheDocument()
  })
})

describe('StatusDot', () => {
  it.each([
    ['draft', 'Draft – not reviewed'],
    ['needs_attention', 'Needs attention'],
    ['approved', 'Approved (this exact version)'],
    ['stale', 'Out of date – approval no longer applies'],
    ['checking', 'Checking…'],
    ['ready_for_review', 'Ready for review – not approved'],
    ['rejected', 'Rejected by reviewer'],
  ] as const)('%s has a text label, not colour alone', (status, label) => {
    render(<StatusDot status={status} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })
})

describe('HashChip', () => {
  const hash = 'a'.repeat(12) + 'b'.repeat(52)
  it('shows a 12-character prefix with the full hash available', () => {
    render(<HashChip hash={hash} />)
    expect(screen.getByText('aaaaaaaaaaaa…')).toBeInTheDocument()
    expect(screen.getByTitle(hash)).toBeInTheDocument()
  })
  it('flags invalid and missing hashes', () => {
    render(
      <>
        <HashChip hash="<script>" />
        <HashChip hash={null} />
      </>,
    )
    expect(screen.getByText(/invalid hash/)).toBeInTheDocument()
    expect(screen.getByText(/not computed/)).toBeInTheDocument()
  })
})
