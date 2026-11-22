import { Check, ChevronDown, X } from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { cn } from '@/lib/utils'
import { buildOptions, type LocationOption } from '@/lib/locations'

/**
 * Searchable multi-select over the state -> towns map. Picking a state covers all its towns
 * (towns already picked inside it are folded into the state). "Remote" is its own option.
 */
export default function LocationPicker({
  value,
  onChange,
  locationMap,
}: {
  value: string[]
  onChange: (v: string[]) => void
  locationMap: Record<string, string[]>
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const root = useRef<HTMLDivElement>(null)
  const listId = useId()

  const selected = useMemo(() => new Set(value.map((v) => v.toLowerCase())), [value])
  const options = useMemo(() => buildOptions(locationMap, query), [locationMap, query])
  const stateOf = useMemo(() => {
    const m = new Map<string, string>()
    for (const [s, towns] of Object.entries(locationMap)) for (const t of towns) m.set(t.toLowerCase(), s)
    return m
  }, [locationMap])

  useEffect(() => {
    const close = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  useEffect(() => setActive(0), [query])

  const coveredByState = (o: LocationOption) => o.kind === 'town' && selected.has(o.state.toLowerCase())

  const toggle = (o: LocationOption) => {
    if (coveredByState(o)) return
    const key = o.value.toLowerCase()
    if (selected.has(key)) return onChange(value.filter((v) => v.toLowerCase() !== key))
    if (o.kind === 'state') {
      const towns = new Set((locationMap[o.value] ?? []).map((t) => t.toLowerCase()))
      return onChange([...value.filter((v) => !towns.has(v.toLowerCase())), o.value])
    }
    onChange([...value, o.value])
  }

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActive((a) => Math.min(a + 1, options.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'Enter' && open && options[active]) {
      e.preventDefault()
      toggle(options[active])
    } else if (e.key === 'Escape') {
      setOpen(false)
    } else if (e.key === 'Backspace' && !query && value.length) {
      onChange(value.slice(0, -1))
    }
  }

  return (
    <div ref={root} className="relative">
      <div
        className={cn(
          'flex min-h-10 flex-wrap items-center gap-1.5 rounded-lg border border-input bg-background px-2 py-1.5',
          open && 'border-ring ring-2 ring-ring/20',
        )}
        onClick={() => setOpen(true)}
      >
        {value.map((v) => {
          const parent = stateOf.get(v.toLowerCase())
          return (
            <span key={v} className="inline-flex items-center gap-1 rounded-md bg-selected py-0.5 pr-1 pl-2.5 text-sm text-foreground">
              {v}
              {locationMap[v] && <span className="text-xs opacity-75">whole state</span>}
              {parent && <span className="text-xs opacity-75">{parent}</span>}
              <button
                type="button"
                aria-label={`Remove ${v}`}
                className="rounded-sm p-0.5 hover:bg-foreground/10"
                onClick={(e) => {
                  e.stopPropagation()
                  onChange(value.filter((x) => x !== v))
                }}
              >
                <X className="size-3.5" />
              </button>
            </span>
          )
        })}
        <input
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-label="Search states and towns"
          className="min-w-40 flex-1 bg-transparent px-1 py-0.5 text-[15px] outline-none placeholder:text-muted-foreground"
          placeholder={value.length ? 'Add another…' : 'Search a state or town, e.g. Selangor, Cyberjaya, Remote'}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKey}
        />
        <ChevronDown className="size-4 text-muted-foreground" />
      </div>

      {open && (
        <ul
          id={listId}
          role="listbox"
          aria-multiselectable
          className="absolute z-30 mt-1 max-h-80 w-full overflow-y-auto rounded-lg border bg-popover py-1 shadow-lg"
        >
          {options.length === 0 && <li className="px-3 py-2 text-sm text-muted-foreground">No state or town matches “{query}”.</li>}
          {options.map((o, i) => {
            const covered = coveredByState(o)
            const isSel = selected.has(o.value.toLowerCase()) || covered
            return (
              <li
                key={`${o.kind}:${o.state}:${o.value}`}
                role="option"
                aria-selected={isSel}
                aria-disabled={covered}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => {
                  e.preventDefault()
                  toggle(o)
                }}
                className={cn(
                  'flex cursor-pointer items-center gap-2 px-3 py-1.5 text-[15px]',
                  o.kind === 'town' && 'pl-8',
                  o.kind === 'state' && 'mt-1 font-medium first:mt-0',
                  i === active && 'bg-muted',
                  covered && 'cursor-default text-muted-foreground',
                )}
              >
                <span className={cn('flex size-4 items-center justify-center rounded border', isSel ? 'border-foreground bg-foreground text-background' : 'border-input')}>
                  {isSel && <Check className="size-3" />}
                </span>
                <span className="flex-1">{o.value}</span>
                {o.kind === 'state' && <span className="text-xs text-muted-foreground">all {o.count} towns</span>}
                {covered && <span className="text-xs">included in {o.state}</span>}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
