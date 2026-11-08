// Funding cases (owner: Dev B funding; DEV-B-BUNDLE-002 M3/M4). Staff establish a funding context,
// anchor typed requirements to exact quotes in saved captures, review an exact version, then run
// deterministic scenario checks. Signals stay separate: source coverage, interpretation review,
// input quality, deterministic findings. There is no "eligible" badge.
import { useEffect, useState } from 'react'
import type {
  CaptureContent,
  CapturedDocument,
  EvaluateCommand,
  EvaluationList,
  EvaluationReport,
  FundingCaseCommand,
  FundingCaseEnvelope,
  FundingCaseList,
} from '@strongstart/contracts'
import { describeError, type FundingClient } from './client'
import { locateQuote } from './quote'

type Phase<T> =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'done'; data: T }

type AnchorDraft = FundingCaseCommand['anchors'] extends (infer A)[] | undefined ? A : never
type RequirementDraft = FundingCaseCommand['requirements'] extends (infer R)[] | undefined
  ? R
  : never
type Kind = RequirementDraft['spec']['kind']
type Stage = 'eoi' | 'full_application' | 'single_stage' | 'unknown'
type ReviewKeys = Parameters<FundingClient['reviewCase']>[2]['requirement_keys']

const KINDS: { kind: Kind; label: string }[] = [
  { kind: 'deadline', label: 'Deadline (cutoff)' },
  { kind: 'project_window', label: 'Project window' },
  { kind: 'amount_range', label: 'Amount range' },
  { kind: 'geography', label: 'Geography membership' },
  { kind: 'organization_type', label: 'Organization type' },
  { kind: 'activity', label: 'Eligible activity' },
  { kind: 'invitation', label: 'Invitation / prior stage' },
]

const OUTCOME_LABEL: Record<string, string> = {
  met: 'Rule met (with these inputs)',
  not_met: 'Rule not met',
  unknown: 'Unknown',
  not_applicable: 'Not applicable (reviewed condition)',
  at_cutoff_needs_review: 'At the cutoff: needs review',
}

let counter = 0
function freshKey(prefix: string): string {
  counter += 1
  const random =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${counter}`
  return `${prefix}-${random}`
}

const csv = (v: string) =>
  v
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean)
// Generated contract types encode list bounds as tuples; the server enforces the bounds.
const ids = (v: string) => csv(v) as [string, ...string[]]
const orNull = (v: string) => (v.trim() === '' ? null : v.trim())

function AnchorBuilder({
  client,
  onAdd,
}: {
  client: FundingClient
  onAdd: (a: AnchorDraft) => void
}) {
  const [captureId, setCaptureId] = useState('')
  const [doc, setDoc] = useState<Phase<CapturedDocument>>({ kind: 'idle' })
  const [content, setContent] = useState<Phase<CaptureContent>>({ kind: 'idle' })
  const [quote, setQuote] = useState('')
  const [anchorKey, setAnchorKey] = useState('')
  const [problem, setProblem] = useState<string | null>(null)

  const loadDoc = async () => {
    setDoc({ kind: 'loading' })
    setContent({ kind: 'idle' })
    const r = await client.getCapture(captureId.trim())
    setDoc(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
  }
  const loadContent = async (artifactId: string) => {
    if (doc.kind !== 'done') return
    setContent({ kind: 'loading' })
    const r = await client.content(doc.data.capture_id, artifactId)
    setContent(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
  }
  const add = () => {
    setProblem(null)
    if (content.kind !== 'done' || doc.kind !== 'done') return
    if (!/^[a-z0-9][a-z0-9_-]{0,39}$/.test(anchorKey)) {
      setProblem('Give the anchor a short key (lowercase letters, digits, - or _).')
      return
    }
    const found = locateQuote(content.data.text, quote)
    if (!found) {
      setProblem('That exact text does not occur in the stored representation.')
      return
    }
    if (found.count > 1) {
      setProblem(`That text occurs ${found.count} times; select a longer, unique passage.`)
      return
    }
    onAdd({
      anchor_key: anchorKey,
      capture_id: doc.data.capture_id,
      artifact_id: content.data.artifact.artifact_id,
      expected_artifact_sha256: content.data.artifact.sha256,
      quote,
      start: found.start,
      end: found.start + Array.from(quote).length,
    })
    setQuote('')
    setAnchorKey('')
  }
  return (
    <fieldset>
      <legend>Add an evidence anchor (exact quote from a saved capture)</legend>
      <label htmlFor="anchor-capture">Capture ID</label>
      <input id="anchor-capture" value={captureId} onChange={(e) => setCaptureId(e.target.value)} />
      <button type="button" onClick={() => void loadDoc()}>
        Load capture
      </button>
      {doc.kind === 'error' && <p role="alert">{doc.message}</p>}
      {doc.kind === 'done' &&
        doc.data.artifacts.map((a) => (
          <button key={a.artifact_id} type="button" onClick={() => void loadContent(a.artifact_id)}>
            Show {a.representation}
          </button>
        ))}
      {content.kind === 'error' && <p role="alert">{content.message}</p>}
      {content.kind === 'done' && (
        <>
          <p className="hint">
            {content.data.artifact.representation} · sha256{' '}
            <code>{content.data.artifact.sha256}</code> (integrity verified; inert text). Copy the
            exact passage you rely on.
          </p>
          <pre className="evidence" data-testid="anchor-source">
            {content.data.text}
          </pre>
          <label htmlFor="anchor-quote">Exact quote</label>
          <textarea id="anchor-quote" value={quote} onChange={(e) => setQuote(e.target.value)} />
          <label htmlFor="anchor-key">Anchor key</label>
          <input id="anchor-key" value={anchorKey} onChange={(e) => setAnchorKey(e.target.value)} />
          <button type="button" onClick={add}>
            Add anchor
          </button>
        </>
      )}
      {problem && <p role="alert">{problem}</p>}
    </fieldset>
  )
}

function RequirementBuilder({
  anchorKeys,
  onAdd,
}: {
  anchorKeys: string[]
  onAdd: (r: RequirementDraft) => void
}) {
  const [kind, setKind] = useState<Kind>('amount_range')
  const [key, setKey] = useState('')
  const [anchors, setAnchors] = useState('')
  const [interpretation, setInterpretation] = useState('')
  const [f, setF] = useState<Record<string, string>>({})
  const [scopeStream, setScopeStream] = useState('')
  const [scopeStage, setScopeStage] = useState('')
  const [problem, setProblem] = useState<string | null>(null)
  const set = (name: string) => (e: { target: { value: string } }) =>
    setF((prev) => ({ ...prev, [name]: e.target.value }))
  const v = (name: string) => f[name] ?? ''

  const spec = (): RequirementDraft['spec'] => {
    switch (kind) {
      case 'deadline':
        return {
          kind,
          original_wording: v('wording'),
          precision: (v('precision') || 'exact') as 'exact',
          date: orNull(v('date')),
          local_time: orNull(v('time')),
          timezone: orNull(v('timezone')),
          utc_offset: orNull(v('offset')),
          fold: v('fold') === '' ? null : (Number(v('fold')) as 0 | 1),
          boundary: (v('boundary') || 'unstated') as 'unstated',
        }
      case 'project_window':
        return {
          kind,
          earliest_start: orNull(v('start')),
          latest_end: orNull(v('end')),
          start_boundary: (v('startB') || 'inclusive') as 'inclusive',
          end_boundary: (v('endB') || 'inclusive') as 'inclusive',
        }
      case 'amount_range':
        return {
          kind,
          limit_kind: (v('limitKind') || 'per_award') as 'per_award',
          minimum: orNull(v('min')),
          maximum: orNull(v('max')),
          currency: v('currency') || 'CAD',
          scale: (v('scale') || 'units') as 'units',
        }
      case 'geography':
      case 'organization_type':
        return { kind, allowed: ids(v('allowed')) }
      case 'activity':
        return { kind, allowed: ids(v('allowed')), mode: (v('mode') || 'any') as 'any' }
      case 'invitation':
        return {
          kind,
          required: v('required') !== 'no',
          evidence_required: v('evidence') !== 'no',
        }
    }
  }
  const add = () => {
    const keys = csv(anchors)
    if (!key || keys.length === 0 || !interpretation.trim()) {
      setProblem('A requirement needs a key, at least one anchor key and an interpretation.')
      return
    }
    const unknown = keys.filter((k) => !anchorKeys.includes(k))
    if (unknown.length) {
      setProblem(`Unknown anchor keys: ${unknown.join(', ')}`)
      return
    }
    setProblem(null)
    onAdd({
      requirement_key: key,
      spec: spec(),
      anchor_keys: keys as RequirementDraft['anchor_keys'],
      scope: { stream_label: orNull(scopeStream), stage: (orNull(scopeStage) as Stage) ?? null },
      interpretation: interpretation.trim(),
    })
    setKey('')
    setF({})
  }
  const field = (name: string, label: string, placeholder = '') => (
    <label>
      {label}
      <input aria-label={label} value={v(name)} onChange={set(name)} placeholder={placeholder} />
    </label>
  )
  return (
    <fieldset>
      <legend>Add a typed requirement (finite rule kinds only)</legend>
      <label>
        Rule kind
        <select value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
          {KINDS.map((k) => (
            <option key={k.kind} value={k.kind}>
              {k.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Requirement key
        <input aria-label="Requirement key" value={key} onChange={(e) => setKey(e.target.value)} />
      </label>
      <label>
        Anchor keys (comma separated; available: {anchorKeys.join(', ') || 'none yet'})
        <input
          aria-label="Anchor keys"
          value={anchors}
          onChange={(e) => setAnchors(e.target.value)}
        />
      </label>
      {kind === 'deadline' && (
        <>
          {field('wording', 'Original wording')}
          {field('precision', 'Precision', 'exact | date_only | rolling | unknown')}
          {field('date', 'Date', 'YYYY-MM-DD')}
          {field('time', 'Local time', 'HH:MM:SS')}
          {field('timezone', 'IANA timezone', 'America/Toronto')}
          {field('offset', 'Explicit UTC offset (optional)', '-04:00')}
          {field('fold', 'DST fold (0 first / 1 second; only if stated)')}
          {field('boundary', 'Boundary', 'inclusive | exclusive | unstated')}
        </>
      )}
      {kind === 'project_window' && (
        <>
          {field('start', 'Earliest start', 'YYYY-MM-DD')}
          {field('end', 'Latest end', 'YYYY-MM-DD')}
          {field('startB', 'Start boundary', 'inclusive | exclusive')}
          {field('endB', 'End boundary', 'inclusive | exclusive')}
        </>
      )}
      {kind === 'amount_range' && (
        <>
          {field('limitKind', 'Limit kind', 'per_award | total_pool | matching_ratio')}
          {field('min', 'Minimum (exact decimal)')}
          {field('max', 'Maximum (exact decimal)')}
          {field('currency', 'Currency', 'CAD')}
          {field('scale', 'Scale', 'units | thousands | millions')}
        </>
      )}
      {(kind === 'geography' || kind === 'organization_type' || kind === 'activity') &&
        field('allowed', 'Allowed identifiers (comma separated)')}
      {kind === 'activity' && field('mode', 'Semantics', 'any | all')}
      {kind === 'invitation' && (
        <>
          {field('required', 'Invitation required (yes/no)', 'yes')}
          {field('evidence', 'Evidence required (yes/no)', 'yes')}
        </>
      )}
      <label>
        Applies to stream (blank = the case stream)
        <input
          aria-label="Applies to stream"
          value={scopeStream}
          onChange={(e) => setScopeStream(e.target.value)}
        />
      </label>
      <label>
        Applies to stage (blank = the case stage)
        <input
          aria-label="Applies to stage"
          value={scopeStage}
          onChange={(e) => setScopeStage(e.target.value)}
          placeholder="eoi | full_application | single_stage"
        />
      </label>
      <label>
        Interpretation / rationale (kept separate from the quoted text)
        <textarea
          aria-label="Interpretation"
          value={interpretation}
          onChange={(e) => setInterpretation(e.target.value)}
        />
      </label>
      <button type="button" onClick={add}>
        Add requirement
      </button>
      {problem && <p role="alert">{problem}</p>}
    </fieldset>
  )
}

function CaseView({
  env,
  client,
  onChanged,
}: {
  env: FundingCaseEnvelope
  client: FundingClient
  onChanged: (env: FundingCaseEnvelope) => void
}) {
  const v = env.version
  const [review, setReview] = useState<Phase<null>>({ kind: 'idle' })
  const runReview = async () => {
    setReview({ kind: 'loading' })
    const r = await client.reviewCase(v.case_id, v.version, {
      idempotency_key: freshKey('review'),
      version_digest: env.version_digest,
      requirement_keys: v.requirements.map((x) => x.requirement_key) as ReviewKeys,
    })
    if (r.ok) {
      setReview({ kind: 'done', data: null })
      onChanged(r.data)
    } else setReview({ kind: 'error', message: describeError(r) })
  }
  return (
    <section aria-labelledby={`case-${v.case_id}`} className="case-view">
      <h4 id={`case-${v.case_id}`}>
        Case <code>{v.case_id}</code> v{v.version}
        {env.is_current ? '' : ` (not current; current is v${env.current_version})`}
      </h4>
      <p className="hint">Staff-selected context, not a certified opportunity.</p>
      <ul className="checks">
        <li>
          Interpretation review: <strong>{env.review_status}</strong>
          {env.review && ` by ${env.review.reviewer} at ${env.review.reviewed_at}`}
        </li>
        <li>
          Source status: <strong>{env.source_status.replaceAll('_', ' ')}</strong>
        </li>
        <li>
          Rule readiness: <strong>{env.readiness.replaceAll('_', ' ')}</strong>
        </li>
        <li>
          Version digest: <code>{env.version_digest}</code>
        </li>
      </ul>
      {env.source_findings && env.source_findings.length > 0 && (
        <ul className="warnings">
          {env.source_findings.map((s) => (
            <li key={s.observation_id}>
              {s.capture_id}: {s.overall} - {s.message}
            </li>
          ))}
        </ul>
      )}
      <dl className="meta">
        <dt>Funder / stream / cycle / stage</dt>
        <dd>
          {v.context.funder_label ?? 'unknown'} / {v.context.stream_label ?? 'unknown'} /{' '}
          {v.context.cycle_label ?? 'unknown'} / {v.context.stage}
        </dd>
        <dt>Shared opportunity</dt>
        <dd>
          {env.opportunity
            ? `${env.opportunity.opportunity_id} (deadline date ${env.opportunity.deadline.status})`
            : `Not established: missing ${env.opportunity_missing?.join(', ')}`}
        </dd>
      </dl>
      <h5>Evidence anchors</h5>
      <ul>
        {v.anchors.map((a) => (
          <li key={a.anchor_key}>
            <strong>{a.anchor_key}</strong>: &ldquo;{a.quote}&rdquo; ({a.capture_id}, chars{' '}
            {a.start}-{a.end}, coverage {a.coverage}
            {a.is_simulated ? ', simulated' : ''}) - quote matched hash-verified bytes
          </li>
        ))}
      </ul>
      <h5>Requirements</h5>
      <ul>
        {v.requirements.map((r) => (
          <li key={r.requirement_key}>
            <strong>{r.requirement_key}</strong> ({r.spec.kind}; rules {r.rule_ids.join(', ')}):{' '}
            <code>{JSON.stringify(r.spec)}</code> - interpretation: {r.interpretation}
            {(r.scope.stream_label || r.scope.stage) &&
              ` · applies to ${[r.scope.stream_label, r.scope.stage].filter(Boolean).join(' / ')}`}
          </li>
        ))}
      </ul>
      {env.is_current && env.review_status === 'unreviewed' && v.requirements.length > 0 && (
        <p>
          <button
            type="button"
            onClick={() => void runReview()}
            disabled={review.kind === 'loading'}
          >
            Review these requirements
          </button>{' '}
          <span className="hint">
            Confirms these typed interpretations of the cited text for v{v.version} only. It does
            not verify organizational facts or approve anything.
          </span>
        </p>
      )}
      {review.kind === 'error' && <p role="alert">{review.message}</p>}
      <Evaluate env={env} client={client} />
    </section>
  )
}

function Evaluate({ env, client }: { env: FundingCaseEnvelope; client: FundingClient }) {
  const v = env.version
  const [clock, setClock] = useState('')
  const [stream, setStream] = useState('')
  const [stage, setStage] = useState('')
  const [prov, setProv] = useState<'staff_asserted' | 'simulated'>('staff_asserted')
  const [f, setF] = useState<Record<string, string>>({})
  const [report, setReport] = useState<Phase<EvaluationReport>>({ kind: 'idle' })
  const [history, setHistory] = useState<Phase<EvaluationList>>({ kind: 'idle' })
  const set = (name: string) => (e: { target: { value: string } }) =>
    setF((prev) => ({ ...prev, [name]: e.target.value }))
  const val = (n: string) => (f[n] ?? '').trim()

  const run = async () => {
    const inputs: EvaluateCommand['inputs'] = {}
    if (val('amount'))
      inputs.request_amount = {
        amount: val('amount'),
        currency: val('currency') || 'CAD',
        provenance: prov,
      }
    if (val('region')) inputs.region = { value: val('region'), provenance: prov }
    if (val('orgType')) inputs.organization_type = { value: val('orgType'), provenance: prov }
    if (val('activities')) inputs.activities = { values: ids(val('activities')), provenance: prov }
    if (val('invitation'))
      inputs.invitation = {
        status: val('invitation') as 'invited' | 'not_invited',
        provenance: prov,
        evidence_note: orNull(val('evidence')),
      }
    if (val('start')) inputs.project_start = { value: val('start'), provenance: prov }
    if (val('end')) inputs.project_end = { value: val('end'), provenance: prov }
    if (val('appType')) inputs.application_type = { value: val('appType'), provenance: prov }
    setReport({ kind: 'loading' })
    const r = await client.evaluateCase(v.case_id, {
      idempotency_key: freshKey('eval'),
      case_version: v.version,
      clock: orNull(clock),
      scope: { stream_label: orNull(stream), stage: (orNull(stage) as Stage) ?? null },
      inputs,
    })
    setReport(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
  }
  const loadHistory = async () => {
    setHistory({ kind: 'loading' })
    const r = await client.listEvaluations(v.case_id)
    setHistory(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
  }
  const field = (name: string, label: string, placeholder = '') => (
    <label>
      {label}
      <input
        aria-label={label}
        value={f[name] ?? ''}
        onChange={set(name)}
        placeholder={placeholder}
      />
    </label>
  )
  return (
    <fieldset>
      <legend>Scenario check (deterministic; not an eligibility decision)</legend>
      <label>
        Evaluation clock (ISO with offset; blank = now)
        <input
          aria-label="Evaluation clock"
          value={clock}
          onChange={(e) => setClock(e.target.value)}
          placeholder="2026-03-01T09:00:00-05:00"
        />
      </label>
      <label>
        Stream (blank = case)
        <input
          aria-label="Evaluation stream"
          value={stream}
          onChange={(e) => setStream(e.target.value)}
        />
      </label>
      <label>
        Stage (blank = case)
        <input
          aria-label="Evaluation stage"
          value={stage}
          onChange={(e) => setStage(e.target.value)}
        />
      </label>
      <label>
        Input provenance
        <select value={prov} onChange={(e) => setProv(e.target.value as 'staff_asserted')}>
          <option value="staff_asserted">Staff asserted (scenario)</option>
          <option value="simulated">Simulated</option>
        </select>
      </label>
      {field('amount', 'Request amount (exact decimal)')}
      {field('currency', 'Request currency', 'CAD')}
      {field('region', 'Region identifier')}
      {field('orgType', 'Organization type identifier')}
      {field('activities', 'Activities (comma separated)')}
      {field('invitation', 'Invitation status', 'invited | not_invited')}
      {field('evidence', 'Invitation evidence note')}
      {field('start', 'Project start', 'YYYY-MM-DD')}
      {field('end', 'Project end', 'YYYY-MM-DD')}
      {field('appType', 'Application type')}
      <button type="button" onClick={() => void run()} disabled={report.kind === 'loading'}>
        Run scenario check
      </button>{' '}
      <button type="button" onClick={() => void loadHistory()}>
        Show evaluation history
      </button>
      {report.kind === 'error' && <p role="alert">{report.message}</p>}
      {report.kind === 'done' && <ReportView report={report.data} />}
      {history.kind === 'error' && <p role="alert">{history.message}</p>}
      {history.kind === 'done' && (
        <ul>
          {history.data.items.map((e) => (
            <li key={e.report.evaluation_id}>
              {e.report.evaluation_id} at clock {e.report.clock} (v{e.report.case_version}):{' '}
              {e.report.eligibility_group_outcome ?? 'no eligibility rules'}
              {e.stale ? ` - STALE: ${e.stale_reasons?.join('; ')}` : ' - historical record'}
            </li>
          ))}
        </ul>
      )}
    </fieldset>
  )
}

export function ReportView({ report }: { report: EvaluationReport }) {
  return (
    <section aria-label="Evaluation report" className="report">
      <p>
        <strong>{report.scenario_summary}</strong>
      </p>
      <p className="badge badge-planned">{report.reliance_explanation}</p>
      <p className="hint">
        Clock {report.clock} ({report.clock_source}) · case v{report.case_version} · inputs digest{' '}
        <code>{report.inputs_digest}</code> · evaluator {report.evaluator_version}
      </p>
      <ol>
        {report.results.map((r) => (
          <li key={r.requirement_key}>
            <strong>
              {r.requirement_key}: {OUTCOME_LABEL[r.outcome] ?? r.outcome}
            </strong>{' '}
            ({r.rule_ids.join(', ')})
            <ul>
              <li>Compared: {r.compared}</li>
              <li>
                Source:{' '}
                {r.support.map((s) => (
                  <q key={s.anchor_key}>{s.quote}</q>
                ))}
              </li>
              <li>Inputs: {r.inputs_used.length ? r.inputs_used.join('; ') : 'none'}</li>
              <li>Found: {r.found}</li>
              <li>Uncertain: {r.uncertainty}</li>
              <li>Next: {r.next_action}</li>
            </ul>
          </li>
        ))}
      </ol>
      {report.excluded && report.excluded.length > 0 && (
        <details open>
          <summary>Not used ({report.excluded.length})</summary>
          <ul>
            {report.excluded.map((e) => (
              <li key={e.requirement_key}>
                {e.requirement_key}: {e.reason}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}

export function FundingCases({ client }: { client: FundingClient }) {
  const [list, setList] = useState<Phase<FundingCaseList>>({ kind: 'loading' })
  const [opened, setOpened] = useState<Phase<FundingCaseEnvelope>>({ kind: 'idle' })
  const [ctx, setCtx] = useState({ funder: '', stream: '', cycle: '', stage: 'unknown', title: '' })
  const [links, setLinks] = useState('')
  const [anchors, setAnchors] = useState<AnchorDraft[]>([])
  const [requirements, setRequirements] = useState<RequirementDraft[]>([])
  const [reviseOf, setReviseOf] = useState<FundingCaseEnvelope | null>(null)
  const [save, setSave] = useState<Phase<null>>({ kind: 'idle' })

  useEffect(() => {
    let active = true
    client.listCases().then((r) => {
      if (!active) return
      setList(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
    })
    return () => {
      active = false
    }
  }, [client])

  const reload = async () => {
    const r = await client.listCases()
    setList(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
  }
  const open = async (id: string) => {
    setOpened({ kind: 'loading' })
    const r = await client.getCase(id)
    setOpened(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
  }
  const startRevision = (env: FundingCaseEnvelope) => {
    const v = env.version
    setReviseOf(env)
    setCtx({
      funder: v.context.funder_label ?? '',
      stream: v.context.stream_label ?? '',
      cycle: v.context.cycle_label ?? '',
      stage: v.context.stage,
      title: v.context.opportunity_title ?? '',
    })
    setLinks(v.capture_links.map((l) => l.capture_id).join(', '))
    setAnchors(
      v.anchors.map((a) => ({
        anchor_key: a.anchor_key,
        capture_id: a.capture_id,
        artifact_id: a.artifact_id,
        expected_artifact_sha256: a.artifact_sha256,
        quote: a.quote,
        start: a.start,
        end: a.end,
      })),
    )
    setRequirements(
      v.requirements.map((r) => ({
        requirement_key: r.requirement_key,
        spec: r.spec,
        anchor_keys: r.anchor_keys,
        scope: r.scope,
        applicability: r.applicability ?? null,
        interpretation: r.interpretation,
      })) as RequirementDraft[],
    )
  }
  const runSave = async () => {
    setSave({ kind: 'loading' })
    const body: FundingCaseCommand = {
      idempotency_key: freshKey('case'),
      expected_version: reviseOf ? reviseOf.version.version : null,
      context: {
        funder_label: orNull(ctx.funder),
        stream_label: orNull(ctx.stream),
        cycle_label: orNull(ctx.cycle),
        stage: ctx.stage as Stage,
        opportunity_title: orNull(ctx.title),
      },
      capture_links: csv(links).map((capture_id) => ({
        capture_id,
      })) as FundingCaseCommand['capture_links'],
      anchors,
      requirements,
    }
    const r = await client.saveCase(body, reviseOf?.version.case_id)
    if (r.ok) {
      setSave({ kind: 'done', data: null })
      setOpened({ kind: 'done', data: r.data })
      setReviseOf(null)
      void reload()
    } else setSave({ kind: 'error', message: describeError(r) })
  }
  const setC = (name: keyof typeof ctx) => (e: { target: { value: string } }) =>
    setCtx((prev) => ({ ...prev, [name]: e.target.value }))

  return (
    <section aria-labelledby="funding-cases">
      <h3 id="funding-cases">Funding cases and reviewed requirements</h3>
      <p className="hint">
        A case groups the funding context you selected. Requirements must quote saved captures
        exactly; they stay inactive until you review that exact version. Checks report what the
        encoded rules say about a scenario. They never confirm eligibility.
      </p>
      {list.kind === 'loading' && <p role="status">Loading funding cases...</p>}
      {list.kind === 'error' && <p role="alert">{list.message}</p>}
      {list.kind === 'done' && list.data.items.length === 0 && (
        <p role="status">No funding cases yet.</p>
      )}
      {list.kind === 'done' && list.data.items.length > 0 && (
        <ul>
          {list.data.items.map((s) => (
            <li key={s.case_id}>
              <code>{s.case_id}</code>{' '}
              {s.status === 'ok'
                ? `${s.title ?? s.funder_label ?? '(untitled)'} · v${s.current_version} · ${s.review_status} · source ${s.source_status} · ${s.requirement_count} requirements`
                : 'integrity failure (content withheld)'}{' '}
              <button
                type="button"
                disabled={s.status !== 'ok'}
                onClick={() => void open(s.case_id)}
              >
                Open case {s.case_id}
              </button>
            </li>
          ))}
        </ul>
      )}

      <fieldset>
        <legend>
          {reviseOf
            ? `Revise ${reviseOf.version.case_id} (from v${reviseOf.version.version})`
            : 'New funding case'}
        </legend>
        <label>
          Funder
          <input aria-label="Funder" value={ctx.funder} onChange={setC('funder')} />
        </label>
        <label>
          Stream
          <input aria-label="Stream" value={ctx.stream} onChange={setC('stream')} />
        </label>
        <label>
          Cycle
          <input aria-label="Cycle" value={ctx.cycle} onChange={setC('cycle')} />
        </label>
        <label>
          Stage
          <select aria-label="Stage" value={ctx.stage} onChange={setC('stage')}>
            <option value="unknown">unknown</option>
            <option value="eoi">expression of interest</option>
            <option value="full_application">full application</option>
            <option value="single_stage">single stage</option>
          </select>
        </label>
        <label>
          Opportunity title (optional)
          <input aria-label="Opportunity title" value={ctx.title} onChange={setC('title')} />
        </label>
        <label>
          Linked capture IDs (comma separated)
          <input
            aria-label="Linked capture IDs"
            value={links}
            onChange={(e) => setLinks(e.target.value)}
          />
        </label>
        <AnchorBuilder client={client} onAdd={(a) => setAnchors((prev) => [...prev, a])} />
        <ul>
          {anchors.map((a) => (
            <li key={a.anchor_key}>
              {a.anchor_key}: &ldquo;{a.quote}&rdquo; ({a.capture_id} chars {a.start}-{a.end}){' '}
              <button
                type="button"
                onClick={() =>
                  setAnchors((prev) => prev.filter((x) => x.anchor_key !== a.anchor_key))
                }
              >
                Remove anchor {a.anchor_key}
              </button>
            </li>
          ))}
        </ul>
        <RequirementBuilder
          anchorKeys={anchors.map((a) => a.anchor_key)}
          onAdd={(r) => setRequirements((prev) => [...prev, r])}
        />
        <ul>
          {requirements.map((r) => (
            <li key={r.requirement_key}>
              {r.requirement_key} ({r.spec.kind}) cites {r.anchor_keys.join(', ')}{' '}
              <button
                type="button"
                onClick={() =>
                  setRequirements((prev) =>
                    prev.filter((x) => x.requirement_key !== r.requirement_key),
                  )
                }
              >
                Remove requirement {r.requirement_key}
              </button>
            </li>
          ))}
        </ul>
        <button type="button" onClick={() => void runSave()} disabled={save.kind === 'loading'}>
          {reviseOf ? 'Save new case version' : 'Create funding case'}
        </button>
        {reviseOf && (
          <button type="button" onClick={() => setReviseOf(null)}>
            Cancel revision
          </button>
        )}
        {save.kind === 'error' && <p role="alert">{save.message}</p>}
      </fieldset>

      {opened.kind === 'loading' && <p role="status">Opening case...</p>}
      {opened.kind === 'error' && <p role="alert">{opened.message}</p>}
      {opened.kind === 'done' && (
        <>
          <CaseView
            env={opened.data}
            client={client}
            onChanged={(env) => setOpened({ kind: 'done', data: env })}
          />
          {opened.data.is_current && (
            <button type="button" onClick={() => startRevision(opened.data)}>
              Revise this case (creates a new, unreviewed version)
            </button>
          )}
        </>
      )}
    </section>
  )
}
