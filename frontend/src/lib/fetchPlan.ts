/** Pure helpers for the Fetch now dialog (tested in fetchPlan.test.ts). */

export interface FetchSource {
  key: string
  label: string
  max_results: number
  runs_today: number
  running: boolean
}

export const DEFAULT_CAP = '5'
export const CAP_STORAGE_KEY = 'jobfinder.fetchCap'

/** "Fetch from 1 source" with a limit; with the box empty, say plainly that the source's own limit applies. */
export function fetchButtonLabel(chosen: FetchSource[], cap: string): string {
  const base = `Fetch from ${chosen.length} source${chosen.length === 1 ? '' : 's'}`
  if (cap.trim() !== '' || chosen.length === 0) return base
  const most = Math.max(...chosen.map((s) => s.max_results))
  return `${base}, no limit: up to ${most} jobs${chosen.length > 1 ? ' each' : ''}`
}

/** Sources already fetched today: a second fetch needs a confirmation. */
export function fetchedToday(chosen: FetchSource[]): FetchSource[] {
  return chosen.filter((s) => s.runs_today > 0)
}

export function confirmAgainText(again: FetchSource[]): string {
  const list = again.map((s) => `${s.label} (${s.runs_today} run${s.runs_today === 1 ? '' : 's'} today)`).join(', ')
  return `Already fetched today: ${list}.\n\nFetch again? This uses another of today's runs.`
}

/** Fetch is blocked while any chosen source is being fetched. */
export function anyRunning(chosen: FetchSource[]): boolean {
  return chosen.some((s) => s.running)
}
