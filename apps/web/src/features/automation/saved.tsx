// Saved definitions (owner: B2; DEV-B-BUNDLE-002 M1). Save the current preview as an immutable
// version, list saved definitions, reopen one exactly and copy its question-set ID for Dev C.
// Saving is not reviewing or approving. All imported strings render as escaped React text.
import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  ApplicationIntakeResult,
  DefinitionList,
  PublishedApplicationVersion,
} from '@strongstart/contracts'
import {
  describeError,
  getDefinition,
  getQuestionSet,
  listDefinitions,
  newIdempotencyKey,
  saveDefinition,
  type IntakeSource,
} from './api'
import { EvidencePanel, QuestionTable } from './views'

export interface Preview {
  token: number
  result: ApplicationIntakeResult
  source: IntakeSource
}

type SaveState =
  | { kind: 'idle' }
  | { kind: 'saving'; token: number }
  | { kind: 'saved'; token: number; pub: PublishedApplicationVersion; replayed: boolean }
  | { kind: 'error'; token: number; message: string }

type Load<T> =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'done'; data: T }

const CASE_ID = /^case-[0-9a-f]{26}$/

function toListState(r: Awaited<ReturnType<typeof listDefinitions>>): Load<DefinitionList> {
  if (!r.ok) return { kind: 'error', message: describeError(r) }
  if (!r.data || !Array.isArray(r.data.items)) {
    return { kind: 'error', message: 'The saved-definition list response was not understood.' }
  }
  return { kind: 'done', data: r.data }
}

export function SavedDefinitions({ preview }: { preview: Preview | null }) {
  const [list, setList] = useState<Load<DefinitionList>>({ kind: 'loading' })
  const [target, setTarget] = useState('')
  const [caseId, setCaseId] = useState('')
  const [caseVersion, setCaseVersion] = useState('')
  const [saveState, setSave] = useState<SaveState>({ kind: 'idle' })
  // A save result belongs to the preview it was made for; a new preview shows none.
  const save: SaveState =
    saveState.kind !== 'idle' && saveState.token === preview?.token ? saveState : { kind: 'idle' }
  const [opened, setOpened] = useState<Load<PublishedApplicationVersion>>({ kind: 'idle' })
  const [selected, setSelected] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const tokenRef = useRef<number | null>(preview?.token ?? null)
  const intentRef = useRef<{ fingerprint: string; key: string } | null>(null)

  const fetchList = useCallback(async () => {
    const r = await listDefinitions()
    setList(toListState(r))
  }, [])

  const reload = useCallback(async () => {
    setList({ kind: 'loading' })
    await fetchList()
  }, [fetchList])

  useEffect(() => {
    let active = true
    listDefinitions().then((r) => {
      if (!active) return
      setList(toListState(r))
    })
    return () => {
      active = false
    }
  }, [])

  // Track the current preview so a late save response never relabels a newer preview.
  useEffect(() => {
    tokenRef.current = preview?.token ?? null
  }, [preview?.token])

  const items = list.kind === 'done' ? list.data.items : []
  const targetItem = items.find((i) => i.definition_id === target)

  async function runSave() {
    if (!preview) return
    const caseTrim = caseId.trim()
    const versionNumber = caseVersion.trim() === '' ? null : Number(caseVersion.trim())
    if (caseTrim && (!CASE_ID.test(caseTrim) || !Number.isInteger(versionNumber))) {
      setSave({
        kind: 'error',
        token: preview.token,
        message: 'Enter a funding case ID and its exact version number together.',
      })
      return
    }
    const body = {
      source: preview.source,
      expected_input_sha256: preview.result.input.sha256,
      definition_id: targetItem ? targetItem.definition_id : null,
      expected_version: targetItem ? (targetItem.current_version ?? null) : null,
      funding_case_id: caseTrim || null,
      funding_case_version: caseTrim ? versionNumber : null,
    }
    // One idempotency key per save intent: a retried click replays instead of duplicating.
    const fingerprint = JSON.stringify([preview.token, body])
    if (intentRef.current?.fingerprint !== fingerprint) {
      intentRef.current = { fingerprint, key: newIdempotencyKey() }
    }
    const startedFor = preview.token
    setSave({ kind: 'saving', token: startedFor })
    const r = await saveDefinition({ ...body, idempotency_key: intentRef.current.key })
    if (tokenRef.current !== startedFor) return // a late response never relabels a newer preview
    if (r.ok) {
      setSave({
        kind: 'saved',
        token: startedFor,
        pub: r.data.publication,
        replayed: r.data.replayed,
      })
      void reload()
    } else {
      setSave({ kind: 'error', token: startedFor, message: describeError(r) })
    }
  }

  async function open(fetcher: Promise<Awaited<ReturnType<typeof getDefinition>>>) {
    setOpened({ kind: 'loading' })
    setCopied(false)
    const r = await fetcher
    if (r.ok) {
      setOpened({ kind: 'done', data: r.data })
      setSelected(r.data.intake.questions?.[0]?.question_id ?? null)
    } else {
      setOpened({ kind: 'error', message: describeError(r) })
    }
  }

  async function copyId(id: string) {
    try {
      await navigator.clipboard.writeText(id)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  const pub = opened.kind === 'done' ? opened.data : null
  const question = pub?.intake.questions?.find((q) => q.question_id === selected)

  return (
    <section aria-labelledby="saved-heading" className="panel">
      <h3 id="saved-heading">Saved definitions for drafting</h3>
      <p className="hint">
        Saving keeps an exact, immutable version (questions, limits, conflicts and source evidence).
        It is <strong>not</strong> a review or an approval. Connection to Applications is pending
        until Dev C reads saved definitions.
      </p>
      {preview && (
        <div className="save-box">
          <p>
            Current preview: <code>{preview.result.input.sha256}</code> (
            {preview.result.questions?.length ?? 0} questions)
          </p>
          <label>
            Save as
            <select value={target} onChange={(e) => setTarget(e.target.value)}>
              <option value="">a new saved definition</option>
              {items
                .filter((i) => i.status === 'ok')
                .map((i) => (
                  <option key={i.definition_id} value={i.definition_id}>
                    revision of {i.definition_id} (current v{i.current_version}) - {i.title ?? ''}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Funding case ID (optional, exact version required)
            <input
              type="text"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              placeholder="case-..."
            />
          </label>
          <label>
            Funding case version
            <input
              type="text"
              inputMode="numeric"
              value={caseVersion}
              onChange={(e) => setCaseVersion(e.target.value)}
            />
          </label>
          <p>
            <button type="button" onClick={runSave} disabled={save.kind === 'saving'}>
              {save.kind === 'saving' ? 'Saving...' : 'Save definition for drafting'}
            </button>
          </p>
          {save.kind === 'error' && (
            <p role="alert" className="badge badge-unavailable">
              {save.message}
            </p>
          )}
          {save.kind === 'saved' && (
            <div role="status" className="saved-result">
              <p>
                <strong>
                  Saved{save.replayed ? ' (already saved; same version returned)' : ''}
                </strong>
                ; connection to Applications pending.
              </p>
              <ul className="meta">
                <li>
                  Definition <code>{save.pub.definition_id}</code> version {save.pub.version}
                </li>
                <li>
                  Question set <code>{save.pub.question_set_id}</code>
                </li>
                <li>
                  Saved {save.pub.saved_at} by {save.pub.saved_by} · input sha256{' '}
                  <code>{save.pub.integrity.raw_input_sha256}</code>
                </li>
                <li>
                  {save.pub.question_set.questions.length} questions ·{' '}
                  {save.pub.unresolved?.length ?? 0} unresolved items · approval:{' '}
                  {save.pub.approval_status}
                </li>
                <li>
                  Opportunity: {save.pub.context.opportunity_id} (
                  {save.pub.context.opportunity_basis.replaceAll('_', ' ')})
                </li>
              </ul>
            </div>
          )}
        </div>
      )}

      <h4>Saved definitions</h4>
      <p>
        <button type="button" onClick={() => void reload()}>
          Reload saved definitions
        </button>
      </p>
      {list.kind === 'loading' && <p role="status">Loading saved definitions...</p>}
      {list.kind === 'error' && (
        <p role="alert" className="badge badge-unavailable">
          {list.message}
        </p>
      )}
      {list.kind === 'done' && list.data.items.length === 0 && (
        <p role="status">No saved definitions yet.</p>
      )}
      {list.kind === 'done' && list.data.items.length > 0 && (
        <table className="saved-list">
          <thead>
            <tr>
              <th scope="col">Definition</th>
              <th scope="col">Version</th>
              <th scope="col">Questions / unresolved</th>
              <th scope="col">Label</th>
              <th scope="col">Open</th>
            </tr>
          </thead>
          <tbody>
            {list.data.items.map((i) => (
              <tr key={i.definition_id}>
                <td>
                  <code>{i.definition_id}</code>
                  {i.title && <div>{i.title}</div>}
                </td>
                <td>{i.status === 'ok' ? `v${i.current_version}` : 'integrity failure'}</td>
                <td>
                  {i.status === 'ok' ? `${i.question_count} / ${i.unresolved_count}` : i.detail}
                </td>
                <td>{i.mode_label}</td>
                <td>
                  <button
                    type="button"
                    disabled={i.status !== 'ok'}
                    onClick={() => void open(getDefinition(i.definition_id))}
                  >
                    Reopen {i.definition_id}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {list.kind === 'done' && (list.data.more || list.data.incomplete) && (
        <p className="hint">
          {list.data.more ? 'More saved definitions exist beyond this page. ' : ''}
          {list.data.incomplete
            ? 'The listing scan limit was reached; the list is incomplete.'
            : ''}
        </p>
      )}

      {opened.kind === 'loading' && <p role="status">Opening...</p>}
      {opened.kind === 'error' && (
        <p role="alert" className="badge badge-unavailable">
          {opened.message}
        </p>
      )}
      {pub && (
        <section aria-labelledby="reopened-heading" className="reopened">
          <h4 id="reopened-heading">
            Saved definition {pub.definition_id} v{pub.version}
          </h4>
          <p className="banner-mode">{pub.mode_label}</p>
          <ul className="meta">
            <li>
              Question set <code data-testid="saved-qs-id">{pub.question_set_id}</code>{' '}
              <button type="button" onClick={() => void copyId(pub.question_set_id)}>
                Copy question-set ID for Dev C
              </button>
              {copied && <span role="status"> Copied.</span>}
            </li>
            <li>
              Review: {(pub.review_status ?? 'saved_not_reviewed').replaceAll('_', ' ')} · approval:{' '}
              {pub.approval_status} · prefill permitted: no
            </li>
            <li>
              Input sha256 <code>{pub.integrity.raw_input_sha256}</code> (
              {pub.integrity.raw_input_size} bytes) · digest{' '}
              <code>{pub.integrity.normalized_digest}</code>
            </li>
            <li>
              Opportunity {pub.context.opportunity_id} (
              {pub.context.opportunity_basis.replaceAll('_', ' ')})
              {pub.context.binding &&
                ` · funding case ${pub.context.binding.funding_case_id} v${pub.context.binding.funding_case_version}`}
            </li>
            {pub.revision_of_version && (
              <li>
                Revision of v{pub.revision_of_version}. Added:{' '}
                {pub.added_original_ids?.join(', ') || 'none'} · Removed:{' '}
                {pub.removed_original_ids?.join(', ') || 'none'}
              </li>
            )}
            {pub.version > 1 && (
              <li>
                <button
                  type="button"
                  onClick={() =>
                    void open(getQuestionSet(`qs-${pub.definition_id}-v${pub.version - 1}`))
                  }
                >
                  Open previous version v{pub.version - 1}
                </button>
              </li>
            )}
          </ul>
          <h5>Unresolved items ({pub.unresolved?.length ?? 0})</h5>
          <ul className="unresolved">
            {(pub.unresolved ?? []).map((u, n) => (
              <li key={`${u.question_id}-${u.kind}-${n}`}>
                <code>{u.question_id}</code>: {u.kind.replaceAll('_', ' ')} - {u.detail}
              </li>
            ))}
          </ul>
          <QuestionTable
            questions={pub.intake.questions ?? []}
            selected={selected}
            onSelect={setSelected}
          />
          <EvidencePanel result={pub.intake} question={question} />
        </section>
      )}
    </section>
  )
}
