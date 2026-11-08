// Find Funding feature entry point. Owner: B1. Edit within src/features/funding/.
import type { FeatureEntry } from '../types'
import { FundingPage } from './Page'

export const fundingFeature: FeatureEntry = {
  id: 'funding',
  label: 'Find Funding',
  owner: 'B1',
  summary: 'Discovery, official capture, eligibility and deadlines.',
  Component: FundingPage,
}
