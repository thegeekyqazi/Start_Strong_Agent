// Review page. Owner: C. C3 spec rev 1.0 s7; engineering s18 "Review" row.
// Shows exact versions, their differences, deterministic findings, reviewer suggestions,
// notes, exact-version approval and export readiness. Everything renders as React text.
// State and staleness come from the server; nothing here decides them (SEC-14).
import { useCallback, useEffect, useState } from 'react'
import type {
  AnswerHistory,
  AnswerVersion,
  ApplicationWorkspace,
  ExportResult,
} from '@strongstart/contracts'
import { FindingRow, HashChip, StatusDot } from '../../shell/components'
import {
  describeWorkspaceError,
  httpApplicationsClient,
  type ApplicationsClient,
} from '../applications/client'
import { QuestionSetPicker } from '../applications/QuestionSetPicker'
import {
  httpQuestionSetClient,
  loadSelectedQuestionSet,
  saveSelectedQuestionSet,
  type QuestionSetClient,
} from '../applications/questionSets'
import { describeReviewError, httpReviewClient, type ReviewClient } from './client'
import { wordDiff } from './diff'
import { selectApprovedAnswer } from '../automation/approvedHandoff'

const STALE_REASON: Record<string, string> = {
  newer_version_saved: 'a newer version was saved',
  dependency_changed: 'linked evidence, the question, policy or rules changed',
}

function staleText(reason: string | null | undefined): string {
  if (!reason) return 'its dependencies changed'
  if (reason.startsWith('change_set_applied:'))
    return `a published evidence change (${reason.split(':')[1]}) touched its facts`
  return STALE_REASON[reason] ?? reason
}

function Diff({ before, after }: { before: AnswerVersion; after: AnswerVersion }) {
  const parts = wordDiff(before.rendered.text, after.rendered.text)
  return (
    <section aria-labelledby="diff-heading" className="diff">
      <h4 id="diff-heading">
        Changes from version {before.answer_version} to version {after.answer_version}
      </h4>
      <p>
        {parts.map((p, n) =>
          p.kind === 'same' ? (
            <span key={n}>{p.text}</span>
          ) : p.kind === 'added' ? (
            <ins key={n} aria-label={`added: ${p.text}`}>
              {p.text}
            </ins>
          ) : (
            <del key={n} aria-label={`removed: ${p.text}`}>
              {p.text}
            </del>
          ),
        )}
      </p>
    </section>
  )
}

export function ReviewPage({
  appClient = httpApplicationsClient,
  client = httpReviewClient,
  questionSets = httpQuestionSetClient,
}: {
  appClient?: ApplicationsClient
  client?: ReviewClient
  questionSets?: QuestionSetClient
}) {
  // C2b: the same explicit question-set choice as the Applications page (shared per tab).
  const [qsId, setQsId] = useState<string | null>(loadSelectedQuestionSet)
  const [loadedFor, setLoadedFor] = useState<string | null | undefined>(undefined)
  const [ws, setWs] = useState<ApplicationWorkspace | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [questionId, setQuestionId] = useState<string | null>(null)
  const [hist, setHist] = useState<AnswerHistory | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [ack, setAck] = useState(false)
  const [note, setNote] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [exported, setExported] = useState<ExportResult | null>(null)

  useEffect(() => {
    let active = true
    appClient.workspace(qsId).then((r) => {
      if (!active) return
      setLoadedFor(qsId)
      if (r.ok) {
        setWs(r.data)
        setLoadError(null)
        setQuestionId(r.data.question_set.questions[0]?.question_id ?? null)
      } else {
        setWs(null)
        setHist(null)
        setLoadError(describeWorkspaceError(r))
      }
    })
    return () => {
      active = false
    }
  }, [appClient, qsId])

  function chooseQuestionSet(id: string | null) {
    saveSelectedQuestionSet(id)
    setQsId(id)
    setMessage(null)
    setExported(null)
  }

  const picker = (
    <QuestionSetPicker value={qsId} onChange={chooseQuestionSet} client={questionSets} />
  )

  const reload = useCallback(async () => {
    if (!questionId) return
    const r = await client.history(questionId, qsId)
    if (r.ok) {
      setHist(r.data)
      setSelectedId(r.data.versions.at(-1)?.answer_version_id ?? null)
      setAck(false)
    } else setMessage(describeReviewError(r))
  }, [client, questionId, qsId])

  // Load history when the question changes (state is set only in the async callback).
  useEffect(() => {
    if (!questionId) return
    let active = true
    client.history(questionId, qsId).then((r) => {
      if (!active) return
      if (r.ok) {
        setHist(r.data)
        setSelectedId(r.data.versions.at(-1)?.answer_version_id ?? null)
        setAck(false)
      } else setMessage(describeReviewError(r))
    })
    return () => {
      active = false
    }
  }, [client, questionId, qsId])

  if (loadedFor !== qsId || (!ws && !loadError))
    return (
      <section aria-labelledby="review-heading">
        <h2 id="review-heading">Review</h2>
        {picker}
        <p role="status">Loading reviews…</p>
      </section>
    )
  if (loadError || !ws)
    return (
      <section aria-labelledby="review-heading">
        <h2 id="review-heading">Review</h2>
        {picker}
        <p role="alert">{loadError}</p>
        {qsId && (
          <button type="button" onClick={() => chooseQuestionSet(null)}>
            Use the demo fixture questions instead
          </button>
        )}
      </section>
    )

  const questions = [...ws.question_set.questions].sort((a, b) => a.order - b.order)
  const versions = hist?.versions ?? []
  const latest = versions.at(-1)
  const selected = versions.find((v) => v.answer_version_id === selectedId) ?? latest
  const previous = selected
    ? versions.find((v) => v.answer_version === selected.answer_version - 1)
    : undefined
  const latestApproval = hist?.approvals.find(
    (a) => a.answer_version_id === latest?.answer_version_id,
  )
  const anyStale = hist?.approvals.find((a) => a.is_stale)
  const decided = !!hist?.approvals.find((a) => a.answer_version_id === selected?.answer_version_id)
  const reviewItems =
    selected?.check.findings.filter((f) => f.result.outcome === 'needs_review').length ?? 0

  async function decide(decision: 'approve' | 'reject') {
    if (!selected) return
    setMessage(null)
    const r = await client.decide({
      answer_version_id: selected.answer_version_id,
      expected_content_sha256: selected.content_sha256,
      expected_snapshot_sha256: selected.snapshot_sha256,
      decision,
      note,
      acknowledge_review_items: ack,
    })
    if (!r.ok) setMessage(describeReviewError(r))
    else {
      setNote('')
      setMessage(decision === 'approve' ? 'Approved this exact version.' : 'Rejected this version.')
      await reload()
    }
  }

  async function addNote() {
    if (!selected || note.trim() === '') return
    const r = await client.addNote({ answer_version_id: selected.answer_version_id, text: note })
    if (!r.ok) setMessage(describeReviewError(r))
    else {
      setNote('')
      await reload()
    }
  }

  async function ask(role: 'numerical_reviewer' | 'meaning_reviewer') {
    if (!selected) return
    const r = await client.propose({ answer_version_id: selected.answer_version_id, role })
    if (!r.ok) setMessage(describeReviewError(r))
    else await reload()
  }

  async function exportAs(mode: 'working' | 'reviewed') {
    const [first, ...rest] = questions.map((q) => q.question_id)
    if (first === undefined) return // the contract requires at least one question
    const r = await client.exportAnswers({
      mode,
      question_ids: [first, ...rest],
      question_set_id: qsId,
    })
    if (r.ok) setExported(r.data)
    else setMessage(describeReviewError(r))
  }

  return (
    <section aria-labelledby="review-heading">
      <h2 id="review-heading">Review</h2>
      <p>
        Check exact answer versions, then approve or reject them. An approval covers one exact
        version; any edit or evidence change makes it out of date.
      </p>
      {hist?.store_is_fixture && (
        <p className="badge badge-planned">
          FIXTURE store – saved versions and approvals are demo data and are lost on restart.
          Fixture approval – not authentication.
        </p>
      )}
      {picker}
      {ws.question_set_ref && (
        <p className="hint">
          Questions from saved definition {ws.question_set_ref.definition_id}, version{' '}
          {ws.question_set_ref.definition_version} (saved, not reviewed by Dev B).
        </p>
      )}
      <label htmlFor="review-question">Question</label>{' '}
      <select
        id="review-question"
        value={questionId ?? ''}
        onChange={(e) => {
          setQuestionId(e.target.value)
          setMessage(null)
        }}
      >
        {questions.map((q) => (
          <option key={q.question_id} value={q.question_id}>
            {q.order}. {q.original_text}
          </option>
        ))}
      </select>
      {versions.length > 0 && (
        <p role="status" className="prefill">
          {hist?.prefill_ready
            ? 'Ready for prefill: the latest version is approved and current.'
            : latestApproval
              ? 'Not ready for prefill: the approval of the latest version no longer applies.'
              : 'Not ready for prefill: the latest version is not approved.'}
        </p>
      )}
      {qsId &&
        loadedFor === qsId &&
        hist?.question_id === questionId &&
        hist?.prefill_ready &&
        latest?.question_set_id === qsId &&
        latestApproval?.decision === 'approve' &&
        !latestApproval.is_stale && (
          <button
            type="button"
            onClick={() =>
              selectApprovedAnswer(qsId, latest.question_id, latestApproval.approval_id)
            }
          >
            Use approved answer in Automation
          </button>
        )}
      {anyStale && (
        <p role="alert" className="stale-banner">
          Out of date – the approval of version{' '}
          {versions.find((v) => v.answer_version_id === anyStale.answer_version_id)?.answer_version}{' '}
          no longer applies because {staleText(anyStale.stale_reason)}.
        </p>
      )}
      {message && <p role="alert">{message}</p>}
      {versions.length === 0 ? (
        <p>No saved versions yet. Save one from the Applications page.</p>
      ) : (
        <div className="review-layout">
          <nav aria-label="Versions" className="versions">
            <h3>Versions</h3>
            <ol>
              {[...versions].reverse().map((v) => (
                <li key={v.answer_version_id}>
                  <button
                    type="button"
                    aria-current={
                      v.answer_version_id === selected?.answer_version_id ? 'true' : undefined
                    }
                    onClick={() => {
                      setSelectedId(v.answer_version_id)
                      setAck(false)
                    }}
                  >
                    Version {v.answer_version}
                    {v.is_latest ? ' (latest)' : ''} <StatusDot status={v.state} />
                  </button>
                </li>
              ))}
            </ol>
          </nav>

          {selected && (
            <div className="version-detail">
              <h3>
                Version {selected.answer_version} <StatusDot status={selected.state} />
              </h3>
              <p className="draft-meta">
                <HashChip hash={selected.content_sha256} />
                <span className="hint">Saved by {selected.created_by}</span>
              </p>
              <blockquote className="original-question">{selected.rendered.text}</blockquote>
              {previous && <Diff before={previous} after={selected} />}

              <section aria-labelledby="checks-heading">
                <h4 id="checks-heading">Checks (review mode)</h4>
                {selected.check.findings.map((f, n) => (
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

              <section aria-labelledby="suggestions-heading">
                <h4 id="suggestions-heading">Reviewer suggestions</h4>
                <p className="hint">Suggestions only – they cannot approve anything.</p>
                <button type="button" onClick={() => ask('numerical_reviewer')}>
                  Ask the numbers reviewer
                </button>{' '}
                <button type="button" onClick={() => ask('meaning_reviewer')}>
                  Ask the meaning reviewer
                </button>
                <ul>
                  {hist?.proposals
                    .filter((p) => p.answer_version_id === selected.answer_version_id)
                    .flatMap((p) =>
                      p.findings.map((f, n) => (
                        <li key={`${p.proposal_id}-${n}`}>
                          {p.role === 'numerical_reviewer'
                            ? 'Numbers reviewer'
                            : 'Meaning reviewer'}
                          {p.reviewer.is_fixture ? ' (demo, not an AI model)' : ''}: {f.concern}
                        </li>
                      )),
                    )}
                </ul>
              </section>

              <section aria-labelledby="notes-heading">
                <h4 id="notes-heading">Notes</h4>
                <ul>
                  {hist?.notes
                    .filter((n) => n.answer_version_id === selected.answer_version_id)
                    .map((n) => (
                      <li key={n.note_id}>
                        {n.author_id}: {n.text}
                      </li>
                    ))}
                </ul>
                <label htmlFor="review-note">Note or decision comment</label>
                <textarea
                  id="review-note"
                  rows={3}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
                <button type="button" onClick={addNote}>
                  Add note
                </button>
              </section>

              {selected.is_latest && !decided && (
                <section aria-labelledby="decide-heading" className="decide">
                  <h4 id="decide-heading">Decision</h4>
                  {reviewItems > 0 && (
                    <label>
                      <input
                        type="checkbox"
                        checked={ack}
                        onChange={(e) => setAck(e.target.checked)}
                      />{' '}
                      I have read all {reviewItems} "Needs your review" items above.
                    </label>
                  )}
                  <p>
                    <button type="button" onClick={() => decide('approve')}>
                      Approve this exact version ({selected.content_sha256.slice(0, 12)}…)
                    </button>{' '}
                    <button type="button" onClick={() => decide('reject')}>
                      Reject
                    </button>
                  </p>
                </section>
              )}
            </div>
          )}
        </div>
      )}
      <section aria-labelledby="export-heading" className="export">
        <h3 id="export-heading">Export</h3>
        <button type="button" onClick={() => exportAs('working')}>
          Export working draft (DOCX)
        </button>{' '}
        <button type="button" onClick={() => exportAs('reviewed')}>
          Export reviewed (DOCX)
        </button>
        {exported && (
          <div role="status">
            <p>{exported.labels.join(' · ')}</p>
            {exported.blocked ? (
              <>
                <p>Reviewed export blocked:</p>
                <ul>
                  {exported.blocked_by.map((b, n) => (
                    <li key={n}>
                      {questions.find((q) => q.question_id === b.question_id)?.original_text ??
                        b.question_id}
                      : {b.message}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              exported.export_id && (
                <p>
                  <a href={client.downloadUrl(exported.export_id, 'docx')}>Download DOCX</a> ·{' '}
                  <a href={client.downloadUrl(exported.export_id, 'audit')}>Download audit JSON</a>
                </p>
              )
            )}
          </div>
        )}
      </section>
    </section>
  )
}
