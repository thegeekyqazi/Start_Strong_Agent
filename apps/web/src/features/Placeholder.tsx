import type { FeatureOwner } from './types'

/** Shared entry-point placeholder. Owners replace their page when their feature spec lands. */
export function FeaturePlaceholder({ label, owner }: { label: string; owner: FeatureOwner }) {
  return (
    <section aria-labelledby="feature-heading">
      <h2 id="feature-heading">{label}</h2>
      <p className="badge badge-planned">Planned - not implemented</p>
      <p>
        This is a labelled entry point registered by INIT-001. No {label} functionality exists yet.
        Owner: <strong>{owner}</strong>.
      </p>
    </section>
  )
}
