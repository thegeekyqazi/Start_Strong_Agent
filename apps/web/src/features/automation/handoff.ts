// Funding -> Automation handoff (owner: Dev B; DEV-B-BUNDLE-002 s6). Passes IDs only: the
// automation intake resolves and authorizes the capture server-side. sessionStorage is a
// per-viewer convenience; every read/write is guarded because storage can be unavailable.
export const INTAKE_REFERENCE_KEY = 'strongstart.intakeReference'
const REFERENCE = /^[a-z0-9][a-z0-9._:-]*:[a-z0-9][a-z0-9._:-]*$/

export function readIntakeReference(): string | null {
  try {
    const ref = window.sessionStorage.getItem(INTAKE_REFERENCE_KEY)
    return ref && REFERENCE.test(ref) ? ref : null
  } catch {
    return null
  }
}

export function clearIntakeReference(): void {
  try {
    window.sessionStorage.removeItem(INTAKE_REFERENCE_KEY)
  } catch {
    // storage unavailable: nothing to clear
  }
}

/** Store the exact capture_id:artifact_id and open the Automation page. */
export function openInApplicationIntake(reference: string): boolean {
  if (!REFERENCE.test(reference)) return false
  try {
    window.sessionStorage.setItem(INTAKE_REFERENCE_KEY, reference)
  } catch {
    return false
  }
  window.location.hash = '#/automation'
  return true
}
