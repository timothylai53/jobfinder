import { useMutation, useQuery } from '@tanstack/react-query'
import { ChevronRight, Search, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api } from '@/api/client'
import type { Settings as SettingsT } from '@/api/types'
import { ErrorText } from '@/components/common'
import { useToast } from '@/components/Toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { addTown, findTowns, mapToText, removeTown, resetState, statesWith, textToMap, type LocationMap } from '@/lib/locations'
import { cn } from '@/lib/utils'

/** Settings → Location map: one collapsible section per state, towns as chips. Changes stay local until Save,
 * which rescores every job. A plain-text view for bulk edits sits under Advanced. */
export default function LocationMapEditor({ onSaved }: { onSaved: () => void }) {
  const toast = useToast()
  const q = useQuery({ queryKey: ['settings'], queryFn: () => api.get<SettingsT>('/api/settings') })
  const defaults = useQuery({ queryKey: ['locations-defaults'], queryFn: () => api.get<LocationMap>('/api/settings/locations/defaults') })
  // Local edits; null means "no changes: show what is saved". A background refetch never wipes unsaved edits.
  const [edited, setMap] = useState<LocationMap | null>(null)
  const [open, setOpen] = useState<Set<string>>(new Set())
  const [query, setQuery] = useState('')
  const saved = q.data?.locations
  const map = useMemo(() => edited ?? saved ?? {}, [edited, saved])
  const dirty = edited !== null && JSON.stringify(saved) !== JSON.stringify(edited)
  const save = useMutation({
    mutationFn: () => api.put('/api/settings', { ...q.data!, locations: map }),
    onSuccess: () => { onSaved(); setMap(null); toast({ message: 'Location map saved. Jobs rescored.' }) },
  })
  // Every change goes through here, so each one can be undone from its toast.
  const change = (next: LocationMap, message: string) => {
    const before = edited
    setMap(next)
    toast({ message, undo: () => setMap(before) })
  }
  const hits = useMemo(() => findTowns(map, query), [map, query])
  const hitStates = useMemo(() => new Set(hits.map((h) => h.state)), [hits])
  // While searching, only the states that have a matching town are listed (already open, matches highlighted).
  const states = Object.keys(map).filter((st) => !query.trim() || hitStates.has(st))

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <label className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input type="search" aria-label="Find a town or area" placeholder="Find a town or area" value={query}
            onChange={(e) => setQuery(e.target.value)} className="w-64 pl-8" />
        </label>
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {query.trim() && (hits.length === 0 ? `No town matches “${query.trim()}”.`
            : `Found in ${[...hitStates].join(', ')}.`)}
        </p>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="ghost" disabled={!defaults.data}
            onClick={() => defaults.data && change({ ...defaults.data }, 'Every state reset to its default towns.')}>Reset all to default</Button>
        </div>
      </div>
      <ErrorText error={q.error || defaults.error} />

      <ul className="divide-y rounded-lg border bg-background empty:hidden">
        {states.map((state) => {
          const expanded = open.has(state) || (query.trim() !== '' && hitStates.has(state))
          const toggle = () => setOpen((o) => { const n = new Set(o); if (n.has(state)) n.delete(state); else n.add(state); return n })
          return (
            <li key={state}>
              <h3>
                <button type="button" aria-expanded={expanded} onClick={toggle}
                  className="flex w-full items-center gap-2 px-4 py-2.5 text-left hover:bg-muted">
                  <ChevronRight className={cn('size-4 shrink-0 text-muted-foreground transition-transform', expanded && 'rotate-90')} aria-hidden />
                  <span className="flex-1 font-medium">{state}</span>
                  <span className="text-sm text-muted-foreground tabular-nums">{map[state].length} {map[state].length === 1 ? 'town' : 'towns'}</span>
                </button>
              </h3>
              {expanded && (
                <StateTowns state={state} map={map} query={query} hasDefault={!!defaults.data && state in defaults.data}
                  onAdd={(town) => {
                    const r = addTown(map, state, town)
                    if (!r.error) setMap(r.map)
                    return r.error
                  }}
                  onRemove={(town) => change(removeTown(map, state, town), `Removed ${town} from ${state}.`)}
                  onReset={() => defaults.data && change(resetState(map, defaults.data, state), `${state} reset to its default towns.`)} />
              )}
            </li>
          )
        })}
        {Object.keys(map).length === 0 && q.data && <li className="px-4 py-5 text-muted-foreground">No states yet. Reset to the defaults, or add them under Advanced.</li>}
      </ul>

      <details className="rounded-lg border bg-background">
        <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium select-none hover:bg-muted">Advanced: import or export as text</summary>
        <TextView key={mapToText(map)} map={map} onApply={(next) => change(next, 'Text applied to the location map.')} />
      </details>

      <div className="sticky bottom-0 flex items-center justify-end gap-3 border-t bg-fog py-3">
        {dirty && <span className="text-sm text-muted-foreground">Unsaved changes</span>}
        <ErrorText error={save.error} />
        <Button variant="ghost" disabled={!dirty} onClick={() => setMap(null)}>Discard changes</Button>
        <Button disabled={!dirty || save.isPending} onClick={() => save.mutate()}>Save and rescore</Button>
      </div>
    </div>
  )
}

function StateTowns({ state, map, query, hasDefault, onAdd, onRemove, onReset }: {
  state: string; map: LocationMap; query: string; hasDefault: boolean
  onAdd: (town: string) => string | undefined; onRemove: (town: string) => void; onReset: () => void
}) {
  const [town, setTown] = useState('')
  const [error, setError] = useState('')
  const q = query.trim().toLowerCase()
  const add = () => {
    const e = onAdd(town)
    setError(e ?? '')
    if (!e) setTown('')
  }
  const inputId = `add-town-${state.replace(/\W+/g, '-')}`
  return (
    <div className="flex flex-col gap-3 px-4 pt-1 pb-4 pl-10">
      {map[state].length > 0 ? (
        <ul aria-label={`Towns in ${state}`} className="flex flex-wrap gap-1.5">
          {map[state].map((t) => {
            const also = statesWith(map, t).filter((s) => s !== state)
            const hit = q !== '' && t.toLowerCase().includes(q)
            return (
              <li key={t} className={cn('inline-flex items-center gap-1 rounded-sm bg-selected py-0.5 pr-1 pl-2 text-sm', hit && 'bg-attention-bg text-attention ring-1 ring-attention-edge')}>
                {t}
                {also.length > 0 && <span className="text-xs text-muted-foreground">also in {also.join(', ')}</span>}
                <button type="button" className="rounded-sm p-0.5 hover:bg-foreground/10" aria-label={`Remove ${t} from ${state}`} onClick={() => onRemove(t)}>
                  <X className="size-3.5" aria-hidden />
                </button>
              </li>
            )
          })}
        </ul>
      ) : <p className="text-sm text-muted-foreground">No towns yet.</p>}
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={inputId} className="sr-only">Add a town or area to {state}</label>
        <Input id={inputId} placeholder="Add a town or area, then Enter" value={town} className="w-72"
          onChange={(e) => { setTown(e.target.value); setError('') }}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }} />
        <Button variant="outline" size="sm" disabled={!town.trim()} onClick={add}>Add</Button>
        {hasDefault && <Button variant="ghost" size="sm" className="ml-auto text-muted-foreground" onClick={onReset}>Reset {state} to default</Button>}
      </div>
      {error && <p className="text-sm text-danger" role="alert">{error}</p>}
    </div>
  )
}

/** The old text format, "State: town, town" per line, for bulk edits. Apply replaces the map (with Undo); nothing is saved
 * until Save. */
function TextView({ map, onApply }: { map: LocationMap; onApply: (m: LocationMap) => void }) {
  const [text, setText] = useState(() => mapToText(map))
  const parsed = textToMap(text)
  return (
    <div className="flex flex-col gap-2 border-t px-4 py-3">
      <p className="text-sm text-muted-foreground">
        One state per line, as <code>State: town, town, …</code>. Copy it out to keep a copy, or paste a list in and apply it.
        Matching is whole-word and case-insensitive, so “KL” does not match “Klang”.
      </p>
      <Textarea aria-label="Location map as text" rows={10} className="font-mono text-sm" value={text} onChange={(e) => setText(e.target.value)} />
      <div className="flex justify-end">
        <Button variant="outline" size="sm" disabled={text === mapToText(map) || Object.keys(parsed).length === 0}
          onClick={() => onApply(parsed)}>Apply text ({Object.keys(parsed).length} states)</Button>
      </div>
    </div>
  )
}
