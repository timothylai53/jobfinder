import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { FilterRule } from '@/api/types'
import { ErrorText, Field } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { FILTER_TYPES, ruleSentence } from '@/lib/filters'
import { useToast } from '@/lib/toast'
import { useRestoreFocus } from '@/lib/hooks'
import { cn } from '@/lib/utils'

type Draft = Omit<FilterRule, 'id' | 'action'> & { id?: number }

/** Settings → Filter rules: each rule as one plain sentence with an on/off switch; edited one at a time in a side panel. */
export default function FilterRules({ onChanged }: { onChanged: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['filters'], queryFn: () => api.get<FilterRule[]>('/api/filters') })
  const [draft, setDraft] = useState<Draft | null>(null)
  const [hidden, setHidden] = useState<Set<number>>(new Set()) // deleted, waiting for Undo
  const refresh = () => { qc.invalidateQueries({ queryKey: ['filters'] }); onChanged() }
  const toggle = useMutation({
    mutationFn: (r: FilterRule) => api.put(`/api/filters/${r.id}`, { type: r.type, value: r.value, enabled: !r.enabled }),
    onSuccess: refresh,
  })
  const remove = (r: FilterRule) => {
    if (draft?.id === r.id) setDraft(null)
    setHidden((h) => new Set(h).add(r.id))
    const show = () => setHidden((h) => { const n = new Set(h); n.delete(r.id); return n })
    toast({
      message: 'Rule deleted. Jobs are rechecked.',
      undo: show,
      onExpire: () => { api.del(`/api/filters/${r.id}`).finally(() => { refresh(); show() }) },
    })
  }
  const rules = (q.data ?? []).filter((r) => !hidden.has(r.id))

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">Rules re-check every job when you change them. Jobs you hid or unhid by hand are left alone.</p>
        <Button onClick={() => setDraft({ type: 'title_contains', value: '', enabled: true })}>Add rule</Button>
      </div>
      <ErrorText error={q.error || toggle.error} />
      <div className={cn('grid items-start gap-4', draft && 'lg:grid-cols-[minmax(0,1fr)_22rem]')}>
        {rules.length > 0 ? (
          <ul className="divide-y rounded-lg border bg-background">
            {rules.map((r) => (
              <li key={r.id} className={cn('flex flex-wrap items-center gap-3 px-4 py-3', draft?.id === r.id && 'bg-selected')}>
                <input type="checkbox" className="size-4 shrink-0 accent-foreground" checked={r.enabled}
                  aria-label={`Use the rule: ${ruleSentence(r)}`} onChange={() => toggle.mutate(r)} />
                <span className={cn('min-w-0 flex-1 break-words', !r.enabled && 'text-muted-foreground')}>
                  {ruleSentence(r)}{!r.enabled && <span className="text-sm"> (off)</span>}
                </span>
                <Button size="sm" variant="outline" aria-label={`Edit the rule: ${ruleSentence(r)}`}
                  onClick={() => setDraft({ id: r.id, type: r.type, value: r.value, enabled: r.enabled })}>Edit</Button>
                <Button size="sm" variant="ghost" className="text-danger hover:bg-danger-bg hover:text-danger"
                  aria-label={`Delete the rule: ${ruleSentence(r)}`} onClick={() => remove(r)}>Delete</Button>
              </li>
            ))}
          </ul>
        ) : (
          q.data && <p className="rounded-lg border bg-background px-4 py-5">No rules yet. Add one to hide jobs you never want to see.</p>
        )}
        {draft && <Panel key={draft.id ?? 'new'} initial={draft} onClose={() => setDraft(null)} onSaved={refresh} />}
      </div>
    </div>
  )
}

function Panel({ initial, onClose, onSaved }: { initial: Draft; onClose: () => void; onSaved: () => void }) {
  const toast = useToast()
  const [r, setR] = useState<Draft>(initial)
  useRestoreFocus() // must run before the panel takes focus, so it remembers the opener
  const first = useRef<HTMLSelectElement>(null)
  useEffect(() => first.current?.focus(), [])
  const isNew = initial.id === undefined
  const type = FILTER_TYPES.find((t) => t.value === r.type)!
  const invalid = !r.value.trim() || (type.numeric && Number.isNaN(Number(r.value)))
  const save = useMutation({
    mutationFn: () => {
      const body = { type: r.type, value: r.value.trim(), enabled: r.enabled }
      return isNew ? api.post('/api/filters', body) : api.put(`/api/filters/${initial.id}`, body)
    },
    onSuccess: () => { onSaved(); toast({ message: isNew ? 'Rule added. Jobs rechecked.' : 'Rule saved. Jobs rechecked.' }); onClose() },
  })
  return (
    <aside aria-label={isNew ? 'Add a rule' : 'Edit rule'} className="flex flex-col gap-4 rounded-lg border bg-background p-4 lg:sticky lg:top-4"
      onKeyDown={(e) => e.key === 'Escape' && onClose()}>
      <div className="flex items-center justify-between">
        <h3 className="font-heading text-lg font-semibold">{isNew ? 'Add a rule' : 'Edit rule'}</h3>
        <Button size="icon-sm" variant="ghost" aria-label="Close" onClick={onClose}><X className="size-4" aria-hidden /></Button>
      </div>
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium text-muted-foreground">Hide jobs when</span>
        <select ref={first} value={r.type} onChange={(e) => setR({ ...r, type: e.target.value as FilterRule['type'] })}
          className="h-9 rounded-lg border border-input bg-background px-2 text-[15px]">
          {FILTER_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </label>
      <Field label={type.numeric ? 'Number' : 'Words'}>
        <Input inputMode={type.numeric ? 'numeric' : undefined} value={r.value} onChange={(e) => setR({ ...r, value: e.target.value })} />
      </Field>
      <p className="text-sm text-muted-foreground">{type.hint}</p>
      {r.value.trim() && <p className="rounded-md bg-muted px-3 py-2 text-sm">{ruleSentence(r)}</p>}
      <ErrorText error={save.error} />
      <div className="flex items-center justify-end gap-2 border-t pt-3">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button disabled={invalid || save.isPending} onClick={() => save.mutate()}>{isNew ? 'Add rule' : 'Save'}</Button>
      </div>
    </aside>
  )
}
