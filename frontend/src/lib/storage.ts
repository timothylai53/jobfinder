/**
 * localStorage that never throws: it can be blocked (some private windows, strict privacy settings, a full disk).
 * Everything stored here is a per-browser convenience, so a failure just means the default is used.
 */
export function readLocal(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeLocal(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* storage blocked: keep going without remembering */
  }
}
