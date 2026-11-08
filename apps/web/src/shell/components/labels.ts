// Shared plain-language labels and helpers for C's shell components (owner: C).
// Kept separate from component files so React fast refresh works (oxlint only-export-components).
import type { Fact } from '@strongstart/contracts'

export const FACT_STATUS: Record<Fact['status'], string> = {
  extracted: 'Extracted – not reviewed',
  needs_review: 'Not yet verified by staff',
  verified: 'Verified by staff',
  conflicting: 'Conflicts with another source',
  superseded: 'Replaced by a newer figure',
}
export const SOURCE_STATUS: Record<string, string> = {
  unverified: 'Source not verified',
  verified: 'Source verified',
  conflicting: 'Source conflicts',
}
export const PROVENANCE_LABEL: Record<string, string> = {
  simulated: 'Simulated – synthetic demo data',
  engineering_derived: 'Derived from the engineering plan, not the original guide',
  supplied: 'Supplied by partner',
  public: 'Public source',
}

export const factStatusLabel = (status: Fact['status']) => FACT_STATUS[status]

export function isSafeHref(href: string): boolean {
  return href.startsWith('#/') || (href.startsWith('/') && !href.startsWith('//'))
}
