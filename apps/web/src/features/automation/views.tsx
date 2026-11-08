// Presentational views for the automation page. Imported content is always rendered as text.
import type {
  ApplicationIntakeResult,
  Finding,
  FormInspectionResult,
  IntakeLimit,
  IntakeQuestion,
} from '@strongstart/contracts'

function limitText(l: IntakeLimit): string {
  const range =
    l.minimum && l.maximum ? `${l.minimum}-${l.maximum}` : (l.maximum ?? `>= ${l.minimum}`)
  const unit = l.unit === 'utf16_code_units' ? 'UTF-16 code units (native maxlength)' : l.unit
  const stream = l.applies_to_stream ? ` [stream: ${l.applies_to_stream}]` : ''
  return `${range} ${unit}${stream}`
}

const KIND_LABEL: Record<IntakeLimit['kind'], string> = {
  instruction_text: 'instruction text',
  structured_definition: 'structured definition',
  native_dom_maxlength: 'browser property',
  native_dom_range: 'browser property',
}

export function QuestionTable({
  questions,
  selected,
  onSelect,
}: {
  questions: IntakeQuestion[]
  selected: string | null
  onSelect: (id: string) => void
}) {
  return (
    <table className="questions">
      <caption>Questions in original order (wording shown exactly as imported)</caption>
      <thead>
        <tr>
          <th scope="col">#</th>
          <th scope="col">Question</th>
          <th scope="col">Type</th>
          <th scope="col">Required</th>
          <th scope="col">Limits</th>
          <th scope="col">Status</th>
        </tr>
      </thead>
      <tbody>
        {questions.map((q) => (
          <tr
            key={q.question_id}
            aria-selected={q.question_id === selected}
            className={q.question_id === selected ? 'selected' : undefined}
          >
            <td>{q.original_number ?? '-'}</td>
            <td>
              <button type="button" className="link" onClick={() => onSelect(q.question_id)}>
                {q.text.display_text || '(no label in source)'}
              </button>
              {q.section && <div className="sub">{q.section.display_text}</div>}
              <div className="sub">
                <code>{q.question_id}</code>
              </div>
            </td>
            <td>
              {q.answer_kind}
              {q.choice_mode ? ` (${q.choice_mode})` : ''}
            </td>
            <td>
              {q.required_status}
              {(q.conditions ?? []).map((c, i) => (
                <div key={i} className="sub">
                  if {c.predicate_text ?? `${c.depends_on_question_id} = ${c.expected_value}`} (
                  {c.basis.replaceAll('_', ' ')}; {c.status.replaceAll('_', ' ')})
                </div>
              ))}
            </td>
            <td>
              <ul className="plain">
                {(q.limits ?? []).map((l) => (
                  <li key={l.limit_id}>
                    {limitText(l)}{' '}
                    <small>
                      ({KIND_LABEL[l.kind]}; convention {l.counting_convention})
                    </small>
                  </li>
                ))}
                {q.attachment && (
                  <li>
                    file types {q.attachment.accepted_types?.join(', ') ?? 'unknown'}; max size{' '}
                    {q.attachment.max_size_bytes ?? 'unknown'} bytes; max count{' '}
                    {q.attachment.max_count ?? 'unknown'}{' '}
                    <small>({q.attachment.basis.replaceAll('_', ' ')})</small>
                  </li>
                )}
              </ul>
              {(q.limit_conflicts ?? []).map((c) => (
                <p key={c.conflict_id} className="conflict" role="note">
                  Conflict ({c.resolution}): {c.description}
                </p>
              ))}
            </td>
            <td>
              {q.action_state === 'held_unresolved_requirement' ? (
                <span className="badge badge-unavailable">Held</span>
              ) : (
                <span className="badge badge-planned">No blocker found - not approved</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function FindingList({ findings, title }: { findings: Finding[]; title: string }) {
  if (findings.length === 0) return null
  return (
    <div className="findings">
      <h4>{title}</h4>
      <ul>
        {findings.map((f, i) => (
          <li key={i} className={`sev-${f.severity}`}>
            <strong>{f.severity}</strong> <code>{f.code}</code>: {f.message}
            {f.locator && (
              <span className="sub">
                {' '}
                at {f.locator.value}
                {f.locator.line ? ` (line ${f.locator.line})` : ''}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function EvidencePanel({
  result,
  question,
}: {
  result: ApplicationIntakeResult
  question: IntakeQuestion | undefined
}) {
  return (
    <aside aria-labelledby="evidence-heading" className="evidence">
      <h4 id="evidence-heading">Evidence</h4>
      {result.evidence_excerpt && (
        <>
          <p>
            Read-only text of the input{result.evidence_excerpt_truncated ? ' (truncated)' : ''}:
          </p>
          <pre className="raw">{result.evidence_excerpt.text}</pre>
        </>
      )}
      {!question && !result.evidence_excerpt && (
        <p>Select a question to see its exact imported text and source.</p>
      )}
      {question && (
        <dl>
          <dt>Exact wording</dt>
          <dd>
            <pre className="raw">{question.text.text}</pre>
          </dd>
          <dt>Locator</dt>
          <dd>
            {question.text.locator.kind}: <code>{question.text.locator.value}</code>
            {question.text.locator.line
              ? ` (line ${question.text.locator.line}, column ${question.text.locator.column})`
              : ''}
          </dd>
          {(question.instructions ?? []).length > 0 && (
            <>
              <dt>Instructions (exact)</dt>
              {(question.instructions ?? []).map((t, i) => (
                <dd key={i}>
                  <pre className="raw">{t.text}</pre>{' '}
                  <small>
                    <code>{t.locator.value}</code>
                  </small>
                </dd>
              ))}
            </>
          )}
          {(question.limits ?? []).length > 0 && (
            <>
              <dt>Limit evidence</dt>
              {(question.limits ?? []).map((l) => (
                <dd key={l.limit_id}>
                  {limitText(l)}: <q>{l.evidence.text}</q>{' '}
                  <small>({l.authority_status.replaceAll('_', ' ')})</small>
                </dd>
              ))}
            </>
          )}
          <dt>Source</dt>
          <dd>
            {question.source_ref.source_id} / {question.source_ref.source_version_id} ·{' '}
            {question.source_ref.verification_status} ·{' '}
            {question.source_ref.provenance.provenance_class}
            {question.source_ref.provenance.is_simulated ? ' (simulated)' : ''}
          </dd>
          <dd>
            hash <code>{question.source_ref.content_hash}</code> · locator{' '}
            <code>{question.source_ref.locator}</code>
          </dd>
          {question.hold_reasons && question.hold_reasons.length > 0 && (
            <>
              <dt>Held because</dt>
              <dd>{question.hold_reasons.join(', ')}</dd>
            </>
          )}
          {question.unrecognized_fields && Object.keys(question.unrecognized_fields).length > 0 && (
            <>
              <dt>Preserved unrecognised fields (not interpreted)</dt>
              <dd>
                <pre className="raw">{JSON.stringify(question.unrecognized_fields, null, 2)}</pre>
              </dd>
            </>
          )}
        </dl>
      )}
      {question && (
        <FindingList
          findings={(result.findings ?? []).filter((f) => f.question_id === question.question_id)}
          title="Findings for this question"
        />
      )}
    </aside>
  )
}

export function InspectionView({ result }: { result: FormInspectionResult }) {
  const act = result.activity
  return (
    <div className="inspection">
      <p className="banner-mode">{result.mode_label}</p>
      <ul className="meta">
        <li>
          Map:{' '}
          <strong className={result.map_status === 'valid' ? 'ok' : 'bad'}>
            {result.map_status}
          </strong>{' '}
          · Fingerprint <strong>{result.fingerprint_status.replaceAll('_', ' ')}</strong> (v
          {result.expected_form_version}) <code>{result.fingerprint}</code>
        </li>
        <li>
          Prefill permitted: <strong>no</strong> · A valid map is not permission to fill.
        </li>
        <li>
          Browser {result.browser_name} {result.browser_version}; requests allowed{' '}
          {act.requests_allowed}, blocked {act.requests_blocked}, write attempts blocked{' '}
          {act.mutation_requests_blocked}, writes reaching the fixture server{' '}
          {act.fixture_server_mutation_hits}, inspector actions{' '}
          {(act.inspector_actions ?? []).length}
        </li>
      </ul>
      <table className="questions">
        <caption>Expected fields and what the browser observed</caption>
        <thead>
          <tr>
            <th scope="col">Question</th>
            <th scope="col">Expected</th>
            <th scope="col">Result</th>
            <th scope="col">Observed</th>
          </tr>
        </thead>
        <tbody>
          {result.mappings.map((m) => (
            <tr key={m.question_id}>
              <td>
                <code>{m.question_id}</code>
                {m.requirement_hold && <span className="badge badge-unavailable"> held</span>}
              </td>
              <td>
                <code>{m.expected_selector}</code> ({m.expected_type}, {m.expected_kind})
              </td>
              <td>
                <span className={m.status === 'matched' ? 'ok' : 'bad'}>{m.status}</span>
              </td>
              <td>
                {m.observed_count} - {m.message}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <FindingList findings={result.findings ?? []} title="Inspection findings" />
      <details>
        <summary>Observed controls ({result.fields.length})</summary>
        <ul className="plain">
          {result.fields.map((f) => (
            <li key={f.observed_index}>
              <code>{f.field_key}</code> {f.tag}
              {f.input_type ? `[${f.input_type}]` : ''}{' '}
              {f.label_text ? `"${f.label_text}"` : '(no label)'}
              {f.required ? ' required' : ''}
              {f.disabled ? ' disabled' : ''}
              {f.visible ? '' : ' hidden'}
              {f.max_length != null ? ` maxlength=${f.max_length}` : ''}
              {f.supported ? '' : ' UNSUPPORTED'}
            </li>
          ))}
        </ul>
      </details>
    </div>
  )
}
