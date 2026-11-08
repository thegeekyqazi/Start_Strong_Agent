// Code-point quote location (matches the server's Python str indexing).
/** Locate an exact quote in verified stored text; reports how many occurrences exist. */
export function locateQuote(text: string, quote: string): { start: number; count: number } | null {
  if (!quote) return null
  const points = Array.from(text)
  const q = Array.from(quote)
  let first = -1
  let count = 0
  for (let i = 0; i + q.length <= points.length; i++) {
    let ok = true
    for (let j = 0; j < q.length; j++) {
      if (points[i + j] !== q[j]) {
        ok = false
        break
      }
    }
    if (ok) {
      count += 1
      if (first < 0) first = i
    }
  }
  return first < 0 ? null : { start: first, count }
}
