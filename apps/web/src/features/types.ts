import type { ComponentType } from 'react'

export type FeatureOwner = 'A' | 'B1' | 'B2' | 'C'

/** A registered UI feature. Each lane owns its own feature folder and edits only that entry. */
export interface FeatureEntry {
  /** Matches the API capability `feature` name. */
  id: string
  label: string
  owner: FeatureOwner
  summary: string
  Component: ComponentType
}
