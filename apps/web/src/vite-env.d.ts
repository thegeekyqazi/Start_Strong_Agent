/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Public API base URL (non-secret). Empty/undefined = same origin via dev proxy. */
  readonly VITE_API_BASE_URL?: string
}
