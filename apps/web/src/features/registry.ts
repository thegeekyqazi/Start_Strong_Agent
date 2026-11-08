// Feature registration (INIT-001). Lanes edit their own feature folder, not this list,
// for their first tickets. Shared shell ownership: Dev C.
import { applicationsFeature } from './applications'
import { automationFeature } from './automation'
import { fundingFeature } from './funding'
import { knowledgeFeature } from './knowledge'
import { reviewFeature } from './review'
import { skillsFeature } from './skills'
import type { FeatureEntry } from './types'

export const FEATURES: readonly FeatureEntry[] = [
  knowledgeFeature,
  fundingFeature,
  automationFeature,
  applicationsFeature,
  reviewFeature,
  skillsFeature,
]
