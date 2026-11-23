import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Search, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { Skill } from '@/api/types'
import { ErrorText, Field, NativeSelect } from '@/components/common'
import { useToast } from '@/lib/toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { skillCategories, visibleSkills, type SkillSort } from '@/lib/skills'
import { useRestoreFocus } from '@/lib/hooks'
import { cn } from '@/lib/utils'

type Draft = Omit<Skill, 'id'> & { id?: number }
const EMPTY: Draft = { name: '', category: 'other', aliases: [] }

/** Settings → Skill dictionary: a searchable, sortable table; one skill is edited at a time in the side panel. */
export default function SkillDictionary({ onChanged }: { onChanged: () => void }) {
  const q = useQuery({ queryKey: ['skills'], queryFn: () => api.get<Skill[]>('/api/skills') })
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [sort, setSort] = useState<{ key: SkillSort; desc: boolean }>({ key: 'name', desc: false })
  const [draft, setDraft] = useState<Draft | null>(null)
  const all = useMemo(() => q.data ?? [], [q.data])
  const rows = useMemo(() => visibleSkills(all, query, category, sort.key, sort.desc), [all, query, category, sort])
  const categories = useMemo(() => skillCategories(all), [all])
  const sortBy = (key: SkillSort) => setSort((s) => ({ key, desc: s.key === key ? !s.desc : false }))

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input type="search" aria-label="Search skills and aliases" placeholder="Search skills and aliases" value={query}
            onChange={(e) => setQuery(e.target.value)} className="w-64 pl-8" />
        </label>
        <NativeSelect label="Category" value={category} onChange={setCategory}
          options={[{ value: '', label: 'All categories' }, ...categories.map((c) => ({ value: c, label: c }))]} />
        <span className="text-sm text-muted-foreground tabular-nums">{rows.length} of {all.length}</span>
        <Button className="ml-auto" onClick={() => setDraft({ ...EMPTY })}>Add skill</Button>
      </div>
      <ErrorText error={q.error} />
      <div className={cn('grid items-start gap-4', draft && 'lg:grid-cols-[minmax(0,1fr)_22rem]')}>
        <div className="overflow-hidden rounded-lg border bg-background">
          <table className="w-full table-fixed text-[15px]">
            <colgroup><col className="w-[42%]" /><col className="w-[18%]" /><col /></colgroup>
            <thead className="border-b text-left text-sm text-muted-foreground">
              <tr>
                <SortHead label="Name" active={sort.key === 'name'} desc={sort.desc} onClick={() => sortBy('name')} />
                <SortHead label="Category" active={sort.key === 'category'} desc={sort.desc} onClick={() => sortBy('category')} />
                <th scope="col" className="px-4 py-2 font-medium">Aliases</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id} onClick={() => setDraft(s)}
                  className={cn('cursor-pointer border-t align-top first:border-t-0 hover:bg-muted', draft?.id === s.id && 'bg-selected hover:bg-selected')}>
                  <td className="px-4 py-2 break-words">
                    <button type="button" className="text-left font-medium" aria-label={`Edit ${s.name}`}
                      onClick={(e) => { e.stopPropagation(); setDraft(s) }}>{s.name}</button>
                  </td>
                  <td className="px-4 py-2"><span className="rounded-sm bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">{s.category || 'other'}</span></td>
                  <td className="truncate px-4 py-2 text-muted-foreground" title={s.aliases.join(', ') || undefined}>
                    {s.aliases.join(', ') || '–'}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={3} className="px-4 py-6 text-center text-muted-foreground">No skills match. Try another search, or add it.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {draft && <Panel key={draft.id ?? 'new'} initial={draft} categories={categories} onClose={() => setDraft(null)} onChanged={onChanged} />}
      </div>
    </div>
  )
}

function SortHead({ label, active, desc, onClick }: { label: string; active: boolean; desc: boolean; onClick: () => void }) {
  const Icon = desc ? ArrowDown : ArrowUp
  return (
    <th scope="col" aria-sort={active ? (desc ? 'descending' : 'ascending') : 'none'} className="px-4 py-2 font-medium">
      <button type="button" className={cn('flex items-center gap-1 hover:text-foreground', active && 'text-foreground')} onClick={onClick}>
        {label}{active && <Icon className="size-3.5" aria-hidden />}
      </button>
    </th>
  )
}

/** The side panel: name, category, aliases as chips. Saving rescores every job (the matcher uses the dictionary). */
function Panel({ initial, categories, onClose, onChanged }: {
  initial: Draft; categories: string[]; onClose: () => void; onChanged: () => void
}) {
  const qc = useQueryClient()
  const toast = useToast()
  const [s, setS] = useState<Draft>(initial)
  const [alias, setAlias] = useState('')
  const [aliasError, setAliasError] = useState('')
  useRestoreFocus() // must run before the panel takes focus, so it remembers the opener
  const nameRef = useRef<HTMLInputElement>(null)
  useEffect(() => nameRef.current?.focus(), [])
  const isNew = initial.id === undefined
  const done = (message: string) => { qc.invalidateQueries({ queryKey: ['skills'] }); onChanged(); toast({ message }); onClose() }
  const save = useMutation({
    mutationFn: () => (isNew ? api.post('/api/skills', s) : api.put(`/api/skills/${initial.id}`, s)),
    onSuccess: () => done(isNew ? `Added ${s.name.trim()}. Jobs rescored.` : `Saved ${s.name.trim()}. Jobs rescored.`),
  })
  const del = useMutation({ mutationFn: () => api.del(`/api/skills/${initial.id}`), onSuccess: () => done(`Deleted ${initial.name}.`) })
  const addAlias = () => {
    const a = alias.trim()
    if (!a) return
    if ([s.name, ...s.aliases].some((x) => x.toLowerCase() === a.toLowerCase())) { setAliasError(`${a} is already listed.`); return }
    setS({ ...s, aliases: [...s.aliases, a] })
    setAlias('')
    setAliasError('')
  }
  return (
    <aside aria-label={isNew ? 'Add a skill' : `Edit ${initial.name}`} className="flex flex-col gap-4 rounded-lg border bg-background p-4 lg:sticky lg:top-4"
      onKeyDown={(e) => e.key === 'Escape' && onClose()}>
      <div className="flex items-center justify-between">
        <h3 className="font-heading text-lg font-semibold">{isNew ? 'Add a skill' : 'Edit skill'}</h3>
        <Button size="icon-sm" variant="ghost" aria-label="Close" onClick={onClose}><X className="size-4" aria-hidden /></Button>
      </div>
      <Field label="Name"><Input ref={nameRef} value={s.name} onChange={(e) => setS({ ...s, name: e.target.value })} /></Field>
      <Field label="Category">
        <NativeSelect value={s.category} onChange={(v) => setS({ ...s, category: v })} options={categories} />
      </Field>
      <div className="flex flex-col gap-1.5">
        <span id="aliases-label" className="text-sm font-medium text-muted-foreground">Other names for it</span>
        {s.aliases.length > 0 && (
          <ul aria-labelledby="aliases-label" className="flex flex-wrap gap-1.5">
            {s.aliases.map((a) => (
              <li key={a} className="inline-flex items-center gap-1 rounded-sm bg-selected py-0.5 pr-1 pl-2 text-sm">
                {a}
                <button type="button" className="rounded-sm p-0.5 hover:bg-foreground/10" aria-label={`Remove ${a}`}
                  onClick={() => setS({ ...s, aliases: s.aliases.filter((x) => x !== a) })}><X className="size-3.5" aria-hidden /></button>
              </li>
            ))}
          </ul>
        )}
        <div className="flex gap-2">
          <Input aria-labelledby="aliases-label" placeholder="Add a name, then Enter" value={alias} onChange={(e) => { setAlias(e.target.value); setAliasError('') }}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addAlias() } }} />
          <Button variant="outline" onClick={addAlias} disabled={!alias.trim()}>Add</Button>
        </div>
        {aliasError && <p className="text-sm text-danger">{aliasError}</p>}
        <p className="text-sm text-muted-foreground">The matcher finds the skill by any of these names, as whole words.</p>
      </div>
      <ErrorText error={save.error || del.error} />
      <div className="flex items-center gap-2 border-t pt-3">
        {!isNew && (
          <Button variant="ghost" className="text-danger hover:bg-danger-bg hover:text-danger" disabled={del.isPending}
            onClick={() => confirm(`Delete the skill ${initial.name}? Jobs are rescored without it.`) && del.mutate()}>Delete</Button>
        )}
        <Button variant="ghost" className="ml-auto" onClick={onClose}>Cancel</Button>
        <Button disabled={!s.name.trim() || save.isPending} onClick={() => save.mutate()}>{isNew ? 'Add skill' : 'Save'}</Button>
      </div>
    </aside>
  )
}
