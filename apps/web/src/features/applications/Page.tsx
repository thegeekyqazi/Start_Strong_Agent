// Applications workspace. Owner: C. C1 spec rev 1.1 s7; C2 spec rev 1.1 s7; lane plan s6.3.
// All data comes from the API (fixture-backed). Everything renders as React text.
// Fact values are rendered by the server (s8.2); findings come from deterministic checks
// bound to the exact text. Nothing here reviews or approves an answer (SEC-14).
import { useEffect, useRef, useState, type ReactNode } from 'react'
import type {
  AnswerFinding,
  AnswerVersion,
  AnswerPlan,
  ApplicationWorkspace,
  CheckReport,
  DraftProposal,
  EvidenceBundle,
  Question,
  RenderedAnswer,
} from '@strongstart/contracts'
import {
  EvidenceCard,
  factStatusLabel,
  FindingRow,
  HashChip,
  PROVENANCE_LABEL,
  StatusDot,
} from '../../shell/components'
import {
  describeDraftError,
  describeWorkspaceError,
  httpApplicationsClient,
  type ApplicationsClient,
} from './client'
import { describeReviewError, httpReviewClient, type ReviewClient } from '../review/client'

const CHECK_DELAY_MS = 300

type Mode = 'working' | 'reviewed'
type Load =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; data: ApplicationWorkspace }
type Checked = { text: string; mode: Mode; report: CheckReport }

/** Server spans are Unicode code-point offsets; slice by code point, not UTF-16 unit. */
function RenderedPreview({
  rendered,
  bundle,
  heading,
}: {
  rendered: RenderedAnswer
  bundle: EvidenceBundle
  heading: string
}) {
  const chars = Array.from(rendered.text)
  const marks = [
    ...rendered.bindings.map((b) => ({ start: b.span_start, end: b.span_end, fact: b.fact_id })),
    ...rendered.unsupported_markers.map((m) => ({
      start: m.span_start,
      end: m.span_end,
      fact: null as string | null,
    })),
  ].sort((a, b) => a.start - b.start)
  const parts: ReactNode[] = []
  let pos = 0
  for (const m of marks) {
    if (m.start > pos) parts.push(chars.slice(pos, m.start).join(''))
    const text = chars.slice(m.start, m.end).join('')
    const fact = m.fact ? bundle.facts.find((f) => f.fact_id === m.fact) : undefined
    parts.push(
      fact ? (
        <span
          key={m.start}
          className="fact-chip"
          aria-label={`Linked fact ${fact.metric_id}: ${text}, ${
            fact.provenance.is_simulated ? 'simulated' : 'not simulated'
          }, ${factStatusLabel(fact.status).toLowerCase()}`}
        >
          {text} · {fact.provenance.is_simulated ? 'Simulated' : 'Source data'} ·{' '}
          {factStatusLabel(fact.status)}
        </span>
      ) : (
        <span key={m.start} className="fact-chip fact-chip-unknown">
          {text}
        </span>
      ),
    )
    pos = m.end
  }
  if (pos < chars.length) parts.push(chars.slice(pos).join(''))
  return (
    <section className="slot-preview" aria-label={heading}>
      <h4>{heading}</h4>
      <p>{parts}</p>
    </section>
  )
}

function QuestionNotices({ question }: { question: Question }) {
  const conflicts = question.conflicts ?? []
  const limit = question.limit ?? null
  return (
    <div className="limit-info">
      {conflicts.length === 0 && limit && limit.unit !== 'unknown' && limit.maximum != null && (
        <p>
          Limit: {limit.maximum} {limit.unit}.{' '}
          {limit.counting_convention
            ? `Counting method: ${limit.counting_convention}.`
            : 'Counting method not confirmed.'}
        </p>
      )}
      {conflicts.length === 0 && limit === null && <p>No limit is stated in the question data.</p>}
      {conflicts.map((c) => (
        <FindingRow
          key={c.conflict_id}
          origin="question_data"
          outcome="notice"
          message={`The guide gives ${c.candidate_limits.length} different limits: ${c.candidate_limits
            .map((l) => `${l.maximum ?? 'unknown'} ${l.unit}`)
            .join(' and ')}. We have not chosen one.`}
          nextAction="Ask staff to confirm which limit applies."
        />
      ))}
      {conflicts.length === 0 && limit?.unit === 'unknown' && (
        <FindingRow
          origin="question_data"
          outcome="notice"
          message={`The guide says "Max ${limit.maximum ?? 'unknown'}" but does not say words or characters. We have not chosen one.`}
          nextAction="Both counts are shown until staff confirm the unit."
        />
      )}
    </div>
  )
}

function Findings({ findings, stale }: { findings: AnswerFinding[]; stale: boolean }) {
  return (
    <section aria-labelledby="findings-heading" className={stale ? 'findings stale' : 'findings'}>
      <h4 id="findings-heading">Checks on this text</h4>
      {stale && (
        <p role="status" className="hint">
          Out of date – the text or check mode changed since these checks ran. Re-checking…
        </p>
      )}
      {findings.map((f, n) => (
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

function PlanPanel({ plan, questions }: { plan: AnswerPlan; questions: Question[] }) {
  const label = (id: string) => questions.find((q) => q.question_id === id)?.original_text ?? id
  return (
    <section aria-labelledby="plan-heading" className="plan-panel">
      <h3 id="plan-heading">Answer plan</h3>
      <p className="hint">
        {plan.planner.is_fixture
          ? 'Planned by the demo planning assistant (fixed sample output, not an AI model).'
          : `Planned by ${plan.planner.adapter} (${plan.planner.model}).`}{' '}
        A plan suggests evidence and lists what is missing; it never invents figures.
      </p>
      <ol>
        {plan.items.map((i) => (
          <li key={i.question_id}>
            <strong>{label(i.question_id)}</strong>
            <div>
              Evidence:{' '}
              {i.evidence_fact_ids.length ? i.evidence_fact_ids.join(', ') : 'none assigned'}
            </div>
            {i.missing_inputs.map((m) => (
              <div key={m}>Missing: {m} (not invented)</div>
            ))}
            {i.repeated_with.length > 0 && (
              <div>Asks for the same content as: {i.repeated_with.map(label).join('; ')}</div>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}

function QuestionTags({ q }: { q: Question }) {
  const tags: string[] = [
    q.required === true ? 'Required' : q.required === false ? 'Optional' : 'Required: not stated',
  ]
  if ((q.conflicts ?? []).length > 0) tags.push('Limit conflict')
  if (q.limit?.unit === 'unknown') tags.push('Unit unknown')
  return <span className="question-tags">{tags.join(' · ')}</span>
}

export function ApplicationsPage({
  client = httpApplicationsClient,
  reviewClient = httpReviewClient,
}: {
  client?: ApplicationsClient
  reviewClient?: ReviewClient
}) {
  const [load, setLoad] = useState<Load>({ kind: 'loading' })
  const [selected, setSelected] = useState<string | null>(null)
  const [texts, setTexts] = useState<Record<string, string>>({})
  const [drafts, setDrafts] = useState<Record<string, DraftProposal>>({})
  const [pending, setPending] = useState<Record<string, DraftProposal>>({})
  const [checked, setChecked] = useState<Record<string, Checked>>({})
  const [mode, setMode] = useState<Mode>('working')
  const [plan, setPlan] = useState<AnswerPlan | null>(null)
  const [planError, setPlanError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [draftError, setDraftError] = useState<string | null>(null)
  // Latest saved version per question (C3): number for optimistic saves, server state for display.
  const [saved, setSaved] = useState<Record<string, AnswerVersion | null>>({})
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  // Latest editor text, read after an await so in-flight typing is never overwritten (s15).
  const textsRef = useRef(texts)
  useEffect(() => {
    textsRef.current = texts
  }, [texts])

  useEffect(() => {
    let active = true
    client.workspace().then((r) => {
      if (!active) return
      if (r.ok) {
        setLoad({ kind: 'ready', data: r.data })
        setSelected(r.data.question_set.questions[0]?.question_id ?? null)
      } else {
        setLoad({ kind: 'error', message: describeWorkspaceError(r) })
      }
    })
    return () => {
      active = false
    }
  }, [client])

  const ws = load.kind === 'ready' ? load.data : null
  const question = ws?.question_set.questions.find((q) => q.question_id === selected) ?? null
  const text = question ? (texts[question.question_id] ?? '') : ''

  // Re-run deterministic checks after edits (debounced). Results bind to the exact text.
  useEffect(() => {
    if (!ws || !question) return
    const qid = question.question_id
    const handle = setTimeout(() => {
      client
        .check(qid, {
          question_version: question.question_version,
          evidence_bundle_id: ws.evidence_bundle.bundle_id,
          text,
          mode,
        })
        .then((r) => {
          if (r.ok) setChecked((c) => ({ ...c, [qid]: { text, mode, report: r.data } }))
        })
    }, CHECK_DELAY_MS)
    return () => clearTimeout(handle)
  }, [client, ws, question, text, mode])

  // Load the latest saved version for the selected question (C3 saved versions).
  useEffect(() => {
    if (!question || question.question_id in saved) return
    const qid = question.question_id
    reviewClient.history(qid).then((r) => {
      setSaved((s) => ({ ...s, [qid]: r.ok ? (r.data.versions.at(-1) ?? null) : null }))
    })
  }, [reviewClient, question, saved])

  if (load.kind === 'loading') return <p role="status">Loading the application…</p>
  if (load.kind === 'error' || !ws) {
    return (
      <section aria-labelledby="applications-heading">
        <h2 id="applications-heading">Applications</h2>
        <p role="alert">{load.kind === 'error' ? load.message : ''}</p>
      </section>
    )
  }

  const questions = [...ws.question_set.questions].sort((a, b) => a.order - b.order)
  const bundle = ws.evidence_bundle
  const draft = question ? drafts[question.question_id] : undefined
  const suggestion = question ? pending[question.question_id] : undefined
  const current = question ? checked[question.question_id] : undefined
  const stale = !!current && (current.text !== text || current.mode !== mode)
  const app01 = current?.report.findings.find((f) => f.result.rule_id === 'APP-01')

  async function requestPlan() {
    setPlanError(null)
    const r = await client.plan({ evidence_bundle_id: bundle.bundle_id })
    if (r.ok) setPlan(r.data)
    else setPlanError(describeDraftError(r))
  }

  async function requestDraft(q: Question) {
    setBusy(true)
    setDraftError(null)
    const r = await client.draft(q.question_id, {
      question_version: q.question_version,
      evidence_bundle_id: bundle.bundle_id,
    })
    setBusy(false)
    if (!r.ok) {
      setDraftError(describeDraftError(r))
      return
    }
    setDrafts((d) => ({ ...d, [q.question_id]: r.data }))
    if ((textsRef.current[q.question_id] ?? '').trim() === '') {
      setTexts((t) => ({ ...t, [q.question_id]: r.data.template_text }))
    } else {
      // Never overwrite staff work (engineering s15): keep the proposal separate.
      setPending((p) => ({ ...p, [q.question_id]: r.data }))
    }
  }

  function acceptSuggestion(q: Question, s: DraftProposal) {
    setTexts((t) => ({ ...t, [q.question_id]: s.template_text }))
    setPending((p) => {
      const next = { ...p }
      delete next[q.question_id]
      return next
    })
  }

  return (
    <section aria-labelledby="applications-heading">
      <h2 id="applications-heading">Applications</h2>
      <p>
        Draft answers to the funder's questions using your organization's evidence. Drafts are
        suggestions; nothing here is reviewed or approved.
      </p>
      {ws.is_fixture && <p className="badge badge-planned">{ws.data_label}</p>}
      <div className="plan-actions">
        <button type="button" onClick={requestPlan}>
          Plan this application
        </button>
        {planError && <p role="alert">{planError}</p>}
      </div>
      {plan && <PlanPanel plan={plan} questions={questions} />}
      <div className="workspace">
        <nav aria-label="Questions" className="ws-questions">
          <h3>Questions ({questions.length})</h3>
          {questions.length === 0 ? (
            <p>This application has no questions yet.</p>
          ) : (
            <ol>
              {questions.map((q) => (
                <li key={q.question_id}>
                  <button
                    type="button"
                    aria-current={q.question_id === selected ? 'true' : undefined}
                    onClick={() => {
                      setSelected(q.question_id)
                      setDraftError(null)
                    }}
                  >
                    <span className="question-section">
                      {q.order}. {q.section ?? 'Section not stated'}
                    </span>
                    <span className="question-text">{q.original_text}</span>
                    <QuestionTags q={q} />
                  </button>
                </li>
              ))}
            </ol>
          )}
        </nav>

        <div className="ws-editor">
          {question && (
            <>
              <h3>Funder's question (original wording)</h3>
              <blockquote className="original-question">{question.original_text}</blockquote>
              <p className="hint">
                {PROVENANCE_LABEL[question.source_refs[0].provenance.provenance_class] ??
                  question.source_refs[0].provenance.provenance_class}
              </p>
              <QuestionNotices question={question} />
              <fieldset className="mode-toggle">
                <legend>Check mode</legend>
                <label>
                  <input
                    type="radio"
                    name="mode"
                    checked={mode === 'working'}
                    onChange={() => setMode('working')}
                  />{' '}
                  Working draft (missing items are allowed and marked)
                </label>
                <label>
                  <input
                    type="radio"
                    name="mode"
                    checked={mode === 'reviewed'}
                    onChange={() => setMode('reviewed')}
                  />{' '}
                  Review check (missing items block review)
                </label>
              </fieldset>
              <p aria-live="polite" className="counter">
                {app01 && !stale ? app01.message : 'Counting…'}
              </p>
              <label htmlFor="answer-editor">Your answer</label>
              <textarea
                id="answer-editor"
                rows={8}
                value={text}
                onChange={(e) =>
                  setTexts((t) => ({ ...t, [question.question_id]: e.target.value }))
                }
              />
              <div className="draft-actions">
                <button
                  type="button"
                  onClick={() => requestDraft(question)}
                  disabled={busy}
                  aria-busy={busy}
                >
                  {busy ? 'Requesting a draft…' : 'Request a draft'}
                </button>
                <p className="hint">
                  The assistant suggests wording. Figures appear as linked facts, not typed numbers.
                  You stay in control of the text.
                </p>
              </div>
              {draftError && <p role="alert">{draftError}</p>}
              <div className="save-version">
                <button
                  type="button"
                  disabled={text.trim() === ''}
                  onClick={async () => {
                    setSaveMessage(null)
                    const latest = saved[question.question_id] ?? null
                    const r = await reviewClient.saveVersion({
                      question_id: question.question_id,
                      question_version: question.question_version,
                      evidence_bundle_id: bundle.bundle_id,
                      text,
                      expected_answer_version: latest ? latest.answer_version : null,
                    })
                    if (r.ok) {
                      setSaved((s) => ({ ...s, [question.question_id]: r.data }))
                      setSaveMessage(`Saved as version ${r.data.answer_version}.`)
                    } else setSaveMessage(describeReviewError(r))
                  }}
                >
                  Save version
                </button>{' '}
                {saved[question.question_id] && (
                  <span className="hint">
                    Latest saved: version {saved[question.question_id]?.answer_version}{' '}
                    <StatusDot status={saved[question.question_id]!.state} />{' '}
                    <a href="#/review">Open in Review</a>
                  </span>
                )}
                {saveMessage && <p role="status">{saveMessage}</p>}
              </div>
              {suggestion && (
                <section aria-labelledby="suggested-draft" className="suggestion">
                  <h4 id="suggested-draft">Suggested draft</h4>
                  <p>Your answer already has text, so the suggestion was not inserted.</p>
                  {suggestion.check && (
                    <RenderedPreview
                      rendered={suggestion.check.rendered}
                      bundle={bundle}
                      heading="Suggestion with linked facts"
                    />
                  )}
                  <button type="button" onClick={() => acceptSuggestion(question, suggestion)}>
                    Replace my text with this suggestion
                  </button>
                </section>
              )}
              {current && text.trim() !== '' && !stale && (
                <RenderedPreview
                  rendered={current.report.rendered}
                  bundle={bundle}
                  heading="Preview with linked facts"
                />
              )}
              {current && <Findings findings={current.report.findings} stale={stale} />}
              {draft && (
                <section aria-labelledby="draft-details" className="draft-details">
                  <h4 id="draft-details">About the latest suggestion</h4>
                  <p>
                    Drafted by:{' '}
                    {draft.provider.is_fixture
                      ? 'demo writing assistant (fixed sample output, not an AI model)'
                      : `${draft.provider.adapter} (${draft.provider.model})`}
                  </p>
                  <p className="draft-meta">
                    <StatusDot status="draft" />
                    <HashChip hash={draft.template_sha256} />
                  </p>
                  {draft.uncertainties.length > 0 && (
                    <>
                      <p>What the draft is unsure about:</p>
                      <ul>
                        {draft.uncertainties.map((u) => (
                          <li key={u}>{u}</li>
                        ))}
                      </ul>
                    </>
                  )}
                </section>
              )}
            </>
          )}
        </div>

        <aside aria-labelledby="evidence-heading" className="ws-evidence">
          <h3 id="evidence-heading">Evidence for this application</h3>
          <p className="hint">Not yet matched to individual questions.</p>
          {bundle.facts.length === 0 ? (
            <p>No evidence is available yet. Drafts can't link to facts until evidence is added.</p>
          ) : (
            bundle.facts.map((f) => (
              <EvidenceCard key={f.fact_id} fact={f} coverageNotes={bundle.coverage_notes ?? []} />
            ))
          )}
        </aside>
      </div>
    </section>
  )
}
