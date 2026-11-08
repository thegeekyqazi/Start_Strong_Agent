// Knowledge feature entry point. Owner: A. Edit within src/features/knowledge/.
import type { FeatureEntry } from '../types'
import { KnowledgePage } from './Page'

export const knowledgeFeature: FeatureEntry = {
  id: 'knowledge',
  label: 'Knowledge',
  owner: 'A',
  summary: 'Packs, sources, facts and conflicts.',
  Component: KnowledgePage,
}
