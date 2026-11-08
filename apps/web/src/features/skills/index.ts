// Skills feature entry point. Owner: C. Edit within src/features/skills/.
import type { FeatureEntry } from '../types'
import { SkillsPage } from './Page'

export const skillsFeature: FeatureEntry = {
  id: 'skills',
  label: 'Skills',
  owner: 'C',
  summary: 'Practice-skill proposals, screening and release.',
  Component: SkillsPage,
}
