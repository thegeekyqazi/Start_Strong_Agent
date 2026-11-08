// PLACEHOLDER counter (C1). Not APP-01: the versioned counting convention arrives in C2.
// Words = whitespace-separated tokens; characters = Unicode code points.
export function countWords(text: string): number {
  return text.trim() === '' ? 0 : text.trim().split(/\s+/).length
}

export function countCharacters(text: string): number {
  return [...text].length
}
