import { parseList } from './score'

export const mapToText = (m: Record<string, string[]>) =>
  Object.entries(m).map(([s, t]) => `${s}: ${t.join(', ')}`).join('\n')

/** "State: town, town" per line -> map. Lines without a state before a colon are ignored. */
export function textToMap(text: string): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const line of text.split('\n')) {
    const i = line.indexOf(':')
    if (i < 1) continue
    const state = line.slice(0, i).trim()
    if (state) out[state] = parseList(line.slice(i + 1))
  }
  return out
}

export type LocationOption =
  | { kind: 'remote'; value: 'Remote'; state: '' }
  | { kind: 'state'; value: string; state: string; count: number }
  | { kind: 'town'; value: string; state: string }

/**
 * Flat, grouped option list for the location picker. A state that matches the query shows all
 * its towns; otherwise only matching towns are shown under their state.
 */
export function buildOptions(map: Record<string, string[]>, query: string): LocationOption[] {
  const q = query.trim().toLowerCase()
  const out: LocationOption[] = []
  if (!q || 'remote'.includes(q) || 'work from home'.includes(q)) out.push({ kind: 'remote', value: 'Remote', state: '' })
  for (const [state, towns] of Object.entries(map)) {
    const stateHit = !q || state.toLowerCase().includes(q)
    const shown = stateHit ? towns : towns.filter((t) => t.toLowerCase().includes(q))
    if (!stateHit && shown.length === 0) continue
    out.push({ kind: 'state', value: state, state, count: towns.length })
    for (const t of shown) out.push({ kind: 'town', value: t, state })
  }
  return out
}
