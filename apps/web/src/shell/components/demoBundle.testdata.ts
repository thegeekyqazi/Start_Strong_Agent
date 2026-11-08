// TEST-ONLY: parses the real shared synthetic fixture (tests/fixtures/demo/demo-bundle-v1.json)
// so web tests cannot drift from the bundle the API serves. Not imported by app code.
import type { ApplicationWorkspace, EvidenceBundle, QuestionSet } from '@strongstart/contracts'
import raw from '../../../../../tests/fixtures/demo/demo-bundle-v1.json?raw'

const bundle = JSON.parse(raw) as {
  evidence_bundles: EvidenceBundle[]
  question_sets: QuestionSet[]
}

export const demoEvidence: EvidenceBundle = bundle.evidence_bundles[0]
export const demoFact = demoEvidence.facts[0]

export const demoWorkspace: ApplicationWorkspace = {
  schema_version: '1',
  application_definition_id: 'demo-gos-app-v1',
  question_set: bundle.question_sets[0],
  evidence_bundle: demoEvidence,
  is_fixture: true,
  data_label: 'FIXTURE: synthetic demo-bundle@1 data, not partner records',
}
