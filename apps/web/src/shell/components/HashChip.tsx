// Content-version fingerprint (APP-04 display; lane plan s6.2). Owner: C (shared shell).
const SHA256 = /^[0-9a-f]{64}$/

export function HashChip({
  hash,
  label = 'Version fingerprint',
}: {
  hash: string | null
  label?: string
}) {
  if (hash === null) {
    return <span className="hash-chip">{label}: not computed</span>
  }
  if (!SHA256.test(hash)) {
    return <span className="hash-chip hash-invalid">{label}: invalid hash</span>
  }
  const short = hash.slice(0, 12)
  return (
    <span className="hash-chip" title={hash}>
      {label}: <code>{short}…</code>
      <span className="visually-hidden"> (full fingerprint {hash})</span>
    </span>
  )
}
