import { wordDiff } from './diff'

describe('wordDiff', () => {
  it('marks a one-word edit', () => {
    expect(wordDiff('We help many families.', 'We help some families.')).toEqual([
      { kind: 'same', text: 'We help ' },
      { kind: 'removed', text: 'many' },
      { kind: 'added', text: 'some' },
      { kind: 'same', text: ' families.' },
    ])
  })
  it('handles identical, empty and appended text', () => {
    expect(wordDiff('same', 'same')).toEqual([{ kind: 'same', text: 'same' }])
    expect(wordDiff('', 'new')).toEqual([{ kind: 'added', text: 'new' }])
    expect(wordDiff('a', 'a b')).toEqual([
      { kind: 'same', text: 'a' },
      { kind: 'added', text: ' b' },
    ])
  })
})
