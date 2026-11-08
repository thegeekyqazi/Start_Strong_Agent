// Skills page. Owner: C. C4-SKL-001 r1.0 s10.3 (thin practice slice).
// Source authority → candidate → scans/screening/tests → exact-hash review/activation → working
// draft preview → revoke. Every state comes from the server; all content renders as React text
// (no raw HTML, no remote images). Uses the shared shell components and existing styles only.
import { useCallback, useEffect, useState } from 'react'
import type {
  AnswerFinding,
  ApplicationWorkspace,
  CheckReport,
  PracticeCandidate,
  PracticeOverview,
  PracticePreview,
  PracticeReviewRequest,
} from '@strongstart/contracts'
import { FindingRow, HashChip } from '../../shell/components'
import {
  httpApplicationsClient,
  type ApiResult,
  type ApplicationsClient,
} from '../applications/client'
import {
  describeSkillsError,
  httpSkillsClient,
  type FixtureSourceKey,
  type SkillsClient,
} from './client'

const SAMPLE = 'Our kids love story circle saturdays at the Demo Literacy Program.'

const STATUS_LABEL: Record<PracticeCandidate['status'], string> = {
  proposed: 'Proposed — screening not run',
  needs_review: 'Gates passed — needs staff review',
  held: 'Held — a hard gate failed',
  approved: 'Reviewed — ready to activate',
  active: 'Active',
  superseded: 'Superseded',
  revoked: 'Revoked',
  stale_source: 'Stale — source changed',
}

function statusBadge(status: PracticeCandidate['status']): string {
  if (status === 'active' || status === 'approved') return 'badge badge-ok'
  if (status === 'needs_review' || status === 'proposed') return 'badge badge-planned'
  return 'badge badge-unavailable'
}

function PolicyFindings({ report, title }: { report: CheckReport | null; title: string }) {
  if (!report) return null
  const relevant = report.findings.filter((f: AnswerFinding) =>
    ['POL-01', 'POL-02'].includes(f.result.rule_id),
  )
  return (
    <section className="findings" aria-label={title}>
      <h5>{title}</h5>
      {relevant.map((f, n) => (
        <FindingRow
          key={`${f.result.rule_id}-${n}`}
          origin="check"
          outcome={f.result.outcome}
          message={`${f.result.rule_id}: ${f.message}`}
          affectedText={f.affected_text ?? undefined}
          nextAction={f.next_action ?? undefined}
        />
      ))}
    </section>
  )
}

export function SkillsPage({
  client = httpSkillsClient,
  appClient = httpApplicationsClient,
}: {
  client?: SkillsClient
  appClient?: ApplicationsClient
}) {
  const [data, setData] = useState<PracticeOverview | null>(null)
  const [ws, setWs] = useState<ApplicationWorkspace | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [supported, setSupported] = useState(false)
  const [acks, setAcks] = useState<string[]>([])
  const [sample, setSample] = useState(SAMPLE)
  const [preview, setPreview] = useState<PracticePreview | null>(null)

  const apply = useCallback((res: ApiResult<PracticeOverview>) => {
    if (res.ok) {
      setData(res.data)
      setSelected((s) => s ?? res.data.candidates.at(-1)?.candidate_id ?? null)
    } else setError(describeSkillsError(res))
  }, [])

  const reload = useCallback(async () => apply(await client.overview()), [client, apply])

  useEffect(() => {
    let live = true
    void client.overview().then((res) => live && apply(res))
    void appClient.workspace(null).then((r) => live && r.ok && setWs(r.data))
    return () => {
      live = false
    }
  }, [client, appClient, apply])

  async function act<T>(
    label: string,
    run: () => Promise<ApiResult<T>>,
    after?: (data: T) => void,
  ) {
    setBusy(label)
    setError(null)
    const res = await run()
    setBusy(null)
    if (res.ok) after?.(res.data)
    else setError(describeSkillsError(res))
    await reload()
  }

  if (!data)
    return (
      <section aria-labelledby="skills-heading">
        <h2 id="skills-heading">Skills</h2>
        <p role={error ? 'alert' : 'status'} className="hint">
          {error ?? 'Loading practice skills…'}
        </p>
      </section>
    )

  const current = data.sources.find((s) => s.is_current) ?? null
  const cand = data.candidates.find((c) => c.candidate_id === selected) ?? null
  const active = data.releases.find((r) => r.effective_state === 'active') ?? null
  const reviewIds = cand
    ? [
        ...cand.scan.findings.filter((f) => f.severity === 'review').map((f) => f.finding_id),
        ...(cand.screening?.signal === 'review'
          ? cand.screening.findings.length
            ? cand.screening.findings.map((_, n) => `screen-${n + 1}`)
            : ['screen-signal']
          : []),
      ]
    : []
  const question = ws ? [...ws.question_set.questions].sort((a, b) => a.order - b.order)[0] : null

  return (
    <section aria-labelledby="skills-heading">
      <h2 id="skills-heading">Skills</h2>
      <p className="banner-fixture" role="note">
        SYNTHETIC demonstration: invented practices and a local fixture identity. Previews are
        working-only and cannot be approved, exported or used for prefill.
      </p>
      {error && (
        <p role="alert" className="stale-banner">
          {error}
        </p>
      )}

      <section aria-labelledby="skills-source">
        <h3 id="skills-source">1. Source and scope</h3>
        <ul className="meta">
          <li>Scope: {data.context.label}</li>
          <li>Program: {data.context.program}</li>
          <li>Registered names: {data.context.registered_names.join(', ')}</li>
        </ul>
        <div className="draft-actions">
          {(['demo', 'conflict', 'hostile'] as FixtureSourceKey[]).map((key) => (
            <button
              key={key}
              type="button"
              className="button-secondary"
              disabled={busy !== null}
              onClick={() => void act('source', () => client.loadFixtureSource(key))}
            >
              {key === 'demo'
                ? 'Publish synthetic demo source'
                : key === 'conflict'
                  ? 'Publish conflicting source'
                  : 'Publish planted hostile source'}
            </button>
          ))}
        </div>
        {current ? (
          <div>
            <p>
              <strong>{current.title}</strong> (version {current.version}){' '}
              <span className="badge badge-planned">
                {current.provenance.is_simulated ? 'SYNTHETIC' : 'Administrator-authored'}
              </span>{' '}
              <HashChip hash={current.text_sha256} label="Source fingerprint" />
            </p>
            <pre className="plain">{current.text}</pre>
            {current.authority ? (
              <p className="hint">
                Reviewed as practice authority for this scope by {current.authority.approved_by}
                {current.authority.is_fixture ? ' (local fixture action)' : ''}. Approving the
                source does not approve generated rules.
              </p>
            ) : (
              <button
                type="button"
                className="button-primary"
                disabled={busy !== null}
                onClick={() =>
                  void act('authority', () => client.approveAuthority(current.source_version_id))
                }
              >
                Approve as practice authority for this scope
              </button>
            )}
          </div>
        ) : (
          <p className="hint">No practice source yet. Publish the synthetic demo source.</p>
        )}
      </section>

      <section aria-labelledby="skills-candidate">
        <h3 id="skills-candidate">2. Proposed practices</h3>
        <div className="draft-actions">
          <button
            type="button"
            className="button-primary"
            disabled={busy !== null || !current?.authority}
            aria-busy={busy === 'generate'}
            onClick={() =>
              current &&
              void act(
                'generate',
                () => client.generate(current.source_version_id),
                (c) => setSelected(c.candidate_id),
              )
            }
          >
            Generate candidate from current source
          </button>
          {data.candidates.length > 1 && (
            <label>
              Candidate{' '}
              <select value={selected ?? ''} onChange={(e) => setSelected(e.target.value)}>
                {data.candidates.map((c) => (
                  <option key={c.candidate_id} value={c.candidate_id}>
                    {c.candidate_id} — {STATUS_LABEL[c.status]}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {cand && (
          <div>
            <p>
              <span className={statusBadge(cand.status)}>{STATUS_LABEL[cand.status]}</span>{' '}
              <HashChip hash={cand.package.package_sha256} label="Package fingerprint" />{' '}
              <span className="hint">
                Proposer: {cand.proposer.adapter} {cand.proposer.model}
                {cand.proposer.is_fixture ? ' (FIXTURE, not model-written)' : ''}
              </span>
            </p>
            <table>
              <thead>
                <tr>
                  <th scope="col">Rule</th>
                  <th scope="col">Supporting source excerpt (exact)</th>
                </tr>
              </thead>
              <tbody>
                {cand.rules.map((r) => (
                  <tr key={r.rule_id}>
                    <td>
                      {r.operator === 'preferred_term'
                        ? `Use "${r.preferred_term}" instead of "${r.forbidden_term}"`
                        : `Write "${r.full_name}" exactly`}{' '}
                      <span className="hint">({r.rule_id})</span>
                    </td>
                    <td>
                      {r.citations.map((c) => (
                        <q key={`${c.start}-${c.end}`}>{c.quote}</q>
                      ))}
                      <span className="hint">
                        {' '}
                        code points {r.citations.map((c) => `${c.start}–${c.end}`).join(', ')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <details>
              <summary>Compiled package files ({cand.package.compiler_version})</summary>
              {cand.package.files.map((f) => (
                <div key={f.path}>
                  <p>
                    <code>{f.path}</code> <HashChip hash={f.sha256} label="File fingerprint" />
                  </p>
                  <pre className="plain">{f.content}</pre>
                </div>
              ))}
            </details>
          </div>
        )}
      </section>

      {cand && (
        <section aria-labelledby="skills-gates">
          <h3 id="skills-gates">3. Scans, screening and rule tests</h3>
          <h4>Deterministic scan ({cand.scan.scanner_version})</h4>
          {cand.scan.findings.length === 0 ? (
            <p className="hint">
              No scan findings across {cand.scan.inspected_parts.length} inspected parts.
            </p>
          ) : (
            cand.scan.findings.map((f) => (
              <FindingRow
                key={f.finding_id}
                origin="check"
                outcome={f.severity === 'block' ? 'fail' : 'needs_review'}
                message={`${f.category} in ${f.part} (${f.location}): ${f.message}`}
                affectedText={f.excerpt}
              />
            ))
          )}
          <h4>Rule tests ({cand.tests.passed ? 'all passed' : 'failed'})</h4>
          <ul className="meta">
            {cand.tests.cases.map((t) => (
              <li key={t.case_id}>
                {t.passed ? 'Passed' : 'FAILED'}: {t.expectation} — <q>{t.sample}</q>
              </li>
            ))}
          </ul>
          <h4>Model-based screening signal</h4>
          <p className="hint">
            A review signal, not a calibrated security classifier.{' '}
            {data.screening_live
              ? 'Live model configured.'
              : 'FIXTURE screening (no live model configured).'}
          </p>
          {cand.screening ? (
            <p>
              Signal <strong>{cand.screening.signal}</strong>; coverage{' '}
              {cand.screening.covered_parts.length}/{cand.screening.expected_parts.length} parts
              {cand.screening.complete ? ' (complete)' : ' (INCOMPLETE)'}
              {cand.screening.provider?.is_fixture ? '; FIXTURE signal' : ''}
              {cand.screening.hold_reason ? `; held: ${cand.screening.hold_reason}` : ''}
            </p>
          ) : (
            <p className="hint">Screening has not run for this exact package.</p>
          )}
          <button
            type="button"
            className="button-secondary"
            disabled={busy !== null}
            aria-busy={busy === 'screen'}
            onClick={() => void act('screen', () => client.screen(cand.candidate_id))}
          >
            Run screening for this package
          </button>
          {cand.hold_reasons.length > 0 && (
            <p role="status" className="stale-banner">
              Holds: {cand.hold_reasons.join(', ')}. Activation stays disabled.
            </p>
          )}
        </section>
      )}

      {cand && (
        <section aria-labelledby="skills-review">
          <h3 id="skills-review">4. Exact-fingerprint review and activation</h3>
          <label>
            <input
              type="checkbox"
              checked={supported}
              onChange={(e) => setSupported(e.target.checked)}
            />{' '}
            I confirm every rule follows from its source excerpt.
          </label>
          {reviewIds.map((id) => (
            <label key={id}>
              <input
                type="checkbox"
                checked={acks.includes(id)}
                onChange={(e) =>
                  setAcks(e.target.checked ? [...acks, id] : acks.filter((a) => a !== id))
                }
              />{' '}
              Acknowledge review item {id}
            </label>
          ))}
          <div className="draft-actions">
            <button
              type="button"
              className="button-primary"
              disabled={
                busy !== null || cand.hold_reasons.length > 0 || cand.status !== 'needs_review'
              }
              onClick={() =>
                void act('review', () =>
                  client.review(cand.candidate_id, {
                    package_sha256: cand.package.package_sha256,
                    source_supported: supported,
                    acknowledged_findings: acks.slice(
                      0,
                      20,
                    ) as PracticeReviewRequest['acknowledged_findings'],
                    rationale: 'Reviewed on the Skills page.',
                  }),
                )
              }
            >
              Approve this exact package
            </button>
            <button
              type="button"
              className="button-primary"
              disabled={busy !== null || cand.status !== 'approved'}
              onClick={() =>
                void act('activate', () =>
                  client.activate(cand.candidate_id, {
                    package_sha256: cand.package.package_sha256,
                    idempotency_key: `ui-${cand.candidate_id}`,
                  }),
                )
              }
            >
              Activate for this scope
            </button>
          </div>
          {active ? (
            <p>
              <span className="badge badge-ok">Active release {active.release_id}</span>{' '}
              <HashChip hash={active.package_sha256} label="Active package" />{' '}
              <button
                type="button"
                className="button-secondary"
                disabled={busy !== null}
                onClick={() =>
                  void act('revoke', () =>
                    client.revoke(active.release_id, 'Revoked on the Skills page.'),
                  )
                }
              >
                Revoke
              </button>
            </p>
          ) : (
            <p className="hint">No active practice for this scope.</p>
          )}
          <ul className="meta">
            {data.releases.map((r) => (
              <li key={r.release_id}>
                {r.release_id}: {r.effective_state}
                {r.revoked_reason ? ` (${r.revoked_reason})` : ''}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="skills-preview">
        <h3 id="skills-preview">5. Working draft preview</h3>
        <label>
          Sample text checked with and without the practice
          <textarea
            value={sample}
            maxLength={2000}
            rows={3}
            onChange={(e) => setSample(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="button-primary"
          disabled={busy !== null || !question || !ws}
          aria-busy={busy === 'preview'}
          onClick={() =>
            question &&
            ws &&
            void act(
              'preview',
              () =>
                client.preview({
                  question_id: question.question_id,
                  question_version: question.question_version,
                  evidence_bundle_id: ws.evidence_bundle.bundle_id,
                  sample_text: sample,
                }),
              (p) => setPreview(p),
            )
          }
        >
          Preview a draft{question ? ` for “${question.original_text.slice(0, 60)}…”` : ''}
        </button>
        {preview && (
          <div>
            <p className="banner-fixture" role="note">
              Working preview only — approval is not permitted from here.
            </p>
            {preview.applied ? (
              <>
                <p>
                  Applied release {preview.applied.release_id}{' '}
                  <HashChip hash={preview.applied.package_sha256} label="Package" />{' '}
                  <HashChip
                    hash={preview.applied.instruction_sha256}
                    label="Instruction snapshot"
                  />
                  {preview.current ? '' : ' — NOT CURRENT (practice changed during preview)'}
                </p>
                <h4>Applied-instruction trace (sent to the draft model)</h4>
                <pre className="plain">{preview.applied.instructions}</pre>
              </>
            ) : (
              <p className="stale-banner" role="status">
                No practice applied: {preview.hold_reason}
              </p>
            )}
            <h4>
              Baseline draft ({preview.baseline_draft.provider.adapter}
              {preview.baseline_draft.provider.is_fixture ? ', FIXTURE' : ''})
            </h4>
            <p>
              {preview.baseline_draft.check?.rendered.text ?? preview.baseline_draft.template_text}
            </p>
            {preview.practice_draft && (
              <>
                <h4>Draft with the active practice</h4>
                <p>
                  {preview.practice_draft.check?.rendered.text ??
                    preview.practice_draft.template_text}
                </p>
              </>
            )}
            <PolicyFindings
              report={preview.sample_baseline_check}
              title="Sample checked with the base policy only"
            />
            <PolicyFindings
              report={preview.sample_practice_check}
              title="Sample checked with the active practice"
            />
            <ul className="meta">
              {preview.next_actions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <details>
        <summary>Audit trail ({data.audit.length} recent events)</summary>
        <ul className="meta">
          {data.audit.map((e) => (
            <li key={e.event_id}>
              {e.at}: {e.action} {e.object_id} by {e.actor_id} — {e.detail}
            </li>
          ))}
        </ul>
      </details>
    </section>
  )
}
