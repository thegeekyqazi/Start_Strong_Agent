// Applications workspace. Owner: C. C1 spec rev 1.0 s7; lane plan s6.3.
// All data comes from the API (fixture-backed in C1). Everything renders as React text.
// Drafts are proposals: nothing here reviews or approves an answer (SEC-14).
import { useEffect, useRef, useState, type ReactNode } from 'react'
import type {
  ApplicationWorkspace,
  DraftProposal,
  EvidenceBundle,
  Fact,
  Question,
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
import { countCharacters, countWords } from './counter'

const SLOT = /\{\{fact:([a-z0-9][a-z0-9._:-]{0,127})\}\}/g
const COUNT_NOTE = '(placeholder count; counting convention unverified)'

type Load =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; data: ApplicationWorkspace }

function factChipText(fact: Fact): string {
  const value = fact.value ?? 'unknown value'
  const unit = fact.unit ?? '(unit unknown)'
  const period = fact.reporting_period ?? 'period unknown'
  const prov = fact.provenance.is_simulated
    ? 'Simulated'
    : PROVENANCE_LABEL[fact.provenance.provenance_class]
  return `${value} ${unit} · ${period} · ${prov} · ${factStatusLabel(fact.status)}`
}

function SlotPreview({ text, bundle }: { text: string; bundle: EvidenceBundle }) {
  const parts: ReactNode[] = []
  let last = 0
  for (const m of text.matchAll(SLOT)) {
    const start = m.index ?? 0
    if (start > last) parts.push(text.slice(last, start))
    const fact = bundle.facts.find((f) => f.fact_id === m[1])
    parts.push(
      fact ? (
        <span
          key={start}
          className="fact-chip"
          aria-label={`Linked fact ${fact.metric_id}: ${factChipText(fact)}`}
        >
          {factChipText(fact)}
        </span>
      ) : (
        <span key={start} className="fact-chip fact-chip-unknown">
          Unknown fact – not shown
        </span>
      ),
    )
    last = start + m[0].length
  }
  if (last < text.length) parts.push(text.slice(last))
  return (
    <section aria-labelledby="slot-preview" className="slot-preview">
      <h4 id="slot-preview">Preview with linked facts</h4>
      <p>{parts}</p>
    </section>
  )
}

function LimitInfo({ question, text }: { question: Question; text: string }) {
  const words = countWords(text)
  const chars = countCharacters(text)
  const conflicts = question.conflicts ?? []
  const limit = question.limit ?? null
  let summary: string
  if (conflicts.length > 0) {
    summary = `Placeholder count: ${words} words, ${chars} characters ${COUNT_NOTE}`
  } else if (limit === null || limit.maximum === null || limit.maximum === undefined) {
    summary = `Placeholder count: ${words} words ${COUNT_NOTE}`
  } else if (limit.unit === 'unknown') {
    summary = `Placeholder count: ${words} words, ${chars} characters ${COUNT_NOTE}`
  } else {
    const n = limit.unit === 'characters' ? chars : words
    const over = n - limit.maximum
    summary = `Placeholder count: ${n} of ${limit.maximum} ${limit.unit}${over > 0 ? ` – ${over} over` : ''} ${COUNT_NOTE}`
  }
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
      {question.required === null && (
        <FindingRow
          origin="question_data"
          outcome="notice"
          message="The guide does not say whether this question is required."
        />
      )}
      <p aria-live="polite" className="counter">
        {summary}
      </p>
    </div>
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
}: {
  client?: ApplicationsClient
}) {
  const [load, setLoad] = useState<Load>({ kind: 'loading' })
  const [selected, setSelected] = useState<string | null>(null)
  const [texts, setTexts] = useState<Record<string, string>>({})
  const [drafts, setDrafts] = useState<Record<string, DraftProposal>>({})
  const [pending, setPending] = useState<Record<string, DraftProposal>>({})
  const [busy, setBusy] = useState(false)
  const [draftError, setDraftError] = useState<string | null>(null)
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

  if (load.kind === 'loading') return <p role="status">Loading the application…</p>
  if (load.kind === 'error') {
    return (
      <section aria-labelledby="applications-heading">
        <h2 id="applications-heading">Applications</h2>
        <p role="alert">{load.message}</p>
      </section>
    )
  }

  const ws = load.data
  const questions = [...ws.question_set.questions].sort((a, b) => a.order - b.order)
  const question = questions.find((q) => q.question_id === selected) ?? null
  const bundle = ws.evidence_bundle
  const text = question ? (texts[question.question_id] ?? '') : ''
  const draft = question ? drafts[question.question_id] : undefined
  const suggestion = question ? pending[question.question_id] : undefined

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
              <LimitInfo question={question} text={text} />
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
              {suggestion && (
                <section aria-labelledby="suggested-draft" className="suggestion">
                  <h4 id="suggested-draft">Suggested draft</h4>
                  <p>Your answer already has text, so the suggestion was not inserted.</p>
                  <SlotPreview text={suggestion.template_text} bundle={bundle} />
                  <button type="button" onClick={() => acceptSuggestion(question, suggestion)}>
                    Replace my text with this suggestion
                  </button>
                </section>
              )}
              {text.trim() !== '' && <SlotPreview text={text} bundle={bundle} />}
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
