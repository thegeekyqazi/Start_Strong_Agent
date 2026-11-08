// Question-set picker (owner: C; C2b). Lists Dev B's saved definitions; the demo fixture
// is an explicit choice, never an automatic fallback.
import { useEffect, useState } from 'react'
import type { DefinitionSummary } from '@strongstart/contracts'
import { httpQuestionSetClient, type QuestionSetClient } from './questionSets'

export function QuestionSetPicker({
  value,
  onChange,
  client = httpQuestionSetClient,
}: {
  value: string | null
  onChange: (id: string | null) => void
  client?: QuestionSetClient
}) {
  const [items, setItems] = useState<DefinitionSummary[]>([])
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    client.list().then((r) => {
      if (!active) return
      if (r.ok) setItems(r.data.items.filter((d) => d.status === 'ok' && d.question_set_id))
      else setNote('Saved question sets could not be listed; only the demo questions are offered.')
    })
    return () => {
      active = false
    }
  }, [client])

  const known = value === null || items.some((d) => d.question_set_id === value)
  return (
    <div className="question-set-picker">
      <label htmlFor="question-set">Questions from</label>{' '}
      <select
        id="question-set"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value === '' ? null : e.target.value)}
      >
        <option value="">Demo fixture questions (synthetic)</option>
        {items.map((d) => (
          <option key={d.definition_id} value={d.question_set_id ?? ''}>
            {d.title ?? d.definition_id} (saved definition v{d.current_version}
            {d.is_fixture ? ', fixture material' : ''})
          </option>
        ))}
        {!known && value && <option value={value}>Selected set {value}</option>}
      </select>
      {note && <p className="hint">{note}</p>}
    </div>
  )
}
