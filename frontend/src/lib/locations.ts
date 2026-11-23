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

// ---------- the Location map editor (Settings) ----------

export type LocationMap = Record<string, string[]>

const same = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase()

/** Add a town to a state. Rejects an empty name or one the state already has (any case). The same town in another
 * state is allowed (Cheras is in both Kuala Lumpur and Selangor). */
export function addTown(map: LocationMap, state: string, town: string): { map: LocationMap; error?: string } {
  const t = town.trim().replace(/\s+/g, ' ')
  if (!t) return { map, error: 'Type a town or area first.' }
  const towns = map[state] ?? []
  if (towns.some((x) => same(x, t))) return { map, error: `${t} is already in ${state}.` }
  return { map: { ...map, [state]: [...towns, t] } }
}

export function removeTown(map: LocationMap, state: string, town: string): LocationMap {
  return { ...map, [state]: (map[state] ?? []).filter((x) => x !== town) }
}

/** Every state that lists this town (case-insensitive), for "also in …" labels. */
export function statesWith(map: LocationMap, town: string): string[] {
  return Object.keys(map).filter((s) => map[s].some((x) => same(x, town)))
}

/** Towns matching a search, across all states, as [state, town] pairs in map order. */
export function findTowns(map: LocationMap, query: string): { state: string; town: string }[] {
  const q = query.trim().toLowerCase()
  if (!q) return []
  return Object.entries(map).flatMap(([state, towns]) => towns.filter((t) => t.toLowerCase().includes(q)).map((town) => ({ state, town })))
}

/** One state back to its default towns (a state with no default keeps its towns). */
export function resetState(map: LocationMap, defaults: LocationMap, state: string): LocationMap {
  return state in defaults ? { ...map, [state]: [...defaults[state]] } : map
}

/** Add a new, empty state (or area such as a federal territory). Rejects an empty name or one already listed (any case). */
export function addState(map: LocationMap, state: string): { map: LocationMap; error?: string } {
  const s = state.trim().replace(/\s+/g, ' ')
  if (!s) return { map, error: 'Type a state name first.' }
  const existing = Object.keys(map).find((x) => same(x, s))
  if (existing) return { map, error: `${existing} is already in the map.` }
  return { map: { ...map, [s]: [] } }
}
