// Applications feature entry point. Owner: C. Edit within src/features/applications/.
import type { FeatureEntry } from '../types'
import { ApplicationsPage } from './Page'

export const applicationsFeature: FeatureEntry = {
  id: 'applications',
  label: 'Applications',
  owner: 'C',
  summary: 'Application workspace and draft proposals (fixture-backed in C1).',
  Component: ApplicationsPage,
}
