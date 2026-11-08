// Review feature entry point. Owner: C. Edit within src/features/review/.
import type { FeatureEntry } from '../types'
import { ReviewPage } from './Page'

export const reviewFeature: FeatureEntry = {
  id: 'review',
  label: 'Review',
  owner: 'C',
  summary: 'Checks, evidence and exact-version approval.',
  Component: ReviewPage,
}
