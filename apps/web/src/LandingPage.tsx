import { FEATURES } from './features/registry'

const FLOW = ['funding', 'automation', 'knowledge', 'applications', 'review'] as const

const PRINCIPLES = [
  {
    title: 'Source-linked evidence',
    body: 'Keep the source, version, locator, reporting period and provenance attached to the facts used in an answer.',
  },
  {
    title: 'Meaningful human review',
    body: 'Review exact answer versions and make edits, evidence changes and stale approvals visible before transfer.',
  },
  {
    title: 'Safe form transfer',
    body: 'Prepare approved content for browser-assisted transfer while staff retain control of final submission and signing.',
  },
] as const

const HOW_IT_WORKS = [
  {
    step: 'Start with the opportunity',
    action:
      'Find the funder, capture the official page and bring its requirements into the workspace.',
    outcome: 'A source-backed opportunity and structured questions.',
  },
  {
    step: 'Build with your evidence',
    action:
      'Connect organizational facts, draft each response and run the source and numeric checks.',
    outcome: 'Checked answers that show where every important claim came from.',
  },
  {
    step: 'Review before transfer',
    action:
      'Review the exact answer version, resolve issues and approve only the version staff intend to use.',
    outcome: 'An approved snapshot ready for controlled form transfer.',
  },
] as const

export function LandingPage() {
  const flow = FLOW.map((id) => FEATURES.find((feature) => feature.id === id)).filter(
    (feature): feature is (typeof FEATURES)[number] => Boolean(feature),
  )
  const skills = FEATURES.find((feature) => feature.id === 'skills')
  const landingFeatures = skills ? [...flow, skills] : flow

  return (
    <div className="landing-page">
      <section className="landing-hero" aria-labelledby="landing-title">
        <div className="landing-hero-copy">
          <h2 id="landing-title">Build stronger grants with evidence.</h2>
          <p className="landing-lead">
            Strong Start brings funding discovery, official requirements, organizational evidence,
            drafting and review into one traceable workflow.
          </p>
          <div className="landing-actions">
            <a className="button-primary" href="#/funding">
              Open the workspace
            </a>
            <a className="button-secondary" href="#landing-features">
              See how it works
            </a>
          </div>
          <p className="landing-assurance">
            Staff stay in control of approvals, browser transfer and final submission.
          </p>
        </div>

        <div className="landing-flow" aria-label="Strong Start workflow preview">
          <div className="landing-flow-head">
            <p>One connected workflow</p>
            <span>Source to submission</span>
          </div>
          <ol>
            {flow.map((feature, index) => (
              <li key={feature.id}>
                <span>{index + 1}</span>
                <div>
                  <strong>{feature.label}</strong>
                  <p>{feature.summary}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="landing-how" aria-labelledby="how-title">
        <div className="landing-section-heading">
          <h2 id="how-title">Three moves from funding lead to reviewed answer.</h2>
          <p>Each stage has a clear job and a clear handoff to the next one.</p>
        </div>
        <ol>
          {HOW_IT_WORKS.map((item, index) => (
            <li key={item.step}>
              <span>{index + 1}</span>
              <div>
                <h3>{item.step}</h3>
                <p>{item.action}</p>
                <p className="landing-outcome">Outcome: {item.outcome}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="landing-features" id="landing-features" aria-labelledby="features-title">
        <div className="landing-section-heading">
          <h2 id="features-title">Everything stays connected to its source.</h2>
          <p>Built around the real grant process, from discovery through review.</p>
        </div>
        <div className="landing-feature-index">
          {landingFeatures.map((feature, index) => (
            <a key={feature.id} href={`#/${feature.id}`} aria-label={`Open ${feature.label}`}>
              <span className="landing-feature-number">0{index + 1}</span>
              <span>
                <strong>{feature.label}</strong>
                <small>{feature.summary}</small>
              </span>
              {feature.id === 'skills' && (
                <span className="landing-feature-state">Coming later</span>
              )}
            </a>
          ))}
        </div>
      </section>

      <section className="landing-principles" aria-labelledby="principles-title">
        <div className="landing-section-heading">
          <h2 id="principles-title">Designed for accuracy and responsible review.</h2>
          <p>Trust, provenance and staff control stay visible throughout the workflow.</p>
        </div>
        <div className="landing-principle-grid">
          {PRINCIPLES.map((principle) => (
            <article key={principle.title}>
              <h3>{principle.title}</h3>
              <p>{principle.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-close" aria-labelledby="landing-close-title">
        <div>
          <h2 id="landing-close-title">Start with the opportunity. Keep the evidence with you.</h2>
          <p>
            Enter the guided workspace and follow the existing grant journey one stage at a time.
          </p>
        </div>
        <a className="button-primary" href="#/funding">
          Find funding
        </a>
      </section>
    </div>
  )
}
