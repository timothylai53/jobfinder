import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { BaseResume, ExperienceItem } from '@/api/types'
import { ErrorText } from '@/components/common'
import { useToast } from '@/components/Toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { groupItems, toggleGroup, typeSummary } from '@/lib/baseResumes'
import { formatDate } from '@/lib/score'

const PURPOSE = 'A base resume is a starting set of bank items: one for software roles, one for IT support.'

/** Base resumes on the Resume page: a list (one row each), and an editor that picks bank items by group. */
export default function BaseResumes({ items }: { items: ExperienceItem[] }) {
  const qc = useQueryClient()
  const toast = useToast()
  const resumes = useQuery({ queryKey: ['resumes'], queryFn: () => api.get<BaseResume[]>('/api/resumes') })
  const [editing, setEditing] = useState<number | null>(null)
  const [hidden, setHidden] = useState<Set<number>>(new Set()) // deleted, waiting for Undo
  const [creating, setCreating] = useState(false)
  const refresh = () => qc.invalidateQueries({ queryKey: ['resumes'] })
  const create = useMutation({
    mutationFn: (name: string) => api.post<{ id: number }>('/api/resumes', { name, item_ids: [] }),
    onSuccess: (r) => { setCreating(false); refresh(); setEditing(r.id) },
  })
  const duplicate = useMutation({
    mutationFn: (r: BaseResume) => api.post<{ id: number; name: string }>(`/api/resumes/${r.id}/duplicate`),
    onSuccess: (c) => { refresh(); toast({ message: `Made a copy: ${c.name}.` }) },
  })
  const remove = (r: BaseResume) => {
    setHidden((h) => new Set(h).add(r.id))
    const show = () => setHidden((h) => { const n = new Set(h); n.delete(r.id); return n })
    toast({
      message: `Deleted ${r.name}. Its bank items stay.`,
      undo: show,
      onExpire: () => { api.del(`/api/resumes/${r.id}`).finally(() => { refresh(); show() }) },
    })
  }
  const list = (resumes.data ?? []).filter((r) => !hidden.has(r.id))
  const current = list.find((r) => r.id === editing)

  return (
    <section aria-labelledby="base-resumes" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="base-resumes" className="text-lg font-semibold">Base resumes</h2>
          <p className="text-sm text-muted-foreground">{PURPOSE}</p>
        </div>
        {!current && !creating && <Button variant="outline" onClick={() => setCreating(true)}>New base resume</Button>}
      </div>
      <ErrorText error={resumes.error || create.error || duplicate.error} />
      {current ? (
        <Editor resume={current} items={items} onClose={() => setEditing(null)} />
      ) : (
        <>
          {creating && (
            <NameForm label="Name for the new base resume" initial="" submit="Create" pending={create.isPending}
              onSubmit={(n) => create.mutate(n)} onCancel={() => setCreating(false)} />
          )}
          {list.length === 0 && !creating ? (
            <div className="rounded-lg border bg-background px-5 py-5">
              <p>No base resumes yet. Make one for each kind of role you apply for.</p>
            </div>
          ) : list.length > 0 && (
            <ul className="divide-y rounded-lg border bg-background">
              {list.map((r) => (
                <Row key={r.id} resume={r} items={items} onEdit={() => setEditing(r.id)} onDuplicate={() => duplicate.mutate(r)} onDelete={() => remove(r)} />
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  )
}

function Row({ resume, items, onEdit, onDuplicate, onDelete }: {
  resume: BaseResume; items: ExperienceItem[]; onEdit: () => void; onDuplicate: () => void; onDelete: () => void
}) {
  const qc = useQueryClient()
  const [renaming, setRenaming] = useState(false)
  const rename = useMutation({
    mutationFn: (name: string) => api.put(`/api/resumes/${resume.id}`, { name, item_ids: resume.item_ids }),
    onSuccess: () => { setRenaming(false); qc.invalidateQueries({ queryKey: ['resumes'] }) },
  })
  const chosen = items.filter((i) => resume.item_ids.includes(i.id))
  return (
    <li className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3.5">
      <div className="min-w-0 flex-1 basis-72">
        {renaming ? (
          <>
            <NameForm label={`New name for ${resume.name}`} initial={resume.name} submit="Save name" pending={rename.isPending}
              onSubmit={(n) => rename.mutate(n)} onCancel={() => setRenaming(false)} />
            <ErrorText error={rename.error} />
          </>
        ) : (
          <>
            <p className="font-medium">{resume.name}</p>
            <p className="text-sm text-muted-foreground">{typeSummary(chosen)}</p>
          </>
        )}
      </div>
      <dl className="flex gap-6 text-sm">
        <div><dt className="text-muted-foreground">Items</dt><dd className="tabular-nums">{chosen.length}</dd></div>
        <div><dt className="text-muted-foreground">Last changed</dt><dd>{formatDate(resume.updated_at)}</dd></div>
      </dl>
      {!renaming && (
        <div className="flex items-center gap-1">
          <Button size="sm" variant="outline" onClick={onEdit} aria-label={`Edit ${resume.name}`}>Edit</Button>
          <Button size="sm" variant="ghost" onClick={() => setRenaming(true)} aria-label={`Rename ${resume.name}`}>Rename</Button>
          <Button size="sm" variant="ghost" onClick={onDuplicate} aria-label={`Duplicate ${resume.name}`}>Duplicate</Button>
          <Button size="sm" variant="ghost" className="text-danger hover:bg-danger-bg hover:text-danger" onClick={onDelete}
            aria-label={`Delete ${resume.name}`}>Delete</Button>
        </div>
      )}
    </li>
  )
}

function NameForm({ label, initial, submit, pending, onSubmit, onCancel }: {
  label: string; initial: string; submit: string; pending: boolean; onSubmit: (name: string) => void; onCancel: () => void
}) {
  const [name, setName] = useState(initial)
  return (
    <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (name.trim()) onSubmit(name.trim()) }}>
      <Input autoFocus aria-label={label} placeholder="e.g. Software roles" value={name} onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === 'Escape' && onCancel()} className="w-72" />
      <Button type="submit" size="sm" disabled={!name.trim() || pending}>{submit}</Button>
      <Button type="button" size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
    </form>
  )
}

/** Pick bank items for one base resume: grouped by type, with select-all per group, a search box and one Save. */
function Editor({ resume, items, onClose }: { resume: BaseResume; items: ExperienceItem[]; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [selected, setSelected] = useState(() => new Set(resume.item_ids))
  const [query, setQuery] = useState('')
  const groups = useMemo(() => groupItems(items, query), [items, query])
  const dirty = selected.size !== resume.item_ids.length || resume.item_ids.some((id) => !selected.has(id))
  const save = useMutation({
    mutationFn: () => api.put(`/api/resumes/${resume.id}`, { name: resume.name, item_ids: items.filter((i) => selected.has(i.id)).map((i) => i.id) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['resumes'] }); toast({ message: `Saved ${resume.name}.` }); onClose() },
  })
  const close = () => (!dirty || confirm('Leave without saving your changes?')) && onClose()
  return (
    <div className="rounded-lg border bg-background">
      <div className="flex flex-wrap items-center gap-3 border-b px-5 py-3">
        <Button size="sm" variant="ghost" onClick={close}><ArrowLeft className="size-4" aria-hidden /> All base resumes</Button>
        <h3 className="min-w-0 flex-1 font-heading text-lg font-semibold">{resume.name}</h3>
        <label className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input type="search" aria-label="Search bank items" placeholder="Search items" value={query} onChange={(e) => setQuery(e.target.value)} className="w-64 pl-8" />
        </label>
      </div>
      <div className="flex flex-col gap-6 px-5 py-4">
        {items.length === 0 && <p className="text-muted-foreground">Your Experience Bank is empty. Upload a resume or add items above first.</p>}
        {items.length > 0 && groups.length === 0 && <p className="text-muted-foreground">No items match “{query}”.</p>}
        {groups.map((g) => <Group key={g.type} label={g.label} items={g.items} selected={selected} onChange={setSelected} />)}
      </div>
      <div className="sticky bottom-0 flex flex-wrap items-center gap-3 rounded-b-lg border-t bg-background px-5 py-3">
        <p className="flex-1 text-sm" aria-live="polite">
          <span className="font-medium tabular-nums">{selected.size}</span> of {items.length} items selected
          {dirty && <span className="text-muted-foreground"> · unsaved changes</span>}
        </p>
        <ErrorText error={save.error} />
        <Button variant="ghost" onClick={close}>Cancel</Button>
        <Button disabled={!dirty || save.isPending} onClick={() => save.mutate()}>Save</Button>
      </div>
    </div>
  )
}

function Group({ label, items, selected, onChange }: {
  label: string; items: ExperienceItem[]; selected: Set<number>; onChange: (s: Set<number>) => void
}) {
  const ids = items.map((i) => i.id)
  const count = ids.filter((id) => selected.has(id)).length
  const all = useRef<HTMLInputElement>(null)
  useEffect(() => { if (all.current) all.current.indeterminate = count > 0 && count < ids.length }, [count, ids.length])
  const id = `group-${label.toLowerCase()}`
  return (
    <fieldset aria-labelledby={id}>
      <div className="mb-1.5 flex items-center gap-3 border-b pb-1.5">
        <h4 id={id} className="flex-1 font-semibold">{label} <span className="font-normal text-muted-foreground tabular-nums">{count}/{ids.length}</span></h4>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input ref={all} type="checkbox" className="size-4 accent-foreground" checked={count === ids.length} onChange={(e) => onChange(toggleGroup(selected, ids, e.target.checked))} />
          Select all in {label}
        </label>
      </div>
      <ul>
        {items.map((it) => (
          <li key={it.id}>
            <label className="flex cursor-pointer items-start gap-3 rounded-md px-2 py-1.5 hover:bg-muted">
              <input type="checkbox" className="mt-1 size-4 accent-foreground" checked={selected.has(it.id)}
                onChange={(e) => onChange(toggleGroup(selected, [it.id], e.target.checked))} />
              <span className="min-w-0 flex-1">
                <span className="font-medium">{it.title}</span>
                {it.organization && <span className="text-muted-foreground"> · {it.organization}</span>}
                {(it.start || it.end) && <span className="block text-sm text-muted-foreground">{[it.start, it.end].filter(Boolean).join(' – ')}</span>}
              </span>
              <span className="text-xs text-muted-foreground tabular-nums">{it.code}</span>
            </label>
          </li>
        ))}
      </ul>
    </fieldset>
  )
}
