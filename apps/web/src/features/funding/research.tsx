// Saved searches and source rechecks (owner: Dev B funding; DEV-B-BUNDLE-002 M5). Every run or
// recheck is one explicit staff action: no schedule, notification or background job exists.
import { useEffect, useState } from 'react'
import type {
  ChangeObservation,
  ChangeObservationList,
  CapturedDocument,
  RunComparison,
  SearchProfileCommand,
  SearchProfileList,
  SearchProfileVersion,
  SearchRunList,
} from '@strongstart/contracts'
import { describeError, type FundingClient } from './client'

type Phase<T> =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'done'; data: T }

let n = 0
const freshKey = (p: string) => {
  n += 1
  return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? `${p}-${crypto.randomUUID()}`
    : `${p}-${Date.now()}-${n}`
}

const OVERALL_LABEL: Record<string, string> = {
  unchanged: 'Unchanged (stored bytes match)',
  changed: 'Changed (stored bytes differ; re-review needed)',
  partial: 'Partial (cannot fully compare; re-review needed)',
  failed: 'Recheck failed (old capture unchanged)',
  not_comparable: 'Not comparable (different provider options)',
}

function Profile({ p, client }: { p: SearchProfileVersion; client: FundingClient }) {
  const [runs, setRuns] = useState<Phase<SearchRunList>>({ kind: 'idle' })
  const [running, setRunning] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [base, setBase] = useState('')
  const [target, setTarget] = useState('')
  const [cmp, setCmp] = useState<Phase<RunComparison>>({ kind: 'idle' })
  const load = async () => {
    const r = await client.listRuns(p.profile_id)
    setRuns(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
  }
  const runNow = async () => {
    setRunning(true)
    setMessage(null)
    const r = await client.runProfile(p.profile_id, {
      idempotency_key: freshKey('run'),
      profile_version: p.version,
    })
    setRunning(false)
    if (!r.ok) setMessage(describeError(r))
    else
      setMessage(
        r.data.outcome === 'success'
          ? `Run ${r.data.run_id}: ${r.data.normalized_urls?.length ?? 0} results.`
          : `Run ${r.data.run_id} ${r.data.outcome}: ${r.data.error_message ?? ''} (kept in history; no fixture results substituted)`,
      )
    void load()
  }
  const compare = async () => {
    setCmp({ kind: 'loading' })
    const r = await client.compareRuns(p.profile_id, base, target)
    setCmp(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
  }
  const items = runs.kind === 'done' ? runs.data.items : []
  return (
    <li>
      <strong>{p.label}</strong> (<code>{p.profile_id}</code> v{p.version}) - query sent:{' '}
      <code>{p.query_preview}</code> (public fields only: {p.public_fields_used.join(', ')})
      <div>
        <button type="button" onClick={() => void runNow()} disabled={running}>
          Run search now ({p.label})
        </button>{' '}
        <button type="button" onClick={() => void load()}>
          Show run history ({p.label})
        </button>
      </div>
      {message && <p role="status">{message}</p>}
      {runs.kind === 'error' && <p role="alert">{runs.message}</p>}
      {items.length > 0 && (
        <>
          <ul>
            {items.map((r) => (
              <li key={r.run_id}>
                <code>{r.run_id}</code> v{r.profile_version}, {r.outcome}
                {r.error_reason ? ` (${r.error_reason})` : ''}, {r.completed_at},{' '}
                {r.normalized_urls?.length ?? 0} results
              </li>
            ))}
          </ul>
          <label>
            Compare: earlier run
            <select aria-label="Earlier run" value={base} onChange={(e) => setBase(e.target.value)}>
              <option value="">Choose...</option>
              {items.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id} ({r.outcome})
                </option>
              ))}
            </select>
          </label>
          <label>
            Later run
            <select
              aria-label="Later run"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              <option value="">Choose...</option>
              {items.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id} ({r.outcome})
                </option>
              ))}
            </select>
          </label>
          <button type="button" disabled={!base || !target} onClick={() => void compare()}>
            Compare runs
          </button>
        </>
      )}
      {cmp.kind === 'error' && <p role="alert">{cmp.message}</p>}
      {cmp.kind === 'done' && (
        <div>
          <p className="hint">{cmp.data.note}</p>
          <p>Newly seen: {cmp.data.newly_seen.join(', ') || 'none'}</p>
          <p>Seen again: {cmp.data.seen_again.join(', ') || 'none'}</p>
          <p>
            Not seen in this result set (not removed or closed):{' '}
            {cmp.data.not_seen_in_this_result_set.join(', ') || 'none'}
          </p>
        </div>
      )}
    </li>
  )
}

export function SavedSearches({ client }: { client: FundingClient }) {
  const [list, setList] = useState<Phase<SearchProfileList>>({ kind: 'loading' })
  const [label, setLabel] = useState('')
  const [interests, setInterests] = useState('early learning')
  const [geography, setGeography] = useState('')
  const [save, setSave] = useState<Phase<null>>({ kind: 'idle' })

  useEffect(() => {
    let active = true
    client.listProfiles().then((r) => {
      if (!active) return
      setList(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
    })
    return () => {
      active = false
    }
  }, [client])

  const runSave = async () => {
    setSave({ kind: 'loading' })
    const body = {
      idempotency_key: freshKey('profile'),
      label: label.trim() || 'Saved search',
      profile: {
        interests: interests
          .split(',')
          .map((x) => x.trim())
          .filter(Boolean) as SearchProfileCommand['profile']['interests'],
        geography: geography.trim() || null,
      },
    }
    const r = await client.saveProfile(body)
    if (!r.ok) {
      setSave({ kind: 'error', message: describeError(r) })
      return
    }
    setSave({ kind: 'done', data: null })
    const l = await client.listProfiles()
    setList(l.ok ? { kind: 'done', data: l.data } : { kind: 'error', message: describeError(l) })
  }

  return (
    <section aria-labelledby="saved-searches">
      <h3 id="saved-searches">Saved searches</h3>
      <p className="hint">
        Saved searches keep public terms only. Each run happens only when you press Run (no schedule
        or alerts). Results are bounded and ranked by the provider.
      </p>
      <label htmlFor="profile-label">Label (stays here; never sent)</label>
      <input id="profile-label" value={label} onChange={(e) => setLabel(e.target.value)} />
      <label htmlFor="profile-interests">Public interests (comma separated)</label>
      <input
        id="profile-interests"
        value={interests}
        onChange={(e) => setInterests(e.target.value)}
      />
      <label htmlFor="profile-geography">Public geography (optional)</label>
      <input
        id="profile-geography"
        value={geography}
        onChange={(e) => setGeography(e.target.value)}
      />
      <button type="button" onClick={() => void runSave()} disabled={save.kind === 'loading'}>
        Save search
      </button>
      {save.kind === 'error' && <p role="alert">{save.message}</p>}
      {list.kind === 'error' && <p role="alert">{list.message}</p>}
      {list.kind === 'done' && list.data.items.length === 0 && (
        <p role="status">No saved searches yet.</p>
      )}
      {list.kind === 'done' && (
        <ul>
          {list.data.items.map((p) => (
            <Profile key={p.profile_id} p={p} client={client} />
          ))}
        </ul>
      )}
    </section>
  )
}

export function ObservationView({ o }: { o: ChangeObservation }) {
  return (
    <div className="observation">
      <p>
        <strong>{OVERALL_LABEL[o.overall] ?? o.overall}</strong>, {o.observed_at}, new capture{' '}
        {o.new_capture_id ?? 'none'}
        {o.failure_reason ? `, ${o.failure_reason}` : ''}
      </p>
      <p>{o.explanation}</p>
      {o.comparisons && o.comparisons.length > 0 && (
        <ul>
          {o.comparisons.map((c) => (
            <li key={c.representation}>
              {c.representation}: {c.outcome.replaceAll('_', ' ')}
            </li>
          ))}
        </ul>
      )}
      {o.text_diff && (
        <details>
          <summary>Text differences (assistive, not authoritative)</summary>
          <pre className="evidence">{o.text_diff}</pre>
          {o.text_diff_truncated && <p className="hint">Diff truncated.</p>}
        </details>
      )}
      <ul className="warnings">
        {(o.downstream_effects ?? []).map((e) => (
          <li key={e}>{e}</li>
        ))}
      </ul>
    </div>
  )
}

/** "Capture again and compare" for one explicitly selected saved capture. */
export function Recheck({ doc, client }: { doc: CapturedDocument; client: FundingClient }) {
  const [caseId, setCaseId] = useState('')
  const [caseVersion, setCaseVersion] = useState('')
  const [result, setResult] = useState<Phase<ChangeObservation>>({ kind: 'idle' })
  const [history, setHistory] = useState<Phase<ChangeObservationList>>({ kind: 'idle' })
  const run = async () => {
    setResult({ kind: 'loading' })
    const linked = caseId.trim()
    const r = await client.recheck(doc.capture_id, {
      idempotency_key: freshKey('recheck'),
      funding_case_id: linked || null,
      funding_case_version: linked ? Number(caseVersion) : null,
    })
    setResult(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
  }
  const load = async () => {
    const r = await client.listObservations(doc.capture_id)
    setHistory(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
  }
  return (
    <section aria-labelledby={`recheck-${doc.capture_id}`}>
      <h4 id={`recheck-${doc.capture_id}`}>Capture again and compare</h4>
      <p className="hint">
        Makes one new capture of {doc.requested_url} with the same destination rules. The old
        capture is never overwritten.
      </p>
      <label>
        Linked funding case ID (optional)
        <input
          aria-label="Linked funding case ID"
          value={caseId}
          onChange={(e) => setCaseId(e.target.value)}
        />
      </label>
      <label>
        Case version
        <input
          aria-label="Linked case version"
          value={caseVersion}
          onChange={(e) => setCaseVersion(e.target.value)}
        />
      </label>
      <button type="button" onClick={() => void run()} disabled={result.kind === 'loading'}>
        Capture again and compare
      </button>{' '}
      <button type="button" onClick={() => void load()}>
        Show change observations
      </button>
      {result.kind === 'loading' && <p role="status">Rechecking...</p>}
      {result.kind === 'error' && <p role="alert">{result.message}</p>}
      {result.kind === 'done' && <ObservationView o={result.data} />}
      {history.kind === 'error' && <p role="alert">{history.message}</p>}
      {history.kind === 'done' && (
        <ul>
          {history.data.items.map((o) => (
            <li key={o.observation_id}>
              <ObservationView o={o} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
