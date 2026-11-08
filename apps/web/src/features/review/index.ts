// Review feature entry point. Owner: C. Edit within src/features/review/.
import type { FeatureEntry } from '../types'
import { ReviewPage } from './Page'

export const reviewFeature: FeatureEntry = {
  id: 'review',
  label: 'Review',
  owner: 'C',
  summary:
    'Saved versions, exact-version approval, staleness and DOCX/audit export (fixture store).',
  Component: ReviewPage,
}
