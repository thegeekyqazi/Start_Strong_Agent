// Saved captures library (owner: Dev B funding; DEV-B-BUNDLE-002 M2). Lists captures after a
// reload or navigation, opens one by ID, and hands an exact capture_id:artifact_id to intake.
// Metadata only in the list; content is shown only after the server re-verifies its hash.
import { useEffect, useState } from 'react'
import type { CaptureCatalogPage, CapturedDocument, CaptureSummary } from '@strongstart/contracts'
import { openInApplicationIntake } from '../automation/handoff'
import { describeError, type FundingClient } from './client'

type Phase<T> =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'done'; data: T }

const CAPTURE_ID = /^cap-[0-9a-f]{32}$/

/** Exact intake references for importable artifacts, labelled separately from full JSON. */
export function IntakeReferences({ doc }: { doc: CapturedDocument }) {
  const [copied, setCopied] = useState<string | null>(null)
  const [blocked, setBlocked] = useState(false)
  const importable = doc.artifacts.filter((a) =>
    doc.supported_import_representations.includes(a.representation),
  )
  const copy = async (ref: string) => {
    try {
      await navigator.clipboard.writeText(ref)
      setCopied(ref)
    } catch {
      setCopied(null)
    }
  }
  return (
    <section aria-labelledby={`intake-refs-${doc.capture_id}`}>
      <h4 id={`intake-refs-${doc.capture_id}`}>Use in application intake</h4>
      {importable.length === 0 ? (
        <p className="hint">
          No importable form representation was stored (markdown and prose are context only).
        </p>
      ) : (
        <ul className="checks">
          {importable.map((a) => {
            const ref = `${doc.capture_id}:${a.artifact_id}`
            return (
              <li key={a.artifact_id}>
                {a.representation} <code data-testid="intake-reference">{ref}</code>{' '}
                <button type="button" onClick={() => void copy(ref)}>
                  Copy intake reference ({a.representation})
                </button>{' '}
                <button type="button" onClick={() => setBlocked(!openInApplicationIntake(ref))}>
                  Use {a.representation} in application intake
                </button>
                {copied === ref && <span role="status"> Copied intake reference.</span>}
              </li>
            )
          })}
        </ul>
      )}
      {blocked && (
        <p role="alert">Could not hand the reference to Intake here; copy and paste it instead.</p>
      )}
      <p className="hint">
        Provider-rendered HTML is not the funder&apos;s original page bytes. Intake extracts only
        supported form controls; it never invents questions from prose.
      </p>
    </section>
  )
}

function SummaryRow({ s, onOpen }: { s: CaptureSummary; onOpen: (id: string) => void }) {
  if (s.status === 'corrupt') {
    return (
      <tr>
        <td>
          <code>{s.capture_id}</code>
        </td>
        <td colSpan={4}>
          <span className="badge badge-unavailable">Corrupt</span> {s.detail}
        </td>
        <td />
      </tr>
    )
  }
  return (
    <tr>
      <td>
        <code>{s.capture_id}</code>
        <div>{s.page_title ?? '(no title)'}</div>
        <div className="url">{s.final_url ?? s.requested_url}</div>
      </td>
      <td>{s.captured_at} (capture time only)</td>
      <td>
        {s.provider} {s.provider_mode === 'fixture' ? '(FIXTURE)' : ''}
        {s.is_simulated ? ' · simulated' : ''}
      </td>
      <td>
        {s.coverage} · {s.representation_count} representations
      </td>
      <td>{s.authority_review}</td>
      <td>
        <button type="button" onClick={() => onOpen(s.capture_id)}>
          Open {s.capture_id}
        </button>
      </td>
    </tr>
  )
}

export function SavedCaptures({
  client,
  renderCapture,
}: {
  client: FundingClient
  renderCapture: (doc: CapturedDocument) => React.ReactNode
}) {
  const [page, setPage] = useState<Phase<CaptureCatalogPage>>({ kind: 'loading' })
  const [extra, setExtra] = useState<CaptureSummary[]>([])
  const [opened, setOpened] = useState<Phase<CapturedDocument>>({ kind: 'idle' })
  const [openId, setOpenId] = useState('')

  useEffect(() => {
    let active = true
    client.listCaptures().then((r) => {
      if (!active) return
      setPage(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
    })
    return () => {
      active = false
    }
  }, [client])

  const reload = async () => {
    setPage({ kind: 'loading' })
    setExtra([])
    const r = await client.listCaptures()
    setPage(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
  }

  const loadMore = async (cursor: string) => {
    const r = await client.listCaptures(cursor)
    if (r.ok) {
      setExtra((prev) => [...prev, ...r.data.items])
      setPage({ kind: 'done', data: { ...r.data, items: [] } })
    } else {
      setPage({ kind: 'error', message: describeError(r) })
    }
  }

  const open = async (id: string) => {
    if (!CAPTURE_ID.test(id)) {
      setOpened({ kind: 'error', message: 'Enter a capture ID like cap-<32 hex characters>.' })
      return
    }
    setOpened({ kind: 'loading' })
    const r = await client.getCapture(id)
    setOpened(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
  }

  const data = page.kind === 'done' ? page.data : null
  const items = data ? [...extra, ...data.items] : extra

  return (
    <section aria-labelledby="saved-captures">
      <h3 id="saved-captures">Saved captures</h3>
      <p className="hint">
        Captures stay available after you navigate away or reload. The list shows stored metadata
        only; content is checked against its hash when opened.
      </p>
      <p>
        <button type="button" onClick={() => void reload()}>
          Reload saved captures
        </button>
      </p>
      {page.kind === 'loading' && <p role="status">Loading saved captures...</p>}
      {page.kind === 'error' && <p role="alert">{page.message}</p>}
      {data && items.length === 0 && <p role="status">No saved captures yet.</p>}
      {items.length > 0 && (
        <table>
          <thead>
            <tr>
              <th scope="col">Capture</th>
              <th scope="col">Captured</th>
              <th scope="col">Provider</th>
              <th scope="col">Coverage</th>
              <th scope="col">Source authority</th>
              <th scope="col">Open</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <SummaryRow key={s.capture_id} s={s} onOpen={(id) => void open(id)} />
            ))}
          </tbody>
        </table>
      )}
      {data?.more && data.next_cursor && (
        <button type="button" onClick={() => void loadMore(data.next_cursor as string)}>
          Load more captures
        </button>
      )}
      {data && data.backfill_status !== 'complete' && (
        <p className="hint" role="status">
          Older captures are still being indexed ({data.backfill_pending} pending
          {data.backfill_status === 'incomplete_scan' ? '; scan limit reached' : ''}). Reload to
          continue; nothing was deleted.
        </p>
      )}
      {data?.incomplete && (
        <p className="hint">The capture listing reached its scan limit; it is incomplete.</p>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          void open(openId.trim())
        }}
      >
        <label htmlFor="open-capture-id">Open a capture by ID</label>
        <input id="open-capture-id" value={openId} onChange={(e) => setOpenId(e.target.value)} />
        <button type="submit">Open capture</button>
      </form>
      {opened.kind === 'loading' && <p role="status">Opening capture...</p>}
      {opened.kind === 'error' && <p role="alert">{opened.message}</p>}
      {opened.kind === 'done' && renderCapture(opened.data)}
    </section>
  )
}
