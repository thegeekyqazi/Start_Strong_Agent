// AUTO2-27: only IDs reach preparation; execution always uses the exact server plan.
import { useEffect, useRef, useState } from 'react'
import type {
  PrefillPlan,
  PrefillPlanView,
  PrefillRunView,
  PreparePrefillPlanRequest,
  PublishedApplicationVersion,
} from '@strongstart/contracts'
import {
  describeError,
  executePrefill,
  getPrefillPlan,
  getPrefillRun,
  getQuestionSet,
  newIdempotencyKey,
  preparePrefill,
} from './api'

import { readApprovedSelection } from './approvedHandoff'

export const PREFILL_PENDING_KEY = 'strongstart.automation.prefill.pending.v1'
type Intent = { planId: string; hash: string; key: string }

function remembered(): Intent | null {
  try {
    const p = JSON.parse(sessionStorage.getItem(PREFILL_PENDING_KEY) ?? 'null')
    return p &&
      /^pfp-[0-9a-f]{26}$/.test(p.planId) &&
      /^[0-9a-f]{64}$/.test(p.hash) &&
      /^[A-Za-z0-9._:-]{8,128}$/.test(p.key)
      ? p
      : null
  } catch {
    return null
  }
}

function remember(intent: Intent): boolean {
  try {
    sessionStorage.setItem(PREFILL_PENDING_KEY, JSON.stringify(intent))
    return true
  } catch {
    return false
  }
}

const OUTCOME: Record<string, string> = {
  in_progress: 'Running — this plan has already been claimed',
  selected_fields_verified: 'Selected fields verified',
  stopped_with_partial_entry: 'Stopped with partial entry',
  blocked_before_entry: 'Blocked before entry',
  outcome_unknown: 'Outcome unknown — do not assume entry succeeded',
}

export function PrefillPanel() {
  const [handoff] = useState(readApprovedSelection)
  const [questionSet, setQuestionSet] = useState(handoff?.questionSetId ?? '')
  const [portal, setPortal] = useState('rep-prefill-v1')
  const [definition, setDefinition] = useState<PublishedApplicationVersion | null>(null)
  const [approvals, setApprovals] = useState<Record<string, string>>({})
  const [plan, setPlan] = useState<PrefillPlan | null>(null)
  const [availability, setAvailability] = useState<PrefillPlanView['availability']>('empty')
  const [nextAction, setNextAction] = useState('')
  const [receipt, setReceipt] = useState<PrefillRunView | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [pending, setPending] = useState<Intent | null>(remembered)
  const generation = useRef(0)
  const inFlight = useRef(false)
  const intentRef = useRef<Intent | null>(pending)

  useEffect(
    () => () => {
      generation.current++
    },
    [],
  )

  useEffect(() => {
    if (!handoff) return
    const token = ++generation.current
    inFlight.current = true
    setBusy('Loading approved answer selection')
    getQuestionSet(handoff.questionSetId).then((r) => {
      if (token !== generation.current) return
      inFlight.current = false
      setBusy('')
      if (!r.ok) {
        setError(describeError(r))
        return
      }
      if (
        !Object.keys(handoff.approvals).every((id) =>
          r.data.id_mapping.some((m) => m.published_question_id === id),
        )
      ) {
        setError(
          'The approved selection does not match these questions. Return to Review and select a current answer.',
        )
        return
      }
      setDefinition(r.data)
      setApprovals(handoff.approvals)
      setPortal(
        r.data.id_mapping.some((m) => m.original_question_id.startsWith('rp-'))
          ? 'rep-portal-v1'
          : 'rep-prefill-v1',
      )
    })
    return () => {
      generation.current++
    }
  }, [handoff])

  function changed() {
    generation.current++
    inFlight.current = false
    setBusy('')
    setError('')
    setPlan(null)
    setAvailability('empty')
    setNextAction('')
    setReceipt(null)
    // Pending execution identity survives selection changes and refresh. It is read-only
    // unless staff explicitly retries the same displayed plan.
  }

  async function load() {
    if (inFlight.current) return
    const token = ++generation.current
    inFlight.current = true
    setBusy('Loading questions')
    setError('')
    setPlan(null)
    setReceipt(null)
    const r = await getQuestionSet(questionSet.trim())
    if (token !== generation.current) return
    inFlight.current = false
    setBusy('')
    if (r.ok) {
      setDefinition(r.data)
      setApprovals({})
    } else {
      setDefinition(null)
      setError(describeError(r))
    }
  }

  async function prepare() {
    if (!definition || inFlight.current) return
    const selections = definition.id_mapping
      .filter((m) => approvals[m.published_question_id]?.trim())
      .map((m) => ({
        published_question_id: m.published_question_id,
        approval_snapshot_id: approvals[m.published_question_id].trim(),
      }))
    if (!selections.length || selections.length > 20) {
      setError('Select between 1 and 20 existing approval IDs.')
      return
    }
    const token = ++generation.current
    inFlight.current = true
    setBusy('Preparing exact plan')
    setError('')
    setPlan(null)
    setReceipt(null)
    const r = await preparePrefill({
      question_set_id: definition.question_set_id,
      portal_fixture_id: portal,
      selections: selections as PreparePrefillPlanRequest['selections'],
    })
    if (token !== generation.current) return
    inFlight.current = false
    setBusy('')
    if (r.ok) {
      setPlan(r.data)
      setAvailability(r.data.executable ? 'executable' : 'empty')
      setNextAction('')
      intentRef.current = null
    } else setError(describeError(r))
  }

  async function fill() {
    if (!plan || !plan.executable || availability !== 'executable' || inFlight.current || receipt)
      return
    let intent = intentRef.current
    if (!intent || intent.planId !== plan.plan_id || intent.hash !== plan.plan_sha256) {
      intent = { planId: plan.plan_id, hash: plan.plan_sha256, key: newIdempotencyKey() }
      if (!remember(intent)) {
        setError('Cannot retain execution identity in this tab. Entry is blocked.')
        return
      }
      intentRef.current = intent
      setPending(intent)
    }
    const token = generation.current
    inFlight.current = true
    setBusy('Running approved entry')
    setError('')
    const r = await executePrefill(intent.planId, {
      expected_plan_sha256: intent.hash,
      idempotency_key: intent.key,
    })
    if (token !== generation.current) return
    inFlight.current = false
    setBusy('')
    if (r.ok) setReceipt(r.data.run)
    else
      setError(
        `${describeError(r)} Check the stored receipt before any further action. An explicit retry uses the same request identity.`,
      )
  }

  async function refreshUsability() {
    if (!plan || inFlight.current) return
    const token = generation.current
    inFlight.current = true
    setBusy('Checking current sources')
    const result = await getPrefillPlan(plan.plan_id)
    if (token !== generation.current) return
    inFlight.current = false
    setBusy('')
    if (!result.ok) {
      setError(describeError(result))
      return
    }
    if (result.data.plan.plan_sha256 !== plan.plan_sha256) {
      setAvailability('stale')
      setError('The saved plan failed verification. Prepare a new plan.')
      return
    }
    setAvailability(result.data.availability)
    setNextAction(result.data.next_action ?? '')
  }

  async function checkReceipt() {
    if (!pending || inFlight.current) return
    const token = generation.current
    inFlight.current = true
    setBusy('Checking stored execution')
    setError('')
    const p = await getPrefillPlan(pending.planId)
    if (token !== generation.current) return
    if (!p.ok) {
      inFlight.current = false
      setBusy('')
      setError(describeError(p))
      return
    }
    if (p.data.plan.plan_sha256 !== pending.hash) {
      inFlight.current = false
      setBusy('')
      setError('Stored plan hash changed. Entry is blocked.')
      return
    }
    if (!p.data.run_id) {
      inFlight.current = false
      setBusy('')
      setError(
        'No execution has been claimed. Refresh never starts entry. Prepare and review a new plan to proceed.',
      )
      return
    }
    const r = await getPrefillRun(p.data.run_id)
    if (token !== generation.current) return
    inFlight.current = false
    setBusy('')
    if (r.ok) {
      setPlan(p.data.plan)
      setReceipt(r.data)
    } else setError(describeError(r))
  }

  return (
    <section className="panel" aria-labelledby="prefill-heading">
      <h3 id="prefill-heading">4. Approved selected-field prefill</h3>
      <p>
        Local fixture demonstration with the connected C approved-content reader. Approve answers in
        Review, then use them here. No approvals are seeded. The ephemeral page closes after entry;
        this receipt does not establish application completeness.
      </p>
      {handoff && (
        <p role="status">
          Selected from Review: {Object.keys(handoff.approvals).length} approved answer(s). Return
          to Review to add another answer for this question set. The server checks every approval
          again.
        </p>
      )}
      <label>
        Exact saved question-set ID
        <input
          value={questionSet}
          onChange={(e) => {
            changed()
            setQuestionSet(e.target.value)
            setDefinition(null)
            setApprovals({})
          }}
        />
      </label>
      <button onClick={load} disabled={!!busy || !questionSet.trim()}>
        Load prefill questions
      </button>
      <label>
        Registered prefill portal
        <select
          value={portal}
          onChange={(e) => {
            changed()
            setPortal(e.target.value)
          }}
        >
          <option value="rep-prefill-v1">rep-prefill-v1 — unambiguous fixture</option>
          <option value="rep-portal-v1">rep-portal-v1 — unresolved requirements remain held</option>
        </select>
      </label>
      {definition && (
        <>
          <p>
            Exact selection: <code>{definition.question_set_id}</code>, version {definition.version}
            . Saved is not approved.
          </p>
          {definition.id_mapping.map((m) => (
            <label key={m.published_question_id}>
              Approval ID for {m.original_question_id} <code>{m.published_question_id}</code>
              <input
                value={approvals[m.published_question_id] ?? ''}
                onChange={(e) => {
                  changed()
                  setApprovals((a) => ({ ...a, [m.published_question_id]: e.target.value }))
                }}
              />
            </label>
          ))}
          <button onClick={prepare} disabled={!!busy}>
            Prepare selected-field plan (no entry)
          </button>
        </>
      )}
      {busy && <p role="status">{busy}…</p>}
      {error && <p role="alert">{error}</p>}
      {plan && (
        <>
          <h4>Exact approved plan preview</h4>
          <p>{plan.mode_label}</p>
          <p>{plan.scope_note}</p>
          <p>
            {plan.producers.approval_reader === 'c_reader'
              ? 'C producer connected'
              : 'Explicit test approval provider'}{' '}
            ·
            {plan.producers.dependency_currentness === 'a4_adapter'
              ? 'Managed A4 currentness registered'
              : 'A4 not integrated for this evidence (unmanaged demo)'}
          </p>
          <p aria-live="polite">
            Plan usability: {availability}. {nextAction}
          </p>
          <button onClick={refreshUsability} disabled={!!busy}>
            Check current sources (no entry)
          </button>
          <p>
            Plan <code>{plan.plan_id}</code> · hash <code>{plan.plan_sha256}</code> · expires{' '}
            {plan.expires_at}
          </p>
          <ol>
            {plan.actions.map((a) => (
              <li key={a.action_index}>
                <strong>{a.published_question_id}</strong> → {a.field_id} ({a.operation})
                <pre className="raw">{a.intended_value ?? JSON.stringify(a.intended_choices)}</pre>
                <p>
                  Approval {a.approval_snapshot_id} · answer {a.answer_version_id}
                </p>
                <p>
                  Template hash <code>{a.template_sha256}</code> · rendered hash{' '}
                  <code>{a.rendered_sha256}</code>
                </p>
                <p>
                  {(a.constraints ?? []).join('; ')} · {a.comparison}
                </p>
              </li>
            ))}
          </ol>
          <h4>Held fields</h4>
          {(plan.held ?? []).length ? (
            <ul>
              {(plan.held ?? []).map((h) => (
                <li key={h.published_question_id}>
                  {h.published_question_id}: {h.reason} — {h.detail}
                </li>
              ))}
            </ul>
          ) : (
            <p>No selected fields held.</p>
          )}
          <h4>Other requirements</h4>
          <ul>
            {(plan.unselected_requirements ?? []).map((q) => (
              <li key={q.published_question_id}>
                {q.published_question_id}: {q.required_status}, unselected
              </li>
            ))}
          </ul>
          <h4>Attachment checklist — upload disabled</h4>
          <ul>
            {(plan.attachments ?? []).map((a) => (
              <li key={a.published_question_id}>
                {a.published_question_id}: {a.status} · types{' '}
                {a.accepted_types?.join(', ') ?? 'unknown'} · size {a.max_size_bytes ?? 'unknown'}{' '}
                bytes · count {a.max_count ?? 'unknown'}
                <p>
                  {(a.findings ?? []).join('; ')} · {a.evidence_basis}
                </p>
              </li>
            ))}
          </ul>
          {!plan.executable && (
            <p role="status">Entry blocked: {(plan.not_executable_reasons ?? []).join('; ')}</p>
          )}
          <button
            onClick={fill}
            disabled={!!busy || !plan.executable || availability !== 'executable' || !!receipt}
          >
            Fill these approved fields
          </button>
        </>
      )}
      {pending && (
        <p>
          Execution identity retained for <code>{pending.planId}</code>. Refresh never executes it.{' '}
          <button onClick={checkReceipt} disabled={!!busy}>
            Check stored receipt
          </button>
        </p>
      )}
      {receipt && (
        <section aria-label="Read-back receipt">
          <h4>{OUTCOME[receipt.effective_outcome]}</h4>
          <p>{receipt.run.outcome_reason}</p>
          <p>{receipt.history_note}</p>
          <p>{receipt.run.receipt_note}</p>
          <p>Final reread: {receipt.run.final_reread}. No application was submitted.</p>
          <ul>
            {receipt.run.fields.map((f) => (
              <li key={f.action_index}>
                {f.field_id}: {f.state} ({f.result})<pre className="raw">{f.actual_value}</pre>
                <p>
                  Intended <code>{f.intended_sha256}</code> · actual <code>{f.actual_sha256}</code>{' '}
                  · {f.comparison}
                </p>
                <p>
                  {f.reason} · {f.next_action}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  )
}
