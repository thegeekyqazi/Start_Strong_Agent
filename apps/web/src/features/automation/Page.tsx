// Intake & Prefill page (owner: B2, B2-AUTO-001). Import, inspect evidence, inspect the fixture
// portal read-only and export the handoff. Every imported string is rendered as escaped React
// text; nothing here uses innerHTML, runs imported scripts, fills fields or submits anything.
import { useEffect, useState } from 'react'
import type {
  ApplicationIntakeResult,
  AutomationAvailability,
  FormInspectionResult,
  IntakeQuestion,
} from '@strongstart/contracts'
import {
  describeError,
  exportDefinition,
  getAvailability,
  importDefinition,
  inspectFixture,
  portalUrl,
  type IntakeSource,
} from './api'
import { EvidencePanel, FindingList, InspectionView, QuestionTable } from './views'
import { SavedDefinitions, type Preview } from './saved'
import { clearIntakeReference, readIntakeReference } from './handoff'
import './automation.css'

type Mode = IntakeSource['mode']
type Load<T> =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'done'; data: T }

const MODE_LABEL: Record<Mode, string> = {
  fixture: 'Known fixture',
  structured_json: 'Structured JSON definition',
  html: 'Saved HTML form',
  capture: 'Captured document (capture port)',
}

const CAP_LABEL: Record<string, string> = {
  available: 'Available',
  fixture_only: 'Fixture only',
  not_implemented: 'Not implemented',
  unavailable: 'Unavailable',
}

export function AutomationPage() {
  const [avail, setAvail] = useState<Load<AutomationAvailability>>({ kind: 'loading' })
  const [handoffRef] = useState(readIntakeReference)
  const [mode, setMode] = useState<Mode>(handoffRef ? 'capture' : 'fixture')
  const [fixtureId, setFixtureId] = useState('rep-portal-definition-v1')
  const [captureKey, setCaptureKey] = useState(handoffRef ?? '')
  const [text, setText] = useState('')
  const [intake, setIntake] = useState<Load<ApplicationIntakeResult>>({ kind: 'idle' })
  const [lastSource, setLastSource] = useState<IntakeSource | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [portalId, setPortalId] = useState('rep-portal-v1')
  const [inspection, setInspection] = useState<Load<FormInspectionResult>>({ kind: 'idle' })
  const [exportState, setExportState] = useState<Load<string>>({ kind: 'idle' })
  const [previewToken, setPreviewToken] = useState(0)

  // "Use in application intake" from Find Funding passes IDs only (resolved server-side).
  useEffect(() => clearIntakeReference(), [])

  useEffect(() => {
    let active = true
    getAvailability().then((r) => {
      if (!active) return
      setAvail(r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) })
    })
    return () => {
      active = false
    }
  }, [])

  const a = avail.kind === 'done' ? avail.data : null
  const fixtures = a?.fixtures ?? []
  const intakeFixtures = fixtures.filter(
    (f) => f.kind === 'structured_definition' || f.kind === 'html_form',
  )
  const portals = fixtures.filter((f) => f.kind === 'portal')
  const captures = fixtures.filter((f) => f.kind === 'capture')
  const maxBytes = a?.import_modes.find((m) => m.mode === mode)?.max_bytes ?? 0

  function buildSource(): IntakeSource | string {
    if (mode === 'fixture') return { mode: 'fixture', fixture_id: fixtureId }
    if (mode === 'capture') {
      const [capture_id, artifact_id] = captureKey.split(':')
      if (!capture_id || !artifact_id) return 'Choose a captured document first.'
      return { mode: 'capture', capture_id, artifact_id }
    }
    if (!text.trim()) return 'Paste or upload content first (the input is empty).'
    if (maxBytes && new TextEncoder().encode(text).length > maxBytes) {
      return `The input is larger than the ${maxBytes}-byte limit. [input_too_large]`
    }
    return { mode, content: text }
  }

  async function runImport() {
    const source = buildSource()
    if (typeof source === 'string') {
      setIntake({ kind: 'error', message: source })
      return
    }
    setIntake({ kind: 'loading' })
    setSelected(null)
    setExportState({ kind: 'idle' })
    const r = await importDefinition(source)
    if (r.ok) {
      setLastSource(source)
      setPreviewToken((n) => n + 1)
      setIntake({ kind: 'done', data: r.data })
      setSelected(r.data.questions?.[0]?.question_id ?? null)
    } else {
      setIntake({ kind: 'error', message: describeError(r) })
    }
  }

  async function runInspect() {
    setInspection({ kind: 'loading' })
    const r = await inspectFixture({ fixture_id: portalId })
    setInspection(
      r.ok ? { kind: 'done', data: r.data } : { kind: 'error', message: describeError(r) },
    )
  }

  async function runExport() {
    if (!lastSource) return
    setExportState({ kind: 'loading' })
    const withInspection = inspection.kind === 'done' ? inspection.data.fixture_id : null
    const r = await exportDefinition({ source: lastSource, inspect_fixture_id: withInspection })
    if (!r.ok) {
      setExportState({ kind: 'error', message: describeError(r) })
      return
    }
    const json = JSON.stringify(r.data, null, 2)
    if (typeof URL.createObjectURL === 'function') {
      const url = URL.createObjectURL(new Blob([json], { type: 'application/json' }))
      const link = document.createElement('a')
      link.href = url
      link.download = `${r.data.export_id}.json`
      link.click()
      URL.revokeObjectURL(url)
    }
    setExportState({ kind: 'done', data: `${r.data.export_id} - ${r.data.label}` })
  }

  async function onFile(file: File | undefined) {
    if (!file) return
    if (maxBytes && file.size > maxBytes) {
      setIntake({
        kind: 'error',
        message: `The file is larger than the ${maxBytes}-byte limit. [input_too_large]`,
      })
      return
    }
    setText(await file.text())
  }

  const result = intake.kind === 'done' ? intake.data : null
  const current = buildSource()
  const sourceChanged =
    result !== null && lastSource !== null && JSON.stringify(current) !== JSON.stringify(lastSource)
  const preview: Preview | null =
    result && lastSource && !sourceChanged
      ? { token: previewToken, result, source: lastSource }
      : null
  const question: IntakeQuestion | undefined = result?.questions?.find(
    (q) => q.question_id === selected,
  )

  return (
    <section aria-labelledby="automation-heading" className="automation">
      <h2 id="automation-heading">Intake &amp; Prefill</h2>
      <p className="badge badge-planned">
        Intake and read-only fixture inspection only. Prefill is not implemented; submission is
        staff-only.
      </p>

      <section aria-labelledby="avail-heading" className="panel">
        <h3 id="avail-heading">Availability</h3>
        {avail.kind === 'loading' && <p role="status">Checking availability...</p>}
        {avail.kind === 'error' && (
          <p role="alert" className="badge badge-unavailable">
            {avail.message}
          </p>
        )}
        {a && (
          <>
            <ul className="cap-list">
              {a.capabilities.map((c) => (
                <li key={c.feature}>
                  <span className={`badge cap-${c.status}`}>{CAP_LABEL[c.status]}</span>{' '}
                  <code>{c.feature}</code> - {c.detail}
                </li>
              ))}
            </ul>
            <p>
              Browser: <strong>{a.browser_status.replaceAll('_', ' ')}</strong> - {a.browser_detail}
            </p>
            {a.fixture_mode && (
              <p className="banner-fixture">
                FIXTURE MODE - all fixtures are engineering-derived; not funder sources.
              </p>
            )}
          </>
        )}
      </section>

      <section aria-labelledby="import-heading" className="panel">
        <h3 id="import-heading">1. Import an application definition</h3>
        <fieldset>
          <legend>Import mode</legend>
          {(Object.keys(MODE_LABEL) as Mode[]).map((m) => {
            const info = a?.import_modes.find((x) => x.mode === m)
            return (
              <label key={m} className="inline">
                <input
                  type="radio"
                  name="mode"
                  value={m}
                  checked={mode === m}
                  disabled={info?.status === 'unavailable'}
                  onChange={() => setMode(m)}
                />
                {MODE_LABEL[m]} {info && <small>({CAP_LABEL[info.status]})</small>}
              </label>
            )
          })}
        </fieldset>
        {mode === 'fixture' && (
          <label>
            Fixture
            <select value={fixtureId} onChange={(e) => setFixtureId(e.target.value)}>
              {intakeFixtures.map((f) => (
                <option key={f.fixture_id} value={f.fixture_id}>
                  {f.fixture_id} - {f.description}
                </option>
              ))}
            </select>
          </label>
        )}
        {mode === 'capture' && (
          <label>
            Captured document
            <select value={captureKey} onChange={(e) => setCaptureKey(e.target.value)}>
              <option value="">Choose...</option>
              {captures.map((f) => (
                <option key={f.fixture_id} value={f.fixture_id}>
                  {f.fixture_id} - {f.description}
                </option>
              ))}
            </select>
          </label>
        )}
        {mode === 'capture' && (
          <label>
            Or paste a capture reference from Find Funding (capture_id:artifact_id)
            <input
              type="text"
              value={captureKey}
              onChange={(e) => setCaptureKey(e.target.value.trim())}
              placeholder="cap-...:cap-...-html"
            />
          </label>
        )}
        {(mode === 'structured_json' || mode === 'html') && (
          <>
            <label>
              {mode === 'html' ? 'Saved HTML (parsed statically, never run)' : 'Definition JSON'}
              <textarea
                className="input-text"
                rows={8}
                value={text}
                onChange={(e) => setText(e.target.value)}
                spellCheck={false}
              />
            </label>
            <label>
              Or upload a file
              <input
                type="file"
                accept={mode === 'html' ? '.html,.htm,text/html' : '.json,application/json'}
                onChange={(e) => onFile(e.target.files?.[0])}
              />
            </label>
            {maxBytes > 0 && (
              <small>Limit: {maxBytes} bytes. Uploaded input is labelled unverified.</small>
            )}
          </>
        )}
        <p>
          <button type="button" onClick={runImport} disabled={intake.kind === 'loading'}>
            {intake.kind === 'loading' ? 'Importing...' : 'Import'}
          </button>
        </p>
        {intake.kind === 'error' && (
          <p role="alert" className="badge badge-unavailable">
            {intake.message}
          </p>
        )}
      </section>

      {result && (
        <section aria-labelledby="result-heading" className="panel">
          <h3 id="result-heading">2. Imported questions</h3>
          <p className="banner-mode">{result.mode_label}</p>
          <ul className="meta">
            <li>
              Approval: <strong>{result.approval_status}</strong> · Authority:{' '}
              {result.authority_status} · Saved:{' '}
              {result.persisted ? 'yes' : 'no - this result exists only in this response'}
            </li>
            <li>
              Coverage: <strong>{result.coverage.status.replaceAll('_', ' ')}</strong> (
              {result.coverage.questions_extracted} questions)
            </li>
            <li>
              Input: {result.input.representation_type} · {result.input.byte_size} bytes · sha256{' '}
              <code>{result.input.sha256}</code> · parser {result.input.parser_id}/
              {result.input.parser_version}
            </li>
            {result.input.capture && (
              <li>
                Capture: {result.input.capture.capture_id} /{' '}
                {result.input.capture.source_version_id} / {result.input.capture.artifact_id} (
                {result.input.capture.producer}
                {result.input.capture.capture_is_fixture ? ', fixture/simulated' : ''})
              </li>
            )}
          </ul>
          {(result.questions?.length ?? 0) === 0 ? (
            <p role="status">
              No questions were extracted. The input is preserved as evidence and needs a manual
              definition.
            </p>
          ) : (
            <QuestionTable
              questions={result.questions ?? []}
              selected={selected}
              onSelect={setSelected}
            />
          )}
          <FindingList
            findings={(result.findings ?? []).filter((f) => !f.question_id)}
            title="Document findings"
          />
          <EvidencePanel result={result} question={question} />
          <p>
            <button type="button" onClick={runExport} disabled={exportState.kind === 'loading'}>
              Export JSON handoff (not approved)
            </button>{' '}
            {exportState.kind === 'done' && <span role="status">Exported {exportState.data}</span>}
            {exportState.kind === 'error' && (
              <span role="alert" className="badge badge-unavailable">
                {exportState.message}
              </span>
            )}
          </p>
        </section>
      )}

      {sourceChanged && (
        <p role="status" className="badge badge-unavailable">
          The source changed since this preview. Re-import before saving.
        </p>
      )}
      <SavedDefinitions preview={preview} />

      <section aria-labelledby="inspect-heading" className="panel">
        <h3 id="inspect-heading">3. Representative portal inspection (read-only)</h3>
        <p>
          The portal is this team&apos;s fixture, not a funder site. Inspection reads fields only:
          no values are entered and nothing is submitted.
        </p>
        <label>
          Portal fixture
          <select value={portalId} onChange={(e) => setPortalId(e.target.value)}>
            {portals.map((p) => (
              <option key={p.fixture_id} value={p.fixture_id}>
                {p.fixture_id} ({p.variant}) - {p.description}
              </option>
            ))}
          </select>
        </label>{' '}
        <a href={portalUrl(portalId)} target="_blank" rel="noreferrer noopener">
          Open portal (sandboxed)
        </a>
        <p>
          <button
            type="button"
            onClick={runInspect}
            disabled={
              inspection.kind === 'loading' || a?.browser_status !== 'installed_not_launched'
            }
          >
            {inspection.kind === 'loading' ? 'Inspecting...' : 'Inspect fields'}
          </button>
        </p>
        {inspection.kind === 'error' && (
          <p role="alert" className="badge badge-unavailable">
            {inspection.message}
          </p>
        )}
        {inspection.kind === 'done' && <InspectionView result={inspection.data} />}
      </section>
    </section>
  )
}
