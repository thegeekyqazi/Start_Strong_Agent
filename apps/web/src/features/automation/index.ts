// Intake & Prefill feature entry point. Owner: B2. Edit within src/features/automation/.
import type { FeatureEntry } from '../types'
import { AutomationPage } from './Page'

export const automationFeature: FeatureEntry = {
  id: 'automation',
  label: 'Intake & Prefill',
  owner: 'B2',
  summary: 'Questions, limits, form maps, approved prefill and read-back.',
  Component: AutomationPage,
}
